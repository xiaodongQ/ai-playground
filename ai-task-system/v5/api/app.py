"""
V5 REST API — FastAPI 应用
──────────────────────────
基于 FastAPI + uvicorn 的生产级 REST API。

运行方式：
    # 方式 1：直接运行
    python -m v5.api.app

    # 方式 2：uvicorn
    uvicorn v5.api:app --host 0.0.0.0 --port 18792

    # 方式 3：gunicorn
    gunicorn v5.api:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:18792

REST 端点：
    GET  /health                  # 健康检查（无需认证）
    GET  /info                    # 系统信息（无需认证）

    POST /tasks                   # 提交任务
    GET  /tasks                   # 任务列表
    GET  /tasks/{task_id}         # 任务详情
    DELETE /tasks/{task_id}       # 删除任务
    POST /tasks/{task_id}/fail    # 标记失败
    POST /tasks/{task_id}/retry  # 重试任务

    GET  /queue/metrics           # 队列指标

    GET  /workers                 # Worker 列表
    GET  /workers/{worker_id}     # Worker 详情
    POST /workers/{worker_id}/restart  # 重启 Worker

    GET  /supervisor/metrics      # Supervisor 指标

    GET  /metrics                 # Prometheus scrape endpoint（text/plain，无需认证）

认证：
    受保护端点需要 X-API-Key header
    配置环境变量 AI_TASK_API_KEY=key1,key2（逗号分隔多个 key）
    未配置 AI_TASK_API_KEY 时，所有端点无需认证（向后兼容）
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── 尝试延迟导入 optional 依赖 ──────────────────────────────────────────────
try:
    from pydantic import Field
except ImportError:
    raise ImportError("pydantic is required: pip install pydantic")

try:
    import uvicorn
except ImportError:
    raise ImportError("uvicorn is required: pip install uvicorn")

# ── V5 模块 ──────────────────────────────────────────────────────────────────
import sys
_repo_root = str(Path(__file__).parent.parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from v4.core.base import AgentType, ExecutionConfig, AdapterRegistry
from v4.core.router import TaskRouter, RouteResult
from v4.core.session_store import SessionStore
from v5.queue.queue import TaskQueue, TaskPriority, TaskStatus
from v5.worker.pool import WorkerPool, WorkerStatus
from v5.worker.supervisor import Supervisor, HealthStatus
from v5.integration.session_pool import SessionPoolManager
from v5.integration.queue_dispatcher import QueueDispatcher

from .models import (
    HealthResponse, RouteRequest, RouteResponse,
    TaskSubmitRequest, TaskSubmitResponse, TaskDetailResponse, TaskListResponse,
    TaskFailRequest, TaskRetryResponse,
    QueueMetricsResponse,
    WorkerDetailResponse, WorkerListResponse, WorkerRestartResponse,
    SupervisorMetricsResponse,
    SessionResponse, SessionListResponse,
    SessionArchiveResponse, SessionDeleteResponse, SessionStatsResponse,
    TaskPriorityEnum, TaskStatusEnum, WorkerStatusEnum, HealthStatusEnum,
)
from .websocket import (
    get_ws_manager,
    setup_ws_hooks,
    WSEventType,
    WSMessage,
)
from . import websocket as ws_module
from .metrics import (
    registry,
    update_queue_metrics,
    update_worker_metrics,
    update_supervisor_metrics,
    observe_task_duration,
    update_task_counters,
)


# ─── API Key 认证 ────────────────────────────────────────────────────────────

# 环境变量中配置的 API Keys（逗号分隔，支持多个）
_API_KEYS_STR = os.environ.get("AI_TASK_API_KEY", "")
_API_KEYS: set[str] = set(k.strip() for k in _API_KEYS_STR.split(",") if k.strip())

# API Key 模式：无 key 时表示未启用认证（允许匿名访问受保护端点）
_API_AUTH_ENABLED = bool(_API_KEYS)

if not _API_AUTH_ENABLED:
    logging.warning(
        "[AI Task System API] AI_TASK_API_KEY not set — API authentication DISABLED. "
        "All endpoints are accessible without credentials. "
        "Set AI_TASK_API_KEY in your environment to enable authentication."
    )
else:
    logging.info(
        f"[AI Task System API] API authentication ENABLED — {len(_API_KEYS)} key(s) loaded. "
        "Protected endpoints require X-API-Key header."
    )

# FastAPI Security scheme — 在 OpenAPI schema 中声明 X-API-Key
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)] = None,
) -> str | None:
    """FastAPI 依赖项：校验 X-API-Key。

    行为：
    - AI_TASK_API_KEY 未配置 → 不校验（向后兼容），返回 None
    - AI_TASK_API_KEY 配置了 → 必须提供匹配的有效 key
    - 返回已验证的 key（用于审计日志），失败则 raise 401
    """
    if not _API_AUTH_ENABLED:
        return None

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key not in _API_KEYS:
        logging.getLogger("ai_task_system.api.auth").warning(
            "Invalid API key attempt"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


# ─── 路由依赖类型别名（模块级，供 create_app 内部使用）─────────────────────────
# 在 create_app() 执行时求值，此时 require_api_key 已定义
_AuthDep = Annotated[str | None, Depends(require_api_key)]


# ─── 全局状态 ────────────────────────────────────────────────────────────────

class APIState:
    """API 全局单例状态（进程内共享）"""

    def __init__(self):
        self.started_at: float = time.time()
        self._pool:      Optional[WorkerPool] = None
        self._queue:     Optional[TaskQueue]   = None
        self._supervisor: Optional[Supervisor] = None
        self._router:    Optional[TaskRouter]  = None
        self._registry:  Optional[AdapterRegistry] = None
        self._session_store: Optional[SessionStore] = None
        self._session_pool: Optional[SessionPoolManager] = None
        self._dispatcher: Optional[Any] = None  # QueueDispatcher

    @property
    def registry(self) -> AdapterRegistry:
        if self._registry is None:
            self._registry = AdapterRegistry()
        return self._registry

    @property
    def router(self) -> TaskRouter:
        if self._router is None:
            self._router = TaskRouter(self.registry)
        return self._router

    @property
    def queue(self) -> TaskQueue:
        if self._queue is None:
            db_path = Path.home() / ".ai_task_system" / "tasks.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._queue = TaskQueue(db_path=str(db_path))
        return self._queue

    @property
    def pool(self) -> WorkerPool:
        if self._pool is None:
            self._pool = WorkerPool(agent_type="claude", size=2)
            self._pool.start()
        return self._pool

    @property
    def supervisor(self) -> Supervisor:
        if self._supervisor is None:
            self._supervisor = Supervisor(
                self.pool,
                interval=10.0,
                recovery_policy="auto",
            )
            self._supervisor.start()
        return self._supervisor

    @property
    def session_store(self) -> SessionStore:
        if self._session_store is None:
            self._session_store = SessionStore()
        return self._session_store

    @property
    def session_pool(self) -> SessionPoolManager:
        if self._session_pool is None:
            self._session_pool = SessionPoolManager(
                pool=self.pool,         # 触发 pool.start()
                store=self.session_store,
            )
            self._session_pool.start()
        return self._session_pool

    @property
    def dispatcher(self) -> QueueDispatcher:
        if self._dispatcher is None:
            self._dispatcher = QueueDispatcher(
                queue=self.queue,
                pool=self.pool,
                poll_interval=1.0,
                max_concurrent=10,
            )
            self._dispatcher.start()
        return self._dispatcher

    def shutdown(self):
        if self._dispatcher:
            self._dispatcher.stop()
            self._dispatcher = None
        if self._supervisor:
            self._supervisor.stop()
            self._supervisor = None
        if self._session_pool:
            self._session_pool.stop()
            self._session_pool = None
        if self._pool:
            self._pool.stop()
            self._pool = None
        if self._queue:
            self._queue.close()
            self._queue = None
        # 广播系统关闭事件
        try:
            get_ws_manager().broadcast_system("API server shutting down", level="warn")
        except Exception:
            pass

    def uptime(self) -> float:
        return time.time() - self.started_at


_state: Optional[APIState] = None


def get_state() -> APIState:
    global _state
    if _state is None:
        _state = APIState()
    return _state


def _serialize_task(task: Any) -> dict[str, Any]:
    result = {
        "task_id":      task.task_id,
        "status":       TaskStatusEnum(task.status.name.lower() if hasattr(task.status, 'name') else str(task.status)),
        "priority":     TaskPriorityEnum(task.priority.name.lower() if hasattr(task.priority, 'name') else "normal"),
        "payload":      task.payload if isinstance(task.payload, dict) else {},
        "timeout":      task.timeout,
        "max_retries":  task.max_retries,
        "retry_count":  task.retry_count,
        "created_at":   task.created_at,
        "dequeued_at":  getattr(task, "dequeued_at", None),
        "started_at":   getattr(task, "started_at", None),
        "completed_at": getattr(task, "completed_at", None),
        "worker_id":    getattr(task, "worker_id", None),
        "result":       getattr(task, "result", None),
        "error":        getattr(task, "error", None),
        "metadata":     getattr(task, "metadata", None),
    }
    if isinstance(task.payload, dict):
        result["agent"] = task.payload.get("agent")
    return result


def _map_worker(w: Any, monitor: Optional[Any] = None) -> dict[str, Any]:
    health = HealthStatusEnum.UNKNOWN
    cpu = mem = None
    if monitor:
        snap = monitor.get_snapshot(w)
        health = HealthStatusEnum(snap.health_status.name.lower())
        cpu = snap.cpu_percent
        mem = snap.memory_mb

    return {
        "worker_id":       w.worker_id,
        "agent_type":      w.agent_type,
        "status":          WorkerStatusEnum(w.status.name.lower()),
        "task_count":      w.task_count,
        "error_count":     w.error_count,
        "current_task_id": w.current_task_id,
        "started_at":      getattr(w, "started_at", None),
        "last_heartbeat":  getattr(w, "last_heartbeat", None),
        "cpu_percent":     cpu,
        "memory_mb":       mem,
        "health_status":   health,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _state
    _state = APIState()
    # 将 WebSocket 广播接入 pool/supervisor 事件系统
    try:
        # 触发 session_pool 创建（session_pool.start() 在其中调用）
        session_pool = _state.session_pool
        # 启动队列调度器（TaskQueue → WorkerPool）
        dispatcher = _state.dispatcher

        # 等待 workers 真正就绪（避免 Supervisor 首次检测时 workers 还在 STARTING）
        deadline = time.time() + 10.0
        while time.time() < deadline:
            workers_ready = all(
                w.status != WorkerStatus.STARTING
                for w in _state.pool.list_workers()
            )
            if workers_ready:
                break
            time.sleep(0.05)
        else:
            logger.warning("[lifespan] Workers not ready after 10s startup grace")

        # 等待 Supervisor 至少完成一次健康检测
        supervisor_started = False
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if _state.supervisor._started:
                supervisor_started = True
                break
            time.sleep(0.05)

        setup_ws_hooks(_state.pool, _state.supervisor, session_pool)
        get_ws_manager().broadcast_system("API server started", level="info")
    except Exception as e:
        logging.getLogger("ai_task_system.api").warning(f"WebSocket/Dispatcher setup failed: {e}")
    yield
    if _state:
        _state.shutdown()
        _state = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Task System V5 API",
        description=(
            "Production-grade REST API for AI Task System V5 — Worker Pool + Task Queue + Supervisor. "
            "Protected endpoints require X-API-Key header when AI_TASK_API_KEY is configured."
        ),
        version="5.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── WebSocket 路由 ────────────────────────────────────────────────────
    from .websocket import _wss_router
    app.include_router(_wss_router, tags=["WebSocket"])

    # ── 公开端点（无需认证）───────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    def health():
        s = get_state()
        try:
            qm = s.queue.metrics()
            pool_status = s.pool.workers_status() if s._pool else []
        except Exception:
            return HealthResponse(
                status="unhealthy",
                version="5.0.0",
                uptime=s.uptime(),
                workers=0,
                tasks={"pending": 0, "running": 0},
            )
        workers_active = sum(1 for w in pool_status if w["status"] != "stopped")
        return HealthResponse(
            status="ok",
            version="5.0.0",
            uptime=s.uptime(),
            workers=workers_active,
            tasks={
                "pending": qm.pending,
                "running": qm.running,
                "done_today": qm.done_today,
                "dead":    qm.dead_letters,
            },
        )

    @app.get("/info", tags=["System"])
    def info():
        s = get_state()
        return {
            "version":            "5.0.0",
            "uptime":             s.uptime(),
            "auth_enabled":       _API_AUTH_ENABLED,
            "v4_adapters":       [a.agent_type.name.lower() for a in s.registry.get_all()],
            "ws_enabled":        True,
            "ws_session_updates": True,   # 任务完成时自动推送 session 更新
            "ws_connections":     get_ws_manager().connection_count,
        }

    # ── 受保护端点（需要 X-API-Key）──────────────────────────────────────

    # Type alias — 简化路由函数签名
    _AuthDep = Annotated[str | None, Depends(require_api_key)]

    @app.post("/route", response_model=RouteResponse, tags=["Routing"])
    def route(req: RouteRequest, _apikey: _AuthDep):
        """对 prompt 进行分类并路由到最合适的 Agent"""
        s = get_state()
        if req.agent:
            try:
                agent_type = AgentType(req.agent.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unknown agent: {req.agent}")
            task_type = s.router.classify(req.prompt)
            return RouteResponse(
                agent=req.agent,
                task_type=task_type.name,
                confidence=1.0,
                message=f"Forced agent={req.agent}, classified as {task_type.name}",
            )
        result: RouteResult = s.router.route(req.prompt)
        return RouteResponse(
            agent=result.agent.agent_type.value.lower() if result.agent else "none",
            task_type=result.task_type.name if hasattr(result.task_type, 'name') else str(result.task_type),
            confidence=result.confidence,
            message=result.reason,
        )

    @app.post("/tasks", response_model=TaskSubmitResponse, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
    def submit_task(req: TaskSubmitRequest, _apikey: _AuthDep):
        """提交一个新任务到队列"""
        s = get_state()
        if not req.agent:
            route_res = s.router.route(req.prompt)
            agent_str = route_res.agent.name.lower() if hasattr(route_res.agent, 'name') else str(route_res.agent)
        else:
            agent_str = req.agent.lower()

        priority_map = {
            TaskPriorityEnum.CRITICAL: TaskPriority.CRITICAL,
            TaskPriorityEnum.HIGH:     TaskPriority.HIGH,
            TaskPriorityEnum.NORMAL:   TaskPriority.NORMAL,
            TaskPriorityEnum.LOW:      TaskPriority.LOW,
            TaskPriorityEnum.BG:       TaskPriority.BACKGROUND,
        }

        payload = {
            "prompt":   req.prompt,
            "agent":    agent_str,
            "allowed_tools": req.allowed_tools,
            "permission_mode": req.permission_mode,
        }

        task_id = s.queue.submit(
            payload=payload,
            priority=priority_map[req.priority],
            timeout=req.timeout,
            max_retries=req.max_retries,
            retry_delay=req.retry_delay,
        )
        return TaskSubmitResponse(
            task_id=task_id,
            status=TaskStatusEnum.PENDING,
            message=f"Task submitted, agent={agent_str}",
        )

    @app.get("/tasks", response_model=TaskListResponse, tags=["Tasks"])
    def list_tasks(
        _apikey: _AuthDep,
        status_filter: Optional[str] = Query(None, alias="status"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """列出任务（支持分页和状态过滤）"""
        s = get_state()
        if status_filter:
            try:
                st = TaskStatus[status_filter.upper()]
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Unknown status: {status_filter}")
            if st == TaskStatus.PENDING:
                tasks = s.queue.list_pending(limit=limit, offset=offset)
            elif st == TaskStatus.RUNNING:
                tasks = s.queue.list_running(limit=limit)
            elif st == TaskStatus.DEAD:
                tasks = s.queue.list_dead_letters(since=0.0)
            elif st == TaskStatus.DONE:
                tasks = s.queue.list_done(limit=limit, offset=offset)
            else:
                tasks = []
        else:
            tasks = s.queue.list_pending(limit=limit, offset=offset)
            tasks += s.queue.list_running(limit=limit)

        return TaskListResponse(
            tasks=[TaskDetailResponse(**_serialize_task(t)) for t in tasks],
            total=len(tasks),
            page=offset // limit + 1,
            size=limit,
        )

    @app.get("/tasks/{task_id}", response_model=TaskDetailResponse, tags=["Tasks"])
    def get_task(task_id: str, _apikey: _AuthDep):
        """获取任务详情"""
        s = get_state()
        task = s.queue.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return TaskDetailResponse(**_serialize_task(task))

    @app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"])
    def delete_task(task_id: str, _apikey: _AuthDep):
        """删除任务（仅允许 pending/dead 状态）"""
        s = get_state()
        # queue.delete() handles both tasks table (PENDING) and dead_letters (DEAD)
        try:
            deleted = s.queue.delete(task_id)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    @app.post("/tasks/{task_id}/fail", response_model=TaskRetryResponse, tags=["Tasks"])
    def fail_task(task_id: str, req: TaskFailRequest, _apikey: _AuthDep):
        """标记任务失败（可选择重试）"""
        s = get_state()
        task = s.queue.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        s.queue.fail(task_id, error=req.error, retry=req.retry)
        updated = s.queue.get(task_id)
        new_status = updated.status.name.lower() if updated else "failed"
        return TaskRetryResponse(
            task_id=task_id,
            status=TaskStatusEnum(new_status),
            message="Task marked as failed" + (" (retry scheduled)" if req.retry else ""),
        )

    @app.post("/tasks/{task_id}/retry", response_model=TaskRetryResponse, tags=["Tasks"])
    def retry_task(task_id: str, _apikey: _AuthDep):
        """重试一个失败任务（重新入队）"""
        s = get_state()
        task = s.queue.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        if task.status not in (TaskStatus.DEAD, TaskStatus.FAILED):
            raise HTTPException(status_code=409, detail=f"Can only retry DEAD/FAILED tasks, got {task.status.name}")
        new_id = s.queue.submit(
            payload=task.payload,
            priority=task.priority,
            timeout=task.timeout,
            max_retries=task.max_retries,
            retry_delay=task.retry_delay,
        )
        return TaskRetryResponse(
            task_id=new_id,
            status=TaskStatusEnum.PENDING,
            message=f"Retried as new task {new_id}",
        )

    @app.get("/queue/metrics", response_model=QueueMetricsResponse, tags=["Queue"])
    def queue_metrics(_apikey: _AuthDep):
        """获取队列聚合指标"""
        s = get_state()
        m = s.queue.metrics()
        return QueueMetricsResponse(
            pending=m.pending,
            running=m.run_count,
            done_today=m.done_today,
            failed_today=m.failed_today,
            dead_letters=m.dead_letters,
            avg_wait_time=m.avg_wait_time,
            avg_run_time=m.avg_run_time,
        )

    @app.get("/workers", response_model=WorkerListResponse, tags=["Workers"])
    def list_workers(_apikey: _AuthDep):
        """列出所有 Worker"""
        s = get_state()
        workers = s.pool.list_workers()
        monitors = {}
        if s._supervisor is not None:
            monitors = {m.worker_id: m for m in s.supervisor._monitors.values()}
        return WorkerListResponse(
            workers=[
                WorkerDetailResponse(**_map_worker(w, monitors.get(w.worker_id)))
                for w in workers
            ],
            total=len(workers),
        )

    @app.get("/workers/{worker_id}", response_model=WorkerDetailResponse, tags=["Workers"])
    def get_worker(worker_id: str, _apikey: _AuthDep):
        """获取单个 Worker 详情"""
        s = get_state()
        workers = s.pool.list_workers()
        w = next((w for w in workers if w.worker_id == worker_id), None)
        if not w:
            raise HTTPException(status_code=404, detail=f"Worker not found: {worker_id}")
        monitor = None
        if s._supervisor is not None:
            monitor = s.supervisor._monitors.get(worker_id)
        return WorkerDetailResponse(**_map_worker(w, monitor))

    @app.post("/workers/{worker_id}/restart", response_model=WorkerRestartResponse, tags=["Workers"])
    def restart_worker(worker_id: str, _apikey: _AuthDep):
        """手动重启一个 Worker"""
        s = get_state()
        workers = s.pool.list_workers()
        w = next((w for w in workers if w.worker_id == worker_id), None)
        if not w:
            raise HTTPException(status_code=404, detail=f"Worker not found: {worker_id}")
        s.pool._recover_worker(w)
        return WorkerRestartResponse(worker_id=worker_id, message="Restart triggered")

    @app.get("/supervisor/metrics", response_model=SupervisorMetricsResponse, tags=["Supervisor"])
    def supervisor_metrics(_apikey: _AuthDep):
        """获取 Supervisor 健康指标"""
        s = get_state()
        sup = s.supervisor
        if sup is None:
            raise HTTPException(status_code=503, detail="Supervisor not available")
        m = sup.get_metrics()
        return SupervisorMetricsResponse(
            total_workers=m.total_workers,
            healthy_workers=m.healthy_workers,
            unhealthy_workers=m.unhealthy_workers,
            recovered_count=m.recovered_count,
            last_health_check=m.last_health_check,
            pool_uptime=m.pool_uptime,
        )

    # ── Sessions ─────────────────────────────────────────────────────────────

    @app.get("/sessions", response_model=SessionListResponse, tags=["Sessions"])
    def list_sessions(
        _apikey: _AuthDep,
        agent:    Annotated[str | None, Query(description="Filter by agent type")] = None,
        status:   Annotated[str | None, Query(description="Filter by status: active | archived")] = None,
        limit:    Annotated[int, Query(ge=1, le=500)] = 50,
    ):
        """列出所有会话（支持按 agent / status 过滤）"""
        s = get_state()
        sessions = s.session_store.list_sessions(agent=agent, status=status, limit=limit)
        return SessionListResponse(
            sessions=[
                SessionResponse(
                    agent=si.agent,
                    session_id=si.session_id,
                    status=si.status,
                    created_at=si.created_at,
                    last_used_at=si.last_used_at,
                    task_count=len(si.task_ids),
                    task_ids=si.task_ids,
                    note=si.note,
                )
                for si in sessions
            ],
            total=len(sessions),
        )

    @app.get("/sessions/stats", response_model=SessionStatsResponse, tags=["Sessions"])
    def session_stats(_apikey: _AuthDep):
        """获取会话统计信息"""
        s = get_state()
        stats = s.session_store.stats()
        return SessionStatsResponse(
            total=stats.get("total", 0),
            by_agent=stats.get("by_agent", {}),
            by_status=stats.get("by_status", {}),
        )

    @app.get("/sessions/{session_id}", response_model=SessionResponse, tags=["Sessions"])
    def get_session(session_id: str, _apikey: _AuthDep):
        """获取单个会话详情"""
        s = get_state()
        info = s.session_store.get(session_id)
        if info is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return SessionResponse(
            agent=info.agent,
            session_id=info.session_id,
            status=info.status,
            created_at=info.created_at,
            last_used_at=info.last_used_at,
            task_count=len(info.task_ids),
            task_ids=info.task_ids,
            note=info.note,
        )

    @app.post("/sessions/{session_id}/archive", response_model=SessionArchiveResponse, tags=["Sessions"])
    def archive_session(session_id: str, _apikey: _AuthDep):
        """归档指定会话"""
        s = get_state()
        ok = s.session_store.archive(session_id)
        return SessionArchiveResponse(
            session_id=session_id,
            archived=ok,
            message="Archived" if ok else f"Session not found: {session_id}",
        )

    @app.post("/sessions/{session_id}/note", response_model=SessionResponse, tags=["Sessions"])
    def update_session_note(
        session_id: str,
        _apikey:    _AuthDep,
        body:       dict[str, str],
    ):
        """更新会话备注"""
        s = get_state()
        note = body.get("note", "")
        ok = s.session_store.update_note(session_id, note)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        info = s.session_store.get(session_id)
        return SessionResponse(
            agent=info.agent,
            session_id=info.session_id,
            status=info.status,
            created_at=info.created_at,
            last_used_at=info.last_used_at,
            task_count=len(info.task_ids),
            task_ids=info.task_ids,
            note=info.note,
        )

    @app.delete("/sessions/{session_id}", response_model=SessionDeleteResponse, tags=["Sessions"])
    def delete_session(session_id: str, _apikey: _AuthDep):
        """删除指定会话"""
        s = get_state()
        ok = s.session_store.delete(session_id)
        return SessionDeleteResponse(
            session_id=session_id,
            deleted=ok,
            message="Deleted" if ok else f"Session not found: {session_id}",
        )

    # ── Prometheus Metrics（公开，无需认证）────────────────────────────────

    @app.get(
        "/metrics",
        tags=["Monitoring"],
        summary="Prometheus metrics endpoint",
        description="Returns metrics in Prometheus text exposition format. No authentication required.",
    )
    def metrics() -> PlainTextResponse:
        """Prometheus scrape endpoint — text/plain; version=0.0.4"""
        s = get_state()
        update_queue_metrics(s._queue)
        update_worker_metrics(s._pool)
        update_supervisor_metrics(s._supervisor)
        rendered = registry.render()
        return PlainTextResponse(
            content=rendered,
            media_type="text/plain; charset=utf-8",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    # ── 错误处理器 ─────────────────────────────────────────────────────────

    @app.exception_handler(Exception)
    def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
        )

    # ── Web UI 静态文件和模板 ────────────────────────────────────────────
    _web_dir = Path(__file__).parent.parent / "web"
    _static_dir = _web_dir / "static"
    _templates_dir = _web_dir / "templates"

    if _static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    templates = Jinja2Templates(directory=str(_templates_dir)) if _templates_dir.exists() else None

    @app.get("/", include_in_schema=False)
    def web_index():
        """Web UI 首页 — 任务列表"""
        if templates:
            return templates.TemplateResponse("index.html", {"request": {}})
        raise HTTPException(status_code=404, detail="Web UI not available")

    @app.get("/new", include_in_schema=False)
    def web_new_task():
        """Web UI 新建任务页"""
        if templates:
            return templates.TemplateResponse("new.html", {"request": {}})
        raise HTTPException(status_code=404, detail="Web UI not available")

    @app.get("/task/{task_id}", include_in_schema=False)
    def web_task_detail(task_id: str):
        """Web UI 任务详情页"""
        if templates:
            return templates.TemplateResponse("task.html", {"request": {}, "task_id": task_id})
        raise HTTPException(status_code=404, detail="Web UI not available")

    return app


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI Task System V5 REST API")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=18792, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    print(f"🚀 Starting AI Task System V5 REST API on http://{args.host}:{args.port}")
    print(f"   Web UI: http://{args.host}:{args.port}/")
    print(f"   Docs: http://{args.host}:{args.port}/docs")
    if _API_AUTH_ENABLED:
        print(f"   🔐 API authentication ENABLED ({len(_API_KEYS)} key(s))")
    else:
        print(f"   🔓 API authentication DISABLED (set AI_TASK_API_KEY to enable)")
    uvicorn.run(
        create_app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

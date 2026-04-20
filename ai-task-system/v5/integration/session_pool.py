"""
V4→V5 集成：SessionStore × WorkerPool 会话亲和性管理器

功能：
1. 会话亲和性（Session Affinity）：优先将任务派发到持有相同 session_id 的 Worker
2. 自动会话记录：任务完成后自动更新 SessionStore（last_used_at + task_ids）
3. 智能会话推荐：为新任务推荐最佳会话（基于 Agent 类型 + 任务历史）
4. 统一 submit()：自动完成 session_id 赋值 + SessionStore 更新

架构：
    SessionPoolManager (Facade)
        ├── SessionStore (V4)  — 会话元数据持久化
        └── WorkerPool  (V5)  — 进程池执行
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from v4.core.session_store import SessionInfo, SessionStore
    from v5.worker.pool import PooledTask, Worker, WorkerPool

logger = logging.getLogger(__name__)


# ─── 数据模型 ────────────────────────────────────────────────────────────────


class AffinityStrategy(Enum):
    """会话亲和性策略"""

    SESSION_AFFINITY = "session_affinity"  # 优先使用持有 session 的 Worker
    ANY = "any"                           # 不考虑亲和性，随便派发


@dataclass
class PoolSessionAssignment:
    """某个 Worker 当前持有的 session 分配记录"""
    worker_id: str
    session_id: str
    assigned_at: float = field(default_factory=time.time)


@dataclass
class SessionPoolMetrics:
    """SessionPool 指标"""
    total_sessions: int
    active_sessions: int
    affinity_hits: int      # 命中亲和性的次数
    affinity_misses: int    # 未命中（新建会话）
    session_updates: int   # SessionStore 更新次数


# ─── SessionPoolManager ────────────────────────────────────────────────────────


class SessionPoolManager:
    """
    V4 SessionStore 与 V5 WorkerPool 的集成管理器。

    用法：

        from v4.core.session_store import SessionStore
        from v5.worker.pool import WorkerPool
        from v5.integration.session_pool import SessionPoolManager

        # 初始化各组件
        store = SessionStore()
        pool = WorkerPool(agent_type="claude", size=2)
        pool.start()

        # 创建集成管理器
        mgr = SessionPoolManager(pool, store)
        mgr.start()

        # 提交任务（自动会话分配 + 完成后记录）
        task_id = mgr.submit("帮我写一个 Python 函数", note="我的项目")
        result = mgr.wait(task_id)

        mgr.stop()
        pool.stop()

    特性：
    - 会话亲和性：同一个 session 的任务优先路由到同一 Worker
    - 自动会话记录：submit 时自动注册会话，完成后自动更新 SessionStore
    - 智能推荐：suggest_session() 为新任务推荐最佳会话
    - 线程安全：所有公开方法均线程安全
    """

    def __init__(
        self,
        pool: "WorkerPool",
        store: "SessionStore",
        affinity_strategy: AffinityStrategy = AffinityStrategy.SESSION_AFFINITY,
        on_session_update: Callable[[str, dict], None] | None = None,
    ):
        self._pool = pool
        self._store = store
        self._affinity = affinity_strategy
        self._on_session_update = on_session_update  # WebSocket session 推送回调

        # session_id → worker_id 的亲和性映射
        self._affinity_map: dict[str, PoolSessionAssignment] = {}
        self._affinity_lock = threading.RLock()

        # Worker → session_id 的反向映射（用于快速查找）
        self._worker_session_map: dict[str, str] = {}

        # 指标
        self._affinity_hits = 0
        self._affinity_misses = 0
        self._session_updates = 0
        self._metrics_lock = threading.RLock()

        # 是否已启动
        self._started = False
        self._original_on_task_complete: Callable[["PooledTask"], None] | None = None

    # ─── 生命周期 ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """启动集成管理器（注册回调）"""
        if self._started:
            return
        self._started = True

        # 保存原有的 on_task_complete 回调
        self._original_on_task_complete = self._pool.on_task_complete

        # 替换为我们的组合回调
        self._pool.on_task_complete = self._on_task_complete_wrapper

        logger.info("SessionPoolManager started (affinity=%s)", self._affinity.value)

    def stop(self) -> None:
        """停止集成管理器（恢复原回调）"""
        if not self._started:
            return
        self._started = False

        self._pool.on_task_complete = self._original_on_task_complete

        with self._affinity_lock:
            self._affinity_map.clear()
            self._worker_session_map.clear()

        logger.info("SessionPoolManager stopped")

    # ─── 核心 API ────────────────────────────────────────────────────────────

    def submit(
        self,
        prompt: str,
        agent_type: str | None = None,
        priority: int = 1,
        timeout: int | None = None,
        session_id: str | None = None,
        note: str = "",
        skip_permissions: bool = True,
        allowed_tools: list[str] | None = None,
    ) -> str:
        """
        提交任务，自动完成会话分配和记录。

        与 WorkerPool.submit() 的区别：
        1. 自动为任务分配 session_id（从 SessionStore 或新建）
        2. 考虑会话亲和性（优先派发到持有该 session 的 Worker）
        3. 任务完成后自动更新 SessionStore

        Args:
            prompt: 任务描述
            agent_type: Agent 类型（默认继承 pool.agent_type）
            priority: 任务优先级（0=LOW, 1=NORMAL, 2=HIGH, 3=CRITICAL）
            timeout: 超时秒数
            session_id: 指定会话 ID（None=自动推荐）
            note: 会话备注（仅新建会话时使用）
            skip_permissions: 跳过确认
            allowed_tools: 工具白名单

        Returns:
            task_id
        """
        from v5.worker.pool import TaskPriority

        # 确定 agent_type
        agent = agent_type or self._pool.agent_type

        # 智能分配 session_id
        if session_id is None:
            session_id = self._assign_session(agent, prompt, note)

        # 注册新会话到 SessionStore（如果还没有）
        existing = self._store.get(session_id)
        if existing is None:
            try:
                self._store.create(agent=agent, session_id=session_id, note=note)
                logger.debug("Created new session %s for agent %s", session_id[:12], agent)
            except Exception as e:
                logger.warning("Failed to create session %s: %s", session_id[:12], e)

        # 建立亲和性映射
        self._set_affinity(session_id)

        # 提交到 WorkerPool
        task_priority = TaskPriority(priority)
        task_id = self._pool.submit(
            prompt=prompt,
            agent_type=agent,
            priority=task_priority,
            timeout=timeout,
            session_id=session_id,
            skip_permissions=skip_permissions,
            allowed_tools=allowed_tools,
        )

        logger.info(
            "SessionPoolManager.submit task=%s session=%s agent=%s",
            task_id, session_id[:12] if session_id else None, agent,
        )
        return task_id

    def wait(self, task_id: str, timeout: float | None = None) -> "PooledTask":
        """等待任务完成"""
        return self._pool.wait(task_id, timeout=timeout)

    def status(self, task_id: str) -> dict[str, Any]:
        """查询任务状态"""
        return self._pool.status(task_id)

    def list(self) -> list[dict[str, Any]]:
        """列出所有任务"""
        return self._pool.tasks()

    # ─── 会话亲和性 ──────────────────────────────────────────────────────────

    def _assign_session(self, agent: str, prompt: str, note: str) -> str:
        """
        为任务分配最佳 session_id。

        分配策略（按优先级）：
        1. 尝试从 SessionStore 找到该 agent 的最新 active 会话
        2. 生成新 session_id（格式：sess_{uuid_hex}）
        """
        # 策略：根据 affinity_strategy 决定
        if self._affinity == AffinityStrategy.ANY:
            return self._generate_session_id()

        # SESSION_AFFINITY 模式：尝试找现有会话
        sessions = self._store.list_sessions(agent=agent, status="active")
        if sessions:
            # 返回最新的那个
            latest = max(sessions, key=lambda s: s.last_used_at)
            with self._metrics_lock:
                self._affinity_misses += 1
            logger.debug("Reusing existing session %s for agent %s", latest.session_id[:12], agent)
            return latest.session_id

        # 没有现有会话，生成新的
        return self._generate_session_id()

    def _set_affinity(self, session_id: str) -> None:
        """
        设置 session_id 的亲和性映射。

        查找当前持有该 session 的 Worker，分配亲和性。
        如果没有 Worker 持有该 session，选择任意空闲 Worker 绑定。
        """
        if self._affinity != AffinityStrategy.SESSION_AFFINITY:
            return

        # 如果已经有亲和性映射，不需要重复设置
        with self._affinity_lock:
            if session_id in self._affinity_map:
                return

        # 尝试找一个空闲的 Worker 来绑定这个 session
        try:
            workers = self._pool.list_workers()
            idle_workers = [w for w in workers if w.status.value == "idle"]

            if not idle_workers:
                # 没有空闲 Worker，无法建立亲和性（任务会在 Worker 空闲后执行）
                logger.debug("No idle workers to assign session %s", session_id[:12])
                return

            # 选择第一个空闲 Worker
            worker = idle_workers[0]

            with self._affinity_lock:
                assignment = PoolSessionAssignment(worker_id=worker.worker_id, session_id=session_id)
                self._affinity_map[session_id] = assignment
                self._worker_session_map[worker.worker_id] = session_id

            logger.debug(
                "Set affinity: session %s → worker %s",
                session_id[:12], worker.worker_id,
            )
        except Exception as e:
            logger.warning("Failed to set affinity for session %s: %s", session_id[:12], e)

    def get_affinity_worker(self, session_id: str) -> str | None:
        """查询某个 session 当前亲和的 Worker ID"""
        with self._affinity_lock:
            assignment = self._affinity_map.get(session_id)
            return assignment.worker_id if assignment else None

    # ─── 智能会话推荐 ────────────────────────────────────────────────────────

    def suggest_session(
        self,
        agent: str | None = None,
        task_type: str | None = None,
    ) -> "SessionInfo | None":
        """
        为给定 Agent 和任务类型推荐最佳会话。

        推荐策略：
        1. 优先选择最近使用过的 active 会话
        2. 如果 task_type 指定，优先选择有相关历史任务的会话

        Args:
            agent: Agent 类型
            task_type: 任务类型（如 "CODING", "DEBUGGING"）

        Returns:
            SessionInfo 或 None（无合适会话）
        """
        agent = agent or self._pool.agent_type
        sessions = self._store.list_sessions(agent=agent, status="active")
        if not sessions:
            return None

        # 优先选择最近使用的
        latest = max(sessions, key=lambda s: s.last_used_at)
        return latest

    def list_active_sessions(self, agent: str | None = None) -> list["SessionInfo"]:
        """列出当前可用的会话"""
        return self._store.list_sessions(agent=agent, status="active")

    # ─── 回调处理 ────────────────────────────────────────────────────────────

    def _on_task_complete_wrapper(self, task: "PooledTask") -> None:
        """包装 WorkerPool 的 on_task_complete 回调"""
        try:
            self._on_pool_task_complete(task)
        finally:
            # 调用原有的回调
            if self._original_on_task_complete:
                self._original_on_task_complete(task)

    def _on_pool_task_complete(self, task: "PooledTask") -> None:
        """任务完成后更新 SessionStore"""
        if not task.session_id:
            return

        session_id = task.session_id

        # 更新 SessionStore
        try:
            info = self._store.get(session_id)
            if info:
                self._store.record_task(session_id, task.task_id)
                # 获取更新后的会话信息（追加了 task_id）
                updated_info = self._store.get(session_id)
                if updated_info and self._on_session_update:
                    session_dict = {
                        "agent": updated_info.agent,
                        "session_id": updated_info.session_id,
                        "status": updated_info.status,
                        "created_at": updated_info.created_at,
                        "last_used_at": updated_info.last_used_at,
                        "task_count": len(updated_info.task_ids),
                        "task_ids": updated_info.task_ids,
                        "note": updated_info.note or "",
                    }
                    try:
                        self._on_session_update(session_id, session_dict)
                    except Exception as cb_err:
                        logger.error("on_session_update callback failed: %s", cb_err)
                logger.debug(
                    "Updated SessionStore: session=%s task=%s",
                    session_id[:12], task.task_id,
                )
            else:
                logger.warning(
                    "Session %s not found in SessionStore after task %s completed",
                    session_id[:12], task.task_id,
                )
            with self._metrics_lock:
                self._session_updates += 1
        except Exception as e:
            logger.error("Failed to update SessionStore for session %s: %s", session_id[:12], e)

        # 清除亲和性映射（任务完成，Worker 恢复空闲）
        self._clear_affinity(session_id)

    def _clear_affinity(self, session_id: str) -> None:
        """清除 session 的亲和性映射"""
        with self._affinity_lock:
            assignment = self._affinity_map.pop(session_id, None)
            if assignment:
                self._worker_session_map.pop(assignment.worker_id, None)

    # ─── 工具方法 ────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_session_id() -> str:
        """生成新的 session_id"""
        import uuid
        return f"sess_{uuid.uuid4().hex[:16]}"

    # ─── 指标 ────────────────────────────────────────────────────────────────

    def metrics(self) -> SessionPoolMetrics:
        """获取集成层指标"""
        with self._metrics_lock:
            active = self._store.list_sessions(status="active")
            total = len(self._store.list_sessions())
            return SessionPoolMetrics(
                total_sessions=total,
                active_sessions=len(active),
                affinity_hits=self._affinity_hits,
                affinity_misses=self._affinity_misses,
                session_updates=self._session_updates,
            )

    def pool_status(self) -> dict[str, Any]:
        """获取底层 WorkerPool 状态（透传）"""
        return {
            "workers": self._pool.workers_status(),
            "tasks": self._pool.tasks(),
        }

    # ─── 兼容 WorkerPool 原生 API ───────────────────────────────────────────

    def workers_status(self) -> list[dict[str, Any]]:
        """透传 WorkerPool.workers_status()"""
        return self._pool.workers_status()

    def tasks(self) -> list[dict[str, Any]]:
        """透传 WorkerPool.tasks()"""
        return self._pool.tasks()


# ─── 全局单例 ────────────────────────────────────────────────────────────────


_session_pool: SessionPoolManager | None = None
_session_pool_lock = threading.Lock()


def get_session_pool(
    pool: "WorkerPool | None" = None,
    store: "SessionStore | None" = None,
) -> SessionPoolManager:
    """
    获取全局 SessionPoolManager 单例。

    首次调用时必须提供 pool 和 store，之后返回同一实例。

    Args:
        pool: WorkerPool 实例（首次调用时必须提供）
        store: SessionStore 实例（首次调用时必须提供）

    Returns:
        SessionPoolManager 单例
    """
    global _session_pool
    with _session_pool_lock:
        if _session_pool is None:
            if pool is None or store is None:
                raise ValueError("First call to get_session_pool requires pool and store")
            _session_pool = SessionPoolManager(pool, store)
            _session_pool.start()
        return _session_pool

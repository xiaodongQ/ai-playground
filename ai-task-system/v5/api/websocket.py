"""
V5 WebSocket 实时推送系统
────────────────────────
基于 FastAPI WebSocket 的生产级实时推送：
- 任务状态变更推送（pending→running→done/failed）
- Worker stdout 实时流推送
- Worker 健康状态变更推送
- 系统公告推送

WebSocket URL: ws://host:port/ws
认证: URL?token=<api_key> 或 首次连接发送 auth 消息

推送消息格式（JSON）：
    {
        "type": "task_status" | "task_output" | "worker_health" | "system",
        "task_id": "...",
        "worker_id": "...",
        "data": {...},
        "ts": 1713456789.123
    }

用法：
    # 启动 API（含 WebSocket）
    python -m v5.api.app

    # 前端连接示例
    const ws = new WebSocket("ws://localhost:18792/ws");
    ws.onmessage = (e) => console.log(JSON.parse(e.data));
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger("ai_task_system.websocket")


# ─── 事件类型枚举 ────────────────────────────────────────────────────────────

class WSEventType(str, Enum):
    TASK_STATUS   = "task_status"    # 任务状态变更
    TASK_OUTPUT   = "task_output"    # Worker stdout 行
    TASK_COMPLETE = "task_complete"  # 任务完成（含结果/错误）
    WORKER_HEALTH = "worker_health"  # Worker 健康状态变更
    SESSION_UPDATE = "session_update" # 会话信息更新（如任务完成追加）
    SYSTEM        = "system"         # 系统公告


# ─── 消息模型 ────────────────────────────────────────────────────────────────

@dataclass
class WSMessage:
    type:     WSEventType
    task_id:  str | None = None
    worker_id: str | None = None
    data:     dict[str, Any] = field(default_factory=dict)
    ts:       float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "type":      self.type.value,
            "task_id":   self.task_id,
            "worker_id": self.worker_id,
            "data":      self.data,
            "ts":        self.ts,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "WSMessage":
        obj = json.loads(raw)
        return cls(
            type=WSEventType(obj["type"]),
            task_id=obj.get("task_id"),
            worker_id=obj.get("worker_id"),
            data=obj.get("data", {}),
            ts=obj.get("ts", time.time()),
        )


# ─── 连接管理器 ──────────────────────────────────────────────────────────────

class ConnectionManager:
    """线程安全的 WebSocket 连接管理器"""

    def __init__(self):
        # 所有活跃连接
        self._connections: set[WebSocket] = set()
        # 订阅特定 task_id 的连接
        self._task_subs: dict[str, set[WebSocket]] = defaultdict(set)
        # 订阅特定 worker_id 的连接
        self._worker_subs: dict[str, set[WebSocket]] = defaultdict(set)
        # 订阅特定 session_id 的连接
        self._session_subs: dict[str, set[WebSocket]] = defaultdict(set)
        # 订阅所有任务的连接（广播模式）
        self._broadcast_conns: set[WebSocket] = set()
        self._lock = threading.RLock()

    # ── 连接管理 ────────────────────────────────────────────────────────────

    def connect(self, ws: WebSocket, task_id: str | None = None, worker_id: str | None = None) -> None:
        """注册一个新的 WebSocket 连接"""
        with self._lock:
            self._connections.add(ws)
            if task_id:
                self._task_subs[task_id].add(ws)
            if worker_id:
                self._worker_subs[worker_id].add(ws)
            logger.info(
                f"[WS] Connected. total={len(self._connections)}, "
                f"task={task_id or '*'}, worker={worker_id or '*'}"
            )

    def disconnect(self, ws: WebSocket) -> None:
        """注销一个 WebSocket 连接"""
        with self._lock:
            self._connections.discard(ws)
            for subs in self._task_subs.values():
                subs.discard(ws)
            for subs in self._worker_subs.values():
                subs.discard(ws)
            for subs in self._session_subs.values():
                subs.discard(ws)
            self._broadcast_conns.discard(ws)
            logger.info(f"[WS] Disconnected. total={len(self._connections)}")

    def subscribe_task(self, ws: WebSocket, task_id: str) -> None:
        """订阅特定任务更新"""
        with self._lock:
            self._task_subs[task_id].add(ws)

    def subscribe_worker(self, ws: WebSocket, worker_id: str) -> None:
        """订阅特定 Worker 更新"""
        with self._lock:
            self._worker_subs[worker_id].add(ws)

    def subscribe_session(self, ws: WebSocket, session_id: str) -> None:
        """订阅特定会话更新"""
        with self._lock:
            self._session_subs[session_id].add(ws)

    def subscribe_all(self, ws: WebSocket) -> None:
        """订阅所有广播（系统公告等）"""
        with self._lock:
            self._broadcast_conns.add(ws)

    # ── 广播 ────────────────────────────────────────────────────────────────

    def _send(self, ws: WebSocket, msg: WSMessage) -> bool:
        """发送单条消息，返回是否成功"""
        try:
            # WebSocket.send_text 是协程方法，需要在事件循环中调用
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(ws.send_text(msg.to_json()))
            else:
                loop.run_until_complete(ws.send_text(msg.to_json()))
            return True
        except Exception:
            return False

    def _broadcast(self, recipients: set[WebSocket], msg: WSMessage) -> int:
        """向一组连接广播，返回成功发送数"""
        dead = set()
        sent = 0
        for ws in recipients:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(ws.send_text(msg.to_json()))
                else:
                    loop.run_until_complete(ws.send_text(msg.to_json()))
                sent += 1
            except Exception:
                dead.add(ws)
        # 清理死连接
        if dead:
            with self._lock:
                self._connections -= dead
                for subs in self._task_subs.values():
                    subs -= dead
                for subs in self._worker_subs.values():
                    subs -= dead
                self._broadcast_conns -= dead
        return sent

    def broadcast_task_status(
        self,
        task_id: str,
        worker_id: str | None,
        status: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """广播任务状态变更"""
        msg = WSMessage(
            type=WSEventType.TASK_STATUS,
            task_id=task_id,
            worker_id=worker_id,
            data={**({"status": status}), **(data or {})},
        )
        recipients: set[WebSocket] = set()
        with self._lock:
            recipients.update(self._task_subs.get(task_id, set()))
            recipients.update(self._broadcast_conns)
        self._broadcast(recipients, msg)

    def broadcast_task_output(
        self,
        task_id: str,
        worker_id: str,
        line: str,
        stream: str = "stdout",
    ) -> None:
        """广播 Worker stdout 行"""
        msg = WSMessage(
            type=WSEventType.TASK_OUTPUT,
            task_id=task_id,
            worker_id=worker_id,
            data={"line": line, "stream": stream},
        )
        recipients: set[WebSocket] = set()
        with self._lock:
            recipients.update(self._task_subs.get(task_id, set()))
            recipients.update(self._broadcast_conns)
        self._broadcast(recipients, msg)

    def broadcast_task_complete(
        self,
        task_id: str,
        worker_id: str,
        status: str,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        """广播任务完成"""
        msg = WSMessage(
            type=WSEventType.TASK_COMPLETE,
            task_id=task_id,
            worker_id=worker_id,
            data={
                "status": status,
                "result": result,
                "error": error,
            },
        )
        recipients: set[WebSocket] = set()
        with self._lock:
            recipients.update(self._task_subs.get(task_id, set()))
            recipients.update(self._broadcast_conns)
        self._broadcast(recipients, msg)

    def broadcast_worker_health(
        self,
        worker_id: str,
        health_status: str,
        reason: str | None = None,
    ) -> None:
        """广播 Worker 健康状态变更"""
        msg = WSMessage(
            type=WSEventType.WORKER_HEALTH,
            worker_id=worker_id,
            data={
                "health_status": health_status,
                "reason": reason,
            },
        )
        recipients: set[WebSocket] = set()
        with self._lock:
            recipients.update(self._worker_subs.get(worker_id, set()))
            recipients.update(self._broadcast_conns)
        self._broadcast(recipients, msg)

    def broadcast_session_update(self, session_id: str, session_info: dict) -> None:
        """广播会话信息更新（如任务完成追加到会话）"""
        msg = WSMessage(
            type=WSEventType.SESSION_UPDATE,
            data={
                "session_id": session_id,
                "session": session_info,
            },
        )
        recipients: set[WebSocket] = set()
        with self._lock:
            recipients.update(self._session_subs.get(session_id, set()))
            recipients.update(self._broadcast_conns)
        self._broadcast(recipients, msg)

    def broadcast_system(self, message: str, level: str = "info") -> None:
        """广播系统公告"""
        msg = WSMessage(
            type=WSEventType.SYSTEM,
            data={"message": message, "level": level},
        )
        with self._lock:
            self._broadcast(set(self._connections), msg)

    @property
    def connection_count(self) -> int:
        with self._lock:
            return len(self._connections)


# ─── 全局单例 ────────────────────────────────────────────────────────────────

_ws_manager: Optional[ConnectionManager] = None


def get_ws_manager() -> ConnectionManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = ConnectionManager()
    return _ws_manager


# ─── WebSocket 路由 ─────────────────────────────────────────────────────────

_wss_router = APIRouter()


@_wss_router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str | None = Query(None),
):
    """
    WebSocket 端点。

    认证方式（二选一）：
    1. URL 参数：ws://host:port/ws?token=<api_key>
    2. 首条消息：{"type": "auth", "token": "<api_key>"}

    订阅消息（客户端发送）：
    - {"type": "subscribe_task", "task_id": "xxx"}
    - {"type": "subscribe_worker", "worker_id": "xxx"}
    - {"type": "subscribe_all"}

    关闭连接：发送 {"type": "close"} 或断开 TCP
    """
    manager = get_ws_manager()

    # ── 认证 ──────────────────────────────────────────────────────────────
    from .app import _API_AUTH_ENABLED, _API_KEYS

    auth_ok = not _API_AUTH_ENABLED  # 未启用认证时直接允许

    if _API_AUTH_ENABLED:
        if token and token in _API_KEYS:
            auth_ok = True
        else:
            # 等待首条 auth 消息
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=10.0)
                msg = json.loads(raw)
                if msg.get("type") == "auth" and msg.get("token") in _API_KEYS:
                    auth_ok = True
                else:
                    await ws.send_text(WSMessage(
                        type=WSEventType.SYSTEM,
                        data={"message": "Authentication failed", "level": "error"},
                    ).to_json())
                    await ws.close(code=4001, reason="Unauthorized")
                    return
            except asyncio.TimeoutError:
                await ws.close(code=4002, reason="Auth timeout")
                return

    if not auth_ok:
        await ws.close(code=4001, reason="Unauthorized")
        return

    # ── 接受连接 ──────────────────────────────────────────────────────────
    await ws.accept()
    manager.connect(ws)
    logger.info(f"[WS] Client connected. total={manager.connection_count}")

    # ── 发送欢迎消息 ─────────────────────────────────────────────────────
    await ws.send_text(WSMessage(
        type=WSEventType.SYSTEM,
        data={"message": "Connected to AI Task System V5 WebSocket", "level": "info"},
    ).to_json())

    # ── 消息循环 ──────────────────────────────────────────────────────────
    while True:
        try:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            msg_type = msg.get("type")

            if msg_type == "subscribe_task":
                task_id = msg.get("task_id")
                if task_id:
                    manager.subscribe_task(ws, task_id)
                    logger.debug(f"[WS] Task subscription: {task_id}")

            elif msg_type == "subscribe_worker":
                worker_id = msg.get("worker_id")
                if worker_id:
                    manager.subscribe_worker(ws, worker_id)
                    logger.debug(f"[WS] Worker subscription: {worker_id}")

            elif msg_type == "subscribe_session":
                session_id = msg.get("session_id")
                if session_id:
                    manager.subscribe_session(ws, session_id)
                    logger.debug(f"[WS] Session subscription: {session_id}")

            elif msg_type == "subscribe_all":
                manager.subscribe_all(ws)
                logger.debug("[WS] Broadcast subscription enabled")

            elif msg_type == "ping":
                await ws.send_text(WSMessage(
                    type=WSEventType.SYSTEM,
                    data={"message": "pong", "level": "debug"},
                ).to_json())

            elif msg_type == "close":
                break

        except json.JSONDecodeError:
            await ws.send_text(WSMessage(
                type=WSEventType.SYSTEM,
                data={"message": "Invalid JSON", "level": "error"},
            ).to_json())
        except WebSocketDisconnect:
            break
        except Exception as e:
            logger.error(f"[WS] Error: {e}")
            break

    manager.disconnect(ws)
    logger.info(f"[WS] Client disconnected. total={manager.connection_count}")


# ─── 事件钩子（供 APIState 调用）─────────────────────────────────────────────

def setup_ws_hooks(pool, supervisor, session_pool=None) -> None:
    """
    将 WebSocket 广播接入 WorkerPool 和 Supervisor 的事件回调。
    在 APIState 初始化 pool/supervisor 后调用一次。
    session_pool 为可选的 SessionPoolManager 实例，传入时会注册
    on_session_update 回调以在任务完成时推送 WebSocket session 更新。
    """
    manager = get_ws_manager()

    # ── Pool: task output ─────────────────────────────────────────────────
    def _on_task_output(task_id: str, line: str) -> None:
        # 从 pool 查找当前处理此 task 的 worker_id
        worker_id = None
        for w in pool.list_workers():
            if getattr(w, "current_task_id", None) == task_id:
                worker_id = w.worker_id
                break
        manager.broadcast_task_output(task_id, worker_id or "unknown", line)

    # ── Pool: task complete ───────────────────────────────────────────────
    def _on_task_complete(task) -> None:
        task_id = getattr(task, "task_id", "?")
        worker_id = getattr(task, "worker_id", None) or "unknown"
        status = getattr(task, "status", "completed")
        result = getattr(task, "result", None)
        error  = getattr(task, "error", None)
        manager.broadcast_task_complete(task_id, worker_id, str(status), result, error)

    # ── Supervisor: worker health change ─────────────────────────────────
    _prev_health: dict[str, str] = {}

    def _on_health_change(worker_id: str, new_status: str, reason: str | None = None) -> None:
        prev = _prev_health.get(worker_id)
        if prev != new_status:
            _prev_health[worker_id] = new_status
            manager.broadcast_worker_health(worker_id, new_status, reason)

    # 设置回调
    pool.on_task_output   = _on_task_output
    pool.on_task_complete = _on_task_complete

    # Supervisor 每次健康检测后检查变更
    if supervisor is not None:
        import threading
        _orig_check = supervisor._health_check_loop if hasattr(supervisor, "_health_check_loop") else None

        def _health_monitor_loop():
            while getattr(supervisor, "_running", False):
                time.sleep(supervisor.interval)
                try:
                    for mid, mon in supervisor._monitors.items():
                        health = mon.get_snapshot().health_status.name.lower()
                        _on_health_change(mid, health)
                except Exception:
                    pass

        t = threading.Thread(target=_health_monitor_loop, daemon=True)
        t.start()

    # ── SessionPoolManager: session update（WebSocket 推送） ─────────────────
    if session_pool is not None:
        def _on_session_update(session_id: str, session_info: dict) -> None:
            manager.broadcast_session_update(session_id, session_info)

        session_pool._on_session_update = _on_session_update
        logger.debug("[WS] Session update hook registered")

    logger.info("[WS] Event hooks registered with pool and supervisor")

"""V5 集成模块

V4（Adapter/CLI/Router/SessionStore）与 V5（Pool/Queue/Supervisor）的集成层。

当前集成：
- SessionStore × WorkerPool：会话亲和性 + 自动会话记录
- TaskQueue × WorkerPool：队列调度器（QueueDispatcher）
"""
from __future__ import annotations

from .session_pool import SessionPoolManager, get_session_pool
from .queue_dispatcher import QueueDispatcher, setup_queue_dispatcher

__all__ = [
    "SessionPoolManager",
    "get_session_pool",
    "QueueDispatcher",
    "setup_queue_dispatcher",
]

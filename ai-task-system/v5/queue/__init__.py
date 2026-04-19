"""
V5 Task Queue — SQLite-backed persistent priority queue.

Supports:
- Priority queue (0=highest, 9=lowest)
- Exponential backoff retry
- Dead letter queue for exhausted tasks
- Task states: PENDING → DEQUEUED → RUNNING → DONE | FAILED | DEAD
- JSON payload storage
- Scheduled execution (run_at timestamp)
"""

from .queue import (
    TaskQueue,
    Task,
    TaskPriority,
    TaskStatus,
    QueueMetrics,
)

__all__ = [
    "TaskQueue",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "QueueMetrics",
]

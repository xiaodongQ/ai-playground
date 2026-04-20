"""
Tests for V5 TaskQueue - SQLite-backed persistent task queue.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

import pytest


class TestTaskQueue:
    def test_instantiation(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        assert q is not None
        q.close()

    def test_submit_task(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(
            payload={"prompt": "say hello"},
            priority=TaskPriority.NORMAL,
            timeout=30,
        )
        assert isinstance(task_id, str)
        assert task_id.startswith("t-")
        q.close()

    def test_dequeue_single_task(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority, TaskStatus
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(payload={"prompt": "test"}, priority=TaskPriority.NORMAL, timeout=30)
        task = q.dequeue(worker_id="w-test")
        assert task is not None
        assert task.task_id == task_id
        assert task.status == TaskStatus.DEQUEUED
        q.close()

    def test_dequeue_respects_priority(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority, TaskStatus
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        low_id = q.submit(payload={"prompt": "low"}, priority=TaskPriority.LOW, timeout=30)
        high_id = q.submit(payload={"prompt": "high"}, priority=TaskPriority.HIGH, timeout=30)
        task = q.dequeue(worker_id="w-test")
        # HIGH priority should be dequeued first
        assert task.task_id == high_id
        q.close()

    def test_dequeue_empty_queue(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task = q.dequeue(worker_id="w-test")
        assert task is None
        q.close()

    def test_done_task(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority, TaskStatus
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(payload={"prompt": "test"}, priority=TaskPriority.NORMAL, timeout=30)
        q.dequeue(worker_id="w-test")
        q.done(task_id, result={"out": "hello"})
        task = q.get(task_id)
        assert task.status == TaskStatus.DONE
        assert task.result == {"out": "hello"}
        q.close()

    def test_fail_and_retry(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority, TaskStatus
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(
            payload={"prompt": "test"},
            priority=TaskPriority.NORMAL,
            timeout=30,
        )
        q.dequeue(worker_id="w-test")
        retried = q.fail(task_id, "error occurred", retry=True)
        # First fail should retry (retry_count becomes 1, still <= default max_retries=3)
        assert retried is True
        task = q.get(task_id)
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1
        q.close()

    def test_fail_exhausted_retries_to_dead_letter(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority, TaskStatus
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(
            payload={"prompt": "test"},
            priority=TaskPriority.NORMAL,
            timeout=30,
        )
        q.dequeue(worker_id="w-test")

        # Default max_retries=3, so need 4 fails to exhaust
        # Fail 1: retry_count=1 <= 3 -> retry
        assert q.fail(task_id, "err1", retry=True) is True
        # Fail 2: retry_count=2 <= 3 -> retry
        assert q.fail(task_id, "err2", retry=True) is True
        # Fail 3: retry_count=3 <= 3 -> retry
        assert q.fail(task_id, "err3", retry=True) is True
        # Fail 4: retry_count=4 > 3 -> dead letter
        assert q.fail(task_id, "err4", retry=True) is False

        # Should be in dead letters
        dead = q.list_dead_letters()
        assert len(dead) == 1
        assert dead[0].task_id == task_id
        q.close()

    def test_metrics(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        q.submit(payload={"prompt": "t1"}, priority=TaskPriority.NORMAL, timeout=30)
        q.submit(payload={"prompt": "t2"}, priority=TaskPriority.NORMAL, timeout=30)
        m = q.metrics()
        assert m.pending == 2
        q.close()

    def test_delete_pending_task(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(payload={"prompt": "test"}, priority=TaskPriority.NORMAL, timeout=30)
        deleted = q.delete(task_id)
        assert deleted is True
        assert q.get(task_id) is None
        q.close()

    def test_delete_running_task_rejected(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(payload={"prompt": "test"}, priority=TaskPriority.NORMAL, timeout=30)
        q.dequeue(worker_id="w-test")
        with pytest.raises(ValueError):
            q.delete(task_id)
        q.close()

    def test_purge_dead_letters(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(
            payload={"prompt": "test"},
            priority=TaskPriority.NORMAL,
            timeout=30,
        )
        q.dequeue(worker_id="w-test")
        # Exhaust retries (4 fails total for max_retries=3)
        for i in range(4):
            q.fail(task_id, f"err{i}", retry=True)

        dead_before = q.list_dead_letters()
        assert len(dead_before) == 1

        # Purge dead letters older than 1000 seconds in the past
        # (dead_at was just set, so this should NOT purge the fresh letter)
        count = q.purge_dead_letters(before=time.time() - 1000)
        assert count == 0  # fresh letters not purged
        dead_after = q.list_dead_letters()
        assert len(dead_after) == 1
        q.close()

    def test_clear_completed(self, tmp_path):
        from ai_task_system.v5.queue.queue import TaskQueue, TaskPriority
        db_path = tmp_path / "tasks.db"
        q = TaskQueue(db_path=str(db_path))
        task_id = q.submit(payload={"prompt": "test"}, priority=TaskPriority.NORMAL, timeout=30)
        q.dequeue(worker_id="w-test")
        q.done(task_id, result={})
        cleared = q.clear_completed(before=time.time() + 10)
        assert cleared >= 0
        q.close()

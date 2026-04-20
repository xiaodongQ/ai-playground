"""
V5 Task Queue — SQLite-backed persistent priority queue.

Architecture:
  submit() → SQLite (PENDING) → dequeue() → RUNNING → done()/fail()
                                                       ↓ (retries exhausted)
                                                    DEAD

Usage:
    q = TaskQueue(db_path="~/.ai_task_system/tasks.db")

    task_id = q.submit(
        payload={"prompt": "say hello"},
        priority=TaskPriority.HIGH,
        timeout=60,
        max_retries=3,
        metadata={"agent": "claude"},
    )

    task = q.dequeue(worker_id="w-001")
    q.done(task.task_id, result={"output": "hello"})
    # or q.fail(task.task_id, error="timeout")

    # Metrics
    print(q.metrics())

    # Dead letter
    for t in q.list_dead_letters():
        print(f"Dead: {t.task_id}", t.error)
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Iterator, Optional


# ─── Data Models ────────────────────────────────────────────────────────────


class TaskPriority(IntEnum):
    CRITICAL = 0  # Highest — immediate processing
    HIGH = 2
    NORMAL = 5
    LOW = 7
    BACKGROUND = 9  # Lowest


class TaskStatus(IntEnum):
    PENDING = 0      # In queue, waiting
    DEQUEUED = 1     # Pulled from queue but not yet running
    RUNNING = 2      # Worker has picked it up
    DONE = 3         # Completed successfully
    FAILED = 4       # Failed (may retry)
    DEAD = 5         # Exhausted retries → moved to dead letter queue


@dataclass
class Task:
    task_id: str
    payload: dict          # User-supplied task data (e.g. {"prompt": "..."})
    priority: TaskPriority
    status: TaskStatus
    timeout: float         # Seconds before considered stalled
    max_retries: int       # Max retry attempts
    retry_count: int       # Current retry count
    retry_delay: float     # Base delay for exponential backoff (seconds)
    run_at: float          # Unix timestamp — don't run before this
    created_at: float
    dequeued_at: Optional[float]
    started_at: Optional[float]
    completed_at: Optional[float]
    worker_id: Optional[str]
    result: Optional[dict]   # Final result (on DONE)
    error: Optional[str]     # Error message (on FAILED/DEAD)
    metadata: dict          # User-supplied metadata

    @classmethod
    def from_row(cls, row: sqlite3.Row, from_dead_letter: bool = False) -> Task:
        """
        Args:
            row: sqlite3.Row from tasks or dead_letters table.
            from_dead_letter: True if row is from dead_letters (no status column).
        """
        return cls(
            task_id=str(row["task_id"]),
            payload=json.loads(row["payload"]) if row["payload"] else {},
            priority=TaskPriority(int(row["priority"])),
            status=TaskStatus.DEAD if from_dead_letter
                  else TaskStatus(int(row["status"])),
            timeout=float(row["timeout"]),
            max_retries=int(row["max_retries"]),
            retry_count=int(row["retry_count"]),
            retry_delay=float(row["retry_delay"]) if "retry_delay" in row.keys() else 0.0,
            run_at=float(row["run_at"]),
            created_at=float(row["created_at"]),
            dequeued_at=float(row["dequeued_at"]) if row["dequeued_at"] else None,
            started_at=float(row["started_at"]) if row["started_at"] else None,
            completed_at=float(row["completed_at"]) if row["completed_at"] else None,
            worker_id=str(row["worker_id"]) if row["worker_id"] else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=str(row["error"]) if row["error"] else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


@dataclass
class QueueMetrics:
    pending: int
    running: int
    done_today: int
    failed_today: int
    dead_letters: int
    avg_wait_time: float   # seconds from created → dequeued
    avg_run_time: float    # seconds from started → completed


# ─── Schema Migration ───────────────────────────────────────────────────────


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id       TEXT PRIMARY KEY,
    payload       TEXT,
    priority      INTEGER NOT NULL DEFAULT 5,
    status        INTEGER NOT NULL DEFAULT 0,
    timeout       REAL    NOT NULL DEFAULT 300.0,
    max_retries   INTEGER NOT NULL DEFAULT 3,
    retry_count   INTEGER NOT NULL DEFAULT 0,
    retry_delay   REAL    NOT NULL DEFAULT 5.0,
    run_at        REAL    NOT NULL DEFAULT 0.0,
    created_at    REAL    NOT NULL,
    dequeued_at   REAL,
    started_at    REAL,
    completed_at  REAL,
    worker_id     TEXT,
    result        TEXT,
    error         TEXT,
    metadata      TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_priority
    ON tasks(status, priority ASC);

CREATE INDEX IF NOT EXISTS idx_tasks_status_run_at
    ON tasks(status, run_at ASC);

CREATE INDEX IF NOT EXISTS idx_tasks_worker
    ON tasks(worker_id)
    WHERE worker_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS dead_letters (
    task_id       TEXT PRIMARY KEY,
    payload       TEXT,
    priority      INTEGER,
    timeout       REAL,
    max_retries   INTEGER,
    retry_count   INTEGER,
    run_at        REAL,
    created_at    REAL,
    dequeued_at   REAL,
    started_at    REAL,
    completed_at  REAL,
    worker_id     TEXT,
    result        TEXT,
    error         TEXT,
    metadata      TEXT,
    dead_at       REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dead_created
    ON dead_letters(dead_at DESC);
"""


# ─── TaskQueue ───────────────────────────────────────────────────────────────


class TaskQueue:
    """
    SQLite-backed persistent priority task queue with retry support.

    Thread-safe for concurrent submit/dequeue/complete operations.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        default_timeout: float = 300.0,
        default_max_retries: int = 3,
        default_retry_delay: float = 5.0,
    ):
        if db_path is None:
            db_path = os.path.expanduser("~/.ai_task_system/tasks.db")

        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._default_timeout = default_timeout
        self._default_max_retries = default_max_retries
        self._default_retry_delay = default_retry_delay

        self._local = threading.local()
        self._init_db()

    # ── Connection management ───────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        """Thread-local DB connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self._db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        """Run schema migration."""
        conn = self._conn()
        conn.executescript(SCHEMA)
        conn.commit()

    def _close_conn(self) -> None:
        """Close thread-local connection (call from the same thread)."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # ── Submit ───────────────────────────────────────────────────────────────

    def submit(
        self,
        payload: dict,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        run_at: Optional[float] = None,  # Unix timestamp; None=now
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Submit a new task to the queue.

        Returns the task_id string.
        """
        task_id = f"t-{uuid.uuid4().hex[:12]}"
        now = time.time()

        conn = self._conn()
        conn.execute(
            """
            INSERT INTO tasks
                (task_id, payload, priority, status, timeout, max_retries,
                 retry_count, retry_delay, run_at, created_at, metadata)
            VALUES
                (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                task_id,
                json.dumps(payload, ensure_ascii=False),
                int(priority),
                TaskStatus.PENDING,
                timeout or self._default_timeout,
                max_retries or self._default_max_retries,
                retry_delay or self._default_retry_delay,
                run_at or now,
                now,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
        return task_id

    # ── Dequeue ─────────────────────────────────────────────────────────────

    def dequeue(
        self,
        worker_id: str,
        max_wait: float = 0.0,
    ) -> Optional[Task]:
        """
        Atomically dequeue the highest-priority, earliest-availability task.

        Args:
            worker_id: ID of the worker claiming this task
            max_wait: Max seconds to wait for a task (0 = return immediately)

        Returns:
            Task object, or None if no task available.
        """
        conn = self._conn()
        now = time.time()

        deadline = now + max_wait
        while True:
            cursor = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = ?
                  AND run_at <= ?
                ORDER BY priority ASC, run_at ASC
                LIMIT 1
                """,
                (TaskStatus.PENDING, now),
            )
            row = cursor.fetchone()

            if row is not None:
                task_id = str(row["task_id"])
                updated = conn.execute(
                    """
                    UPDATE tasks
                    SET status = ?, dequeued_at = ?, worker_id = ?
                    WHERE task_id = ? AND status = ?
                    """,
                    (TaskStatus.DEQUEUED, now, worker_id, task_id, TaskStatus.PENDING),
                )
                conn.commit()

                if updated.rowcount == 1:
                    # Successfully claimed
                    cursor2 = conn.execute(
                        "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                    )
                    return Task.from_row(cursor2.fetchone())
                # Race: another worker took it; retry

            if max_wait <= 0 or now >= deadline:
                return None

            # Wait and retry (simple polling; avoid sleep(0) spinning)
            sleep_time = min(0.1 + random.random() * 0.2, deadline - now)
            if sleep_time <= 0:
                return None
            time.sleep(sleep_time)
            now = time.time()

    # ── Start ───────────────────────────────────────────────────────────────

    def start(self, task_id: str) -> bool:
        """Mark a dequeued task as actually running (worker started processing)."""
        conn = self._conn()
        now = time.time()
        cur = conn.execute(
            """
            UPDATE tasks
            SET status = ?, started_at = ?
            WHERE task_id = ? AND status = ?
            """,
            (TaskStatus.RUNNING, now, task_id, TaskStatus.DEQUEUED),
        )
        conn.commit()
        return cur.rowcount == 1

    # ── Complete / Fail ─────────────────────────────────────────────────────

    def done(
        self,
        task_id: str,
        result: Optional[dict] = None,
    ) -> bool:
        """Mark a task as successfully completed."""
        conn = self._conn()
        now = time.time()
        cur = conn.execute(
            """
            UPDATE tasks
            SET status = ?, completed_at = ?, result = ?
            WHERE task_id = ? AND status IN (?, ?)
            """,
            (
                TaskStatus.DONE,
                now,
                json.dumps(result or {}, ensure_ascii=False),
                task_id,
                TaskStatus.RUNNING,
                TaskStatus.DEQUEUED,
            ),
        )
        conn.commit()
        return cur.rowcount == 1

    def fail(
        self,
        task_id: str,
        error: str,
        retry: bool = True,
    ) -> bool:
        """
        Mark a task as failed. If retry is True and retry_count < max_retries,
        re-queues the task with exponential backoff delay.
        Returns True if the task was retried, False if it was finalized.
        """
        conn = self._conn()
        now = time.time()

        cur = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        )
        row = cur.fetchone()
        if row is None:
            return False

        task = Task.from_row(row)
        new_retry_count = task.retry_count + 1

        if retry and new_retry_count <= task.max_retries:
            # Exponential backoff: delay * 2^retry_count + jitter
            delay = task.retry_delay * (2 ** task.retry_count) + random.uniform(0, 1)
            next_run_at = now + delay

            conn.execute(
                """
                UPDATE tasks
                SET status = ?, retry_count = ?, run_at = ?,
                    error = ?, dequeued_at = NULL, worker_id = NULL
                WHERE task_id = ?
                """,
                (
                    TaskStatus.PENDING,
                    new_retry_count,
                    next_run_at,
                    error[:500],
                    task_id,
                ),
            )
            conn.commit()
            return True  # Retrying
        else:
            # Move to dead letter queue
            conn.execute(
                """
                INSERT INTO dead_letters
                    (task_id, payload, priority, timeout, max_retries,
                     retry_count, run_at, created_at, dequeued_at,
                     started_at, completed_at, worker_id, result,
                     error, metadata, dead_at)
                SELECT
                    task_id, payload, priority, timeout, max_retries,
                    ?, run_at, created_at, dequeued_at,
                    ?, ?, worker_id, result,
                    ?, metadata, ?
                FROM tasks
                WHERE task_id = ?
                """,
                (
                    new_retry_count,
                    now,
                    now,
                    error[:500],
                    now,
                    task_id,
                ),
            )
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
            return False  # Dead-lettered

    # ── Stale task recovery ──────────────────────────────────────────────────

    def recover_stale(self, worker_id: Optional[str] = None) -> list[str]:
        """
        Find tasks that have been RUNNING/DEQUEUED for longer than their
        timeout and mark them for retry (or dead-letter if exhausted).

        Returns list of recovered task_ids.
        """
        conn = self._conn()
        now = time.time()
        recovered = []

        cursor = conn.execute(
            """
            SELECT task_id, started_at, timeout, retry_count, max_retries, error
            FROM tasks
            WHERE status IN (?, ?)
              AND started_at IS NOT NULL
            """,
                        (TaskStatus.RUNNING, TaskStatus.DEQUEUED),
        )

        for row in cursor:
            elapsed = now - float(row["started_at"])
            if elapsed >= float(row["timeout"]):
                task_id = str(row["task_id"])
                # Don't use self.fail() — avoid reinsert, use direct update
                new_retry_count = int(row["retry_count"]) + 1
                max_retries = int(row["max_retries"])

                if new_retry_count <= max_retries:
                    delay = 5.0 * (2 ** int(row["retry_count"])) + random.uniform(0, 1)
                    conn.execute(
                        """
                        UPDATE tasks
                        SET status = ?, retry_count = ?, run_at = ?,
                            error = ?, dequeued_at = NULL, worker_id = NULL
                        WHERE task_id = ?
                        """,
                        (
                            TaskStatus.PENDING,
                            new_retry_count,
                            now + delay,
                            f"Stale recovery (elapsed={elapsed:.0f}s, timeout={row['timeout']}s)",
                            task_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO dead_letters
                            (task_id, payload, priority, timeout, max_retries,
                             retry_count, run_at, created_at, dequeued_at,
                             started_at, completed_at, worker_id, result,
                             error, metadata, dead_at)
                        SELECT
                            task_id, payload, priority, timeout, max_retries,
                            ?, run_at, created_at, dequeued_at,
                            started_at, ?, worker_id, result,
                            ?, metadata, ?
                        FROM tasks
                        WHERE task_id = ?
                        """,
                        (
                            new_retry_count,
                            now,
                            f"Stale + exhausted retries (elapsed={elapsed:.0f}s)",
                            now,
                            task_id,
                        ),
                    )
                    conn.execute(
                        "DELETE FROM tasks WHERE task_id = ?", (task_id,)
                    )
                recovered.append(task_id)

        conn.commit()
        return recovered

    # ── Query ────────────────────────────────────────────────────────────────

    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID (from main table)."""
        conn = self._conn()
        cur = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        )
        row = cur.fetchone()
        return Task.from_row(row) if row else None

    def list_pending(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """List pending tasks ordered by priority."""
        conn = self._conn()
        cur = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = ?
            ORDER BY priority ASC, run_at ASC
            LIMIT ? OFFSET ?
            """,
            (TaskStatus.PENDING, limit, offset),
        )
        return [Task.from_row(r) for r in cur.fetchall()]

    def list_running(self, limit: int = 100) -> list[Task]:
        """List currently running tasks."""
        conn = self._conn()
        cur = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status IN (?, ?)
            ORDER BY started_at ASC
            LIMIT ?
            """,
            (TaskStatus.RUNNING, TaskStatus.DEQUEUED, limit),
        )
        return [Task.from_row(r) for r in cur.fetchall()]

    def list_done(self, limit: int = 50, offset: int = 0) -> list[Task]:
        """List completed tasks (most recent first)."""
        conn = self._conn()
        cur = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = ?
            ORDER BY completed_at DESC
            LIMIT ? OFFSET ?
            """,
            (TaskStatus.DONE, limit, offset),
        )
        return [Task.from_row(r) for r in cur.fetchall()]

    def list_dead_letters(
        self,
        limit: int = 100,
        since: Optional[float] = None,
    ) -> list[Task]:
        """
        List dead-lettered tasks.

        Args:
            limit: Max results
            since: Only tasks dead after this timestamp (Unix)
        """
        conn = self._conn()
        cols = [
            "task_id", "payload", "priority", "timeout", "max_retries",
            "retry_count", "run_at", "created_at", "dequeued_at",
            "started_at", "completed_at", "worker_id", "result",
            "error", "metadata", "dead_at",
        ]
        col_sql = ", ".join(cols)
        if since:
            cur = conn.execute(
                f"SELECT {col_sql} FROM dead_letters WHERE dead_at >= ?"
                f" ORDER BY dead_at DESC LIMIT ?",
                (since, limit),
            )
        else:
            cur = conn.execute(
                f"SELECT {col_sql} FROM dead_letters"
                f" ORDER BY dead_at DESC LIMIT ?",
                (limit,),
            )
        return [Task.from_row(r, from_dead_letter=True) for r in cur.fetchall()]

    def purge_dead_letters(self, before: float) -> int:
        """Delete dead letters older than `before` (Unix timestamp). Returns count."""
        conn = self._conn()
        cur = conn.execute(
            "DELETE FROM dead_letters WHERE dead_at < ?", (before,)
        )
        conn.commit()
        return cur.rowcount

    def delete(self, task_id: str) -> bool:
        """
        Delete a task by ID from the appropriate table.

        Returns True if the task was deleted, False if not found.
        Only PENDING tasks (in tasks table) and DEAD tasks (in dead_letters table)
        are eligible for deletion.
        """
        conn = self._conn()

        # Check tasks table first (PENDING, DEQUEUED, RUNNING, DONE, FAILED)
        cur = conn.execute(
            "SELECT task_id, status FROM tasks WHERE task_id = ?", (task_id,)
        )
        row = cur.fetchone()
        if row:
            status = TaskStatus(row["status"])
            if status not in (TaskStatus.PENDING, TaskStatus.DEAD):
                raise ValueError(
                    f"Cannot delete task {task_id}: status={status.name}, "
                    f"must be PENDING or DEAD"
                )
            cur2 = conn.execute(
                "DELETE FROM tasks WHERE task_id = ?", (task_id,)
            )
            conn.commit()
            return cur2.rowcount > 0

        # Check dead_letters table
        cur = conn.execute(
            "SELECT task_id FROM dead_letters WHERE task_id = ?", (task_id,)
        )
        row = cur.fetchone()
        if row:
            cur2 = conn.execute(
                "DELETE FROM dead_letters WHERE task_id = ?", (task_id,)
            )
            conn.commit()
            return cur2.rowcount > 0

        return False

    def clear_completed(self, before: float) -> int:
        """Delete completed tasks older than `before`. Returns count."""
        conn = self._conn()
        cur = conn.execute(
            "DELETE FROM tasks WHERE status = ? AND completed_at < ?",
            (TaskStatus.DONE, before),
        )
        conn.commit()
        return cur.rowcount

    # ── Metrics ─────────────────────────────────────────────────────────────

    def metrics(self, since: Optional[float] = None) -> QueueMetrics:
        """
        Return queue metrics, optionally scoped to `since` (Unix timestamp).
        Default scope: today.
        """
        if since is None:
            # Default: since midnight
            now = time.time()
            today_start = datetime.fromtimestamp(now).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            since = today_start.timestamp()

        conn = self._conn()

        pending = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = ?", (TaskStatus.PENDING,)
        ).fetchone()[0]

        running = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status IN (?, ?)",
                        (TaskStatus.RUNNING, TaskStatus.DEQUEUED),
        ).fetchone()[0]

        done_today = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = ? AND completed_at >= ?",
            (TaskStatus.DONE, since),
        ).fetchone()[0]

        failed_today = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = ? AND completed_at >= ?",
            (TaskStatus.FAILED, since),
        ).fetchone()[0]

        dead_letters = conn.execute(
            "SELECT COUNT(*) FROM dead_letters"
        ).fetchone()[0]

        # Average wait time (created → dequeued) for done tasks today
        avg_wait_row = conn.execute(
            """
            SELECT AVG(dequeued_at - created_at)
            FROM tasks
            WHERE status = ? AND completed_at >= ? AND dequeued_at IS NOT NULL
            """,
            (TaskStatus.DONE, since),
        ).fetchone()[0]
        avg_wait_time = float(avg_wait_row) if avg_wait_row else 0.0

        # Average run time (started → completed)
        avg_run_row = conn.execute(
            """
            SELECT AVG(completed_at - started_at)
            FROM tasks
            WHERE status = ? AND completed_at >= ? AND started_at IS NOT NULL
            """,
            (TaskStatus.DONE, since),
        ).fetchone()[0]
        avg_run_time = float(avg_run_row) if avg_run_row else 0.0

        return QueueMetrics(
            pending=pending,
            running=running,
            done_today=done_today,
            failed_today=failed_today,
            dead_letters=dead_letters,
            avg_wait_time=avg_wait_time,
            avg_run_time=avg_run_time,
        )

    # ── Iterator (for worker consumption) ───────────────────────────────────

    def iter_dequeue(
        self,
        worker_id: str,
        poll_interval: float = 1.0,
    ) -> Iterator[Task]:
        """
        Infinite iterator that yields tasks as they become available.

        Example:
            for task in queue.iter_dequeue("w-001"):
                print(task.payload)
                queue.done(task.task_id)
        """
        while True:
            task = self.dequeue(worker_id, max_wait=poll_interval)
            if task is not None:
                self.start(task.task_id)
                yield task

    # ── Close ────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the thread-local connection."""
        self._close_conn()


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _main():
    """Simple CLI demo."""
    import argparse

    parser = argparse.ArgumentParser(description="V5 Task Queue CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_submit = sub.add_parser("submit")
    p_submit.add_argument("payload", help='JSON payload, e.g. \'{"prompt":"hello"}\'')
    p_submit.add_argument("--priority", type=int, default=5)
    p_submit.add_argument("--timeout", type=float, default=60)
    p_submit.add_argument("--retries", type=int, default=3)
    p_submit.add_argument("--delay", type=float, default=5.0)

    sub.add_parser("list-pending")
    sub.add_parser("list-running")
    sub.add_parser("list-dead")
    sub.add_parser("metrics")

    p_recover = sub.add_parser("recover-stale")
    p_recover.add_argument("--worker", default=None)

    args = parser.parse_args()
    q = TaskQueue()

    if args.cmd == "submit":
        payload = json.loads(args.payload)
        tid = q.submit(
            payload=payload,
            priority=TaskPriority(args.priority),
            timeout=args.timeout,
            max_retries=args.retries,
            retry_delay=args.delay,
        )
        print(f"✅ Submitted: {tid}")

    elif args.cmd == "list-pending":
        for t in q.list_pending():
            print(
                f"  {t.task_id}  pri={t.priority}  retry={t.retry_count}/{t.max_retries}"
                f"  payload={json.dumps(t.payload)[:60]}"
            )

    elif args.cmd == "list-running":
        for t in q.list_running():
            print(f"  {t.task_id}  worker={t.worker_id}  started={t.started_at}")

    elif args.cmd == "list-dead":
        for t in q.list_dead_letters():
            print(f"  {t.task_id}  error={t.error[:80]}")

    elif args.cmd == "metrics":
        m = q.metrics()
        print(
            f"pending={m.pending}  running={m.running}"
            f"  done_today={m.done_today}  failed_today={m.failed_today}"
            f"  dead={m.dead_letters}"
            f"  avg_wait={m.avg_wait_time:.1f}s  avg_run={m.avg_run_time:.1f}s"
        )

    elif args.cmd == "recover-stale":
        recovered = q.recover_stale(args.worker)
        print(f"🔄 Recovered {len(recovered)} stale tasks: {recovered}")

    q.close()


if __name__ == "__main__":
    _main()

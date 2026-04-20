"""Async SQLite database layer for tasks, executions, and evaluations."""

import aiosqlite
import uuid
import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class Task(BaseModel):
    id: str
    title: str
    description: str
    status: str = "pending"
    priority: int = 0
    created_at: datetime = None
    claimed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    executor_model: str = "claude-opus-4-6"
    evaluator_model: str = "gpt-4"
    iteration_count: int = 0
    max_iterations: int = 3
    improvement_threshold: int = 7
    result: Optional[str] = None
    feedback_md: Optional[str] = None
    user_input: Optional[str] = None
    last_heartbeat: Optional[str] = None


class Execution(BaseModel):
    id: str
    task_id: str
    executor_model: str
    started_at: datetime = None
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None
    command: Optional[str] = None


class Evaluation(BaseModel):
    id: str
    task_id: str
    execution_id: str
    evaluator_model: str
    score: int
    comments: str
    created_at: datetime = None


class Database:
    def __init__(self, db_path: str = "data/tasks.db"):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    claimed_at DATETIME,
                    started_at DATETIME,
                    completed_at DATETIME,
                    executor_model TEXT DEFAULT 'claude-opus-4-6',
                    evaluator_model TEXT DEFAULT 'gpt-4',
                    iteration_count INTEGER DEFAULT 0,
                    max_iterations INTEGER DEFAULT 3,
                    improvement_threshold INTEGER DEFAULT 7,
                    result TEXT,
                    feedback_md TEXT,
                    user_input TEXT,
                    last_heartbeat DATETIME
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    executor_model TEXT NOT NULL,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    output TEXT,
                    error TEXT,
                    command TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    evaluator_model TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    comments TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id),
                    FOREIGN KEY (execution_id) REFERENCES executions(id)
                )
            """)
            # Index for stale task detection
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status_heartbeat
                ON tasks(status, last_heartbeat)
            """)
            await db.commit()

    def _row_to_task(self, row: aiosqlite.Row) -> Task:
        return Task(
            id=row["id"], title=row["title"], description=row["description"],
            status=row["status"], priority=row.get("priority", 0),
            created_at=row["created_at"], claimed_at=row["claimed_at"],
            started_at=row["started_at"], completed_at=row["completed_at"],
            executor_model=row["executor_model"], evaluator_model=row["evaluator_model"],
            iteration_count=row["iteration_count"], max_iterations=row["max_iterations"],
            improvement_threshold=row["improvement_threshold"],
            result=row["result"], feedback_md=row["feedback_md"],
            user_input=row.get("user_input"),
            last_heartbeat=row.get("last_heartbeat"),
        )

    async def claim_one_task(self, worker_id: str = "scheduler") -> Optional[Task]:
        """Atomically claim one pending task to avoid concurrent double-claiming."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM tasks WHERE status='pending'
                   ORDER BY priority DESC, created_at ASC LIMIT 1"""
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                return None
            task = self._row_to_task(row)
            await db.execute(
                """UPDATE tasks SET status='running', claimed_at=?
                   WHERE id=? AND status='pending'""",
                (datetime.now().isoformat(), task.id)
            )
            await db.commit()
            return task

    async def get_running_tasks(self) -> List[Task]:
        """Return all currently running tasks."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tasks WHERE status='running' ORDER BY started_at ASC"
            ) as cursor:
                rows = await cursor.fetchall()
            return [self._row_to_task(row) for row in rows]

    async def update_heartbeat(self, task_id: str):
        """Update the last_heartbeat timestamp for a running task."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET last_heartbeat=? WHERE id=?",
                (datetime.now().isoformat(), task_id)
            )
            await db.commit()

    async def create_task(self, title: str, description: str,
                          executor_model: str = "claude-opus-4-6",
                          evaluator_model: str = "gpt-4",
                          priority: int = 0) -> Task:
        task = Task(id=str(uuid.uuid4()), title=title, description=description,
                    executor_model=executor_model, evaluator_model=evaluator_model,
                    priority=priority)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tasks (id, title, description, status, priority,
                                  executor_model, evaluator_model, iteration_count,
                                  max_iterations, improvement_threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task.id, task.title, task.description, task.status, task.priority,
                  task.executor_model, task.evaluator_model, task.iteration_count,
                  task.max_iterations, task.improvement_threshold))
            await db.commit()
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
                row = await cursor.fetchone()
                return self._row_to_task(row) if row else None

    async def update_task_status(self, task_id: str, status: str,
                                  result: str = None, feedback_md: str = None):
        now = datetime.now().isoformat()
        fields = "status = ?"
        vals = [status]
        if status == "running":
            fields += ", started_at = ?"
            vals.append(now)
        elif status in ("completed", "evaluated", "failed", "cancelled"):
            fields += ", completed_at = ?"
            vals.append(now)
        if result:
            fields += ", result = ?"
            vals.append(result)
        if feedback_md:
            fields += ", feedback_md = ?"
            vals.append(feedback_md)
        vals.append(task_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE tasks SET {fields} WHERE id = ?", vals)
            await db.commit()

    async def update_task_field(self, task_id: str, field: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE tasks SET {field} = ? WHERE id = ?", (value, task_id))
            await db.commit()

    async def set_task_user_input(self, task_id: str, user_input: str):
        """Store user input for a waiting task."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET user_input = ? WHERE id = ?",
                (user_input, task_id)
            )
            await db.commit()

    async def clear_task_user_input(self, task_id: str):
        """Clear user input after it's been consumed."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET user_input = NULL WHERE id = ?",
                (task_id,)
            )
            await db.commit()

    async def increment_iteration(self, task_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET iteration_count = iteration_count + 1 WHERE id = ?",
                (task_id,)
            )
            await db.commit()

    async def list_tasks(self, status: str = None) -> List[Task]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                async with db.execute(
                        "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                        (status,)) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with db.execute(
                        "SELECT * FROM tasks ORDER BY created_at DESC") as cursor:
                    rows = await cursor.fetchall()
            return [self._row_to_task(row) for row in rows]

    async def delete_task(self, task_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM evaluations WHERE task_id = ?", (task_id,))
            await db.execute("DELETE FROM executions WHERE task_id = ?", (task_id,))
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await db.commit()

    async def create_execution(self, task_id: str, executor_model: str,
                               command: str = None) -> Execution:
        exec_record = Execution(
            id=str(uuid.uuid4()), task_id=task_id,
            executor_model=executor_model, command=command,
        )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO executions (id, task_id, executor_model, command)
                VALUES (?, ?, ?, ?)
            """, (exec_record.id, exec_record.task_id, exec_record.executor_model,
                  exec_record.command))
            await db.commit()
        return exec_record

    async def update_execution(self, execution_id: str, output: str = None,
                               error: str = None):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE executions SET completed_at = ?, output = ?, error = ?
                WHERE id = ?
            """, (now, output, error, execution_id))
            await db.commit()

    async def get_executions(self, task_id: str) -> List[Execution]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                    "SELECT * FROM executions WHERE task_id = ? ORDER BY started_at DESC",
                    (task_id,)) as cursor:
                rows = await cursor.fetchall()
                return [Execution(
                    id=r["id"], task_id=r["task_id"], executor_model=r["executor_model"],
                    started_at=r["started_at"], completed_at=r["completed_at"],
                    output=r["output"], error=r["error"], command=r.get("command"))
                    for r in rows]

    async def create_evaluation(self, task_id: str, execution_id: str,
                                 evaluator_model: str, score: int,
                                 comments: str) -> Evaluation:
        eval_record = Evaluation(
            id=str(uuid.uuid4()), task_id=task_id, execution_id=execution_id,
            evaluator_model=evaluator_model, score=score, comments=comments)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO evaluations (id, task_id, execution_id, evaluator_model,
                                        score, comments)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (eval_record.id, eval_record.task_id, eval_record.execution_id,
                  eval_record.evaluator_model, eval_record.score, eval_record.comments))
            await db.commit()
        return eval_record

    async def get_evaluations(self, task_id: str) -> List[Evaluation]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                    "SELECT * FROM evaluations WHERE task_id = ? ORDER BY created_at DESC",
                    (task_id,)) as cursor:
                rows = await cursor.fetchall()
                return [Evaluation(
                    id=r["id"], task_id=r["task_id"], execution_id=r["execution_id"],
                    evaluator_model=r["evaluator_model"], score=r["score"],
                    comments=r["comments"], created_at=r["created_at"])
                    for r in rows]

    async def close(self):
        pass
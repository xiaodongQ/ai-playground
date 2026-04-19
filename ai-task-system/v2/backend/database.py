import aiosqlite
import uuid
import json
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ArtifactRecord(BaseModel):
    id: str
    root_task_id: str
    parent_task_id: Optional[str] = None
    artifact_name: str
    artifact_type: str = "file"
    file_path: str = ""
    file_hash: str = ""
    version: int = 1
    dependency_declaration: str = "[]"  # JSON array of artifact IDs
    is_valid: bool = True
    is_final: bool = False
    created_by: str = "executor"
    created_at: str = ""

class Task(BaseModel):
    id: str
    title: str
    description: str
    status: str = "pending"
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
    priority: int = 5

class Execution(BaseModel):
    id: str
    task_id: str
    executor_model: str
    started_at: datetime = None
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None
    # Not stored; computed at query time as previous execution's output
    previous_output: Optional[str] = None

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
            # WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA busy_timeout=5000;")

            # Add columns if they don't exist (for existing dbs)
            for col, default in [
                ("priority", "INTEGER DEFAULT 5"),
                ("root_task_id", "TEXT"),
                ("parent_task_id", "TEXT"),
                ("dependency_artifact_ids", "TEXT DEFAULT '[]'"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE tasks ADD COLUMN {col} {default};")
                except Exception:
                    pass  # column already exists

            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
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
                    priority INTEGER DEFAULT 5,
                    root_task_id TEXT,
                    parent_task_id TEXT,
                    dependency_artifact_ids TEXT DEFAULT '[]'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    root_task_id TEXT NOT NULL,
                    parent_task_id TEXT,
                    artifact_name TEXT NOT NULL,
                    artifact_type TEXT DEFAULT 'file',
                    file_path TEXT DEFAULT '',
                    file_hash TEXT DEFAULT '',
                    version INTEGER DEFAULT 1,
                    dependency_declaration TEXT DEFAULT '[]',
                    is_valid INTEGER DEFAULT 1,
                    is_final INTEGER DEFAULT 0,
                    created_by TEXT DEFAULT 'executor',
                    created_at TEXT DEFAULT ''
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
            await db.commit()

    def _row_to_task(self, row) -> Task:
        # Handle rows that may not have priority column (existing dbs)
        priority = row[15] if len(row) > 15 else 5
        return Task(
            id=row[0], title=row[1], description=row[2], status=row[3],
            created_at=row[4], claimed_at=row[5], started_at=row[6],
            completed_at=row[7], executor_model=row[8], evaluator_model=row[9],
            iteration_count=row[10], max_iterations=row[11],
            improvement_threshold=row[12], result=row[13], feedback_md=row[14],
            priority=priority
        )

    async def claim_one_task(self):
        """Atomically claim one pending task, returning None if queue is empty.
        Uses UPDATE ... WHERE status='pending' to prevent double-claiming."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tasks WHERE status='pending' ORDER BY priority DESC, created_at ASC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
            if not row:
                return None
            task = self._row_to_task(row)
            await db.execute(
                "UPDATE tasks SET status='running', claimed_at=? WHERE id=? AND status='pending'",
                (datetime.now().isoformat(), task.id)
            )
            await db.commit()
            # Re-fetch to confirm we actually claimed it (race condition guard)
            async with db.execute("SELECT status FROM tasks WHERE id=?", (task.id,)) as cursor:
                r = await cursor.fetchone()
            if r is None or r[0] != 'running':
                return None
            return task

    async def create_task(self, title: str, description: str,
                          executor_model: str = "claude-opus-4-6",
                          evaluator_model: str = "gpt-4",
                          priority: int = 5) -> Task:
        task = Task(id=str(uuid.uuid4()), title=title, description=description,
                    executor_model=executor_model, evaluator_model=evaluator_model,
                    priority=priority)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tasks (id, title, description, status, executor_model,
                                  evaluator_model, iteration_count, max_iterations,
                                  improvement_threshold, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task.id, task.title, task.description, task.status,
                  task.executor_model, task.evaluator_model, task.iteration_count,
                  task.max_iterations, task.improvement_threshold, task.priority))
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
        elif status == "completed":
            fields += ", completed_at = ?"
            vals.append(now)
        elif status == "evaluated":
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

    async def increment_iteration(self, task_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET iteration_count = iteration_count + 1 WHERE id = ?",
                (task_id,))
            await db.commit()

    async def update_task_field(self, task_id: str, field: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE tasks SET {field} = ? WHERE id = ?", (value, task_id))
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

    async def create_artifact(self, artifact: ArtifactRecord) -> ArtifactRecord:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO artifacts (id, root_task_id, parent_task_id, artifact_name,
                    artifact_type, file_path, file_hash, version, dependency_declaration,
                    is_valid, is_final, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (artifact.id, artifact.root_task_id, artifact.parent_task_id,
                  artifact.artifact_name, artifact.artifact_type, artifact.file_path,
                  artifact.file_hash, artifact.version, artifact.dependency_declaration,
                  int(artifact.is_valid), int(artifact.is_final), artifact.created_by,
                  artifact.created_at or datetime.now().isoformat()))
            await db.commit()
        return artifact

    async def get_artifacts(self, root_task_id: str) -> List[ArtifactRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM artifacts WHERE root_task_id=? ORDER BY created_at DESC",
                (root_task_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [ArtifactRecord(
                    id=r[0], root_task_id=r[1], parent_task_id=r[2],
                    artifact_name=r[3], artifact_type=r[4], file_path=r[5],
                    file_hash=r[6], version=r[7], dependency_declaration=r[8],
                    is_valid=bool(r[9]), is_final=bool(r[10]),
                    created_by=r[11], created_at=r[12])
                    for r in rows]

    async def mark_artifact_invalid(self, artifact_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE artifacts SET is_valid=0 WHERE id=?", (artifact_id,))
            await db.commit()

    async def mark_artifact_final(self, artifact_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE artifacts SET is_final=1 WHERE id=?", (artifact_id,))
            await db.commit()

    async def delete_task(self, task_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM evaluations WHERE task_id = ?", (task_id,))
            await db.execute("DELETE FROM executions WHERE task_id = ?", (task_id,))
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await db.commit()

    async def create_execution(self, task_id: str, executor_model: str) -> Execution:
        exec_record = Execution(
            id=str(uuid.uuid4()), task_id=task_id, executor_model=executor_model)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO executions (id, task_id, executor_model)
                VALUES (?, ?, ?)
            """, (exec_record.id, exec_record.task_id, exec_record.executor_model))
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

    async def get_executions(self, task_id: str, order_desc: bool = True) -> List[Execution]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            order = "DESC" if order_desc else "ASC"
            async with db.execute(
                    f"SELECT * FROM executions WHERE task_id = ? ORDER BY started_at {order}",
                    (task_id,)) as cursor:
                rows = await cursor.fetchall()
                executions = [Execution(
                    id=r[0], task_id=r[1], executor_model=r[2],
                    started_at=r[3], completed_at=r[4], output=r[5], error=r[6])
                    for r in rows]
            # Compute previous_output: for DESC order, "previous" = next in list
            if order_desc and len(executions) > 1:
                for i, ex in enumerate(executions):
                    ex.previous_output = executions[i + 1].output if i + 1 < len(executions) else None
            return executions

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
                    id=r[0], task_id=r[1], execution_id=r[2],
                    evaluator_model=r[3], score=r[4], comments=r[5], created_at=r[6])
                    for r in rows]

    async def close(self):
        pass
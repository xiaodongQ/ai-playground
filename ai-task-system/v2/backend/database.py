import aiosqlite
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

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
    last_heartbeat: Optional[str] = None
    retry_count: int = 0
    failed_at: Optional[datetime] = None

class Execution(BaseModel):
    id: str
    task_id: str
    executor_model: str
    command: Optional[str] = None
    started_at: datetime = None
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None

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
            # 迁移：添加 command 列（如果不存在）
            try:
                await db.execute("ALTER TABLE executions ADD COLUMN command TEXT")
            except Exception:
                pass  # 列已存在

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
                    last_heartbeat TEXT,
                    retry_count INTEGER DEFAULT 0,
                    failed_at TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    executor_model TEXT NOT NULL,
                    command TEXT,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    output TEXT,
                    error TEXT,
                    exit_code INTEGER,
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            # 默认配置
            await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('cli', 'claude')")
            await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('executor_models', 'claude-opus-4-6,claude-sonnet-4-6,gpt-4,gpt-4o,gpt-3.5-turbo,minimax-chat,minimax-2.7,glm-4,qwen-turbo,qwen-plus,qwen-max,kimi-chat')")
            await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('default_executor_model', 'claude-opus-4-6')")
            await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('evaluator_models', 'gpt-4,gpt-4o,claude-opus-4-6,claude-sonnet-4-6,minimax-chat,minimax-2.7,glm-4,qwen-max,kimi-chat')")
            await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('default_evaluator_model', 'gpt-4')")
            await db.commit()
            await db.commit()

    def _row_to_task(self, row) -> Task:
        return Task(
            id=row[0], title=row[1], description=row[2], status=row[3],
            created_at=row[4], claimed_at=row[5], started_at=row[6],
            completed_at=row[7], executor_model=row[8], evaluator_model=row[9],
            iteration_count=row[10], max_iterations=row[11],
            improvement_threshold=row[12], result=row[13], feedback_md=row[14],
            last_heartbeat=row[15] if len(row) > 15 else None,
            retry_count=row[16] if len(row) > 16 else 0,
            failed_at=row[17] if len(row) > 17 else None
        )

    async def create_task(self, title: str, description: str,
                          executor_model: str = "claude-opus-4-6",
                          evaluator_model: str = "gpt-4") -> Task:
        task = Task(id=str(uuid.uuid4()), title=title, description=description,
                    executor_model=executor_model, evaluator_model=evaluator_model)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tasks (id, title, description, status, executor_model,
                                  evaluator_model, iteration_count, max_iterations,
                                  improvement_threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task.id, task.title, task.description, task.status,
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
        elif status == "completed":
            fields += ", completed_at = ?"
            vals.append(now)
        elif status == "evaluated":
            fields += ", completed_at = ?"
            vals.append(now)
        elif status == "failed":
            fields += ", failed_at = ?"
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

    async def increment_retry_count(self, task_id: str):
        """增加重试计数"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET retry_count = retry_count + 1 WHERE id = ?",
                (task_id,))
            await db.commit()

    async def reset_task_for_retry(self, task_id: str):
        """重置任务以便重试（保留 retry_count）"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET status = 'pending', last_heartbeat = NULL WHERE id = ?",
                (task_id,))
            await db.commit()

    async def update_task_field(self, task_id: str, field: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE tasks SET {field} = ? WHERE id = ?", (value, task_id))
            await db.commit()

    async def list_tasks(self, status: str = None, page: int = 1, page_size: int = 20) -> List[Task]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            offset = (page - 1) * page_size
            if status:
                query = f"SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
                async with db.execute(query, (status,)) as cursor:
                    rows = await cursor.fetchall()
            else:
                query = f"SELECT * FROM tasks ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
            return [self._row_to_task(row) for row in rows]

    async def count_tasks(self, status: str = None) -> int:
        """统计任务数量"""
        await self.init()
        sql = "SELECT COUNT(*) as count FROM tasks"
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def update_heartbeat(self, task_id: str):
        """更新任务心跳"""
        await self.init()
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET last_heartbeat = ? WHERE id = ?",
                (now, task_id)
            )
            await db.commit()

    async def batch_update_heartbeat(self, task_ids: List[str]):
        """批量更新任务心跳"""
        if not task_ids:
            return
        await self.init()
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            for task_id in task_ids:
                await db.execute(
                    "UPDATE tasks SET last_heartbeat = ? WHERE id = ?",
                    (now, task_id)
                )
            await db.commit()

    async def delete_task(self, task_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM evaluations WHERE task_id = ?", (task_id,))
            await db.execute("DELETE FROM executions WHERE task_id = ?", (task_id,))
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await db.commit()

    async def delete_all_tasks(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM evaluations")
            await db.execute("DELETE FROM executions")
            await db.execute("DELETE FROM tasks")
            await db.commit()
        return {"deleted": True}

    async def get_config(self, key: str) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def set_config(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
            await db.commit()
        return {"key": key, "value": value}

    async def get_all_config(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT key, value FROM config") as cursor:
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

    async def create_execution(self, task_id: str, executor_model: str,
                               command: str = None) -> Execution:
        exec_record = Execution(
            id=str(uuid.uuid4()), task_id=task_id, executor_model=executor_model,
            command=command)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO executions (id, task_id, executor_model, command, exit_code)
                VALUES (?, ?, ?, ?, NULL)
            """, (exec_record.id, exec_record.task_id, exec_record.executor_model, exec_record.command))
            await db.commit()
        return exec_record

    async def update_execution(self, execution_id: str, output: str = None,
                               error: str = None, command: str = None, exit_code: int = None):
        now = datetime.now().isoformat()
        fields = "completed_at = ?, output = ?, error = ?"
        vals = [now, output, error]
        if command:
            fields += ", command = ?"
            vals.append(command)
        if exit_code is not None:
            fields += ", exit_code = ?"
            vals.append(exit_code)
        vals.append(execution_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                UPDATE executions SET {fields}
                WHERE id = ?
            """, vals)
            await db.commit()

    async def get_executions(self, task_id: str) -> List[Execution]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                    "SELECT * FROM executions WHERE task_id = ? ORDER BY started_at DESC",
                    (task_id,)) as cursor:
                rows = await cursor.fetchall()
                return [Execution(
                    id=r[0], task_id=r[1], executor_model=r[2],
                    command=r[3], started_at=r[4], completed_at=r[5], output=r[6], error=r[7],
                    exit_code=r[8] if len(r) > 8 else None)
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
                    id=r[0], task_id=r[1], execution_id=r[2],
                    evaluator_model=r[3], score=r[4], comments=r[5], created_at=r[6])
                    for r in rows]

    async def close(self):
        pass
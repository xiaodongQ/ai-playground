"""
AI Task System V3 - Storage Module
SQLite 极简封装
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, List
from .models import Task, TaskStatus, Execution, Evaluation


class Storage:
    """SQLite 存储封装"""

    def __init__(self, db_path: str = "./data/tasks.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                allowed_tools TEXT DEFAULT 'Read,Write,Bash,Git',
                permission_mode TEXT DEFAULT 'acceptEdits',
                output_format TEXT DEFAULT 'text',
                json_schema TEXT,
                max_iterations INTEGER DEFAULT 3,
                current_iteration INTEGER DEFAULT 0,
                pass_threshold INTEGER DEFAULT 7,
                absolute_timeout INTEGER DEFAULT 3600,
                no_output_timeout INTEGER DEFAULT 600,
                session_id TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                duration INTEGER,
                workspace_path TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                session_id TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                output TEXT,
                error TEXT,
                status TEXT NOT NULL,
                duration INTEGER,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                execution_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                comments TEXT,
                evaluated_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        # 高频查询索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)")
        
        conn.commit()
        conn.close()

    def create_task(self, task: Task) -> Task:
        """创建任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (
                id, title, description, status, allowed_tools, permission_mode,
                output_format, json_schema, max_iterations, current_iteration,
                pass_threshold, absolute_timeout, no_output_timeout,
                session_id, created_at, started_at, completed_at, duration, workspace_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.id, task.title, task.description, task.status.value,
            task.allowed_tools, task.permission_mode, task.output_format,
            task.json_schema, task.max_iterations, task.current_iteration,
            task.pass_threshold, task.absolute_timeout, task.no_output_timeout,
            task.session_id, task.created_at.isoformat(),
            task.started_at.isoformat() if task.started_at else None,
            task.completed_at.isoformat() if task.completed_at else None,
            task.duration, task.workspace_path
        ))
        conn.commit()
        conn.close()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return Task(
            id=row[0], title=row[1], description=row[2],
            status=TaskStatus(row[3]), allowed_tools=row[4],
            permission_mode=row[5], output_format=row[6],
            json_schema=row[7], max_iterations=row[8],
            current_iteration=row[9], pass_threshold=row[10],
            absolute_timeout=row[11], no_output_timeout=row[12],
            session_id=row[13],
            created_at=datetime.fromisoformat(row[14]),
            started_at=datetime.fromisoformat(row[15]) if row[15] else None,
            completed_at=datetime.fromisoformat(row[16]) if row[16] else None,
            duration=row[17], workspace_path=row[18]
        )

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """列出任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status.value,))
        else:
            cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in rows:
            tasks.append(Task(
                id=row[0], title=row[1], description=row[2],
                status=TaskStatus(row[3]), allowed_tools=row[4],
                permission_mode=row[5], output_format=row[6],
                json_schema=row[7], max_iterations=row[8],
                current_iteration=row[9], pass_threshold=row[10],
                absolute_timeout=row[11], no_output_timeout=row[12],
                session_id=row[13],
                created_at=datetime.fromisoformat(row[14]),
                started_at=datetime.fromisoformat(row[15]) if row[15] else None,
                completed_at=datetime.fromisoformat(row[16]) if row[16] else None,
                duration=row[17], workspace_path=row[18]
            ))
        return tasks

    def update_task(self, task: Task) -> Task:
        """更新任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tasks SET
                title=?, description=?, status=?, allowed_tools=?,
                permission_mode=?, output_format=?, json_schema=?,
                max_iterations=?, current_iteration=?, pass_threshold=?,
                absolute_timeout=?, no_output_timeout=?, session_id=?,
                started_at=?, completed_at=?, duration=?, workspace_path=?
            WHERE id=?
        """, (
            task.title, task.description, task.status.value,
            task.allowed_tools, task.permission_mode, task.output_format,
            task.json_schema, task.max_iterations, task.current_iteration,
            task.pass_threshold, task.absolute_timeout, task.no_output_timeout,
            task.session_id,
            task.started_at.isoformat() if task.started_at else None,
            task.completed_at.isoformat() if task.completed_at else None,
            task.duration, task.workspace_path, task.id
        ))
        conn.commit()
        conn.close()
        return task

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

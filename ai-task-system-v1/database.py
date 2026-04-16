"""
AI Task Pickup System - SQLite Database Operations
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from contextlib import contextmanager

from models import Task, TaskCreate, TaskUpdate, TaskStatus, Evaluation


class Database:
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'code_dev',
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    created_at TEXT NOT NULL,
                    picked_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    assignee TEXT,
                    solution TEXT,
                    result TEXT,
                    logs TEXT DEFAULT '[]',
                    evaluation TEXT
                )
            """)
            conn.commit()
    
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task model"""
        task_dict = dict(row)
        
        # Parse logs JSON
        if task_dict.get('logs'):
            task_dict['logs'] = json.loads(task_dict['logs'])
        
        # Parse evaluation JSON
        if task_dict.get('evaluation'):
            eval_data = json.loads(task_dict['evaluation'])
            task_dict['evaluation'] = Evaluation(**eval_data)
        
        # Parse datetime strings
        for field in ['created_at', 'picked_at', 'started_at', 'completed_at']:
            if task_dict.get(field):
                task_dict[field] = datetime.fromisoformat(task_dict[field])
        
        return Task(**task_dict)
    
    def create_task(self, task_data: TaskCreate) -> Task:
        """Create a new task"""
        task = Task(
            title=task_data.title,
            description=task_data.description,
            type=task_data.type,
            priority=task_data.priority,
        )
        
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO tasks (id, title, description, type, status, priority, 
                                 created_at, logs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.title,
                task.description,
                task.type.value if hasattr(task.type, 'value') else task.type,
                task.status.value if hasattr(task.status, 'value') else task.status,
                task.priority.value if hasattr(task.priority, 'value') else task.priority,
                task.created_at.isoformat(),
                json.dumps(task.logs)
            ))
            conn.commit()
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return self._row_to_task(row)
        return None
    
    def get_all_tasks(self, status: Optional[str] = None) -> List[Task]:
        """Get all tasks, optionally filtered by status"""
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC",
                ).fetchall()
                # Filter in Python for enum compatibility
                tasks = [self._row_to_task(row) for row in rows]
                return [t for t in tasks if t.status == status]
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC"
                ).fetchall()
                return [self._row_to_task(row) for row in rows]
    
    def update_task(self, task_id: str, updates: TaskUpdate) -> Optional[Task]:
        """Update a task"""
        task = self.get_task(task_id)
        if not task:
            return None
        
        update_data = updates.model_dump(exclude_unset=True)
        
        if not update_data:
            return task
        
        # Convert enum values
        for key, value in update_data.items():
            if hasattr(value, 'value'):
                update_data[key] = value.value
        
        # Build SQL dynamically
        set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [task_id]
        
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()
        
        return self.get_task(task_id)
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus,
        **kwargs
    ) -> Optional[Task]:
        """Update task status and related fields"""
        task = self.get_task(task_id)
        if not task:
            return None
        
        updates = {"status": status.value if hasattr(status, 'value') else status}
        
        # Add timestamp
        now = datetime.now().isoformat()
        if status == TaskStatus.PICKED:
            updates["picked_at"] = now
        elif status == TaskStatus.EXECUTING:
            updates["started_at"] = now
        elif status == TaskStatus.COMPLETED:
            updates["completed_at"] = now
        
        # Add other fields
        for key, value in kwargs.items():
            if value is not None:
                updates[key] = value
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [task_id]
        
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()
        
        return self.get_task(task_id)
    
    def add_task_log(self, task_id: str, log: str) -> Optional[Task]:
        """Add a log entry to a task"""
        task = self.get_task(task_id)
        if not task:
            return None
        
        task.logs.append(log)
        
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET logs = ? WHERE id = ?",
                (json.dumps(task.logs), task_id)
            )
            conn.commit()
        
        return self.get_task(task_id)
    
    def set_task_result(
        self, 
        task_id: str, 
        solution: str,
        result: str
    ) -> Optional[Task]:
        """Set task execution result"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET solution = ?, result = ? WHERE id = ?",
                (solution, result, task_id)
            )
            conn.commit()
        return self.get_task(task_id)
    
    def set_task_evaluation(self, task_id: str, evaluation: Evaluation) -> Optional[Task]:
        """Set task evaluation result"""
        eval_json = json.dumps(evaluation.model_dump(), default=str)
        
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET evaluation = ? WHERE id = ?",
                (eval_json, task_id)
            )
            conn.commit()
        return self.get_task(task_id)
    
    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks ordered by priority and creation time"""
        tasks = self.get_all_tasks(status=TaskStatus.PENDING.value)
        
        # Sort by priority (high > medium > low) then by created_at
        priority_order = {"high": 0, "medium": 1, "low": 2}
        tasks.sort(key=lambda t: (
            priority_order.get(t.priority, 1),
            t.created_at
        ))
        
        return tasks

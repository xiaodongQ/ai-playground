import difflib
import os
import yaml
from pathlib import Path as _Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from backend.database import Database

router = APIRouter()

# Load config.yaml for database path
_CONFIG_PATH = _Path(__file__).parent.parent.parent / "config.yaml"
_config = {
    "database": {"path": "data/tasks.db"},
    "evaluator": {"default_model": "gpt-4o"},
}
if _CONFIG_PATH.exists():
    with open(_CONFIG_PATH) as f:
        _config = yaml.safe_load(f)

# Get db_path from config
_db_path = _config.get("database", {}).get("path", "data/tasks.db")
db = Database(db_path=_db_path)


class TaskCreate(BaseModel):
    title: str
    description: str
    executor_model: str = "claude-opus-4-6"
    evaluator_model: str = "gpt-4"
    max_iterations: int = 3
    improvement_threshold: int = 7

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    executor_model: Optional[str] = None
    evaluator_model: Optional[str] = None

@router.post("/tasks")
async def create_task(task: TaskCreate):
    await db.init()
    new_task = await db.create_task(
        title=task.title,
        description=task.description,
        executor_model=task.executor_model,
        evaluator_model=task.evaluator_model
    )
    return new_task

@router.get("/tasks")
async def list_tasks(status: Optional[str] = None):
    await db.init()
    tasks = await db.list_tasks(status=status)
    return tasks

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, task: TaskUpdate):
    await db.init()
    existing = await db.get_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.title:
        await db.update_task_field(task_id, "title", task.title)
    if task.description:
        await db.update_task_field(task_id, "description", task.description)
    if task.executor_model:
        await db.update_task_field(task_id, "executor_model", task.executor_model)
    if task.evaluator_model:
        await db.update_task_field(task_id, "evaluator_model", task.evaluator_model)
    return await db.get_task(task_id)

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete_task(task_id)
    return {"status": "deleted"}

@router.get("/tasks/{task_id}/executions")
async def get_executions(task_id: str):
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await db.get_executions(task_id)

@router.get("/tasks/{task_id}/evaluations")
async def get_evaluations(task_id: str):
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await db.get_evaluations(task_id)


@router.get("/tasks/{task_id}/executions/diff")
async def get_executions_diff(task_id: str):
    """Return diff data between consecutive executions (ASC order)."""
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get executions in ASC order for consecutive diffs
    executions = await db.get_executions(task_id, order_desc=False)
    if len(executions) < 2:
        return []

    diffs = []
    for i in range(len(executions) - 1):
        exec1 = executions[i]
        exec2 = executions[i + 1]
        out1 = exec1.output or ""
        out2 = exec2.output or ""
        diff_lines = list(difflib.unified_diff(
            out1.splitlines(),
            out2.splitlines(),
            lineterm="",
        ))
        diffs.append({
            "exec1_id": exec1.id,
            "exec2_id": exec2.id,
            "exec1_time": exec1.started_at.isoformat() if exec1.started_at else "",
            "exec2_time": exec2.started_at.isoformat() if exec2.started_at else "",
            "diff_lines": diff_lines[:100],
        })
    return diffs

@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    from backend.main import scheduler, ws_manager
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "running":
        # Kill the running subprocess
        await scheduler.executor.cancel(task_id)
    await db.update_task_status(task_id, "cancelled")
    try:
        await ws_manager.broadcast(
            {"type": "task_update", "task_id": task_id, "status": "cancelled"}
        )
    except Exception:
        pass
    return {"status": "cancelled"}


@router.get("/stats")
async def get_stats():
    await db.init()
    all_tasks = await db.list_tasks()
    pending = len([t for t in all_tasks if t.status == "pending"])
    completed = len([t for t in all_tasks if t.status == "completed"])
    evaluated = len([t for t in all_tasks if t.status == "evaluated"])
    return {
        "total": len(all_tasks),
        "pending": pending,
        "completed": completed,
        "evaluated": evaluated
    }

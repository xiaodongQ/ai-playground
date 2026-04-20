import difflib
import os
import yaml
import json
from pathlib import Path as _Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from backend.database import Database
from backend.config import get_logger

logger = get_logger(__name__)

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
    executor_model: str = ""
    evaluator_model: str = ""
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
        executor_model=task.executor_model or "",
        evaluator_model=task.evaluator_model or ""
    )
    logger.info(f"[Task] 创建任务 | ID: {new_task.id} | 标题: {new_task.title} | 模型: {new_task.executor_model or '默认'}")
    return new_task

@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, page: int = 1, page_size: int = 20):
    await db.init()
    tasks = await db.list_tasks(status=status if status else None, page=page, page_size=page_size)
    total = await db.count_tasks(status=status if status else None)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return {
        "tasks": [task.to_dict() if hasattr(task, 'to_dict') else {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "executor_model": task.executor_model,
            "evaluator_model": task.evaluator_model,
            "iteration_count": task.iteration_count,
            "max_iterations": task.max_iterations,
            "improvement_threshold": task.improvement_threshold,
            "created_at": task.created_at,
            "last_heartbeat": task.last_heartbeat,
            "retry_count": task.retry_count,
            "failed_at": task.failed_at
        } for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }

@router.get("/tasks/waiting")
async def list_waiting_tasks():
    """List all waiting tasks (waiting for dependencies)."""
    await db.init()
    tasks = await db.list_tasks(status="waiting")
    return tasks


@router.post("/tasks/{task_id}/wait")
async def set_task_waiting(task_id: str, dependency_artifact_ids: List[str]):
    """Set a task to waiting status, specifying artifact IDs it depends on."""
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.update_task_field(task_id, "dependency_artifact_ids", json.dumps(dependency_artifact_ids))
    await db.update_task_status(task_id, "waiting")
    return {"status": "waiting", "task_id": task_id}


@router.get("/tasks/{task_id}/dependencies-status")
async def check_dependencies_status(task_id: str):
    """Check if all dependencies for a waiting task are satisfied."""
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    deps = json.loads(task.dependency_artifact_ids or "[]")

    artifacts = await db.get_artifacts(task.root_task_id or task_id)
    artifact_map = {a.id: a for a in artifacts}

    results = []
    for dep_id in deps:
        if dep_id in artifact_map:
            a = artifact_map[dep_id]
            results.append({
                "artifact_id": dep_id,
                "is_valid": a.is_valid,
                "is_final": a.is_final
            })
        else:
            results.append({"artifact_id": dep_id, "is_valid": False, "is_final": False, "reason": "not_found"})

    all_ready = all(r.get("is_valid", False) for r in results)
    return {"all_satisfied": all_ready, "dependencies": results}


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
    task_title = task.title
    await db.delete_task(task_id)
    logger.info(f"[Task] 删除任务 | ID: {task_id} | 标题: {task_title}")
    return {"status": "deleted"}

@router.delete("/tasks")
async def delete_all_tasks():
    await db.init()
    count = len(await db.list_tasks())
    await db.delete_all_tasks()
    logger.info(f"[Task] 清空所有任务 | 数量: {count}")
    return {"status": "deleted all"}

@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("failed", "completed"):
        raise HTTPException(status_code=400, detail=f"Cannot retry task with status: {task.status}")

    await db.reset_task_for_retry(task_id)
    return {"status": "ok", "message": "Task reset to pending"}

@router.post("/tasks/recover")
async def recover_tasks():
    """恢复所有僵尸任务"""
    from backend.scheduler import Scheduler
    scheduler = Scheduler()
    recovered = await scheduler.recover_stale_tasks()
    return {"status": "ok", "recovered": recovered}

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
    total = await db.count_tasks()
    pending = await db.count_tasks(status="pending")
    running = await db.count_tasks(status="running")
    completed = await db.count_tasks(status="completed")
    failed = await db.count_tasks(status="failed")
    evaluated = await db.count_tasks(status="evaluated")
    waiting = await db.count_tasks(status="waiting")
    return {
        "total": total,
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed,
        "evaluated": evaluated,
        "waiting": waiting,
    }

@router.get("/config")
async def get_config():
    await db.init()
    return await db.get_all_config()

@router.get("/config/{key}")
async def get_config_key(key: str):
    await db.init()
    value = await db.get_config(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"key": key, "value": value}

@router.put("/config/{key}")
async def set_config_key(key: str, body: dict):
    await db.init()
    value = body.get("value")
    if value is None:
        raise HTTPException(status_code=400, detail="Value required")
    return await db.set_config(key, value)

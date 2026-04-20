from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from backend.database import Database
from backend.config import get_logger

logger = get_logger(__name__)

router = APIRouter()
db = Database()

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

@router.get("/stats")
async def get_stats():
    await db.init()
    total = await db.count_tasks()
    pending = await db.count_tasks(status="pending")
    running = await db.count_tasks(status="running")
    completed = await db.count_tasks(status="completed")
    failed = await db.count_tasks(status="failed")
    return {
        "total": total,
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed
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
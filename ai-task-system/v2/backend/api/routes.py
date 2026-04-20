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

    # 获取评分
    task_ids = [t.id for t in tasks]
    scores = await db.get_latest_scores(task_ids)

    def task_to_dict(task):
        d = {
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
            "failed_at": task.failed_at,
            "score": scores.get(task.id),
            "session_id": task.session_id if hasattr(task, 'session_id') else None,
            "pending_input": task.pending_input if hasattr(task, 'pending_input') else None,
            "user_input_required": task.user_input_required if hasattr(task, 'user_input_required') else False
        }
        if hasattr(task, 'to_dict'):
            d.update(task.to_dict())
        return d

    return {
        "tasks": [task_to_dict(t) for t in tasks],
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

class ContinueRequest(BaseModel):
    user_input: str

@router.post("/tasks/{task_id}/continue")
async def continue_task(task_id: str, body: ContinueRequest):
    """继续等待用户输入的任务"""
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "waiting_input":
        raise HTTPException(status_code=400, detail=f"Task is not waiting for input, current status: {task.status}")

    if not task.session_id:
        raise HTTPException(status_code=400, detail="No session_id found for this task")

    # 使用 claude -c 继续会话
    from backend.executor import Executor
    executor = Executor()
    output, error, cmd, exit_code = await executor.continue_execute(
        task.session_id, body.user_input, model=task.executor_model
    )

    logger.info(f"[{task_id}] 继续执行 | exit_code: {exit_code} | 输出长度: {len(output) if output else 0}")

    # 更新 execution
    executions = await db.get_executions(task_id)
    if executions:
        await db.update_execution(executions[0].id, output, error, command=cmd, exit_code=exit_code)

    # 检测是否还需要用户输入
    if executor.needs_user_input(output):
        # 仍然需要确认，更新 pending_input 后继续等待
        await db.update_task_field(task.id, "pending_input", output)
        await db.update_task_status(task.id, "waiting_input")
        return {"status": "waiting_input", "output": output, "needs_more_input": True}

    # 清空 pending_input
    await db.update_task_field(task.id, "pending_input", None)

    # 判断状态
    if exit_code is None or exit_code == -1:  # 超时或异常
        await db.update_task_status(task.id, "completed", result=output)
        return {"status": "completed", "output": output}
    elif exit_code != 0:  # CLI 执行失败
        await db.update_task_status(task.id, "failed", result=output)
        return {"status": "failed", "output": output}
    else:  # 成功
        await db.update_task_status(task.id, "completed", result=output)
        return {"status": "completed", "output": output}
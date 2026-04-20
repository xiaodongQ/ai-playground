"""REST API routes for task management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.database import Database
from backend.scheduler import Scheduler

router = APIRouter()
db = Database()


class TaskCreate(BaseModel):
    title: str
    description: str
    executor_model: str = "claude-opus-4-6"
    evaluator_model: str = "gpt-4"
    max_iterations: int = 3
    improvement_threshold: int = 7
    priority: int = 0


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    executor_model: Optional[str] = None
    evaluator_model: Optional[str] = None


class TaskCancel(BaseModel):
    reason: Optional[str] = None


class SubmitInputRequest(BaseModel):
    user_input: str


def set_scheduler(scheduler_instance: Scheduler):
    """Inject scheduler instance for cancel/submit operations."""
    global _scheduler
    _scheduler = scheduler_instance


_scheduler: Optional[Scheduler] = None


@router.post("/tasks")
async def create_task(task: TaskCreate):
    await db.init()
    new_task = await db.create_task(
        title=task.title,
        description=task.description,
        executor_model=task.executor_model,
        evaluator_model=task.evaluator_model,
        priority=task.priority,
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


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, cancel_req: TaskCancel = None):
    """
    Cancel a running task: SIGKILL the subprocess and mark as cancelled.
    """
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in ("pending", "running", "waiting_input"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task with status '{task.status}'"
        )

    reason = cancel_req.reason if cancel_req else "Cancelled by user"

    # Delegate to scheduler if it's running the task
    if _scheduler:
        await _scheduler.cancel_task(task_id)

    feedback_md = f"## 任务已取消\n\n原因: {reason}"
    await db.update_task_status(task_id, "cancelled", feedback_md=feedback_md)
    return {"status": "cancelled", "task_id": task_id, "reason": reason}


@router.post("/tasks/{task_id}/submit_input")
async def submit_input(task_id: str, req: SubmitInputRequest):
    """
    Submit human input for a waiting_input task and re-trigger execution.
    """
    await db.init()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "waiting_input":
        raise HTTPException(
            status_code=400,
            detail=f"Task is not waiting for input (status: {task.status})"
        )

    user_input = req.user_input.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="user_input cannot be empty")

    # Store input and re-trigger execution via scheduler
    if _scheduler:
        success = await _scheduler.submit_user_input(task_id, user_input)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to submit input")
    else:
        # Fallback: just store and set to pending
        await db.set_task_user_input(task_id, user_input)
        await db.update_task_status(task_id, "pending")

    return {"status": "input_submitted", "task_id": task_id}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Hard delete a task (only cancelled/completed/failed)."""
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


@router.get("/stats")
async def get_stats():
    await db.init()
    all_tasks = await db.list_tasks()
    stats = {
        "total": len(all_tasks),
        "pending": len([t for t in all_tasks if t.status == "pending"]),
        "running": len([t for t in all_tasks if t.status == "running"]),
        "completed": len([t for t in all_tasks if t.status == "completed"]),
        "evaluated": len([t for t in all_tasks if t.status == "evaluated"]),
        "cancelled": len([t for t in all_tasks if t.status == "cancelled"]),
        "failed": len([t for t in all_tasks if t.status == "failed"]),
        "waiting_input": len([t for t in all_tasks if t.status == "waiting_input"]),
    }
    return stats
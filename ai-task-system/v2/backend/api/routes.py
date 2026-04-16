from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from backend.database import Database

router = APIRouter()
db = Database()

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
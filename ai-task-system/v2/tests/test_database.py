import pytest
import pytest_asyncio
import asyncio
import os
import tempfile
from backend.database import Database, Task, Execution, Evaluation

@pytest_asyncio.fixture
async def db():
    # Use temp file for testing since :memory: creates separate DB per connection
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    await db.init()
    yield db
    await db.close()
    os.unlink(db_path)

@pytest.mark.asyncio
async def test_create_task(db):
    task = await db.create_task(
        title="测试任务",
        description="这是一个测试",
        executor_model="claude-opus-4-6",
        evaluator_model="gpt-4"
    )
    assert task.id is not None
    assert task.title == "测试任务"
    assert task.status == "pending"

@pytest.mark.asyncio
async def test_get_task(db):
    task = await db.create_task(title="Test", description="Desc")
    retrieved = await db.get_task(task.id)
    assert retrieved.id == task.id
    assert retrieved.title == "Test"

@pytest.mark.asyncio
async def test_update_task_status(db):
    task = await db.create_task(title="Test", description="Desc")
    await db.update_task_status(task.id, "running")
    updated = await db.get_task(task.id)
    assert updated.status == "running"

@pytest.mark.asyncio
async def test_list_tasks(db):
    await db.create_task(title="Task 1", description="Desc 1")
    await db.create_task(title="Task 2", description="Desc 2")
    tasks = await db.list_tasks()
    assert len(tasks) == 2

@pytest.mark.asyncio
async def test_delete_task(db):
    task = await db.create_task(title="Test", description="Desc")
    await db.delete_task(task.id)
    assert await db.get_task(task.id) is None
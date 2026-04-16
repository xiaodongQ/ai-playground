import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_create_task(client):
    response = await client.post("/api/tasks", json={
        "title": "Test Task",
        "description": "Test Description",
        "executor_model": "claude-opus-4-6",
        "evaluator_model": "gpt-4"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_list_tasks(client):
    await client.post("/api/tasks", json={"title": "Task 1", "description": "Desc 1"})
    await client.post("/api/tasks", json={"title": "Task 2", "description": "Desc 2"})
    response = await client.get("/api/tasks")
    assert response.status_code == 200
    assert len(response.json()) >= 2

@pytest.mark.asyncio
async def test_get_task(client):
    create_resp = await client.post("/api/tasks", json={"title": "Test", "description": "Desc"})
    task_id = create_resp.json()["id"]
    response = await client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Test"

@pytest.mark.asyncio
async def test_delete_task(client):
    create_resp = await client.post("/api/tasks", json={"title": "Test", "description": "Desc"})
    task_id = create_resp.json()["id"]
    response = await client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 200
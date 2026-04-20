"""
AI Task Pickup System - Main Application
FastAPI backend with web UI
"""
import os
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import Task, TaskCreate, TaskUpdate, TaskStatus
from database import Database
from executor import TaskExecutor
from evaluator import TaskEvaluator
from scheduler import TaskScheduler, MultiAgentScheduler

# Configuration
DB_PATH = os.environ.get("TASK_DB_PATH", "tasks.db")
WORKSPACE_DIR = os.environ.get("TASK_WORKSPACE_DIR", "./workspace")
SCHEDULER_INTERVAL = int(os.environ.get("SCHEDULER_INTERVAL", "60"))  # seconds
NUM_AGENTS = int(os.environ.get("NUM_AGENTS", "2"))

# Initialize components
db = Database(DB_PATH)
executor = TaskExecutor(workspace_dir=WORKSPACE_DIR)
evaluator = TaskEvaluator()
scheduler: Optional[MultiAgentScheduler] = None

# Create FastAPI app
app = FastAPI(
    title="AI Task Pickup System",
    description="AI-powered task management with automatic pickup and evaluation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)


# Response models
class StatusResponse(BaseModel):
    status: str
    message: str


class SchedulerStatus(BaseModel):
    running: bool
    num_agents: int
    interval: int


# API Endpoints
@app.get("/api/tasks", response_model=list[Task])
async def list_tasks(status: Optional[str] = Query(None)):
    """List all tasks, optionally filtered by status"""
    return db.get_all_tasks(status=status)


@app.post("/api/tasks", response_model=Task)
async def create_task(task_data: TaskCreate):
    """Create a new task"""
    task = db.create_task(task_data)
    return task


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """Get a specific task"""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/api/tasks/{task_id}", response_model=StatusResponse)
async def delete_task(task_id: str):
    """Delete a task"""
    if not db.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return StatusResponse(status="success", message="Task deleted")


@app.post("/api/tasks/{task_id}/execute", response_model=Task)
async def execute_task(task_id: str):
    """Manually trigger task execution"""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.PENDING, TaskStatus.PICKED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot execute task in status: {task.status}"
        )
    
    # Update to picked
    task = db.update_task_status(task_id, TaskStatus.PICKED)
    task = db.update_task_status(task_id, TaskStatus.EXECUTING)
    
    # Execute
    solution, result, logs = await executor.execute_task_sync(task)
    
    for log in logs:
        db.add_task_log(task_id, log)
    
    task = db.set_task_result(task_id, solution, result)
    task = db.update_task_status(task_id, TaskStatus.COMPLETED)
    
    # Evaluate
    evaluation = await evaluator.evaluate_task_simple(task)
    task = db.set_task_evaluation(task_id, evaluation)
    task = db.update_task_status(task_id, TaskStatus.EVALUATED)
    
    return task


@app.post("/api/tasks/{task_id}/evaluate", response_model=Task)
async def evaluate_task(task_id: str):
    """Manually trigger task evaluation"""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot evaluate task in status: {task.status}"
        )
    
    evaluation = await evaluator.evaluate_task_simple(task)
    task = db.set_task_evaluation(task_id, evaluation)
    task = db.update_task_status(task_id, TaskStatus.EVALUATED)
    
    return task


# Scheduler endpoints
@app.get("/api/scheduler/status", response_model=SchedulerStatus)
async def scheduler_status():
    """Get scheduler status"""
    return SchedulerStatus(
        running=scheduler.is_running() if scheduler else False,
        num_agents=NUM_AGENTS,
        interval=SCHEDULER_INTERVAL
    )


@app.post("/api/scheduler/start")
async def start_scheduler():
    """Start the auto-pickup scheduler"""
    global scheduler
    if scheduler and scheduler.is_running():
        return StatusResponse(status="info", message="Scheduler already running")
    
    scheduler = MultiAgentScheduler(
        db=db,
        executor=executor,
        evaluator=evaluator,
        poll_interval=SCHEDULER_INTERVAL,
        num_agents=NUM_AGENTS,
        agent_name=f"Agent-{id(scheduler) % 1000}"
    )
    scheduler.start()
    
    return StatusResponse(status="success", message="Scheduler started")


@app.post("/api/scheduler/stop")
async def stop_scheduler():
    """Stop the auto-pickup scheduler"""
    global scheduler
    if not scheduler or not scheduler.is_running():
        return StatusResponse(status="info", message="Scheduler not running")
    
    scheduler.stop()
    return StatusResponse(status="success", message="Scheduler stopped")


@app.post("/api/scheduler/trigger")
async def trigger_pickup():
    """Manually trigger one pickup cycle"""
    if not scheduler:
        raise HTTPException(status_code=400, detail="Scheduler not initialized")
    
    scheduler.run_once()
    return StatusResponse(status="success", message="Pickup triggered")


# Web UI
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web page"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    
    # Return simple inline HTML if file doesn't exist
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Task System</title>
        <meta charset="utf-8">
        <style>
            body { font-family: system-ui; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .task { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; }
            .pending { border-left: 4px solid #ffc107; }
            .executing { border-left: 4px solid #2196f3; }
            .completed { border-left: 4px solid #4caf50; }
            .evaluated { border-left: 4px solid #9c27b0; }
            .header { display: flex; justify-content: space-between; align-items: center; }
            .btn { padding: 8px 16px; cursor: pointer; }
            .btn-primary { background: #1976d2; color: white; border: none; border-radius: 4px; }
            .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
            .badge-pending { background: #ffc107; }
            .badge-executing { background: #2196f3; color: white; }
            .badge-completed { background: #4caf50; color: white; }
            .badge-evaluated { background: #9c27b0; color: white; }
            .form-group { margin: 10px 0; }
            .form-group label { display: block; margin-bottom: 5px; }
            .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 8px; }
            .log { background: #f5f5f5; padding: 10px; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto; }
        </style>
    </head>
    <body>
        <h1>🤖 AI Task Pickup System</h1>
        <div class="header">
            <div>
                <button class="btn btn-primary" onclick="showAddForm()">+ Add Task</button>
                <button class="btn" onclick="triggerPickup()">🔄 Trigger Pickup</button>
                <button class="btn" onclick="toggleScheduler()">
                    <span id="scheduler-btn">Start Scheduler</span>
                </button>
            </div>
            <div id="scheduler-status">Scheduler: Stopped</div>
        </div>
        
        <div id="add-form" style="display: none; background: #f9f9f9; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>Add New Task</h3>
            <div class="form-group">
                <label>Title</label>
                <input type="text" id="task-title" placeholder="Task title">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="task-desc" rows="4" placeholder="Task description"></textarea>
            </div>
            <div class="form-group">
                <label>Type</label>
                <select id="task-type">
                    <option value="code_dev">Code Development</option>
                    <option value="doc_summary">Document Summary</option>
                </select>
            </div>
            <div class="form-group">
                <label>Priority</label>
                <select id="task-priority">
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </select>
            </div>
            <button class="btn btn-primary" onclick="createTask()">Create</button>
            <button class="btn" onclick="hideAddForm()">Cancel</button>
        </div>
        
        <h2>Tasks</h2>
        <div id="task-list">Loading...</div>
        
        <script>
            let tasks = [];
            
            async function loadTasks() {
                const resp = await fetch('/api/tasks');
                tasks = await resp.json();
                renderTasks();
            }
            
            function renderTasks() {
                const list = document.getElementById('task-list');
                if (tasks.length === 0) {
                    list.innerHTML = '<p>No tasks yet. Create one!</p>';
                    return;
                }
                
                list.innerHTML = tasks.map(task => `
                    <div class="task ${task.status}">
                        <div style="display: flex; justify-content: space-between;">
                            <h3>${task.title}</h3>
                            <span class="badge badge-${task.status}">${task.status}</span>
                        </div>
                        <p>${task.description || ''}</p>
                        <div style="font-size: 12px; color: #666;">
                            Type: ${task.type} | Priority: ${task.priority}
                            ${task.evaluation ? ` | Score: ${task.evaluation.overall_score.toFixed(1)}/100` : ''}
                        </div>
                        <div style="font-size: 12px; color: #999;">
                            Created: ${new Date(task.created_at).toLocaleString()}
                            ${task.picked_at ? ` | Picked: ${new Date(task.picked_at).toLocaleString()}` : ''}
                            ${task.completed_at ? ` | Completed: ${new Date(task.completed_at).toLocaleString()}` : ''}
                        </div>
                        ${task.logs && task.logs.length > 0 ? `
                            <div class="log" style="margin-top: 10px;">
                                ${task.logs.slice(-5).join('<br>')}
                            </div>
                        ` : ''}
                        <div style="margin-top: 10px;">
                            <button class="btn" onclick="executeTask('${task.id}')">▶ Execute</button>
                            <button class="btn" onclick="deleteTask('${task.id}')">🗑 Delete</button>
                        </div>
                    </div>
                `).join('');
            }
            
            async function createTask() {
                const title = document.getElementById('task-title').value;
                const description = document.getElementById('task-desc').value;
                const type = document.getElementById('task-type').value;
                const priority = document.getElementById('task-priority').value;
                
                await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title, description, type, priority})
                });
                
                hideAddForm();
                loadTasks();
            }
            
            async function deleteTask(id) {
                if (!confirm('Delete this task?')) return;
                await fetch(`/api/tasks/${id}`, {method: 'DELETE'});
                loadTasks();
            }
            
            async function executeTask(id) {
                await fetch(`/api/tasks/${id}/execute`, {method: 'POST'});
                loadTasks();
            }
            
            async function triggerPickup() {
                await fetch('/api/scheduler/trigger', {method: 'POST'});
                loadTasks();
            }
            
            async function toggleScheduler() {
                const resp = await fetch('/api/scheduler/status');
                const status = await resp.json();
                if (status.running) {
                    await fetch('/api/scheduler/stop', {method: 'POST'});
                } else {
                    await fetch('/api/scheduler/start', {method: 'POST'});
                }
                updateSchedulerStatus();
            }
            
            async function updateSchedulerStatus() {
                const resp = await fetch('/api/sscheduler/status');
                const status = await resp.json();
                document.getElementById('scheduler-status').textContent = 
                    `Scheduler: ${status.running ? 'Running' : 'Stopped'}`;
                document.getElementById('scheduler-btn').textContent =
                    status.running ? 'Stop Scheduler' : 'Start Scheduler';
            }
            
            function showAddForm() {
                document.getElementById('add-form').style.display = 'block';
            }
            
            function hideAddForm() {
                document.getElementById('add-form').style.display = 'none';
            }
            
            // Load tasks on start
            loadTasks();
            updateSchedulerStatus();
            
            // Auto-refresh every 10 seconds
            setInterval(loadTasks, 10000);
        </script>
    </body>
    </html>
    """


# Create static files if needed
index_html = static_dir / "index.html"
if not index_html.exists():
    # Will be served from the inline HTML in root endpoint
    pass


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

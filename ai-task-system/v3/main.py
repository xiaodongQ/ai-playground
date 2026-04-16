"""
AI Task System V3 - Main Entry Point
CodeBuddy 个人内网专属版
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from core import Storage, Executor, Scheduler, RealtimeManager
from core.models import Task, TaskStatus


# 配置
DB_PATH = os.getenv("TASK_DB_PATH", "./data/tasks.db")
WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", "./workspace")
PORT = int(os.getenv("PORT", "8000"))

# 全局实例
storage = Storage(DB_PATH)
executor = Executor(WORKSPACE_ROOT)
scheduler = Scheduler(storage, executor)
realtime = RealtimeManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时
    scheduler.register_callback(lambda e: asyncio.create_task(
        realtime.broadcast(e["event_type"], e.get("data", {}))
    ))
    realtime.start_heartbeat()
    
    yield
    
    # 关闭时
    realtime.stop_heartbeat()
    if scheduler._running:
        await scheduler.stop()


app = FastAPI(title="AI Task System V3", lifespan=lifespan)


# ============ Web UI ============

@app.get("/", response_class=HTMLResponse)
async def index():
    """首页 - 轻量看板"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Task System V3</title>
        <meta charset="utf-8">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }
            .stat-card { background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center; }
            .stat-value { font-size: 2em; font-weight: bold; color: #007bff; }
            .stat-label { color: #666; margin-top: 5px; }
            .task-form { background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .task-list { margin-top: 20px; }
            .task-item { background: #fff; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .task-title { font-weight: bold; margin-bottom: 5px; }
            .task-status { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 0.85em; }
            .status-pending { background: #ffc; }
            .status-running { background: #cff; }
            .status-completed { background: #cfc; }
            .status-failed { background: #f99; }
            input, textarea, select { width: 100%; padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .scheduler-controls { margin: 15px 0; }
        </style>
    </head>
    <body>
        <h1>🤖 AI Task System V3</h1>
        
        <div class="stats">
            <div class="stat-card"><div class="stat-value" id="total">-</div><div class="stat-label">总任务</div></div>
            <div class="stat-card"><div class="stat-value" id="pending">-</div><div class="stat-label">待执行</div></div>
            <div class="stat-card"><div class="stat-value" id="running">-</div><div class="stat-label">运行中</div></div>
            <div class="stat-card"><div class="stat-value" id="completed">-</div><div class="stat-label">已完成</div></div>
        </div>
        
        <div class="scheduler-controls">
            调度器: <span id="scheduler-status">-</span>
            <button onclick="startScheduler()">启动</button>
            <button onclick="stopScheduler()">停止</button>
        </div>
        
        <div class="task-form">
            <h2>创建新任务</h2>
            <input type="text" id="task-title" placeholder="任务标题">
            <textarea id="task-desc" placeholder="任务详细描述" rows="4"></textarea>
            <select id="task-tools">
                <option value="Read,Write,Bash,Git">默认工具</option>
                <option value="Read,Write,Bash,Git,WebSearch">含搜索</option>
                <option value="Read,Write,Bash">仅基础</option>
            </select>
            <button onclick="createTask()">创建并执行</button>
        </div>
        
        <div class="task-list">
            <h2>任务列表</h2>
            <div id="tasks"></div>
        </div>
        
        <script>
            const ws = new WebSocket(`ws://${location.host}/ws/global`);
            ws.onmessage = (e) => {
                const event = JSON.parse(e.data);
                if (event.event_type === 'task_status_changed' || event.event_type === 'task_created') {
                    loadTasks();
                    loadStats();
                }
            };
            
            async function loadTasks() {
                const res = await fetch('/api/tasks');
                const tasks = await res.json();
                document.getElementById('tasks').innerHTML = tasks.map(t => `
                    <div class="task-item">
                        <div class="task-title">${t.title} <span class="task-status status-${t.status}">${t.status}</span></div>
                        <div>ID: ${t.id} | 创建: ${new Date(t.created_at).toLocaleString()}</div>
                    </div>
                `).join('');
            }
            
            async function loadStats() {
                const res = await fetch('/api/tasks');
                const tasks = await res.json();
                document.getElementById('total').textContent = tasks.length;
                document.getElementById('pending').textContent = tasks.filter(t => t.status === 'pending').length;
                document.getElementById('running').textContent = tasks.filter(t => t.status === 'running').length;
                document.getElementById('completed').textContent = tasks.filter(t => t.status === 'completed').length;
            }
            
            async function loadSchedulerStatus() {
                const res = await fetch('/api/scheduler/status');
                const status = await res.json();
                document.getElementById('scheduler-status').textContent = status.running ? '运行中' : '已停止';
            }
            
            async function createTask() {
                const title = document.getElementById('task-title').value;
                const description = document.getElementById('task-desc').value;
                const tools = document.getElementById('task-tools').value;
                
                await fetch('/api/tasks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title, description, allowed_tools: tools})
                });
                
                document.getElementById('task-title').value = '';
                document.getElementById('task-desc').value = '';
                loadTasks();
            }
            
            async function startScheduler() {
                await fetch('/api/scheduler/start', {method: 'POST'});
                loadSchedulerStatus();
            }
            
            async function stopScheduler() {
                await fetch('/api/scheduler/stop', {method: 'POST'});
                loadSchedulerStatus();
            }
            
            loadTasks();
            loadStats();
            loadSchedulerStatus();
        </script>
    </body>
    </html>
    """


# ============ WebSocket ============

@app.websocket("/ws/global")
async def websocket_global(websocket: WebSocket):
    """全局事件 WebSocket"""
    await realtime.connect_global(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect(websocket)


@app.websocket("/ws/tasks/{task_id}")
async def websocket_task(task_id: str, websocket: WebSocket):
    """单任务事件 WebSocket"""
    await realtime.connect_task(task_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect(websocket, task_id)


# ============ API Routes ============

@app.get("/api/tasks")
async def list_tasks():
    """列出所有任务"""
    tasks = storage.list_tasks()
    return [t.model_dump() for t in tasks]


@app.post("/api/tasks")
async def create_task(task: Task):
    """创建新任务"""
    task = storage.create_task(task)
    
    # 触发回调
    await realtime.send_task_created(task.model_dump())
    
    return task


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    success = storage.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@app.post("/api/tasks/{task_id}/execute")
async def execute_task(task_id: str):
    """手动执行任务"""
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await scheduler.pick_and_execute(task)
    return {"status": "executed", "task_id": task_id}


@app.get("/api/scheduler/status")
async def scheduler_status():
    """获取调度器状态"""
    return scheduler.get_status()


@app.post("/api/scheduler/start")
async def scheduler_start():
    """启动调度器"""
    return scheduler.start()


@app.post("/api/scheduler/stop")
async def scheduler_stop():
    """停止调度器"""
    return await scheduler.stop()


@app.post("/api/scheduler/trigger")
async def scheduler_trigger():
    """触发一次领取"""
    return await scheduler.trigger()


if __name__ == "__main__":
    import uvicorn
    
    # 确保目录存在
    os.makedirs("./data", exist_ok=True)
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    
    uvicorn.run(app, host="127.0.0.1", port=PORT)

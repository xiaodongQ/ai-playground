import os
import yaml
from pathlib import Path

# Load config.yaml from v2 root
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
_default_config = {
    "server": {"host": "0.0.0.0", "port": 8000},
    "database": {"path": "data/tasks.db"},
    "executor": {"engine": "cli", "cli_path": "claw", "sdk_path": "claw", "timeout": 300},
    "sdk": {"permission_mode": "bypassPermissions", "model": "claude-opus-4-6"},
    "evaluator": {"default_model": "gpt-4o", "timeout": 60},
}
if CONFIG_PATH.exists():
    with open(CONFIG_PATH) as f:
        _default_config = yaml.safe_load(f)

config = _default_config

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi import WebSocket, WebSocketDisconnect
from backend.api.routes import router as api_router
from backend.scheduler import Scheduler
from backend.websocket_manager import WebSocketManager

app = FastAPI(title="AI Task System")
scheduler = Scheduler()
ws_manager = WebSocketManager()

app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/scheduler/start")
async def start_scheduler():
    return await scheduler.start()

@app.post("/api/scheduler/stop")
async def stop_scheduler():
    return await scheduler.stop()

@app.get("/api/scheduler/status")
async def scheduler_status():
    return {"running": scheduler._running}

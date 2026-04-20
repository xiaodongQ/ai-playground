"""FastAPI application entry point with WebSocket support."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from backend.api import routes
from backend.api.routes import set_scheduler
from backend.scheduler import Scheduler
from backend.websocket_manager import WebSocketManager

app = FastAPI(title="AI Task System v2.4")

# Global WebSocket manager
ws_manager = WebSocketManager()

# Global scheduler
scheduler = Scheduler(ws_manager=ws_manager)

# Wire scheduler into routes for cancel/submit operations
set_scheduler(scheduler)

# Include API router
app.include_router(routes.router, prefix="/api")


@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "v2.4"}


@app.post("/api/scheduler/start")
async def start_scheduler():
    return await scheduler.start()


@app.post("/api/scheduler/stop")
async def stop_scheduler():
    return await scheduler.stop()


@app.get("/api/scheduler/status")
async def scheduler_status():
    return {
        "running": scheduler._running,
        "task_timeout": scheduler.task_timeout,
        "no_output_timeout": scheduler.no_output_timeout,
        "stale_threshold": scheduler.stale_threshold,
        "concurrency": scheduler.concurrency,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
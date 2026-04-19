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
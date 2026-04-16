from fastapi import FastAPI
from fastapi.responses import FileResponse
from backend.api.routes import router as api_router
from backend.scheduler import Scheduler

app = FastAPI(title="AI Task System")
scheduler = Scheduler()

app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

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
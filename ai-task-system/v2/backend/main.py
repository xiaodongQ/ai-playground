import os
from backend.config import setup_logging, get_logger

# 初始化日志
logger = get_logger(__name__)
config_module = setup_logging()

import logging
from fastapi import FastAPI
from fastapi.responses import FileResponse
from backend.api.routes import router as api_router
from backend.scheduler import Scheduler
from backend.database import Database

app = FastAPI(title="AI Task System")
scheduler = Scheduler()

logger.info("=" * 50)
logger.info("AI Task System 服务启动")
logger.info("=" * 50)

app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    # 确保 data 目录存在
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"创建数据目录: {data_dir}")

    logger.info("=" * 50)
    logger.info("AI Task System 启动恢复")
    logger.info("=" * 50)
    recovered = await scheduler.recover_stale_tasks()
    if recovered > 0:
        logger.info(f"启动时恢复 {recovered} 个僵尸任务")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("服务关闭")

@app.post("/api/scheduler/start")
async def start_scheduler():
    db = Database()
    await db.init()
    cli = await db.get_config("cli") or "claude"
    scheduler.cli = cli
    scheduler.executor.cli = cli
    result = await scheduler.start()
    logger.info(f"调度器启动 | CLI: {scheduler.cli} | 间隔: {scheduler.poll_interval}s")
    return result

@app.post("/api/scheduler/stop")
async def stop_scheduler():
    result = await scheduler.stop()
    logger.info("调度器停止")
    return result

@app.get("/api/scheduler/status")
async def scheduler_status():
    return {"running": scheduler._running}
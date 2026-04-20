"""
AI Task System V3 - Scheduler Module
双模式任务调度器
"""
import asyncio
from datetime import datetime
from typing import Optional, Callable
from .models import Task, TaskStatus


class Scheduler:
    """双模式任务调度器"""

    def __init__(
        self,
        storage,
        executor,
        interval: int = 30,
        max_concurrent: int = 2
    ):
        self.storage = storage
        self.executor = executor
        self.interval = interval
        self.max_concurrent = max_concurrent
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks = []

    def register_callback(self, callback: Callable):
        """注册状态变更回调"""
        self._callbacks.append(callback)

    async def _notify(self, event: dict):
        """通知所有回调"""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass

    async def pick_and_execute(self, task: Task):
        """领取并执行单个任务"""
        # 更新任务状态为运行中
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.storage.update_task(task)
        
        await self._notify({
            "event_type": "task_status_changed",
            "task_id": task.id,
            "old_status": "pending",
            "new_status": "running"
        })
        
        # 执行任务
        result = await self.executor.execute(task)
        
        # 更新任务状态
        task.completed_at = datetime.now()
        task.duration = int((task.completed_at - task.started_at).total_seconds())
        task.status = TaskStatus.COMPLETED if result["success"] else TaskStatus.FAILED
        self.storage.update_task(task)
        
        await self._notify({
            "event_type": "task_completed" if result["success"] else "task_failed",
            "task_id": task.id,
            "result": result
        })

    async def _run_loop(self):
        """定时轮询循环"""
        while self._running:
            try:
                # 获取待执行任务
                pending_tasks = self.storage.list_tasks(TaskStatus.PENDING)
                
                if pending_tasks:
                    # 按创建时间排序，取第一个
                    task = pending_tasks[0]
                    await self.pick_and_execute(task)
                    
            except Exception as e:
                await self._notify({
                    "event_type": "scheduler_error",
                    "error": str(e)
                })
            
            await asyncio.sleep(self.interval)

    def start(self):
        """启动调度器"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            return {"status": "started", "interval": self.interval}
        return {"status": "already_running"}

    async def stop(self):
        """停止调度器"""
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
            return {"status": "stopped"}
        return {"status": "not_running"}

    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "running": self._running,
            "interval": self.interval,
            "max_concurrent": self.max_concurrent
        }

    async def trigger(self):
        """手动触发一次领取"""
        pending_tasks = self.storage.list_tasks(TaskStatus.PENDING)
        if pending_tasks:
            task = pending_tasks[0]
            await self.pick_and_execute(task)
            return {"status": "picked", "task_id": task.id}
        return {"status": "no_pending_tasks"}

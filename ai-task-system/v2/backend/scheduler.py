import asyncio
from datetime import datetime
from typing import Optional
from backend.database import Database
from backend.executor import Executor
from backend.evaluator import Evaluator
from backend.retry import RetryExecutor, RetryConfig


class Scheduler:
    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self._running = False
        self._task = None
        self.db = Database()
        self.executor = Executor()
        self.evaluator = Evaluator()
        self.retry_executor = RetryExecutor(self.executor, RetryConfig())

    async def start(self):
        self._running = True
        await self.db.init()
        self._task = asyncio.create_task(self._poll_loop())
        return {"status": "started"}

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        return {"status": "stopped"}

    async def _poll_loop(self):
        while self._running:
            try:
                await self._process_pending_tasks()
            except Exception as e:
                print(f"Scheduler error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _process_pending_tasks(self):
        # Atomically claim exactly one task per poll cycle
        task = await self.db.claim_one_task()
        if not task:
            return
        # Execute without blocking the poll loop
        asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task):
        try:
            # Broadcast running status
            try:
                from backend.main import ws_manager
                await ws_manager.broadcast(
                    {"type": "task_update", "task_id": task.id, "status": "running"}
                )
            except Exception:
                pass  # WebSocket not yet ready

            execution = await self.db.create_execution(task.id, task.executor_model)

            output, error = await self.retry_executor.execute_with_retry(task)
            await self.db.update_execution(execution.id, output, error or "")

            if error and "timeout" in error.lower():
                await self.db.update_task_status(task.id, "failed")
            else:
                await self.db.update_task_status(task.id, "completed", result=output)
                await self._evaluate_task(task, execution, output)
        except Exception as e:
            await self.db.update_task_status(task.id, "failed")

        # Broadcast final status
        try:
            from backend.main import ws_manager
            task = await self.db.get_task(task.id)
            if task:
                await ws_manager.broadcast(
                    {"type": "task_update", "task_id": task.id, "status": task.status}
                )
        except Exception:
            pass

    async def _evaluate_task(self, task, execution, output):
        await self.db.update_task_status(task.id, "evaluating")

        try:
            parsed = await self.evaluator.evaluate(
                task.description, output, iteration_count=task.iteration_count,
                model=task.evaluator_model
            )
        except Exception as e:
            parsed = {"score": 5, "comments": f"### 评分: 5/10\n### 错误\n{str(e)}"}

        await self.db.create_evaluation(
            task.id, execution.id, task.evaluator_model,
            parsed["score"], parsed["comments"]
        )

        feedback_md = self.evaluator.build_feedback_md(
            task.description, output, parsed["comments"], task.iteration_count
        )

        if parsed["score"] < task.improvement_threshold:
            if task.iteration_count < task.max_iterations:
                await self.db.increment_iteration(task.id)
                await self.db.update_task_status(task.id, "re-execute", feedback_md=feedback_md)
            else:
                await self.db.update_task_status(task.id, "evaluated", feedback_md=feedback_md)
        else:
            await self.db.update_task_status(task.id, "evaluated", feedback_md=feedback_md)

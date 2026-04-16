import asyncio
from datetime import datetime
from typing import Optional
from backend.database import Database
from backend.executor import Executor
from backend.evaluator import Evaluator

class Scheduler:
    def __init__(self, poll_interval: int = 5):
        self.poll_interval = poll_interval
        self._running = False
        self._task = None
        self.db = Database()
        self.executor = Executor()
        self.evaluator = Evaluator()

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        return {"status": "started"}

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        return {"status": "stopped"}

    async def _poll_loop(self):
        await self.db.init()
        while self._running:
            try:
                await self._process_pending_tasks()
            except Exception as e:
                print(f"Scheduler error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _process_pending_tasks(self):
        tasks = await self.db.list_tasks(status="pending")
        for task in tasks:
            await self._execute_task(task)

    async def _execute_task(self, task):
        # 更新状态为 running
        await self.db.update_task_status(task.id, "running")

        # 创建执行记录
        execution = await self.db.create_execution(task.id, task.executor_model)

        # 调用执行引擎
        output, error = await self.executor.execute(
            task.id, task.executor_model, task.description, task.feedback_md
        )

        # 更新执行记录
        await self.db.update_execution(execution.id, output, error)

        # 更新任务状态为 completed
        await self.db.update_task_status(task.id, "completed", result=output)

        # 触发评估
        await self._evaluate_task(task, execution, output)

    async def _evaluate_task(self, task, execution, output):
        await self.db.update_task_status(task.id, "evaluating")

        # 构建评估 prompt
        eval_prompt = self.evaluator.build_evaluation_prompt(
            task.description, output, iteration_count=task.iteration_count
        )

        # TODO: 调用评估模型 API（实际实现时需要接入 API）
        # 这里先用模拟结果
        evaluation_result = f"""### 评分: 7/10
### 优点
- 任务已完成基本要求

### 问题
- 可以进一步优化

### 改进建议
1. 建议添加错误处理
"""

        # 解析评估
        parsed = self.evaluator.parse_evaluation(evaluation_result)

        # 创建评估记录
        await self.db.create_evaluation(
            task.id, execution.id, task.evaluator_model,
            parsed["score"], parsed["comments"]
        )

        # 构建反馈 MD
        feedback_md = self.evaluator.build_feedback_md(
            task.description, output, evaluation_result, task.iteration_count
        )

        # 判断是否需要重新执行
        if parsed["score"] < task.improvement_threshold:
            if task.iteration_count < task.max_iterations:
                await self.db.increment_iteration(task.id)
                await self.db.update_task_status(task.id, "re-execute", feedback_md=feedback_md)
            else:
                await self.db.update_task_status(task.id, "evaluated", feedback_md=feedback_md)
        else:
            await self.db.update_task_status(task.id, "evaluated", feedback_md=feedback_md)
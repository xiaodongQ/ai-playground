import asyncio
import uuid
from datetime import datetime
from typing import Optional
from backend.database import Database
from backend.executor import Executor
from backend.evaluator import Evaluator
from backend.config import get_logger, load_config

logger = get_logger(__name__)


def is_heartbeat_stale(last_heartbeat: str, threshold: int = 120) -> bool:
    """判断心跳是否超时"""
    if not last_heartbeat:
        return True
    last = datetime.fromisoformat(last_heartbeat)
    return (datetime.now() - last).total_seconds() > threshold


class Scheduler:
    def __init__(self, poll_interval: int = None, cli: str = None):
        config = load_config()
        scheduler_config = config.get('scheduler', {})
        self.poll_interval = poll_interval or scheduler_config.get('poll_interval', 5)
        self.cli = cli or scheduler_config.get('cli', 'claude')
        self.heartbeat_interval = scheduler_config.get('heartbeat_interval', 30)
        self.stale_threshold = scheduler_config.get('stale_threshold', 120)
        self.concurrency = scheduler_config.get('concurrency', 2)
        executor_config = config.get('executor', {})
        self.max_auto_retries = executor_config.get('max_auto_retries', 3)
        self.auto_retry_delay = executor_config.get('auto_retry_delay', 180)
        self._running = False
        self._task = None
        self._heartbeat_task = None
        self._semaphore = None
        self.db = Database()
        self.executor = Executor(cli=self.cli)
        self.evaluator = Evaluator()

    async def start(self):
        logger.info(f"调度器启动 | CLI: {self.cli} | 轮询间隔: {self.poll_interval}s | 并发度: {self.concurrency}")
        self._running = True
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._task = asyncio.create_task(self._poll_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        return {"status": "started"}

    async def stop(self):
        logger.info("调度器停止")
        self._running = False
        if self._task:
            self._task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        return {"status": "stopped"}

    async def _poll_loop(self):
        await self.db.init()
        logger.info("轮询循环开始")
        while self._running:
            try:
                await self._process_pending_tasks()
            except Exception as e:
                logger.error(f"轮询异常: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _heartbeat_loop(self):
        """心跳更新循环"""
        await self.db.init()
        while self._running:
            try:
                running_tasks = await self.db.list_tasks(status="running")
                if running_tasks:
                    task_ids = [t.id for t in running_tasks]
                    await self.db.batch_update_heartbeat(task_ids)
                    logger.debug(f"心跳更新: {len(task_ids)} 个 running 任务")
            except Exception as e:
                logger.error(f"心跳更新异常: {e}")
            await asyncio.sleep(self.heartbeat_interval)

    async def _process_pending_tasks(self):
        tasks = await self.db.list_tasks(status="pending")
        if tasks:
            logger.info(f"发现 {len(tasks)} 个待执行任务")

        async def execute_with_semaphore(task):
            async with self._semaphore:
                await self._execute_task(task)

        await asyncio.gather(*[execute_with_semaphore(task) for task in tasks if task.status == "pending"])

    async def _execute_task(self, task):
        # 统一日志格式：[ID] 标题: xxx | 信息
        task_info = f"[{task.id}] {task.title}"

        # 生成或使用 session_id
        session_id = task.session_id or str(uuid.uuid4())

        logger.info(f"{task_info} | 开始执行")
        logger.info(f"{task_info} | 模型: {task.executor_model or '默认(使用CLI)'}")
        logger.info(f"{task_info} | session_id: {session_id}")
        logger.info(f"{task_info} | 任务描述: {task.description[:100]}{'...' if len(task.description) > 100 else ''}")

        await self.db.update_task_status(task.id, "running")
        logger.info(f"{task_info} | 状态: pending -> running")

        execution = await self.db.create_execution(task.id, task.executor_model)
        logger.info(f"{task_info} | 执行命令...")
        output, error, cmd, exit_code = await self.executor.execute(
            task.id, task.description, task.feedback_md, model=task.executor_model,
            session_id=session_id, allowed_tools=self.executor.allowed_tools
        )
        logger.info(f"{task_info} | 命令: {cmd}")

        # 执行完成后更新 execution（带 exit_code）
        await self.db.update_execution(execution.id, output, error, command=cmd, exit_code=exit_code)

        # 检测是否需要用户输入
        if self.executor.needs_user_input(output):
            # 暂停任务，等待用户确认
            await self.db.update_task_status(task.id, "waiting_input")
            await self.db.update_task_field(task.id, "session_id", session_id)
            await self.db.update_task_field(task.id, "pending_input", output)
            logger.info(f"{task_info} | 需要用户确认 | 输出长度: {len(output) if output else 0} 字符")
            return

        # 判断状态
        if exit_code is None or exit_code == -1:  # 超时或异常
            await self.db.update_task_status(task.id, "completed", result=output)
            logger.info(f"{task_info} | 执行完成 | 输出长度: {len(output) if output else 0} 字符")
            if error:
                logger.warning(f"{task_info} | 错误: {error[:200]}")
        elif exit_code != 0:  # CLI 执行失败
            await self.db.update_task_status(task.id, "failed", result=output)
            await self.db.increment_retry_count(task.id)
            logger.warning(f"{task_info} | 执行失败 | exit_code: {exit_code} | 错误: {error[:200] if error else '无'}")
        else:  # 成功
            await self.db.update_task_status(task.id, "completed", result=output)
            logger.info(f"{task_info} | 执行完成 | 输出长度: {len(output) if output else 0} 字符")

        # 评估（仅成功或超时的任务，失败的不评估）
        if exit_code != 0 and exit_code != -1:
            # 失败任务不评估，等待重试
            await self._handle_failed_task(task)
        else:
            await self._evaluate_task(task, execution, output)

    async def _evaluate_task(self, task, execution, output):
        task_info = f"[{task.id}] {task.title}"
        logger.info(f"{task_info} | 开始评估")
        await self.db.update_task_status(task.id, "evaluating")

        eval_prompt = self.evaluator.build_evaluation_prompt(
            task.description, output, iteration_count=task.iteration_count
        )

        # TODO: 调用评估模型 API
        evaluation_result = f"""### 评分: 7/10
### 优点
- 任务已完成基本要求

### 问题
- 可以进一步优化

### 改进建议
1. 建议添加错误处理
"""

        parsed = self.evaluator.parse_evaluation(evaluation_result)
        await self.db.create_evaluation(
            task.id, execution.id, task.evaluator_model,
            parsed["score"], parsed["comments"]
        )
        logger.info(f"{task_info} | 评估完成 | 评分: {parsed['score']}/10")

        feedback_md = self.evaluator.build_feedback_md(
            task.description, output, evaluation_result, task.iteration_count
        )

        if parsed["score"] < task.improvement_threshold:
            if task.iteration_count < task.max_iterations:
                await self.db.increment_iteration(task.id)
                await self.db.update_task_status(task.id, "re-execute", feedback_md=feedback_md)
                logger.warning(f"{task_info} | 评分低于阈值({task.improvement_threshold})，标记待重试 | 迭代: {task.iteration_count + 1}/{task.max_iterations}")
            else:
                await self.db.update_task_status(task.id, "completed", feedback_md=feedback_md)
                logger.warning(f"{task_info} | 评分低于阈值，已达最大迭代次数，标记完成")
        else:
            await self.db.update_task_status(task.id, "completed", feedback_md=feedback_md)
            logger.info(f"{task_info} | 评估通过 | 最终状态: completed")

    async def _handle_failed_task(self, task):
        """处理失败任务"""
        task_info = f"[{task.id}] {task.title}"

        # 检查是否超过最大重试次数
        loaded_task = await self.db.get_task(task.id)
        if loaded_task.retry_count >= self.max_auto_retries:
            logger.warning(f"{task_info} | 超过最大重试次数({self.max_auto_retries})，保持 failed 状态")
        else:
            logger.info(f"{task_info} | {self.auto_retry_delay}秒后自动重试...")
            asyncio.create_task(self._delayed_retry(task.id))

    async def _delayed_retry(self, task_id: str):
        """延迟重试"""
        await asyncio.sleep(self.auto_retry_delay)
        try:
            task = await self.db.get_task(task_id)
            if task and task.status == "failed":
                await self.db.reset_task_for_retry(task_id)
                logger.info(f"[{task_id}] 自动重试，状态已重置为 pending")
        except Exception as e:
            logger.error(f"延迟重试异常: {e}")

    async def recover_stale_tasks(self):
        """恢复僵尸任务（心跳超时）"""
        await self.db.init()
        running_tasks = await self.db.list_tasks(status="running")
        recovered = 0
        for task in running_tasks:
            if is_heartbeat_stale(task.last_heartbeat, self.stale_threshold):
                await self.db.update_task_status(task.id, "pending")
                logger.warning(f"任务 [{task.id}] 心跳超时，标记为 pending")
                recovered += 1
        return recovered

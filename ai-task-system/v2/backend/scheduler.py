import asyncio
import uuid
from datetime import datetime
from typing import Optional
from backend.database import Database
from backend.executor import Executor
from backend.evaluator import Evaluator
from backend.retry import RetryExecutor, RetryConfig
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
        self.concurrency = scheduler_config.get('concurrency', 2)  # 并发数
        executor_config = config.get('executor', {})
        self.max_auto_retries = executor_config.get('max_auto_retries', 3)
        self.auto_retry_delay = executor_config.get('auto_retry_delay', 180)
        self._running = False
        self._task = None
        self._heartbeat_task = None
        self._semaphore = None
        self.db = Database()
        # 用 RetryExecutor 包装，实现指数退避
        self.executor = RetryExecutor(
            Executor(cli=self.cli),
            config=RetryConfig(
                max_retries=self.max_auto_retries,
                base_delay=2.0,
                max_delay=30.0
            )
        )
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
        # 并发执行任务（受 semaphore 控制）
        async def execute_with_semaphore(task):
            async with self._semaphore:
                await self._execute_task(task)

        await asyncio.gather(*[execute_with_semaphore(task) for task in tasks if task.status == "pending"])

    async def _execute_task(self, task):
        # 统一日志格式：[ID] 标题: xxx | 信息
        task_info = f"[{task.id}] {task.title}"

        await self.db.update_task_status(task.id, "running")
        logger.info(f"{task_info} | 状态: pending -> running")

        # 生成或使用 session_id
        session_id = task.session_id or str(uuid.uuid4())

        # 构建完整的执行信息
        model_info = f"模型: {task.executor_model}" if task.executor_model else "模型: CLI默认"
        tools_info = f"工具: {self.executor.allowed_tools}" if self.executor.allowed_tools else "工具: 无限制"
        logger.info(f"{task_info} | 开始执行 | {model_info} | {tools_info}")
        logger.info(f"{task_info} | session_id: {session_id}")
        logger.info(f"{task_info} | 任务描述: {task.description[:100]}{'...' if len(task.description) > 100 else ''}")

        # 执行前先构建命令并存储（便于 UI 实时显示）
        cmd = self.executor.build_command(
            task.id, task.description,
            model=task.executor_model, session_id=session_id,
            allowed_tools=self.executor.allowed_tools
        )
        cmd_str = self.executor._cmd_to_str(cmd)
        execution = await self.db.create_execution(task.id, task.executor_model, command=cmd_str)
        logger.info(f"{task_info} | 执行命令: {cmd}")
        output, error, _, exit_code = await self.executor.execute(
            task.id, task.description, task.feedback_md,
            model=task.executor_model, session_id=session_id,
            allowed_tools=self.executor.allowed_tools
        )

        # 执行完成后更新 execution（带 exit_code）
        await self.db.update_execution(execution.id, output, error, command=cmd_str, exit_code=exit_code)

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
            await self._evaluate_task(task, execution, output)
        elif exit_code != 0:  # CLI 执行失败（RetryExecutor 已处理重试，仍失败）
            await self.db.update_task_status(task.id, "failed", result=output)
            await self.db.increment_retry_count(task.id)
            logger.warning(f"{task_info} | 执行失败（已重试）| exit_code: {exit_code} | 错误: {error[:200] if error else '无'}")
        else:  # 成功
            await self.db.update_task_status(task.id, "completed", result=output)
            logger.info(f"{task_info} | 执行完成 | 输出长度: {len(output) if output else 0} 字符")
            await self._evaluate_task(task, execution, output)

    async def _evaluate_task(self, task, execution, output):
        task_info = f"[{task.id}] {task.title}"
        logger.info(f"{task_info} | 开始评估")
        await self.db.update_task_status(task.id, "evaluating")

        eval_prompt = self.evaluator.build_evaluation_prompt(
            task.description, output, iteration_count=task.iteration_count
        )

        # 调用评估器进行真实评估
        score, evaluation_result = await self.evaluator.evaluate(
            task.description, output, iteration_count=task.iteration_count
        )

        parsed = self.evaluator.parse_evaluation(evaluation_result)
        await self.db.create_evaluation(
            task.id, execution.id, task.evaluator_model,
            score, evaluation_result
        )
        logger.info(f"{task_info} | 评估完成 | 评分: {score}/10")

        feedback_md = self.evaluator.build_feedback_md(
            task.description, output, evaluation_result, task.iteration_count
        )

        if score < task.improvement_threshold:
            await self.db.update_task_status(task.id, "completed", feedback_md=feedback_md)
            logger.warning(f"{task_info} | 评分低于阈值({task.improvement_threshold})，请手动优化后重试")
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
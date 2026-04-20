import random
import asyncio
from dataclasses import dataclass


@dataclass
class RetryConfig:
    """重试配置：指数退避策略"""
    max_retries: int = 3
    base_delay: float = 2.0
    max_delay: float = 30.0


class RetryExecutor:
    """包装执行器，添加指数退避重试能力"""

    def __init__(self, executor, config: RetryConfig = None):
        self.executor = executor
        self.config = config or RetryConfig()

    async def execute_with_retry(self, task):
        """执行任务，带指数退避重试。返回 (output, error) 元组。"""
        last_error = None
        for attempt in range(self.config.max_retries):
            output, error = await self.executor.execute(
                task.id, task.executor_model, task.description, task.feedback_md
            )
            if error is None:
                return output, None  # 成功

            last_error = error
            if attempt < self.config.max_retries - 1:
                delay = min(self.config.base_delay * (2 ** attempt), self.config.max_delay)
                delay += random.uniform(-0.5, 0.5)
                await asyncio.sleep(delay)

        return output, last_error  # 最终结果

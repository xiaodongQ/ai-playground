"""
RetryExecutor - 指数退避重试包装器
"""
import asyncio
import random
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class RetryConfig:
    """重试配置：指数退避策略"""
    max_retries: int = 3
    base_delay: float = 2.0  # 初始延迟秒
    max_delay: float = 30.0   # 最大延迟秒
    jitter: float = 0.5       # 随机抖动范围


class RetryExecutor:
    """包装执行器，添加指数退避重试能力"""

    def __init__(self, executor, config: RetryConfig = None):
        self.executor = executor
        self.config = config or RetryConfig()

    def needs_user_input(self, output: str) -> bool:
        """代理到内部执行器"""
        return self.executor.needs_user_input(output)

    async def execute(self, task_id: str, description: str,
                      feedback_md: Optional[str] = None,
                      model: Optional[str] = None,
                      session_id: str = None,
                      allowed_tools: str = None) -> Tuple[str, Optional[str], str, Optional[int]]:
        """
        执行任务，失败时指数退避重试。
        返回 (output, error, command, exit_code)
        """
        last_error = None
        last_cmd = None

        for attempt in range(self.config.max_retries):
            output, error, cmd, exit_code = await self.executor.execute(
                task_id, description, feedback_md,
                model=model, session_id=session_id,
                allowed_tools=allowed_tools
            )
            last_cmd = cmd

            # 成功或无需重试
            if exit_code == 0 or exit_code is None:
                return output, error, cmd, exit_code

            # 最后一次尝试失败
            if attempt >= self.config.max_retries - 1:
                return output, error, cmd, exit_code

            # 指数退避 + 随机抖动
            delay = min(self.config.base_delay * (2 ** attempt), self.config.max_delay)
            delay += random.uniform(-self.config.jitter, self.config.jitter)
            await asyncio.sleep(delay)

        return output, last_error, last_cmd, -1

"""RetryExecutor - Exponential backoff retry wrapper for task execution."""

import asyncio
import random
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class RetryConfig:
    """Retry configuration with exponential backoff strategy."""
    max_retries: int = 3
    base_delay: float = 2.0
    max_delay: float = 30.0
    jitter: float = 0.5


class RetryExecutor:
    """Wraps an executor with exponential backoff retry capability."""

    def __init__(self, executor, config: RetryConfig = None):
        self.executor = executor
        self.config = config or RetryConfig()

    def needs_user_input(self, output: str) -> bool:
        """Delegate to the wrapped executor."""
        return self.executor.needs_user_input(output)

    def parse_confirm_request(self, output: str) -> Optional[dict]:
        """Delegate to the wrapped executor."""
        return self.executor.parse_confirm_request(output)

    async def execute(self, task_id: str, description: str,
                      feedback_md: Optional[str] = None,
                      model: Optional[str] = None,
                      session_id: str = None,
                      allowed_tools: str = None) -> Tuple[str, Optional[str], str, Optional[int]]:
        """
        Execute a task with exponential backoff retry on failure.
        Returns (output, error, command, exit_code).
        """
        last_error = None
        last_cmd = None

        for attempt in range(self.config.max_retries):
            output, error, cmd, exit_code = await self.executor.execute(
                task_id, description, feedback_md,
                model=model, session_id=session_id,
                allowed_tools=allowed_tools,
            )
            last_cmd = cmd

            if exit_code == 0 or exit_code is None:
                return output, error, cmd, exit_code

            if attempt >= self.config.max_retries - 1:
                return output, error, cmd, exit_code

            delay = min(self.config.base_delay * (2 ** attempt), self.config.max_delay)
            delay += random.uniform(-self.config.jitter, self.config.jitter)
            await asyncio.sleep(delay)

        return output, last_error, last_cmd, -1
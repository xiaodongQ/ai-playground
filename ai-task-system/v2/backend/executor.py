import os
from .base_executor import BaseExecutor
from .cli_executor import CLIExecutor
from .sdk_executor import SDKExecutor


class Executor:
    """执行器路由：根据配置选择 CLI 或 SDK 引擎"""

    def __init__(self, config: dict = None):
        config = config or {}
        engine = os.environ.get("EXECUTOR_ENGINE", config.get("engine", "cli"))

        if engine == "sdk":
            self._impl: BaseExecutor = SDKExecutor(
                cli_path=config.get("claw_path", "claw")
            )
        else:
            self._impl: BaseExecutor = CLIExecutor(
                cli_command=config.get("claw_command", "claw"),
                default_timeout=config.get("timeout", 600),
            )

    @property
    def name(self) -> str:
        return self._impl.name

    async def execute(self, task_id: str, model: str, description: str,
                      feedback_md=None, timeout=None):
        return await self._impl.execute(task_id, model, description, feedback_md, timeout)

    async def cancel(self, task_id: str) -> bool:
        return await self._impl.cancel(task_id)

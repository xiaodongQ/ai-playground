import logging
from typing import Tuple, Optional, Dict, Any
from .base_executor import BaseExecutor

logger = logging.getLogger(__name__)


class SDKExecutor(BaseExecutor):
    """CodeBuddy 官方 Python SDK 执行器"""

    name = "sdk"

    def __init__(self, cli_path: str = "claw"):
        self.cli_path = cli_path
        self._sessions: Dict[str, Any] = {}
        self._interrupt_flags: Dict[str, bool] = {}
        self._client = None

    @property
    def client(self):
        """延迟导入，SDK 未安装时 CLI 回退"""
        if self._client is None:
            try:
                from codebuddy_agent_sdk import CodeBuddy
                self._client = CodeBuddy(cli_path=self.cli_path)
            except ImportError:
                logger.warning(
                    "codebuddy_agent_sdk not installed, SDKExecutor will not be usable. "
                    "Install with: pip install codebuddy-agent-sdk"
                )
                return None
        return self._client

    async def execute(
        self,
        task_id: str,
        model: str,
        description: str,
        feedback_md: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[str, Optional[str]]:
        prompt = description
        if feedback_md:
            prompt = (
                f"{feedback_md}\n\n"
                f"---\n"
                f"请继续根据上述反馈执行任务。\n\n"
                f"任务：{description}"
            )

        self._interrupt_flags[task_id] = False
        output_parts = []

        sdk_client = self.client
        if sdk_client is None:
            return "", "codebuddy_agent_sdk not installed"

        try:
            # SDK 原生 async generator
            async for message in sdk_client.query(
                prompt=prompt,
                session_id=task_id,
                timeout=timeout or 600,
            ):
                if self._interrupt_flags.get(task_id):
                    return "\n".join(output_parts), "Interrupted by user"

                if hasattr(message, 'content') and message.content:
                    for block in message.content:
                        if hasattr(block, 'text') and block.text:
                            output_parts.append(block.text)

                if hasattr(message, 'is_error') and message.is_error:
                    err_msg = getattr(message, 'error', 'Unknown SDK error')
                    return "\n".join(output_parts), f"SDK error: {err_msg}"

            return "\n".join(output_parts), None

        except Exception as e:
            logger.error(f"SDKExecutor[{task_id}] error: {e}")
            return "\n".join(output_parts), str(e)

    async def cancel(self, task_id: str) -> bool:
        self._interrupt_flags[task_id] = True
        return True

"""FastAPI executor interface: wraps CLIExecutor/RetryExecutor for HTTP API usage."""

from typing import Optional, Tuple

from backend.cli_executor import CLIExecutor
from backend.retry import RetryExecutor, RetryConfig
from backend.config import get_logger

logger = get_logger(__name__)


class Executor:
    """
    Unified executor supporting Claude Code and CodeBuddy CLI.
    Wraps CLIExecutor with RetryExecutor for HTTP/async usage.
    """

    def __init__(self, cli: str = "claude"):
        self.cli = cli
        self._cli = CLIExecutor(cli=cli)
        self._retry = RetryExecutor(self._cli, RetryConfig())

    @property
    def allowed_tools(self) -> Optional[str]:
        return self._cli.allowed_tools

    @property
    def timeout(self) -> int:
        return self._cli.timeout

    def needs_user_input(self, output: str) -> bool:
        """Check if output needs human confirmation."""
        return self._cli.needs_user_input(output)

    def parse_confirm_request(self, output: str) -> Optional[dict]:
        """Parse JSON confirm request from output."""
        return self._cli.parse_confirm_request(output)

    async def execute(
        self,
        task_id: str,
        description: str,
        feedback_md: Optional[str] = None,
        model: Optional[str] = None,
        session_id: str = None,
        allowed_tools: str = None,
    ) -> Tuple[str, Optional[str], str, Optional[int]]:
        """
        Execute task with optional retry.
        Returns (output, error, command_string, exit_code).
        """
        output, error, cmd, exit_code = await self._retry.execute(
            task_id, description, feedback_md,
            model=model, session_id=session_id,
            allowed_tools=allowed_tools or self.allowed_tools,
        )
        return output, error, cmd, exit_code

    async def continue_execute(
        self,
        session_id: str,
        user_input: str,
        model: str = None,
    ) -> Tuple[str, Optional[str], str, Optional[int]]:
        """Continue an existing session with user input."""
        return await self._cli.continue_session(
            session_id, user_input, model=model,
        )

    def kill(self):
        """Kill the current subprocess."""
        self._cli.kill()
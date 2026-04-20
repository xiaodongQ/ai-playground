"""CLI executor with streaming output and process management."""

import asyncio
import json
import re
import signal
from typing import Optional, Tuple, List, Callable, Awaitable

from backend.config import load_config, get_logger

logger = get_logger(__name__)


class CLIExecutor:
    """Executes CLI commands (Claude Code / CodeBuddy) with streaming and process management."""

    def __init__(self, cli: str = "claude"):
        self.cli = cli
        config = load_config()
        executor_cfg = config.get('executor', {})
        self.timeout = executor_cfg.get('timeout', 1800)
        self.allowed_tools = executor_cfg.get('allowed_tools', None)
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._session_id: Optional[str] = None

    def build_command(self, task_id: str, description: str,
                      model: str = None, session_id: str = None,
                      allowed_tools: str = None) -> List[str]:
        """Build CLI command list to avoid shell injection."""
        if self.cli == "codebuddy":
            cmd = ["codebuddy", "-p"]
            if model:
                cmd.extend(["-m", model])
            cmd.append(description)
            return cmd
        else:
            cmd = ["claude", "--print", "--verbose"]
            if allowed_tools or self.allowed_tools:
                cmd.extend(["--allowedTools", allowed_tools or self.allowed_tools])
            if model:
                cmd.extend(["--model", model])
            if session_id:
                cmd.extend(["--session-id", session_id])
            cmd.append(description)
            return cmd

    def build_continue_command(self, session_id: str, user_input: str,
                               model: str = None) -> List[str]:
        """Build a continue-session command."""
        cmd = ["claude", "-c"]
        if model:
            cmd.extend(["--model", model])
        if session_id:
            cmd.extend(["--session-id", session_id])
        cmd.append(user_input)
        return cmd

    def _cmd_to_str(self, cmd: List[str]) -> str:
        """Convert command list to string for logging."""
        return " ".join(cmd)

    def needs_user_input(self, output: str) -> bool:
        """Detect if output contains interactive prompts that need user confirmation."""
        if not output:
            return False
        signals = [
            '?', '[Y/n]', '[是/否]', '[y/n]', '[Yes/No]',
            '是否要', '要不要', '是否需要', '请确认',
            '不确定', '需要更多信息', '请告诉我', '请选择',
            'Press Enter', '按 Enter', '输入选择',
            'Continue?', 'Proceed?', 'Confirm',
        ]
        return any(signal in output for signal in signals)

    def parse_confirm_request(self, output: str) -> Optional[dict]:
        """
        Parse JSON confirm request from output.
        Looks for {...} pattern containing confirm_type field.
        """
        if not output:
            return None
        # Find JSON block: look for { ... } with confirm_type
        pattern = r'\{[^{}]*"confirm_type"[^{}]*\}'
        match = re.search(pattern, output, re.DOTALL)
        if not match:
            # Try a more lenient approach for nested JSON
            # Find first { and try to match brace pairs
            start = output.find('{')
            if start == -1:
                return None
            depth = 0
            end = start
            for i, ch in enumerate(output[start:], start):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            json_str = output[start:end]
            try:
                data = json.loads(json_str)
                if "confirm_type" in data:
                    return data
            except json.JSONDecodeError:
                pass
        else:
            try:
                data = json.loads(match.group())
                if "confirm_type" in data:
                    return data
            except json.JSONDecodeError:
                pass
        return None

    async def execute(
        self,
        task_id: str,
        description: str,
        feedback_md: Optional[str] = None,
        model: Optional[str] = None,
        session_id: str = None,
        allowed_tools: str = None,
        output_callback: Optional[Callable[[str], Awaitable]] = None,
    ) -> Tuple[str, Optional[str], str, Optional[int]]:
        """
        Execute CLI command with optional streaming output.
        output_callback: async function that receives each output chunk.
        Returns (full_output, error, command_string, exit_code).
        """
        cmd = self.build_command(task_id, description, model, session_id, allowed_tools)
        cmd_str = self._cmd_to_str(cmd)
        self._session_id = session_id

        full_output = ""
        full_error = ""
        exit_code: Optional[int] = None

        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )

            async def read_stream(stream: asyncio.StreamReader,
                                  is_stderr: bool = False):
                nonlocal full_output, full_error
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='replace')
                    if is_stderr:
                        full_error += decoded
                    else:
                        full_output += decoded
                    if output_callback:
                        await output_callback(decoded)

            # Start reading both streams concurrently
            stdout_task = asyncio.create_task(
                read_stream(self._proc.stdout, is_stderr=False))
            stderr_task = asyncio.create_task(
                read_stream(self._proc.stderr, is_stderr=True))

            try:
                exit_code = await asyncio.wait_for(
                    self._proc.wait(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{task_id}] Execution timeout ({self.timeout}s), killing process")
                self._proc.kill()
                await self._proc.wait()
                exit_code = -1
                full_error = f"Execution timeout after {self.timeout}s"

            # Wait for stream readers to finish
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

        except Exception as e:
            logger.error(f"[{task_id}] Execution error: {e}")
            return full_output, str(e), cmd_str, -1

        return full_output, full_error if exit_code != 0 else None, cmd_str, exit_code

    async def continue_session(
        self,
        session_id: str,
        user_input: str,
        model: str = None,
        output_callback: Optional[Callable[[str], Awaitable]] = None,
    ) -> Tuple[str, Optional[str], str, Optional[int]]:
        """Continue an existing CLI session with user input."""
        cmd = self.build_continue_command(session_id, user_input, model)
        cmd_str = self._cmd_to_str(cmd)

        full_output = ""
        full_error = ""

        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def read_stream(stream, is_stderr=False):
                nonlocal full_output, full_error
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='replace')
                    if is_stderr:
                        full_error += decoded
                    else:
                        full_output += decoded
                    if output_callback:
                        await output_callback(decoded)

            stdout_task = asyncio.create_task(read_stream(self._proc.stdout))
            stderr_task = asyncio.create_task(read_stream(self._proc.stderr))

            exit_code = await asyncio.wait_for(self._proc.wait(), timeout=self.timeout)
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

        except Exception as e:
            logger.error(f"[{session_id}] Continue session error: {e}")
            return full_output, str(e), cmd_str, -1

        return full_output, full_error if exit_code != 0 else None, cmd_str, exit_code

    def kill(self):
        """Send SIGKILL to the running subprocess."""
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
                logger.info(f"Killed subprocess pid={self._proc.pid}")
            except Exception as e:
                logger.warning(f"Failed to kill subprocess: {e}")

    @property
    def is_running(self) -> bool:
        """Check if the subprocess is still running."""
        return self._proc is not None and self._proc.returncode is None
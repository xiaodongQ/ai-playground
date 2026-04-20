import asyncio
import uuid
from typing import Optional, Tuple, List

from backend.config import load_config


class Executor:
    """统一执行器，支持 Claude Code 和 CodeBuddy CLI"""

    def __init__(self, cli: str = "claude"):
        """
        Args:
            cli: "claude" 或 "codebuddy"
        """
        self.cli = cli
        config = load_config()
        self.timeout = config.get('executor', {}).get('timeout', 1800)
        self.allowed_tools = config.get('executor', {}).get('allowed_tools', None)

    def needs_user_input(self, output: str) -> bool:
        """检测输出是否包含需要用户确认的信号"""
        if not output:
            return False
        signals = [
            '?', '[Y/n]', '[是/否]', '[y/n]', '[Yes/No]',
            '是否要', '要不要', '是否需要', '请确认',
            '不确定', '需要更多信息', '请告诉我', '请选择',
            'Press Enter', '按 Enter', '输入选择'
        ]
        return any(signal in output for signal in signals)

    def build_command(self, task_id: str, description: str, model: str = None,
                      session_id: str = None, allowed_tools: str = None) -> List[str]:
        """构建 CLI 命令列表，避免 shell 注入"""
        if self.cli == "codebuddy":
            cmd = ["codebuddy", "-p"]
            if model:
                cmd.extend(["-m", model])
            cmd.append(description)
            return cmd
        else:
            # Claude Code
            cmd = ["claude", "--print", "--verbose"]
            if allowed_tools:
                cmd.extend(["--allowedTools", allowed_tools])
            if model:
                cmd.extend(["--model", model])
            if session_id:
                cmd.extend(["--session-id", session_id])
            cmd.append(description)
            return cmd

    def build_continue_command(self, session_id: str, user_input: str,
                               model: str = None) -> List[str]:
        """构建继续会话命令"""
        cmd = ["claude", "-c"]
        if model:
            cmd.extend(["--model", model])
        if session_id:
            cmd.extend(["--session-id", session_id])
        cmd.append(user_input)
        return cmd

    def _cmd_to_str(self, cmd: List[str]) -> str:
        """命令列表转字符串（用于日志显示）"""
        return " ".join(cmd)

    async def execute(self, task_id: str, description: str,
                      feedback_md: Optional[str] = None,
                      model: Optional[str] = None,
                      session_id: str = None,
                      allowed_tools: str = None) -> Tuple[str, Optional[str], str, Optional[int]]:
        """执行任务，返回 (output, error, command, exit_code)"""
        cmd = self.build_command(task_id, description, model, session_id, allowed_tools)
        cmd_str = self._cmd_to_str(cmd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return "", "Execution timeout", cmd_str, -1

            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

            if proc.returncode == 0:
                return stdout_str, None, cmd_str, proc.returncode
            else:
                return stdout_str, stderr_str, cmd_str, proc.returncode

        except Exception as e:
            return "", str(e), cmd_str, -1

    async def continue_execute(self, session_id: str, user_input: str,
                                model: str = None) -> Tuple[str, Optional[str], str, Optional[int]]:
        """使用 claude -c 继续会话"""
        cmd = self.build_continue_command(session_id, user_input, model)
        cmd_str = self._cmd_to_str(cmd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""

            if proc.returncode == 0:
                return stdout_str, None, cmd_str, proc.returncode
            else:
                return stdout_str, stderr_str, cmd_str, proc.returncode
        except Exception as e:
            return "", str(e), cmd_str, -1
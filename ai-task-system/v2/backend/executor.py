import subprocess
import asyncio
import uuid
from typing import Optional, Tuple

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
                      session_id: str = None, allowed_tools: str = None) -> str:
        """构建 CLI 命令"""
        model_arg = f" --model {model}" if model else ""
        session_arg = f" --session-id {session_id}" if session_id else ""
        tools_arg = f" --allowedTools {allowed_tools}" if allowed_tools else ""

        if self.cli == "codebuddy":
            # CodeBuddy: -p 表示 headless/print 模式，-m 指定模型
            model_arg = f" -m {model}" if model else ""
            return f'codebuddy -p{model_arg} "{description}"'
        else:
            # Claude Code: --print 后面先跟任务描述，再跟其他参数
            tools_arg = f" --allowedTools {allowed_tools}" if allowed_tools else ""
            model_arg = f" --model {model}" if model else ""
            return f'claude --print "{description}" --verbose{tools_arg}{model_arg}'

    def _run_sync(self, cmd: str) -> Tuple[str, Optional[str], str, Optional[int]]:
        """同步执行命令（在线程中运行）"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0:
                return result.stdout, None, cmd, result.returncode
            else:
                return result.stdout, result.stderr, cmd, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Execution timeout", cmd, -1
        except Exception as e:
            return "", str(e), cmd, -1

    async def execute(self, task_id: str, description: str,
                      feedback_md: Optional[str] = None,
                      model: Optional[str] = None,
                      session_id: str = None,
                      allowed_tools: str = None) -> Tuple[str, Optional[str], str, Optional[int]]:
        """执行任务，返回 (output, error, command, exit_code)"""
        cmd = self.build_command(task_id, description, model, session_id, allowed_tools)

        # feedback 通过任务描述传递，不作为 CLI 参数
        # 在线程池中执行，避免阻塞事件循环
        return await asyncio.to_thread(self._run_sync, cmd)

    async def continue_execute(self, session_id: str, user_input: str,
                                model: str = None) -> Tuple[str, Optional[str], str, Optional[int]]:
        """使用 claude -c 继续会话（不需要 --print，因为 -c 本身就是非交互模式）"""
        model_arg = f" --model {model}" if model else ""
        cmd = f'claude -c --session-id {session_id}{model_arg} "{user_input}"'
        return await asyncio.to_thread(self._run_sync, cmd)
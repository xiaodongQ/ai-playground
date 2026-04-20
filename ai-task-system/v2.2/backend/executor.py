import subprocess
import asyncio
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
        self.timeout = load_config().get('executor', {}).get('timeout', 1800)

    def build_command(self, task_id: str, description: str, model: str = None) -> str:
        """构建 CLI 命令"""
        model_arg = f" --model {model}" if model else ""

        if self.cli == "codebuddy":
            # CodeBuddy: -p 表示 headless/print 模式，-m 指定模型
            model_arg = f" -m {model}" if model else ""
            return f'codebuddy -p{model_arg} "{description}"'
        else:
            # Claude Code: --print 无头模式，--verbose 输出详细信息
            return f'claude --print --verbose{model_arg} "{description}"'

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
                      model: Optional[str] = None) -> Tuple[str, Optional[str], str, Optional[int]]:
        """执行任务，返回 (output, error, command, exit_code)"""
        cmd = self.build_command(task_id, description, model)

        if feedback_md:
            cmd = f'{cmd} --feedback "{feedback_md}"'

        # 在线程池中执行，避免阻塞事件循环
        return await asyncio.to_thread(self._run_sync, cmd)
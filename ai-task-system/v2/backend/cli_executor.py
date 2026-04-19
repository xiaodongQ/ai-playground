import asyncio
import os
from typing import Optional, Tuple, Dict
from .base_executor import BaseExecutor

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


class CLIExecutor(BaseExecutor):
    """CLI 执行器，通过 subprocess 调用 claw 命令"""

    name = "cli"

    def __init__(self, cli_command: str = "claw", default_timeout: int = 600):
        self.cli_command = cli_command
        self.default_timeout = default_timeout
        self._processes: Dict[str, asyncio.subprocess.Process] = {}

    def build_command(self, task_id: str, model: str, description: str) -> list:
        """构建命令列表，避免 shell 注入"""
        return [
            self.cli_command,
            "--task-id", task_id,
            "--model", model,
            "--description", description
        ]

    async def execute(
        self,
        task_id: str,
        model: str,
        description: str,
        feedback_md: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[str, Optional[str]]:
        """异步执行命令，使用 asyncio.create_subprocess_exec 避免 shell 注入"""
        timeout = timeout or self.default_timeout

        cmd = self.build_command(task_id, model, description)
        if feedback_md:
            cmd.extend(["--feedback", feedback_md])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self._processes[task_id] = process

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                stdout = stdout_bytes.decode('utf-8', errors='replace')
                stderr = stderr_bytes.decode('utf-8', errors='replace')

                self._processes.pop(task_id, None)

                if process.returncode == 0:
                    return stdout, None
                else:
                    return stdout, stderr
            except asyncio.TimeoutExpired:
                process.kill()
                await process.wait()
                self._processes.pop(task_id, None)
                return "", "Execution timeout"
        except FileNotFoundError:
            return "", f"Command not found: {self.cli_command}"
        except Exception as e:
            self._processes.pop(task_id, None)
            return "", str(e)

    async def cancel(self, task_id: str) -> bool:
        """通过 task_id 查找并 kill 进程"""
        process = self._processes.pop(task_id, None)
        if process:
            try:
                process.kill()
                await process.wait()
                return True
            except Exception:
                return False

        # 尝试通过 psutil 查找进程
        if psutil is not None:
            try:
                for proc in psutil.process_iter(['pid', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline') or []
                        if any(task_id in arg for arg in cmdline):
                            proc.kill()
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass

        return False

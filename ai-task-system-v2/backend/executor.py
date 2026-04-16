import subprocess
from typing import Optional, Tuple

class Executor:
    def __init__(self, cli_command: str = "claw"):
        self.cli_command = cli_command

    def build_command(self, task_id: str, model: str, description: str) -> str:
        return f'{self.cli_command} --task-id {task_id} --model {model} "{description}"'

    async def execute(self, task_id: str, model: str, description: str,
                      feedback_md: Optional[str] = None) -> Tuple[str, Optional[str]]:
        cmd = self.build_command(task_id, model, description)

        # 如果有反馈，追加到命令
        if feedback_md:
            cmd = f'{cmd} --feedback "{feedback_md}"'

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600  # 10 分钟超时
            )
            if result.returncode == 0:
                return result.stdout, None
            else:
                return result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return "", "Execution timeout"
        except Exception as e:
            return "", str(e)
"""
AI Task System V3 - Executor Module
CodeBuddy 无头模式执行器
"""
import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from .models import Task, TaskStatus


class Executor:
    """CodeBuddy 执行器"""

    def __init__(self, workspace_root: str = "./workspace"):
        self.workspace_root = Path(workspace_root)

    def create_workspace(self, task: Task) -> Path:
        """创建任务沙箱目录"""
        # 目录命名: task_{日期}_{UUID前8位}_{标题简名}
        date_str = task.created_at.strftime("%Y%m%d%H%M")
        title_short = task.title[:20].replace(" ", "_").replace("/", "_")
        dir_name = f"task_{date_str}_{task.id}_{title_short}"
        
        workspace_path = self.workspace_root / dir_name
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Git 仓库
        subprocess.run(["git", "init"], cwd=workspace_path, capture_output=True)
        
        return workspace_path

    def write_task_file(self, workspace_path: Path, task: Task):
        """写入 TASK.md 需求文件"""
        task_file = workspace_path / "TASK.md"
        content = f"""# 任务需求
## 基础信息
- 任务ID：{task.id}
- 任务标题：{task.title}
- 创建时间：{task.created_at.isoformat()}
- 最大迭代次数：{task.max_iterations}
- 达标评分阈值：{task.pass_threshold}
- 绝对超时时间：{task.absolute_timeout}秒
- 无输出超时时间：{task.no_output_timeout}秒

## 执行配置
- 允许工具：{task.allowed_tools}
- 权限模式：{task.permission_mode}
- 输出格式：{task.output_format}

## 任务详细描述
{task.description}
"""
        task_file.write_text(content, encoding="utf-8")

    async def execute(self, task: Task) -> dict:
        """执行 CodeBuddy 无头模式"""
        # 创建沙箱
        workspace_path = self.create_workspace(task)
        self.write_task_file(workspace_path, task)
        
        task.workspace_path = str(workspace_path)
        
        # 构建 CodeBuddy CLI 命令
        cmd = self._build_command(task)
        
        # 准备环境变量
        env = os.environ.copy()
        env["CLAUDE_HOME"] = str(workspace_path)
        
        logs = []
        result = ""
        error = None
        
        try:
            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(workspace_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 异步读取输出
            stdout, stderr = await process.communicate()
            
            result = stdout.decode('utf-8', errors='replace') if stdout else ""
            error = stderr.decode('utf-8', errors='replace') if stderr else None
            
            if error:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Stderr: {error[:200]}")
            
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Execution completed")
            
        except Exception as e:
            error = str(e)
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {error}")
        
        # 保存执行日志
        self._save_run_log(workspace_path, task, logs, result)
        
        # 自动 Git 提交
        self._git_commit(workspace_path, task)
        
        return {
            "success": error is None,
            "result": result,
            "error": error,
            "logs": logs,
            "workspace_path": str(workspace_path)
        }

    def _build_command(self, task: Task) -> list:
        """构建 CodeBuddy CLI 命令"""
        cmd = [
            "codebuddy",
            "-p",  # 无头模式
            "-y",  # 跳过授权确认
            task.description,
            "--allowedTools", task.allowed_tools,
            "--permission-mode", task.permission_mode,
            "--output-format", task.output_format,
            "--verbose"
        ]
        
        if task.session_id:
            cmd = ["codebuddy", "-p", "-y", "--resume", task.session_id,
                   f"基于上一轮的反馈优化执行，这是第{task.current_iteration}次迭代",
                   "--allowedTools", task.allowed_tools,
                   "--permission-mode", task.permission_mode,
                   "--verbose"]
        
        return cmd

    def _save_run_log(self, workspace_path: Path, task: Task, logs: list, result: str):
        """保存 RUN_LOG.md"""
        log_file = workspace_path / "RUN_LOG.md"
        content = f"""# 任务执行全量日志
## 时间节点
- 任务创建时间：{task.created_at.isoformat()}
- 执行开始时间：{datetime.now().isoformat()}
- 任务ID：{task.id}

## 执行日志
"""
        for log in logs:
            content += f"- {log}\n"
        
        content += f"""
## 执行输出
```\n{result}\n```
"""
        log_file.write_text(content, encoding="utf-8")

    def _git_commit(self, workspace_path: Path, task: Task):
        """Git 自动提交"""
        try:
            subprocess.run(["git", "add", "."], cwd=workspace_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"task execution completed: {task.id}"],
                cwd=workspace_path,
                capture_output=True
            )
        except Exception:
            pass

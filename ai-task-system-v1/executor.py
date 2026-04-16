"""
AI Task Pickup System - Task Executor
Executes tasks using Claude Code CLI
"""
import subprocess
import os
import asyncio
from datetime import datetime
from typing import Optional, Tuple

from models import Task, TaskType


class TaskExecutor:
    def __init__(self, workspace_dir: str = "./workspace"):
        self.workspace_dir = workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)
    
    def _get_task_prompt(self, task: Task) -> str:
        """Generate prompt based on task type"""
        if task.type == TaskType.CODE_DEV:
            return f"""Task: {task.title}

Description:
{task.description}

Please implement this code task. Create necessary files, write clean code, and ensure it works correctly.

When done, summarize:
1. What you implemented
2. Files created/modified
3. How to run/test
"""
        else:  # DOC_SUMMARY
            return f"""Task: {task.title}

Description:
{task.description}

Please analyze this document/content and provide a comprehensive summary including:
1. Key points
2. Main insights
3. Action items or conclusions

Be thorough and well-structured in your analysis.
"""
    
    async def execute_task(self, task: Task) -> Tuple[str, str]:
        """
        Execute a task using Claude Code CLI
        Returns: (solution_plan, result)
        """
        prompt = self._get_task_prompt(task)
        
        # Create task-specific workspace
        task_dir = os.path.join(self.workspace_dir, f"task_{task.id}")
        os.makedirs(task_dir, exist_ok=True)
        
        # Initialize git repo if not exists
        git_dir = os.path.join(task_dir, ".git")
        if not os.path.exists(git_dir):
            subprocess.run(["git", "init"], cwd=task_dir, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "ai@tasksystem.local"],
                cwd=task_dir, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "AI Task System"],
                cwd=task_dir, capture_output=True
            )
        
        # Write task description
        task_file = os.path.join(task_dir, "TASK.md")
        with open(task_file, "w") as f:
            f.write(f"# Task: {task.title}\n\n")
            f.write(f"## Type: {task.type}\n\n")
            f.write(f"## Description\n{task.description}\n\n")
            f.write(f"## Created: {task.created_at}\n")
        
        # Build Claude Code command
        # Use --print for non-interactive mode
        cmd = [
            "claude",
            "--print",
            prompt
        ]
        
        # Set environment
        env = os.environ.copy()
        # Ensure Claude uses the task directory
        env["CLAUDE_HOME"] = task_dir
        
        logs = []
        solution_plan = ""
        result = ""
        
        try:
            # Run Claude Code
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting execution...")
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Task type: {task.type}")
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Workspace: {task_dir}")
            
            # For now, use a simpler approach - run claude with the prompt
            # In production, you'd want proper error handling and streaming
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=task_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                result = stdout.decode('utf-8', errors='replace')
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Execution completed")
            else:
                result = "(No output produced)"
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: No output produced")
            
            if stderr:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Stderr: {stderr.decode('utf-8', errors='replace')[:500]}")
            
            # Generate solution plan (simplified)
            solution_plan = f"""1. Analyzed task: {task.title}
2. Type: {task.type}
3. Workspace: {task_dir}
4. Implementation completed
"""
            
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Done!")
            
        except FileNotFoundError:
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: Claude CLI not found")
            logs.append("Please ensure Claude Code CLI is installed: npm install -g @anthropic-ai/claude-code")
            result = "Error: Claude CLI not installed"
            solution_plan = "Failed to generate plan due to CLI error"
            
        except Exception as e:
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {str(e)}")
            result = f"Error: {str(e)}"
            solution_plan = "Failed to generate plan due to execution error"
        
        return solution_plan, result
    
    async def execute_task_sync(self, task: Task) -> Tuple[str, str, list]:
        """
        Execute task synchronously with logging
        Returns: (solution_plan, result, logs)
        """
        logs = []
        
        try:
            prompt = self._get_task_prompt(task)
            
            # Create workspace
            task_dir = os.path.join(self.workspace_dir, f"task_{task.id}")
            os.makedirs(task_dir, exist_ok=True)
            
            # Initialize git
            git_dir = os.path.join(task_dir, ".git")
            if not os.path.exists(git_dir):
                subprocess.run(["git", "init"], cwd=task_dir, capture_output=True)
                subprocess.run(
                    ["git", "config", "user.email", "ai@tasksystem.local"],
                    cwd=task_dir, capture_output=True
                )
                subprocess.run(
                    ["git", "config", "user.name", "AI Task System"],
                    cwd=task_dir, capture_output=True
                )
            
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting task execution...")
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Task: {task.title}")
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Type: {task.type}")
            
            # Write task file
            with open(os.path.join(task_dir, "TASK.md"), "w") as f:
                f.write(f"# Task: {task.title}\n\n## Description\n{task.description}\n")
            
            # Run Claude Code
            cmd = [
                "claude",
                "--print",
                prompt
            ]
            
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Executing Claude Code...")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=task_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            result = stdout.decode('utf-8', errors='replace') if stdout else "(No output)"
            
            if stderr:
                stderr_text = stderr.decode('utf-8', errors='replace')[:200]
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Stderr: {stderr_text}")
            
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Execution completed")
            
            solution_plan = f"""1. Analyzed task requirements
2. Created workspace at {task_dir}
3. Executed implementation
4. Result length: {len(result)} chars
"""
            
        except FileNotFoundError:
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Claude CLI not found")
            result = "Error: Claude CLI not installed"
            solution_plan = "Failed"
        except Exception as e:
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
            result = f"Error: {str(e)}"
            solution_plan = "Failed"
        
        return solution_plan, result, logs

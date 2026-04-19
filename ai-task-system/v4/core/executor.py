"""V4 统一执行器：进程管理 + 超时控制 + 无输出超时检测"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from datetime import datetime
from typing import Callable

from .base import (
    AgentAdapter,
    ExecutionConfig,
    ExecutionResult,
    Task,
    TaskStatus,
)


class NoOutputWatcher:
    """
    无输出超时检测器

    定期检查子进程的 stdout/stderr 是否有新输出，
    如果超过 no_output_timeout 秒无任何输出，则判定为超时。
    """

    def __init__(self, process: subprocess.Popen, timeout: int, callback: Callable[[], None] | None = None):
        self.process = process
        self.timeout = timeout
        self.callback = callback
        self._stop_event = threading.Event()
        self._last_output_time: float = time.time()
        self._thread: threading.Thread | None = None
        self._triggered = False

    def _read_available(self):
        """尝试读取可用的输出，不阻塞"""
        try:
            # 非阻塞读取 stderr（通常更快到达）
            if self.process.stderr:
                import select
                if select.select([self.process.stderr], [], [], 0)[0]:
                    chunk = self.process.stderr.read(4096)
                    if chunk:
                        self._last_output_time = time.time()

            # 非阻塞读取 stdout
            if self.process.stdout:
                import select
                if select.select([self.process.stdout], [], [], 0)[0]:
                    chunk = self.process.stdout.read(4096)
                    if chunk:
                        self._last_output_time = time.time()
        except Exception:
            pass

    def _watch(self):
        check_interval = 5  # 每 5 秒检查一次
        while not self._stop_event.is_set():
            self._read_available()

            elapsed_since_output = time.time() - self._last_output_time
            if elapsed_since_output >= self.timeout and not self._triggered:
                self._triggered = True
                if self.callback:
                    self.callback()
                # 杀死进程
                try:
                    self.process.terminate()
                    time.sleep(0.5)
                    if self.process.poll() is None:
                        self.process.kill()
                except Exception:
                    pass
                return

            # 如果进程已结束，不再等待
            if self.process.poll() is not None:
                return

            self._stop_event.wait(timeout=check_interval)

    def start(self):
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def was_triggered(self) -> bool:
        return self._triggered


class SubprocessExecutor:
    """
    统一执行器

    使用 subprocess 执行命令，支持：
    - 总超时控制
    - 无输出超时检测
    - stdout/stderr 捕获
    - 环境变量注入
    - 回调通知
    """

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def execute(self, config: ExecutionConfig, adapter: AgentAdapter, task_id: str | None = None) -> Task:
        """
        执行任务

        Args:
            config: 执行配置
            adapter: 使用的适配器
            task_id: 可选的任务 ID

        Returns:
            Task 对象
        """
        if task_id is None:
            task_id = config.session_id or f"task-{int(time.time())}"

        task = Task(task_id=task_id, config=config)
        self._tasks[task_id] = task

        return self._do_execute(task, adapter)

    def _do_execute(self, task: Task, adapter: AgentAdapter) -> Task:
        config = task.config
        assert config is not None

        cmd = adapter.build_command(config)
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        # 合并环境变量
        env = os.environ.copy()
        if config.env_vars:
            env.update(config.env_vars)
        # 注入 API key 等（从环境变量继承）
        if "ANTHROPIC_API_KEY" in os.environ:
            env.setdefault("ANTHROPIC_API_KEY", os.environ["ANTHROPIC_API_KEY"])
        if "OPENAI_API_KEY" in os.environ:
            env.setdefault("OPENAI_API_KEY", os.environ["OPENAI_API_KEY"])

        process: subprocess.Popen | None = None
        no_output_watcher: NoOutputWatcher | None = None
        timeout_triggered = False
        no_output_triggered = False

        def on_no_output_timeout():
            nonlocal no_output_triggered
            no_output_triggered = True

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=config.working_dir or None,
                env=env,
                text=True,
                bufsize=1,
            )

            # 启动无输出超时检测器
            if config.no_output_timeout and config.no_output_timeout > 0:
                no_output_watcher = NoOutputWatcher(
                    process,
                    timeout=config.no_output_timeout,
                    callback=on_no_output_timeout,
                )
                no_output_watcher.start()

            # 等待进程结束（带总超时）
            timeout_sec = config.timeout if config.timeout else 600

            try:
                stdout, stderr = process.communicate(timeout=timeout_sec)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                process.terminate()
                time.sleep(0.5)
                if process.poll() is None:
                    process.kill()
                stdout, stderr = process.communicate()
                timeout_triggered = True
                return_code = -1

        except FileNotFoundError as e:
            stderr = f"Command not found: {e}"
            stdout = ""
            return_code = 127
        except Exception as e:
            stderr = str(e)
            stdout = ""
            return_code = 1
        finally:
            if no_output_watcher:
                no_output_watcher.stop()
            # 清理 adapter 创建的临时文件（如 Codex JSON Schema 文件）
            for fp in config._temp_files:
                try:
                    os.unlink(fp)
                except OSError:
                    pass
            config._temp_files.clear()

        task.finished_at = datetime.now()
        duration = (task.finished_at - task.started_at).total_seconds()

        # 判断状态
        if no_output_triggered:
            status = TaskStatus.NO_OUTPUT_TIMEOUT
            stderr = f"[NO_OUTPUT_TIMEOUT] No output for {config.no_output_timeout}s\n" + (stderr or "")
        elif timeout_triggered:
            status = TaskStatus.TIMEOUT
            stderr = f"[TIMEOUT] Exceeded {config.timeout}s\n" + (stderr or "")
        elif return_code == 0:
            status = TaskStatus.SUCCESS
        else:
            status = TaskStatus.FAILED

        # 从输出中提取 session_id（尝试）
        session_id = self._extract_session_id(stdout, stderr, config)

        task.result = ExecutionResult(
            status=status,
            stdout=stdout or "",
            stderr=stderr or "",
            return_code=return_code,
            duration_seconds=duration,
            session_id=session_id,
            metadata={
                "cmd": " ".join(cmd),
                "timeout_triggered": timeout_triggered,
                "no_output_triggered": no_output_triggered,
            },
        )
        task.status = status

        return task

    def _extract_session_id(self, stdout: str, stderr: str, config: ExecutionConfig) -> str | None:
        """从输出中尝试提取 session ID"""
        combined = stdout + "\n" + stderr

        # Claude Code 格式：Session ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        match = re.search(r"Session ID:\s*([a-zA-Z0-9_-]+)", combined)
        if match:
            return match.group(1)

        # 其他格式的 session id
        match = re.search(r"session[_-]?id[:\s]+([a-zA-Z0-9_-]+)", combined, re.IGNORECASE)
        if match:
            return match.group(1)

        return config.session_id

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        """取消运行中的任务（发送 SIGTERM）"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        # 注意：实际取消需要通过进程 PID，这里简化处理
        task.status = TaskStatus.CANCELLED
        task.finished_at = datetime.now()
        return True

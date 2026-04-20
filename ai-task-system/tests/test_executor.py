"""
Tests for SubprocessExecutor - process execution and task management.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

import pytest
from ai_task_system.v4.core.base import (
    AgentType,
    ExecutionConfig,
    OutputFormat,
    PermissionMode,
)
from ai_task_system.v4.core.executor import SubprocessExecutor
from ai_task_system.v4.adapters.claude_adapter import ClaudeCodeAdapter


class TestSubprocessExecutor:
    def test_instantiation(self):
        executor = SubprocessExecutor()
        assert executor is not None

    def test_list_tasks_empty(self):
        executor = SubprocessExecutor()
        tasks = executor.list_tasks()
        assert tasks == []

    def test_get_task_nonexistent(self):
        executor = SubprocessExecutor()
        task = executor.get_task("nonexistent")
        assert task is None

    def test_execute_simple_command(self):
        """Execute a simple echo command via shell (not Claude Code agent)."""
        executor = SubprocessExecutor()
        # Use shell command directly - but Executor.execute() wraps with Claude Code
        # So we just verify the task is registered and can be retrieved
        config = ExecutionConfig(
            prompt="echo test123",
            timeout=10,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
        )
        adapter = ClaudeCodeAdapter()
        task = executor.execute(config, adapter)
        assert task is not None
        assert task.task_id is not None
        # Verify task can be retrieved
        retrieved = executor.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    def test_cancel_task(self):
        executor = SubprocessExecutor()
        config = ExecutionConfig(
            prompt="echo test",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
        )
        adapter = ClaudeCodeAdapter()
        task = executor.execute(config, adapter)
        task_id = task.task_id
        # Verify task is tracked
        assert executor.get_task(task_id) is not None
        # Cancel the task
        cancelled = executor.cancel_task(task_id)
        assert cancelled is True


class TestNoOutputWatcher:
    def test_instantiation_requires_process(self):
        """NoOutputWatcher requires a Popen process object."""
        from ai_task_system.v4.core.executor import NoOutputWatcher
        # Create a real subprocess
        proc = subprocess.Popen(
            ["echo", "hello"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        watcher = NoOutputWatcher(process=proc, timeout=60)
        assert watcher.timeout == 60
        proc.terminate()
        proc.wait()

    def test_watcher_triggers_on_no_output(self):
        """NoOutputWatcher terminates a process that produces no output within timeout."""
        from ai_task_system.v4.core.executor import NoOutputWatcher
        import time

        # Use Python to run a long sleep (20s) before producing output
        # with a short no_output_timeout (3s) so it triggers before output
        # Note: check_interval is 5s, so watcher fires ~5s after start (not 3s exactly)
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(20); print('late output')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        watcher = NoOutputWatcher(process=proc, timeout=3)
        watcher.start()

        # Wait for the watcher to detect no output and kill the process
        # check_interval is 5s, so we need > 5s to guarantee the first check fires
        time.sleep(8)

        # The process should have been terminated by the watcher
        poll_result = proc.poll()
        assert poll_result is not None, "Process should have been terminated by watcher"
        assert watcher.was_triggered, "Watcher should have been triggered"
        # cleanup
        if poll_result is None:
            proc.kill()
            proc.wait()

    def test_watcher_does_not_trigger_with_output(self):
        """NoOutputWatcher does NOT trigger if output arrives within timeout."""
        from ai_task_system.v4.core.executor import NoOutputWatcher
        import time

        # Use a process that outputs quickly (within the no_output_timeout)
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; print('early'); time.sleep(1); print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        watcher = NoOutputWatcher(process=proc, timeout=5)
        watcher.start()

        # Wait for process to finish naturally (should be < 5s)
        time.sleep(4)

        poll_result = proc.poll()
        # Process should have finished on its own (not killed by watcher)
        if poll_result is None:
            # Still running - kill it for cleanup
            proc.kill()
            proc.wait()

        # Watcher should NOT have been triggered since output arrived
        assert not watcher.was_triggered, "Watcher should NOT have been triggered with early output"

    def test_watcher_stop_prevents_trigger(self):
        """Stopping the watcher before timeout prevents process termination."""
        from ai_task_system.v4.core.executor import NoOutputWatcher
        import time

        # Long sleep (20s) but we stop the watcher before it triggers
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(20); print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        watcher = NoOutputWatcher(process=proc, timeout=4)
        watcher.start()

        # Stop the watcher before the 4s timeout triggers
        time.sleep(2)
        watcher.stop()

        # Process should still be alive (we stopped the watcher)
        poll_result = proc.poll()
        assert poll_result is None, "Process should still be running after watcher.stop()"

        # Cleanup - kill the process
        proc.kill()
        proc.wait()

    def test_watcher_timeout_during_execution_sets_flag(self):
        """Verify watcher.was_triggered is True after a no-output timeout."""
        from ai_task_system.v4.core.executor import NoOutputWatcher
        import time

        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(20)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        watcher = NoOutputWatcher(process=proc, timeout=2)
        watcher.start()

        # Poll until triggered
        for _ in range(10):
            time.sleep(0.5)
            if watcher.was_triggered:
                break

        assert watcher.was_triggered, "Watcher should have been triggered"
        proc.kill()
        proc.wait()

    def test_callback_called_on_no_output_timeout(self):
        """Callback is invoked when no-output timeout occurs."""
        from ai_task_system.v4.core.executor import NoOutputWatcher
        import time

        callback_called = {"flag": False}

        def my_callback():
            callback_called["flag"] = True

        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(20)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        watcher = NoOutputWatcher(process=proc, timeout=2, callback=my_callback)
        watcher.start()

        # Wait for callback to be called (check_interval=5s, so give it 7s)
        time.sleep(7)

        assert callback_called["flag"], "Callback should have been called"
        proc.kill()
        proc.wait()

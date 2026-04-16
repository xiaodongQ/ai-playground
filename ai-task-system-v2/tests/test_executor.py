import pytest
from backend.executor import Executor

def test_executor_initialization():
    executor = Executor()
    assert executor.cli_command == "claw"

def test_build_command():
    executor = Executor()
    cmd = executor.build_command(
        task_id="test-123",
        model="claude-opus-4-6",
        description="测试任务"
    )
    assert "claw" in cmd
    assert "test-123" in cmd
    assert "claude-opus-4-6" in cmd
    assert "测试任务" in cmd
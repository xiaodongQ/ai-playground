import pytest
from backend.executor import Executor

def test_executor_initialization():
    executor = Executor()
    assert executor.cli == "claude"

def test_codebuddy_initialization():
    executor = Executor(cli="codebuddy")
    assert executor.cli == "codebuddy"

def test_build_command_claude():
    executor = Executor(cli="claude")
    cmd = executor.build_command(
        task_id="test-123",
        description="测试任务"
    )
    assert "claude --print --verbose" in cmd
    assert "测试任务" in cmd

def test_build_command_codebuddy():
    executor = Executor(cli="codebuddy")
    cmd = executor.build_command(
        task_id="test-456",
        description="CodeBuddy 任务"
    )
    assert "codebuddy -p" in cmd
    assert "CodeBuddy 任务" in cmd
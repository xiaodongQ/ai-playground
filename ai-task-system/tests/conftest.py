"""
pytest fixtures for AI Task System V4 tests.
"""
from __future__ import annotations

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Ensure ai_task_system is importable from ai-task-system/
_PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKG_ROOT.parent))

from ai_task_system.v4.core.base import (
    AdapterRegistry,
    AgentType,
    ExecutionConfig,
    OutputFormat,
    PermissionMode,
)
from ai_task_system.v4.core.command_builder import CommandBuilder
from ai_task_system.v4.core.router import TaskRouter
from ai_task_system.v4.core.session_store import SessionStore
from ai_task_system.v4.core.retry import RetryConfig
from ai_task_system.v4.adapters.claude_adapter import ClaudeCodeAdapter
from ai_task_system.v4.adapters.codex_adapter import CodexAdapter
from ai_task_system.v4.adapters.codebuddy_adapter import CodeBuddyAdapter


@pytest.fixture
def registry():
    """Fresh AdapterRegistry with all adapters registered."""
    reg = AdapterRegistry()
    reg.register(ClaudeCodeAdapter())
    reg.register(CodexAdapter())
    reg.register(CodeBuddyAdapter())
    return reg


@pytest.fixture
def claude_adapter():
    return ClaudeCodeAdapter()


@pytest.fixture
def codex_adapter():
    return CodexAdapter()


@pytest.fixture
def codebuddy_adapter():
    return CodeBuddyAdapter()


@pytest.fixture
def cmd_builder(registry):
    builder = CommandBuilder()
    # Register adapters from registry into builder
    for adapter in registry.get_all():
        builder._adapters[adapter.agent_type] = adapter
    return builder


@pytest.fixture
def router(registry):
    return TaskRouter(registry)


@pytest.fixture
def temp_session_store(tmp_path):
    """SessionStore backed by a temporary JSON file."""
    db_path = tmp_path / "sessions.json"
    return SessionStore(db_path=str(db_path))


@pytest.fixture
def sample_config():
    """Minimal ExecutionConfig for testing."""
    return ExecutionConfig(
        prompt="say hello",
        timeout=30,
        permission_mode=PermissionMode.PLAN,
        output_format=OutputFormat.TEXT,
    )


@pytest.fixture
def sample_config_bypass():
    """ExecutionConfig with skip-permissions (AUTO mode for root safety)."""
    return ExecutionConfig(
        prompt="say hello",
        timeout=30,
        permission_mode=PermissionMode.AUTO,
        output_format=OutputFormat.TEXT,
    )


@pytest.fixture
def temp_task_dir(tmp_path):
    """Temporary workspace directory."""
    d = tmp_path / "workspace"
    d.mkdir()
    return d

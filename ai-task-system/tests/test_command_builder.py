"""
Tests for CommandBuilder - cross-agent command parameter mapping.
"""
from __future__ import annotations

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
from ai_task_system.v4.core.command_builder import CommandBuilder


class TestCommandBuilder:
    def test_build_for_claude(self, cmd_builder, sample_config):
        # sample_config defaults to CLAUDE_CODE agent_type
        cmd, adapter = cmd_builder.build(sample_config)
        assert cmd[0] == "claude"
        assert "--print" in cmd

    def test_build_for_codex(self, cmd_builder, tmp_path):
        # Codex adapter registered but not available - still builds command
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            agent_type=AgentType.CODEX,
        )
        cmd, adapter = cmd_builder.build(config)
        assert cmd[0] == "codex"
        assert "exec" in cmd

    def test_build_for_codebuddy(self, cmd_builder, tmp_path):
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            agent_type=AgentType.CODEBUDDY,
        )
        cmd, adapter = cmd_builder.build(config)
        assert cmd[0] == "codebuddy"

    def test_build_unknown_agent(self, cmd_builder, tmp_path):
        # Create a config with unknown agent type
        config = ExecutionConfig(
            prompt="hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            agent_type="unknown_agent",
        )
        with pytest.raises(ValueError, match="Unknown agent type"):
            cmd_builder.build(config)

    def test_unified_output_format(self, cmd_builder):
        """Output format should map to the right flag per agent."""
        config_json = ExecutionConfig(
            prompt="hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.JSON,
            agent_type=AgentType.CLAUDE_CODE,
        )
        cmd, _ = cmd_builder.build(config_json)
        assert "--output-format" in cmd
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "json"

    def test_permission_flags_claude_bypass(self, cmd_builder):
        """BYPASS mode for Claude maps to --dangerously-skip-permissions."""
        config = ExecutionConfig(
            prompt="hello",
            timeout=30,
            permission_mode=PermissionMode.BYPASS,
            output_format=OutputFormat.TEXT,
            agent_type=AgentType.CLAUDE_CODE,
        )
        cmd, _ = cmd_builder.build(config)
        assert "--dangerously-skip-permissions" in cmd

    def test_permission_flags_claude_plan(self, cmd_builder):
        """PLAN mode for Claude should not include skip-permissions."""
        config = ExecutionConfig(
            prompt="hello",
            timeout=30,
            permission_mode=PermissionMode.PLAN,
            output_format=OutputFormat.TEXT,
            agent_type=AgentType.CLAUDE_CODE,
        )
        cmd, _ = cmd_builder.build(config)
        assert "--dangerously-skip-permissions" not in cmd

    def test_build_returns_adapter(self, cmd_builder, sample_config):
        cmd, adapter = cmd_builder.build(sample_config)
        assert adapter is not None
        assert adapter.agent_type == AgentType.CLAUDE_CODE

"""
Tests for V4 Agent Adapters.
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
    TaskStatus,
)
from ai_task_system.v4.adapters.claude_adapter import ClaudeCodeAdapter
from ai_task_system.v4.adapters.codex_adapter import CodexAdapter
from ai_task_system.v4.adapters.codebuddy_adapter import CodeBuddyAdapter


class TestClaudeCodeAdapter:
    def test_agent_type(self):
        assert ClaudeCodeAdapter().agent_type == AgentType.CLAUDE_CODE

    def test_is_available(self):
        adapter = ClaudeCodeAdapter()
        available, reason = adapter.is_available()
        # Claude Code may or may not be installed
        assert isinstance(available, bool)
        assert reason is None or isinstance(reason, str)

    def test_build_command_basic(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
        )
        cmd = adapter.build_command(config)
        assert isinstance(cmd, list)
        assert cmd[0] == "claude"
        assert "--print" in cmd

    def test_build_command_json_format(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.JSON,
        )
        cmd = adapter.build_command(config)
        assert "--output-format" in cmd
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "json"

    def test_build_command_skip_permissions(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.BYPASS,
            output_format=OutputFormat.TEXT,
        )
        cmd = adapter.build_command(config)
        assert "--dangerously-skip-permissions" in cmd

    def test_build_command_bare_mode(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            bare=True,
        )
        cmd = adapter.build_command(config)
        assert "--bare" in cmd

    def test_build_command_with_model(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            model="claude-sonnet-4-20250514",
        )
        cmd = adapter.build_command(config)
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-sonnet-4-20250514"

    def test_build_command_with_session(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            session_id="sess_test_001",
            resume=True,
        )
        cmd = adapter.build_command(config)
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "sess_test_001"

    def test_build_command_max_budget(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            max_budget=0.01,
        )
        cmd = adapter.build_command(config)
        idx = cmd.index("--max-budget-usd")
        assert cmd[idx + 1] == "0.01"

    def test_build_command_allowed_tools(self):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            allowed_tools=["Read", "Write", "Bash"],
        )
        cmd = adapter.build_command(config)
        idx = cmd.index("--allowed-tools")
        assert cmd[idx + 1] == "Read,Write,Bash"

    def test_build_command_add_dirs(self, tmp_path):
        adapter = ClaudeCodeAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
            add_dirs=[str(tmp_path)],
        )
        cmd = adapter.build_command(config)
        idx = cmd.index("--add-dir")
        assert cmd[idx + 1] == str(tmp_path)

    def test_capabilities(self):
        adapter = ClaudeCodeAdapter()
        caps = adapter.get_capabilities()
        assert isinstance(caps, list)
        # Should have multiple capabilities
        assert len(caps) >= 5

    def test_validate_config_valid(self, sample_config):
        adapter = ClaudeCodeAdapter()
        valid, err = adapter.validate_config(sample_config)
        assert valid is True
        assert err is None


class TestCodexAdapter:
    def test_agent_type(self):
        assert CodexAdapter().agent_type == AgentType.CODEX

    def test_is_available(self):
        adapter = CodexAdapter()
        available, reason = adapter.is_available()
        # codex not in PATH in this env
        assert available is False
        assert "codex" in reason.lower()

    def test_build_command_basic(self):
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
        )
        cmd = adapter.build_command(config)
        assert isinstance(cmd, list)
        assert cmd[0] == "codex"
        assert "exec" in cmd

    def test_build_command_json(self):
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.JSON,
        )
        cmd = adapter.build_command(config)
        # Codex exec is present for JSON format requests
        assert "exec" in cmd

    def test_build_command_sandbox(self):
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
        )
        cmd = adapter.build_command(config)
        assert "--sandbox" in cmd

    def test_build_command_json_schema(self):
        """Codex --output-schema flag is added when json_schema is set."""
        adapter = CodexAdapter()
        schema = '{"type":"object","properties":{"name":{"type":"string"}}}'
        config = ExecutionConfig(
            prompt="Return a person object",
            timeout=60,
            permission_mode=PermissionMode.AUTO,
            json_schema=schema,
        )
        cmd = adapter.build_command(config)
        assert "--output-schema" in cmd
        schema_idx = cmd.index("--output-schema")
        schema_file = cmd[schema_idx + 1]
        # 文件存在且为 .json 文件
        import os
        assert os.path.exists(schema_file), f"Schema file {schema_file} should exist"
        assert schema_file.endswith(".json")
        # config._temp_files 已注册
        assert schema_file in config._temp_files, "Schema file should be in _temp_files for cleanup"
        # 验证 schema 内容
        with open(schema_file) as f:
            import json
            loaded = json.load(f)
            assert loaded["type"] == "object"

    def test_build_command_json_schema_not_set(self):
        """No --output-schema when json_schema is None."""
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            json_schema=None,
        )
        cmd = adapter.build_command(config)
        assert "--output-schema" not in cmd
        assert len(config._temp_files) == 0

    def test_parse_output_valid_json_with_schema(self):
        """parse_output succeeds with valid JSON when schema is set."""
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="Return a person",
            json_schema='{"type":"object"}',
        )
        result = adapter.parse_output('{"name": "Alice"}', config)
        assert result.status == TaskStatus.SUCCESS
        assert result.return_code == 0

    def test_parse_output_invalid_json_with_schema(self):
        """parse_output fails with invalid JSON when schema is set."""
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="Return a person",
            json_schema='{"type":"object"}',
        )
        result = adapter.parse_output("not valid json", config)
        assert result.status == TaskStatus.FAILED
        assert result.return_code == 1
        assert "Invalid JSON output:" in result.stderr

    def test_parse_output_valid_json_invalid_schema(self):
        """parse_output fails when JSON is valid but doesn't match schema."""
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="Return a person",
            json_schema='{"type":"object","properties":{"name":{"type":"string"}}}',
        )
        # Output is valid JSON but is a string, not an object as required
        result = adapter.parse_output('"Alice"', config)
        assert result.status == TaskStatus.FAILED
        assert result.return_code == 1
        assert "Schema validation failed" in result.stderr

    def test_parse_output_valid_json_partial_schema(self):
        """parse_output fails when JSON matches type but missing required properties."""
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="Return a person",
            json_schema='{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"integer"}},"required":["name","age"]}',
        )
        # Output is an object but missing required 'age' field
        result = adapter.parse_output('{"name": "Alice"}', config)
        assert result.status == TaskStatus.FAILED
        assert result.return_code == 1
        assert "Schema validation failed" in result.stderr
        assert "'age' is a required property" in result.stderr

    def test_parse_output_invalid_schema_format(self):
        """parse_output fails when the schema itself is malformed JSON."""
        adapter = CodexAdapter()
        config = ExecutionConfig(
            prompt="Return a person",
            json_schema='not a valid json schema {',
        )
        result = adapter.parse_output('{"name": "Alice"}', config)
        assert result.status == TaskStatus.FAILED
        assert result.return_code == 1
        assert "Invalid JSON Schema" in result.stderr

    def test_parse_output_valid_json_without_schema(self):
        """parse_output succeeds regardless of JSON validity when no schema set."""
        adapter = CodexAdapter()
        config = ExecutionConfig(prompt="Return a person", json_schema=None)
        result = adapter.parse_output("any text output", config)
        assert result.status == TaskStatus.SUCCESS


class TestCodeBuddyAdapter:
    def test_agent_type(self):
        assert CodeBuddyAdapter().agent_type == AgentType.CODEBUDDY

    def test_is_available(self):
        adapter = CodeBuddyAdapter()
        available, reason = adapter.is_available()
        assert available is False
        assert isinstance(reason, str)

    def test_build_command_basic(self):
        adapter = CodeBuddyAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.AUTO,
            output_format=OutputFormat.TEXT,
        )
        cmd = adapter.build_command(config)
        assert isinstance(cmd, list)
        assert cmd[0] == "codebuddy"

    def test_build_command_skip_permissions(self):
        adapter = CodeBuddyAdapter()
        config = ExecutionConfig(
            prompt="say hello",
            timeout=30,
            permission_mode=PermissionMode.BYPASS,
            output_format=OutputFormat.TEXT,
        )
        cmd = adapter.build_command(config)
        assert "-y" in cmd or "--yes" in cmd


class TestAdapterRegistry:
    def test_register_and_get(self, registry):
        adapter = registry.get(AgentType.CLAUDE_CODE)
        assert adapter is not None
        assert adapter.agent_type == AgentType.CLAUDE_CODE

    def test_get_all(self, registry):
        all_adapters = registry.get_all()
        assert len(all_adapters) >= 3  # Claude, Codex, CodeBuddy
        types = {a.agent_type for a in all_adapters}
        assert AgentType.CLAUDE_CODE in types

    def test_get_available(self, registry):
        available = registry.get_available()
        # At least Claude Code should be available in the test env
        types = {a.agent_type for a, err in available if err is None}
        # Claude Code may or may not be available
        assert isinstance(available, list)

    def test_auto_select_with_claude_available(self, registry):
        selected = registry.auto_select()
        # Claude should be the auto-select if available
        # If Claude is available, it should be returned
        if selected is not None:
            assert selected.agent_type == AgentType.CLAUDE_CODE

    def test_auto_select_none_available(self, registry):
        """When no adapters are registered, auto_select should return None."""
        empty_reg = type(registry)()  # fresh registry
        selected = empty_reg.auto_select()
        assert selected is None

    def test_get_unknown_agent(self, registry):
        # Non-existent agent type
        adapter = registry.get(AgentType.CODEX)
        # Codex is registered but may not be "available"
        assert adapter is not None  # Codex is registered


class TestExecutionConfig:
    def test_default_values(self):
        from ai_task_system.v4.core.base import ExecutionConfig
        config = ExecutionConfig(prompt="test")
        assert config.prompt == "test"
        assert config.timeout == 600  # default
        assert config.no_output_timeout == 120  # derived
        assert config.bare is False  # default

    def test_bare_field(self):
        from ai_task_system.v4.core.base import ExecutionConfig
        config = ExecutionConfig(prompt="test", bare=True)
        assert config.bare is True

    def test_session_id_field(self):
        from ai_task_system.v4.core.base import ExecutionConfig
        config = ExecutionConfig(prompt="test", session_id="sess_abc")
        assert config.session_id == "sess_abc"

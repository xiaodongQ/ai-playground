"""Claude Code 适配器"""
from __future__ import annotations

import shutil
from typing import Any

from ..core.base import (
    AgentAdapter,
    AgentCapability,
    AgentType,
    ExecutionConfig,
    ExecutionResult,
    OutputFormat,
    PermissionMode,
    TaskStatus,
)


class ClaudeCodeAdapter(AgentAdapter):
    """Claude Code CLI 适配器"""

    AGENT_CMD = "claude"

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CLAUDE_CODE

    def get_capabilities(self) -> list[AgentCapability]:
        return [
            # 权限控制
            AgentCapability.SKIP_PERMISSIONS,
            AgentCapability.AUTO_PERMISSIONS,
            # 输入输出
            AgentCapability.STRUCTURED_OUTPUT,
            AgentCapability.STREAM_JSON,
            AgentCapability.OUTPUT_FORMAT,
            AgentCapability.OUTPUT_FILE,
            # 会话管理
            AgentCapability.SESSION_RESUME,
            AgentCapability.EPHEMERAL_SESSION,
            AgentCapability.NO_SESSION_PERSISTENCE,
            # 工具控制
            AgentCapability.ALLOWED_TOOLS,
            AgentCapability.DENIED_TOOLS,
            # 模型控制
            AgentCapability.MODEL_SELECTION,
            AgentCapability.MAX_BUDGET,
            # 工作区
            AgentCapability.ADD_DIR,
            # MCP
            AgentCapability.MCP_CONFIG,
            # 无头模式
            AgentCapability.HEADLESS,
            # 其他
            AgentCapability.BARE_MODE,
        ]

    def is_available(self) -> tuple[bool, str | None]:
        """检查 Claude Code 是否可用"""
        if not shutil.which(self.AGENT_CMD):
            return False, f"'{self.AGENT_CMD}' not found in PATH"
        return True, None

    def validate_config(self, config: ExecutionConfig) -> tuple[bool, str | None]:
        """验证配置"""
        if not config.prompt:
            return False, "prompt is required"
        if config.output_format == OutputFormat.JSON and not config.output_format:
            pass  # OK
        return True, None

    def build_command(self, config: ExecutionConfig) -> list[str]:
        cmd = [self.AGENT_CMD]

        # 无头模式（必须）
        cmd.append("--print")

        # 权限模式
        if config.permission_mode == PermissionMode.BYPASS:
            cmd.append("--dangerously-skip-permissions")
        elif config.permission_mode == PermissionMode.AUTO:
            # AUTO 模式：claude --print 默认不需要确认
            pass
        elif config.permission_mode == PermissionMode.PLAN:
            cmd.append("--plan")

        # 工具白名单
        if config.allowed_tools:
            cmd.extend(["--allowed-tools", ",".join(config.allowed_tools)])

        # 模型选择
        if config.model:
            cmd.extend(["--model", config.model])

        # 预算控制
        if config.max_budget:
            cmd.extend([f"--max-budget-usd", str(config.max_budget)])

        # 输出格式
        if config.output_format == OutputFormat.JSON:
            cmd.extend(["--output-format", "json"])
        elif config.output_format == OutputFormat.STREAM_JSON:
            cmd.extend(["--output-format", "stream-json"])
        else:
            cmd.extend(["--output-format", "text"])

        # 结构化输出
        # --json-schema <schema>  或 --output-format json --schema ...

        # 会话管理
        if config.session_id and config.resume:
            cmd.extend(["--resume", config.session_id])
        elif config.no_session_persistence:
            cmd.append("--no-session-persistence")

        # MCP 配置
        if config.mcp_config:
            cmd.extend(["--mcp-config", config.mcp_config])

        # 工作目录
        if config.add_dirs:
            for d in config.add_dirs:
                cmd.extend(["--add-dir", d])

        # Bare 模式（跳过 CLAUDE.md discovery）
        if config.bare:
            cmd.append("--bare")

        # 额外参数
        if config.extra_args:
            cmd.extend(config.extra_args)

        # 工作目录（cd 到指定目录）
        # 注意：实际 cwd 由 executor 控制

        # prompt（最后）
        cmd.extend(["--", config.prompt])

        return cmd

    def parse_output(self, raw_output: str, config: ExecutionConfig) -> ExecutionResult:
        """解析输出"""
        return ExecutionResult(
            status=TaskStatus.SUCCESS if raw_output else TaskStatus.FAILED,
            stdout=raw_output,
            stderr="",
            return_code=0,
        )

    def get_permission_flags(self, mode: PermissionMode) -> list[str]:
        if mode == PermissionMode.BYPASS:
            return ["--dangerously-skip-permissions"]
        elif mode == PermissionMode.PLAN:
            return ["--plan"]
        return []

    def get_metadata(self) -> dict[str, Any]:
        base = super().get_metadata()
        base["cli_example"] = (
            "claude --print --dangerously-skip-permissions --allowed-tools Bash,Read "
            "--model sonnet-4-20250514 'Your task here'"
        )
        return base

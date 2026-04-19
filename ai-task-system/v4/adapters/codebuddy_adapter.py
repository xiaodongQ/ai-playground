"""CodeBuddy 适配器（基于 V3 逆向）"""
from __future__ import annotations

import shutil
from typing import Any

from ..core.base import (
    AgentAdapter,
    AgentCapability,
    AgentType,
    ExecutionConfig,
    ExecutionResult,
    PermissionMode,
    TaskStatus,
)


class CodeBuddyAdapter(AgentAdapter):
    """CodeBuddy CLI 适配器（逆向自 V3）"""

    AGENT_CMD = "codebuddy"

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CODEBUDDY

    def get_capabilities(self) -> list[AgentCapability]:
        return [
            # 权限控制
            AgentCapability.SKIP_PERMISSIONS,
            # 输入输出
            AgentCapability.OUTPUT_FORMAT,
            # 会话管理
            AgentCapability.SESSION_RESUME,
            # 工具控制
            AgentCapability.ALLOWED_TOOLS,
            # 无头模式
            AgentCapability.HEADLESS,
        ]
        # 不支持：SANDBOX_MODE, STRUCTURED_OUTPUT, MODEL_SELECTION, MAX_BUDGET 等

    def is_available(self) -> tuple[bool, str | None]:
        if not shutil.which(self.AGENT_CMD):
            return False, f"'{self.AGENT_CMD}' not found in PATH (not installed or not in PATH)"
        return True, None

    def validate_config(self, config: ExecutionConfig) -> tuple[bool, str | None]:
        if not config.prompt:
            return False, "prompt is required"
        return True, None

    def build_command(self, config: ExecutionConfig) -> list[str]:
        cmd = [self.AGENT_CMD]

        # 无头模式（-p 或 --print，V3 使用 -p）
        cmd.append("-p")

        # 跳过确认（-y）
        if config.permission_mode in (PermissionMode.BYPASS, PermissionMode.AUTO):
            cmd.append("-y")

        # 输出格式（--output-format）
        if config.output_format.value != "text":
            cmd.extend(["--output-format", config.output_format.value])

        # 工具白名单（--allowedTools，逗号分隔）
        if config.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(config.allowed_tools)])

        # 会话恢复（--resume）
        if config.session_id and config.resume:
            cmd.extend(["--resume", config.session_id])

        # 工作目录（V3 使用 cwd）
        # 注意：V3 硬编码 cwd 为 TASK.md 所在目录

        # 额外参数
        if config.extra_args:
            cmd.extend(config.extra_args)

        # prompt（最后）
        cmd.append(config.prompt)

        return cmd

    def parse_output(self, raw_output: str, config: ExecutionConfig) -> ExecutionResult:
        return ExecutionResult(
            status=TaskStatus.SUCCESS if raw_output else TaskStatus.FAILED,
            stdout=raw_output,
            stderr="",
            return_code=0,
        )

    def get_permission_flags(self, mode: PermissionMode) -> list[str]:
        if mode in (PermissionMode.BYPASS, PermissionMode.AUTO):
            return ["-y"]
        return []

    def get_metadata(self) -> dict[str, Any]:
        base = super().get_metadata()
        base["note"] = "Based on V3 reverse-engineering; not tested (CodeBuddy not installed)"
        base["cli_example"] = "codebuddy -p -y --allowedTools Bash,Read 'Your task here'"
        return base

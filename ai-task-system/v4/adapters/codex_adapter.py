"""OpenAI Codex 适配器"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any

import jsonschema

from ..core.base import (
    AgentAdapter,
    AgentCapability,
    AgentType,
    ExecutionConfig,
    ExecutionResult,
    PermissionMode,
    TaskStatus,
)


class CodexAdapter(AgentAdapter):
    """OpenAI Codex CLI 适配器（codex exec）"""

    AGENT_CMD = "codex"

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CODEX

    def get_capabilities(self) -> list[AgentCapability]:
        return [
            # 权限控制
            AgentCapability.SKIP_PERMISSIONS,
            AgentCapability.AUTO_PERMISSIONS,
            AgentCapability.SANDBOX_MODE,
            # 输入输出
            AgentCapability.STRUCTURED_OUTPUT,
            AgentCapability.OUTPUT_FILE,
            # 会话管理
            AgentCapability.EPHEMERAL_SESSION,
            # 模型控制
            AgentCapability.MODEL_SELECTION,
            # 工作区
            AgentCapability.ADD_DIR,
            AgentCapability.SANDBOX_READONLY,
            # 无头模式
            AgentCapability.HEADLESS,
        ]
        # 不支持：ALLOWED_TOOLS, SESSION_RESUME, NO_SESSION_PERSISTENCE, MCP_CONFIG, MAX_BUDGET

    def is_available(self) -> tuple[bool, str | None]:
        if not shutil.which(self.AGENT_CMD):
            return False, f"'{self.AGENT_CMD}' not found in PATH"
        return True, None

    def validate_config(self, config: ExecutionConfig) -> tuple[bool, str | None]:
        if not config.prompt:
            return False, "prompt is required"
        return True, None

    def build_command(self, config: ExecutionConfig) -> list[str]:
        cmd = [self.AGENT_CMD, "exec"]

        # 权限模式
        if config.permission_mode in (PermissionMode.BYPASS, PermissionMode.AUTO):
            cmd.append("--full-auto")
        elif config.permission_mode == PermissionMode.PLAN:
            cmd.extend(["--plan", "true"])

        # 沙箱模式
        sandbox = config.sandbox_mode or "danger-full-access"
        if sandbox in ("workspace-write", "read-only", "danger-full-access", "workspace-read-network-write"):
            cmd.extend(["--sandbox", sandbox])

        # 临时会话（ephemeral）
        if config.no_session_persistence or config.resume:
            cmd.append("--ephemeral")

        # 模型选择
        if config.model:
            cmd.extend(["-m", config.model])

        # 工作目录
        if config.working_dir:
            cmd.extend(["-C", config.working_dir])
        if config.add_dirs:
            for d in config.add_dirs:
                cmd.extend(["--add-dir", d])

        # 输出文件
        if config.output_file:
            cmd.extend(["-o", config.output_file])

        # 结构化输出（--output-schema）
        # Codex --output-schema 需要 JSON Schema 文件路径
        # 临时文件路径记录在 config._temp_files，由调用方负责清理
        schema_file_path = None
        if config.json_schema:
            try:
                schema_fd, schema_file_path = tempfile.mkstemp(suffix=".json", prefix="codex_schema_")
                with os.fdopen(schema_fd, "w") as f:
                    f.write(config.json_schema)
                cmd.extend(["--output-schema", schema_file_path])
                config._temp_files.append(schema_file_path)
            except Exception:
                # 写入失败，忽略 schema（不阻断命令构建）
                schema_file_path = None

        # 额外参数
        if config.extra_args:
            cmd.extend(config.extra_args)

        # prompt（最后，以 -- 分隔）
        cmd.append("--")
        cmd.append(config.prompt)

        return cmd

    def parse_output(self, raw_output: str, config: ExecutionConfig) -> ExecutionResult:
        status = TaskStatus.SUCCESS
        error_message = None

        # 如果配置了 json_schema，验证输出是否为有效 JSON 并符合 Schema 结构
        if config.json_schema:
            try:
                parsed = json.loads(raw_output)
            except json.JSONDecodeError as e:
                status = TaskStatus.FAILED
                error_message = f"Invalid JSON output: {e}"
            else:
                # 严格 Schema 结构校验
                try:
                    schema_obj = json.loads(config.json_schema)
                    jsonschema.validate(instance=parsed, schema=schema_obj)
                except jsonschema.ValidationError as e:
                    status = TaskStatus.FAILED
                    error_message = f"Schema validation failed: {e.message}"
                except jsonschema.SchemaError as e:
                    status = TaskStatus.FAILED
                    error_message = f"Invalid JSON Schema: {e.message}"
                except json.JSONDecodeError as e:
                    status = TaskStatus.FAILED
                    error_message = f"Invalid JSON Schema (not parseable): {e}"

        return ExecutionResult(
            status=status,
            stdout=raw_output,
            stderr=error_message or "",
            return_code=0 if status == TaskStatus.SUCCESS else 1,
        )

    def get_metadata(self) -> dict[str, Any]:
        base = super().get_metadata()
        base["cli_example"] = (
            "codex exec --full-auto --sandbox danger-full-access -C /path/to/project -- 'Your task here'"
        )
        base["sandbox_modes"] = [
            "workspace-write",
            "workspace-read-network-write",
            "read-only",
            "danger-full-access",
        ]
        return base

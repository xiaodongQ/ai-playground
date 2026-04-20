"""V4 命令构建器：跨 Agent 参数映射"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import AgentAdapter, AgentCapability, AgentType, ExecutionConfig, OutputFormat, PermissionMode


class CommandBuilder:
    """
    统一命令构建器

    负责将 ExecutionConfig 转换为各 Agent 的命令行参数。
    具体转换逻辑委托给各 AgentAdapter。
    """

    def __init__(self):
        self._adapters: dict[AgentType, AgentAdapter] = {}

    def register(self, adapter: AgentAdapter):
        self._adapters[adapter.agent_type] = adapter

    def build(self, config: ExecutionConfig) -> tuple[list[str], AgentAdapter]:
        """
        构建命令，返回 (命令列表, 使用的适配器)

        Raises:
            ValueError: 没有可用适配器或配置不合法
        """
        agent_type = config.agent_type
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError:
                raise ValueError(f"Unknown agent type: {agent_type}")

        adapter = self._adapters.get(agent_type)
        if not adapter:
            raise ValueError(f"No adapter registered for {agent_type.value}")

        ok, err = adapter.validate_config(config)
        if not ok:
            raise ValueError(f"Invalid config for {agent_type.value}: {err}")

        cmd = adapter.build_command(config)
        return cmd, adapter

    def build_for_auto(self, config: ExecutionConfig) -> tuple[list[str], AgentAdapter]:
        """
        自动选择适配器并构建命令
        """
        if isinstance(config.agent_type, str):
            try:
                config.agent_type = AgentType(config.agent_type)
            except ValueError:
                config.agent_type = AgentType.CLAUDE_CODE

        if config.agent_type == AgentType.UNKNOWN:
            # 遍历找可用的
            for at in [AgentType.CLAUDE_CODE, AgentType.CODEX, AgentType.CODEBUDDY]:
                adapter = self._adapters.get(at)
                if adapter:
                    ok, _ = adapter.is_available()
                    if ok:
                        config.agent_type = at
                        adapter = adapter
                        break
            else:
                raise ValueError("No available agent found")

        adapter = self._adapters.get(config.agent_type)
        if not adapter:
            raise ValueError(f"No adapter for {config.agent_type.value}")

        ok, err = adapter.validate_config(config)
        if not ok:
            raise ValueError(f"Invalid config: {err}")

        return adapter.build_command(config), adapter

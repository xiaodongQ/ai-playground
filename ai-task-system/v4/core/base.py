"""V4 核心抽象层：数据模型 + AgentAdapter 接口定义"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable


class AgentType(Enum):
    """支持的 Agent 类型"""
    CLAUDE_CODE = "claude"
    CODEX = "codex"
    CODEBUDDY = "codebuddy"
    UNKNOWN = "unknown"


class AgentCapability(Enum):
    """Agent 能力枚举"""
    # 权限控制
    SKIP_PERMISSIONS = auto()      # 跳过确认
    AUTO_PERMISSIONS = auto()      # 自动权限
    SANDBOX_MODE = auto()          # 沙箱模式

    # 输入输出
    STRUCTURED_OUTPUT = auto()    # 结构化输出（JSON Schema）
    STREAM_JSON = auto()          # 流式 JSON 输出
    OUTPUT_FORMAT = auto()         # 输出格式控制
    OUTPUT_FILE = auto()           # 输出到文件

    # 会话管理
    SESSION_RESUME = auto()       # 会话恢复
    EPHEMERAL_SESSION = auto()     # 临时会话
    NO_SESSION_PERSISTENCE = auto() # 无会话持久化

    # 工具控制
    ALLOWED_TOOLS = auto()        # 工具白名单
    DENIED_TOOLS = auto()         # 工具黑名单

    # 模型控制
    MODEL_SELECTION = auto()      # 模型选择
    MAX_BUDGET = auto()            # 预算上限

    # 工作区
    ADD_DIR = auto()              # 添加工作目录
    SANDBOX_READONLY = auto()     # 只读沙箱

    # MCP 支持
    MCP_CONFIG = auto()           # MCP 配置

    # 无头模式
    HEADLESS = auto()             # 无头/静默模式

    # 其他
    BARE_MODE = auto()             # 跳过 CLAUDE.md discovery


class PermissionMode(Enum):
    """权限模式"""
    PLAN = "plan"       # 先查看计划
    AUTO = "auto"       # 自动执行（跳过确认）
    BYPASS = "bypass"   # 强制跳过（危险）
    INTERACTIVE = "interactive"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NO_OUTPUT_TIMEOUT = "no_output_timeout"
    CANCELLED = "cancelled"
    AGENT_ERROR = "agent_error"     # Agent 自身错误（非进程退出）
    GIVE_UP = "give_up"             # 重试耗尽后放弃


class OutputFormat(Enum):
    """输出格式"""
    TEXT = "text"
    JSON = "json"
    STREAM_JSON = "stream-json"


@dataclass
class ExecutionConfig:
    """统一的执行配置"""
    prompt: str
    # Agent 选择
    agent_type: AgentType | str = AgentType.CLAUDE_CODE

    # 权限控制
    permission_mode: PermissionMode = PermissionMode.AUTO

    # 超时控制（秒）
    timeout: int | None = 600
    no_output_timeout: int | None = 120  # 无输出超时

    # 输出控制
    output_format: OutputFormat = OutputFormat.TEXT
    output_file: str | None = None  # 输出到文件
    json_schema: str | None = None  # JSON Schema（用于结构化输出，Codex --output-schema）

    # 会话控制
    session_id: str | None = None
    resume: bool = False
    no_session_persistence: bool = False

    # 资源控制
    model: str | None = None
    max_budget: float | None = None

    # 工具控制
    allowed_tools: list[str] | None = None
    denied_tools: list[str] | None = None

    # 工作区
    working_dir: str | None = None
    add_dirs: list[str] | None = None

    # 沙箱（Codex 专用）
    sandbox_mode: str | None = None  # workspace-write | read-only | danger-full-access | workspace-read-network-write

    # MCP
    mcp_config: str | None = None

    # Bare 模式（仅 Claude Code）
    bare: bool = False  # 跳过 CLAUDE.md discovery，适合自动化场景

    # 其他
    extra_args: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    # 内部字段（不暴露在 to_dict）
    _temp_files: list[str] = field(default_factory=list)  # 临时文件路径（adapter 创建，executor 清理）

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "agent_type": self.agent_type.value if isinstance(self.agent_type, AgentType) else self.agent_type,
            "permission_mode": self.permission_mode.value,
            "timeout": self.timeout,
            "no_output_timeout": self.no_output_timeout,
            "output_format": self.output_format.value,
            "session_id": self.session_id,
            "model": self.model,
            "max_budget": self.max_budget,
            "allowed_tools": self.allowed_tools,
            "working_dir": self.working_dir,
            "bare": self.bare,
            "json_schema": self.json_schema,
        }


@dataclass
class ExecutionResult:
    """执行结果"""
    status: TaskStatus
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    duration_seconds: float = 0.0
    session_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        return self.status == TaskStatus.SUCCESS


@dataclass
class Task:
    """任务模型"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: ExecutionConfig | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: ExecutionResult | None = None

    def duration(self) -> float:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return 0.0


class AgentAdapter(ABC):
    """
    Agent 适配器抽象基类

    各 Agent CLI 工具（Claude Code / Codex / CodeBuddy）有不同的命令行接口，
    适配器层将它们统一抽象为一致的接口。
    """

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """返回支持的 Agent 类型"""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[AgentCapability]:
        """
        返回该 Agent 支持的能力列表
        """
        ...

    @abstractmethod
    def is_available(self) -> tuple[bool, str | None]:
        """
        检查 Agent 是否可用
        返回 (是否可用, 错误信息)
        """
        ...

    @abstractmethod
    def validate_config(self, config: ExecutionConfig) -> tuple[bool, str | None]:
        """
        验证执行配置是否合法
        返回 (是否合法, 错误信息)
        """
        ...

    @abstractmethod
    def build_command(self, config: ExecutionConfig) -> list[str]:
        """
        将 ExecutionConfig 构建为命令行参数列表
        """
        ...

    @abstractmethod
    def parse_output(self, raw_output: str, config: ExecutionConfig) -> ExecutionResult:
        """
        解析原始输出为标准 ExecutionResult
        """
        ...

    def get_permission_flags(self, mode: PermissionMode) -> list[str]:
        """
        获取权限相关的命令行标志
        默认实现，子类可覆盖
        """
        return []

    def supports(self, capability: AgentCapability) -> bool:
        """检查是否支持指定能力"""
        return capability in self.get_capabilities()

    def get_metadata(self) -> dict[str, Any]:
        """返回适配器的元信息"""
        return {
            "agent_type": self.agent_type.value,
            "capabilities": [c.name for c in self.get_capabilities()],
        }


class AdapterRegistry:
    """
    适配器注册表：管理与实例化所有 Agent 适配器
    """

    def __init__(self):
        self._adapters: dict[AgentType, AgentAdapter] = {}

    def register(self, adapter: AgentAdapter):
        self._adapters[adapter.agent_type] = adapter

    def get(self, agent_type: AgentType) -> AgentAdapter | None:
        return self._adapters.get(agent_type)

    def get_all(self) -> list[AgentAdapter]:
        return list(self._adapters.values())

    def get_available(self) -> list[tuple[AgentAdapter, str | None]]:
        """返回所有可用的适配器及其状态"""
        available = []
        for adapter in self._adapters.values():
            ok, msg = adapter.is_available()
            available.append((adapter, msg if not ok else None))
        return available

    def auto_select(self) -> AgentAdapter | None:
        """
        自动选择最佳可用 Agent
        优先级：Claude Code > Codex > CodeBuddy
        """
        priority = [AgentType.CLAUDE_CODE, AgentType.CODEX, AgentType.CODEBUDDY]
        for at in priority:
            adapter = self.get(at)
            if adapter:
                ok, _ = adapter.is_available()
                if ok:
                    return adapter
        return None

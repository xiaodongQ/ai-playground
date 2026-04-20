"""V4 任务路由策略：基于任务类型 + Agent 能力 + 基准数据自动选择最佳 Agent"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from .base import (
    AdapterRegistry,
    AgentAdapter,
    AgentCapability,
    AgentType,
    ExecutionConfig,
)

if TYPE_CHECKING:
    from .benchmark_scores import BenchmarkScoreDB


class TaskType(Enum):
    """任务类型枚举"""
    # 核心任务类型
    CODING = auto()           # 写代码 / 实现功能
    DEBUGGING = auto()        # 调试 / 修复 Bug
    REFACTORING = auto()      # 重构 / 优化代码
    ARCHITECTURE = auto()     # 架构设计 / 系统设计
    CODE_REVIEW = auto()     # 代码审查

    # 分析与研究
    RESEARCH = auto()         # 技术研究 / 调研
    LEARNING = auto()         # 学习 / 概念解释

    # 写作与文档
    WRITING = auto()          # 写作 / 博客 / 文档
    TRANSLATION = auto()      # 翻译

    # DevOps / 基础设施
    DEVOPS = auto()           # CI/CD / 部署 / 容器
    INFRA = auto()            # 基础设施 / 云配置

    # 数据与脚本
    DATA_SCRIPT = auto()      # 数据处理 / 脚本
    QUERY = auto()            # 数据库查询 / API 调用

    # 其他
    GENERAL = auto()          # 通用任务（无法分类）
    UNKNOWN = auto()          # 未知


@dataclass
class RoutingRule:
    """单条路由规则"""
    task_type: TaskType
    # 关键词（命中任一即匹配，大小写不敏感）
    keywords: list[str] = field(default_factory=list)
    # 优先 Agent 列表（按优先级排序）
    preferred_agents: list[AgentType] = field(default_factory=list)
    # 推荐的 permission_mode
    recommended_permission: str | None = None
    # 推荐的 timeout（秒）
    recommended_timeout: int | None = None
    # 备注
    note: str | None = None


# 默认路由规则表
DEFAULT_ROUTING_RULES: list[RoutingRule] = [
    # ===== 核心开发任务 =====
    RoutingRule(
        task_type=TaskType.CODING,
        keywords=[
            "写代码", "写个", "实现", "功能", "写一个", "编程",
            "代码", "写函数", "写类", "写模块",
            "build", "implement", "write code", "create function",
            "create class", "write script", "coding",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX, AgentType.CODEBUDDY],
        recommended_timeout=600,
        note="代码开发任务，优先 Claude Code（完整工具链）",
    ),
    RoutingRule(
        task_type=TaskType.DEBUGGING,
        keywords=[
            "调试", "debug", "bug", "修复", "fix", "报错",
            "exception", "error", "crash", "panic",
            "segmentation fault", "空指针", "null pointer",
            "找不到", "not found", "失败", "failed",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX, AgentType.CODEBUDDY],
        recommended_timeout=300,
        note="调试任务，优先 Claude Code（Read/grep 工具强大）",
    ),
    RoutingRule(
        task_type=TaskType.REFACTORING,
        keywords=[
            "重构", "refactor", "优化代码", "代码优化",
            "清理代码", "clean code", "improve",
            "简化", "simplify", "consolidate",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX],
        recommended_timeout=600,
        note="重构任务，Claude Code 的 Read 工具便于理解上下文",
    ),
    RoutingRule(
        task_type=TaskType.ARCHITECTURE,
        keywords=[
            "架构", "architecture", "设计系统", "system design",
            "微服务", "microservice", "分布式", "distributed",
            "高并发", "scalability", "技术选型",
            "框架选型", "方案设计", "架构设计",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE],
        recommended_timeout=900,
        note="架构设计需要强上下文理解，Claude Code 最佳",
    ),
    RoutingRule(
        task_type=TaskType.CODE_REVIEW,
        keywords=[
            "review", "代码审查", "审阅", "检查代码",
            "pull request", "pr review", "diff",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX],
        recommended_timeout=300,
        note="代码审查，Claude Code 支持 Read 遍历文件",
    ),

    # ===== 分析与研究 =====
    RoutingRule(
        task_type=TaskType.RESEARCH,
        keywords=[
            "研究", "调研", "research", "investigate",
            "分析", "analyze", "对比", "compare",
            "评估", "evaluate", "benchmark",
            "搜索", "search", "find best",
            "技术调研", "技术选型", "选哪个",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX],
        recommended_timeout=600,
        note="技术研究，Claude Code 可结合 Web/MCP 工具",
    ),
    RoutingRule(
        task_type=TaskType.LEARNING,
        keywords=[
            "学习", "教程", "tutorial", "learn", "理解",
            "概念", "concept", "explain", "入门",
            "怎么学", "什么是", "how to learn",
            "教学", "解释", "explain",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE],
        recommended_timeout=600,
        note="学习任务，Claude Code 可以生成示例代码辅助理解",
    ),

    # ===== 写作与文档 =====
    RoutingRule(
        task_type=TaskType.WRITING,
        keywords=[
            "写博客", "写文章", "写作", "写文档", "写报告",
            "write blog", "write article", "documentation",
            "撰写", "润色", "改写", "优化文章",
            "blog", "article", "post", "writing",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE],
        recommended_timeout=600,
        note="写作任务，Claude Code 输出质量高",
    ),
    RoutingRule(
        task_type=TaskType.TRANSLATION,
        keywords=[
            "翻译", "translate", "translation",
            "中译英", "英译中", "翻译成",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE],
        recommended_timeout=300,
        note="翻译任务，Claude 系列模型翻译质量优秀",
    ),

    # ===== DevOps / 基础设施 =====
    RoutingRule(
        task_type=TaskType.DEVOPS,
        keywords=[
            "ci/cd", "github actions", "gitlab ci", "jenkins",
            "dockerfile", "容器化", "containerize",
            "部署", "deploy", "kubernetes", "k8s",
            "流水线", "pipeline", "自动化部署",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX],
        recommended_timeout=600,
        note="DevOps 任务，Claude Code 熟悉 YAML 和 Shell",
    ),
    RoutingRule(
        task_type=TaskType.INFRA,
        keywords=[
            "terraform", "ansible", "cloudformation",
            "基础设施", "infrastructure", "云配置",
            "aws", "gcp", "azure", "阿里云",
            "配置管理", "config management",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX],
        recommended_timeout=600,
        note="基础设施即代码，Claude Code 熟悉主流 IaC 工具",
    ),

    # ===== 数据与脚本 =====
    RoutingRule(
        task_type=TaskType.DATA_SCRIPT,
        keywords=[
            "数据处理", "data processing", "etl",
            "脚本", "script", "自动化",
            "bash script", "shell script", "python script",
            "批处理", "batch", "cron",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX, AgentType.CODEBUDDY],
        recommended_timeout=300,
        note="脚本任务，Codex 对 Shell/Python 脚本支持好",
    ),
    RoutingRule(
        task_type=TaskType.QUERY,
        keywords=[
            "sql", "查询", "database", "数据库",
            "api", "接口调用", "http request",
            "curl", "fetch", "request",
        ],
        preferred_agents=[AgentType.CLAUDE_CODE, AgentType.CODEX],
        recommended_timeout=300,
        note="查询/API 任务，Claude Code 可生成完整调用代码",
    ),
]


class TaskRouter:
    """
    任务路由器

    基于任务类型分类 + Agent 可用性 + 路由规则，
    自动选择最合适的 Agent 并推荐配置。
    """

    def __init__(
        self,
        registry: AdapterRegistry,
        rules: list[RoutingRule] | None = None,
        benchmark_db: "BenchmarkScoreDB | None" = None,
    ):
        self.registry = registry
        self.rules = rules or DEFAULT_ROUTING_RULES
        self.benchmark_db = benchmark_db
        # 编译关键词为正则（预编译加速）
        self._compiled_rules: list[tuple[RoutingRule, re.Pattern]] = []
        for rule in self.rules:
            if rule.keywords:
                pattern = re.compile(
                    "|".join(re.escape(k) for k in rule.keywords),
                    re.IGNORECASE,
                )
                self._compiled_rules.append((rule, pattern))

    def classify(self, prompt: str) -> TaskType:
        """
        从 prompt 文本分类任务类型

        Args:
            prompt: 任务描述文本

        Returns:
            分类结果（可能返回 TaskType.UNKNOWN）
        """
        if not prompt:
            return TaskType.UNKNOWN

        scores: dict[TaskType, int] = {}
        for rule, pattern in self._compiled_rules:
            matches = len(pattern.findall(prompt))
            if matches > 0:
                current = scores.get(rule.task_type, 0)
                scores[rule.task_type] = current + matches

        if not scores:
            return TaskType.GENERAL

        # 返回得分最高的类型
        best = max(scores, key=lambda t: scores[t])
        return best

    def route(self, prompt: str) -> RouteResult:
        """
        路由决策：给定 prompt，返回最佳 Agent + 推荐配置

        Args:
            prompt: 任务描述

        Returns:
            RouteResult：包含选中的 Agent、配置、路由原因
        """
        task_type = self.classify(prompt)
        rule = self._find_rule(task_type)

        # 获取所有可用 Agent
        available = self.registry.get_available()
        if not available:
            return RouteResult(
                agent=None,
                config=None,
                task_type=task_type,
                reason="No agents available",
                fallback_reason=None,
                confidence=0.0,
            )

        # 尝试按规则优先选择
        if rule and rule.preferred_agents:
            for agent_type in rule.preferred_agents:
                adapter = self.registry.get(agent_type)
                if adapter:
                    is_avail, _ = adapter.is_available()
                    if is_avail:
                        config = self._build_config_for_rule(prompt, rule)
                        confidence = self._calc_confidence(prompt, task_type, rule, adapter)
                        return RouteResult(
                            agent=adapter,
                            config=config,
                            task_type=task_type,
                            reason=f"Rule match: {rule.task_type.name}",
                            fallback_reason=None,
                            confidence=confidence,
                        )

        # 回退：auto_select（AdapterRegistry 的简单优先级）
        fallback = self.registry.auto_select()
        fallback_reason = "Preferred agent(s) not available, fell back to auto_select"
        if fallback:
            is_avail, _ = fallback.is_available()
            if is_avail:
                return RouteResult(
                    agent=fallback,
                    config=ExecutionConfig(prompt=prompt),
                    task_type=task_type,
                    reason="Auto-select fallback",
                    fallback_reason=fallback_reason,
                    confidence=0.3,
                )

        return RouteResult(
            agent=None,
            config=None,
            task_type=task_type,
            reason="No route available",
            fallback_reason=fallback_reason if fallback else "All agents unavailable",
            confidence=0.0,
        )

    def route_for_agents(
        self,
        prompt: str,
        agent_types: list[AgentType],
    ) -> RouteResult:
        """
        在指定 Agent 列表中路由（用户偏好优先）

        Args:
            prompt: 任务描述
            agent_types: 允许使用的 Agent 类型列表

        Returns:
            RouteResult
        """
        task_type = self.classify(prompt)
        rule = self._find_rule(task_type)

        for agent_type in agent_types:
            adapter = self.registry.get(agent_type)
            if adapter:
                is_avail, _ = adapter.is_available()
                if is_avail:
                    config = self._build_config_for_rule(prompt, rule)
                    confidence = self._calc_confidence(prompt, task_type, rule, adapter)
                    return RouteResult(
                        agent=adapter,
                        config=config,
                        task_type=task_type,
                        reason=f"User-specified agent: {agent_type.value}",
                        fallback_reason=None,
                        confidence=confidence,
                    )

        # 回退到任意可用
        fallback = self.registry.auto_select()
        return RouteResult(
            agent=fallback,
            config=ExecutionConfig(prompt=prompt) if fallback else None,
            task_type=task_type,
            reason="Fallback to available",
            fallback_reason="Specified agent(s) unavailable",
            confidence=0.2,
        )

    def explain_routing(self, prompt: str) -> str:
        """
        解释路由决策（用于调试/用户展示）

        Args:
            prompt: 任务描述

        Returns:
            可读的路由解释文本
        """
        task_type = self.classify(prompt)
        rule = self._find_rule(task_type)

        available = self.registry.get_available()
        lines = [
            f"📋 任务分类: {task_type.name}",
        ]

        if rule:
            lines.append(f"📌 匹配规则: {rule.task_type.name}")
            if rule.note:
                lines.append(f"   说明: {rule.note}")
            lines.append(f"   优先 Agent: {[a.value for a in rule.preferred_agents]}")

            if rule.recommended_timeout:
                lines.append(f"   推荐超时: {rule.recommended_timeout}s")

        lines.append(f"\n🔍 Agent 可用性:")
        for adapter, issue in available:
            status = f"❌ {issue}" if issue else "✅ 可用"
            lines.append(f"   {adapter.agent_type.value}: {status}")

        # 基准数据摘要
        if self.benchmark_db and self.benchmark_db.has_data():
            lines.append(f"\n📊 基准分数: {self.get_benchmark_summary()}")

        route_result = self.route(prompt)
        if route_result.agent:
            lines.append(f"\n✅ 最终选择: {route_result.agent.agent_type.value}")
            lines.append(f"   置信度: {route_result.confidence:.0%}")
            lines.append(f"   原因: {route_result.reason}")
        else:
            lines.append(f"\n❌ 无法路由: {route_result.reason}")

        return "\n".join(lines)

    def _find_rule(self, task_type: TaskType) -> RoutingRule | None:
        for rule in self.rules:
            if rule.task_type == task_type:
                return rule
        return None

    def _build_config_for_rule(
        self,
        prompt: str,
        rule: RoutingRule | None,
    ) -> ExecutionConfig:
        """根据规则构建推荐的 ExecutionConfig"""
        config = ExecutionConfig(prompt=prompt)
        if rule:
            if rule.recommended_timeout:
                config.timeout = rule.recommended_timeout
            # permission_mode 可以在这里扩展
        return config

    def _calc_confidence(
        self,
        prompt: str,
        task_type: TaskType,
        rule: RoutingRule | None,
        selected_agent: AgentAdapter | None = None,
    ) -> float:
        """
        计算路由置信度（0.0 - 1.0）

        融合两套信号：
        1. 关键词命中置信度（keyword_conf）
        2. 基准分数置信度（benchmark_conf）：基于历史真实评测数据

        最终置信度 = keyword_conf × 0.6 + benchmark_conf × 0.4
        当没有基准数据时，退化为纯关键词置信度。
        """
        if not rule or task_type == TaskType.UNKNOWN:
            return 0.2
        if task_type == TaskType.GENERAL:
            return 0.3

        # ---- 1. 关键词命中置信度 ----
        keyword_conf = self._keyword_confidence(prompt, task_type, rule)

        # ---- 2. 基准分数置信度 ----
        benchmark_conf = self._benchmark_confidence(task_type, selected_agent)

        # ---- 融合：如果有基准数据，使用加权平均 ----
        if benchmark_conf is not None:
            confidence = keyword_conf * 0.6 + benchmark_conf * 0.4
        else:
            confidence = keyword_conf

        return round(min(1.0, confidence), 2)

    def _keyword_confidence(
        self,
        prompt: str,
        task_type: TaskType,
        rule: RoutingRule | None,
    ) -> float:
        """基于关键词命中计算置信度"""
        if not rule:
            return 0.3
        total_kw = len(rule.keywords)
        if total_kw > 0:
            _, pattern = next(
                (r, p) for r, p in self._compiled_rules if r.task_type == task_type
            )
            matches = len(pattern.findall(prompt))
            # 命中 1 个关键词 → 0.5，命中 >=5 个 → 0.9
            return min(0.9, 0.4 + matches * 0.1)
        return 0.6

    def _benchmark_confidence(
        self,
        task_type: TaskType,
        selected_agent: AgentAdapter | None = None,
    ) -> float | None:
        """
        基于基准数据计算置信度。

        如果有该分类的基准数据：
        - 找到该分类得分最高的 Agent
        - 计算 selected_agent 的相对得分（相对最佳 Agent）
        - 返回相对得分作为基准置信度

        Returns:
            None 如果没有基准数据
            0.0 ~ 1.0 的置信度（相对得分）
        """
        if self.benchmark_db is None or not self.benchmark_db.has_data():
            return None

        # TaskType enum name → benchmark category name（如 CODING, REFACTORING）
        category = task_type.name

        # 检查该分类是否有数据
        best_agent = self.benchmark_db.get_best_agent(category)
        if best_agent is None:
            return None

        best_score = self.benchmark_db.get_score(best_agent, category)
        if best_score is None or best_score <= 0:
            return None

        # 如果没有选中 Agent（仅做分类），返回该分类的基准得分作为参考
        if selected_agent is None:
            return round(best_score, 2)

        # 计算选中 Agent 相对于最佳 Agent 的得分
        agent_score = self.benchmark_db.get_score(selected_agent.agent_type.value, category)
        if agent_score is None:
            return None

        # 相对得分：agent_score / best_score，上限 1.0
        relative = min(1.0, agent_score / best_score)
        return round(relative, 2)

    def get_benchmark_summary(self) -> str:
        """返回基准分数摘要（供 explain_routing 使用）"""
        if self.benchmark_db is None:
            return "（基准数据：未加载）"
        if not self.benchmark_db.has_data():
            return "（基准数据：无）"

        lines = []
        for agent in sorted(self.benchmark_db.agent_names()):
            overall = self.benchmark_db.get_overall(agent)
            if overall is not None:
                lines.append(f"{agent}={overall:.2f}")

        if not lines:
            return "（基准数据：无）"
        return f"（基准数据：{', '.join(lines)}）"


@dataclass
class RouteResult:
    """路由决策结果"""
    agent: AgentAdapter | None
    config: ExecutionConfig | None
    task_type: TaskType
    reason: str
    fallback_reason: str | None = None
    confidence: float = 0.0  # 0.0 - 1.0

    @property
    def success(self) -> bool:
        return self.agent is not None

    def __str__(self) -> str:
        if not self.agent:
            return f"RouteResult(FAILED: {self.reason})"
        return (
            f"RouteResult("
            f"agent={self.agent.agent_type.value}, "
            f"task_type={self.task_type.name}, "
            f"confidence={self.confidence:.0%})"
        )

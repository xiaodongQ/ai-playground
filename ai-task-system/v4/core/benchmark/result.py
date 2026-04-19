"""V4 Agent 能力评估基准：结果数据模型"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from ..base import AgentType


class ResultStatus(Enum):
    """任务执行状态"""
    PASS = auto()      # 通过
    FAIL = auto()      # 失败
    TIMEOUT = auto()   # 超时
    ERROR = auto()     # 执行错误
    SKIPPED = auto()   # 跳过


@dataclass
class TaskResult:
    """单个任务的执行结果"""
    task_id: str
    agent_type: AgentType
    status: ResultStatus

    # 时间和性能指标
    start_time: float = 0.0      # time.time() 时间戳
    end_time: float = 0.0       # time.time() 时间戳
    duration_seconds: float = 0.0  # 实际耗时

    # 质量评估（0.0 - 1.0）
    quality_score: float = 0.0  # 整体质量分
    correctness: float = 0.0    # 正确性
    completeness: float = 0.0   # 完整性
    code_quality: float = 0.0   # 代码质量
    clarity: float = 0.0         # 清晰度（仅写作类）

    # 输出信息
    raw_output: str = ""        # 原始输出（截断）
    output_tokens: int = 0      # 输出 token 数（估算）

    # 错误信息
    error_message: str | None = None

    # 元数据
    prompt_tokens: int = 0      # 输入 token 数（估算）
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.end_time and self.start_time:
            self.duration_seconds = self.end_time - self.start_time

    @property
    def passed(self) -> bool:
        return self.status == ResultStatus.PASS

    @property
    def score_summary(self) -> str:
        return (
            f"quality={self.quality_score:.2f}, "
            f"correctness={self.correctness:.2f}, "
            f"completeness={self.completeness:.2f}"
        )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type.name,
            "status": self.status.name,
            "duration_seconds": round(self.duration_seconds, 2),
            "quality_score": round(self.quality_score, 3),
            "correctness": round(self.correctness, 3),
            "completeness": round(self.completeness, 3),
            "code_quality": round(self.code_quality, 3),
            "clarity": round(self.clarity, 3),
            "output_tokens": self.output_tokens,
            "prompt_tokens": self.prompt_tokens,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TaskResult:
        from ..base import AgentType
        return cls(
            task_id=d["task_id"],
            agent_type=AgentType[d["agent_type"]],
            status=ResultStatus[d["status"]],
            duration_seconds=d.get("duration_seconds", 0),
            quality_score=d.get("quality_score", 0),
            correctness=d.get("correctness", 0),
            completeness=d.get("completeness", 0),
            code_quality=d.get("code_quality", 0),
            clarity=d.get("clarity", 0),
            output_tokens=d.get("output_tokens", 0),
            prompt_tokens=d.get("prompt_tokens", 0),
            error_message=d.get("error_message"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class BenchmarkResult:
    """完整 benchmark 运行结果"""
    run_id: str
    agent_types: list[AgentType]      # 本次评估的 Agent 列表
    task_ids: list[str]                # 评估的任务 ID 列表

    task_results: list[TaskResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    # 全局配置
    timeout_per_task: int = 600       # 每任务超时（秒）
    parallel: bool = False             # 是否并行

    @property
    def duration_seconds(self) -> float:
        if self.completed_at:
            return self.completed_at - self.started_at
        return time.time() - self.started_at

    def get_result(self, task_id: str, agent_type: AgentType) -> TaskResult | None:
        for r in self.task_results:
            if r.task_id == task_id and r.agent_type == agent_type:
                return r
        return None

    def get_agent_summary(self, agent_type: AgentType) -> dict:
        """获取某个 Agent 的汇总统计"""
        results = [r for r in self.task_results if r.agent_type == agent_type]
        if not results:
            return {}

        passed = sum(1 for r in results if r.passed)
        quality_scores = [r.quality_score for r in results]
        durations = [r.duration_seconds for r in results]

        return {
            "agent": agent_type.name,
            "total_tasks": len(results),
            "passed": passed,
            "pass_rate": round(passed / len(results), 3) if results else 0,
            "avg_quality": round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else 0,
            "avg_duration": round(sum(durations) / len(durations), 1) if durations else 0,
        }

    def get_task_summary(self, task_id: str) -> dict:
        """获取某个任务的汇总统计"""
        results = [r for r in self.task_results if r.task_id == task_id]
        if not results:
            return {}

        passed = sum(1 for r in results if r.passed)
        quality_scores = [r.quality_score for r in results]

        return {
            "task_id": task_id,
            "total_agents": len(results),
            "passed": passed,
            "pass_rate": round(passed / len(results), 3) if results else 0,
            "avg_quality": round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else 0,
        }

    def summary_table(self) -> str:
        """生成汇总表格"""
        lines = ["\n📊 Benchmark 结果汇总\n"]
        lines.append(f"{'Agent':<20} {'Tasks':>6} {'Pass':>6} {'Rate':>8} {'AvgQuality':>10} {'AvgTime':>8}")
        lines.append("-" * 65)

        for agent in self.agent_types:
            s = self.get_agent_summary(agent)
            if s:
                lines.append(
                    f"{s['agent']:<20} {s['total_tasks']:>6} "
                    f"{s['passed']:>6} {s['pass_rate']:>8.1%} "
                    f"{s['avg_quality']:>10.3f} {s['avg_duration']:>7.1f}s"
                )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "agent_types": [a.name for a in self.agent_types],
            "task_ids": self.task_ids,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "timeout_per_task": self.timeout_per_task,
            "parallel": self.parallel,
            "task_results": [r.to_dict() for r in self.task_results],
        }

    def to_json(self, indent: bool = True) -> str:
        return json.dumps(self.to_dict(), indent=2 if indent else None, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> BenchmarkResult:
        from ..base import AgentType
        br = cls(
            run_id=d["run_id"],
            agent_types=[AgentType[a] for a in d["agent_types"]],
            task_ids=d["task_ids"],
            started_at=d.get("started_at", 0),
            completed_at=d.get("completed_at", 0),
            timeout_per_task=d.get("timeout_per_task", 600),
            parallel=d.get("parallel", False),
        )
        br.task_results = [TaskResult.from_dict(r) for r in d.get("task_results", [])]
        return br

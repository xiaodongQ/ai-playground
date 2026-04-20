"""V4 Agent 能力评估基准（Agent Capability Benchmark）

提供标准化的任务基准测试套件，用于评估和比较不同 Agent 在各类任务上的表现。

主要组件：
- tasks.py: 标准 benchmark 任务定义
- runner.py: 基准测试执行器
- db.py: 分数数据库（SQLite）
"""
from .tasks import BENCHMARK_TASKS, BenchmarkTask, TaskCategory
from .runner import BenchmarkRunner, cmd_benchmark
from .result import BenchmarkResult, TaskResult

__all__ = [
    "BenchmarkTask",
    "TaskCategory",
    "BenchmarkResult",
    "TaskResult",
    "BenchmarkRunner",
    "cmd_benchmark",
    "BENCHMARK_TASKS",
]

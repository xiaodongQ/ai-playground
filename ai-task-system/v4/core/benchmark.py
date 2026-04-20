"""
AI Task System V4 — Agent 能力评估基准

对各 Agent（Claude/Codex/CodeBuddy）在标准化任务集上进行能力评估，
为 TaskRouter 提供实证路由数据。

任务分类：
  - CODING        : 短代码片段（函数/类）
  - REFACTORING   : 代码重构
  - DEBUGGING     : Bug 定位与修复
  - ARCHITECTURE  : 系统设计
  - LEARNING      : 概念解释
  - WRITING       : 文档/报告撰写
  - SHELL         : Shell 命令
  - RESEARCH      : 信息检索与总结

运行方式：
  python -m ai_task_system.v4.cli benchmark
  python -m ai_task_system.v4.cli benchmark --agent claude --tasks coding
  python -m ai_task_system.v4.cli benchmark --report  # 输出 CSV
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from ai_task_system.v4.core.base import (
    AdapterRegistry,
    AgentType,
    ExecutionConfig,
    PermissionMode,
)
from ai_task_system.v4.core.executor import SubprocessExecutor
from ai_task_system.v4.core.command_builder import CommandBuilder


# ---------------------------------------------------------------------------
# 任务难度
# ---------------------------------------------------------------------------
class Difficulty:
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ---------------------------------------------------------------------------
# 标准任务集
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkTask:
    id: str
    name: str
    category: str
    prompt: str
    timeout: int = 60  # 秒
    expected_keywords: list[str] = field(default_factory=list)
    difficulty: str = Difficulty.MEDIUM  # easy | medium | hard
    # 评估维度提示（用于多维评分）
    scoring_hints: dict[str, float] = field(default_factory=dict)  # {dimension: weight}

BENCHMARK_TASKS: list[BenchmarkTask] = [
    # CODING
    BenchmarkTask(
        id="coding-fibonacci",
        name="Fibonacci Function",
        category="CODING",
        prompt="Write a Python function `fib(n)` that returns the nth Fibonacci number using iteration (not recursion). Include type hints and a docstring.",
        timeout=30,
        expected_keywords=["def fib", "iter", "int"],
    ),
    BenchmarkTask(
        id="coding-quick-sort",
        name="Quick Sort",
        category="CODING",
        prompt="Implement quick sort in Python. Write a function that takes a list and returns a sorted list. Use in-place partitioning.",
        timeout=45,
        expected_keywords=["def quick_sort", "pivot", "partition"],
    ),
    BenchmarkTask(
        id="coding-json-parser",
        name="JSON Parser",
        category="CODING",
        prompt="Write a minimal JSON parser in Python that can handle: objects {}, arrays [], strings, numbers, booleans, and null. Use recursive descent parsing.",
        timeout=60,
        expected_keywords=["json", "parse", "def"],
    ),

    # REFACTORING
    BenchmarkTask(
        id="refactor-long-function",
        name="Long Function Refactor",
        category="REFACTORING",
        prompt="""Refactor this Python function into smaller, more readable parts:

def process_data(data):
    result = []
    for item in data:
        if item['type'] == 'a':
            value = item['value'] * 2
            if value > 10:
                value = 10
            result.append({'type': 'a', 'processed': value})
        elif item['type'] == 'b':
            value = item['value'] + 5
            if value < 0:
                value = 0
            result.append({'type': 'b', 'processed': value})
        else:
            result.append({'type': 'unknown', 'processed': 0})
    return result

Extract helper functions and explain what each does.""",
        timeout=60,
        expected_keywords=["def ", "helper", "function"],
    ),
    BenchmarkTask(
        id="refactor-globals",
        name="Global State Refactor",
        category="REFACTORING",
        prompt="""Refactor this code to eliminate global variables using a class or closure:

counter = 0
total = 0

def add(x):
    global counter, total
    counter += 1
    total += x
    return total

def get_count():
    return counter

def reset():
    global counter, total
    counter = 0
    total = 0

Show the refactored version.""",
        timeout=60,
        expected_keywords=["class ", "self.", "__init__"],
    ),

    # DEBUGGING
    BenchmarkTask(
        id="debug-infinite-loop",
        name="Infinite Loop Bug",
        category="DEBUGGING",
        prompt="""Find and fix the bug in this Python code:

def find_duplicates(nums):
    seen = {}
    duplicates = []
    for num in nums:
        if num in seen:
            duplicates.append(num)
        else:
            seen[num] = True
    return duplicates

print(find_duplicates([1, 2, 3, 2, 4, 3]))  # Expected: [2, 3]""",
        timeout=45,
        expected_keywords=["set", "seen[num]", "True", "bug"],
    ),
    BenchmarkTask(
        id="debug-off-by-one",
        name="Off-by-One Error",
        category="DEBUGGING",
        prompt="""Debug this binary search implementation:

def binary_search(arr, target):
    left, right = 0, len(arr)
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

print(binary_search([1, 3, 5, 7, 9], 7))  # Returns -1 instead of 3""",
        timeout=45,
        expected_keywords=["right", "len(arr)", "-1", "bug"],
    ),

    # ARCHITECTURE
    BenchmarkTask(
        id="arch-url-shortener",
        name="URL Shortener Design",
        category="ARCHITECTURE",
        prompt="Design a URL shortener service (like bit.ly). Include: data model, API endpoints, hash strategy, collision resolution, and scaling considerations.",
        timeout=90,
        expected_keywords=["API", "database", "hash", "scale"],
    ),
    BenchmarkTask(
        id="arch-event-sourcing",
        name="Event Sourcing Pattern",
        category="ARCHITECTURE",
        prompt="Explain event sourcing CQRS pattern. When is it appropriate? What are the main challenges? Provide a simple Python example showing event storage and projection.",
        timeout=90,
        expected_keywords=["event", "command", "query", "aggregate"],
    ),

    # LEARNING
    BenchmarkTask(
        id="learn-closures",
        name="Python Closures",
        category="LEARNING",
        prompt="Explain Python closures with a practical example. When would you use a closure vs a class?",
        timeout=45,
        expected_keywords=["closure", "nonlocal", "scope"],
    ),
    BenchmarkTask(
        id="learn-async-io",
        name="Async IO",
        category="LEARNING",
        prompt="Explain Python asyncio. When should you use async/await vs multithreading vs multiprocessing?",
        timeout=60,
        expected_keywords=["async", "await", "event loop", "coroutine"],
    ),

    # WRITING
    BenchmarkTask(
        id="write-readme",
        name="README Writing",
        category="WRITING",
        prompt="Write a README.md for a Python CLI tool called `csvstats` that reads a CSV file and prints summary statistics. Include: description, installation, usage examples, and output format.",
        timeout=60,
        expected_keywords=["# csvstats", "## Installation", "## Usage", "```"],
    ),

    # SHELL
    BenchmarkTask(
        id="shell-find-duplicates",
        name="Find Duplicate Files",
        category="SHELL",
        prompt="Write a bash one-liner to find all duplicate files in /tmp by content (using md5sum), ignoring the first field (filename).",
        timeout=30,
        expected_keywords=["md5sum", "sort", "uniq", "cut"],
    ),
    BenchmarkTask(
        id="shell-log-analysis",
        name="Log Analysis",
        category="SHELL",
        prompt="Write a bash pipeline to find the top 10 IP addresses from an Apache access log (format: '127.0.0.1 - - ...'), sorted by request count.",
        timeout=30,
        expected_keywords=["awk", "sort", "uniq", "head"],
    ),

    # RESEARCH
    BenchmarkTask(
        id="research-python-gil",
        name="Python GIL",
        category="RESEARCH",
        prompt="What is Python's GIL? How does it affect multithreading? What are the alternatives? Be concise.",
        timeout=45,
        expected_keywords=["GIL", "Global", "Interpreter", "Lock"],
    ),
]

# ---------------------------------------------------------------------------
# 评估结果
# ---------------------------------------------------------------------------
@dataclass
class TaskResult:
    task_id: str
    agent: str
    category: str
    status: str  # success | timeout | error | skipped
    duration: float  # 秒
    output_snippet: str
    keyword_match_count: int
    score: float  # 0.0 ~ 1.0
    timestamp: str


@dataclass
class BenchmarkReport:
    agent: str
    overall_score: float
    category_scores: dict[str, float]
    task_results: list[TaskResult]
    total_duration: float
    timestamp: str


# ---------------------------------------------------------------------------
# Agent 评估器
# ---------------------------------------------------------------------------
class AgentBenchmarker:
    def __init__(self, agent_type: AgentType, verbose: bool = False):
        self.agent_type = agent_type
        self.verbose = verbose
        self.registry = AdapterRegistry()
        self._setup_adapters()

    def _setup_adapters(self) -> None:
        from ai_task_system.v4.adapters.claude_adapter import ClaudeCodeAdapter
        from ai_task_system.v4.adapters.codex_adapter import CodexAdapter
        from ai_task_system.v4.adapters.codebuddy_adapter import CodeBuddyAdapter
        self.registry.register(ClaudeCodeAdapter())
        self.registry.register(CodexAdapter())
        self.registry.register(CodeBuddyAdapter())

    def _get_adapter(self):
        return self.registry.get(self.agent_type)

    def _run_single_task(self, task: BenchmarkTask) -> TaskResult:
        adapter = self._get_adapter()
        if adapter is None:
            return TaskResult(
                task_id=task.id,
                agent=self.agent_type.value,
                category=task.category,
                status="skipped",
                duration=0.0,
                output_snippet="",
                keyword_match_count=0,
                score=0.0,
                timestamp=datetime.now().isoformat(),
            )

        # 检查 Agent 可用性
        available, msg = adapter.is_available()
        if not available:
            return TaskResult(
                task_id=task.id,
                agent=self.agent_type.value,
                category=task.category,
                status="skipped",
                duration=0.0,
                output_snippet=f"Not available: {msg}",
                keyword_match_count=0,
                score=0.0,
                timestamp=datetime.now().isoformat(),
            )

        config = ExecutionConfig(
            prompt=task.prompt,
            agent_type=self.agent_type,
            permission_mode=PermissionMode.AUTO,
            timeout=task.timeout,
            no_output_timeout=30,
            allowed_tools=["Bash", "Read", "Write", "Edit"],
        )

        ok, err = adapter.validate_config(config)
        if not ok:
            return TaskResult(
                task_id=task.id,
                agent=self.agent_type.value,
                category=task.category,
                status="error",
                duration=0.0,
                output_snippet=f"Config error: {err}",
                keyword_match_count=0,
                score=0.0,
                timestamp=datetime.now().isoformat(),
            )

        executor = SubprocessExecutor()

        start = time.time()
        try:
            task_obj = executor.execute(config, adapter)
            duration = time.time() - start

            # executor.execute() returns a Task; result is in task_obj.result
            exec_result = task_obj.result
            if exec_result is None:
                status = "error"
                output = f"No result: task status={task_obj.status}"
                snippet = output[:500]
                matches = 0
                score = 0.0
            else:
                status = "success" if exec_result.return_code == 0 else "error"
                output = exec_result.stdout + exec_result.stderr
                snippet = output[:500]

                # 关键词匹配
                matches = sum(1 for kw in task.expected_keywords if kw.lower() in output.lower())
                match_ratio = matches / max(len(task.expected_keywords), 1)
                score = match_ratio if status == "success" else 0.0

            return TaskResult(
                task_id=task.id,
                agent=self.agent_type.value,
                category=task.category,
                status=status,
                duration=duration,
                output_snippet=snippet,
                keyword_match_count=matches,
                score=score,
                timestamp=datetime.now().isoformat(),
            )
        except TimeoutError:
            duration = time.time() - start
            return TaskResult(
                task_id=task.id,
                agent=self.agent_type.value,
                category=task.category,
                status="timeout",
                duration=duration,
                output_snippet="Task timed out",
                keyword_match_count=0,
                score=0.0,
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            duration = time.time() - start
            return TaskResult(
                task_id=task.id,
                agent=self.agent_type.value,
                category=task.category,
                status="error",
                duration=duration,
                output_snippet=str(e),
                keyword_match_count=0,
                score=0.0,
                timestamp=datetime.now().isoformat(),
            )

    def run(self, task_filter: str | None = None) -> BenchmarkReport:
        tasks = BENCHMARK_TASKS
        if task_filter:
            tasks = [t for t in tasks if t.category.lower() == task_filter.lower()]

        results: list[TaskResult] = []
        start_total = time.time()

        for task in tasks:
            if self.verbose:
                print(f"  [{self.agent_type.value}] Running: {task.name}...", end=" ", flush=True)

            result = self._run_single_task(task)
            results.append(result)

            if self.verbose:
                print(f"{result.status} ({result.duration:.1f}s, score={result.score:.2f})")

        total_duration = time.time() - start_total

        # 聚合分类得分
        category_scores: dict[str, float] = {}
        for cat in set(r.category for r in results):
            cat_results = [r for r in results if r.category == cat]
            scores = [r.score for r in cat_results]
            category_scores[cat] = sum(scores) / len(scores) if scores else 0.0

        overall = sum(r.score for r in results) / len(results) if results else 0.0

        return BenchmarkReport(
            agent=self.agent_type.value,
            overall_score=overall,
            category_scores=category_scores,
            task_results=results,
            total_duration=total_duration,
            timestamp=datetime.now().isoformat(),
        )


# ---------------------------------------------------------------------------
# 多 Agent 对比报告
# ---------------------------------------------------------------------------
def run_full_benchmark(verbose: bool = False, task_filter: str | None = None) -> dict[str, BenchmarkReport]:
    """对所有可用的 Agent 运行基准测试"""
    agents = [AgentType.CLAUDE_CODE, AgentType.CODEX, AgentType.CODEBUDDY]
    reports: dict[str, BenchmarkReport] = {}

    for agent in agents:
        bench = AgentBenchmarker(agent, verbose=verbose)
        print(f"\nBenchmarking {agent.value}...")
        reports[agent.value] = bench.run(task_filter=task_filter)
        print(f"  Overall score: {reports[agent.value].overall_score:.2f}")

    return reports


def print_comparison(reports: dict[str, BenchmarkReport]) -> None:
    """打印多 Agent 对比表格"""
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
    except ImportError:
        console = None

    if console:
        table = Table(title="Agent Capability Comparison")
        table.add_column("Category", style="cyan")
        for agent in reports:
            table.add_column(agent, justify="right")

        all_categories = sorted(set(
            cat for r in reports.values() for cat in r.category_scores
        ))
        for cat in all_categories:
            row = [cat]
            for agent in reports:
                score = reports[agent].category_scores.get(cat, 0.0)
                row.append(f"{score:.2f}")
            table.add_row(*row)

        table.add_row("", "")  # spacer
        overall_row = ["OVERALL"]
        for agent in reports:
            overall_row.append(f"{reports[agent].overall_score:.2f}")
        table.add_row(*overall_row, style="bold")

        console.print(table)
    else:
        # Plain text fallback
        print("\nAgent Capability Comparison")
        print("=" * 60)
        all_categories = sorted(set(
            cat for r in reports.values() for cat in r.category_scores
        ))
        print(f"{'Category':<20}", end="")
        for agent in reports:
            print(f"{agent:>15}", end="")
        print()
        print("-" * 60)
        for cat in all_categories:
            print(f"{cat:<20}", end="")
            for agent in reports:
                score = reports[agent].category_scores.get(cat, 0.0)
                print(f"{score:>15.2f}", end="")
            print()
        print("-" * 60)
        print(f"{'OVERALL':<20}", end="")
        for agent in reports:
            print(f"{reports[agent].overall_score:>15.2f}", end="")
        print()


def export_csv(reports: dict[str, BenchmarkReport], path: str | None = None) -> str:
    """导出 CSV 格式报告"""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["agent", "category", "task_id", "task_name", "status", "duration", "score", "keyword_matches"])

    task_names = {t.id: t.name for t in BENCHMARK_TASKS}

    for agent, report in reports.items():
        for result in report.task_results:
            writer.writerow([
                result.agent,
                result.category,
                result.task_id,
                task_names.get(result.task_id, ""),
                result.status,
                f"{result.duration:.2f}",
                f"{result.score:.2f}",
                result.keyword_match_count,
            ])

    csv_text = buf.getvalue()

    if path:
        Path(path).write_text(csv_text)
        print(f"CSV report saved to: {path}")

    return csv_text


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------
def cmd_benchmark(args) -> int:
    """CLI benchmark 命令实现"""
    agent_filter = args.agent if hasattr(args, 'agent') and args.agent else None
    task_filter = args.tasks if hasattr(args, 'tasks') and args.tasks else None
    export_path = args.report if hasattr(args, 'report') and args.report else None
    verbose = args.verbose if hasattr(args, 'verbose') else False

    if agent_filter:
        try:
            agent_type = AgentType(agent_filter)
        except ValueError:
            print(f"Unknown agent: {agent_filter}")
            print(f"Available: {[a.value for a in AgentType]}")
            return 1

        bench = AgentBenchmarker(agent_type, verbose=verbose)
        print(f"Benchmarking {agent_type.value}...")
        report = bench.run(task_filter=task_filter)

        print(f"\n=== {report.agent} Benchmark Results ===")
        print(f"Overall Score: {report.overall_score:.2f}")
        print(f"Total Duration: {report.total_duration:.1f}s")
        print(f"\nCategory Scores:")
        for cat, score in sorted(report.category_scores.items()):
            print(f"  {cat:<15} {score:.2f}")

        print(f"\nTask Results:")
        for r in report.task_results:
            icon = "✅" if r.status == "success" else "❌" if r.status == "error" else "⏰" if r.status == "timeout" else "⏭️"
            print(f"  {icon} {r.task_id:<30} {r.status:<10} {r.duration:>6.1f}s  score={r.score:.2f}")
    else:
        # 全量对比
        reports = run_full_benchmark(verbose=verbose, task_filter=task_filter)
        print_comparison(reports)

        if export_path:
            csv_text = export_csv(reports, export_path)
            print(f"\nCSV saved to: {export_path}")

    return 0

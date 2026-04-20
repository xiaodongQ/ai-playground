"""V4 Agent 能力评估基准：执行器

对给定的 Agent + 任务组合执行基准测试，支持：
- 本地 agent 可用性检测
- 自动评分（基于规则）
- 分数持久化到 SQLite
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from ..base import AgentType
from .db import BenchmarkDB
from .result import BenchmarkResult, ResultStatus, TaskResult
from .tasks import BenchmarkTask

if TYPE_CHECKING:
    pass


@dataclass
class BenchmarkRunnerConfig:
    """Benchmark Runner 配置"""
    timeout_per_task: int = 600       # 每任务超时（秒）
    parallel: bool = False            # 是否并行执行多 Agent
    max_workers: int = 3              # 并行 worker 数
    save_to_db: bool = True           # 是否保存到数据库
    auto_score: bool = True           # 是否自动评分
    verbose: bool = True              # 详细输出
    dry_run: bool = False             # 仅显示命令不执行


class DefaultScorer:
    """默认评分器（基于规则）"""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算 token 数（中文≈2chars/token，英文≈4chars/token）"""
        chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
        english = len(re.findall(r'[a-zA-Z]', text))
        other = len(text) - chinese - english
        return int(chinese * 0.5 + english * 0.25 + other * 0.5)

    def score_task_result(self, task: BenchmarkTask, raw_output: str) -> TaskResult:
        """根据任务类型和输出内容评分"""
        tr = TaskResult(
            task_id=task.id,
            agent_type=AgentType.CLAUDE_CODE,  # 占位，下层会替换
            status=ResultStatus.PASS,
            start_time=time.time(),
            end_time=time.time(),
        )
        tr.prompt_tokens = self.estimate_tokens(task.prompt)
        tr.output_tokens = self.estimate_tokens(raw_output)
        tr.raw_output = raw_output[:5000]

        # ---- 基础评分逻辑 ----
        output_lower = raw_output.lower()
        prompt_lower = task.prompt.lower()

        # 1. 正确性评估
        correctness = 0.5  # 基础分

        # 检查关键代码元素是否存在（根据任务类型）
        if task.category.name == "CODING":
            # 检查是否有代码块
            if "```" in raw_output:
                correctness += 0.2
            # 检查是否有函数/类定义（简单关键字检测）
            code_keywords = ["def ", "class ", "func ", "fn ", "impl "]
            if any(kw in raw_output for kw in code_keywords):
                correctness += 0.15
            # 检查是否有 imports
            if re.search(r'(import |from .+ import|#include|require|use )', raw_output):
                correctness += 0.1
            # 检查是否有明显的错误关键词
            error_keywords = ["error", "exception", "traceback", "failed", "not defined"]
            error_count = sum(1 for kw in error_keywords if kw in output_lower)
            correctness -= error_count * 0.05
            correctness = max(0.0, min(1.0, correctness))

        elif task.category.name == "DEBUGGING":
            # 调试任务：检查是否有原因分析、修复方案
            debug_keywords = ["原因", "cause", "问题", "fix", "修复", "solution", "race", "leak"]
            if sum(1 for kw in debug_keywords if kw in output_lower) >= 3:
                correctness += 0.3
            if "race" in output_lower or "竞争" in raw_output:
                correctness += 0.1
            if "lock" in output_lower or "mutex" in output_lower or "原子" in raw_output:
                correctness += 0.1
            correctness = max(0.0, min(1.0, correctness))

        elif task.category.name == "ARCHITECTURE":
            # 架构任务：检查是否有架构组件描述
            arch_keywords = ["架构", "component", "service", "database", "cache", "queue"]
            arch_count = sum(1 for kw in arch_keywords if kw in output_lower)
            if arch_count >= 3:
                correctness += 0.3
            elif arch_count >= 1:
                correctness += 0.1
            correctness = max(0.0, min(1.0, correctness))

        elif task.category.name == "RESEARCH":
            # 研究任务：检查是否有引用、数据
            research_keywords = ["python", "go", "java", "http", "api", "性能", "延迟", "qps"]
            if sum(1 for kw in research_keywords if kw in output_lower) >= 2:
                correctness += 0.2
            correctness = max(0.0, min(1.0, correctness))

        elif task.category.name in ("WRITING", "DEVOPS"):
            # 写作/DevOps：检查结构完整性
            structure_keywords = ["##", "# ", "1.", "2.", "- ", "* ", "```"]
            if sum(1 for kw in structure_keywords if kw in raw_output) >= 3:
                correctness += 0.2
            correctness = max(0.0, min(1.0, correctness))

        tr.correctness = correctness

        # 2. 完整性评估
        # 根据 prompt 长度估算任务复杂度
        prompt_complexity = min(len(task.prompt) / 500, 1.0)
        output_ratio = len(raw_output) / max(len(task.prompt), 1)

        completeness = 0.5
        if output_ratio > 0.5:
            completeness += 0.2
        if output_ratio > 1.0:
            completeness += 0.15
        if output_ratio > 2.0:
            completeness += 0.1
        completeness = min(1.0, completeness)
        tr.completeness = completeness

        # 3. 代码质量（仅对编码任务）
        if task.category.name == "CODING":
            code_blocks = re.findall(r'```[\w]*\n(.*?)```', raw_output, re.DOTALL)
            code_text = '\n'.join(code_blocks) if code_blocks else raw_output

            quality = 0.5
            # 命名规范检测（简单）
            if re.search(r'[a-z][a-z0-9_]*\s*=', code_text):  # snake_case
                quality += 0.1
            # 注释检测
            if '# ' in code_text or '// ' in code_text or '"""' in code_text:
                quality += 0.1
            # 函数结构检测
            if re.search(r'def \w+\(.*\):', code_text) or re.search(r'func \w+\(.*\)', code_text):
                quality += 0.1
            # docstring
            if '"""' in code_text or "'''" in code_text:
                quality += 0.05
            quality = min(1.0, quality)
            tr.code_quality = quality
        else:
            tr.code_quality = (tr.correctness + tr.completeness) / 2

        # 4. 清晰度（写作类任务）
        if task.category.name in ("WRITING", "RESEARCH"):
            lines = raw_output.split('\n')
            has_headers = any(re.match(r'^#{1,3}\s', l) for l in lines)
            has_lists = any(re.match(r'^\d+\.|^-\s', l) for l in lines)
            clarity = 0.5
            if has_headers:
                clarity += 0.2
            if has_lists:
                clarity += 0.15
            if len(raw_output) > 500:
                clarity += 0.1
            clarity = min(1.0, clarity)
            tr.clarity = clarity
        else:
            tr.clarity = (tr.correctness + tr.completeness) / 2

        # 5. 整体质量分（加权平均）
        if task.category.name == "CODING":
            tr.quality_score = (
                tr.correctness * 0.35 +
                tr.completeness * 0.30 +
                tr.code_quality * 0.35
            )
        elif task.category.name == "DEBUGGING":
            tr.quality_score = tr.correctness * 0.7 + tr.completeness * 0.3
        elif task.category.name == "ARCHITECTURE":
            tr.quality_score = tr.correctness * 0.5 + tr.completeness * 0.5
        elif task.category.name in ("WRITING", "RESEARCH"):
            tr.quality_score = (
                tr.correctness * 0.3 +
                tr.completeness * 0.3 +
                tr.clarity * 0.4
            )
        elif task.category.name == "DEVOPS":
            tr.quality_score = (
                tr.correctness * 0.4 +
                tr.completeness * 0.35 +
                tr.code_quality * 0.25
            )
        else:
            tr.quality_score = (
                tr.correctness * 0.4 +
                tr.completeness * 0.4 +
                tr.code_quality * 0.2
            )

        return tr


class BenchmarkRunner:
    """Benchmark 执行器"""

    def __init__(
        self,
        config: BenchmarkRunnerConfig | None = None,
        db: BenchmarkDB | None = None,
    ):
        self.config = config or BenchmarkRunnerConfig()
        self.db = db or BenchmarkDB()
        self.scorer = DefaultScorer()

    def check_agent_available(self, agent_type: AgentType) -> tuple[bool, str]:
        """检测 Agent 是否可用"""
        if agent_type == AgentType.CLAUDE_CODE:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            # 也检查 code 命令
            result2 = subprocess.run(
                ["claude", "code", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result2.returncode == 0:
                return True, result2.stdout.strip()
            return False, "claude not found in PATH"
        elif agent_type == AgentType.CODEX:
            result = subprocess.run(
                ["which", "codex"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, "codex found"
            return False, "codex not found in PATH"
        elif agent_type == AgentType.CODEBUDDY:
            result = subprocess.run(
                ["which", "codebuddy"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, "codebuddy found"
            return False, "codebuddy not found in PATH"
        return False, f"unknown agent: {agent_type}"

    def run_single_task(
        self,
        task: BenchmarkTask,
        agent_type: AgentType,
    ) -> TaskResult:
        """运行单个任务，返回 TaskResult"""
        start = time.time()
        tr = TaskResult(
            task_id=task.id,
            agent_type=agent_type,
            status=ResultStatus.PASS,
            start_time=start,
        )

        if self.config.verbose:
            print(f"  [{agent_type.name}] {task.id} {task.name}...", end=" ", flush=True)

        # 构建命令
        if agent_type == AgentType.CLAUDE_CODE:
            cmd = [
                "claude", "--print",
                "--output-format", "text",
                "--model", "sonnet",
                "--",
                task.prompt,
            ]
        elif agent_type == AgentType.CODEX:
            cmd = [
                "codex", "exec",
                f"--prompt={task.prompt}",
                "--json",
            ]
        elif agent_type == AgentType.CODEBUDDY:
            cmd = [
                "codebuddy",
                "-p", task.prompt,
            ]
        else:
            tr.status = ResultStatus.ERROR
            tr.error_message = f"Unsupported agent: {agent_type}"
            return tr

        if self.config.dry_run:
            tr.status = ResultStatus.SKIPPED
            tr.raw_output = f"# DRY RUN\n# Command: {' '.join(cmd)}"
            tr.end_time = time.time()
            if self.config.verbose:
                print("SKIPPED (dry run)")
            return tr

        # 执行
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_per_task,
                env={**subprocess.os.environ.copy()},
            )
            raw_output = proc.stdout
            if proc.returncode != 0 and not raw_output:
                raw_output = proc.stderr

        except subprocess.TimeoutExpired:
            tr.status = ResultStatus.TIMEOUT
            tr.error_message = f"Timeout after {self.config.timeout_per_task}s"
            tr.end_time = time.time()
            tr.duration_seconds = tr.end_time - tr.start_time
            if self.config.verbose:
                print(f"TIMEOUT ({tr.duration_seconds:.0f}s)")
            return tr

        except FileNotFoundError:
            tr.status = ResultStatus.ERROR
            tr.error_message = f"Agent '{agent_type.name}' not found in PATH"
            tr.end_time = time.time()
            tr.duration_seconds = tr.end_time - tr.start_time
            if self.config.verbose:
                print(f"ERROR: {tr.error_message}")
            return tr

        except Exception as e:
            tr.status = ResultStatus.ERROR
            tr.error_message = str(e)
            tr.end_time = time.time()
            tr.duration_seconds = tr.end_time - tr.start_time
            if self.config.verbose:
                print(f"ERROR: {e}")
            return tr

        tr.end_time = time.time()
        tr.duration_seconds = tr.end_time - tr.start_time

        # 自动评分
        if self.config.auto_score:
            scored = self.scorer.score_task_result(task, raw_output)
            tr.raw_output = scored.raw_output
            tr.output_tokens = scored.output_tokens
            tr.prompt_tokens = scored.prompt_tokens
            tr.correctness = scored.correctness
            tr.completeness = scored.completeness
            tr.code_quality = scored.code_quality
            tr.clarity = scored.clarity
            tr.quality_score = scored.quality_score
        else:
            tr.raw_output = raw_output[:5000]

        if self.config.verbose:
            status_icon = "✅" if tr.passed else "❌"
            print(
                f"{status_icon} {tr.duration_seconds:.0f}s "
                f"quality={tr.quality_score:.2f} "
                f"correct={tr.correctness:.2f}"
            )

        return tr

    def run(
        self,
        tasks: list[BenchmarkTask],
        agent_types: list[AgentType],
        run_id: str | None = None,
    ) -> BenchmarkResult:
        """运行完整的 benchmark"""
        run_id = run_id or f"run-{uuid.uuid4().hex[:8]}-{int(time.time())}"

        if self.config.verbose:
            print(f"\n🚀 Benchmark Run: {run_id}")
            print(f"   Agents: {[a.name for a in agent_types]}")
            print(f"   Tasks:  {[t.id for t in tasks]}")
            print(f"   Parallel: {self.config.parallel}")
            print()

        result = BenchmarkResult(
            run_id=run_id,
            agent_types=agent_types,
            task_ids=[t.id for t in tasks],
            timeout_per_task=self.config.timeout_per_task,
            parallel=self.config.parallel,
        )

        # 并行执行
        if self.config.parallel and len(agent_types) > 1:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {}
                for agent in agent_types:
                    for task in tasks:
                        future = executor.submit(self.run_single_task, task, agent)
                        futures[future] = (task, agent)

                for future in as_completed(futures):
                    task, agent = futures[future]
                    try:
                        tr = future.result()
                        result.task_results.append(tr)
                    except Exception as e:
                        tr = TaskResult(
                            task_id=task.id,
                            agent_type=agent,
                            status=ResultStatus.ERROR,
                            error_message=str(e),
                        )
                        result.task_results.append(tr)

        # 串行执行
        else:
            for agent in agent_types:
                available, msg = self.check_agent_available(agent)
                if not available:
                    if self.config.verbose:
                        print(f"⏭️  [{agent.name}] Skipped: {msg}")
                    for task in tasks:
                        tr = TaskResult(
                            task_id=task.id,
                            agent_type=agent,
                            status=ResultStatus.SKIPPED,
                            error_message=msg,
                        )
                        result.task_results.append(tr)
                    continue

                for task in tasks:
                    tr = self.run_single_task(task, agent)
                    result.task_results.append(tr)

        result.completed_at = time.time()

        # 保存到数据库
        if self.config.save_to_db:
            self.db.save_result(result)

        # 打印汇总
        if self.config.verbose:
            print(result.summary_table())
            print(f"\n✅ Run {run_id} completed in {result.duration_seconds:.1f}s")
            if self.config.save_to_db:
                print(f"   Saved to: {self.db.db_path}")

        return result

from ai_task_system.v4.core.base import ExecutionConfig, PermissionMode

from ai_task_system.v4.core.base import ExecutionConfig, PermissionMode
from ai_task_system.v4.core.executor import SubprocessExecutor
from ai_task_system.v4.core.command_builder import CommandBuilder

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

#!/usr/bin/env python3
"""
V4 AI Task System - CLI 入口

用法示例:
    python -m ai_task_system.v4.cli create "用 Python 实现快速排序"
    python -m ai_task_system.v4.cli list
    python -m ai_task_system.v4.cli status <task-id>
    python -m ai_task_system.v4.cli stop <task-id>
    python -m ai_task_system.v4.cli agents
    python -m ai_task_system.v4.cli benchmark --agent claude
    python -m ai_task_system.v4.cli benchmark --report /tmp/benchmark.csv

兼容直接运行（自动设置模块路径）:
    python v4/cli.py agents
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ── 自动路径补全（支持 python v4/cli.py 直接运行）──────────────
# 检测是否为直接运行（而非 python -m 模式）
if __name__ == "__main__" and "ai_task_system" not in sys.modules:
    _script_dir = Path(__file__).resolve().parent  # v4/
    _pkg_root = _script_dir.parent                   # ai-task-system/
    _parent = _pkg_root.parent                       # 父目录
    if str(_parent) not in sys.path:
        sys.path.insert(0, str(_parent))
    # 预先导入包，确立包层级，使相对导入可以求值
    import ai_task_system.v4
    import ai_task_system.v4.core
    import ai_task_system.v4.adapters

# 统一使用绝对导入（相对导入在直接运行时上下文不完整）
from ai_task_system.v4.core.base import (
    AdapterRegistry,
    AgentType,
    ExecutionConfig,
    OutputFormat,
    PermissionMode,
    TaskStatus,
)
from ai_task_system.v4.core.command_builder import CommandBuilder
from ai_task_system.v4.core.executor import SubprocessExecutor
from ai_task_system.v4.core.router import TaskRouter
from ai_task_system.v4.core.benchmark_scores import BenchmarkScoreDB
from ai_task_system.v4.core.session_store import SessionStore, get_session_store
from ai_task_system.v4.core.retry import RetryExecutor, RetryConfig, retry_summary
from .core.benchmark import cmd_benchmark
from ai_task_system.v4.adapters.claude_adapter import ClaudeCodeAdapter
from ai_task_system.v4.adapters.codex_adapter import CodexAdapter
from ai_task_system.v4.adapters.codebuddy_adapter import CodeBuddyAdapter


# ───────────────────────────────────────────────────────────────
# 全局实例（延迟初始化）
# ───────────────────────────────────────────────────────────────

_registry: AdapterRegistry | None = None
_executor: SubprocessExecutor | None = None


def get_registry() -> AdapterRegistry:
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
        _registry.register(ClaudeCodeAdapter())
        _registry.register(CodexAdapter())
        _registry.register(CodeBuddyAdapter())
    return _registry


def get_executor() -> SubprocessExecutor:
    global _executor
    if _executor is None:
        _executor = SubprocessExecutor()
    return _executor


# ───────────────────────────────────────────────────────────────
# CLI 命令实现
# ───────────────────────────────────────────────────────────────

def _get_session_store() -> SessionStore:
    """获取全局 SessionStore 实例。"""
    return get_session_store()


_retry_executor: RetryExecutor | None = None


def _get_retry_executor(
    max_retries: int = 3,
    base_delay: float = 5.0,
) -> RetryExecutor:
    """获取全局 RetryExecutor 实例（单例）。"""
    global _retry_executor
    if _retry_executor is None:
        cfg = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            retry_on=(
                TaskStatus.FAILED,
                TaskStatus.NO_OUTPUT_TIMEOUT,
                TaskStatus.TIMEOUT,
                TaskStatus.AGENT_ERROR,
            ),
        )
        _retry_executor = RetryExecutor(
            SubprocessExecutor(),
            cfg,
            on_retry=lambda state, cfg: print(
                f"  ⏎ Retry attempt {state.attempt}/{cfg.max_retries} "
                f"(delay={cfg.compute_delay(state.attempt - 1):.1f}s)...",
                file=sys.stderr,
            ),
            on_give_up=lambda state: print(
                f"  ❌ Give up after {state.total_attempts} attempts: {state.give_up_reason}",
                file=sys.stderr,
            ),
        )
    return _retry_executor


def cmd_create(args: argparse.Namespace) -> int:
    """创建并执行新任务"""
    registry = get_registry()
    executor = get_executor()
    session_store = _get_session_store()

    # 构建执行配置
    config = ExecutionConfig(
        prompt=args.prompt,
        agent_type=AgentType(args.agent) if args.agent else AgentType.CLAUDE_CODE,
        permission_mode=PermissionMode.BYPASS if args.skip_permissions else PermissionMode.AUTO,
        timeout=args.timeout or 600,
        no_output_timeout=args.no_output_timeout or 120,
        output_format=OutputFormat.JSON if args.json else OutputFormat.TEXT,
        model=args.model,
        max_budget=args.max_budget,
        allowed_tools=args.allowed_tools.split(",") if args.allowed_tools else None,
        working_dir=args.working_dir,
        session_id=args.session,
        resume=args.resume,
        no_session_persistence=args.no_persist,
        bare=args.bare,
        extra_args=args.extra or [],
    )

    # 验证 agent 可用性
    adapter = registry.get(config.agent_type)
    if not adapter:
        print(f"ERROR: Unknown agent type: {args.agent}", file=sys.stderr)
        return 1

    available, msg = adapter.is_available()
    if not available:
        print(f"ERROR: {adapter.agent_type.value} is not available: {msg}", file=sys.stderr)
        return 1

    # 打印将要执行的命令（dry-run 模式）
    if args.dry_run:
        cmd = adapter.build_command(config)
        print("Would execute:", " ".join(cmd))
        return 0

    # 执行任务
    print(f"[{config.agent_type.value}] Creating task...")
    task = executor.execute(config, adapter)

    print(f"Task ID: {task.task_id}")
    print(f"Status:  {task.status.value}")

    # 等待结果（带进度显示）
    if args.wait:
        print(f"Executing (timeout={config.timeout}s, no_output_timeout={config.no_output_timeout}s)...")
        while task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            time.sleep(2)
            task = executor.get_task(task.task_id)
            if task:
                print(f"  Status: {task.status.value} ({task.duration():.1f}s)", end="\r")

        print()  # 换行
        result = task.result
        if result:
            if result.stdout:
                print("\n=== STDOUT ===")
                print(result.stdout)
            if result.stderr:
                print("\n=== STDERR ===")
                print(result.stderr)
            print(f"\nStatus:    {result.status.value}")
            print(f"Duration:  {result.duration_seconds:.1f}s")
            print(f"Exit Code: {result.return_code}")

            # 保存 session_id 到持久化存储
            if result.session_id:
                print(f"Session:   {result.session_id}")
                # 自动记录到 SessionStore
                if result.session_id not in [s.session_id for s in session_store.list_sessions(agent=config.agent_type.value)]:
                    session_store.create(
                        agent=config.agent_type.value,
                        session_id=result.session_id,
                        note=f"Task: {task.task_id[:8]}...",
                    )
                    print(f"✅ Session saved to session store.")
                print(f"\n# Resume with:")
                print(f"  python -m ai_task_system.v4.cli create \"...\" --session {result.session_id} --resume")
    else:
        print(f"Use 'python -m ai_task_system.v4.cli status {task.task_id}' to check progress")

    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    """重试失败的任务（带指数退避）"""
    retry_executor = _get_retry_executor(
        max_retries=args.max_retries,
        base_delay=args.delay,
    )
    registry = get_registry()
    session_store = _get_session_store()

    # 从 task_id 提取 agent（通过历史 create 记录或参数指定）
    agent_str = args.agent
    prompt = args.prompt

    config = ExecutionConfig(
        prompt=prompt,
        agent_type=AgentType(agent_str) if agent_str else AgentType.CLAUDE_CODE,
        permission_mode=PermissionMode.BYPASS if args.skip_permissions else PermissionMode.AUTO,
        timeout=args.timeout or 600,
        no_output_timeout=args.no_output_timeout or 120,
        allowed_tools=args.allowed_tools.split(",") if args.allowed_tools else None,
        working_dir=args.working_dir,
        session_id=args.session,
        resume=args.resume,
        bare=args.bare,
        extra_args=args.extra or [],
    )

    adapter = registry.get(config.agent_type)
    if not adapter:
        print(f"ERROR: Unknown agent type: {agent_str}", file=sys.stderr)
        return 1

    available, msg = adapter.is_available()
    if not available:
        print(f"ERROR: {adapter.agent_type.value} is not available: {msg}", file=sys.stderr)
        return 1

    bare_note = " (bare mode)" if args.bare else ""
    print(f"[{config.agent_type.value}] Retrying (max={args.max_retries}, delay={args.delay}s){bare_note}...")
    task = retry_executor.execute(config, adapter)

    result = task.result
    if result:
        if result.stdout:
            print("\n=== STDOUT ===")
            print(result.stdout)
        if result.stderr:
            print("\n=== STDERR ===")
            print(result.stderr)
        print(f"\nFinal status: {task.status.value}")
        print(f"Total attempts: {retry_executor.last_state.total_attempts}")

        # 从 RetryState history 打印重试摘要
        if retry_executor.last_state:
            print(f"\n{retry_summary(retry_executor.last_state)}")

        if task.status == TaskStatus.SUCCESS:
            print("✅ Task succeeded!")
            return 0
        else:
            print("❌ Task failed after retries.", file=sys.stderr)
            return 1
    else:
        print("❌ No result returned.", file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """列出所有任务"""
    executor = get_executor()
    tasks = executor.list_tasks()

    if not tasks:
        print("No tasks found.")
        return 0

    print(f"{'Task ID':<40} {'Status':<20} {'Duration':<10} {'Agent':<10}")
    print("-" * 82)
    for t in reversed(tasks):
        agent = t.config.agent_type.value if t.config else "?"
        dur = f"{t.duration():.1f}s" if t.duration() > 0 else "-"
        print(f"{t.task_id:<40} {t.status.value:<20} {dur:<10} {agent:<10}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """查看任务状态"""
    executor = get_executor()
    task = executor.get_task(args.task_id)

    if not task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    print(f"Task ID:    {task.task_id}")
    print(f"Status:     {task.status.value}")
    print(f"Agent:      {task.config.agent_type.value if task.config else '?'}")
    print(f"Created:    {task.created_at}")
    print(f"Started:    {task.started_at or '-'}")
    print(f"Finished:   {task.finished_at or '-'}")
    print(f"Duration:   {task.duration():.1f}s")

    result = task.result
    if result:
        if result.stdout:
            print(f"\n=== STDOUT ({len(result.stdout)} chars) ===")
            # 只显示最后 50 行
            lines = result.stdout.splitlines()
            if len(lines) > 50:
                print("... (truncated)")
                print("\n".join(lines[-50:]))
            else:
                print(result.stdout)
        if result.stderr:
            print(f"\n=== STDERR ===")
            print(result.stderr)
        print(f"\nExit Code: {result.return_code}")
        if result.session_id:
            print(f"Session:   {result.session_id}")
        if result.metadata.get("cmd"):
            print(f"Command:   {result.metadata['cmd']}")

    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """停止任务"""
    executor = get_executor()
    task = executor.get_task(args.task_id)
    if not task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1

    ok = executor.cancel_task(args.task_id)
    if ok:
        print(f"Task {args.task_id} marked as cancelled.")
    else:
        print(f"Failed to cancel task {args.task_id}", file=sys.stderr)
    return 0 if ok else 1


def cmd_agents(args: argparse.Namespace) -> int:
    """列出所有已注册的 Agent 及其状态"""
    registry = get_registry()

    print(f"{'Agent':<15} {'Available':<12} {'Capabilities'}")
    print("-" * 80)

    for adapter in registry.get_all():
        available, msg = adapter.is_available()
        status = "✅ Available" if available else f"❌ {msg}"
        caps = ", ".join(c.name for c in adapter.get_capabilities()[:5])
        if len(adapter.get_capabilities()) > 5:
            caps += f" ... (+{len(adapter.get_capabilities())-5})"
        print(f"{adapter.agent_type.value:<15} {status:<12} {caps}")

    best = registry.auto_select()
    if best:
        print(f"\nAuto-select would use: {best.agent_type.value}")

    return 0


# ─── 会话历史查看 ───────────────────────────────────────────────────────────────

def _load_v5_queue_task_status(task_id: str) -> str | None:
    """尝试从 V5 队列获取任务状态，返回状态字符串或 None（不可用）。"""
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from v5.queue import TaskQueue
        q = TaskQueue()
        task = q._get_task(task_id)
        if task:
            return task.status.value if hasattr(task.status, 'value') else str(task.status)
        return None
    except Exception:
        return None


def _cmd_session_log(session_id: str) -> int:
    """会话历史查看：显示会话详情 + 关联任务状态"""
    import datetime
    import sys as _sys

    store = _get_session_store()
    info = store.get(session_id)
    if info is None:
        print(f"Session not found: {session_id}", file=_sys.stderr)
        return 1

    # ── 基本信息 ──────────────────────────────────────────────────────────────
    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║  Session: {info.session_id}")
    print(f"╚══════════════════════════════════════════════════════════╝")
    print(f"  Agent:     {info.agent}")
    print(f"  Status:    {info.status}")
    created = datetime.datetime.fromtimestamp(info.created_at, tz=datetime.timezone.utc)
    print(f"  Created:   {created.strftime('%Y-%m-%d %H:%M UTC')}")
    last = datetime.datetime.fromtimestamp(info.last_used_at, tz=datetime.timezone.utc)
    print(f"  Last Used: {last.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Tasks:     {len(info.task_ids)}")
    if info.note:
        print(f"  Note:      {info.note}")

    # ── 任务历史 ────────────────────────────────────────────────────────────────
    if not info.task_ids:
        print(f"\n  (no tasks recorded)")
        return 0

    print(f"\n  ┌─ Task History ────────────────────────────────────────────┐")
    print(f"  │  {'Task ID':<40} {'Status':<12} {'Recorded At':<22} │")
    print(f"  │  {'-'*40} {'-'*10} {'-'*22} │")

    for i, task_id in enumerate(reversed(info.task_ids)):
        # 尝试从 V5 队列获取状态
        status = _load_v5_queue_task_status(task_id)
        status_str = status or "unknown"
        status_icon = {
            "done": "✅", "failed": "❌", "running": "⏳",
            "pending": "⏸", "dead": "💀", "dequeued": "⏭",
        }.get(status_str.lower(), "❓")
        rec_time = datetime.datetime.fromtimestamp(
            info.last_used_at, tz=datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M")
        bar = "─" * 50
        print(f"  │  {status_icon} {task_id:<38} {status_str:<10} │")
    print(f"  └{'─'*72}│")

    # ── 统计摘要 ────────────────────────────────────────────────────────────────
    print(f"\n  Summary: {len(info.task_ids)} task(s) recorded for this session.")
    return 0


def cmd_sessions(args: argparse.Namespace) -> int:
    """会话管理：list / get / delete / stats"""
    store = _get_session_store()

    if args.sub_cmd == "list":
        sessions = store.list_sessions(agent=args.agent, status=args.status, limit=args.limit)
        if not sessions:
            print("No sessions found.")
            return 0
        print(f"{'Agent':<12} {'Session ID':<40} {'Tasks':<6} {'Last Used':<22} Status")
        print("-" * 100)
        for s in sessions:
            import datetime
            dt = datetime.datetime.fromtimestamp(s.last_used_at, tz=datetime.timezone.utc)
            last = dt.strftime("%Y-%m-%d %H:%M UTC")
            note = f"  #{s.task_ids[0][:8]}..." if s.task_ids else ""
            print(f"{s.agent:<12} {s.session_id:<40} {len(s.task_ids):<6} {last:<22} {s.status}{note}")
        print(f"\nTotal: {len(sessions)} session(s)")
        return 0

    elif args.sub_cmd == "get":
        info = store.get(args.session_id)
        if info is None:
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 1
        import datetime
        created = datetime.datetime.fromtimestamp(info.created_at, tz=datetime.timezone.utc)
        last = datetime.datetime.fromtimestamp(info.last_used_at, tz=datetime.timezone.utc)
        print(f"agent:      {info.agent}")
        print(f"session:    {info.session_id}")
        print(f"status:     {info.status}")
        print(f"created:    {created.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"last_used:  {last.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"task_count: {len(info.task_ids)}")
        if info.task_ids:
            print(f"tasks:      {', '.join(info.task_ids)}")
        if info.note:
            print(f"note:       {info.note}")
        return 0

    elif args.sub_cmd == "delete":
        ok = store.delete(args.session_id)
        print(f"{'Deleted' if ok else 'Not found'}: {args.session_id}")
        return 0 if ok else 1

    elif args.sub_cmd == "archive":
        ok = store.archive(args.session_id)
        print(f"{'Archived' if ok else 'Not found'}: {args.session_id}")
        return 0 if ok else 1

    elif args.sub_cmd == "stats":
        print(json.dumps(store.stats(), indent=2, ensure_ascii=False))
        return 0

    elif args.sub_cmd == "clear-archived":
        n = store.clear_archived()
        print(f"Cleared {n} archived session(s).")
        return 0

    elif args.sub_cmd == "suggest":
        # 建议一个可用的 session 用于 resume
        if args.session_id:
            info = store.get(args.session_id)
            if info:
                print(f"Session: {info.session_id} ({info.agent})")
                print(f"  Tasks: {len(info.task_ids)}")
                print(f"  Status: {info.status}")
                return 0
            else:
                print(f"Session not found: {args.session_id}", file=sys.stderr)
                return 1
        agent = args.agent or "claude"
        info = store.find_by_agent(agent, status="active")
        if info is None:
            print(f"No active session found for {agent}.")
            print(f"\n# Create a new session:")
            print(f"  python -m ai_task_system.v4.cli create \"...\" -a {agent}")
            return 0
        print(f"Suggested session for {agent}:")
        print(f"  --session {info.session_id} --resume")
        print(f"\n  (from {len(info.task_ids)} previous tasks, last used: {info.note})")
        return 0

    elif args.sub_cmd == "log":
        return _cmd_session_log(args.session_id)

    elif args.sub_cmd == "export":
        data = store.export_session(args.session_id)
        if data is None:
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 1
        # Pretty-print with metadata
        output = json.dumps(data, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Exported to {args.output}")
        else:
            print(output)
        return 0

    elif args.sub_cmd == "import":
        if args.filepath == "-":
            data = json.load(sys.stdin)
        else:
            with open(args.filepath, encoding="utf-8") as f:
                data = json.load(f)
        session_id = data.get("session_id", "unknown")
        if args.force:
            # Delete existing first then import
            store.delete(session_id)
        ok = store.import_session(data)
        if ok:
            print(f"Imported session: {session_id}")
            return 0
        else:
            print(f"Failed: session {session_id} already exists. Use --force to overwrite.",
                  file=sys.stderr)
            return 1

    return 0


def cmd_route(args: argparse.Namespace) -> int:
    """路由决策：显示任务分类和推荐的 Agent"""
    registry = get_registry()

    # 尝试加载基准分数
    benchmark_db = None
    if not args.no_benchmark:
        benchmark_db = BenchmarkScoreDB.load()
        if not benchmark_db.has_data():
            benchmark_db = None

    router = TaskRouter(registry, benchmark_db=benchmark_db)

    # 用户指定了 agent
    if args.agent:
        agent_type = AgentType(args.agent)
        adapter = registry.get(agent_type)
        if not adapter:
            print(f"ERROR: Unknown agent: {args.agent}", file=sys.stderr)
            return 1
        available, msg = adapter.is_available()
        if not available:
            print(f"ERROR: {agent_type.value} is not available: {msg}", file=sys.stderr)
            return 1
        result = router.route_for_agents(args.prompt, [agent_type])
    else:
        result = router.route(args.prompt)

    # 打印详细解释
    if args.explain:
        print(router.explain_routing(args.prompt))
        return 0

    # 简洁输出
    task_type = router.classify(args.prompt)
    if result.agent:
        print(f"✅ Agent: {result.agent.agent_type.value}")
        print(f"   Task Type: {task_type.name}")
        print(f"   Confidence: {result.confidence:.0%}")
        print(f"   Reason: {result.reason}")
        if result.fallback_reason:
            print(f"   ⚠️  Fallback: {result.fallback_reason}")
        if result.config and result.config.timeout:
            print(f"   Recommended timeout: {result.config.timeout}s")

        # 构建命令预览
        cmd = result.agent.build_command(result.config)
        print(f"\n   Command preview: {' '.join(cmd[:4])} ...")
    else:
        print(f"❌ No route available: {result.reason}")

    return 0


def cmd_scores(args: argparse.Namespace) -> int:
    """基准分数管理：显示/加载/清除基准数据"""
    action = args.scores_action

    if action == "show":
        db = BenchmarkScoreDB.load(path=args.path)
        if not db.has_data():
            print("No benchmark scores available.")
            print("Run `benchmark` command first to collect scores.")
            return 0
        print(db.summary())
        return 0

    elif action == "load":
        import csv
        from pathlib import Path
        from ai_task_system.v4.core.benchmark import BenchmarkReport, TaskResult

        csv_path = Path(args.csv_path)
        if not csv_path.exists():
            print(f"ERROR: CSV file not found: {csv_path}", file=sys.stderr)
            return 1

        # 解析 CSV，构建 per-agent BenchmarkReport
        # CSV 格式: agent,category,task_id,task_name,status,duration,score,keyword_matches
        reports: dict[str, dict[str, list[float]]] = {}  # agent → category → [scores]

        with csv_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                agent = row["agent"]
                category = row["category"]
                score = float(row["score"])
                if agent not in reports:
                    reports[agent] = {}
                if category not in reports[agent]:
                    reports[agent][category] = []
                reports[agent][category].append(score)

        db = BenchmarkScoreDB.load(path=args.db_path)

        for agent, categories in reports.items():
            all_scores = [s for scores in categories.values() for s in scores]
            overall = sum(all_scores) / len(all_scores) if all_scores else 0.0
            cat_scores = {cat: sum(scores) / len(scores) if scores else 0.0
                          for cat, scores in categories.items()}
            from ai_task_system.v4.core.benchmark_scores import AgentScores
            import time
            db.agents[agent] = AgentScores(
                overall=overall,
                categories=cat_scores,
                last_updated=time.time(),
            )

        db.save(path=args.db_path)
        print(f"✅ Loaded benchmark scores for {len(reports)} agent(s)")
        print(f"   Saved to: {db.DEFAULT_PATH if not args.db_path else args.db_path}")
        return 0

    elif action == "clear":
        if not args.force:
            confirm = input("Clear all benchmark scores? [y/N] ")
            if confirm.lower() != "y":
                print("Cancelled.")
                return 0

        db = BenchmarkScoreDB.load(path=args.path)
        db.agents.clear()
        db.save(path=args.path)
        print("✅ Benchmark scores cleared.")
        return 0

    elif action == "compare":
        db = BenchmarkScoreDB.load(path=args.path)
        if not db.has_data():
            print("No benchmark scores available.")
            print("Run `benchmark` command first to collect scores.")
            return 0
        print(db.compare())
        return 0

    return 0


def cmd_show_cmd(args: argparse.Namespace) -> int:
    """显示将要执行的命令（不实际执行）"""
    registry = get_registry()

    config = ExecutionConfig(
        prompt=args.prompt,
        agent_type=AgentType(args.agent) if args.agent else AgentType.CLAUDE_CODE,
        permission_mode=PermissionMode.BYPASS if args.skip_permissions else PermissionMode.AUTO,
        timeout=args.timeout or 600,
        no_output_timeout=args.no_output_timeout or 120,
        model=args.model,
        max_budget=args.max_budget,
        allowed_tools=args.allowed_tools.split(",") if args.allowed_tools else None,
        working_dir=args.working_dir,
        session_id=args.session,
        resume=args.resume,
        no_session_persistence=args.no_persist,
        bare=args.bare,
        extra_args=args.extra or [],
    )

    adapter = registry.get(config.agent_type)
    if not adapter:
        print(f"ERROR: Unknown agent: {args.agent}", file=sys.stderr)
        return 1

    available, msg = adapter.is_available()
    print(f"# Agent: {adapter.agent_type.value} ({'available' if available else msg})")
    if args.bare:
        print(f"# Bare mode: enabled (skip CLAUDE.md discovery)")
    print()

    cmd = adapter.build_command(config)
    print(" ".join(cmd))
    return 0


# ───────────────────────────────────────────────────────────────
# CLI 主入口
# ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ai_task_system.v4.cli",
        description="AI Task System V4 - Multi-Agent CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── sessions ─────────────────────────────────────────────────
    sess = sub.add_parser("sessions", help="Session management")
    sess_sub = sess.add_subparsers(dest="sub_cmd", required=True)

    sess_list = sess_sub.add_parser("list", help="List saved sessions")
    sess_list.add_argument("--agent", choices=["claude", "codex", "codebuddy"])
    sess_list.add_argument("--status", default="active", choices=["active", "archived"])
    sess_list.add_argument("--limit", type=int, default=50)

    for cmd_name in ["get", "delete", "archive"]:
        p = sess_sub.add_parser(cmd_name, help=f"{cmd_name.capitalize()} a session")
        p.add_argument("session_id", help="Session ID")

    p_stats = sess_sub.add_parser("stats", help="Show session statistics")
    p_clear = sess_sub.add_parser("clear-archived", help="Clear all archived sessions")

    p_suggest = sess_sub.add_parser("suggest", help="Suggest a session for resume")
    p_suggest.add_argument("session_id", nargs="?", help="Session ID (optional)")
    p_suggest.add_argument("--agent", default="claude", choices=["claude", "codex", "codebuddy"])

    p_log = sess_sub.add_parser("log", help="Show session history and task log")
    p_log.add_argument("session_id", help="Session ID")

    p_export = sess_sub.add_parser("export", help="Export a session to JSON file")
    p_export.add_argument("session_id", help="Session ID to export")
    p_export.add_argument("--output", "-o", help="Output file path (default: stdout)")

    p_import = sess_sub.add_parser("import", help="Import a session from JSON file")
    p_import.add_argument("filepath", help="Path to the JSON file (or - for stdin)")
    p_import.add_argument("--force", action="store_true",
                          help="Overwrite if session_id already exists")

    # ── agents ──────────────────────────────────────────────────
    agents = sub.add_parser("agents", help="List all registered agents")

    # ── show-cmd ────────────────────────────────────────────────
    show = sub.add_parser("show-cmd", help="Show command without executing")
    show.add_argument("prompt", help="Task prompt")
    show.add_argument("--agent", "-a", default="claude", choices=["claude", "codex", "codebuddy"])
    show.add_argument("--skip-permissions", "-y", action="store_true")
    show.add_argument("--timeout", "-t", type=int, default=600)
    show.add_argument("--no-output-timeout", type=int, default=120)
    show.add_argument("--model", "-m")
    show.add_argument("--max-budget")
    show.add_argument("--allowed-tools")
    show.add_argument("--working-dir", "-C")
    show.add_argument("--session")
    show.add_argument("--resume", "-r", action="store_true")
    show.add_argument("--no-persist", action="store_true")
    show.add_argument("--bare", action="store_true",
                      help="Minimal mode: skip CLAUDE.md discovery (Claude Code only)")
    show.add_argument("--extra", nargs="*")

    # ── create ──────────────────────────────────────────────────
    create = sub.add_parser("create", help="Create and execute a new task")
    create.add_argument("prompt", help="Task prompt")
    create.add_argument("--agent", "-a", default="claude", choices=["claude", "codex", "codebuddy"])
    create.add_argument("--skip-permissions", "-y", action="store_true")
    create.add_argument("--timeout", "-t", type=int)
    create.add_argument("--no-output-timeout", type=int)
    create.add_argument("--json", "-j", action="store_true", help="JSON output format")
    create.add_argument("--model", "-m")
    create.add_argument("--max-budget")
    create.add_argument("--allowed-tools")
    create.add_argument("--working-dir", "-C")
    create.add_argument("--session")
    create.add_argument("--resume", "-r", action="store_true")
    create.add_argument("--no-persist", action="store_true")
    create.add_argument("--bare", action="store_true",
                        help="Minimal mode: skip CLAUDE.md discovery (Claude Code only)")
    create.add_argument("--extra", nargs="*")
    create.add_argument("--dry-run", action="store_true")
    create.add_argument("--wait", "-w", action="store_true", help="Wait for result")

    # ── list ────────────────────────────────────────────────────
    list_parser = sub.add_parser("list", help="List all tasks")

    # ── status ─────────────────────────────────────────────────
    status = sub.add_parser("status", help="Show task status")
    status.add_argument("task_id", help="Task ID")

    # ── stop ───────────────────────────────────────────────────
    stop = sub.add_parser("stop", help="Stop a running task")
    stop.add_argument("task_id", help="Task ID")

    # ── route ───────────────────────────────────────────────────
    route_p = sub.add_parser("route", help="Show routing decision for a task")
    route_p.add_argument("prompt", help="Task prompt to classify and route")
    route_p.add_argument("--agent", "-a", choices=["claude", "codex", "codebuddy"],
                         help="Force specific agent (skip routing)")
    route_p.add_argument("--explain", "-e", action="store_true",
                         help="Show detailed routing explanation")
    route_p.add_argument("--no-benchmark", action="store_true",
                         help="Ignore benchmark data (use keyword-only routing)")

    # ── retry ──────────────────────────────────────────────────
    retry_p = sub.add_parser("retry", help="Retry a failed task with exponential backoff")
    retry_p.add_argument("prompt", help="Task prompt to retry")
    retry_p.add_argument("--agent", "-a", default="claude",
                         choices=["claude", "codex", "codebuddy"],
                         help="Agent to use (default: claude)")
    retry_p.add_argument("--skip-permissions", "-y", action="store_true",
                         help="Skip permission prompts")
    retry_p.add_argument("--timeout", "-t", type=int, default=600,
                         help="Timeout per attempt (default: 600s)")
    retry_p.add_argument("--no-output-timeout", type=int, default=120,
                         help="No-output timeout (default: 120s)")
    retry_p.add_argument("--max-retries", "-n", type=int, default=3,
                         help="Max retry attempts (default: 3)")
    retry_p.add_argument("--delay", "-d", type=float, default=5.0,
                         help="Initial backoff delay in seconds (default: 5.0)")
    retry_p.add_argument("--allowed-tools")
    retry_p.add_argument("--working-dir", "-C")
    retry_p.add_argument("--session")
    retry_p.add_argument("--resume", "-r", action="store_true")
    retry_p.add_argument("--bare", action="store_true",
                         help="Minimal mode: skip CLAUDE.md discovery (Claude Code only)")
    retry_p.add_argument("--extra", nargs="*")

    # ── benchmark ──────────────────────────────────────────────
    bench_p = sub.add_parser("benchmark", help="Run agent capability benchmark")
    bench_p.add_argument("--agent", "-a", choices=["claude", "codex", "codebuddy"],
                         help="Benchmark specific agent (default: all agents)")
    bench_p.add_argument("--tasks", "-t", choices=["coding", "refactoring", "debugging",
                         "architecture", "learning", "writing", "shell", "research"],
                         help="Filter by task category")
    bench_p.add_argument("--report", "-o", metavar="PATH",
                         help="Export CSV report to path")
    bench_p.add_argument("--verbose", "-v", action="store_true",
                         help="Show per-task progress")

    # ── scores ─────────────────────────────────────────────────
    scores_p = sub.add_parser("scores", help="Manage benchmark score database")
    scores_sub = scores_p.add_subparsers(dest="scores_action", required=True)

    # scores show
    show_p = scores_sub.add_parser("show", help="Show all benchmark scores")
    show_p.add_argument("--path", help="Custom JSON file path")

    # scores load
    load_p = scores_sub.add_parser("load", help="Load benchmark scores from a CSV report")
    load_p.add_argument("csv_path", help="Path to CSV report (from benchmark --report)")
    load_p.add_argument("--db-path", help="Target JSON DB path (default: ~/.ai_task_system/benchmark_scores.json)")

    # scores clear
    clear_p = scores_sub.add_parser("clear", help="Clear all benchmark scores")
    clear_p.add_argument("--path", help="Custom JSON file path")
    clear_p.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    # scores compare
    compare_p = scores_sub.add_parser("compare", help="Compare agents side-by-side with rankings")
    compare_p.add_argument("--path", help="Custom JSON file path")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "agents": cmd_agents,
        "show-cmd": cmd_show_cmd,
        "create": cmd_create,
        "list": cmd_list,
        "status": cmd_status,
        "stop": cmd_stop,
        "route": cmd_route,
        "sessions": cmd_sessions,
        "retry": cmd_retry,
        "benchmark": cmd_benchmark,
        "scores": cmd_scores,
    }

    fn = dispatch.get(args.command)
    if fn:
        try:
            sys.exit(fn(args))
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            sys.exit(130)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

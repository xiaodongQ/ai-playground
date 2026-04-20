#!/usr/bin/env python3
"""
V4 AI Task System — Interactive REPL Mode

An interactive shell for the AI Task System with:
- Direct prompt input (no 'create' prefix needed)
- Command shortcuts: agents, route, sessions, benchmark, quit
- Arrow key history navigation
- Auto-routing with confirmation
- Session resumption

Usage:
    python -m ai_task_system.v4.repl
    python -m ai_task_system.v4 --repl
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# ── 路径设置（同 cli.py）─────────────────────────────────────
if __name__ == "__main__" and "ai_task_system" not in sys.modules:
    _script_dir = Path(__file__).resolve().parent
    _pkg_root = _script_dir.parent
    _parent = _pkg_root.parent
    if str(_parent) not in sys.path:
        sys.path.insert(0, str(_parent))
    import ai_task_system.v4
    import ai_task_system.v4.core
    import ai_task_system.v4.adapters

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
from ai_task_system.v4.core.session_store import get_session_store
from ai_task_system.v4.adapters.claude_adapter import ClaudeCodeAdapter
from ai_task_system.v4.adapters.codex_adapter import CodexAdapter
from ai_task_system.v4.adapters.codebuddy_adapter import CodeBuddyAdapter


# ───────────────────────────────────────────────────────────────
# 全局 REPL 状态
# ───────────────────────────────────────────────────────────────

HISTORY_FILE = Path.home() / ".ai_task_system" / "repl_history"
_PROMPT = "ai-task> "
_CONTINUATION_PROMPT = "....> "


class REPLState:
    """REPL 会话状态"""

    def __init__(self):
        self.registry: AdapterRegistry = AdapterRegistry()
        self.registry.register(ClaudeCodeAdapter())
        self.registry.register(CodexAdapter())
        self.registry.register(CodeBuddyAdapter())

        self.router: TaskRouter = TaskRouter(self.registry)
        self.executor: SubprocessExecutor = SubprocessExecutor()
        self.session_store = get_session_store()

        self.default_agent: AgentType = AgentType.CLAUDE_CODE
        self.skip_permissions: bool = False
        self.default_timeout: int = 600
        self.default_no_output_timeout: int = 120
        self.current_session_id: Optional[str] = None
        self.verbose: bool = False

    def route_prompt(self, prompt: str) -> tuple[AgentType, str]:
        """对 prompt 进行路由决策，返回 (agent, reason)"""
        result = self.router.route(prompt)
        if result.agent:
            return result.agent.agent_type, result.reason or "routed"
        # 回退到默认
        return self.default_agent, "using default (no route)"


# ───────────────────────────────────────────────────────────────
# REPL 核心
# ───────────────────────────────────────────────────────────────

def _setup_readline() -> None:
    """配置 readline（历史记录 + 补全）"""
    import atexit
    try:
        import readline
    except ImportError:
        return

    # 确保历史文件目录存在
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 加载历史
    if HISTORY_FILE.exists():
        try:
            readline.read_history_file(str(HISTORY_FILE))
        except Exception:
            pass

    # 保存历史（退出时）
    atexit.register(lambda: _save_history(readline))

    # 补全
    readline.parse_and_bind("tab: complete")
    readline.set_completer(_completer)


def _save_history(readline) -> None:
    try:
        readline.write_history_file(str(HISTORY_FILE))
    except Exception:
        pass


# 命令补全
_REPL_COMMANDS = [
    "agents", "route", "sessions", "benchmark", "scores",
    "status", "list", "stop", "run", "quit", "exit", "help",
    "set", "unset", "session", "clear",
]


def _completer(text: str, state: int) -> Optional[str]:
    """简单的命令补全"""
    try:
        import readline
    except ImportError:
        return None

    line = readline.get_line_buffer()
    words = line.split()

    if not words or (len(words) == 1 and not line.endswith(" ")):
        # 补全命令
        matches = [c for c in _REPL_COMMANDS if c.startswith(text)]
        if state < len(matches):
            return matches[state]
    elif len(words) == 1 and line.endswith(" "):
        # 补全命令（带尾随空格）
        matches = [c for c in _REPL_COMMANDS if c.startswith(text)]
        if state < len(matches):
            return matches[state]
    elif len(words) >= 2 and words[0] in ("set", "unset"):
        # set/unset 的参数补全
        if words[0] == "set" and words[-1] == "--agent":
            agents = ["claude", "codex", "codebuddy"]
            matches = [a for a in agents if a.startswith(text)]
            if state < len(matches):
                return matches[state]
        if words[0] == "set" and words[-1] == "--timeout":
            timeouts = ["60", "120", "300", "600", "900"]
            matches = [t for t in timeouts if t.startswith(text)]
            if state < len(matches):
                return matches[state]

    return None


def _read_line(prompt: str, state: REPLState) -> Optional[str]:
    """读取一行（支持历史），返回 None 表示 EOF"""
    try:
        import readline
    except ImportError:
        return input(prompt)

    try:
        line = input(prompt)
        return line
    except (EOFError, KeyboardInterrupt):
        return None


def _build_execution_config(state: REPLState, prompt: str, **overrides) -> ExecutionConfig:
    """从 REPL 状态构建 ExecutionConfig"""
    kwargs = dict(
        prompt=prompt,
        agent_type=state.default_agent,
        permission_mode=PermissionMode.BYPASS if state.skip_permissions else PermissionMode.AUTO,
        timeout=state.default_timeout,
        no_output_timeout=state.default_no_output_timeout,
        output_format=OutputFormat.TEXT,
        session_id=state.current_session_id,
        resume=bool(state.current_session_id),
    )
    kwargs.update(overrides)
    return ExecutionConfig(**kwargs)


def _run_task(state: REPLState, prompt: str, dry_run: bool = False,
              explicit_agent: Optional[str] = None,
              wait: bool = True) -> int:
    """执行一个任务，返回 exit code"""
    # 确定 agent
    if explicit_agent:
        agent_type = AgentType(explicit_agent)
        reason = f"explicit: {explicit_agent}"
    else:
        agent_type, reason = state.route_prompt(prompt)

    # 获取 adapter
    adapter = state.registry.get(agent_type)
    if not adapter:
        print(f"❌ Unknown agent: {agent_type}", file=sys.stderr)
        return 1

    available, msg = adapter.is_available()
    if not available:
        print(f"❌ {agent_type.value} not available: {msg}", file=sys.stderr)
        return 1

    config = _build_execution_config(state, prompt)
    config.agent_type = agent_type

    print(f"🤖 Agent: {agent_type.value} ({reason})")
    print(f"⏱️  Timeout: {config.timeout}s | No-output: {config.no_output_timeout}s")
    if config.session_id:
        print(f"🔄 Session: {config.session_id[:16]}...")
    print()

    if dry_run:
        cmd = adapter.build_command(config)
        print("Would execute:", " ".join(cmd))
        return 0

    print(f"▶ Executing...")
    task = state.executor.execute(config, adapter)

    if not wait:
        print(f"Task ID: {task.task_id}")
        print(f"Use `status {task.task_id}` to check progress")
        return 0

    # 等待结果
    import time
    dots = 0
    while task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
        time.sleep(2)
        task = state.executor.get_task(task.task_id)
        if task:
            dots += 1
            suffix = "." * (dots % 4)
            print(f"\r  Running{suffix} ({task.duration():.0f}s)", end="", flush=True)

    print()  # 换行
    result = task.result

    if result:
        if result.stdout:
            print("\n=== STDOUT ===")
            print(result.stdout[:2000])
            if len(result.stdout) > 2000:
                print(f"\n... ({len(result.stdout) - 2000} more characters)")

        if result.stderr:
            print("\n=== STDERR ===")
            print(result.stderr[:500])

        print(f"\n✅ Done! | Status: {result.status.value} | Duration: {result.duration_seconds:.1f}s | Exit: {result.return_code}")

        if result.session_id:
            state.current_session_id = result.session_id
            print(f"🔑 Session: {result.session_id}")

        return 0 if result.return_code == 0 else 1
    else:
        print(f"\n❌ Task failed: {task.status.value}")
        return 1


# ───────────────────────────────────────────────────────────────
# REPL 命令处理器
# ───────────────────────────────────────────────────────────────

def _cmd_agents(state: REPLState, args: list[str]) -> int:
    """列出所有 Agent 及其状态"""
    print("\n" + "=" * 54)
    print(f"  {'Agent':<14} {'Available':<12} {'Status'}")
    print("=" * 54)
    for name in ["claude", "codex", "codebuddy"]:
        try:
            agent_type = AgentType(name)
            adapter = state.registry.get(agent_type)
            if adapter:
                available, msg = adapter.is_available()
                status = "✅ Available" if available else f"❌ {msg or 'not found'}"
                default_mark = " ← default" if agent_type == state.default_agent else ""
                print(f"  {name:<14} {status:<45}{default_mark}")
        except Exception as e:
            print(f"  {name:<14} ❌ Error: {e}")
    print("=" * 54)

    if state.current_session_id:
        print(f"\n🔑 Current session: {state.current_session_id[:20]}...")
    print(f"⚙️  Defaults: agent={state.default_agent.value}, "
          f"timeout={state.default_timeout}s, "
          f"skip_perm={state.skip_permissions}")
    return 0


def _cmd_route(state: REPLState, args: list[str]) -> int:
    """路由一个 prompt（不执行）"""
    if not args:
        print("Usage: route <prompt>", file=sys.stderr)
        return 1

    prompt = " ".join(args)
    result = state.router.route(prompt)

    print(f"\n📋 Classification: {state.router.classify(prompt).name}")
    if result.agent:
        print(f"✅ Agent: {result.agent.agent_type.value}")
        print(f"   Confidence: {result.confidence:.0%}")
        print(f"   Reason: {result.reason}")
        if result.config and result.config.timeout:
            print(f"   Recommended timeout: {result.config.timeout}s")
    else:
        print(f"❌ No route: {result.reason}")

    return 0


def _cmd_sessions(state: REPLState, args: list[str]) -> int:
    """显示会话列表"""
    sessions = state.session_store.list_sessions(status="active")
    if not sessions:
        print("No active sessions.")
        return 0

    print(f"\n{'Session ID':<22} {'Agent':<10} {'Tasks':<6} {'Last Used'}")
    print("-" * 62)
    from datetime import datetime
    now = datetime.now()
    for s in sessions[:10]:
        last = datetime.fromtimestamp(s.last_used_at)
        age = (now - last).total_seconds()
        age_str = f"{age:.0f}s ago" if age < 60 else f"{age/60:.0f}m ago" if age < 3600 else f"{age/3600:.0f}h ago"
        print(f"{s.session_id:<22} {s.agent:<10} {len(s.task_ids):<6} {age_str}")
    print()
    return 0


def _cmd_set(state: REPLState, args: list[str]) -> int:
    """设置 REPL 选项: set --agent claude --timeout 300"""
    i = 0
    while i < len(args):
        if args[i] == "--agent" and i + 1 < len(args):
            state.default_agent = AgentType(args[i + 1])
            print(f"✅ Default agent: {state.default_agent.value}")
            i += 2
        elif args[i] == "--timeout" and i + 1 < len(args):
            state.default_timeout = int(args[i + 1])
            print(f"✅ Default timeout: {state.default_timeout}s")
            i += 2
        elif args[i] == "--no-output-timeout" and i + 1 < len(args):
            state.default_no_output_timeout = int(args[i + 1])
            print(f"✅ Default no-output timeout: {state.default_no_output_timeout}s")
            i += 2
        elif args[i] == "-y" or args[i] == "--skip-permissions":
            state.skip_permissions = True
            print(f"✅ Skip permissions: enabled")
            i += 1
        elif args[i] == "--session" and i + 1 < len(args):
            state.current_session_id = args[i + 1]
            print(f"🔑 Session: {state.current_session_id[:20]}...")
            i += 2
        elif args[i] in ("-y", "--skip-permissions"):
            state.skip_permissions = not state.skip_permissions
            print(f"⚠️  Skip permissions: {state.skip_permissions}")
            i += 1
        else:
            print(f"Unknown option: {args[i]}", file=sys.stderr)
            return 1
    return 0


def _cmd_unset(state: REPLState, args: list[str]) -> int:
    """重置 REPL 选项"""
    for arg in args:
        if arg == "--agent":
            state.default_agent = AgentType.CLAUDE_CODE
            print("✅ Default agent reset to claude")
        elif arg == "--session":
            state.current_session_id = None
            print("✅ Session cleared")
        elif arg == "--skip-permissions":
            state.skip_permissions = False
            print("✅ Skip permissions disabled")
        else:
            print(f"Unknown option to unset: {arg}", file=sys.stderr)
            return 1
    return 0


def _cmd_session(state: REPLState, args: list[str]) -> int:
    """session <session_id> — 设置当前会话"""
    if not args:
        if state.current_session_id:
            print(f"Current session: {state.current_session_id}")
        else:
            print("No active session.")
        return 0

    session_id = args[0]
    # 验证 session 是否存在
    info = state.session_store.get(session_id)
    if not info:
        print(f"⚠️  Session not found in store: {session_id}", file=sys.stderr)
        print("   It will be used anyway (may be new).")

    state.current_session_id = session_id
    print(f"🔑 Session set: {session_id[:20]}...")
    return 0


def _cmd_benchmark(state: REPLState, args: list[str]) -> int:
    """快速基准测试（调用 CLI benchmark）"""
    print("⚠️  Benchmark is long-running. Use the CLI for full control:")
    print("   python -m ai_task_system.v4.cli benchmark --agent claude")
    return 0


def _cmd_status(state: REPLState, args: list[str]) -> int:
    """查看任务状态"""
    if not args:
        print("Usage: status <task-id>", file=sys.stderr)
        return 1

    task = state.executor.get_task(args[0])
    if not task:
        print(f"Task not found: {args[0]}", file=sys.stderr)
        return 1

    print(f"\nTask ID:    {task.task_id}")
    print(f"Status:     {task.status.value}")
    print(f"Duration:   {task.duration():.1f}s")
    if task.result:
        print(f"Exit Code:  {task.result.return_code}")
        print(f"Session:    {task.result.session_id or 'N/A'}")
    return 0


def _cmd_list(state: REPLState, args: list[str]) -> int:
    """列出最近任务"""
    print("(Use the CLI `list` command for full task list)")
    # 简单列出 executor 中的任务
    # executor 内部不一定有 list 接口，这里做个占位
    print(f"Default agent: {state.default_agent.value}")
    return 0


# ───────────────────────────────────────────────────────────────
# REPL 主循环
# ───────────────────────────────────────────────────────────────

def _print_banner(state: REPLState) -> None:
    banner = f"""
╔═══════════════════════════════════════════════════════════╗
║         AI Task System V4 — Interactive REPL             ║
║                                                           ║
║  Commands:                                                ║
║    <prompt>          — Execute task (auto-route)          ║
║    run <prompt>      — Same as above (explicit)           ║
║    agents            — List all agents                   ║
║    route <prompt>    — Show routing decision              ║
║    sessions          — List active sessions              ║
║    session <id>      — Set current session                ║
║    status <task-id>  — Show task status                  ║
║    set --agent claude — Set default agent                 ║
║    set --timeout 300 — Set default timeout                ║
║    set -y            — Enable skip-permissions            ║
║    unset --session   — Clear current session              ║
║    clear             — Clear screen                       ║
║    quit / exit       — Exit REPL                         ║
║                                                           ║
║  Tips:                                                    ║
║    • Multi-line input: end line with \\                    ║
║    • Arrow ↑↓ for history                                 ║
║    • Tab for command completion                            ║
║    • Ctrl+C to interrupt running task                     ║
╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)

    # 显示 Agent 状态
    _cmd_agents(state, [])


def _parse_line(line: str) -> tuple[Optional[str], list[str]]:
    """
    解析 REPL 输入行。
    返回 (command_or_None, args)。

    command_or_None = None 表示这是直接 prompt（需要执行的任务）。
    """
    line = line.strip()
    if not line:
        return None, []

    # 显式命令
    if line.startswith("run ") or line.startswith("exec "):
        return ("run", [line[4:].strip()])

    words = line.split()
    cmd = words[0].lower()
    args = words[1:]

    if cmd in ("quit", "q"):
        return ("quit", [])
    if cmd == "exit":
        return ("exit", [])
    if cmd == "help":
        return ("help", [])
    if cmd == "agents":
        return ("agents", args)
    if cmd == "route":
        return ("route", args)
    if cmd == "sessions":
        return ("sessions", args)
    if cmd == "benchmark":
        return ("benchmark", args)
    if cmd == "status":
        return ("status", args)
    if cmd == "list":
        return ("list", args)
    if cmd == "set":
        return ("set", args)
    if cmd == "unset":
        return ("unset", args)
    if cmd == "session":
        return ("session", args)
    if cmd == "clear":
        return ("clear", [])

    # 直接 prompt（没有已知命令前缀）
    return (None, [line])


def _read_multiline(state: REPLState) -> Optional[str]:
    r"""读取多行输入（以 \ 续行）"""
    import readline
    try:
        line = input(_PROMPT)
    except (EOFError, KeyboardInterrupt):
        return None

    if line.endswith("\\"):
        # 继续输入
        lines = [line[:-1]]
        while True:
            try:
                cont = input(_CONTINUATION_PROMPT)
            except (EOFError, KeyboardInterrupt):
                return None
            if cont.endswith("\\"):
                lines.append(cont[:-1])
            else:
                lines.append(cont)
                break
        return " ".join(lines)
    return line


def _main_loop(state: REPLState) -> None:
    """主 REPL 循环"""
    _setup_readline()

    while True:
        try:
            line = _read_multiline(state)
        except KeyboardInterrupt:
            print("^C")
            continue
        except EOFError:
            print("exit")
            break

        if line is None:
            break

        line = line.strip()
        if not line:
            continue

        cmd, args = _parse_line(line)

        if cmd == "quit" or cmd == "exit":
            print("Goodbye! 👋")
            break

        if cmd == "help":
            _print_banner(state)
            continue

        if cmd == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue

        if cmd == "agents":
            _cmd_agents(state, args)
            continue

        if cmd == "route":
            _cmd_route(state, args)
            continue

        if cmd == "sessions":
            _cmd_sessions(state, args)
            continue

        if cmd == "benchmark":
            _cmd_benchmark(state, args)
            continue

        if cmd == "status":
            _cmd_status(state, args)
            continue

        if cmd == "list":
            _cmd_list(state, args)
            continue

        if cmd == "set":
            _cmd_set(state, args)
            continue

        if cmd == "unset":
            _cmd_unset(state, args)
            continue

        if cmd == "session":
            _cmd_session(state, args)
            continue

        if cmd == "run":
            prompt = args[0] if args else ""
            if not prompt:
                print("Usage: run <prompt>", file=sys.stderr)
                continue
            _run_task(state, prompt, wait=True)
            continue

        # 直接 prompt（默认行为 = 自动路由执行）
        _run_task(state, line, wait=True)


# ───────────────────────────────────────────────────────────────
# 入口
# ───────────────────────────────────────────────────────────────

def run_repl() -> None:
    """启动 REPL"""
    print("Starting AI Task System V4 REPL...")
    state = REPLState()
    _print_banner(state)
    _main_loop(state)


if __name__ == "__main__":
    run_repl()

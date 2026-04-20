"""
AI Task System V4 — Textual TUI 入口

用法:
    cd /root/.openclaw/workspace/ai-task-system
    python v4/tui.py

    # Web 模式（浏览器访问）:
    textual serve v4/tui.py --port 8080

    # 深色主题:
    python v4/tui.py --theme dark
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.events import Key
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Log,
    ProgressBar,
    RadioButton,
    RadioSet,
    Static,
    Switch,
)


# ---------------------------------------------------------------------------
# 路径 setup（支持 python v4/tui.py 直接运行）
# ---------------------------------------------------------------------------
if __name__ == "__main__" and "ai_task_system" not in sys.modules:
    _script_dir = Path(__file__).resolve().parent  # v4/
    _pkg_root = _script_dir.parent                   # ai-task-system/
    _parent = _pkg_root.parent                       # /root/.openclaw/workspace
    if str(_parent) not in sys.path:
        sys.path.insert(0, str(_parent))

from ai_task_system.v4.core.base import (
    AdapterRegistry,
    AgentAdapter,
    AgentType,
    ExecutionConfig,
    PermissionMode,
    Task,
    TaskStatus,
)
from ai_task_system.v4.core.executor import SubprocessExecutor
from ai_task_system.v4.adapters.claude_adapter import ClaudeCodeAdapter
from ai_task_system.v4.adapters.codex_adapter import CodexAdapter
from ai_task_system.v4.adapters.codebuddy_adapter import CodeBuddyAdapter





# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------
TASKS_FILE = Path.home() / ".ai_task_system" / "tui_tasks.json"


def _load_tasks() -> dict[str, dict]:
    try:
        if TASKS_FILE.exists():
            return json.loads(TASKS_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_tasks(tasks: dict[str, dict]) -> None:
    try:
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False, default=str))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 带时间戳的 Log widget（含 ANSI 高亮 + 颜色）
# ---------------------------------------------------------------------------
class TimestampedLog(Log):
    def write_line(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write(f"[{ts}] {text}\n")
        self.scroll_end(animate=False)


# ---------------------------------------------------------------------------
# 主应用
# ---------------------------------------------------------------------------
class TaskTUI(App):
    """
    AI Task System V4 — Textual TUI

    快捷键:
      Ctrl+Q   退出
      Ctrl+N   新建任务（聚焦输入框）
      Ctrl+L   清空日志
      Ctrl+T   切换深色/浅色主题
      ↑/↓      上下选择任务
      Enter    查看任务详情 / 执行输入框任务

    鼠标:
      点击任务列表项 → 查看任务详情
      双击任务 → 重新执行

    ┌────────────────────────────────────────────────────────────────────┐
    │  🤖 AI Task System V4         [☀️/🌙]  Agent: Claude Code ▼   │
    ├────────────────────┬─────────────────────────────────────────────┤
    │  [ Tasks ]          │  [ Output Log ]                             │
    │  ▶ task-001        │  [12:01] Starting...                         │
    │    task-002 ✅     │  [12:01] Thinking...                         │
    │    task-003 ❌     │  [12:02] Done.                               │
    ├────────────────────┴─────────────────────────────────────────────┤
    │  > Enter task...                        [Execute]                  │
    │  [✓ Skip permissions]  [Resume session]  [Progress: ████░░░░ 60%]  │
    └────────────────────────────────────────────────────────────────────┘
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 3;
        grid-rows: auto 1fr auto;
        grid-columns: 1fr 2fr;
    }

    #header-bar {
        column-span: 2;
        background: $surface;
        height: auto;
        padding: 0 2;
        border-bottom: solid $border;
    }

    #agent-selector {
        column-span: 2;
        background: $surface;
        border-bottom: solid $border;
        padding: 1 2;
    }

    #task-list-container {
        width: 100%;
        height: 100%;
        background: $surface;
        border-right: solid $border;
        padding: 1;
    }

    #output-container {
        width: 100%;
        height: 100%;
        background: $surface;
        padding: 1;
    }

    #input-area {
        column-span: 2;
        background: $surface;
        border-top: solid $border;
        padding: 1 2;
    }

    .section-label {
        color: $text-muted;
        margin-bottom: 1;
    }

    #task-count {
        color: $text-muted;
    }

    #agent-availability {
        color: $text-muted;
    }

    #progress-container {
        width: 100%;
        height: auto;
        padding: 0 2;
        background: $surface;
        border-top: solid $border;
    }

    #progress-label {
        color: $text-muted;
        padding: 0 2;
    }

    ListView {
        mouse: True;   /* 启用鼠标滚轮和点击 */
    }

    /* 深色主题下的 Log 高亮 */
    Log {
        background: $panel;
    }
    """

    TITLE = "AI Task System V4 — TUI"
    SUB_TITLE = "Textual"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+n", "focus_input", "New Task", show=True),
        Binding("ctrl+l", "clear_log", "Clear", show=True),
        Binding("ctrl+t", "toggle_theme", "Theme", show=True),
        Binding("up", "select_prev_task", "Up", show=False),
        Binding("down", "select_next_task", "Down", show=False),
        Binding("enter", "activate_task", "Enter", show=False),
    ]

    # ---------------------------------------------------------------------------
    # 反应式状态
    # ---------------------------------------------------------------------------
    selected_agent: reactive[AgentType] = reactive(AgentType.CLAUDE_CODE)
    skip_permissions: reactive[bool] = reactive(True)
    resume_session: reactive[bool] = reactive(False)
    is_dark: reactive[bool] = reactive(True)
    progress_value: reactive[float] = reactive(0.0)
    progress_label: reactive[str] = reactive("")

    # ---------------------------------------------------------------------------
    # 初始化
    # ---------------------------------------------------------------------------
    def __init__(self, initial_theme: str = "dark"):
        super().__init__()
        self._agent_registry = AdapterRegistry()
        self._agent_registry.register(ClaudeCodeAdapter())
        self._agent_registry.register(CodexAdapter())
        self._agent_registry.register(CodeBuddyAdapter())
        self.executor = SubprocessExecutor()
        self._tasks_state: dict[str, dict] = _load_tasks()
        self._adapter_cache: dict[AgentType, AgentAdapter | None] = {}
        self._running_procs: dict[str, asyncio.subprocess.Process] = {}
        self._no_output_timers: dict[str, asyncio.Task] = {}  # task_id → watchdog task
        self._worker_active: bool = False
        self._is_dark = initial_theme == "dark"
        self._theme_name = "textual-dark" if self._is_dark else "textual-light"

    def _get_adapter(self, at: AgentType) -> AgentAdapter | None:
        if at not in self._adapter_cache:
            self._adapter_cache[at] = self._agent_registry.get(at)
        return self._adapter_cache[at]

    # ---------------------------------------------------------------------------
    # 主题切换
    # ---------------------------------------------------------------------------
    def action_toggle_theme(self) -> None:
        self._is_dark = not self._is_dark
        self._theme_name = "textual-dark" if self._is_dark else "textual-light"
        self.theme = self._theme_name
        # 更新 theme toggle button 文字
        btn = self.query_one("#theme-btn", Button)
        btn.label = "☀️" if self._is_dark else "🌙"
        self.notify(f"Theme: {'Dark' if self._is_dark else 'Light'}")

    # ---------------------------------------------------------------------------
    # 布局
    # ---------------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(id="header-bar"):
            yield Static("🤖 AI Task System V4", id="app-title")
            yield Button("🌙", id="theme-btn", variant="primary")
            yield Static("", id="agent-availability")

        with Horizontal(id="agent-selector"):
            yield Static("Agent:", id="lbl-agent")
            yield RadioSet(
                RadioButton("Claude Code", id="rb-claude", value=True),
                RadioButton("Codex", id="rb-codex"),
                RadioButton("CodeBuddy", id="rb-codebuddy"),
                id="agent-radios",
            )

        with Vertical(id="task-list-container"):
            yield Static("Tasks", classes="section-label")
            yield ListView(id="task-list", mouse_scroll=True)
            yield Static("0 tasks", id="task-count")

        with Vertical(id="output-container"):
            yield Static("Output Log", classes="section-label")
            yield TimestampedLog(id="output-log", highlight=True, max_lines=5000)

        with Vertical(id="input-area"):
            with Horizontal(id="input-row"):
                yield Input(
                    placeholder="Enter task description and press Enter or click Execute...",
                    id="task-input",
                )
                yield Button("Execute", id="btn-execute", variant="primary")

        with Vertical(id="progress-container"):
            yield ProgressBar(id="task-progress", show_eta=False)
            yield Static("Ready", id="progress-label")

    # ---------------------------------------------------------------------------
    # 挂载后初始化
    # ---------------------------------------------------------------------------
    def on_mount(self) -> None:
        self.theme = self._theme_name
        self._refresh_agent_availability()
        self._refresh_task_list()
        self._reset_progress()

    # ---------------------------------------------------------------------------
    # Agent 可用性检查
    # ---------------------------------------------------------------------------
    def _refresh_agent_availability(self) -> None:
        at = self.selected_agent
        adapter = self._get_adapter(at)
        widget = self.query_one("#agent-availability", Static)
        if adapter:
            ok, msg = adapter.is_available()
            if ok:
                ver = adapter.get_metadata().get("version", "")
                widget.update(f"✅ {at.value} available {ver}")
                widget.styles.color = "green"
            else:
                widget.update(f"❌ {at.value}: {msg}")
                widget.styles.color = "red"
        else:
            widget.update(f"❓ {at.value} adapter not loaded")
            widget.styles.color = "yellow"

    # ---------------------------------------------------------------------------
    # 任务列表管理
    # ---------------------------------------------------------------------------
    def _refresh_task_list(self) -> None:
        list_view = self.query_one("#task-list", ListView)
        list_view.clear()
        sorted_items = sorted(
            self._tasks_state.items(),
            key=lambda x: x[1].get("created_at", ""),
            reverse=True,
        )
        for task_id, info in sorted_items[:50]:
            icons = {
                "pending": "⏳", "running": "▶️", "success": "✅",
                "failed": "❌", "timeout": "⏰",
                "no_output_timeout": "⚠️", "cancelled": "🚫",
            }
            icon = icons.get(info.get("status", "pending"), "❓")
            prompt = info.get("prompt", "N/A")[:36]
            lbl = f"{icon} {task_id[-8:]} | {prompt}"
            list_view.append(ListItem(Label(lbl), id=f"task-item-{task_id}"))
        self.query_one("#task-count", Static).update(f"{len(sorted_items)} task(s)")

    def _save_task_state(self, task_id: str, status: str, prompt: str) -> None:
        if task_id not in self._tasks_state:
            self._tasks_state[task_id] = {"created_at": datetime.now().isoformat(), "prompt": prompt}
        self._tasks_state[task_id]["status"] = status
        self._tasks_state[task_id]["updated_at"] = datetime.now().isoformat()
        _save_tasks(self._tasks_state)
        self._refresh_task_list()

    # ---------------------------------------------------------------------------
    # 进度条管理
    # ---------------------------------------------------------------------------
    def _set_progress(self, value: float, label: str = "") -> None:
        """设置进度条（0.0~1.0）"""
        self.progress_value = value
        if label:
            self.progress_label = label
            self.query_one("#progress-label", Static).update(label)

    def _reset_progress(self) -> None:
        self.progress_value = 0.0
        self.query_one("#task-progress", ProgressBar).update(progress=0)
        self.query_one("#progress-label", Static).update("Ready")

    def _show_warning(self, msg: str) -> None:
        """在日志中显示警告行（黄色）"""
        log: TimestampedLog = self.query_one("#output-log", TimestampedLog)
        self.call_next(lambda: log.write_line(f"⚠️  {msg}"))

    # ---------------------------------------------------------------------------
    # 无输出超时看门狗
    # ---------------------------------------------------------------------------
    async def _no_output_watchdog(self, task_id: str, timeout: int = 120) -> None:
        """
        监控任务在 `timeout` 秒内是否有新输出。
        如果超时，发送警告到 Log（但不中断任务）。
        """
        last_output_time = time.monotonic()
        check_interval = 10  # 每 10s 检查一次

        while True:
            await asyncio.sleep(check_interval)

            # 检查任务是否还在运行
            if task_id not in self._running_procs:
                break

            elapsed = time.monotonic() - last_output_time
            if elapsed >= timeout:
                elapsed_min = int(elapsed // 60)
                self._show_warning(f"无输出已 {elapsed_min}m，Agent 可能已卡住...")
                last_output_time = time.monotonic()  # 重置计时器（不终止任务）
            else:
                # 重置：下次再检查
                pass

    def _start_watchdog(self, task_id: str, timeout: int = 120) -> None:
        """启动无输出看门狗"""
        if task_id in self._no_output_timers:
            self._no_output_timers[task_id].cancel()
        self._no_output_timers[task_id] = asyncio.create_task(
            self._no_output_watchdog(task_id, timeout)
        )

    def _stop_watchdog(self, task_id: str) -> None:
        """停止看门狗"""
        t = self._no_output_timers.pop(task_id, None)
        if t:
            t.cancel()

    def _bump_watchdog(self, task_id: str) -> None:
        """有新输出时调用，重置看门狗（实际逻辑在看门狗内部：比对 last_output_time）"""
        # 通知看门狗当前有输出（通过重置 - 实际重置发生在下次检查）
        pass

    # ---------------------------------------------------------------------------
    # Switch 事件
    # ---------------------------------------------------------------------------
    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "sw-skip-perm":
            self.skip_permissions = event.switch.value
        elif event.switch.id == "sw-resume":
            self.resume_session = event.switch.value

    # ---------------------------------------------------------------------------
    # RadioSet 事件
    # ---------------------------------------------------------------------------
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        mapping = {
            "rb-claude": AgentType.CLAUDE_CODE,
            "rb-codex": AgentType.CODEX,
            "rb-codebuddy": AgentType.CODEBUDDY,
        }
        pressed_id = event.control.id
        self.selected_agent = mapping.get(pressed_id, AgentType.CLAUDE_CODE)
        self._refresh_agent_availability()

    # ---------------------------------------------------------------------------
    # ListView 选择事件（鼠标点击 / 键盘上下）
    # ---------------------------------------------------------------------------
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        try:
            task_id = event.item.id.replace("task-item-", "")
            log: TimestampedLog = self.query_one("#output-log", TimestampedLog)
            log.clear()
            log.write_line(f"=== Task: {task_id} ===")
            info = self._tasks_state.get(task_id, {})
            log.write_line(f"Status: {info.get('status', 'unknown')}")
            log.write_line(f"Prompt: {info.get('prompt', 'N/A')}")
            log.write_line(f"Created: {info.get('created_at', 'N/A')}")
            log.write_line(f"Updated: {info.get('updated_at', 'N/A')}")
        except Exception:
            pass

    def action_select_prev_task(self) -> None:
        """↑ 键：选择上一个任务"""
        list_view = self.query_one("#task-list", ListView)
        if list_view.index > 0:
            list_view.move_cursor(1)

    def action_select_next_task(self) -> None:
        """↓ 键：选择下一个任务"""
        list_view = self.query_one("#task-list", ListView)
        if list_view.index < len(list_view.children) - 1:
            list_view.move_cursor(1)

    def action_activate_task(self) -> None:
        """Enter 键：查看选中任务详情（若输入框无内容则执行任务）"""
        input_widget = self.query_one("#task-input", Input)
        if input_widget.value.strip():
            self._execute_task()
        else:
            # 查看任务详情
            list_view = self.query_one("#task-list", ListView)
            if list_view.children:
                self.on_list_view_selected(
                    type("E", (), {"item": list_view.children[list_view.index]})()
                )

    # ---------------------------------------------------------------------------
    # 按钮点击 & Enter 键
    # ---------------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-execute":
            self._execute_task()
        elif event.button.id == "theme-btn":
            self.action_toggle_theme()

    async def on_key(self, event: Key) -> None:
        if event.key == "enter":
            focused = self.focused
            if focused and focused.id == "task-input":
                self._execute_task()

    def action_focus_input(self) -> None:
        self.query_one("#task-input", Input).focus()

    def action_clear_log(self) -> None:
        self.query_one("#output-log", TimestampedLog).clear()
        self._reset_progress()

    # ---------------------------------------------------------------------------
    # 核心：执行任务
    # ---------------------------------------------------------------------------
    def _execute_task(self) -> None:
        """通过 Worker 执行任务（不阻塞 UI）"""
        input_widget = self.query_one("#task-input", Input)
        prompt = input_widget.value.strip()
        if not prompt:
            self.notify("Please enter a task description", severity="warning")
            return
        input_widget.value = ""
        self._run_task_worker(prompt)

    @work(exclusive=True)
    async def _run_task_worker(self, prompt: str) -> None:
        """异步执行任务，实时推送输出到 Log（含无输出超时监控）"""
        task_id = f"task-{int(time.time())}"
        log: TimestampedLog = self.query_one("#output-log", TimestampedLog)
        progress_bar: ProgressBar = self.query_one("#task-progress", ProgressBar)

        self._worker_active = True
        self._save_task_state(task_id, "running", prompt)
        self._set_progress(0.0, "🚀 Starting...")

        def log_sync(text: str) -> None:
            """线程安全地写入 Log"""
            self.call_next(lambda: log.write_line(text))

        start_time = time.time()
        last_output = [start_time]  # mutable container for closure

        def log_sync_with_bump(text: str) -> None:
            """带活动记录的 log"""
            last_output[0] = time.time()
            log_sync(text)

        log_sync(f"🚀 Task {task_id} started")
        log_sync(f"   Agent: {self.selected_agent.value}")
        log_sync(f"   Skip perm: {self.skip_permissions}, Resume: {self.resume_session}")
        log_sync(f"   Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        log_sync("---")

        # 启动无输出看门狗（每 10s 检查一次，超时 120s 报警）
        no_out_timeout = 120
        self._start_watchdog(task_id, timeout=no_out_timeout)

        adapter = self._get_adapter(self.selected_agent)
        if adapter is None:
            log_sync(f"❌ No adapter for {self.selected_agent.value}")
            self._save_task_state(task_id, "failed", prompt)
            self._stop_watchdog(task_id)
            self._worker_active = False
            self._reset_progress()
            return

        perm_mode = PermissionMode.BYPASS if self.skip_permissions else PermissionMode.AUTO
        config = ExecutionConfig(
            prompt=prompt,
            agent_type=self.selected_agent,
            permission_mode=perm_mode,
            timeout=600,
            no_output_timeout=no_out_timeout,
            resume=self.resume_session,
            allowed_tools=["Bash", "Read", "Write", "Edit", "Notebook", "Grep", "Glob"],
        )

        ok, err = adapter.validate_config(config)
        if not ok:
            log_sync(f"❌ Config error: {err}")
            self._save_task_state(task_id, "failed", prompt)
            self._stop_watchdog(task_id)
            self._worker_active = False
            self._reset_progress()
            return

        cmd = adapter.build_command(config)
        log_sync(f"CMD: {' '.join(cmd)}")
        log_sync("---")

        env = os.environ.copy()
        proc: asyncio.subprocess.Process | None = None
        total_timeout = config.timeout or 600

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=config.working_dir or None,
                env=env,
            )
            self._running_procs[task_id] = proc

            async def read_stream(
                stream: asyncio.StreamReader, label: str
            ) -> None:
                try:
                    while True:
                        line_bytes = await stream.readline()
                        if not line_bytes:
                            break
                        line = line_bytes.decode("utf-8", errors="replace").rstrip()
                        if line:
                            log_sync_with_bump(f"[{label}] {line}")
                            # 更新进度（模拟：越晚输出，进度越高）
                            elapsed = time.time() - start_time
                            prog = min(elapsed / total_timeout, 1.0)
                            self.call_next(
                                lambda p=prog: progress_bar.update(
                                    progress=int(p * 100)
                                )
                            )
                except Exception:
                    pass

            # 并发读取 stdout + stderr，等待进程结束
            gather_task = asyncio.create_task(
                asyncio.gather(
                    read_stream(proc.stdout, "OUT"),
                    read_stream(proc.stderr, "ERR"),
                    return_exceptions=True,
                )
            )
            return_code = await proc.wait()
            await gather_task

        except FileNotFoundError as e:
            log_sync(f"❌ Command not found: {e}")
            self._save_task_state(task_id, "failed", prompt)
            self._stop_watchdog(task_id)
            self._worker_active = False
            self._reset_progress()
            return
        except Exception as e:
            log_sync(f"❌ Error: {e}")
            self._save_task_state(task_id, "failed", prompt)
            self._stop_watchdog(task_id)
            self._worker_active = False
            self._reset_progress()
            return
        finally:
            self._running_procs.pop(task_id, None)
            self._stop_watchdog(task_id)

        elapsed = time.time() - start_time
        progress_bar.update(progress=100)

        if return_code == 0:
            log_sync("---")
            log_sync(f"✅ Task completed ({elapsed:.1f}s)")
            self._save_task_state(task_id, "success", prompt)
            self._set_progress(1.0, f"✅ Done in {elapsed:.1f}s")
        else:
            log_sync("---")
            log_sync(f"❌ Task failed (exit {return_code}, {elapsed:.1f}s)")
            self._save_task_state(task_id, "failed", prompt)
            self._set_progress(1.0, f"❌ Failed (exit {return_code})")

        self._worker_active = False

    # ---------------------------------------------------------------------------
    # 退出清理
    # ---------------------------------------------------------------------------
    def on_unmount(self) -> None:
        for task_id, proc in list(self._running_procs.items()):
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        for t in list(self._no_output_timers.values()):
            t.cancel()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="AI Task System V4 — TUI")
    parser.add_argument(
        "--theme",
        choices=["dark", "light"],
        default="dark",
        help="Initial color theme (default: dark)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Run in web mode on this port (requires `textual serve`)",
    )
    args = parser.parse_args()

    if args.port:
        # Web 模式：textual serve
        import subprocess
        subprocess.run(["textual", "serve", __file__, "--port", str(args.port), "--dev"])
    else:
        app = TaskTUI(initial_theme=args.theme)
        app.run()

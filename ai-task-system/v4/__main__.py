"""V4 AI Task System — 统一入口（支持 CLI、TUI 和 REPL 三种模式）

用法:
    # CLI 模式（默认）
    python -m ai_task_system.v4 [cli args...]

    # TUI 模式
    python -m ai_task_system.v4 --tui

    # REPL 模式（交互式）
    python -m ai_task_system.v4 --repl

    # 也可直接运行各组件
    python -m ai_task_system.v4.tui
    python -m ai_task_system.v4.repl
"""
import sys


def main() -> None:
    if "--tui" in sys.argv:
        # 移除 --tui 参数后运行 TUI
        sys.argv = [a for a in sys.argv if a != "--tui"]
        _run_tui()
    elif "--repl" in sys.argv:
        # 移除 --repl 参数后运行 REPL
        sys.argv = [a for a in sys.argv if a != "--repl"]
        _run_repl()
    elif len(sys.argv) == 1:
        # 无参数时进入 REPL 模式
        _run_repl()
    else:
        _run_cli()


def _run_cli() -> None:
    from ai_task_system.v4.cli import main as cli_main
    cli_main()


def _run_tui() -> None:
    from ai_task_system.v4.tui_app import TaskTUI
    app = TaskTUI()
    app.run()


def _run_repl() -> None:
    from ai_task_system.v4.repl import run_repl
    run_repl()


if __name__ == "__main__":
    main()

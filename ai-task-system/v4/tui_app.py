"""
AI Task System V4 — TUI 应用模块

这是 tui.py 的重导出（re-export），保证 API 兼容性。
实际实现在 ai_task_system.v4.tui.TaskTUI。
"""
from ai_task_system.v4.tui import TaskTUI, TASKS_FILE, _load_tasks, _save_tasks  # noqa: F401

__all__ = ["TaskTUI", "TASKS_FILE", "_load_tasks", "_save_tasks"]

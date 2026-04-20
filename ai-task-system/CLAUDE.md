# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI Task System 是一个统一的多 Agent CLI 编排层，支持 Claude Code、OpenAI Codex 和 CodeBuddy。包含 v1-v5 多个版本，其中 **v4/v5 是当前活跃版本**。

## 开发命令

```bash
# 安装依赖
pip install -e .

# 运行测试（必须在 ai-task-system 目录执行）
PYTHONPATH=$(pwd) python -m pytest tests/ -v

# 运行单个测试文件
PYTHONPATH=$(pwd) python -m pytest tests/test_router.py -v

# 启动 V4 CLI/REPL/TUI
python -m ai_task_system.v4              # REPL 模式（无参数默认）
python -m ai_task_system.v4 --tui         # TUI 模式
python -m ai_task_system.v4.cli agents    # CLI 模式

# 启动 V5 REST API
python -m v5.api.app --port 18792
```

## 重要：模块名与目录名的差异

- 目录名：`ai-task-system`（连字符）
- 模块名：`ai_task_system`（下划线）
- **所有 import 必须使用 `ai_task_system`，不能用 `ai-task-system`**

## 架构概览

```
ai-task-system/
├── v4/                    # 多 Agent 抽象层
│   ├── cli.py             # CLI 入口（14 个子命令）
│   ├── repl.py            # 交互式 REPL
│   ├── tui.py/tui_app.py  # Textual TUI 全屏界面
│   ├── core/
│   │   ├── base.py        # AgentAdapter 抽象基类
│   │   ├── executor.py    # 统一执行器 + NoOutputWatcher
│   │   ├── router.py      # 任务路由器（13 种任务类型）
│   │   └── session_store.py
│   └── adapters/          # Agent 适配器
│       ├── claude_adapter.py
│       ├── codex_adapter.py
│       └── codebuddy_adapter.py
├── v5/                    # 生产级架构
│   ├── worker/pool.py     # Worker 进程池
│   ├── queue/queue.py     # SQLite 持久化队列
│   └── api/app.py         # FastAPI REST API
└── tests/                 # 136 个测试（pytest）
```

## 入口点

| 入口 | 命令 |
|------|------|
| V4 REPL | `python -m ai_task_system.v4` |
| V4 CLI | `python -m ai_task_system.v4.cli <cmd>` |
| V4 TUI | `python -m ai_task_system.v4 --tui` |
| V5 API | `python -m v5.api.app --port 18792` |

## 数据目录

- 会话存储：`~/.ai_task_system/sessions.json`
- 基准分数：`~/.ai_task_system/benchmark_scores.json`
- REPL 历史：`~/.ai_task_system/repl_history`

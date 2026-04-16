# AI 任务领取系统设计文档

## 概述

AI 任务领取系统（AI Task Pickup System）是一个自动化的多 Agent 任务执行平台，支持从任务池领取任务、通过 Claude Code 执行代码/文档任务，并自动评估执行质量。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Web UI (FastAPI)                       │
│  http://localhost:8000                                      │
├─────────────────────────────────────────────────────────────┤
│                      API Layer                              │
│  /api/tasks - 任务管理                                       │
│  /api/scheduler - 调度器控制                                  │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ Scheduler │  │ Executor  │  │ Evaluator │              │
│  │  调度器    │  │  执行器   │  │  评估器   │              │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘              │
│        │              │              │                     │
│        └──────────────┼──────────────┘                     │
│                       ▼                                     │
│              ┌────────────────┐                             │
│              │  Task Pool     │                             │
│              │  (SQLite)       │                             │
│              └────────────────┘                             │
├─────────────────────────────────────────────────────────────┤
│                    Agent Layer                               │
│  ┌────────────┐  ┌────────────┐                             │
│  │ Claude Code │  │ Claude Code │  ... (可配置多 Agent)      │
│  │  Agent-1   │  │  Agent-2   │                             │
│  └────────────┘  └────────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. models.py - 数据模型

| 模型 | 字段 | 说明 |
|------|------|------|
| `Task` | id, title, description, type, status, priority, timestamps | 任务实体 |
| `TaskType` | code_dev, doc_summary | 任务类型枚举 |
| `TaskStatus` | pending, picked, running, completed, evaluated | 任务状态 |
| `Priority` | low, medium, high | 优先级 |
| `Evaluation` | quality_score, efficiency_score, overall_score, comment | 评估结果 |

### 2. database.py - 数据持久化

- **数据库**: SQLite (`tasks.db`)
- **表结构**: tasks 表
- **操作**: CRUD + 状态更新

### 3. scheduler.py - 任务调度器

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `NUM_AGENTS` | 2 | 并行 Agent 数量 |
| `SCHEDULER_INTERVAL` | 60 | 检查间隔（秒） |

**调度流程:**
1. 每 60 秒检查任务池
2. 扫描 `pending` 状态任务
3. 分配给空闲 Agent
4. 更新任务状态为 `picked`

### 4. executor.py - 任务执行器

**执行流程:**
```
pick_task() → create_workspace() → write_TASK_md() → run_claude_code() → save_result()
```

**Claude Code 调用:**
```bash
claude --print "<prompt>"
```

**Workspace 结构:**
```
workspace/task_{timestamp}/
├── TASK.md          # 任务描述
├── [生成的文件]      # Claude Code 产出
└── .git/            # Git 仓库
```

### 5. evaluator.py - 任务评估器

| 评估器 | 说明 |
|--------|------|
| `SimpleEvaluator` | 基于输出长度和执行时间评分 |
| `MiniMaxEvaluator` | 调用 MiniMax API 评分（需配置 API Key） |

**评分维度:**
- `quality_score`: 质量分
- `efficiency_score`: 效率分
- `overall_score`: 综合分 = (quality + efficiency) / 2

## API 接口

### 任务管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/tasks` | GET | 列出所有任务 |
| `POST /api/tasks` | POST | 创建新任务 |
| `GET /api/tasks/{id}` | GET | 获取任务详情 |
| `DELETE /api/tasks/{id}` | DELETE | 删除任务 |
| `POST /api/tasks/{id}/execute` | POST | 手动执行任务 |
| `POST /api/tasks/{id}/evaluate` | POST | 手动评估任务 |

### 调度器控制

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/scheduler/status` | GET | 获取调度器状态 |
| `POST /api/scheduler/start` | POST | 启动调度器 |
| `POST /api/scheduler/stop` | POST | 停止调度器 |
| `POST /api/scheduler/trigger` | POST | 触发一次领取 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TASK_DB_PATH` | `tasks.db` | SQLite 数据库路径 |
| `TASK_WORKSPACE_DIR` | `./workspace` | 任务执行工作目录 |
| `SCHEDULER_INTERVAL` | `60` | 调度器检查间隔（秒） |
| `NUM_AGENTS` | `2` | 并行 Agent 数量 |
| `ANTHROPIC_API_KEY` | - | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | - | API 地址（如使用代理） |
| `MINIMAX_API_KEY` | - | MiniMax API Key（评估用） |
| `PORT` | `8000` | 服务端口 |

## 使用流程

### 1. 启动服务

```bash
cd ai-task-system
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Key
python main.py
```

### 2. 创建任务

通过 Web UI 或 API:
```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "任务标题",
    "description": "任务描述",
    "task_type": "Code Development",
    "priority": "high"
  }'
```

### 3. 启动自动领取

```bash
curl -X POST http://localhost:8000/api/scheduler/start
```

### 4. 查看执行结果

```bash
curl http://localhost:8000/api/tasks/{id}
```

## 项目结构

```
ai-task-system/
├── main.py           # FastAPI 应用入口
├── models.py         # 数据模型
├── database.py       # 数据库操作
├── executor.py       # 任务执行器
├── evaluator.py      # 任务评估器
├── scheduler.py      # 自动领取调度器
├── requirements.txt  # 依赖
├── .env.example      # 环境变量模板
├── DESIGN.md         # 本文档
└── README.md         # 使用说明
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Python 3.12 |
| 数据库 | SQLite |
| Agent | Claude Code CLI |
| 评估 | MiniMax API / 简单评估器 |
| 异步 | asyncio |

## 扩展计划

- [ ] 支持更多任务类型（测试、部署等）
- [ ] 添加任务依赖管理
- [ ] 实现任务优先级队列
- [ ] 添加 WebSocket 实时推送
- [ ] 支持更多 LLM 提供商评估
- [ ] 添加任务历史和统计报表

---

_最后更新: 2026-04-17_

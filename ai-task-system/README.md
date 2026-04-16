# AI Task System

个人 AI 领取任务系统，支持 Web UI 任务管理、自动领取执行、交叉评估、迭代闭环。

## 功能特性

- **Web UI 任务管理** - 可视化界面添加、删除、查看任务
- **自动领取执行** - 调度器自动从任务池领取 pending 任务并执行
- **交叉评估** - 支持不同 AI 模型交叉评估执行结果
- **迭代闭环** - 评估结果自动反馈给执行引擎，评分低于阈值时自动重试
- **执行追踪** - 完整记录任务的领取时间、开始时间、完成时间、执行输出

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLite (aiosqlite)
- **前端**: HTML5 / Tailwind CSS (单文件，无构建)
- **执行引擎**: Code Buddy CLI (`claw`)
- **交互格式**: Markdown（模型间通信）

## 系统架构

```
┌─────────────────┐     HTTP      ┌─────────────────┐
│  Web UI         │◀────────────▶│  Python API     │
│  (HTML+Tailwind)│              │  (FastAPI)      │
└─────────────────┘              └────────┬────────┘
                                          │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
             │   任务池    │      │   评估引擎  │      │   执行引擎  │
             │  (SQLite)  │      │ (Markdown) │      │ (claw CLI) │
             └─────────────┘      └─────────────┘      └─────────────┘
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/xiaodongQ/ai-playground.git
cd ai-playground/ai-task-system
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
export PYTHONPATH=$(pwd)
uvicorn backend.main:app --reload --port 8000
```

### 4. 访问

- Web UI: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 5. 启动调度器（自动执行任务）

```bash
curl -X POST http://localhost:8000/api/scheduler/start
```

## 项目结构

```
ai-task-system/
├── backend/
│   ├── main.py           # FastAPI 入口 + 调度器端点
│   ├── database.py       # SQLite 数据库操作
│   ├── scheduler.py       # 任务调度器（自动领取）
│   ├── executor.py        # 执行引擎（调用 claw CLI）
│   ├── evaluator.py       # 评估引擎（生成 Markdown 反馈）
│   └── api/
│       └── routes.py     # REST API 路由
├── frontend/
│   └── index.html        # 单页应用（Tailwind CSS）
├── tests/                 # 测试文件
│   ├── test_database.py
│   ├── test_api.py
│   ├── test_scheduler.py
│   ├── test_executor.py
│   └── test_evaluator.py
├── docs/                  # 设计文档
├── CLAUDE.md             # Claude Code 指导
└── requirements.txt
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/tasks` | GET | 获取所有任务 |
| `/api/tasks` | POST | 创建任务 |
| `/api/tasks/{id}` | GET | 获取任务详情 |
| `/api/tasks/{id}` | PUT | 更新任务 |
| `/api/tasks/{id}` | DELETE | 删除任务 |
| `/api/tasks/{id}/executions` | GET | 获取执行历史 |
| `/api/tasks/{id}/evaluations` | GET | 获取评估历史 |
| `/api/stats` | GET | 获取统计信息 |
| `/api/scheduler/start` | POST | 启动调度器 |
| `/api/scheduler/stop` | POST | 停止调度器 |
| `/api/scheduler/status` | GET | 调度器状态 |

## 数据模型

### Task（任务）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| title | string | 任务标题 |
| description | string | 任务描述 |
| status | enum | pending/running/completed/evaluating/evaluated/re-execute |
| executor_model | string | 执行模型 |
| evaluator_model | string | 评估模型 |
| iteration_count | int | 当前迭代次数 |
| max_iterations | int | 最大迭代次数 |
| improvement_threshold | int | 触发改进的评分阈值 |
| feedback_md | text | 评估反馈（Markdown） |

### Execution（执行记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| task_id | UUID | 关联任务 |
| executor_model | string | 执行的模型 |
| started_at | datetime | 开始时间 |
| completed_at | datetime | 完成时间 |
| output | text | 执行输出 |

### Evaluation（评估记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| task_id | UUID | 关联任务 |
| execution_id | UUID | 关联执行记录 |
| evaluator_model | string | 评估模型 |
| score | int | 评分 1-10 |
| comments | text | 评估意见 |

## 任务生命周期

```
[创建任务]
    │
    ▼
pending ──▶ running ──▶ completed ──▶ evaluating ──▶ evaluated
    │                    │                              │
    │                    │ 评分 < 阈值                    │
    │                    ▼                              │
    │              re-execute ◀──── feedback_md ─────────┘
    │                    │
    │                    │ 迭代次数 >= max
    │                    ▼
    └──────────────────▶ abandoned
```

## 运行测试

```bash
pytest tests/ -v
```

## License

MIT

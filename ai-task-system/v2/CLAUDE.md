# AI Task System - Claude Code 指导

## 项目概述

个人 AI 领取任务系统，支持 Web UI 任务管理、自动领取执行、交叉评估、迭代闭环。

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLite (aiosqlite)
- **前端**: HTML5 / Tailwind CSS (CDN)
- **执行引擎**: Code Buddy CLI (`claw`)
- **测试**: pytest / pytest-asyncio

## 启动命令

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 PYTHONPATH 并启动
export PYTHONPATH=$(pwd)
uvicorn backend.main:app --reload --port 8000

# 浏览器访问
open http://localhost:8000
```

## 测试命令

```bash
pytest tests/ -v
```

## 项目结构

```
ai-task-system/
├── backend/
│   ├── main.py           # FastAPI 入口 + 调度器端点
│   ├── database.py       # SQLite 数据库操作
│   ├── scheduler.py       # 任务调度器（自动领取）
│   ├── executor.py        # 执行引擎（调用 claw CLI）
│   ├── evaluator.py       # 评估引擎（Markdown 反馈）
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
│   ├── DESIGN.md         # 详细设计文档
│   └── SUPERPOWERS.md    # Superpowers 使用记录
├── requirements.txt
├── README.md
└── CLAUDE.md            # 本文件
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/tasks` | GET/POST | 任务列表/创建 |
| `/api/tasks/{id}` | GET/PUT/DELETE | 任务操作 |
| `/api/tasks/{id}/executions` | GET | 执行历史 |
| `/api/tasks/{id}/evaluations` | GET | 评估历史 |
| `/api/stats` | GET | 统计信息 |
| `/api/scheduler/start` | POST | 启动调度器 |
| `/api/scheduler/stop` | POST | 停止调度器 |
| `/api/scheduler/status` | GET | 调度器状态 |

## 核心模块

### database.py

SQLite 数据库操作封装，提供 Task、Execution、Evaluation 的 CRUD 操作。

### scheduler.py

任务调度器，轮询 pending 任务并自动执行。

### executor.py

执行引擎，调用 claw CLI 执行任务。

### evaluator.py

评估引擎，生成 Markdown 格式的评估反馈。

## 开发指南

### 添加新 API 端点

在 `backend/api/routes.py` 中添加：

```python
@router.get("/new-endpoint")
async def new_endpoint():
    return {"result": "data"}
```

### 添加新测试

在 `tests/` 目录下创建测试文件：

```python
import pytest

@pytest.mark.asyncio
async def test_new_feature():
    # test code
    pass
```

### 前端修改

直接编辑 `frontend/index.html`，使用 Tailwind CSS 类名。

## 数据库

SQLite 数据库文件：`data/tasks.db`

### 重置数据库

```bash
rm data/tasks.db
```

## 调度器

启动调度器后，AI 会自动：
1. 领取 pending 状态的任务
2. 调用 claw CLI 执行
3. 执行完成后自动评估
4. 根据评分决定是否重试

## TODO

- [ ] 接入真实 AI API（目前评估使用模拟结果）
- [ ] claw CLI 参数适配
- [ ] 任务分类/标签功能
- [ ] 执行进度实时推送

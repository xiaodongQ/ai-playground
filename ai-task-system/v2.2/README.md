# AI Task System V2.2 — 双引擎 + 任务拆分版

在 V2 基础上全面升级，支持**双执行引擎**、**复杂任务拆分**、**产物管理**和 **WebSocket 实时推送**。

## 功能特性

### 双执行引擎
- **CLI 执行器**（`CLIExecutor`）— 调用 `claw` CLI，子进程管理，支持 kill
- **SDK 执行器**（`SDKExecutor`）— 调用 CodeBuddy Python SDK，原生异步流式输出
- **统一抽象层**（`BaseExecutor`）— 双引擎路由切换，通过 `EXECUTOR_ENGINE` 环境变量或 `config.yaml` 指定

### 产物管理与任务拆分
- **`artifacts.py`** — 产物管理器：存储/校验任务间依赖产物
- **`task_splitter.py`** — 任务拆分器：支持线性串行和树状并行拆分
- **`waiting` 状态** — 任务等待依赖产物就绪后才执行
- **Agent 亲和性调度** — 串行子任务优先同 Agent，并行子任务能力最优匹配

### 重试与容错
- **指数退避重试**（`RetryExecutor`）— 失败自动重试，最多重试 3 次
- **任务取消**（`kill`）— 真正终止子进程，非软删除
- **Stale 任务恢复** — 服务重启时自动恢复僵尸任务

### WebSocket 实时推送
- 任务状态变化实时推送至前端
- 支持连接初始化、ping/pong 心跳

### 评估与迭代
- **Evaluator async 化** — OpenAI API 调用不再阻塞事件循环
- **评估 Diff 展示** — 相邻两次执行的 output 差异可视化

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLite (aiosqlite) / WebSocket
- **前端**: HTML5 / Tailwind CSS (单文件)
- **执行引擎**: CLI (`claw`) + SDK (`codebuddy_agent_sdk`)
- **评估**: OpenAI API

## 快速开始

```bash
cd ai-task-system/v2.2
pip install -r requirements.txt
export PYTHONPATH=$(pwd)

# CLI 引擎（默认）
uvicorn backend.main:app --reload --port 8000

# SDK 引擎
EXECUTOR_ENGINE=sdk uvicorn backend.main:app --reload --port 8000

# 访问 http://localhost:8000
```

## 项目结构

```
v2.2/
├── backend/
│   ├── main.py              # FastAPI 入口 + WebSocket
│   ├── database.py          # SQLite + artifacts 表 + waiting 状态
│   ├── scheduler.py          # 调度器（5s 轮询 + stale 检测）
│   ├── evaluator.py          # 评估引擎（async OpenAI）
│   ├── executor.py           # 执行器路由层
│   ├── base_executor.py      # 抽象基类
│   ├── cli_executor.py      # claw CLI 执行器（含 kill）
│   ├── sdk_executor.py      # CodeBuddy SDK 执行器
│   ├── retry.py             # RetryExecutor（指数退避）
│   ├── websocket_manager.py  # WebSocket 管理器
│   ├── artifacts.py         # 产物管理器
│   ├── task_splitter.py    # 任务拆分器
│   └── api/
│       └── routes.py        # REST API（含 waiting/dependencies 端点）
├── frontend/
│   └── index.html           # 单页应用（实时推送 + diff 展示）
├── config.yaml              # 双引擎/评估/Session 持久化配置
└── requirements.txt
```

## 核心 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/tasks` | GET | 获取任务（分页 + 统计）|
| `/api/tasks` | POST | 创建任务 |
| `/api/tasks/{id}` | GET/PUT/DELETE | 任务 CRUD |
| `/api/tasks/waiting` | GET | 列出所有 waiting 任务 |
| `/api/tasks/{id}/wait` | POST | 设置任务为 waiting（附依赖）|
| `/api/tasks/{id}/dependencies-status` | GET | 检查依赖是否满足 |
| `/api/tasks/{id}/executions` | GET | 执行历史 |
| `/api/tasks/{id}/executions/diff` | GET | 相邻执行的 diff |
| `/api/tasks/{id}/evaluations` | GET | 评估历史 |
| `/api/tasks/{id}/cancel` | POST | 取消任务（kill 子进程）|
| `/api/tasks/{id}/retry` | POST | 重试失败任务 |
| `/api/tasks/recover` | POST | 手动恢复僵尸任务 |
| `/api/stats` | GET | 统计（总数/pending/running/failed 等）|
| `/api/scheduler/start` | POST | 启动调度器 |
| `/api/scheduler/stop` | POST | 停止调度器 |
| `/api/scheduler/status` | GET | 调度器状态 |

## 产物管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/artifacts` | GET | 获取所有产物 |
| `/api/artifacts/{id}` | GET | 获取产物详情 |
| `/api/artifacts` | POST | 创建产物 |
| `/api/artifacts/{id}/invalidate` | POST | 标记产物无效（通知下游重跑）|

## 任务拆分模式

| 模式 | 说明 |
|------|------|
| **线性串行**（A→B→C） | 前序产物作为下游输入 |
| **树状并行**（根→多子） | 独立子任务并行执行，最终合并验收 |

## 配置（config.yaml）

```yaml
executor:
  engine: cli      # cli | sdk
  cli_path: claw
  sdk_path: claw
  timeout: 300
sdk:
  permission_mode: bypassPermissions
  model: claude-opus-4-6
evaluator:
  default_model: gpt-4o
  timeout: 60
database:
  path: data/tasks.db
server:
  host: 0.0.0.0
  port: 8000
```

## 任务生命周期

```
pending → waiting(等待依赖) → running → completed → evaluating → evaluated
                    ↘ failed
                    ↘ running (stale → auto-recover)
```

---

## 版本演进

| 版本 | 定位 |
|------|------|
| **v2/** | V2 原始版（heartbeat/stale recovery）|
| **v2.2/** | 双引擎 + 产物管理 + 任务拆分 + WebSocket |
| **v4/** | 多 Agent 抽象层（CLI/TUI/REPL）|
| **v5/** | 生产级（进程池 + 持久化队列 + REST API）|

**入口 README**：请参考 [../README.md](../README.md)

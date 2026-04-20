# AI Task System V2.3 — 合并版（v2 + v2.2）

在 v2.2 基础上合并 v2 的可靠性特性，是当前功能最完整的版本。

## 功能特性

### 双执行引擎
- **CLI 执行器** — 调用 `claw` CLI，子进程管理，支持 kill
- **SDK 执行器** — 调用 CodeBuddy Python SDK，原生异步流式输出
- 通过 `config.yaml` 的 `executor.engine: cli|sdk` 切换

### 可靠性保障（来自 v2）
- **心跳机制**（Heartbeat）— 调度器每 `heartbeat_interval` 秒更新运行中任务心跳
- **Stale 检测** — `stale_threshold` 秒无心跳判定为僵尸任务，自动恢复
- **自动重试** — `max_auto_retries` 次，指数退避间隔 `auto_retry_delay`
- **Exit Code 检测** — 非零退出码 → failed → 自动重试
- **失败记录** — `failed_at` + `retry_count` 追踪

### 产物管理与任务拆分（来自 v2.2）
- **artifacts.py** — 产物管理器：存储/校验任务间依赖产物
- **task_splitter.py** — 任务拆分器：线性串主 + 树状并行
- **Waiting 状态** — 任务等待依赖产物就绪后才执行

### WebSocket 实时推送
- 任务状态变化实时推送至前端
- 支持连接初始化、ping/pong 心跳

### 前端功能
- **调度器启停控制** — 页面直接启动/停止自动调度
- **Settings 弹窗** — 配置 CLI、执行模型、评估模型
- **重试按钮** — failed 任务一键重试
- **分页 + 过滤器** — 任务列表分页切换和状态筛选
- **实时推送** — WebSocket 实时更新任务状态

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLite (aiosqlite) / WebSocket
- **前端**: HTML5 / Tailwind CSS (单文件)
- **执行引擎**: CLI (`claw`) + SDK (`codebuddy_agent_sdk`)
- **评估**: OpenAI API

## 快速开始

```bash
cd v2.3
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
uvicorn backend.main:app --reload --port 8000
```

## 项目结构

```
v2.3/
├── backend/
│   ├── main.py              # FastAPI 入口 + WebSocket
│   ├── database.py          # SQLite（含 heartbeat/retry_count/config 表）
│   ├── scheduler.py          # 调度器（轮询 + 心跳 + stale 检测 + 延迟重试）
│   ├── evaluator.py          # 评估引擎（async OpenAI）
│   ├── executor.py           # 执行器路由层
│   ├── base_executor.py      # 抽象基类
│   ├── cli_executor.py       # claw CLI 执行器（含 kill）
│   ├── sdk_executor.py       # CodeBuddy SDK 执行器
│   ├── retry.py              # RetryExecutor（指数退避）
│   ├── config.py             # YAML 配置加载 + 日志
│   ├── websocket_manager.py  # WebSocket 管理器
│   ├── artifacts.py          # 产物管理器
│   ├── task_splitter.py     # 任务拆分器
│   └── api/
│       └── routes.py         # REST API
├── frontend/
│   └── index.html            # 单页应用（调度器控制 + Settings 弹窗 + 实时推送）
├── config.yaml               # 完整配置（含 heartbeat/retry/engine）
└── requirements.txt
```

## 核心 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/tasks` | GET | 获取任务列表（分页）|
| `POST /api/tasks` | POST | 创建任务 |
| `DELETE /api/tasks` | DELETE | 删除所有任务 |
| `GET /api/tasks/waiting` | GET | 列出 waiting 任务 |
| `POST /api/tasks/{id}/wait` | POST | 设置任务为 waiting |
| `POST /api/tasks/{id}/retry` | POST | 重试失败任务 |
| `POST /api/tasks/{id}/cancel` | POST | 取消任务（kill 子进程）|
| `POST /api/tasks/recover` | POST | 手动恢复 stale 任务 |
| `GET /api/tasks/{id}/executions/diff` | GET | 相邻执行 diff |
| `GET /api/stats` | GET | 统计（含 failed 数量）|
| `GET /api/config` | GET | 获取全部配置 |
| `PUT /api/config/{key}` | PUT | 更新配置项 |
| `GET /api/scheduler/status` | GET | 调度器状态 |
| `POST /api/scheduler/start` | POST | 启动调度器 |
| `POST /api/scheduler/stop` | POST | 停止调度器 |

## 配置（config.yaml）

```yaml
scheduler:
  poll_interval: 5
  heartbeat_interval: 30      # 心跳间隔（秒）
  stale_threshold: 120         # 僵尸任务判定（秒）

executor:
  engine: cli                 # cli | sdk
  cli_path: claw
  sdk_path: claw
  timeout: 1800               # 执行超时（秒）
  max_auto_retries: 3          # 最大自动重试次数
  auto_retry_delay: 180        # 重试延迟（秒）

sdk:
  permission_mode: bypassPermissions

evaluator:
  model: "claude-opus-4-6"    # 评估模型
  default_model: gpt-4o

server:
  host: 0.0.0.0
  port: 8000

log:
  level: INFO
  file: server.log
  max_bytes: 10485760
  backup_count: 5
```

## 任务生命周期

```
pending → waiting(依赖) → running → completed → evaluating → evaluated
                    ↘ failed (auto-retry → pending)
                    ↘ stale (heartbeat 超时 → pending)
```

---

## 版本演进

| 版本 | 定位 |
|------|------|
| **v2/** | V2 原始版（heartbeat/stale recovery）|
| **v2.2/** | 双引擎 + 产物管理 + 任务拆分 + WebSocket |
| **v2.3/** | v2 + v2.2 合并版（可靠性 + 新特性），功能最完整 |

**入口 README**：[../README.md](../README.md)
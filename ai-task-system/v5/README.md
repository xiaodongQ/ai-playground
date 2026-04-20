# AI Task System V5 — 生产级架构

> 基于 V4 的生产级任务系统：进程池、持久化队列、REST API、WebSocket 实时推送、Prometheus 监控。

**V5** 是 V4 的生产级扩展，将 V4 的单次执行模型扩展为带持久化队列和进程池的分布式任务系统，支持高并发、任务追踪、自动恢复和实时监控。

---

## 目录

- [架构](#架构)
- [快速开始](#快速开始)
- [REST API](#rest-api)
- [WebSocket](#websocket)
- [Worker Pool](#worker-pool)
- [Task Queue](#task-queue)
- [Supervisor](#supervisor)
- [V4×V5 集成](#v4xv5-集成)
- [认证](#认证)
- [监控与指标](#监控与指标)
- [部署](#部署)

---

## 架构

```
v5/
├── api/
│   ├── app.py            # FastAPI 主程序（786 行）
│   ├── models.py         # Pydantic 请求/响应模型
│   ├── websocket.py      # WebSocket 实时推送（440 行）
│   └── metrics.py        # Prometheus 指标（350 行）
├── worker/
│   ├── pool.py           # Worker 进程池（650 行）
│   └── supervisor.py    # 健康监护系统（580 行）
├── queue/
│   └── queue.py         # SQLite 持久化队列（861 行）
├── integration/
│   ├── queue_dispatcher.py  # TaskQueue → WorkerPool 调度器
│   └── session_pool.py      # V4×V5 会话池集成
└── web/                    # 可选 Web UI 静态文件
```

### 系统流程

```
HTTP/WebSocket 请求
       ↓
  FastAPI (v5/api/app.py)
       ↓
  TaskQueue (SQLite WAL) ←── 持久化（~/.ai_task_system/tasks.db）
       ↓
  QueueDispatcher (后台线程轮询)
       ↓
  WorkerPool (预热进程池)
       ↓
  V4 CommandBuilder → subprocess → Agent (Claude/Codex/CodeBuddy)
       ↓
  Supervisor (心跳监控 + 自动恢复)
       ↓
  WebSocket 广播 ←── 实时推送任务状态
```

### 核心组件

| 组件 | 职责 | 持久化 |
|------|------|--------|
| `TaskQueue` | 任务存储、优先级调度、死信队列 | SQLite WAL |
| `QueueDispatcher` | 后台轮询 + 派发到 WorkerPool | 内存 |
| `WorkerPool` | 进程预热、负载均衡、任务执行 | 内存 |
| `Supervisor` | 心跳检测、无输出监控、自动重启 | 内存 |
| `SessionPoolManager` | V4 会话与 V5 Worker 的绑定 | 内存 |

---

## 快速开始

### 1. 启动 REST API

```bash
# 设置 API Key（可选，启用认证）
export AI_TASK_API_KEY="my-secret-key"

# 启动
python -m v5.api.app --port 18792
```

访问：
- Web UI：`http://localhost:18792/`
- Swagger 文档：`http://localhost:18792/docs`
- Prometheus 指标：`http://localhost:18792/metrics`

### 2. 提交任务

```bash
# 通过 curl 提交
curl -X POST http://localhost:18792/tasks \
  -H "X-API-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "say hello", "agent": "claude", "timeout": 30}'

# 响应
{"task_id":"t-abc123def456","status":"pending","message":"Task submitted, agent=claude"}
```

### 3. 查询任务

```bash
# 列表
curl http://localhost:18792/tasks?status=pending \
  -H "X-API-Key: my-secret-key"

# 详情
curl http://localhost:18792/tasks/t-abc123def456 \
  -H "X-API-Key: my-secret-key"
```

### 4. WebSocket 实时推送

```javascript
const ws = new WebSocket('ws://localhost:18792/ws?token=my-secret-key');

// 订阅所有任务
ws.send(JSON.stringify({type: 'subscribe_all'}));

// 接收事件
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  console.log('[event]', msg.type, msg.data);
};
```

---

## REST API

### 认证

所有受保护端点需要 `X-API-Key` header：

```bash
curl -X GET http://localhost:18792/tasks \
  -H "X-API-Key: my-secret-key"
```

未配置 `AI_TASK_API_KEY` 时，认证被禁用（所有端点可匿名访问）。

### 端点一览

#### 公开端点（无需认证）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查（workers 数量、任务统计） |
| `/info` | GET | 系统信息（版本、认证状态、WS 连接数） |
| `/metrics` | GET | Prometheus 文本格式指标 |

#### 路由

| 端点 | 方法 | 说明 |
|------|------|------|
| `/route` | POST | 任务分类 + Agent 推荐 |

#### 任务管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/tasks` | POST | 提交新任务 |
| `/tasks` | GET | 任务列表（支持分页、状态过滤） |
| `/tasks/{id}` | GET | 任务详情 |
| `/tasks/{id}` | DELETE | 删除任务（仅 pending/dead） |
| `/tasks/{id}/fail` | POST | 标记失败（可选择重试） |
| `/tasks/{id}/retry` | POST | 重试失败任务 |

#### 队列

| 端点 | 方法 | 说明 |
|------|------|------|
| `/queue/metrics` | GET | 队列聚合指标（pending/running/done/failed/dead） |

#### Worker 管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/workers` | GET | Worker 列表 |
| `/workers/{id}` | GET | Worker 详情 |
| `/workers/{id}/restart` | POST | 手动重启 Worker |

#### Supervisor

| 端点 | 方法 | 说明 |
|------|------|------|
| `/supervisor/metrics` | GET | 健康指标（healthy/unhealthy/recovered） |

#### 会话管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/sessions` | GET | 会话列表（支持 agent/status 过滤） |
| `/sessions/{id}` | GET | 会话详情 |
| `/sessions/{id}/archive` | POST | 归档会话 |
| `/sessions/{id}/note` | POST | 更新备注 |
| `/sessions/{id}` | DELETE | 删除会话 |
| `/sessions/stats` | GET | 会话统计 |

#### WebSocket

| 端点 | 说明 |
|------|------|
| `/ws` | WebSocket 实时推送 |

### 请求 / 响应示例

#### POST /tasks

```json
// Request
{
  "prompt": "帮我写一个快速排序",
  "agent": "claude",
  "priority": "normal",      // critical / high / normal / low / bg
  "timeout": 300,
  "max_retries": 3,
  "retry_delay": 5.0,
  "allowed_tools": ["Bash", "Write"],
  "permission_mode": "bypass"
}

// Response
{
  "task_id": "t-abc123def456",
  "status": "pending",
  "message": "Task submitted, agent=claude"
}
```

#### GET /tasks/{id}

```json
{
  "task_id": "t-abc123def456",
  "status": "running",
  "priority": "normal",
  "payload": {"prompt": "帮我写一个快速排序", "agent": "claude"},
  "timeout": 300,
  "max_retries": 3,
  "retry_count": 0,
  "created_at": 1745123456.789,
  "dequeued_at": 1745123457.123,
  "started_at": 1745123458.456,
  "completed_at": null,
  "worker_id": "w-abc12345",
  "result": null,
  "error": null,
  "metadata": {}
}
```

---

## WebSocket

### 连接

```javascript
// 带 API Key
const ws = new WebSocket('ws://localhost:18792/ws?token=my-secret-key');

// 不带 API Key（认证禁用时）
const ws = new WebSocket('ws://localhost:18792/ws');
```

### 订阅消息

```javascript
// 订阅所有事件
ws.send(JSON.stringify({type: 'subscribe_all'}));

// 订阅特定任务
ws.send(JSON.stringify({type: 'subscribe_task', task_id: 't-abc123'}));

// 订阅特定 Worker
ws.send(JSON.stringify({type: 'subscribe_worker', worker_id: 'w-abc123'}));

// 订阅会话更新
ws.send(JSON.stringify({type: 'subscribe_session', session_id: 'xxx'}));

// 取消订阅
ws.send(JSON.stringify({type: 'unsubscribe_all'}));
```

### 事件类型

| 事件类型 | 说明 | data 字段 |
|----------|------|-----------|
| `task_output` | 任务 stdout 输出 | `{task_id, line}` |
| `task_status` | 任务状态变更 | `{task_id, status}` |
| `task_complete` | 任务完成 | `{task_id, status, returncode}` |
| `task_error` | 任务错误 | `{task_id, error}` |
| `worker_health` | Worker 健康状态变更 | `{worker_id, health_status}` |
| `worker_restart` | Worker 重启 | `{worker_id}` |
| `session_update` | 会话更新 | `{session_id, session}` |
| `system` | 系统消息 | `{message, level}` |

---

## Worker Pool

### 架构

```
WorkerPool
├── Worker[id=w-001]  (IDLE / BUSY / RECOVERING)
├── Worker[id=w-002]  (IDLE / BUSY / RECOVERING)
└── Worker[id=w-N]  (IDLE / BUSY / RECOVERING)
```

### 特性

- **进程预热**：启动时立即就绪，不阻塞主线程
- **Least Connections 负载均衡**：分配给空闲最久的 Worker
- **故障自动恢复**：崩溃的 Worker 自动重启（最多 3 次连续错误）
- **无输出超时**：超过 `no_output_timeout` 秒无输出则终止任务
- **优雅关闭**：等待正在执行的任务完成

### Worker 状态

| 状态 | 说明 |
|------|------|
| `STARTING` | 进程启动中 |
| `IDLE` | 空闲，等待任务 |
| `BUSY` | 执行任务中 |
| `RECOVERING` | 故障恢复中 |
| `STOPPING` | 优雅关闭中 |
| `STOPPED` | 已停止 |

### 配置参数

```python
from v5.worker.pool import WorkerPool

pool = WorkerPool(
    agent_type="claude",      # Agent 类型
    size=2,                   # Worker 数量
    task_timeout=300,         # 任务超时（秒）
    no_output_timeout=60,     # 无输出超时（秒）
    max_queue_size=100,       # 最大待处理任务数
)
pool.start()
```

### CLI

```bash
# 启动 Worker Pool
python -m v5.worker.pool start --agent claude --size 2

# 提交任务
python -m v5.worker.pool submit "say hello" --timeout 30

# 查看状态
python -m v5.worker.pool list

# 停止
python -m v5.worker.pool stop
```

---

## Task Queue

### 架构

```
submit() → SQLite PENDING → dequeue() → RUNNING → done() / fail()
                                                       ↓ (retries exhausted)
                                                    DEAD (死信队列)
```

### SQLite WAL 模式

- **journal_mode=WAL**：支持高并发读写
- **foreign_keys=ON**：级联删除
- **busy_timeout=30000**：30s 锁等待

### 任务状态

| 状态 | 说明 |
|------|------|
| `PENDING` | 队列中等待 |
| `DEQUEUED` | 已被 Worker 认领（还未 start） |
| `RUNNING` | 执行中 |
| `DONE` | 成功完成 |
| `FAILED` | 失败（可重试） |
| `DEAD` | 死信（重试次数耗尽） |

### 优先级

| 优先级 | 值 | 说明 |
|--------|-----|------|
| `CRITICAL` | 0 | 最高优先级，立即处理 |
| `HIGH` | 2 | 高优先级 |
| `NORMAL` | 5 | 默认优先级 |
| `LOW` | 7 | 低优先级 |
| `BACKGROUND` | 9 | 后台任务 |

### 重试策略

- `fail()` 时判断 `retry_count < max_retries`
- 指数退避：`delay = base_delay × 2^retry_count + jitter`
- 超过最大重试次数 → 移入 `dead_letters` 表

### 死信队列

```python
# 查看死信
q.list_dead_letters(since=time.time() - 86400)

# 清理 7 天前的死信
q.purge_dead_letters(before=time.time() - 86400 * 7)
```

### CLI

```bash
# 提交任务
python -m v5.queue.queue submit '{"prompt":"hello"}' --priority 5 --timeout 60

# 查看 pending
python -m v5.queue.queue list-pending

# 查看 running
python -m v5.queue.queue list-running

# 查看死信
python -m v5.queue.queue list-dead

# 指标
python -m v5.queue.queue metrics

# 恢复卡死任务
python -m v5.queue.queue recover-stale --worker w-001
```

---

## Supervisor

### 架构

```
Supervisor
├── monitors[worker_id] = WorkerMonitor
├── health_check_loop (每 interval 秒)
└── recovery_policy (auto | manual)
```

### 健康检测

每个 Worker 有一个 `WorkerMonitor`，跟踪：
- **心跳**：Worker 进程定期输出心跳
- **无输出时间**：超过阈值判定为不健康
- **CPU / Memory**：系统资源使用

### 健康状态

| 状态 | 说明 |
|------|------|
| `HEALTHY` | 心跳正常 |
| `SUSPECTED` | 心跳异常（可能假死） |
| `UNHEALTHY` | 已判定崩溃 |
| `RECOVERING` | 正在重启 |

### 恢复策略

- 连续 N 次检测失败 → 触发 `UNHEALTHY`
- `UNHEALTHY` → 自动重启 Worker（`recovery_policy=auto`）
- 手动模式可通过 `/workers/{id}/restart` 触发

### Supervisor 指标

```json
{
  "total_workers": 2,
  "healthy_workers": 2,
  "unhealthy_workers": 0,
  "recovered_count": 0,
  "last_health_check": 1745123456.789,
  "pool_uptime": 3600.0
}
```

---

## V4×V5 集成

### SessionPoolManager

桥接 V4 会话管理和 V5 Worker 池：

```python
from v5.integration.session_pool import SessionPoolManager
from v5.worker.pool import WorkerPool
from v4.core.session_store import SessionStore

pool = WorkerPool(agent_type="claude", size=2)
pool.start()

session_pool = SessionPoolManager(pool=pool, store=SessionStore())
session_pool.start()

# 自动复用 V4 会话
task_id = session_pool.submit_with_session(
    prompt="继续上次的工作",
    session_id="existing-session-id"
)
```

### QueueDispatcher

桥接 `TaskQueue` 和 `WorkerPool`：

```
TaskQueue.dequeue(worker_id)
    ↓
WorkerPool.submit()
    ↓
completion_callback → TaskQueue.done() / fail()
```

---

## 认证

### 配置 API Key

```bash
# 单个 Key
export AI_TASK_API_KEY="my-secret-key"

# 多个 Key（逗号分隔）
export AI_TASK_API_KEY="key1,key2,key3"
```

### 认证行为

- **未配置** `AI_TASK_API_KEY` → 所有端点无需认证（向后兼容）
- **已配置** → 受保护端点必须提供匹配的 `X-API-Key` header

### WebSocket 认证

```
ws://localhost:18792/ws?token=my-secret-key
```

---

## 监控与指标

### Prometheus 端点

`GET /metrics` — Prometheus text exposition format

关键指标：

| 指标 | 类型 | 说明 |
|------|------|------|
| `ai_task_queue_pending` | Gauge | 等待中的任务数 |
| `ai_task_queue_running` | Gauge | 执行中的任务数 |
| `ai_task_queue_done_total` | Counter | 累计完成任务数 |
| `ai_task_queue_failed_total` | Counter | 累计失败任务数 |
| `ai_task_queue_dead_letters` | Gauge | 死信队列长度 |
| `ai_task_worker_count` | Gauge | Worker 总数 |
| `ai_task_worker_busy` | Gauge | 忙碌的 Worker 数 |
| `ai_task_task_duration_seconds` | Histogram | 任务执行耗时 |

### Prometheus 配置

```yaml
scrape_configs:
  - job_name: 'ai-task-system'
    static_configs:
      - targets: ['localhost:18792']
    metrics_path: '/metrics'
```

---

## 部署

### 方式 1：直接运行

```bash
python -m v5.api.app --host 0.0.0.0 --port 18792
```

### 方式 2：uvicorn

```bash
uvicorn v5.api:app --host 0.0.0.0 --port 18792 --workers 1
```

### 方式 3：gunicorn

```bash
gunicorn v5.api:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:18792
```

### 进程管理建议

```bash
# 使用 systemd
[Unit]
Description=AI Task System V5 API
After=network.target

[Service]
Type=simple
User=ai-task
WorkingDirectory=/opt/ai-task-system
Environment="AI_TASK_API_KEY=your-secret-key"
ExecStart=/usr/bin/python3 -m v5.api.app --port 18792
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 数据目录

| 内容 | 路径 |
|------|------|
| 任务队列 DB | `~/.ai_task_system/tasks.db` |
| 会话存储 | `~/.ai_task_system/sessions.json` |
| Worker 状态 | `~/.ai_task_system/pool/` |

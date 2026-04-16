# CLI 与接口规范

## 一、CLI 命令规范

### 基础用法

```bash
# 创建并执行任务
python cli.py create -p "任务描述"

# 带完整参数
python cli.py create -p --title "任务标题" --allowed-tools "Read,Write,Bash,Git" "任务描述"

# 续跑任务
python cli.py resume {task_id} "优化内容"

# 任务列表
python cli.py list
python cli.py list --status pending

# 查看任务
python cli.py get {task_id}

# 删除任务
python cli.py delete {task_id}

# 调度器
python cli.py scheduler start
python cli.py scheduler stop
python cli.py scheduler status
```

## 二、API 接口规范

### 任务管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/tasks` | GET | 列出所有任务 |
| `POST /api/tasks` | POST | 创建新任务 |
| `GET /api/tasks/{id}` | GET | 获取任务详情 |
| `DELETE /api/tasks/{id}` | DELETE | 删除任务 |
| `POST /api/tasks/{id}/execute` | POST | 手动执行任务 |

### 调度器

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/scheduler/status` | GET | 获取状态 |
| `POST /api/scheduler/start` | POST | 启动 |
| `POST /api/scheduler/stop` | POST | 停止 |
| `POST /api/scheduler/trigger` | POST | 触发一次领取 |

### WebSocket

| 端点 | 说明 |
|------|------|
| `ws://localhost:8000/ws/global` | 全局事件 |
| `ws://localhost:8000/ws/tasks/{id}` | 单任务事件 |

## 三、事件类型

| 事件类型 | 说明 |
|----------|------|
| `task_created` | 任务创建 |
| `task_status_changed` | 状态变更 |
| `task_log_appended` | 日志追加 |
| `task_completed` | 任务完成 |
| `task_failed` | 任务失败 |
| `scheduler_error` | 调度器错误 |

## 四、CodeBuddy CLI 命令

### 首次执行

```bash
codebuddy -p -y "{任务描述}" \
  --allowedTools "Read,Write,Bash,Git" \
  --permission-mode acceptEdits \
  --output-format text \
  --verbose
```

### 续跑执行

```bash
codebuddy -p -y --resume {session_id} "{优化描述}" \
  --allowedTools "Read,Write,Bash,Git" \
  --permission-mode acceptEdits \
  --verbose
```

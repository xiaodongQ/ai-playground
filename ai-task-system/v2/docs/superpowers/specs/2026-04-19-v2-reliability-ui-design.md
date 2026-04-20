# AI Task System v2 - 可靠性与 UI 增强设计

## 概述

本设计针对 v2 的两个核心问题：
1. **可靠性**：服务/CLI 异常后任务恢复 + 失败重试 + 手动重试
2. **UI**：任务列表分页 + 详情增强

---

## 第一部分：数据库修改

### 1.1 新增字段

`tasks` 表新增字段：

```sql
ALTER TABLE tasks ADD COLUMN last_heartbeat TEXT;
ALTER TABLE tasks ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN failed_at TEXT;
```

`executions` 表新增字段：

```sql
ALTER TABLE executions ADD COLUMN exit_code INTEGER;
```

### 1.2 新增状态

任务状态机：

```
pending → running → completed
                ↘ failed
pending ← ← ← ← ← (心跳超时恢复)
failed → pending (手动/自动重试)
```

---

## 第二部分：心跳恢复机制

### 2.1 Scheduler 改造

- scheduler 每 30 秒对所有 `status=running` 的任务执行 `UPDATE tasks SET last_heartbeat = NOW()`（批量更新）
- 执行命令前更新 heartbeat，确保心跳活跃

### 2.2 服务启动恢复

`main.py` 启动时调用恢复逻辑：

```python
async def recover_stale_tasks():
    """恢复僵尸任务（running 但心跳超时的）"""
    stale = await db.list_tasks(status="running")
    for task in stale:
        if is_heartbeat_stale(task.last_heartbeat, threshold=120):  # 2分钟
            await db.update_task_status(task.id, "pending")
            logger.warning(f"任务 {task.id} 心跳超时，标记为 pending")
```

### 2.3 心跳超时判断

```python
def is_heartbeat_stale(last_heartbeat: str, threshold: int = 120) -> bool:
    if not last_heartbeat:
        return True
    last = datetime.fromisoformat(last_heartbeat)
    return (datetime.now() - last).seconds > threshold
```

---

## 第三部分：失败状态与重试机制

### 3.1 失败状态判断

执行完成后，根据以下条件判断：

| 条件 | 标记状态 | 说明 |
|------|----------|------|
| returncode == 0 | completed | 成功 |
| 超时 | completed | 带 error 信息 |
| returncode != 0 | **failed** | 失败 |
| 异常（非超时） | **failed** | 失败 |

### 3.2 失败处理流程

```
执行失败 → 标记 failed + failed_at = NOW()
         → retry_count += 1
         → 如果 retry_count < 3，3分钟后自动变 pending
         → 页面显示 failed 状态 + 重试按钮
```

### 3.3 重试 API

```
POST /api/tasks/{id}/retry
- 重置状态为 pending
- retry_count 不变（人工介入后可以手动重置）
- 清空 last_execution_id 相关（重新创建 execution）
```

---

## 第四部分：API 改造

### 4.1 列表分页

```
GET /api/tasks?status=pending&page=1&page_size=20
Response: {
    "tasks": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
}
```

### 4.2 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/tasks/{id}/retry` | POST | 手动重试 |
| `/api/tasks/recover` | POST | 恢复僵尸任务（管理员用） |
| `/api/stats` | GET | 扩展包含 failed 数量 |

### 4.3 stats 扩展

```json
{
    "total": 100,
    "pending": 10,
    "running": 5,
    "completed": 80,
    "failed": 5
}
```

---

## 第五部分：前端 UI 增强

### 5.1 任务列表分页

组件结构：
```
[全部][待执行][执行中][已完成][失败]  按钮组
任务卡片1...
任务卡片2...
...
[上一页] [1] [2] [3] ... [下一页]  分页控件
```

- 默认 page_size=20
- 筛选状态时保持分页
- 切换筛选时重置到第1页

### 5.2 任务详情增强

**失败任务显示：**
```
状态: ❌ 失败 (第2次尝试)
错误信息: Command exited with code 1
         ls: cannot access '/tmp/xxx': No such file or directory

[🔄 重试此任务]  [🗑 删除任务]
```

**running 任务显示：**
```
状态: 🔄 执行中
开始时间: 2026-04-19 22:30:00
已运行: 5分32秒 (持续计时)
```

**超时任务：**
```
状态: ⏱ 执行超时 (30分钟)
[🔄 重新执行]  [🗑 删除]
```

### 5.3 迭代进度

```
迭代: ████░░░░░░ 2/3 (66%)
评分阈值: 7分
```

---

## 第六部分：文件修改清单

| 文件 | 修改内容 |
|------|----------|
| `backend/database.py` | 新增 heartbeat/retry_count/failed_at 字段，list_tasks 加分页，get_task 加载 executions 时排序 |
| `backend/scheduler.py` | 心跳更新循环，启动时恢复僵尸任务，失败状态处理 |
| `backend/executor.py` | 失败返回区分 exit_code |
| `backend/api/routes.py` | 分页 API，重试 API，stats 扩展 |
| `backend/main.py` | 启动时调用恢复逻辑 |
| `frontend/index.html` | 分页组件，详情增强（失败/超时/running 显示），重试按钮 |
| `config.yaml` | 新增 heartbeat_interval, max_retries 等配置 |

---

## 第七部分：配置项（config.yaml）

```yaml
scheduler:
  poll_interval: 5
  cli: claude
  heartbeat_interval: 30  # 心跳更新间隔（秒）
  stale_threshold: 120   # 僵尸任务判定（秒）

executor:
  timeout: 1800
  max_auto_retries: 3     # 自动重试次数
  auto_retry_delay: 180   # 自动重试延迟（秒）

log:
  level: INFO
  file: server.log
  max_bytes: 10485760
  backup_count: 5
```

---

## 第八部分：测试要点

1. **心跳恢复**：服务 running 时 kill -9 进程，重启后任务应变 pending
2. **失败重试**：模拟 CLI 失败，验证 failed 状态 + 重试按钮
3. **自动重试**：failed 任务 3 分钟后自动变 pending
4. **分页**：创建 30+ 任务，验证分页正确
5. **running 计时器**：详情打开 running 任务，显示实时计时

---

## 实现顺序

1. database.py（字段 + 分页）
2. config.yaml（新增配置项）
3. executor.py（区分失败类型）
4. scheduler.py（心跳 + 恢复 + 失败处理）
5. routes.py（分页 + 重试 API）
6. main.py（启动恢复调用）
7. frontend（分页 + 详情增强 + 重试按钮）

# AI Task System v2 - 可靠性与 UI 增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现心跳恢复机制、失败重试、任务列表分页、任务详情增强

**Architecture:** 在 database 层新增 heartbeat/retry_count/failed_at 字段；scheduler 增加心跳更新和僵尸任务恢复；API 增加分页和重试端点；前端增加分页组件和详情增强。

**Tech Stack:** Python 3.11+, FastAPI, SQLite (aiosqlite), Tailwind CSS

---

## 文件清单

| 文件 | 职责 |
|------|------|
| `backend/database.py` | 新增字段、分页查询、heartbeat 更新 |
| `backend/config.py` | 新增 heartbeat/stale/retry 配置项 |
| `config.yaml` | 新增配置项 |
| `backend/executor.py` | 区分失败类型（exit_code） |
| `backend/scheduler.py` | 心跳循环、失败处理、自动重试延迟 |
| `backend/api/routes.py` | 分页 API、重试 API、stats 扩展 |
| `backend/main.py` | 启动时恢复僵尸任务 |
| `frontend/index.html` | 分页组件、详情增强、重试按钮 |

---

## Task 1: Database 层修改（字段 + 分页）

**Files:**
- Modify: `backend/database.py`
- Test: `tests/test_database.py`

---

- [ ] **Step 1: 读取现有 database.py 结构**

Run: `cat backend/database.py`

确认 Task 类结构、list_tasks 方法签名、update_task_status 方法

---

- [ ] **Step 2: 添加字段到 Task 类**

在 `backend/database.py` 中 Task 类的 `__init__` 方法后添加：

```python
self.last_heartbeat = row.get("last_heartbeat")
self.retry_count = row.get("retry_count", 0)
self.failed_at = row.get("failed_at")
```

---

- [ ] **Step 3: 修改 CREATE TABLE 语句**

找到 `CREATE TABLE IF NOT EXISTS tasks` 块，在 `status TEXT DEFAULT 'pending',` 后添加：

```sql
last_heartbeat TEXT,
retry_count INTEGER DEFAULT 0,
failed_at TEXT,
```

在 `CREATE TABLE IF NOT EXISTS executions` 中添加：

```sql
exit_code INTEGER,
```

---

- [ ] **Step 4: 修改 list_tasks 方法添加分页**

找到 `async def list_tasks` 方法，添加 page 和 page_size 参数：

```python
async def list_tasks(self, status: str = None, page: int = 1, page_size: int = 20) -> List[Task]:
```

在 SQL WHERE 子句后添加：

```python
# 分页
offset = (page - 1) * page_size
query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
```

---

- [ ] **Step 5: 添加 total_count 方法**

在 `database.py` 中添加：

```python
async def count_tasks(self, status: str = None) -> int:
    """统计任务数量"""
    await self.init()
    sql = "SELECT COUNT(*) as count FROM tasks"
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    async with self.db.execute(sql, params) as cursor:
        row = await cursor.fetchone()
        return row["count"] if row else 0
```

---

- [ ] **Step 6: 添加 heartbeat 更新方法**

添加：

```python
async def update_heartbeat(self, task_id: str):
    """更新任务心跳"""
    await self.init()
    now = datetime.now().isoformat()
    await self.db.execute(
        "UPDATE tasks SET last_heartbeat = ? WHERE id = ?",
        (now, task_id)
    )
    await self.db.commit()

async def batch_update_heartbeat(self, task_ids: List[str]):
    """批量更新任务心跳"""
    if not task_ids:
        return
    await self.init()
    now = datetime.now().isoformat()
    for task_id in task_ids:
        await self.db.execute(
            "UPDATE tasks SET last_heartbeat = ? WHERE id = ?",
            (now, task_id)
        )
    await self.db.commit()
```

---

- [ ] **Step 7: 修改 update_task_status 支持 failed 状态**

找到 `update_task_status` 方法，在 `completed` 处理分支后添加 `failed` 处理：

```python
elif status == "failed":
    await self.db.execute(
        "UPDATE tasks SET status = ?, failed_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), task_id)
    )
```

---

- [ ] **Step 8: 添加 retry_count 更新方法**

添加：

```python
async def increment_retry_count(self, task_id: str):
    """增加重试计数"""
    await self.init()
    await self.db.execute(
        "UPDATE tasks SET retry_count = retry_count + 1 WHERE id = ?",
        (task_id,)
    )
    await self.db.commit()
```

---

- [ ] **Step 9: 添加 reset_task_for_retry 方法**

添加：

```python
async def reset_task_for_retry(self, task_id: str):
    """重置任务以便重试（保留 retry_count）"""
    await self.init()
    await self.db.execute(
        "UPDATE tasks SET status = 'pending', last_heartbeat = NULL WHERE id = ?",
        (task_id,)
    )
    await self.db.commit()
```

---

- [ ] **Step 10: 添加 exit_code 到 execution**

找到 `create_execution` 方法中的 INSERT 语句，添加 `exit_code` 字段（设为 NULL）。

找到 `update_execution` 方法，添加 `exit_code` 参数：

```python
async def update_execution(self, execution_id: str, output: str = None, error: str = None,
                          command: str = None, exit_code: int = None):
```

在 UPDATE 语句中添加 `exit_code = ?` 并传入参数。

---

- [ ] **Step 11: 修改 get_task 加载 executions 时排序**

找到 `get_task` 方法中加载 executions 的 SQL，改为：

```python
async with self.db.execute(
    "SELECT * FROM executions WHERE task_id = ? ORDER BY started_at DESC",
    (task_id,)
) as cursor:
```

---

- [ ] **Step 12: 添加测试验证**

创建 `tests/test_database.py`（如果不存在）或在现有测试文件中添加：

```python
import pytest
from backend.database import Database

@pytest.mark.asyncio
async def test_heartbeat_fields():
    db = Database()
    await db.init()
    
    # 创建任务
    task = await db.create_task(
        title="Test",
        description="Test desc",
        executor_model="claude"
    )
    
    # 更新心跳
    await db.update_heartbeat(task.id)
    
    # 获取任务验证 heartbeat 字段
    loaded = await db.get_task(task.id)
    assert loaded.last_heartbeat is not None
    
    # 重试计数初始为 0
    assert loaded.retry_count == 0

@pytest.mark.asyncio
async def test_list_tasks_pagination():
    db = Database()
    await db.init()
    
    # 创建 5 个任务
    for i in range(5):
        await db.create_task(title=f"Task {i}", description="desc", executor_model="claude")
    
    # 分页查询
    tasks = await db.list_tasks(page=1, page_size=2)
    total = await db.count_tasks()
    
    assert len(tasks) == 2
    assert total == 5
```

---

- [ ] **Step 13: 运行测试**

Run: `source .venv/bin/activate && PYTHONPATH=$(pwd) python -m pytest tests/test_database.py -v`

Expected: PASS（或数据库已存在导致字段缺失，可手动添加字段或重建数据库测试）

---

- [ ] **Step 14: Commit**

```bash
git add backend/database.py tests/test_database.py
git commit -m "feat(database): add heartbeat, retry_count, failed_at fields and pagination"
```

---

## Task 2: 配置项修改

**Files:**
- Modify: `backend/config.py`
- Modify: `config.yaml`

---

- [ ] **Step 1: 更新 DEFAULT_CONFIG**

在 `backend/config.py` 的 `DEFAULT_CONFIG` 字典中添加：

```python
'scheduler': {
    'poll_interval': 5,
    'cli': 'claude',
    'heartbeat_interval': 30,
    'stale_threshold': 120
},
'executor': {
    'timeout': 1800,
    'max_auto_retries': 3,
    'auto_retry_delay': 180
},
```

---

- [ ] **Step 2: 更新 config.yaml**

在 `config.yaml` 中更新：

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
```

---

- [ ] **Step 3: Commit**

```bash
git add backend/config.py config.yaml
git commit -m "feat(config): add heartbeat, stale_threshold, retry config options"
```

---

## Task 3: Executor 改造

**Files:**
- Modify: `backend/executor.py`
- Test: `tests/test_executor.py`

---

- [ ] **Step 1: 读取 executor.py 确认当前结构**

确认 `execute` 和 `_run_sync` 方法签名和返回格式。

---

- [ ] **Step 2: 修改 _run_sync 返回 exit_code**

找到 `_run_sync` 方法，修改返回值为 Tuple[str, Optional[str], str, Optional[int]]：

```python
def _run_sync(self, cmd: str) -> Tuple[str, Optional[str], str, Optional[int]]:
    """同步执行命令（在线程中运行）"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        if result.returncode == 0:
            return result.stdout, None, cmd, result.returncode
        else:
            return result.stdout, result.stderr, cmd, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Execution timeout", cmd, -1
    except Exception as e:
        return "", str(e), cmd, -1
```

---

- [ ] **Step 3: 修改 execute 方法处理 exit_code**

找到 `execute` 方法，修改：

```python
async def execute(self, task_id: str, description: str,
                  feedback_md: Optional[str] = None,
                  model: Optional[str] = None) -> Tuple[str, Optional[str], str, Optional[int]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self._run_sync, self._build_cmd(task_id, description, feedback_md, model))
```

---

- [ ] **Step 4: 更新调用处**

找到 scheduler.py 中调用 `executor.execute` 的地方，修改解包：

```python
output, error, cmd, exit_code = await self.executor.execute(...)
```

---

- [ ] **Step 5: Commit**

```bash
git add backend/executor.py
git commit -m "feat(executor): return exit_code for failure detection"
```

---

## Task 4: Scheduler 改造（心跳 + 失败处理 + 自动重试）

**Files:**
- Modify: `backend/scheduler.py`
- Test: `tests/test_scheduler.py`

---

- [ ] **Step 1: 添加心跳和超时判断辅助函数**

在 scheduler.py 顶部 `logger = get_logger(__name__)` 后添加：

```python
def is_heartbeat_stale(last_heartbeat: str, threshold: int = 120) -> bool:
    """判断心跳是否超时"""
    if not last_heartbeat:
        return True
    last = datetime.fromisoformat(last_heartbeat)
    return (datetime.now() - last).total_seconds() > threshold
```

---

- [ ] **Step 2: 修改 __init__ 读取新配置**

修改 `__init__` 方法：

```python
def __init__(self, poll_interval: int = None, cli: str = None):
    config = load_config()
    scheduler_config = config.get('scheduler', {})
    self.poll_interval = poll_interval or scheduler_config.get('poll_interval', 5)
    self.cli = cli or scheduler_config.get('cli', 'claude')
    self.heartbeat_interval = scheduler_config.get('heartbeat_interval', 30)
    self.stale_threshold = scheduler_config.get('stale_threshold', 120)
    executor_config = config.get('executor', {})
    self.max_auto_retries = executor_config.get('max_auto_retries', 3)
    self.auto_retry_delay = executor_config.get('auto_retry_delay', 180)
    self._running = False
    self._task = None
    self._heartbeat_task = None
    self.db = Database()
    self.executor = Executor(cli=self.cli)
    self.evaluator = Evaluator()
```

---

- [ ] **Step 3: 修改 start 方法启动心跳循环**

修改 `start` 方法：

```python
async def start(self):
    logger.info(f"调度器启动 | CLI: {self.cli} | 轮询间隔: {self.poll_interval}s")
    self._running = True
    self._task = asyncio.create_task(self._poll_loop())
    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    return {"status": "started"}
```

---

- [ ] **Step 4: 修改 stop 方法停止心跳循环**

修改 `stop` 方法：

```python
async def stop(self):
    logger.info("调度器停止")
    self._running = False
    if self._task:
        self._task.cancel()
    if self._heartbeat_task:
        self._heartbeat_task.cancel()
    return {"status": "stopped"}
```

---

- [ ] **Step 5: 添加心跳循环方法**

添加：

```python
async def _heartbeat_loop(self):
    """心跳更新循环"""
    await self.db.init()
    while self._running:
        try:
            running_tasks = await self.db.list_tasks(status="running")
            if running_tasks:
                task_ids = [t.id for t in running_tasks]
                await self.db.batch_update_heartbeat(task_ids)
                logger.debug(f"心跳更新: {len(task_ids)} 个 running 任务")
        except Exception as e:
            logger.error(f"心跳更新异常: {e}")
        await asyncio.sleep(self.heartbeat_interval)
```

---

- [ ] **Step 6: 修改 _execute_task 判断失败**

找到 `_execute_task` 方法中执行完成后的处理，修改为：

```python
await self.db.update_execution(execution.id, output, error, command=cmd, exit_code=exit_code)

# 判断状态
if exit_code is None or exit_code == -1:  # 超时或异常
    await self.db.update_task_status(task.id, "completed", result=output)
    logger.info(f"{task_info} | 执行完成 | 输出长度: {len(output) if output else 0} 字符")
    if error:
        logger.warning(f"{task_info} | 错误: {error[:200]}")
elif exit_code != 0:  # CLI 执行失败
    await self.db.update_task_status(task.id, "failed", result=output)
    await self.db.increment_retry_count(task.id)
    await self.db.update_execution(execution.id, output, error, command=cmd, exit_code=exit_code)
    logger.warning(f"{task_info} | 执行失败 | exit_code: {exit_code} | 错误: {error[:200] if error else '无'}")
else:  # 成功
    await self.db.update_task_status(task.id, "completed", result=output)
    logger.info(f"{task_info} | 执行完成 | 输出长度: {len(output) if output else 0} 字符")

# 评估（仅成功或超时的任务，失败的不评估）
if exit_code != 0 and exit_code != -1:
    # 失败任务不评估，等待重试
    await self._handle_failed_task(task)
else:
    await self._evaluate_task(task, execution, output)
```

---

- [ ] **Step 7: 添加 _handle_failed_task 方法**

添加：

```python
async def _handle_failed_task(self, task):
    """处理失败任务"""
    task_info = f"[{task.id}] {task.title}"
    
    # 检查是否超过最大重试次数
    loaded_task = await self.db.get_task(task.id)
    if loaded_task.retry_count >= self.max_auto_retries:
        logger.warning(f"{task_info} | 超过最大重试次数({self.max_auto_retries})，保持 failed 状态")
        # 发送通知（后续扩展）
    else:
        logger.info(f"{task_info} | {self.auto_retry_delay}秒后自动重试...")
        # 延迟后自动变 pending（实际用简单轮询处理）
        asyncio.create_task(self._delayed_retry(task.id))
```

---

- [ ] **Step 8: 添加 _delayed_retry 方法**

添加：

```python
async def _delayed_retry(self, task_id: str):
    """延迟重试"""
    await asyncio.sleep(self.auto_retry_delay)
    try:
        task = await self.db.get_task(task_id)
        if task and task.status == "failed":
            await self.db.reset_task_for_retry(task_id)
            logger.info(f"[{task_id}] 自动重试，状态已重置为 pending")
    except Exception as e:
        logger.error(f"延迟重试异常: {e}")
```

---

- [ ] **Step 9: 添加 recover_stale_tasks 公共方法**

添加：

```python
async def recover_stale_tasks(self):
    """恢复僵尸任务（心跳超时）"""
    await self.db.init()
    running_tasks = await self.db.list_tasks(status="running")
    recovered = 0
    for task in running_tasks:
        if is_heartbeat_stale(task.last_heartbeat, self.stale_threshold):
            await self.db.update_task_status(task.id, "pending")
            logger.warning(f"任务 [{task.id}] 心跳超时，标记为 pending")
            recovered += 1
    return recovered
```

---

- [ ] **Step 10: Commit**

```bash
git add backend/scheduler.py
git commit -m "feat(scheduler): add heartbeat mechanism, failed state, auto-retry"
```

---

## Task 5: API Routes 改造（分页 + 重试 + stats 扩展）

**Files:**
- Modify: `backend/api/routes.py`
- Test: `tests/test_api.py`

---

- [ ] **Step 1: 修改 GET /api/tasks 添加分页**

找到 `GET /api/tasks` 处理器，修改：

```python
@router.get("/tasks")
async def list_tasks(status: str = None, page: int = 1, page_size: int = 20):
    tasks = await db.list_tasks(status=status, page=page, page_size=page_size)
    total = await db.count_tasks(status=status)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return {
        "tasks": [task.to_dict() for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }
```

注意：`to_dict()` 需要添加到 Task 类，或者直接返回字典。检查现有实现选择合适方式。

---

- [ ] **Step 2: 修改 GET /api/stats 添加 failed 数量**

找到 `GET /api/stats` 处理器，修改：

```python
@router.get("/stats")
async def get_stats():
    total = await db.count_tasks()
    pending = await db.count_tasks(status="pending")
    running = await db.count_tasks(status="running")
    completed = await db.count_tasks(status="completed")
    failed = await db.count_tasks(status="failed")
    return {
        "total": total,
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed
    }
```

---

- [ ] **Step 3: 添加 POST /api/tasks/{id}/retry**

添加：

```python
@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("failed", "completed"):
        raise HTTPException(status_code=400, detail=f"Cannot retry task with status: {task.status}")
    
    await db.reset_task_for_retry(task_id)
    return {"status": "ok", "message": "Task reset to pending"}
```

---

- [ ] **Step 4: 添加 POST /api/tasks/recover**

添加：

```python
@router.post("/tasks/recover")
async def recover_tasks():
    """恢复所有僵尸任务"""
    scheduler = Scheduler()
    recovered = await scheduler.recover_stale_tasks()
    return {"status": "ok", "recovered": recovered}
```

---

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes.py
git commit -m "feat(api): add pagination, retry endpoint, failed stats"
```

---

## Task 6: Main.py 启动恢复

**Files:**
- Modify: `backend/main.py`

---

- [ ] **Step 1: 读取 main.py 确认启动逻辑**

确认 `on_event("startup")` 或 lifespan 写法。

---

- [ ] **Step 2: 添加启动恢复调用**

在 startup 事件或 lifespan 中添加：

```python
@app.on_event("startup")
async def startup_event():
    # ... 现有代码 ...
    
    # 恢复僵尸任务
    from backend.scheduler import Scheduler
    scheduler = Scheduler()
    recovered = await scheduler.recover_stale_tasks()
    if recovered > 0:
        logger.info(f"启动时恢复 {recovered} 个僵尸任务")
```

---

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat(main): recover stale tasks on startup"
```

---

## Task 7: 前端 UI 增强

**Files:**
- Modify: `frontend/index.html`

---

- [ ] **Step 1: 添加分页组件到任务列表**

在任务列表下方添加分页控件（id="pagination-controls"）：

```html
<div id="pagination-controls" class="flex justify-center items-center gap-2 mt-4">
    <button id="btn-prev" onclick="changePage(-1)" class="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 disabled:opacity-50" disabled>上一页</button>
    <span id="page-info" class="text-sm text-gray-600">第 1 页 / 共 1 页</span>
    <button id="btn-next" onclick="changePage(1)" class="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 disabled:opacity-50" disabled>下一页</button>
</div>
```

---

- [ ] **Step 2: 添加全局变量管理分页状态**

在 `<script>` 顶部添加：

```javascript
let currentPage = 1;
let totalPages = 1;
let currentPageSize = 20;
```

---

- [ ] **Step 3: 修改 loadTasks 函数支持分页**

修改 `loadTasks` 函数：

```javascript
async function loadTasks(filter) {
    filter = filter || 'all';
    currentFilter = filter;
    currentPage = 1;  // 切换筛选时重置到第1页
    try {
        const params = new URLSearchParams({status: filter === 'all' ? '' : filter, page: currentPage, page_size: currentPageSize});
        const res = await fetch(`${API_BASE}/tasks?${params}`);
        const data = await res.json();
        renderTaskList(data.tasks || []);
        totalPages = data.total_pages || 1;
        updatePagination();
    } catch (e) { console.error('Failed to load tasks:', e); }
}

function updatePagination() {
    document.getElementById('page-info').textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= totalPages;
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage < 1 || newPage > totalPages) return;
    currentPage = newPage;
    loadTasks(currentFilter);
}
```

---

- [ ] **Step 4: 修改 setFilter 重置分页**

在 `setFilter` 函数开头添加 `currentPage = 1;` 或直接依赖 `loadTasks` 的处理。

---

- [ ] **Step 5: 添加 failed 状态显示**

在 `getStatusClass` 和 `getStatusText` 中添加 failed：

```javascript
'failed': 'bg-red-100 text-red-800'
```

```javascript
'failed': '失败'
```

---

- [ ] **Step 6: 修改任务卡片显示 retry_count**

在卡片渲染时，如果任务有 retry_count > 0，显示尝试次数：

```javascript
if (task.retry_count > 0) {
    metaDiv.appendChild(createEl('span', 'text-orange-500 text-xs ml-2', `(第${task.retry_count}次尝试)`));
}
```

---

- [ ] **Step 7: 添加重试按钮到任务详情**

在详情弹窗底部操作区添加重试按钮（当状态为 failed 或 completed 时）：

```javascript
// 在 closeModal 按钮后添加
if (task.status === 'failed' || task.status === 'completed') {
    const retryBtn = createEl('button', 'px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700');
    retryBtn.onclick = () => retryTask(task.id);
    retryBtn.textContent = '🔄 重试此任务';
    // 添加到操作区
}
```

---

- [ ] **Step 8: 添加 retryTask 函数**

添加：

```javascript
async function retryTask(taskId) {
    if (!confirm('确定要重试这个任务吗？')) return;
    try {
        await fetch(`${API_BASE}/tasks/${taskId}/retry`, { method: 'POST' });
        closeModal();
        loadTasks();
        loadStats();
    } catch (e) {
        console.error('Failed to retry task:', e);
        alert('重试失败');
    }
}
```

---

- [ ] **Step 9: 增强 running 任务详情显示计时器**

在 showTaskDetail 中，如果任务状态是 running，显示计时器：

```javascript
if (task.status === 'running') {
    const startTime = task.started_at ? new Date(task.started_at) : new Date();
    const timerDiv = createEl('div', 'text-blue-600 font-medium mt-2');
    timerDiv.id = 'running-timer';
    // 计时器逻辑
    function updateTimer() {
        const elapsed = Math.floor((new Date() - startTime) / 1000);
        const mins = Math.floor(elapsed / 60);
        const secs = elapsed % 60;
        timerDiv.textContent = `已运行: ${mins}分${secs}秒`;
    }
    updateTimer();
    setInterval(updateTimer, 1000);
    // 添加到详情
}
```

---

- [ ] **Step 10: 增强 failed 任务详情显示错误**

在 showTaskDetail 的执行历史部分，检查 error 字段并高亮显示：

```javascript
if (ex.error) {
    const errorP = createEl('p', 'text-red-600 bg-red-50 p-2 rounded mt-1');
    errorP.textContent = `错误: ${ex.error}`;
    execCard.appendChild(errorP);
}
```

---

- [ ] **Step 11: 添加迭代进度可视化**

在详情基本信息区添加迭代进度条：

```javascript
const iterationP = createEl('p', '', [createEl('strong', '', '迭代: ')]);
const progressBar = createEl('div', 'inline-flex items-center gap-2 ml-2');
const filled = '█'.repeat(task.iteration_count || 0);
const empty = '░'.repeat((task.max_iterations || 3) - (task.iteration_count || 0));
progressBar.appendChild(createEl('span', 'text-orange-600', filled + empty));
progressBar.appendChild(createEl('span', '', `${task.iteration_count || 0}/${task.max_iterations || 3}`));
iterationP.appendChild(progressBar);
```

---

- [ ] **Step 12: Commit**

```bash
git add frontend/index.html
git commit -m "feat(frontend): add pagination, failed state display, retry button, running timer"
```

---

## 实施检查清单

- [ ] Task 1: database.py 修改完成
- [ ] Task 2: config.yaml 修改完成
- [ ] Task 3: executor.py 修改完成
- [ ] Task 4: scheduler.py 修改完成
- [ ] Task 5: routes.py 修改完成
- [ ] Task 6: main.py 修改完成
- [ ] Task 7: frontend/index.html 修改完成
- [ ] 手动测试：kill -9 进程模拟崩溃，验证任务恢复
- [ ] 手动测试：创建失败任务，验证重试按钮
- [ ] 手动测试：创建 25+ 任务，验证分页

---

## 实现顺序建议

按 Task 1 → 2 → 3 → 4 → 5 → 6 → 7 顺序执行。

# AI Task System v2.4

## 新特性

- **页面交互式人工确认**：填空式 + 连续会话，executor 格式化输出结构化确认请求
- **实时进度展示**：流式输出 + WebSocket 推送 + 运行时长显示
- **提前结束任务**：SIGKILL 真正杀掉子进程，支持终止按钮
- **服务重启兜底**：僵尸任务检测与恢复，心跳机制

## 架构

- **FastAPI** 后端 + WebSocket 实时推送
- **aiosqlite** 异步数据库
- **RetryExecutor** 指数退避重试
- **Scheduler** 并发控制 + 心跳 + stale 检测

## 启动

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

## API

- `POST /api/tasks` - 创建任务
- `GET /api/tasks` - 列表任务
- `GET /api/tasks/{id}` - 任务详情
- `POST /api/tasks/{id}/cancel` - 取消任务（SIGKILL）
- `POST /api/tasks/{id}/submit_input` - 提交人工输入
- `GET /api/stats` - 统计
- `WS /ws` - WebSocket 实时推送
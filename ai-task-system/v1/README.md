# 🤖 AI Task Pickup System

个人 AI 领取任务系统 - 自动从任务池领取任务并执行，支持评估。

## 功能特性

- ✅ **任务池管理** - 添加、删除、查看任务
- ✅ **AI 自动领取** - AI 自动从池子里领取任务并执行
- ✅ **Claude Code 执行** - 通过 Claude Code CLI 执行代码开发和文档分析任务
- ✅ **自动评估** - 执行完成后自动评估质量和效率
- ✅ **可视化页面** - Web 界面查看任务状态、执行日志和评估结果
- ✅ **多 Agent 并行** - 支持多个 AI 同时工作

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 3. 运行

```bash
python main.py
```

或使用 uvicorn：

```bash
uvicorn main:app --reload --port 8000
```

### 4. 打开页面

浏览器访问 http://localhost:8000

## 使用方法

### 添加任务

1. 点击 "+ Add Task" 按钮
2. 填写任务标题、描述
3. 选择任务类型：
   - `Code Development` - 代码开发任务
   - `Document Summary` - 文档分析总结任务
4. 选择优先级
5. 点击 "Create"

### 手动执行任务

1. 点击任务卡片的 "▶ Execute" 按钮
2. 等待执行完成
3. 查看执行日志和评估结果

### 启动自动领取

1. 点击 "Start Scheduler"
2. AI 会自动检测任务池，每 60 秒检查一次
3. 有新任务时自动领取并执行
4. 执行完成后自动评估

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tasks` | GET | 列出所有任务 |
| `/api/tasks` | POST | 创建新任务 |
| `/api/tasks/{id}` | GET | 获取任务详情 |
| `/api/tasks/{id}` | DELETE | 删除任务 |
| `/api/tasks/{id}/execute` | POST | 手动执行任务 |
| `/api/tasks/{id}/evaluate` | POST | 手动评估任务 |
| `/api/scheduler/status` | GET | 获取调度器状态 |
| `/api/scheduler/start` | POST | 启动调度器 |
| `/api/scheduler/stop` | POST | 停止调度器 |
| `/api/scheduler/trigger` | POST | 触发一次领取 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TASK_DB_PATH` | `tasks.db` | SQLite 数据库路径 |
| `TASK_WORKSPACE_DIR` | `./workspace` | 任务执行工作目录 |
| `SCHEDULER_INTERVAL` | `60` | 调度器检查间隔（秒） |
| `NUM_AGENTS` | `2` | 并行 Agent 数量 |
| `ANTHROPIC_API_KEY` | - | Anthropic API Key |
| `ANTHROPIC_BASE_URL` | - | API 地址（如使用代理） |
| `PORT` | `8000` | 服务端口 |

## 技术栈

- **后端**: FastAPI + Python
- **数据库**: SQLite
- **Agent**: Claude Code CLI
- **评估**: MiniMax API / 简单评估器

## 项目结构

```
ai_task_system/
├── main.py          # FastAPI 应用入口
├── models.py        # 数据模型
├── database.py      # 数据库操作
├── executor.py      # 任务执行器
├── evaluator.py     # 任务评估器
├── scheduler.py     # 自动领取调度器
├── static/          # 静态文件
├── templates/       # 模板文件
├── requirements.txt
├── .env.example
└── README.md
```

## 注意事项

1. 需要安装 Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
2. 确保 `claude` 命令在 PATH 中
3. 评估功能可选，不填 API Key 也能用简单评估器

---

_Built with OpenClaw AI Task System_

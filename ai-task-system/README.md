# AI Task System V4/V5

> Unified multi-agent CLI orchestration layer for Claude Code, OpenAI Codex, and CodeBuddy.

**V4** — Multi-agent abstraction layer (CLI / TUI / REPL)
**V5** — Production-grade worker pool, persistent queue, REST API, WebSocket, Prometheus metrics

---

## 目录

- [特性](#特性)
- [架构](#架构)
- [安装](#安装)
- [快速开始](#快速开始)
- [CLI 参考](#cli-参考)
- [TUI 参考](#tui-参考)
- [REPL 参考](#repl-参考)
- [REST API](#rest-api)
- [配置](#配置)
- [测试](#测试)
- [文件结构](#文件结构)

---

## 特性

### V4 — 多 Agent 抽象层

| 特性 | 说明 |
|------|------|
| **统一适配器** | Claude Code / Codex / CodeBuddy 三合一接口 |
| **CLI 入口** | 10+ 子命令，非交互式脚本支持 |
| **TUI 入口** | Textual 全屏界面，实时任务监控 |
| **REPL 入口** | 交互式命令行，直接输入任务 |
| **任务路由** | 13 种任务类型 → 最优 Agent 自动选择 |
| **基准测试** | Agent 能力评分，持续跟踪对比 |
| **会话持久化** | 跨会话恢复，session export/import |
| **无输出超时** | 卡死检测，自动终止 |
| **错误重试** | 指数退避，最多重试 3 次 |

### V5 — 生产级架构

| 特性 | 说明 |
|------|------|
| **进程池** | 预热 Worker，故障自动恢复 |
| **持久化队列** | SQLite WAL，支持优先级 / 延迟 / 死信 |
| **REST API** | 18 个端点，API Key 认证 |
| **WebSocket** | 实时任务状态 / 输出流推送 |
| **Prometheus** | `/metrics` 端点，Grafana 就绪 |
| **Supervisor** | 心跳检测，无输出监控，自动重启 |

---

## 架构

```
ai_task_system/
├── v4/                          # V4 多 Agent 抽象层
│   ├── cli.py                   # CLI 入口（14 个子命令）
│   ├── tui.py                   # Textual TUI（全屏 UI）
│   ├── repl.py                  # Interactive REPL
│   ├── core/
│   │   ├── base.py              # AgentAdapter 抽象基类 + 数据模型
│   │   ├── command_builder.py   # 统一命令构建器
│   │   ├── executor.py         # 统一执行器 + NoOutputWatcher
│   │   ├── router.py           # 任务路由器（13 种任务类型）
│   │   ├── session_store.py    # 会话持久化
│   │   ├── retry.py           # 指数退避重试
│   │   ├── benchmark/         # Agent 基准测试套件
│   │   └── benchmark_scores.py # 基准分数数据库
│   └── adapters/
│       ├── claude_adapter.py    # Claude Code（15 项能力）
│       ├── codex_adapter.py     # OpenAI Codex（11 项能力）
│       └── codebuddy_adapter.py # CodeBuddy（5 项能力）
├── v5/                          # V5 生产级架构
│   ├── worker/
│   │   ├── pool.py            # Worker 进程池
│   │   └── supervisor.py     # 健康监护
│   ├── queue/
│   │   └── queue.py          # SQLite 持久化队列
│   ├── api/
│   │   ├── app.py            # FastAPI REST API
│   │   ├── websocket.py      # WebSocket 实时推送
│   │   └── metrics.py        # Prometheus Metrics
│   └── integration/
│       └── session_pool.py   # V4×V5 集成 Facade
└── tests/                     # 测试套件（136 测试）
```

### Agent 命令行参数支持矩阵

| 功能 | Claude Code | Codex | CodeBuddy |
|------|-------------|-------|-----------|
| 无头模式 | `--print` | `exec` | `-p` |
| 跳过确认 | `--dangerously-skip-permissions` | `--full-auto` | `-y` |
| 工具白名单 | `--allowed-tools` | ❌ | `--allowedTools` |
| 结构化输出 | `--json-schema` | `--output-schema` | `--output-format` |
| 输出格式 | `--output-format` | `--json` | `--output-format` |
| 会话恢复 | `--resume` | ❌ | `--resume` |
| 模型选择 | `--model` | `-m` | ❌ |
| 预算控制 | `--max-budget-usd` | ❌ | ❌ |
| Bare 模式 | `--bare` | ❌ | ❌ |
| 工作目录 | `--add-dir` | `-C` | cwd |

---

## 安装

### 前置依赖

```bash
# Python 3.10+
python3 --version

# 至少安装一个 Agent（推荐 Claude Code）
# https://github.com/anthropics/claude-code
npm install -g @anthropic-ai/claude-code  # 或 brew 安装

# 可选：其他 Agent
# Codex: https://openai.com/codex
# CodeBuddy: https://codebuddy.com
```

### 方式 1：符号链接（推荐开发用）

```bash
cd /root/.openclaw/workspace
ln -s ai-task-system ai_task_system   # 已有则跳过

# 验证
python3 -m ai_task_system.v4.cli agents
```

### 方式 2：PYTHONPATH

```bash
export PYTHONPATH=/root/.openclaw/workspace:$PYTHONPATH
python3 -m ai_task_system.v4.cli agents
```

### 方式 3：pip 安装

```bash
cd /root/.openclaw/workspace/ai-task-system
pip install -e .
```

---

## 快速开始

### 1. 查看 Agent 状态

```bash
python3 -m ai_task_system.v4.cli agents
```

```
Agent           Available    Capabilities
--------------------------------------------------------------------------------
claude          ✅ Available  SKIP_PERMISSIONS, AUTO_PERMISSIONS, ...
codex           ❌ not found in PATH
codebuddy       ❌ not found in PATH
```

### 2. 创建任务（CLI）

```bash
# 基础执行
python3 -m ai_task_system.v4.cli create "帮我写一个快速排序函数" -a claude -y -w

# 仅显示命令（不执行）
python3 -m ai_task_system.v4.cli show-cmd "帮我写一个快速排序函数" -a claude -y

# 等待结果
python3 -m ai_task_system.v4.cli create "say hello world" -a claude -y -w
```

### 3. 创建任务（TUI，全屏界面）

```bash
python3 -m ai_task_system.v4 --tui
# 或
python3 -m ai_task_system.v4.tui
```

### 4. 创建任务（REPL，交互式）

```bash
python3 -m ai_task_system.v4
# 或直接
python3 -m ai_task_system.v4 --repl
```

```
🤖 AI Task System V4 — Interactive REPL
Type 'help' for commands, or enter a task directly.
Type '\' for line continuation.

ai-task> 帮我写一个斐波那契函数
🤖 Agent: claude (routed: CODING)
⏱  Timeout: 600s | No-output: 120s
▶ Executing...
...
```

### 5. 路由决策（不执行）

```bash
python3 -m ai_task_system.v4.cli route "帮我用 GitHub Actions 写 CI 流水线" --explain
```

```
📋 任务分类: DEVOPS
📌 匹配规则: DEVOPS
   说明: DevOps 任务，Claude Code 熟悉 YAML 和 Shell
   优先 Agent: ['claude', 'codex']
   推荐超时: 600s

🔍 Agent 可用性:
   claude: ✅ 可用

📊 基准分数: （基准数据：claude=0.72, codex=0.55）

✅ 最终选择: claude
   置信度: 60%
   原因: Rule match: DEVOPS
```

### 6. 启动 REST API

```bash
# 设置 API Key（可选，启用认证）
export AI_TASK_API_KEY="my-secret-key"

# 启动
python3 -m v5.api.app --host 0.0.0.0 --port 18792

# 或用 uvicorn
uvicorn v5.api:app --host 0.0.0.0 --port 18792
```

---

## CLI 参考

### 全局命令

```bash
python3 -m ai_task_system.v4.cli <command>

# 无参数 → 进入 REPL 模式
python3 -m ai_task_system.v4

# TUI 模式
python3 -m ai_task_system.v4 --tui
```

### 子命令

| 命令 | 说明 |
|------|------|
| `agents` | 列出所有 Agent 及其可用状态 |
| `show-cmd <prompt>` | 显示执行命令（不执行） |
| `create <prompt>` | 创建并执行任务 |
| `list` | 列出所有任务 |
| `status <task-id>` | 查看任务状态 |
| `stop <task-id>` | 停止运行中的任务 |
| `sessions` | 会话管理（list/get/archive/delete/stats） |
| `sessions log <id>` | 查看会话历史 |
| `sessions export <id>` | 导出会话到 JSON |
| `sessions import <file>` | 从 JSON 导入会话 |
| `route <prompt>` | 任务路由决策 |
| `retry <prompt>` | 错误重试执行 |
| `benchmark` | Agent 能力基准测试 |
| `scores` | 基准分数管理（show/compare/load/clear） |

### create 命令选项

```bash
python3 -m ai_task_system.v4.cli create "任务描述" \
    -a {claude,codex,codebuddy}  # 指定 Agent（默认：自动选择）
    -y                           # 跳过所有确认（等同于 --skip-permissions）
    -w                           # 等待结果（默认：不等待，立即返回）
    -t <seconds>                 # 超时时间（默认：600）
    --no-output-timeout <sec>   # 无输出超时（默认：timeout/2）
    --tools <tool1,tool2>       # 允许的工具白名单
    --output-format {text,json,stream-json}  # 输出格式
    --model <name>              # 指定模型
    --bare                       # Bare 模式（跳过 CLAUDE.md 发现）
    --resume <session-id>        # 恢复指定会话
    --no-commit                  # 禁用 Git 自动提交
    --verbose                    # 详细输出
    -f {text,json}              # 输出格式（简写）
```

### 任务类型分类（13 种）

| 类型 | 说明 | 优先 Agent |
|------|------|-----------|
| `CODING` | 通用编码 | Claude > Codex |
| `DEBUGGING` | Bug 修复 | Claude > Codex |
| `REFACTORING` | 代码重构 | Claude > Codex |
| `ARCHITECTURE` | 架构设计 | Claude |
| `CODE_REVIEW` | 代码审查 | Claude > Codex |
| `RESEARCH` | 技术研究 | Claude |
| `LEARNING` | 学习辅导 | Claude |
| `WRITING` | 写作/文档 | Claude |
| `TRANSLATION` | 翻译 | Claude |
| `DEVOPS` | DevOps 任务 | Claude > Codex |
| `INFRA` | 基础设施 | Claude > Codex |
| `DATA_SCRIPT` | 数据脚本 | Claude > Codex |
| `QUERY` | 查询/分析 | Claude > Codex |

---

## TUI 参考

### 启动

```bash
python3 -m ai_task_system.v4 --tui
# 或
python3 -m ai_task_system.v4.tui
```

### 布局

```
┌────────────────────────────────────────────────────────────────────┐
│  🤖 AI Task System V4                      Agent: Claude Code ▼   │
├────────────────────┬─────────────────────────────────────────────┤
│  Agent Selector    │  Tasks        Output Log                    │
│  ○ Claude Code     │  ▶ task-001  │  Starting...                 │
│  ○ Codex           │  task-002 ✅  │  Thinking...                  │
│  ○ CodeBuddy       │  task-003 ❌  │  Done.                       │
├────────────────────┴─────────────────────────────────────────────┤
│  > Enter task...                        [Execute]                  │
│  [✓ Skip permissions]  [Resume session]                           │
└────────────────────────────────────────────────────────────────────┘
```

### 快捷键

| 快捷键 | 动作 |
|--------|------|
| `Enter` | 执行任务 |
| `↑ / ↓` | 选择任务 |
| `Ctrl+N` | 聚焦输入框 |
| `Ctrl+L` | 清空日志 |
| `Ctrl+R` | 重试选中任务 |
| `Ctrl+Q` | 退出 |

### 功能

- 左右分栏：任务列表 + 实时输出日志
- Agent 选择器（RadioSet）：Auto / Claude / Codex / CodeBuddy
- 实时 ProgressBar（显示执行时间）
- 无输出警告（⚠️ 实时提示）
- 任务状态持久化（`~/.ai_task_system/tui_tasks.json`）

---

## REPL 参考

### 启动

```bash
python3 -m ai_task_system.v4
```

### 命令

| 命令 | 说明 |
|------|------|
| `<prompt>` | 直接输入任务，自动路由执行 |
| `run <prompt>` | 显式执行 |
| `agents` | 列出 Agent 状态 |
| `route <prompt>` | 显示路由决策（不执行） |
| `sessions` | 列出 active 会话 |
| `session <id>` | 设置当前会话（用于 resume） |
| `status <task-id>` | 查看任务状态 |
| `set --agent claude` | 设置默认 Agent |
| `set --timeout 300` | 设置默认超时 |
| `set -y` | 启用 skip-permissions |
| `unset --session` | 清除当前会话 |
| `clear` | 清屏 |
| `quit / exit` | 退出 |

### 功能

- Arrow key 命令历史
- Tab 命令补全
- 多行输入（`\` 续行）
- 自动路由 + 会话管理
- readline 历史持久化

---

## REST API

### 启动

```bash
export AI_TASK_API_KEY="my-secret-key"  # 可选
python3 -m v5.api.app --port 18792
```

API 文档：`http://localhost:18792/docs`（Swagger UI）

### 认证

```bash
# 所有受保护端点需要 X-API-Key header
curl -X POST http://localhost:18792/tasks \
  -H "X-API-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "say hello", "agent": "claude", "timeout": 30}'
```

### 端点一览

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/health` | GET | 健康检查 | ❌ |
| `/info` | GET | 系统信息 | ❌ |
| `/metrics` | GET | Prometheus metrics | ❌ |
| `/route` | POST | 任务路由决策 | ✅ |
| `/tasks` | POST | 提交任务 | ✅ |
| `/tasks` | GET | 任务列表 | ✅ |
| `/tasks/{id}` | GET | 任务详情 | ✅ |
| `/tasks/{id}` | DELETE | 删除任务 | ✅ |
| `/tasks/{id}/fail` | POST | 标记失败 | ✅ |
| `/tasks/{id}/retry` | POST | 重试任务 | ✅ |
| `/queue/metrics` | GET | 队列指标 | ✅ |
| `/workers` | GET | Worker 列表 | ✅ |
| `/workers/{id}` | GET | Worker 详情 | ✅ |
| `/workers/{id}/restart` | POST | 重启 Worker | ✅ |
| `/supervisor/metrics` | GET | Supervisor 指标 | ✅ |
| `/sessions` | GET | 会话列表 | ✅ |
| `/sessions/{id}` | GET | 会话详情 | ✅ |
| `/sessions/{id}/archive` | POST | 归档会话 | ✅ |
| `/sessions/{id}/note` | POST | 更新备注 | ✅ |
| `/sessions/{id}` | DELETE | 删除会话 | ✅ |
| `/sessions/stats` | GET | 会话统计 | ✅ |
| `/ws` | WS | WebSocket 实时推送 | — |

### WebSocket

```javascript
// 连接（带 API Key）
const ws = new WebSocket('ws://localhost:18792/ws?token=my-secret-key');

// 订阅
ws.send(JSON.stringify({type: 'subscribe_all'}));
ws.send(JSON.stringify({type: 'subscribe_task', task_id: 'xxx'}));

// 接收事件
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  switch (msg.type) {
    case 'task_output':  console.log('[stdout]', msg.data.line); break;
    case 'task_status':  console.log('[status]', msg.data.status); break;
    case 'task_complete': console.log('[done]', msg.data.status); break;
    case 'worker_health': console.log('[worker]', msg.data.health_status); break;
    case 'session_update': console.log('[session]', msg.data.session); break;
  }
};
```

### Prometheus 配置

```yaml
scrape_configs:
  - job_name: 'ai-task-system'
    static_configs:
      - targets: ['localhost:18792']
    metrics_path: '/metrics'
```

---

## 配置

### 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `AI_TASK_API_KEY` | REST API 认证 Key（逗号分隔多个） | 无（认证禁用） |
| `PYTHONPATH` | Python 模块搜索路径 | — |

### 配置文件（规划中）

```yaml
# ~/.ai_task_system/config.yaml（未来版本）
defaults:
  agent: claude
  timeout: 600
  skip_permissions: true
  output_format: text

api:
  host: 0.0.0.0
  port: 18792
  api_key: ${AI_TASK_API_KEY}

pool:
  size: 2
  agent: claude
```

### 数据目录

| 内容 | 路径 |
|------|------|
| 会话存储 | `~/.ai_task_system/sessions.json` |
| TUI 任务 | `~/.ai_task_system/tui_tasks.json` |
| 基准分数 | `~/.ai_task_system/benchmark_scores.json` |
| 任务队列 DB | `~/.ai_task_system/tasks.db` |
| REPL 历史 | `~/.ai_task_system/repl_history` |

---

## 测试

### 运行全部测试

```bash
cd /root/.openclaw/workspace
PYTHONPATH=/root/.openclaw/workspace python3 -m pytest ai-task-system/tests/ -v
```

### 运行特定模块测试

```bash
PYTHONPATH=/root/.openclaw/workspace python3 -m pytest ai-task-system/tests/test_router.py -v
PYTHONPATH=/root/.openclaw/workspace python3 -m pytest ai-task-system/tests/test_adapters.py -v
```

### 测试覆盖

| 模块 | 测试数 |
|------|--------|
| Adapters | 29 |
| Router | 16 |
| SessionStore | 14 |
| Queue | 13 |
| Executor | 11 |
| Retry | 10 |
| Benchmark | 8 |
| CommandBuilder | 8 |
| CLI | 18 |
| **总计** | **136** |

---

## 文件结构

```
ai-task-system/
├── README.md              # 本文档
├── v4/
│   ├── __init__.py        # 包入口
│   ├── __main__.py        # python -m ai_task_system.v4 入口
│   ├── cli.py             # CLI 入口（956 行）
│   ├── tui.py             # TUI 入口（Textual）
│   ├── tui_app.py         # TUI 模块化版本
│   ├── repl.py            # REPL 入口（670 行）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base.py               # AgentAdapter 抽象 + 数据模型
│   │   ├── command_builder.py    # 跨 Agent 命令映射
│   │   ├── executor.py          # 执行器 + NoOutputWatcher
│   │   ├── router.py           # 任务路由器
│   │   ├── session_store.py    # 会话持久化
│   │   ├── retry.py           # 重试策略
│   │   ├── benchmark.py       # 基准测试入口
│   │   ├── benchmark_scores.py # 基准分数 DB
│   │   └── benchmark/          # 基准测试子包
│   │       ├── __init__.py
│   │       ├── tasks.py        # 标准任务集（15 个任务）
│   │       ├── runner.py       # 基准测试执行器
│   │       ├── db.py           # SQLite 分数存储
│   │       └── result.py       # 结果模型
│   └── adapters/
│       ├── __init__.py
│       ├── claude_adapter.py    # Claude Code
│       ├── codex_adapter.py     # OpenAI Codex
│       └── codebuddy_adapter.py # CodeBuddy
├── v5/
│   ├── __init__.py
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── pool.py            # Worker 进程池（650 行）
│   │   └── supervisor.py     # 健康监护（580 行）
│   ├── queue/
│   │   ├── __init__.py
│   │   └── queue.py          # SQLite 持久化队列（861 行）
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py            # FastAPI 主程序（786 行）
│   │   ├── models.py         # Pydantic 模型
│   │   ├── websocket.py      # WebSocket（440 行）
│   │   └── metrics.py        # Prometheus（350 行）
│   └── integration/
│       ├── __init__.py
│       └── session_pool.py   # V4×V5 集成（360 行）
└── tests/                     # 测试套件（136 测试）
    ├── __init__.py
    ├── conftest.py
    ├── test_adapters.py
    ├── test_router.py
    ├── test_session_store.py
    ├── test_queue.py
    ├── test_executor.py
    ├── test_retry.py
    ├── test_benchmark.py
    ├── test_command_builder.py
    └── test_cli.py
```

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| V4.0 | 2026-04-18 | 多 Agent CLI 抽象层（CLI/TUI/REPL） |
| V5.0 | 2026-04-18 | 生产级进程池 + 持久化队列 + REST API |
| V5.1–V5.15 | 2026-04-18 | 持续迭代：WebSocket、Prometheus、基准测试等 |

---

## 许可证

Internal use only.

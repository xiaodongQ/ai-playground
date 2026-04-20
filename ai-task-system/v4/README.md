# AI Task System V4 — 多 Agent 抽象层

> 统一的多 Agent CLI 编排层，支持 Claude Code、OpenAI Codex 和 CodeBuddy。

**V4** 是整个系统的核心抽象层，提供 CLI、TUI（Textual 全屏界面）和 REPL（交互式命令行）三种交互入口，负责任务路由、执行调度和会话管理。

---

## 目录

- [架构](#架构)
- [快速开始](#快速开始)
- [入口模式](#入口模式)
- [CLI 参考](#cli-参考)
- [TUI 参考](#tui-参考)
- [REPL 参考](#repl-参考)
- [任务路由](#任务路由)
- [Agent 适配器](#agent-适配器)
- [基准测试](#基准测试)
- [会话管理](#会话管理)
- [配置与数据](#配置与数据)

---

## 架构

```
v4/
├── cli.py                        # CLI 入口（14 个子命令）
├── repl.py                       # 交互式 REPL（670 行）
├── tui.py                        # Textual TUI 全屏界面
├── tui_app.py                    # TUI 模块化版本
├── __main__.py                   # python -m ai_task_system.v4 入口
├── core/
│   ├── base.py                   # AgentAdapter 抽象基类 + 数据模型
│   ├── command_builder.py        # 跨 Agent 命令参数映射
│   ├── executor.py               # 统一执行器 + NoOutputWatcher
│   ├── router.py                # 任务路由器（13 种任务类型）
│   ├── session_store.py         # 会话持久化（JSON 文件）
│   ├── retry.py                # 指数退避重试策略
│   ├── benchmark.py            # 基准测试入口
│   ├── benchmark_scores.py      # 基准分数数据库（JSON）
│   └── benchmark/               # 基准测试子包
│       ├── tasks.py             # 标准任务集（15 个任务）
│       ├── runner.py            # 基准测试执行器
│       ├── db.py                # SQLite 分数存储
│       └── result.py            # 结果模型
└── adapters/
    ├── claude_adapter.py         # Claude Code（15 项能力）
    ├── codex_adapter.py          # OpenAI Codex（11 项能力）
    └── codebuddy_adapter.py      # CodeBuddy（5 项能力）
```

### 核心流程

```
用户输入 prompt
     ↓
TaskRouter.classify()  →  识别 13 种任务类型之一
     ↓
TaskRouter.route()    →  基于规则 + 基准分数选择最佳 Agent
     ↓
CommandBuilder        →  构建该 Agent 的命令行参数
     ↓
SubprocessExecutor    →  执行命令（subprocess + 超时控制）
     ↓
TaskResult            →  捕获 stdout/stderr/session_id
```

---

## 快速开始

### 1. 查看 Agent 状态

```bash
python -m ai_task_system.v4.cli agents
```

```
Agent           Available    Capabilities
--------------------------------------------------------------------------------
claude          ✅ Available  SKIP_PERMISSIONS, AUTO_PERMISSIONS, ...
codex           ❌ not found in PATH
codebuddy       ❌ not found in PATH
```

### 2. 执行任务（CLI）

```bash
# 基础执行
python -m ai_task_system.v4.cli create "帮我写一个快速排序函数" -a claude -y -w

# 仅显示命令（不执行）
python -m ai_task_system.v4.cli show-cmd "帮我写一个快速排序函数" -a claude -y

# 等待结果
python -m ai_task_system.v4.cli create "say hello world" -a claude -y -w
```

### 3. 执行任务（TUI 全屏界面）

```bash
python -m ai_task_system.v4 --tui
# 或
python -m ai_task_system.v4.tui
```

### 4. 执行任务（REPL 交互式）

```bash
python -m ai_task_system.v4
# 或
python -m ai_task_system.v4 --repl
```

```
🤖 AI Task System V4 — Interactive REPL
Type 'help' for commands, or enter a task directly.

ai-task> 帮我写一个斐波那契函数
🤖 Agent: claude (routed: CODING)
⏱  Timeout: 600s | No-output: 120s
▶ Executing...
...
```

### 5. 路由决策（不执行）

```bash
python -m ai_task_system.v4.cli route "帮我用 GitHub Actions 写 CI 流水线" --explain
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

---

## 入口模式

V4 提供三种入口，选择取决于使用场景：

| 入口 | 命令 | 适用场景 |
|------|------|----------|
| **CLI** | `python -m ai_task_system.v4.cli <cmd>` | 脚本化、非交互、CI/CD |
| **TUI** | `python -m ai_task_system.v4 --tui` | 全屏可视化任务监控 |
| **REPL** | `python -m ai_task_system.v4` | 交互式探索、快速任务 |

---

## CLI 参考

### 子命令一览

| 命令 | 说明 |
|------|------|
| `agents` | 列出所有 Agent 及其可用状态 |
| `show-cmd <prompt>` | 显示执行命令（不执行） |
| `create <prompt>` | 创建并执行任务 |
| `list` | 列出所有任务 |
| `status <task-id>` | 查看任务状态 |
| `stop <task-id>` | 停止运行中的任务 |
| `sessions <sub>` | 会话管理（list/get/archive/delete/stats/log/export/import/suggest） |
| `route <prompt>` | 任务路由决策 |
| `retry <prompt>` | 错误重试执行（指数退避） |
| `benchmark` | Agent 能力基准测试 |
| `scores <sub>` | 基准分数管理（show/compare/load/clear） |

### create 命令选项

```bash
python -m ai_task_system.v4.cli create "任务描述" \
    -a {claude,codex,codebuddy}  # 指定 Agent（默认：自动选择）
    -y                           # 跳过所有确认（等同于 --skip-permissions）
    -w                           # 等待结果（默认：不等待，立即返回）
    -t <seconds>                 # 超时时间（默认：600）
    --no-output-timeout <sec>   # 无输出超时（默认：timeout/2）
    --tools <tool1,tool2>       # 允许的工具白名单
    --output-format {text,json}  # 输出格式
    --model <name>              # 指定模型
    --bare                       # Bare 模式（跳过 CLAUDE.md 发现）
    --resume <session-id>        # 恢复指定会话
    --no-commit                  # 禁用 Git 自动提交
    --verbose                    # 详细输出
    -f {text,json}              # 输出格式（简写）
```

### 会话管理子命令

```bash
# 列出会话
python -m ai_task_system.v4.cli sessions list --agent claude --status active

# 查看会话详情
python -m ai_task_system.v4.cli sessions get <session-id>

# 查看会话历史
python -m ai_task_system.v4.cli sessions log <session-id>

# 导出会话
python -m ai_task_system.v4.cli sessions export <session-id> -o session.json

# 导入会话
python -m ai_task_system.v4.cli sessions import session.json

# 建议可用的会话（用于 resume）
python -m ai_task_system.v4.cli sessions suggest --agent claude

# 归档/删除会话
python -m ai_task_system.v4.cli sessions archive <session-id>
python -m ai_task_system.v4.cli sessions delete <session-id>
```

### 重试命令

```bash
python -m ai_task_system.v4.cli retry "重试的任务描述" \
    -a claude \
    -y \
    -n 3                        # 最大重试次数（默认 3）
    -d 5.0                      # 初始退避延迟秒数（默认 5.0）
    --timeout 600
```

### 基准测试命令

```bash
# 全部 Agent 基准测试
python -m ai_task_system.v4.cli benchmark

# 指定 Agent
python -m ai_task_system.v4.cli benchmark --agent claude

# 导出 CSV 报告
python -m ai_task_system.v4.cli benchmark --report /tmp/benchmark.csv

# 过滤任务类别
python -m ai_task_system.v4.cli benchmark --tasks coding --tasks debugging
```

---

## TUI 参考

### 启动

```bash
python -m ai_task_system.v4 --tui
# 或
python -m ai_task_system.v4.tui
```

### 布局

```
┌────────────────────────────────────────────────────────────────────┐
│  🤖 AI Task System V4                      Agent: Claude Code ▼   │
├────────────────────┬─────────────────────────────────────────────┤
│  Agent Selector    │  Tasks        Output Log                    │
│  ○ Claude Code    │  ▶ task-001  │  Starting...                 │
│  ○ Codex          │  task-002 ✅  │  Thinking...                  │
│  ○ CodeBuddy      │  task-003 ❌  │  Done.                       │
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
python -m ai_task_system.v4
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
- readline 历史持久化（`~/.ai_task_system/repl_history`）

---

## 任务路由

### 13 种任务类型

| 类型 | 说明 | 优先 Agent |
|------|------|-----------|
| `CODING` | 通用编码 / 实现功能 | Claude > Codex |
| `DEBUGGING` | Bug 修复 / 调试 | Claude > Codex |
| `REFACTORING` | 代码重构 / 优化 | Claude > Codex |
| `ARCHITECTURE` | 架构设计 / 系统设计 | Claude |
| `CODE_REVIEW` | 代码审查 | Claude > Codex |
| `RESEARCH` | 技术研究 / 调研 | Claude |
| `LEARNING` | 学习辅导 / 概念解释 | Claude |
| `WRITING` | 写作 / 博客 / 文档 | Claude |
| `TRANSLATION` | 翻译 | Claude |
| `DEVOPS` | CI/CD / 部署 / 容器 | Claude > Codex |
| `INFRA` | 基础设施 / 云配置 | Claude > Codex |
| `DATA_SCRIPT` | 数据处理 / 脚本 | Claude > Codex |
| `QUERY` | 数据库查询 / API 调用 | Claude > Codex |

### 路由置信度算法

融合两套信号：
1. **关键词命中置信度**（权重 60%）：prompt 中命中路由规则关键词的数量
2. **基准分数置信度**（权重 40%）：基于历史真实评测数据中该 Agent 在此类任务上的相对得分

```
最终置信度 = keyword_conf × 0.6 + benchmark_conf × 0.4
```

---

## Agent 适配器

### Claude Code（15 项能力）

| 能力 | 参数 | 说明 |
|------|------|------|
| 无头模式 | `--print` | 非交互执行 |
| 跳过确认 | `--dangerously-skip-permissions` | 自动授权所有操作 |
| 工具白名单 | `--allowed-tools` | 限制可用工具 |
| 结构化输出 | `--json-schema` | JSON Schema 约束 |
| 输出格式 | `--output-format` | text/json/stream-json |
| 会话恢复 | `--resume` | 恢复历史会话 |
| 模型选择 | `--model` | 指定模型 |
| 预算控制 | `--max-budget-usd` | 限制花费 |
| Bare 模式 | `--bare` | 跳过 CLAUDE.md 发现 |
| 工作目录 | `--add-dir` | 添加工作目录 |
| Git 自动提交 | `--no-commit` | 禁用自动提交 |
| 输出流 | `--output-format stream-json` | 流式输出 |

### OpenAI Codex（11 项能力）

| 能力 | 参数 | 说明 |
|------|------|------|
| 无头模式 | `exec` | 非交互执行 |
| 跳过确认 | `--full-auto` | 自动授权 |
| 结构化输出 | `--output-schema` | JSON Schema 约束 |
| 输出格式 | `--json` | JSON 输出 |
| 模型选择 | `-m` | 指定模型 |
| 工作目录 | `-C` | 切换工作目录 |

### CodeBuddy（5 项能力）

| 能力 | 参数 | 说明 |
|------|------|------|
| 无头模式 | `-p` | 非交互执行 |
| 跳过确认 | `-y` | 自动确认 |
| 工具白名单 | `--allowedTools` | 限制工具 |
| 结构化输出 | `--output-format` | 输出格式 |
| 会话恢复 | `--resume` | 恢复会话 |

---

## 基准测试

### 运行基准测试

```bash
# 全部 Agent
python -m ai_task_system.v4.cli benchmark

# 指定 Agent + 类别
python -m ai_task_system.v4.cli benchmark --agent claude --tasks coding

# 导出报告
python -m ai_task_system.v4.cli benchmark --report /tmp/bench.csv -v
```

### 标准任务集（15 个任务）

覆盖 8 个类别：`coding`, `refactoring`, `debugging`, `architecture`, `learning`, `writing`, `shell`, `research`

### 分数管理

```bash
# 查看分数
python -m ai_task_system.v4.cli scores show

# 对比 Agent
python -m ai_task_system.v4.cli scores compare

# 加载外部 CSV
python -m ai_task_system.v4.cli scores load /tmp/bench.csv

# 清除分数
python -m ai_task_system.v4.cli scores clear
```

### 基准分数数据库

存储位置：`~/.ai_task_system/benchmark_scores.json`

包含：
- 每个 Agent 的总体分数
- 每个 Agent 在各类别上的分项分数
- 最后更新时间

---

## 会话管理

### 持久化会话

V4 会话存储在 `~/.ai_task_system/sessions.json`，包含：
- `session_id`：会话唯一标识
- `agent`：使用的 Agent 类型
- `status`：active / archived
- `task_ids`：关联的任务 ID 列表
- `note`：用户备注

### 会话恢复

```bash
# 从 CLI 创建带 session 的任务
python -m ai_task_system.v4.cli create "任务" --session <id> --resume -a claude

# 从 REPL 设置当前会话
ai-task> session <session-id>
ai-task> 继续上次的工作...
```

### 导出 / 导入

```bash
# 导出会话（包含所有任务历史）
python -m ai_task_system.v4.cli sessions export <session-id> -o backup.json

# 导入会话
python -m ai_task_system.v4.cli sessions import backup.json
```

---

## 配置与数据

### 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `PYTHONPATH` | Python 模块搜索路径 | — |
| `ANTHROPIC_API_KEY` | Anthropic API Key | 从环境继承 |
| `OPENAI_API_KEY` | OpenAI API Key | 从环境继承 |

### 数据文件

| 内容 | 路径 |
|------|------|
| 会话存储 | `~/.ai_task_system/sessions.json` |
| TUI 任务 | `~/.ai_task_system/tui_tasks.json` |
| 基准分数 | `~/.ai_task_system/benchmark_scores.json` |
| REPL 历史 | `~/.ai_task_system/repl_history` |

---

## 与 V5 的关系

V4 是 V5 的执行引擎：
- **V5 REST API** 的任务最终通过 V4 的 `CommandBuilder` + `SubprocessExecutor` 执行
- **V5 WorkerPool** 每个 Worker 内部调用 V4 的命令构建逻辑
- **V5 Supervisor** 监控的正是 V4 执行器的运行时状态

```
V5 API  →  V5 Queue  →  V5 WorkerPool  →  V4 CommandBuilder  →  subprocess  →  Agent
```

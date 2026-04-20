# AI Task System

> 个人 AI 领取任务系统，支持多 Agent 协调执行、自动领取、评估迭代。

本项目包含 v1 ~ v5 多个版本迭代，**v4/v5 是当前活跃版本**。

---

## 版本概览

| 版本 | 定位 | 技术栈 | 状态 |
|------|------|--------|------|
| **V1** | 单 Agent 任务池 + Web UI + 评估迭代闭环 | FastAPI + SQLite + CodeBuddy | 归档 |
| **V2** | V1 改进版 + Claude Code CLI 支持 | FastAPI + SQLite + Claude Code | 归档 |
| **V3** | CodeBuddy 原生适配版 + 双超时防护 | FastAPI + SQLite + CodeBuddy | 归档 |
| **V4** | 多 Agent 抽象层（CLI / TUI / REPL） | Python CLI + Textual | **活跃** |
| **V5** | 生产级架构（进程池 + 持久化队列 + REST API） | FastAPI + SQLite WAL + WebSocket | **活跃** |

---

## 版本详情

### V1 — 任务池 + 评估迭代闭环

**定位**：最初的原型，基于 CodeBuddy CLI。

**特性**：
- Web UI 任务管理（添加/删除/查看）
- 自动领取执行（调度器自动领取 pending 任务）
- 交叉评估（不同 AI 模型交叉评估）
- 迭代闭环（评分低于阈值自动重试）
- 完整执行追踪（领取时间/开始时间/完成时间/输出）

**入口**：`v1/` 目录（已归档，详细文档见 [v1/README.md](v1/README.md)）

```bash
cd v1
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
uvicorn backend.main:app --reload --port 8000
```

---

### V2 — Claude Code 集成版

**定位**：V1 改进版，接入 Claude Code CLI，支持多 Agent 并行。

**特性**：
- Claude Code CLI 执行引擎
- Web 界面 + API 双接口
- 自动评估（MiniMax API / 简单评估器）
- 多 Agent 并行执行
- 任务调度器（60s 轮询间隔）

**入口**：`v2/` 目录（已归档，详细文档见 [v2/README.md](v2/README.md)）

```bash
cd v2
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
uvicorn backend.main:app --reload --port 8000
```

---

### V3 — CodeBuddy 原生适配版

**定位**：基于豆包 AI（CodeBuddy）设计的任务自动化执行平台。

**特性**：
- 100% 遵循 CodeBuddy CLI 规范
- 单机无容器、零配置一键启动
- WebSocket 实时同步 + 日志文件兜底
- 固定 Markdown 结构（人/AI 都能零歧义读取）
- 双超时防护（绝对超时 + 无输出超时）
- Git 版本自动提交

**入口**：`v3/` 目录（已归档，详细文档见 [v3/README.md](v3/README.md)）

```bash
cd v3
pip install -r requirements.txt
python main.py
```

---

### V4 — 多 Agent 抽象层

**定位**：统一的多 Agent CLI 编排层，支持 Claude Code、OpenAI Codex 和 CodeBuddy。

**特性**：
- **统一适配器**：Claude Code / Codex / CodeBuddy 三合一接口
- **三种入口**：CLI（非交互）/ TUI（全屏）/ REPL（交互）
- **任务路由**：13 种任务类型 → 最优 Agent 自动选择
- **基准测试**：Agent 能力评分，持续跟踪对比
- **会话持久化**：跨会话恢复，session export/import
- **无输出超时**：卡死检测，自动终止
- **错误重试**：指数退避，最多重试 3 次

**入口**：`python -m ai_task_system.v4`（详细文档见 [v4/README.md](v4/README.md)）

```bash
# CLI 模式
python -m ai_task_system.v4.cli create "任务" -a claude -y -w

# TUI 全屏
python -m ai_task_system.v4 --tui

# REPL 交互
python -m ai_task_system.v4
```

---

### V5 — 生产级架构

**定位**：V4 的生产级扩展，带持久化队列和进程池，支持高并发和分布式任务管理。

**特性**：
- **进程池**：预热 Worker，故障自动恢复
- **持久化队列**：SQLite WAL，支持优先级/延迟/死信
- **REST API**：18 个端点，API Key 认证
- **WebSocket**：实时任务状态/输出流推送
- **Prometheus**：`/metrics` 端点，Grafana 就绪
- **Supervisor**：心跳检测，无输出监控，自动重启

**入口**：`python -m v5.api.app`（详细文档见 [v5/README.md](v5/README.md)）

```bash
export AI_TASK_API_KEY="my-secret-key"  # 可选
python -m v5.api.app --port 18792
# API 文档：http://localhost:18792/docs
```

---

## 架构演进

```
V1:  单 Agent  + 任务池  + 评估迭代
     ↓
V2:  多 Agent  + 任务池  + 评估迭代
     ↓
V3:  CodeBuddy 原生适配  + 双超时防护
     ↓
V4:  多 Agent 抽象层  + CLI/TUI/REPL  + 任务路由
     ↓
V5:  V4 × 生产化  + 进程池  + 持久化队列  + REST API
```

---

## 快速开始（当前版本 V4/V5）

### 安装依赖

```bash
pip install -e .
```

### V4 — CLI / TUI / REPL

```bash
# 查看 Agent 状态
python -m ai_task_system.v4.cli agents

# CLI 执行任务
python -m ai_task_system.v4.cli create "帮我写一个快速排序" -a claude -y -w

# TUI 全屏界面
python -m ai_task_system.v4 --tui

# REPL 交互模式
python -m ai_task_system.v4
```

### V5 — REST API

```bash
python -m v5.api.app --port 18792
```

---

## 配置

### 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `AI_TASK_API_KEY` | REST API 认证 Key（逗号分隔多个） | 无（认证禁用） |
| `PYTHONPATH` | Python 模块搜索路径 | — |

### 数据目录

| 内容 | 路径 |
|------|------|
| 会话存储 | `~/.ai_task_system/sessions.json` |
| 基准分数 | `~/.ai_task_system/benchmark_scores.json` |
| 任务队列 DB | `~/.ai_task_system/tasks.db` |
| REPL 历史 | `~/.ai_task_system/repl_history` |

---

## 测试

```bash
# 全部测试（必须在 ai-task-system 目录执行）
PYTHONPATH=$(pwd) python -m pytest tests/ -v

# 单个模块
PYTHONPATH=$(pwd) python -m pytest tests/test_router.py -v
```

---

## 详细文档

| 版本 | 文档路径 | 内容 |
|------|----------|------|
| **V1** | [v1/README.md](v1/README.md) | Web UI、任务池、评估迭代闭环 |
| **V2** | [v2/README.md](v2/README.md) | Claude Code CLI、多 Agent 并行 |
| **V3** | [v3/README.md](v3/README.md) | CodeBuddy 原生适配、双超时防护 |
| **V4** | [v4/README.md](v4/README.md) | CLI/TUI/REPL、任务路由、Agent 适配器 |
| **V5** | [v5/README.md](v5/README.md) | REST API、WebSocket、Worker Pool、部署 |

---

## 许可证

Internal use only.

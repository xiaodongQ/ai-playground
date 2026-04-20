# AI Task System V4 - Claude Code

多 Agent CLI 抽象层，支持 Claude Code、Codex、CodeBuddy。

## 架构

- `core/base.py` — AgentAdapter 抽象基类 + 数据模型
- `core/command_builder.py` — 跨 Agent 命令参数映射
- `core/executor.py` — 统一执行器（自动降级）
- `adapters/claude_adapter.py` — Claude Code 实现
- `adapters/codex_adapter.py` — OpenAI Codex 实现
- `adapters/codebuddy_adapter.py` — CodeBuddy 实现（基于 V3 逆向）

## 核心概念

**AgentAdapter** — 每个 CLI Agent 的统一封装，暴露：
- `build_command(config)` → CLI 参数列表
- `parse_output(raw)` → ExecutionResult
- `is_available()` → (bool, reason)

**ExecutionConfig** — 任务执行的统一配置，屏蔽各 Agent 的差异。

**自动降级** — 指定 Agent 不可用时，自动尝试其他注册的 Agent。

## 命令行参数对比

| 功能 | Claude Code | Codex | CodeBuddy |
|------|-------------|-------|-----------|
| 无头模式 | `--print` | `exec` | `-p` |
| 跳过确认 | `--dangerously-skip-permissions` | `--full-auto` | `-y` |
| 工具白名单 | `--allowed-tools` | ❌ | `--allowedTools` |
| 输出格式 | `--output-format` | `--json` | `--output-format` |
| 会话恢复 | `--resume` | ❌ | `--resume` |

## 运行测试

```bash
cd /home/workspace/repo/ai-playground/ai-task-system
PYTHONPATH=v4 python3 -c "from v4.adapters import ClaudeCodeAdapter; ..."
```

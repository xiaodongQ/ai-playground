# TOOLS.md - Dev·技术匠 工具配置

## 🔍 搜索工具优先级

**所有 Agent 统一遵循全局规则 `RULE-004`**：

```
1️⃣ Tavily Search（首选）
   └─ 通用搜索、新闻、研究

2️⃣ Multi-Search（备用）
   └─ 中文/国内内容、17 个搜索引擎

3️⃣ Exa Search（技术/代码查询）
   └─ 代码示例、技术文档、公司研究

4️⃣ Agent Reach（专用平台）
   └─ 社交媒体、13+ 特定平台（GitHub 等）
```

**Dev·技术匠常用场景**：
- 技术文档查询 → Tavily 或 Exa
- GitHub 项目搜索 → Agent Reach（GitHub 工具）
- 代码示例查找 → Exa
- 中文技术问题 → Multi-Search

## 🛠️ 开发工具

| 工具 | 状态 | 用途 |
|------|------|------|
| `claude` | ✅ 已安装 | Claude Code 代码生成 |
| `claude-code-wrapper.sh` | ✅ 已配置 | **Claude Code 自动确认（推荐使用）** |
| `git` | ✅ 可用 | 版本控制 |
| `node` | ✅ v24.13.0 | JavaScript/TypeScript 运行 |
| `go` | ✅ 可用 | Go 语言编译 |
| `mcporter` | ✅ 已配置 | MCP 工具调用 |

---

## 🔧 Claude Code 使用说明

### Wrapper 脚本（推荐）

**脚本位置**: `/root/.openclaw/scripts/claude-code-wrapper.sh`

**功能**:
- 自动切换到 `clauded` 用户（避免 root 权限问题）
- 自动使用 `--permission-mode bypassPermissions`（无需用户确认）
- 自动设置工作目录

**用法**:
```bash
# 基本用法
/root/.openclaw/scripts/claude-code-wrapper.sh "你的任务描述"

# 指定工作目录
/root/.openclaw/scripts/claude-code-wrapper.sh "任务描述" "/path/to/workdir"
```

**示例**:
```bash
# 写一个 HTTP 服务器
/root/.openclaw/scripts/claude-code-wrapper.sh "用 Go 写一个 HTTP 服务器，监听 8080 端口"

# 运行测试
/root/.openclaw/scripts/claude-code-wrapper.sh "运行单元测试并修复失败的测试"

# 代码审查
/root/.openclaw/scripts/claude-code-wrapper.sh "审查 /root/.openclaw/workspace/main.go 的代码质量"
```

### 直接使用 su 命令（备选）

```bash
su clauded -s /bin/bash -c "cd /root/.openclaw/workspace && claude --print --permission-mode bypassPermissions '任务描述'"
```

### ⚠️ 禁止事项

```bash
# ❌ 不要直接调用 claude（会卡在权限确认）
claude "任务描述"  # 会等待用户确认，导致任务卡住

# ❌ 不要在 root 用户下运行（会拒绝执行）
claude --dangerously-skip-permissions "任务"  # 错误：root 下禁止运行
```

### 前置条件

| 条件 | 状态 |
|------|------|
| `clauded` 用户已创建 | ✅ |
| workspace 权限已配置 | ✅ |
| Wrapper 脚本可执行 | ✅ |
| `/root` 目录可执行 | ✅ |

---

**详细文档**: `/root/.openclaw/workspace/memory/claude-code-root-workaround.md`

## 📋 全局规则

Dev·技术匠启动时读取 `/root/.openclaw/workspace/RULES.md`，遵守：
- RULE-001: 博客发布评审流程（协助技术博客）
- RULE-004: 搜索工具优先级策略
- RULE-005: 挑战式交互原则（技术评审）

---

**最后更新**: 2026-03-11

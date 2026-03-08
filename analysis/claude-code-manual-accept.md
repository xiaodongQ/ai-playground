# Claude Code 为何需要手动接受修改？

## 🔍 问题分析

你在使用 Claude Code（或类似编码代理）时，发现它提出的代码修改需要**手动确认**才能应用，而不是自动执行。

## ✅ 这是设计意图，不是 Bug

### 1. **安全边界**

```
┌─────────────────────────────────────┐
│  安全层级                            │
├─────────────────────────────────────┤
│  🔴 外部操作 → 必须询问              │
│  🟡 代码修改 → 需要确认              │
│  🟢 内部读取 → 可以自由              │
└─────────────────────────────────────┘
```

**原因：**
- 代码修改可能破坏现有功能
- 可能有副作用（删除文件、覆盖重要配置）
- 你（人类）是最终责任人

### 2. **OpenClaw 的安全模型**

根据 `SOUL.md` 和 `AGENTS.md`：

> "Don't run destructive commands without asking."
> "Ask first: Anything that leaves the machine, Anything you're uncertain about"

**编码代理遵循同样原则：**
- 读取代码 ✅ 自动
- 小修小补 ⚠️ 可能自动（取决于配置）
- 结构性修改 ❌ 必须确认

### 3. **ACP Harness 设计**

ACP (Autonomous Coding Protocol) 的设计哲学：

| 操作类型 | 默认行为 | 原因 |
|---------|---------|------|
| 读文件 | 自动 | 无风险 |
| 写新文件 | 可能自动 | 低风险 |
| 修改现有文件 | 需要确认 | 中风险 |
| 删除文件 | 必须确认 | 高风险 |
| 执行命令 | 必须确认 | 高风险 |

## 🛠️ 如何调整？

### 方案 A：信任特定目录（如果支持）

```bash
# 在某些配置中，可以设置信任目录
# 但这取决于具体实现
```

### 方案 B：使用 `sessions_spawn` 的 `sandbox` 参数

```yaml
runtime: "acp"
sandbox: "inherit"  # 或 "require"
mode: "session"     # 持续会话，可以建立信任
```

### 方案 C：调整心理预期

**把确认当作 Code Review：**
- 每次确认都是一次 mini code review
- 确保你理解修改内容
- 防止代理"自作主张"

## 🤔 为什么不能全自动？

```
风险场景：
1. 代理误删了关键配置文件
2. 代理覆盖了你的本地未提交修改
3. 代理引入了安全漏洞
4. 代理修改了生产环境配置

→ 人类确认是最后一道防线
```

## 💡 建议

1. **接受这个设计** - 它是保护你的
2. **批量确认** - 如果信任代理，可以一次 review 多个修改
3. **建立信任** - 在 `sandbox: "inherit"` 模式下，代理会更了解你的代码库
4. **使用 Git** - 所有修改都可以回滚，降低风险

## 📚 相关文档

- OpenClaw Docs: `/home/workspace/local/node-v24.13.0-linux-x64/lib/node_modules/openclaw/docs`
- Coding Agent Skill: `/home/workspace/local/node-v24.13.0-linux-x64/lib/node_modules/openclaw/skills/coding-agent/SKILL.md`
- ACP Harness: 通过 `sessions_spawn` with `runtime: "acp"`

---

**总结：** 手动接受修改是**安全特性**，不是限制。它确保你始终掌控代码库的最终状态。🔒

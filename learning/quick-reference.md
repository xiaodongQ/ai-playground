# OpenClaw 快速参考卡片 🚀

> 一页纸速查 | 常用命令/工具/提示词

---

## ⚡ 常用命令

```bash
# 服务管理
openclaw gateway start|stop|restart|status

# 配置
openclaw configure [--section <section>]

# 状态
openclaw status

# 日志
openclaw logs [--follow]

# 帮助
openclaw help
openclaw <command> --help
```

---

## 🛠️ 核心工具速查

### 文件操作
```markdown
read(path="xxx", limit=100, offset=0)
write(path="xxx", content="xxx")
edit(path="xxx", oldText="xxx", newText="xxx")
```

### 命令执行
```markdown
exec(command="xxx", yieldMs=5000, background=false)
process(action="list|poll|kill", sessionId="xxx")
```

### 网络操作
```markdown
web_search(query="xxx", count=10, freshness="pd|pw|pm|py")
web_fetch(url="xxx", extractMode="markdown|text", maxChars=10000)
```

### 消息发送
```markdown
message(action="send", target="xxx", message="xxx")
```

### 会话管理
```markdown
sessions_list(kinds=["xxx"], limit=10)
sessions_spawn(task="xxx", runtime="subagent|acp", mode="run|session")
sessions_history(sessionKey="xxx", limit=50)
sessions_send(sessionKey="xxx", message="xxx")
```

### Feishu 专用
```markdown
feishu_doc(action="read|write|create", doc_token="xxx")
feishu_chat(action="members|info", chat_id="xxx")
feishu_drive(action="list|create_folder", folder_token="xxx")
feishu_bitable_get_meta(url="xxx")
feishu_bitable_list_records(app_token="xxx", table_id="xxx")
```

---

## 📁 目录结构

```
/root/.openclaw/
├── openclaw.json        # 主配置 ⭐
├── agents/              # 代理配置
├── extensions/          # 插件
├── workspace/           # 工作区 ⭐
├── logs/                # 日志
├── memory/              # 记忆
└── ...
```

---

## 📝 提示词模板

### 通用任务
```markdown
请帮我完成以下任务：

**目标**: [清晰描述]
**约束**: [限制条件]
**期望输出**: [格式要求]
**上下文**: [背景信息]

请逐步执行，遇到不确定的地方先询问。
```

### 代码审查
```markdown
请审查以下代码：

**文件**: [路径]
**关注点**: 安全性 | 性能 | 可读性 | 最佳实践
**代码**:
[粘贴代码]

请指出问题并提供修复建议。
```

### 调试协助
```markdown
我遇到了问题：

**现象**: [描述]
**预期**: [期望行为]
**环境**: [系统/版本]
**错误**: [错误信息]
**已尝试**: [排查步骤]

请分析可能原因和解决方案。
```

### 配置优化
```markdown
请帮我优化 OpenClaw 配置：

**当前配置**: [粘贴]
**使用场景**: [个人/团队/生产]
**痛点**: [当前问题]
**目标**: [期望改进]

请分析并给出优化方案。
```

---

## 🔧 配置速查

### 模型配置
```json
{
  "models": {
    "providers": {
      "bailian": {
        "baseUrl": "https://...",
        "apiKey": "sk-..."
      }
    }
  }
}
```

### 渠道配置
```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx"
    }
  }
}
```

### 工具配置
```json
{
  "tools": {
    "profile": "full"
  }
}
```

---

## ⚠️ 安全提醒

```
✅ 安全操作:
- 工作区内文件操作
- 读取代码和配置
- 发送消息到已授权渠道

❌ 需确认:
- 删除文件
- 外部邮件/消息
- 系统级命令
- 敏感数据操作

🚫 禁止操作:
- rm -rf 根目录/家目录
- 泄露私人数据到群聊
- 未经授权的 external 操作
```

---

## 🐛 故障排查

| 问题 | 检查 | 解决 |
|------|------|------|
| Gateway 无法启动 | `openclaw gateway status` | 检查端口/日志 |
| 消息发送失败 | 检查渠道配置 | 重新认证 |
| 工具执行超时 | 检查命令耗时 | 增加 timeout |
| 插件加载失败 | `ls extensions/` | `npm install` |

---

## 📚 学习资源

| 资源 | 链接 |
|------|------|
| 官方文档 | https://docs.openclaw.ai |
| GitHub | https://github.com/openclaw/openclaw |
| Discord | https://discord.com/invite/clawd |
| 技能市场 | https://clawhub.com |
| 学习指南 | workspace/learning/openclaw-master-guide.md |
| 提示词优化 | workspace/learning/prompt-optimizer.md |
| 30 天计划 | workspace/learning/30-day-plan.md |

---

## 💡 效率技巧

```markdown
# Token 优化
- 用文件引用代替大段粘贴
- 用列表代替段落
- 移除冗余描述

# 上下文管理
- 定期清理会话历史
- 使用子会话处理独立任务
- 用 memory_* 工具管理长期记忆

# 工具组合
- read + edit = 精确修改
- web_search + web_fetch = 信息收集
- sessions_spawn + sessions_send = 任务分发
```

---

## 🎯 快速诊断命令

```bash
# 一键诊断
openclaw status && echo "---" && ls -la /root/.openclaw/extensions/ && echo "---" && tail -5 /root/.openclaw/logs/*.log

# 配置检查
cat /root/.openclaw/openclaw.json | head -50

# 工作区状态
ls -la /root/.openclaw/workspace/

# 会话列表
openclaw sessions list
```

---

## 📞 获取帮助

1. **官方文档**: 首选，最权威
2. **Discord 社区**: 实时交流
3. **GitHub Issues**: 问题反馈
4. **问我**: 随时提问！

---

> 💾 **保存位置**: `/root/.openclaw/workspace/learning/quick-reference.md`
> 📅 **最后更新**: 2026-03-07

---

**打印此页，贴在桌边！📌**

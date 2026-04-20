# nanoClaw 快速参考卡

## 🚀 快速命令

```bash
# 安装
git clone https://github.com/ysz/nanoClaw.git && cd nanoClaw
pip install -e .

# 配置
nanoclaw init

# 启动
nanoclaw serve

# 状态检查
nanoclaw status
nanoclaw doctor

# 测试聊天
nanoclaw chat -m "Hello"
```

## 📁 目录结构

```
nanoClaw/
├── nanoclaw/           # 源代码
│   ├── core/          # 核心模块
│   ├── tools/         # 工具系统
│   ├── security/      # 安全防护
│   ├── memory/        # 记忆存储
│   ├── channels/      # 通信渠道
│   ├── cron/          # 定时任务
│   └── dashboard/     # Web 仪表板
├── tests/             # 测试文件
└── config.example.json # 配置示例
```

## 🔧 配置文件 (~/.nanoclaw/config.json)

```json
{
  "providers": {
    "openrouter": {"apiKey": "sk-or-xxx"}
  },
  "agents": {
    "defaults": {"model": "anthropic/claude-sonnet-4"}
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "BOT_TOKEN",
      "allowFrom": ["USER_ID"]
    }
  }
}
```

## 🛡️ 安全层

1. **InputGuard** - 输入验证
2. **ShellSandbox** - Shell 命令过滤 (三层：BLOCKED/CONFIRM/EXECUTE)
3. **FileGuard** - 文件访问限制
4. **PromptGuard** - 提示词注入防御
5. **SessionBudget** - Token 预算控制
6. **AuditLog** - 审计日志

## 📊 Token 优化

| 组件 | OpenClaw | nanoClaw | 节省 |
|------|----------|----------|------|
| System Prompt | 800 | 300 | 62% |
| Tool Schemas | 5000 | 800 | 84% |
| History | 15000 | 3000 | 80% |
| Tool Outputs | 8000 | 2000 | 75% |
| **总计** | **~28800** | **~6100** | **~80%** |

## 🎯 核心 API

### Agent
```python
agent = get_agent()
response = await agent.run(
    user_message="Hello",
    session_id="user_123",
)
```

### LLM Client
```python
llm = get_llm_client()
response = await llm.chat(
    messages=[{"role": "user", "content": "Hi"}],
    tools=[...],
)
```

### Tool Registry
```python
@tool(
    name="my_tool",
    description="Does something",
    parameters={"arg": {"type": "string"}}
)
async def my_tool(arg: str) -> str:
    return f"Result: {arg}"
```

### Memory Store
```python
memory = get_memory_store()
await memory.save_memory("User likes coffee", category="preference")
memories = await memory.search_memories("coffee", limit=5)
```

## 🔍 调试技巧

```bash
# 启用调试日志
nano ~/.nanoclaw/config.json
# "logging": {"level": "DEBUG"}

# 查看日志
tail -f ~/.nanoclaw/nanoclaw.log

# 运行测试
pytest tests/test_sandbox.py -v

# 代码检查
ruff check nanoclaw/
mypy nanoclaw/
```

## 📝 开发检查清单

### 提交前
- [ ] 代码格式化 (ruff format)
- [ ] 代码检查 (ruff check)
- [ ] 类型检查 (mypy)
- [ ] 测试通过 (pytest)
- [ ] 文档更新

### 技能开发
- [ ] 使用 @tool 装饰器
- [ ] 完整的 docstring
- [ ] 错误处理
- [ ] 输入验证
- [ ] 超时控制
- [ ] 缓存策略 (如适用)

## 🆘 常见问题

### Telegram 无法连接
```bash
# 检查 Bot Token
# 检查用户 ID
# 确保 Bot 已启动 (/start)
```

### API Key 无效
```bash
# 验证 Key 格式
# 检查余额
# 测试连接
curl -H "Authorization: Bearer sk-or-xxx" \
     https://openrouter.ai/api/v1/auth/key
```

### 命令被阻止
```bash
# 查看安全日志
grep "BLOCKED" ~/.nanoclaw/nanoclaw.log

# 检查命令模式
# 不要尝试执行危险命令
```

## 📚 学习资源

- **完整教程**: 01-05 章系统化学习
- **架构图**: assets/architecture.md
- **官方仓库**: https://github.com/ysz/nanoClaw
- **问题反馈**: https://github.com/ysz/nanoClaw/issues

## 💡 最佳实践

### 安全
- 定期更新
- 备份配置
- 限制访问用户
- 监控日志

### 性能
- 启用缓存
- 选择合适模型
- 调整迭代次数
- 设置 Token 预算

### 开发
- 小步提交
- 编写测试
- 文档齐全
- 代码审查

---

**快速参考卡版本**: 1.0
**最后更新**: 2024-03-10
**适用版本**: nanoClaw v0.0.1

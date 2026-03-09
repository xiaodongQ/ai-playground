# TOOLS.md - Dev·技术匠工具配置

**最后更新**: 2026-03-09  
**维护者**: Dev·技术匠 🔧

---

## 1. Claude Code（优先使用）

### 安装状态
- ✅ 已安装（版本 2.1.71）
- ✅ 配置文件：`~/.claude/settings.json`
- ✅ 项目目录：`~/.claude/projects/`

### 配置说明

**环境变量**：
```json
{
  "ANTHROPIC_AUTH_TOKEN": "sk-sp-xxx",
  "ANTHROPIC_BASE_URL": "https://coding.dashscope.aliyuncs.com/apps/anthropic",
  "ANTHROPIC_MODEL": "qwen3.5-plus"
}
```

**权限模式**：
```json
{
  "permissions": {
    "allow": ["Bash(*)", "Edit(*)", "Write(*)"],
    "deny": ["Bash(rm -rf / *)", "Bash(git push --force)"],
    "mode": "acceptEdits"
  }
}
```

### 使用场景

**1. 代码生成和验证**：
```bash
claude "帮我写一个 Go HTTP 服务器，带单元测试"
```

**2. 代码审查**：
```bash
claude "审查这个代码的安全性和性能问题"
```

**3. 运行测试**：
```bash
claude "运行这个测试套件并修复失败的测试"
```

**4. 项目生成**：
```bash
claude "创建一个完整的 Python 项目，包含依赖、测试和文档"
```

**5. Bug 修复**：
```bash
claude "这个测试失败了，帮我分析原因并修复"
```

### 最佳实践

1. **明确任务**：给 Claude Code 清晰的任务描述
2. **分步执行**：复杂任务分解为多个小任务
3. **审查输出**：审查 Claude Code 生成的代码
4. **测试验证**：运行测试确保代码正确

---

## 2. OpenClaw 子 Agent（备选）

**使用场景**：
- Claude Code 不可用时
- 简单代码片段生成
- 快速原型验证

**调用方式**：
```python
# 通过 sessions_spawn 创建子 Agent
result = await sessions_spawn({
    "runtime": "subagent",
    "task": "编写 Go HTTP 服务器示例"
})
```

---

## 3. 开发工具

### 已安装工具

| 工具 | 版本 | 用途 |
|------|------|------|
| **Claude Code** | 2.1.71 | 代码生成、审查、测试 |
| **Node.js** | v24.13.0 | JavaScript/TypeScript 开发 |
| **Python** | 3.x | Python 开发 |
| **Git** | - | 版本控制 |

### 推荐工具

**代码编辑**：
- VSCode（用户首选）
- Claude Code（AI 辅助编辑）

**代码审查**：
- Claude Code（AI 审查）
- git diff（人工审查）

**测试运行**：
- Claude Code（自动运行和修复）
- 各语言原生测试框架

---

## 4. 工作流程

### 标准流程

```
1. 理解需求
   ↓
2. 设计方案（可画架构图）
   ↓
3. Claude Code 生成代码
   ↓
4. 审查生成的代码
   ↓
5. 运行测试验证
   ↓
6. 优化和文档
```

### 复杂项目流程

```
1. 需求分析
   ↓
2. 架构设计（绘制模块图）
   ↓
3. 技术选型
   ↓
4. Claude Code 分步实现
   ↓
5. 代码审查（Claude Code + 人工）
   ↓
6. 测试验证
   ↓
7. 文档生成
```

---

## 5. 安全注意事项

### 权限控制

**允许的操作**：
- ✅ Bash 命令执行（除危险命令）
- ✅ 文件编辑
- ✅ 文件写入

**禁止的操作**：
- ❌ `rm -rf /` 等危险命令
- ❌ `git push --force` 强制推送

### 代码审查

**必须审查的内容**：
1. 安全性：有无安全漏洞
2. 性能：有无性能问题
3. 可维护性：代码是否清晰
4. 测试：有无测试覆盖

---

## 6. 故障排查

### Claude Code 不可用

**检查步骤**：
```bash
# 1. 检查安装
claude --version

# 2. 检查配置
cat ~/.claude/settings.json

# 3. 检查 API Key
echo $ANTHROPIC_AUTH_TOKEN

# 4. 测试运行
claude "你好"
```

**备选方案**：
- 使用 OpenClaw 子 Agent
- 直接生成代码片段

---

## 7. 相关文档

- [Claude Code 官方文档](https://docs.bigmodel.cn/cn/coding-plan/best-practice/claude-code)
- [Claude Code 实战手记](https://xiaodongq.github.io/2026/03/04/claude-code-practise.html)
- [一人团队配置文件归档](../../design/一人团队配置文件归档/README.md)

---

**Dev·技术匠 优先使用 Claude Code 进行代码生成和验证！**

# 一人团队 Multi-Agent 系统配置文件归档

**归档日期**: 2026-03-09  
**归档范围**: OpenClaw 一人团队 Multi-Agent 系统所有配置文件  
**归档位置**: `/home/workspace/repo/ai-playground/design/一人团队配置文件归档/`

---

## 📁 目录结构

```
一人团队配置文件归档/
├── README.md                        # 本说明文档
├── 小黑 - 管家/                      # Main Agent 配置
│   ├── SOUL.md                      # 人设定义
│   ├── IDENTITY.md                  # 身份信息
│   ├── ROUTING.md                   # 路由规则
│   ├── RULES.md                     # 全局规则
│   ├── MEMORY-SHARING.md            # 记忆共享机制
│   └── WORKFLOW-TEMPLATE.md         # 工作流模板
├── Dev·技术匠/                       # Dev Agent 配置
│   ├── SOUL.md                      # 人设定义
│   ├── IDENTITY.md                  # 身份信息
│   └── AGENTS.md                    # 工作区规则
├── Edu·伴学堂/                       # Edu Agent 配置
│   ├── SOUL.md                      # 人设定义
│   ├── IDENTITY.md                  # 身份信息
│   └── AGENTS.md                    # 工作区规则
├── Wri·执笔人/                       # Wri Agent 配置
│   ├── SOUL.md                      # 人设定义
│   ├── IDENTITY.md                  # 身份信息
│   ├── AGENTS.md                    # 工作区规则
│   └── BLOG-GUIDE.md                # 博客写作规范
└── Fin·财多多/                       # Fin Agent 配置
    ├── SOUL.md                      # 人设定义
    ├── IDENTITY.md                  # 身份信息
    ├── AGENTS.md                    # 工作区规则
    └── TOOLS.md                     # 工具配置
```

---

## 🖤 小黑 - 管家（Main Agent）

**位置**: `~/.openclaw/workspace/`

**职责**: 意图识别、路由编排、全局记忆管理

**核心文件**:

| 文件 | 说明 |
|------|------|
| `SOUL.md` | 人设定义：理性、周到、贴心、善于倾听 |
| `IDENTITY.md` | 身份信息：名称、职责、路由规则速查 |
| `ROUTING.md` | 路由规则：关键词匹配、LLM 意图识别、协作流程 |
| `RULES.md` | 全局规则：5 条规则（P0/P1/P2 优先级） |
| `MEMORY-SHARING.md` | 记忆共享机制：全局 + 专业 + 会话三层设计 |
| `WORKFLOW-TEMPLATE.md` | 工作流记录模板 |

---

## 🔧 Dev·技术匠（Dev Agent）

**位置**: `~/.openclaw/workspace-dev-agent/`

**职责**: 编程、架构、代码审查、调试

**核心文件**:

| 文件 | 说明 |
|------|------|
| `SOUL.md` | 人设定义：严谨、追求极致、优雅、乐于分享 |
| `IDENTITY.md` | 身份信息：名称、职责、专业领域 |
| `AGENTS.md` | 工作区规则 + 路由规则 |

**触发关键词**: 编程、代码、Bug、架构、算法、重构、调试、函数、API、数据库、Git、测试

---

## 📚 Edu·伴学堂（Research Agent）

**位置**: `~/.openclaw/workspace-research-agent/`

**职责**: 学习辅导、概念讲解、资源推荐

**核心文件**:

| 文件 | 说明 |
|------|------|
| `SOUL.md` | 人设定义：耐心、博学、善于拆解、鼓励探索 |
| `IDENTITY.md` | 身份信息：名称、职责、专业领域 |
| `AGENTS.md` | 工作区规则 + 路由规则 |

**触发关键词**: 学习、研究、教程、概念、入门、原理、学习路线、怎么学、什么是、解释

---

## ✍️ Wri·执笔人（Writer Agent）

**位置**: `~/.openclaw/workspace-writer-agent/`

**职责**: 写作、润色、博客、文案

**核心文件**:

| 文件 | 说明 |
|------|------|
| `SOUL.md` | 人设定义：文思敏捷、生动有趣、注重逻辑、善于倾听 |
| `IDENTITY.md` | 身份信息：名称、职责、专业领域 |
| `AGENTS.md` | 工作区规则 + 路由规则 |
| `BLOG-GUIDE.md` | 博客写作规范（Front Matter、结构、格式） |

**触发关键词**: 写博客、文章、润色、写作、文案、发布、大纲、翻译、改写、优化

**特殊规则**: 所有博客提交前必须经过用户评审

---

## 💰 Fin·财多多（Finance Agent）

**位置**: `~/.openclaw/workspace-finance-agent/`

**职责**: 理财建议、投资分析、预算规划

**核心文件**:

| 文件 | 说明 |
|------|------|
| `SOUL.md` | 人设定义：精明谨慎、以数据说话、注重隐私、理性分析 |
| `IDENTITY.md` | 身份信息：名称、职责、专业领域 |
| `AGENTS.md` | 工作区规则 + 路由规则 |
| `TOOLS.md` | 工具配置（免费数据源：Alpha Vantage、CoinGecko 等） |

**触发关键词**: 理财、投资、股票、基金、预算、省钱、财务、收益、风险、定投、资产配置

**隐私保护**: 敏感财务数据仅存储于本地记忆，不写入共享记忆

---

## 📋 全局规则（RULES.md）

所有 Agent 启动时必须读取并遵守的全局规则：

| 规则 ID | 名称 | 优先级 | 适用 Agent |
|--------|------|--------|-----------|
| RULE-001 | 博客发布评审流程 | P0（强制） | Wri·执笔人、小黑 - 管家 |
| RULE-002 | 群聊消息归属混合模式 | P0（强制） | 所有 Agent |
| RULE-003 | 多 Agent 协作工作流记录 | P1（重要） | 小黑 - 管家 |
| RULE-004 | 搜索工具优先级策略 | P1（重要） | 所有 Agent |
| RULE-005 | 挑战式交互原则 | P2（建议） | 所有 Agent |

**违规处理**:
- P0 违规：立即停止，向用户报告
- P1 违规：记录日志，事后报告
- P2 违规：参考执行

---

## 🔄 路由机制（ROUTING.md）

### 路由决策树

```
用户输入
   │
   ├─ 显式指定 Agent？（如 @Dev·技术匠） → 直接转交
   │
   ├─ 关键词匹配 ≥2 个？ → 转交对应 Agent
   │
   ├─ 关键词冲突或模糊？ → LLM 意图识别
   │
   ├─ 通用知识/闲聊/简单查询？ → 小黑直接处理
   │
   └─ 混合需求？ → 小黑启动协作流程（串行/并行调度）
```

### 群聊消息归属规则（混合模式）

**优先级**：
1. 有 @ → 回复指定的人
2. 有引用 → 回复引用的消息
3. 无@无引用 → 智能判断话题连续性
4. 不确定 → 提示用户确认

**语义相似度阈值**：
- ≥ 0.8: 高置信度，直接回复
- 0.6-0.8: 中等置信度，直接回复
- < 0.6: 低置信度，提示确认

---

## 🧠 记忆系统（MEMORY-SHARING.md）

### 记忆分类

| 类型 | 存储位置 | 内容 | 访问权限 |
|------|---------|------|---------|
| **全局记忆** | `MEMORY.md` | 用户基本信息、项目背景、重要决策 | 所有 Agent 可读，仅小黑可写 |
| **专业记忆** | `workspace-{agent}/memory/` | 领域特定偏好、项目进度 | 仅对应 Agent 可读写 |
| **会话记忆** | `sessions/` | 当前对话历史 | 仅对应 Agent 可访问 |

### 记忆共享流程

```
子 Agent → 发现重要信息 → 通知小黑 → 小黑确认 → 写入 MEMORY.md
```

---

## 📊 协作工作流（WORKFLOW-TEMPLATE.md）

### 工作流记录模板

**记录时机**:
- 单 Agent 任务：不记录
- 多 Agent 协作（≥2 个专业 Agent）：必须记录

**记录位置**: `memory/workflow-{YYYY-MM-DD-HHMMSS}.md`

### 事后总结展示（方案 B）

多 Agent 协作完成后，向用户展示精简摘要：

```
🖤 小黑：任务完成！

【协作过程】
📚 Edu·伴学堂 → 研究量化交易基础（2.5 分钟）
🔧 Dev·技术匠 → 编写示例代码（3 分钟）
✍️ Wri·执笔人 → 整合撰写文章（2 分钟）

【总耗时】7.5 分钟
【产出】博客文章 + 示例代码

【最终结果】
[博客链接]
```

---

## 📝 博客写作规范（BLOG-GUIDE.md）

### Front Matter 格式

```yaml
---
title: AI 能力集 -- OpenClaw 一人团队 Multi-Agent 系统设计与搭建
categories: [AI, AI 能力集]
tags: [AI, OpenClaw, Multi-Agent, 自动化]
---
```

### 文章结构

```markdown
## 1. 引言

## 2. 为什么需要 Multi-Agent 系统

## 3. 系统架构设计

## 4. 搭建步骤

## 5. 验证和测试

## 6. 性能优化

## 7. 常见问题

## 8. 总结

## 参考链接
```

### 格式要求

- 章节编号：`1.` `2.` `3.`（不是 `一、` `二、`）
- 语言风格：技术实践型，简洁直接
- 代码示例：带注释，可运行

---

## 🛠️ 工具配置（Fin·财多多 TOOLS.md）

### 免费数据源

| 数据源 | 用途 | API Key |
|--------|------|---------|
| Alpha Vantage | 股票行情 | 需要（免费 25 次/天） |
| CoinGecko | 加密货币 | 无需 |
| 新浪财经 | A 股行情 | 无需 |
| Exchangerate.host | 外汇汇率 | 无需 |

### 配置步骤

1. 注册 Alpha Vantage：https://www.alphavantage.co/support/#api-key
2. 添加到 Gateway 环境变量：`openclaw config.patch`
3. 重启 Gateway：`openclaw gateway restart`

---

## 📦 归档说明

### 归档目的

1. **备份配置文件**：防止意外丢失
2. **版本管理**：通过 Git 跟踪配置变更
3. **学习参考**：便于学习 Multi-Agent 系统设计
4. **快速恢复**：需要时可快速重建环境

### 更新策略

- **定期归档**：每周或配置变更时归档
- **Git 提交**：每次归档后提交到 ai-playground 仓库
- **版本标记**：重要变更添加 Git Tag

### 恢复方法

如需恢复配置：

```bash
# 1. 备份当前配置
cp -r ~/.openclaw/workspace ~/.openclaw/workspace.backup

# 2. 从归档恢复
cp -r /path/to/ai-playground/design/一人团队配置文件归档/小黑 - 管家/* ~/.openclaw/workspace/
# 其他 Agent 同理

# 3. 重启 Gateway
openclaw gateway restart
```

---

## 🔗 相关文档

- [一人团队设计文档](一人团队设计.md)
- [一人团队 Multi-Agent 系统设计](一人团队-Multi-Agent-系统设计.md)
- [CrewAI + LangChain 学习材料包](../learning/crewai-langchain/README.md)

---

**归档完成时间**: 2026-03-09  
**维护者**: 小黑 - 管家 🖤

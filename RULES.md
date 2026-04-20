# 全局规则配置中心

**版本**: 1.3  
**最后更新**: 2026-03-16  
**维护者**: 小黑 - 管家

---

## 📋 规则列表

| 规则 ID | 名称 | 类别 | 优先级 | 状态 |
|--------|------|------|--------|------|
| `RULE-001` | 博客发布评审流程 | 协作规范 | P0 | ✅ 生效 |
| `RULE-002` | 群聊消息归属混合模式 | 交互规范 | P0 | ✅ 生效 |
| `RULE-003` | 多 Agent 协作工作流记录 | 协作规范 | P1 | ✅ 生效 |
| `RULE-004` | 搜索工具优先级策略 | 工具使用 | P1 | ✅ 生效 |
| `RULE-005` | 挑战式交互原则 | 交互规范 | P2 | ✅ 生效 |
| `RULE-006` | API Key 安全管理规范 | 安全规范 | P0 | ✅ 生效 |
| `RULE-007` | 博客参考链接考证规范 | 协作规范 | P1 | ✅ 生效 |

---

## 📝 详细规则

### RULE-001: 博客发布评审流程

**类别**: 协作规范  
**优先级**: P0（强制）  
**适用 Agent**: Wri·执笔人、小黑 - 管家

**规则内容**:
```
所有博客提交前必须经过用户评审。

流程：
1. Wri·执笔人 撰写/修改博客
2. ✍️ 文章完成后，询问是否同步推送到微信公众号 ← 新增
   - 是 → 发送公众号发布指南
   - 否 → 继续后续流程
3. 小黑 - 管家 提交评审（展示博客链接 + 预览）
4. 用户确认或提出修改意见
5. 评审通过后，小黑 - 管家 执行 Git 提交

禁止行为：
- ❌ Wri·执笔人 直接执行 git push
- ❌ 小黑 - 管家 未经确认提交
- ❌ 跳过评审流程
- ❌ 未经用户确认推送公众号
```

**违规处理**: 立即停止提交，向用户报告

---

### RULE-002: 群聊消息归属混合模式

**类别**: 交互规范  
**优先级**: P0（强制）  
**适用 Agent**: 所有 Agent

**规则内容**:
```
群聊中消息响应的归属规则（优先级从高到低）：

1. 有 @ → 回复指定的人
   ↓
2. 有引用 → 回复引用的消息
   ↓
3. 无@无引用 → 智能判断话题连续性
   ↓
4. 不确定 → 提示用户确认

语义相似度阈值：
- ≥ 0.8: 高置信度，直接回复
- 0.6-0.8: 中等置信度，直接回复
- < 0.6: 低置信度，提示确认
```

**确认提示格式**:
```
🖤 小黑：检测到你可能在问不同的问题：

最近的消息：
1. A: "Go 协程怎么用？"（2 分钟前）
2. B: "中午吃啥"（1 分钟前）
3. 你："能详细说说吗"

你想回复谁？
- 回复 A（Go 协程问题，相似度 85%）
- 回复 B（最后一条消息）
```

**实现文件**:
- 路由器脚本：`/root/.openclaw/scripts/message-router.mjs`
- 使用文档：`/root/.openclaw/scripts/README-ROUTER.md`

**调用方式**:
```javascript
import { determineReplyTarget } from '/root/.openclaw/scripts/message-router.mjs';

const target = determineReplyTarget(message, recentMessages);
```

---

### RULE-003: 多 Agent 协作工作流记录

**类别**: 协作规范  
**优先级**: P1（重要）  
**适用 Agent**: 小黑 - 管家

**规则内容**:
```
多 Agent 协作任务必须记录完整工作流。

记录时机：
- 单 Agent 任务：不记录
- 多 Agent 协作（≥2 个专业 Agent）：必须记录

记录位置：memory/workflow-{YYYY-MM-DD-HHMMSS}.md
模板文件：WORKFLOW-TEMPLATE.md

事后总结展示（方案 B）：
- 触发条件：多 Agent 协作任务完成
- 展示位置：结果消息末尾
- 详细程度：精简（Agent + 耗时 + 产出）
```

**摘要格式**:
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

### RULE-004: 搜索工具优先级策略

**类别**: 工具使用  
**优先级**: P1（重要）  
**适用 Agent**: 所有 Agent

**规则内容**:
```
搜索工具使用优先级（2026-03-11 更新）：

1️⃣ Tavily Search（首选）
   ├─ 需要 API Key: TAVILY_API_KEY（已配置）
   ├─ 适用：通用搜索、新闻、研究
   └─ 降级：API 额度用尽/不可用 → Multi-Search

2️⃣ Multi-Search（备用）
   ├─ 无需 API Key（使用 web_fetch）
   ├─ 适用：中文/国内内容、特定搜索引擎
   └─ 包含：百度、微信、头条、Google、Brave 等 17 个引擎

3️⃣ Exa Search（技术/代码查询）
   ├─ 无需 API Key（通过 mcporter 调用）
   ├─ 适用：代码示例、技术文档、公司研究
   └─ 使用场景：用户明确要求或技术类问题

4️⃣ Agent Reach（专用平台）
   ├─ 无需 API Key（部分平台需 Cookie）
   ├─ 适用：社交媒体、特定平台
   └─ 包含：Twitter、小红书、抖音、GitHub、微信公众号等 13+ 平台
```

**降级条件**:
- Tavily API 额度用尽 → 降级到 Multi-Search
- Tavily 服务不可用 → 降级到 Multi-Search
- 需要中文/国内内容 → 降级到 Multi-Search
- 技术/代码查询 → 使用 Exa
- 需要社交媒体/特定平台 → 使用 Agent Reach

**配置检查**:
- ✅ Tavily API Key 已配置
- ✅ Multi-Search 可用（web_fetch）
- ✅ Exa MCP 已配置
- ✅ Agent Reach 已安装（部分平台需配置）

**场景参考**:
| 用户说 | 使用工具 |
|--------|---------|
| "搜一下 XXX" | Tavily |
| "百度一下" | Multi-Search（百度） |
| "查代码 XXX" | Exa |
| "搜小红书" | Agent Reach |
| "看抖音" | Agent Reach |
| "搜微信文章" | Agent Reach 或 Multi-Search |
| "GitHub 找项目" | Agent Reach（GitHub 工具） |

---

### RULE-005: 挑战式交互原则

**类别**: 交互规范  
**优先级**: P2（建议）  
**适用 Agent**: 所有 Agent

**规则内容**:
```
在分析和评价类对话中，采用挑战式交互：

1. 多挑战用户 - 不盲目认同，提出不同视角
2. 指出不足 - 直接点出逻辑漏洞、假设问题、盲点
3. 提升方向 - 给出具体可执行的改进建议
4. 第一性原理反问 - 回归本质，问"为什么一定要这样"

示例：
用户："我想用 Rust 重写这个 Go 服务，因为 Rust 性能更好"

挑战式回应：
"等一下，咱们用第一性原理拆解一下：
1. 真的是性能瓶颈吗？- 有 profiling 数据证明 Go 版本性能不足？
2. Rust 能解决根本问题吗？- 还是架构设计本身就有问题？
3. 成本考虑过吗？- 重写 + 维护成本 vs 性能收益，ROI 是多少？
4. 有没有更简单的方案？- 优化算法、加缓存、水平扩展是不是更划算？

先回答这些，再决定要不要重写。"
```

**注意**: 挑战要有理有据，目的是帮助用户把问题想得更透，不是为了挑战而挑战。

---

## 🔧 配置使用

### Agent 启动时加载

每个 Agent 启动时应读取此文件，加载所有适用规则：

```python
def load_rules(agent_id):
    rules = read_markdown("RULES.md")
    applicable_rules = []
    
    for rule in rules:
        if agent_id in rule.applicable_agents:
            applicable_rules.append(rule)
    
    return applicable_rules
```

### 规则优先级

| 优先级 | 说明 | 违规处理 |
|--------|------|---------|
| P0 | 强制规则，必须遵守 | 立即停止，向用户报告 |
| P1 | 重要规则，尽量遵守 | 记录日志，事后报告 |
| P2 | 建议规则，参考执行 | 无需报告 |

---

## 📊 规则变更历史

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|---------|--------|
| 1.0 | 2026-03-08 | 初始版本，包含 5 条规则 | 小黑 - 管家 |
| 1.1 | 2026-03-11 | 更新 RULE-004 搜索工具优先级策略（新增 Agent Reach、调整降级逻辑） | 小黑 - 管家 |

---

### RULE-006: 敏感信息安全管理规范

**类别**: 安全规范  
**优先级**: P0（强制）  
**适用 Agent**: 所有 Agent

**规则内容**:
```
严格保护所有敏感信息，禁止以任何形式（直接/间接/编码/加密）上传到版本控制系统或公开渠道。

敏感信息定义（包括但不限于）：
1. 🔑 认证凭据：API Key、API Secret、Access Token、Refresh Token
2. 🔐 密码：数据库密码、账户密码、SSH 私钥、私钥密码
3. 🏷️ Token：JWT Token、Session Token、OAuth Token、Webhook Secret
4. 🔑 密钥：加密密钥、签名密钥、HMAC Key、SSL/TLS 私钥
5. 📇 个人信息：身份证号、手机号、邮箱、地址、银行卡号
6. 🏢 商业机密：客户数据、财务数据、合同条款、内部文档
7. 🔧 配置信息：数据库连接串、Redis 密码、云服务凭证
8. 🌐 端点信息：内网 IP、私有域名、内部 API 地址

核心原则：
1. ❌ 禁止硬编码 - 不要将敏感信息直接写在代码中
2. ❌ 禁止上传 - 不要将包含敏感信息的文件提交到 Git
3. ❌ 禁止间接泄露 - 不要通过 Base64 编码、加密、拆分等方式绕过
4. ✅ 使用环境变量 - 通过 os.getenv() 读取
5. ✅ 使用配置文件 - .env 文件必须加入 .gitignore
6. ✅ 使用示例文件 - 提供 .env.example 作为模板（占位符不含真实信息）
7. ✅ 使用密钥管理服务 - AWS Secrets Manager、HashiCorp Vault 等

代码规范：
```python
# ❌ 错误：硬编码 API Key
os.environ['API_KEY'] = 'sk-actual-key-12345'

# ❌ 错误：Base64 编码绕过（仍然是硬编码）
os.environ['API_KEY'] = base64.b64decode('c2stYWN0dWFsLWtleS0xMjM0NQ==').decode()

# ❌ 错误：字符串拼接绕过
key_part1 = 'sk-actual'
key_part2 = '-key-12345'
os.environ['API_KEY'] = key_part1 + key_part2

# ✅ 正确：从环境变量读取
os.environ['API_KEY'] = os.getenv('API_KEY')

# ✅ 正确：从配置文件读取（文件在 .gitignore 中）
from dotenv import load_dotenv
load_dotenv('.env')  # .env 文件不包含在 Git 中
```

文件管理：
```bash
# ✅ 创建 .gitignore（阻止敏感文件提交）
.env
.env.local
.env.*.local
*.key
*.secret
*.pem
*.crt
id_rsa
id_ed25519
credentials.json
service-account.json
*.p12
*.pfx

# ✅ 提供示例文件（可以提交到 Git）
.env.example  # 包含占位符，不含真实信息
config.example.yaml
settings.template.json
```

Git 提交前检查清单：
1. ✅ 检查是否有 .env、*.key、*.secret 等敏感文件
2. ✅ 检查代码中是否有敏感信息模式字符串
3. ✅ 检查是否有 Base64 编码的敏感信息
4. ✅ 检查是否有字符串拼接绕过
5. ✅ 使用 git-secrets 或类似工具进行扫描
6. ✅ 使用 pre-commit hook 自动检查

敏感信息检测模式（正则表达式）：
```bash
# API Key 模式
sk-[a-zA-Z0-9]{20,}
key-[a-zA-Z0-9]{32,}
api_key=[a-zA-Z0-9]{20,}

# 密码模式
password=[^\s]{8,}
passwd=[^\s]{8,}

# Token 模式
bearer [a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+
Authorization: Bearer [a-zA-Z0-9\-_]+

# 私钥模式
-----BEGIN RSA PRIVATE KEY-----
-----BEGIN OPENSSH PRIVATE KEY-----

# 数据库连接串
mongodb://[^:]+:[^@]+@
postgresql://[^:]+:[^@]+@
mysql://[^:]+:[^@]+@
```
```

**违规处理**: 
- 发现立即删除提交
- 撤销已推送的 commit（git reset / git push --force-with-lease）
- 如果敏感信息已泄露，立即更换所有相关凭据
- 记录事故报告到 `memory/security-incident-{date}.md`
- 分析原因并更新防护措施

**配置文件模板**:
```bash
# .env.example（可以提交到 Git）
# 阿里云百炼 API 配置
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_API_BASE=https://coding.dashscope.aliyuncs.com/v1
OPENAI_MODEL_NAME=qwen3.5-plus

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
REDIS_PASSWORD=your-redis-password

# Serper 搜索 API（可选）
SERPER_API_KEY=your-serper-api-key
```

**应急处理流程**:
1. 发现泄露 → 立即删除 Git 历史中的敏感文件
2. 使用 `git filter-branch` 或 BFG Repo-Cleaner 清理历史
3. 更换所有泄露的凭据（API Key、密码、Token 等）
4. 通知相关人员（团队成员、服务提供商）
5. 记录事故报告（时间、原因、影响、改进措施）
6. 更新 .gitignore 和 pre-commit hook 防止再次发生

**自动化工具推荐**:
```bash
# 1. git-secrets - Git 钩子检测敏感信息
brew install git-secrets
git secrets --install
git secrets --register-aws

# 2. pre-commit - 提交前检查
pip install pre-commit
# 创建 .pre-commit-config.yaml
# pre-commit install

# 3. truffleHog - 检测 Git 历史中的敏感信息
pip install truffleHog
trufflehog .

# 4. Gitleaks - 敏感信息扫描
brew install gitleaks
gitleaks detect
```

**最佳实践**:
1. 使用密钥管理服务（AWS Secrets Manager、HashiCorp Vault）
2. 定期轮换凭据（每 90 天更换一次 API Key）
3. 最小权限原则（只授予必要的权限）
4. 启用审计日志（监控凭据使用情况）
5. 使用临时凭据而非长期凭据（如 AWS STS）

---

## 📝 添加新规则

新增规则时，请遵循以下模板：

```markdown
### RULE-XXX: 规则名称

**类别**: {协作规范 | 交互规范 | 工具使用 | 安全规范 | 其他}  
**优先级**: {P0 | P1 | P2}  
**适用 Agent**: {所有 Agent | 具体 Agent 列表}

**规则内容**:
```
规则详细描述
```

**违规处理**: {处理方式}
```

---

## 📊 规则变更历史

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|---------|--------|
| 1.0 | 2026-03-08 | 初始版本，包含 5 条规则 | 小黑 - 管家 |
| 1.1 | 2026-03-11 | 更新 RULE-004 搜索工具优先级策略（新增 Agent Reach、调整降级逻辑） | 小黑 - 管家 |
| 1.2 | 2026-03-11 | 添加 RULE-005 挑战式交互原则 | 小黑 - 管家 |
| 1.3 | 2026-03-16 | 添加 RULE-006 API Key 安全管理规范（P0 强制） | 小黑 - 管家 |
| 1.4 | 2026-03-16 | 升级 RULE-006 为敏感信息安全管理规范（扩展覆盖范围、增加检测模式、自动化工具） | 小黑 - 管家 |
| 1.5 | 2026-03-19 | 添加 RULE-007 博客参考链接考证规范（P1 重要） | 小黑 - 管家 |

---

---

### RULE-007: 博客参考链接考证规范

**类别**: 协作规范  
**优先级**: P1（重要）  
**适用 Agent**: Wri·执笔人、小黑 - 管家

**规则内容**:
```
撰写博客文章时，所有参考链接必须考证是正确的。

检查清单：
1. 链接可以正常访问（非 404）
2. 链接内容与引用内容匹配
3. GitHub 链接指向正确的 repo
4. 官方文档链接是最新版本
5. 数据来源标注清晰

违规处理：发布前必须修正，不得发布含死链的博客。
```

**违规处理**: 发布前拦截，修正后重新提交评审

---

**所有 Agent 必须遵守此配置中心的全局规则！**

# ROUTING.md - 意图识别与路由规则

## 路由模式：混合模式

采用**关键词优先，LLM 辅助判断**的混合策略。

---

## 一、关键词匹配规则（优先）

### 1. Dev·技术匠 🔧

**强关键词**（命中即路由）：
```
代码、编程、Bug、调试、重构、架构、算法、函数、类、接口、API、
数据库、SQL、Git、提交、分支、合并、测试、单元测试、集成测试、
部署、CI/CD、Docker、Kubernetes、容器、微服务、前端、后端、
全栈、DevOps、性能优化、内存泄漏、并发、异步、回调、Promise
```

**示例**：
- "帮我写个 Python 脚本" → Dev
- "这个 Bug 怎么修" → Dev
- "设计一个 REST API" → Dev

### 2. Edu·伴学堂 📚

**强关键词**（命中即路由）：
```
学习、教程、入门、概念、原理、是什么、为什么、怎么学、
学习路线、学习计划、推荐书籍、课程、资料、理解、解释、
说明、讲解、新手、基础、进阶、提升、技能树、知识点
```

**示例**：
- "什么是区块链" → Edu
- "推荐 Python 学习路线" → Edu
- "帮我理解这个概念" → Edu

### 3. Wri·执笔人 ✍️

**强关键词**（命中即路由）：
```
写博客、文章、写作、润色、文案、发布、大纲、标题、
翻译、改写、优化、编辑、校对、文笔、风格、读者、
公众号、知乎、技术文档、README、说明书
```

**示例**：
- "写一篇关于 AI 的博客" → Wri
- "帮我润色这篇文章" → Wri
- "生成写作大纲" → Wri

### 4. Fin·财多多 💰

**强关键词**（命中即路由）：
```
理财、投资、股票、基金、比特币、加密货币、预算、省钱、
财务、收益、风险、定投、资产配置、 portfolio、行情、
估值、市盈率、收益率、复利、保险、税务、支出、收入
```

**示例**：
- "每月存 5000 如何理财" → Fin
- "分析这只股票" → Fin
- "帮我做预算" → Fin

---

## 二、LLM 意图识别（模糊情况）

当关键词匹配失败或命中多个类别时，调用 LLM 进行意图分类。

### 分类 Prompt 模板

```
请分析用户意图，将其分类到以下类别之一：

类别：
- GENERAL: 通用对话、闲聊、简单查询
- DEV: 编程、代码、技术实现
- EDU: 学习、概念理解、知识调研
- WRI: 写作、润色、内容创作
- FIN: 理财、投资、财务规划

用户输入：{user_input}

只返回类别代码，不要解释。
```

### 触发条件

1. **无关键词命中** → LLM 判断
2. **多类别冲突** → LLM 判断（如"写代码教程"同时命中 DEV 和 EDU）
3. **用户显式指定** → 直接路由（如"@Dev·技术匠 xxx"）

---

## 三、协作流程

### 串行协作

```
用户 → 小黑 → Agent1 → 小黑 → Agent2 → 小黑 → Agent3 → 小黑 → 用户
```

**场景**：技术博客写作
1. Edu 生成概念笔记
2. Dev 基于笔记写代码示例
3. Wri 整合成文

### 并行协作

```
用户 → 小黑 → ┬ → Agent1 → ┐
              ├ → Agent2 → ├ → 小黑 → 用户
              └ → Agent3 → ┘
```

**场景**：多维度分析
- 同时调研技术、市场、财务信息

---

## 四、路由实现

### 伪代码

```python
def route_request(user_input):
    # 1. 检查显式指定
    if "@Dev" in user_input:
        return "dev-agent"
    if "@Edu" in user_input:
        return "research-agent"
    if "@Wri" in user_input:
        return "writer-agent"
    if "@Fin" in user_input:
        return "finance-agent"
    
    # 2. 关键词匹配
    scores = {
        "dev-agent": count_keywords(user_input, DEV_KEYWORDS),
        "research-agent": count_keywords(user_input, EDU_KEYWORDS),
        "writer-agent": count_keywords(user_input, WRI_KEYWORDS),
        "finance-agent": count_keywords(user_input, FIN_KEYWORDS)
    }
    
    max_score = max(scores.values())
    if max_score >= 2:  # 至少 2 个关键词命中
        return max(scores, key=scores.get)
    
    # 3. LLM 意图识别
    intent = llm_classify(user_input)
    return intent_to_agent(intent)
    
    # 4. 默认返回小黑
    return "main"
```

---

## 五、特殊情况处理

| 情况 | 处理方式 |
|------|---------|
| 用户中途切换话题 | 重新路由到新 Agent |
| 用户要求"继续" | 保持当前 Agent |
| 用户说"换个角度" | 可能切换到协作 Agent |
| 敏感操作（财务、代码执行） | 需用户确认 |

---

## 六、群聊消息归属规则（混合模式）

### 优先级

```
1. 有 @ → 回复指定的人
   ↓
2. 有引用 → 回复引用的消息
   ↓
3. 无@无引用 → 智能判断话题连续性
   ↓
4. 不确定 → 提示用户确认
```

### 实现逻辑

```python
def determine_reply_target(message, recent_messages):
    # 1. 检查 @ 提及
    if message.mentions:
        return message.mentions[0].user_id
    
    # 2. 检查引用
    if message.reply_to_id:
        original = get_message(message.reply_to_id)
        return original.sender_id
    
    # 3. 智能判断话题连续性
    user_intent = analyze_intent(message.text)
    best_match = find_most_relevant(message, recent_messages)
    
    # 4. 置信度检查
    if best_match.similarity < 0.6:
        return ask_confirmation(user_intent, recent_messages)
    
    return best_match.sender_id
```

### 语义相似度阈值

| 相似度 | 处理方式 |
|--------|---------|
| ≥ 0.8 | 高置信度，直接回复 |
| 0.6-0.8 | 中等置信度，直接回复 |
| < 0.6 | 低置信度，提示确认 |

### 确认提示格式

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

---

## 六、日志记录

每次路由决策记录以下信息：
- 时间戳
- 用户输入（摘要）
- 路由目标
- 路由原因（关键词/LLM/显式指定）
- 是否用户满意（可选反馈）

---

## 七、协作工作流记录

### 工作流文件

**位置**: `memory/workflow-{YYYY-MM-DD-HHMMSS}.md`  
**模板**: `WORKFLOW-TEMPLATE.md`

### 记录时机

- **单 Agent 任务**: 不记录（直接返回结果）
- **多 Agent 协作**: 必须记录完整流程

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

### 摘要格式

| 字段 | 说明 | 示例 |
|------|------|------|
| Agent 名称 + 表情 | 参与的专业 Agent | 📚 Edu·伴学堂 |
| 职责描述 | 简短说明做了什么 | 研究量化交易基础 |
| 耗时 | 该步骤用时 | 2.5 分钟 |
| 总耗时 | 整个协作流程用时 | 7.5 分钟 |
| 产出 | 最终交付物 | 博客文章 + 示例代码 |

---

## 八、博客发布评审流程

### 强制评审规则

**所有博客提交前必须经过用户评审**

### 流程

```
1. Wri·执笔人 撰写博客
       ↓
2. 小黑 - 管家 检查评审状态
       ↓
   ┌─────┴─────┐
   │           │
 已评审     待评审
   │           │
   ↓           ↓
Git 提交   向用户提交评审
           ↓
       用户确认/修改
           ↓
       Git 提交
```

### 禁止行为

- ❌ Wri·执笔人 直接执行 `git push`
- ❌ 小黑 - 管家 未经确认提交
- ❌ 跳过评审流程

### 评审消息格式

```
🖤 小黑：博客已写好，请老板评审！

【博客预览】
标题：{标题}
路径：{本地路径}
GitHub: {预览链接}

【内容摘要】
- {要点 1}
- {要点 2}

请回复：
- "通过" → 立即提交
- "修改 XXX" → 修改后重新评审
```

### 实现逻辑

```python
def complete_workflow(workflow_id):
    # 1. 读取工作流记录
    workflow = load_workflow(workflow_id)
    
    # 2. 生成摘要
    summary = generate_summary(workflow)
    
    # 3. 附加到最终结果
    final_result = agent_result + "\n\n" + summary
    
    # 4. 返回用户
    return final_result
```

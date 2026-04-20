# SDD + TDD + Harness AI 工程实践研究

**归档日期**: 2026-04-03  
**搜索执行**: OpenClaw 子代理（Tavily Search）  
**资源总数**: 40+ 条（4 类搜索 × 5 条/类 × 2 主题）

---

## 📋 目录

1. [核心趋势](#核心趋势)
2. [SDD 规格驱动开发](#sdd-规格驱动开发)
3. [TDD 测试驱动开发 + AI](#tdd-测试驱动开发--ai)
4. [Harness 工程实践](#harness-工程实践)
5. [评估框架与基准](#评估框架与基准)
6. [工具推荐](#工具推荐)
7. [学习路径](#学习路径)

---

## 🎯 核心趋势

### 范式转变
```
从"写代码" → "编写精确规格 + 编排 AI + 约束环境"
```

### 三位一体框架
```
┌──────────────────────────────────────────────────────────────┐
│           AI 时代软件工程三位一体                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   📋 SDD (规格驱动)                                           │
│   "做正确的事" - 需求→规格→契约                               │
│                                                              │
│         ↓ 规格传递给                                          │
│                                                              │
│   ✅ TDD (测试驱动)                                           │
│   "正确地做事" - 测试→实现→重构                               │
│                                                              │
│         ↓ 运行在                                              │
│                                                              │
│   🏗️ Harness (约束环境)                                       │
│   "安全地做事" - 沙箱→监控→评估                               │
│                                                              │
│   人类角色：指挥家 + 审查者 + 架构师                          │
└──────────────────────────────────────────────────────────────┘
```

### 核心论点（OpenAI & Anthropic 验证）
> "Agents aren't hard; the Harness is hard."  
> （代理不难，难的是 Harness）

---

## 📋 SDD 规格驱动开发

### 核心资源

| # | 标题 | URL | 亮点 |
|---|------|-----|------|
| 1 | [ThoughtWorks: Spec-driven development 2025](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices) | 深度解析 2025 年新兴 AI 工程实践 |
| 2 | [GitHub Spec-Kit 框架](https://blog.tadsummit.com/2025/11/19/spec-driven-development/) | SDD 为 AI 生成生产就绪代码提供精确基础 |
| 3 | [2026 实践指南：Claude Code + SDD](https://www.nvarma.com/blog/2026-03-01-spec-driven-development-claude-code/) | 如何在编码前结构化思考 |
| 4 | [Red Hat: SDD 提升 AI 代码质量](https://developers.redhat.com/articles/2025/10/22/how-spec-driven-development-improves-ai-coding-quality) | "人类是指挥家，规格是乐谱" |
| 5 | [OpenSpec 实践](https://medium.com/@gravitano/coding-in-2026-from-writing-code-to-orchestrating-ai-18ad29df0cf0) | 工作流可靠性大幅提升 |
| 6 | [GitHub: Spec-driven toolkit](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/) | 开源工具包入门 |
| 7 | [JetBrains: Spec-driven approach](https://blog.jetbrains.com/junie/2025/10/how-to-use-a-spec-driven-approach-for-coding-with-ai/) | 高级需求细化为开发计划 |
| 8 | [Augment Code: SDD 完整指南](https://www.augmentcode.com/guides/what-is-spec-driven-development) | 规格作为可执行工件 |

### 关键洞察
- SDD 是 2025-2026 年新兴趋势，多家权威机构推广
- 将开发从"不可预测的手工艺"转变为"可扩展的工程学科"
- 核心挑战：管理审查负载和返工成本

---

## ✅ TDD 测试驱动开发 + AI

### 核心资源

| # | 标题 | URL | 亮点 |
|---|------|-----|------|
| 1 | [GitHub: TDD with Copilot](https://github.blog/ai-and-ml/github-copilot/github-for-beginners-test-driven-development-tdd-with-github-copilot/) | 官方指南：自动化测试编写 |
| 2 | [Martin Fowler: TDD with Copilot](https://martinfowler.com/articles/exploring-gen-ai/06-tdd-with-coding-assistance.html) | "AI 在分解问题时表现最佳" |
| 3 | [Cursor + TDD 实战](https://medium.com/@juanmabareamartinez/how-to-use-tdd-with-ai-tools-like-cursor-d41253e4b62e) | 红 - 绿 - 蓝循环详解 |
| 4 | [GitHub 示例项目](https://github.com/dominno/python-git-ttd-cursor-ai-flow) | TDD+Git 工作流实战 |
| 5 | [Builder.io: AI 时代的 TDD](https://www.builder.io/blog/test-driven-development-ai) | 从"被跳过"到"强大方法" |
| 6 | [testRigor: TDD with AI](https://testrigor.com/blog/how-to-handle-tdd-with-ai/) | "人类写测试，AI 生成代码" |
| 7 | [Endor Labs: Test-First Prompting](https://www.endorlabs.com/learn/test-first-prompting-using-tdd-for-secure-ai-generated-code) | 提升 AI 生成代码安全性 |
| 8 | [Perfecto: AI + TDD](https://www.perfecto.io/blog/ai-test-driven-development-tdd) | 从最关键的测试开始应用 AI |

### 关键洞察
- AI 使 TDD 从"被跳过的最佳实践"转变为强大方法
- 警告：AI 生成的测试和代码可能都不正确
- 建议：人类编写测试，AI 重构或生成代码通过测试

---

## 🏗️ Harness 工程实践

### 核心资源

| # | 标题 | URL | 亮点 |
|---|------|-----|------|
| 1 | [OpenAI: Harness Engineering](https://openai.com/index/harness-engineering/) | 官方："无手动输入代码"作为强制功能 |
| 2 | [NXCode: Harness 完整指南](https://www.nxcode.io/resources/news/harness-engineering-complete-guide-ai-agent-codex-2026) | 约束、反馈、生命周期管理 |
| 3 | [Epsilla: Harness 取代 Prompting](https://www.epsilla.com/blogs/harness-engineering-evolution-prompt-context-autonomous-agents) | 用规则、linter 约束提高可靠性 |
| 4 | [Phil Schmid: Agent Harness 2026](https://www.philschmid.de/agent-harness-2026) | 管理长期任务的基础设施 |
| 5 | [Louis Bouchard: Harness 工程](https://www.louisbouchard.ai/harness-engineering/) | AI 代理背后的缺失层 |
| 6 | [Martin Fowler 分析](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) | 深度分析 OpenAI 实践 |
| 7 | [约束驱动开发](https://www.linkedin.com/pulse/ai-harness-constraint-driven-software-development-age-alex-bunardzic-kwrcc) | 建立系统性约束 |
| 8 | [生产级 Harness 构建](https://dev.to/apssouza22/building-a-production-ready-ai-agent-harness-2570) | Deep Agents 框架实战 |

### Harness 核心组件
```
┌─────────────────────────────────────────────────────┐
│                  Agent Harness                       │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  任务调度器  │  │  沙箱环境   │  │  评估引擎   │ │
│  │  Task Queue │  │  Sandbox    │  │  Evaluator  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  工具注册表  │  │  状态追踪   │  │  安全网关   │ │
│  │  Tools      │  │  Tracing    │  │  Gateway    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 关键工程实践
1. **沙箱隔离** - 文件系统、网络、进程、资源限制
2. **工具调用控制** - 白名单、速率限制、权限管理
3. **评估指标** - 正确性、效率、安全、稳定性、成本
4. **测试场景** - 单元、集成、压力、对抗、回归
5. **监控日志** - 会话追踪、工具使用、Token 用量

---

## 📊 评估框架与基准

### 核心资源

| # | 标题 | URL | 亮点 |
|---|------|-----|------|
| 1 | [AgentBench (GitHub)](https://github.com/THUDM/AgentBench) | 综合性基准，OS/数据库多场景 |
| 2 | [IBM Research: 360° 评估](https://research.ibm.com/blog/AI-agent-benchmarks) | 120 种评估方法调研 |
| 3 | [Maxim AI: 框架对比](https://www.getmaxim.ai/blog/llm-agent-evaluation-framework-comparison/) | AgentBench、GAIA 对比 |
| 4 | [Confident AI: 评估指南](https://www.confident-ai.com/blog/definitive-ai-agent-evaluation-guide) | 指标、追踪、测试方法 |
| 5 | [Databricks: 评估介绍](https://www.databricks.com/blog/what-is-agent-evaluation) | 推理、工具使用、决策 |
| 6 | [AWS: Strands Evals 实践](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents-for-production-a-practical-guide-to-strands-evals/) | 从小处开始迭代 |
| 7 | [Maxim AI: 指标与策略](https://www.getmaxim.ai/articles/ai-agent-evaluation-metrics-strategies-and-best-practices/) | 系统性评估方法 |
| 8 | [Arthur AI: 持续评估](https://www.arthur.ai/blog/best-practices-for-building-agents-part-3-continuous-evaluations) | 无监督 + 监督结合 |

### 评估维度
| 维度 | 指标 | 说明 |
|------|------|------|
| **正确性** | Pass Rate | 任务完成成功率 |
| **效率** | Token Usage | 输入/输出/总 Token |
| **安全** | Violation Count | 违规操作次数 |
| **稳定性** | Error Rate | 异常/超时比例 |
| **成本** | Cost/Task | 单次任务成本 |

---

## 🛠️ 工具推荐

### 分类推荐

| 类别 | 工具 | 适用场景 |
|------|------|---------|
| **SDD 规格** | GitHub Spec-Kit, OpenSpec, Claude Code | 需求→规格转换 |
| **TDD 测试** | GitHub Copilot, Cursor, testRigor | 测试生成与验证 |
| **Harness** | OpenClaw ACP, Deep Agents, Harness AI | 代理编排与约束 |
| **评估** | AgentBench, Strands Evals, Maxim AI | 性能基准测试 |
| **监控** | AgentOps, Braintrust, Arthur AI | 生产环境追踪 |

### 主流 Harness 框架对比

| 框架 | 语言 | 特点 | 适用场景 |
|------|------|------|---------|
| **OpenClaw ACP** | TypeScript | 轻量、集成 Gateway | 多 Agent 协作 |
| **LangChain Eval** | Python | 丰富评估指标 | RAG/LLM 评估 |
| **AgentOps** | Python | 监控 + 追踪 | 生产环境 |
| **Braintrust** | TS/Python | 评估平台 | 企业级 |
| **CrewAI** | Python | 多 Agent 编排 | 团队协作 |

---

## 📚 学习路径

### 入门级（1-2 小时）
1. [OpenAI: Harness Engineering](https://openai.com/index/harness-engineering/) - 理解 Harness 工程核心概念
2. [GitHub: Spec-driven development](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/) - 开始 SDD 实践
3. [Martin Fowler: TDD with Copilot](https://martinfowler.com/articles/exploring-gen-ai/06-tdd-with-coding-assistance.html) - TDD+AI 最佳实践

### 进阶级（4-6 小时）
1. [ThoughtWorks: Spec-driven development 2025](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)
2. [NXCode: Harness Engineering 完整指南](https://www.nxcode.io/resources/news/harness-engineering-complete-guide-ai-agent-codex-2026)
3. [AgentBench GitHub](https://github.com/THUDM/AgentBench) - 动手实践评估框架

### 专家级（深入实践）
1. [IBM Research: 360° AI 代理基准测试](https://research.ibm.com/blog/AI-agent-benchmarks) - 120 种评估方法调研
2. [AWS: Strands Evals 生产实践](https://aws.amazon.com/blogs/machine-learning/evaluating-ai-agents-for-production-a-practical-guide-to-strands-evals/)
3. [Epsilla: Harness 工程演进](https://www.epsilla.com/blogs/harness-engineering-evolution-prompt-context-autonomous-agents) - 约束驱动开发

---

## 📝 笔记

- 搜索时间：2026-04-03
- 搜索工具：Tavily Search（通过 OpenClaw 子代理）
- 资源时效性：优先 2025-2026 年最新内容
- 总资源数：40+ 条（去重后约 30 条独特资源）

---

**归档完成** ✅

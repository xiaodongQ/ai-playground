# CrewAI + LangChain 学习材料包

> 📚 完整的 CrewAI 和 LangChain 学习资源，从入门到实战  
> 目标读者：有 C++/Go 经验的开发者，正在搭建 Multi-Agent 系统

---

## 📁 项目结构

```
crewai-langchain-demos/
├── README.md                    # 本文件
├── docs/                        # 文档
│   └── crewai-langchain-research.md  # 框架调研报告
├── demos/                       # Demo 代码
│   ├── crewai-basic/            # CrewAI 基础 Demo
│   ├── crewai-advanced/         # CrewAI 进阶 Demo
│   ├── langchain-basic/         # LangChain 基础 Demo
│   └── langchain-advanced/      # LangChain 进阶 Demo
└── projects/                    # 完整项目
    └── content-creation-crew/   # 自动化内容创作系统
```

---

## 🎯 学习路径

### 阶段 1：快速入门（30 分钟）

1. **阅读框架调研**（10 分钟）
   ```bash
   cat docs/crewai-langchain-research.md
   ```

2. **运行基础 Demo**（20 分钟）
   ```bash
   # CrewAI 基础
   cd demos/crewai-basic
   pip install -r requirements.txt
   python main.py
   
   # LangChain 基础
   cd demos/langchain-basic
   pip install -r requirements.txt
   python main.py
   ```

### 阶段 2：深入理解（60 分钟）

1. **运行进阶 Demo**（30 分钟）
   ```bash
   # CrewAI 进阶（带工具）
   cd demos/crewai-advanced
   python main.py
   
   # LangChain 进阶（带记忆）
   cd demos/langchain-advanced
   python main.py
   ```

2. **阅读代码和注释**（30 分钟）
   - 对比两个框架的异同
   - 理解核心概念的实现方式

### 阶段 3：实战演练（90 分钟）

1. **运行完整项目**（30 分钟）
   ```bash
   cd projects/content-creation-crew
   pip install -r requirements.txt
   ./run.sh "Rust 编程语言"
   ```

2. **修改和扩展**（60 分钟）
   - 添加新的 Agent
   - 集成自定义工具
   - 调整工作流程

---

## 📚 文档索引

| 文档 | 说明 | 链接 |
|------|------|------|
| 框架调研 | CrewAI 和 LangChain 核心概念对比 | [docs/crewai-langchain-research.md](docs/crewai-langchain-research.md) |
| CrewAI 基础 | 双 Agent 协作示例 | [demos/crewai-basic/README.md](demos/crewai-basic/README.md) |
| CrewAI 进阶 | 带工具和三 Agent 流程 | [demos/crewai-advanced/README.md](demos/crewai-advanced/README.md) |
| LangChain 基础 | Chain + Agent 示例 | [demos/langchain-basic/README.md](demos/langchain-basic/README.md) |
| LangChain 进阶 | 记忆 + 结构化输出 | [demos/langchain-advanced/README.md](demos/langchain-advanced/README.md) |
| 完整项目 | 自动化内容创作系统 | [projects/content-creation-crew/README.md](projects/content-creation-crew/README.md) |

---

## 🔧 环境要求

### 必需

- Python 3.10+
- LLM API Key（OpenAI 或 Anthropic）

### 可选

- Serper API Key（用于网络搜索）
- Git（用于版本控制）

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd crewai-langchain-demos

# 安装依赖（每个 Demo 独立）
cd demos/crewai-basic
pip install -r requirements.txt
```

---

## 💡 核心概念速查

### CrewAI

| 概念 | 说明 | 示例 |
|------|------|------|
| Agent | 智能体，有角色和目标 | `Agent(role="研究员", goal="调研...")` |
| Task | 任务，分配给 Agent | `Task(description="...", agent=...)` |
| Crew | 团队，编排 Agent 和 Task | `Crew(agents=[...], tasks=[...])` |
| Process | 执行流程 | `Process.sequential` / `Process.hierarchical` |

### LangChain

| 概念 | 说明 | 示例 |
|------|------|------|
| Model | 语言模型 | `init_chat_model("anthropic:claude-sonnet-4-6")` |
| Tool | 工具，Agent 可调用的函数 | `@tool def my_tool(...): ...` |
| Agent | 智能体，使用工具的 LLM | `create_agent(model="...", tools=[...])` |
| Chain | 链，组合组件 | `chain = prompt \| model` |
| Memory | 记忆，保持对话历史 | `InMemorySaver()` |

---

## 🎓 框架对比

| 维度 | CrewAI | LangChain |
|------|--------|-----------|
| **定位** | 多 Agent 协作编排 | LLM 应用开发框架 |
| **学习曲线** | 低（约定优于配置） | 中（灵活但复杂） |
| **多 Agent** | 原生支持 | 通过 LangGraph |
| **配置方式** | YAML + Python | 纯 Python |
| **工具生态** | CrewAI + LangChain | 丰富集成 |
| **适用场景** | 团队协作任务 | 通用 LLM 应用 |

**建议：**
- 快速搭建多 Agent 系统 → CrewAI
- 构建复杂 LLM 应用 → LangChain
- 最佳实践 → 两者结合使用

---

## 📖 学习资源

### 官方文档

- [CrewAI 文档](https://docs.crewai.com)
- [LangChain 文档](https://python.langchain.com)

### 社区资源

- [CrewAI GitHub](https://github.com/crewAIInc/crewAI)
- [LangChain GitHub](https://github.com/langchain-ai/langchain)
- [CrewAI 社区](https://community.crewai.com)

---

## ❓ 常见问题

### Q: 应该先学哪个框架？

**A:** 建议先学 CrewAI：
- 概念简单，快速上手
- 容易看到多 Agent 协作效果
- 建立信心后再学 LangChain

### Q: 两个框架能一起用吗？

**A:** 可以！推荐方式：
- 用 CrewAI 编排多 Agent 流程
- 用 LangChain 提供工具和模型集成
- 两者工具生态兼容

### Q: 需要多少编程经验？

**A:** 有 C++/Go 经验完全足够：
- Python 语法简单，1 天就能上手
- 框架抽象良好，关注业务逻辑
- Demo 代码有详细注释

### Q: 运行 Demo 需要多少费用？

**A:** 取决于使用频率：
- 学习阶段：$1-5（测试用）
- 完整项目：$5-20（生成多篇文章）
- 建议使用便宜的模型先测试

---

## 🚀 下一步

完成学习后，你可以：

1. **创建自己的项目**
   - 参考 `content-creation-crew` 项目结构
   - 根据需求调整 Agent 和 Task

2. **集成到工作流**
   - 自动化技术文档生成
   - 批量创作博客文章
   - 构建内部知识库

3. **深入学习**
   - LangGraph 高级编排
   - RAG（检索增强生成）
   - Fine-tuning 定制模型

---

## 📝 更新日志

- **2026-03-09**: 初始版本
  - ✅ 框架调研报告
  - ✅ 4 个基础/进阶 Demo
  - ✅ 完整实战项目
  - ✅ 学习指南和 FAQ

---

## 📄 许可证

MIT License

---

**创建时间**: 2026-03-09  
**维护者**: Edu·伴学堂 📚 + Dev·技术匠 🔧 + Wri·执笔人 ✍️ + 小黑 - 管家 🖤

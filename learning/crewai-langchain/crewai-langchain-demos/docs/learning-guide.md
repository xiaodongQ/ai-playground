# CrewAI + LangChain 学习指南

> 从入门到实战的完整教程  
> 目标读者：有 C++/Go 经验的开发者  
> 预计学习时间：3-4 小时

---

## 目录

1. [前言](#1-前言)
2. [框架对比和选择建议](#2-框架对比和选择建议)
3. [快速入门（30 分钟上手）](#3-快速入门 30 分钟上手)
4. [Demo 代码详解](#4-demo-代码详解)
5. [完整场景实战](#5-完整场景实战)
6. [常见问题 FAQ](#6-常见问题-faq)
7. [下一步学习路径](#7-下一步学习路径)

---

## 1. 前言

### 1.1 为什么学习 Multi-Agent 框架？

作为有 C++/Go 背景的开发者，你可能已经熟悉：
- 系统级编程的严谨性
- 性能优化的重要性
- 并发编程的复杂性

现在，LLM 和 Agent 技术正在改变软件开发方式：
- **单个 LLM 能力有限** → 多个 Agent 协作可以完成复杂任务
- **手动编排流程繁琐** → 框架提供标准化抽象
- **重复造轮子** → 利用成熟框架快速搭建

### 1.2 本指南的目标

学完本指南后，你将能够：
- ✅ 理解 CrewAI 和 LangChain 的核心概念
- ✅ 运行和修改 4 个示例 Demo
- ✅ 搭建自己的 Multi-Agent 系统
- ✅ 根据场景选择合适的框架

### 1.3 前置要求

- 编程经验：C++/Go/Python任一即可
- Python 基础：了解基本语法（变量、函数、类）
- API 使用经验：知道如何使用 API Key

---

## 2. 框架对比和选择建议

### 2.1 核心定位

| 框架 | 定位 | 类比 |
|------|------|------|
| **CrewAI** | 多 Agent 协作编排 | 类似"团队管理系统" |
| **LangChain** | LLM 应用开发框架 | 类似"LLM 的 SDK" |

### 2.2 核心概念对比

#### CrewAI 的抽象

```
Agent（员工） → Task（任务） → Crew（团队）
```

**代码示例：**
```python
# 定义员工
researcher = Agent(role="研究员", goal="调研主题")

# 分配任务
task = Task(description="调研 Rust 语言", agent=researcher)

# 组建团队
crew = Crew(agents=[researcher], tasks=[task])
crew.kickoff()
```

#### LangChain 的抽象

```
Model（模型） + Tool（工具） → Agent（智能体）
Chain（链）：组合多个组件
```

**代码示例：**
```python
# 定义工具
@tool
def search(query: str): ...

# 创建 Agent
agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[search]
)

# 运行
agent.invoke({"messages": [...]})
```

### 2.3 选择建议

| 场景 | 推荐框架 | 理由 |
|------|---------|------|
| 多 Agent 协作（Research→Write→Review） | CrewAI | 原生支持，配置简单 |
| 单 Agent + 工具调用 | LangChain | 灵活，工具生态丰富 |
| 复杂流程编排 | LangGraph | 细粒度控制 |
| 快速原型 | CrewAI | 约定优于配置 |
| 生产级应用 | 两者结合 | 取长补短 |

### 2.4 我的建议（针对 C++/Go 开发者）

**学习顺序：**
1. **第 1 天**：CrewAI 基础（概念简单，类似定义类 + 对象）
2. **第 2 天**：CrewAI 进阶（工具、多 Agent）
3. **第 3 天**：LangChain 基础（Chain、Agent）
4. **第 4 天**：LangChain 进阶（记忆、结构化输出）
5. **第 5 天**：实战项目（结合两者）

**理由：**
- CrewAI 学习曲线平缓，容易建立信心
- LangChain 更灵活但概念多，有基础后更容易理解
- 两者结合可以发挥各自优势

---

## 3. 快速入门（30 分钟上手）

### 3.1 环境准备（5 分钟）

```bash
# 1. 安装 Python 3.10+
python --version

# 2. 获取 API Key
# OpenAI: https://platform.openai.com/api-keys
# Anthropic: https://console.anthropic.com/settings/keys

# 3. 设置环境变量
export OPENAI_API_KEY=sk-...
# 或
export ANTHROPIC_API_KEY=sk-...
```

### 3.2 CrewAI 5 分钟上手（10 分钟）

**步骤 1：安装**
```bash
pip install crewai crewai-tools
```

**步骤 2：创建第一个 Crew**
```python
from crewai import Agent, Task, Crew, Process

# 1. 定义 Agent
researcher = Agent(
    role="技术研究员",
    goal="调研{topic}的核心概念",
    backstory="你有 10 年技术研究经验",
    verbose=True
)

# 2. 定义 Task
task = Task(
    description="调研{topic}，输出 5 个核心概念",
    expected_output="5 个核心概念的列表",
    agent=researcher
)

# 3. 创建 Crew
crew = Crew(
    agents=[researcher],
    tasks=[task],
    process=Process.sequential
)

# 4. 执行
result = crew.kickoff(inputs={"topic": "Rust 编程语言"})
print(result)
```

**步骤 3：运行**
```bash
python my_first_crew.py
```

### 3.3 LangChain 5 分钟上手（10 分钟）

**步骤 1：安装**
```bash
pip install langchain langchain-anthropic
```

**步骤 2：创建第一个 Agent**
```python
from langchain.agents import create_agent
from langchain.tools import tool

# 1. 定义工具
@tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    return f"{city}: 晴朗，25°C"

# 2. 创建 Agent
agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_weather],
    system_prompt="你是一个天气助手"
)

# 3. 运行
response = agent.invoke({
    "messages": [{"role": "user", "content": "北京天气怎么样？"}]
})
print(response)
```

**步骤 3：运行**
```bash
python my_first_agent.py
```

### 3.4 对比总结

| 步骤 | CrewAI | LangChain |
|------|--------|-----------|
| 安装 | `crewai` | `langchain` |
| Agent 定义 | `Agent(role=..., goal=...)` | `create_agent(model=..., tools=...)` |
| 执行 | `crew.kickoff()` | `agent.invoke()` |
| 特点 | 角色驱动 | 工具驱动 |

---

## 4. Demo 代码详解

### 4.1 CrewAI 基础 Demo

**位置：** `demos/crewai-basic/`

**场景：** 技术调研团队（Researcher + Writer）

**核心代码：**
```python
# 1. 定义两个 Agent
researcher = Agent(role="技术研究员", goal="调研{topic}")
writer = Agent(role="技术作家", goal="撰写文章")

# 2. 定义两个 Task（有依赖关系）
research_task = Task(description="调研...", agent=researcher)
writing_task = Task(
    description="写作...",
    agent=writer,
    context=[research_task]  # 依赖调研结果
)

# 3. 创建 Crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential  # 顺序执行
)

# 4. 执行
result = crew.kickoff(inputs={"topic": "Rust 编程语言"})
```

**关键点：**
- `context=[research_task]`：Task 依赖
- `Process.sequential`：顺序执行
- `output_file`：输出到文件

**运行：**
```bash
cd demos/crewai-basic
python main.py
```

### 4.2 CrewAI 进阶 Demo

**位置：** `demos/crewai-advanced/`

**新增内容：**
- 三 Agent 协作（Researcher + Writer + Reviewer）
- 集成搜索工具（SerperDevTool）
- 质量审查流程

**核心代码：**
```python
from crewai_tools import SerperDevTool

# 给 Agent 配备工具
researcher = Agent(
    role="高级技术研究员",
    tools=[SerperDevTool()],  # 可以搜索网络
    max_iter=5  # 最大迭代次数
)

# 审查任务
review_task = Task(
    description="审查文章质量...",
    agent=reviewer,
    context=[writing_task]
)
```

**运行：**
```bash
cd demos/crewai-advanced
export SERPER_API_KEY=...  # 可选，用于搜索
python main.py
```

### 4.3 LangChain 基础 Demo

**位置：** `demos/langchain-basic/`

**场景：** 智能助手（Chain + Agent）

**核心代码：**
```python
# 1. Chain 示例
from langchain.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{expertise}专家"),
    ("user", "{question}")
])

chain = prompt | model
response = chain.invoke({"expertise": "Python", "question": "什么是装饰器？"})

# 2. Agent 示例
@tool
def get_weather(city: str): ...

agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_weather]
)
```

**关键点：**
- `|` 管道操作符：组合组件
- `@tool` 装饰器：定义工具
- `invoke()`：执行

**运行：**
```bash
cd demos/langchain-basic
python main.py
```

### 4.4 LangChain 进阶 Demo

**位置：** `demos/langchain-advanced/`

**新增内容：**
- 多轮对话记忆
- 结构化输出
- 运行时上下文

**核心代码：**
```python
# 1. 定义上下文
@dataclass
class UserContext:
    user_id: str
    user_name: str

# 2. 定义响应格式
@dataclass
class WeatherResponse:
    greeting: str
    temperature: str
    suggestion: str

# 3. 创建带记忆的 Agent
checkpointer = InMemorySaver()

agent = create_agent(
    model=model,
    tools=[...],
    context_schema=UserContext,
    response_format=ToolStrategy(WeatherResponse),
    checkpointer=checkpointer  # 启用记忆
)

# 4. 多轮对话
config = {"configurable": {"thread_id": "conversation_001"}}
agent.invoke(..., config=config, context=UserContext(...))
```

**关键点：**
- `InMemorySaver()`：记忆存储
- `thread_id`：对话标识
- `ToolStrategy()`：结构化输出

**运行：**
```bash
cd demos/langchain-advanced
python main.py
```

---

## 5. 完整场景实战

### 5.1 项目说明

**位置：** `projects/content-creation-crew/`

**场景：** 自动化技术博客创作

**流程：**
```
Researcher → Writer → Reviewer → Editor
   ↓           ↓          ↓         ↓
 调研        写作       审查      编辑
```

### 5.2 项目结构

```
content-creation-crew/
├── main.py              # 入口
├── src/
│   ├── agents.py        # 4 个 Agent 定义
│   ├── tasks.py         # 4 个 Task 定义
│   ├── crew.py          # Crew 编排
│   └── tools.py         # 工具定义
├── tests/
│   └── test_crew.py     # 测试
└── output/              # 输出
```

### 5.3 运行项目

```bash
cd projects/content-creation-crew
pip install -r requirements.txt
./run.sh "Python 异步编程"
```

### 5.4 输出示例

```
output/
├── research.md       # 调研报告（2000+ 字）
├── draft.md          # 初稿（3000+ 字）
├── review.md         # 审查报告（含评分和建议）
└── final_article.md  # 最终文章（可发布）
```

### 5.5 自定义扩展

**添加翻译 Agent：**

```python
# src/agents.py
def create_translator():
    return Agent(
        role="翻译专家",
        goal="将文章翻译成英文",
        backstory="你是专业翻译，有 10 年经验"
    )

# src/tasks.py
def create_translation_task(agent, editing_task):
    return Task(
        description="将文章翻译成英文",
        agent=agent,
        context=[editing_task]
    )

# src/crew.py
crew = Crew(
    agents=[..., create_translator()],
    tasks=[..., create_translation_task(...)]
)
```

---

## 6. 常见问题 FAQ

### Q1: API 费用太高怎么办？

**A:** 降低费用的方法：
1. 使用便宜的模型（如 GPT-3.5-Turbo）
2. 减少 `max_iter` 参数
3. 简化任务描述
4. 本地测试用 Mock 数据

**示例：**
```python
agent = Agent(
    ...,
    llm="gpt-3.5-turbo",  # 便宜模型
    max_iter=3  # 减少迭代
)
```

### Q2: 输出质量不稳定？

**A:** 优化方法：
1. 丰富 `backstory`，给 Agent 更清晰的角色
2. 细化 `expected_output`，明确期望
3. 添加审查环节（Reviewer Agent）
4. 使用 Few-Shot 示例

**示例：**
```python
writer = Agent(
    role="资深技术作家",
    backstory=(
        "你有 10 年技术写作经验，"
        "发表过 100+ 篇技术文章，"
        "擅长用清晰的例子解释复杂概念"
    ),
    goal="撰写高质量技术文章"
)
```

### Q3: 执行时间太长？

**A:** 优化方法：
1. 并行执行独立任务（`async_execution=True`）
2. 减少 Agent 数量
3. 简化任务描述
4. 使用缓存（`cache=True`）

**示例：**
```python
task1 = Task(..., async_execution=True)
task2 = Task(..., async_execution=True)

crew = Crew(..., cache=True)
```

### Q4: 如何调试 Agent 行为？

**A:** 调试方法：
1. 启用 `verbose=True` 查看详细日志
2. 打印中间结果
3. 使用 LangSmith（LangChain 的调试工具）
4. 分步执行，定位问题

**示例：**
```python
agent = Agent(..., verbose=True)
crew = Crew(..., verbose=True)
```

### Q5: 两个框架能一起用吗？

**A:** 可以！推荐方式：

```python
# 用 LangChain 定义工具
from langchain.tools import tool

@tool
def custom_tool(...): ...

# 用 CrewAI 编排 Agent
from crewai import Agent

researcher = Agent(
    tools=[custom_tool],  # 使用 LangChain 工具
    ...
)
```

---

## 7. 下一步学习路径

### 7.1 巩固基础（1 周）

- [ ] 运行所有 4 个 Demo
- [ ] 修改 Demo 参数，观察变化
- [ ] 添加自定义工具
- [ ] 阅读官方文档核心章节

### 7.2 进阶学习（2 周）

- [ ] 学习 LangGraph（LangChain 的流程编排）
- [ ] 学习 RAG（检索增强生成）
- [ ] 学习 Fine-tuning（定制模型）
- [ ] 学习 Agent 评估和优化

### 7.3 实战项目（持续）

**项目建议：**
1. **技术博客生成器**：输入主题，输出完整文章
2. **代码审查助手**：自动审查代码质量
3. **文档翻译系统**：多语言文档生成
4. **知识库问答系统**：基于内部文档问答

### 7.4 学习资源

**官方文档：**
- [CrewAI 文档](https://docs.crewai.com)
- [LangChain 文档](https://python.langchain.com)

**社区资源：**
- [CrewAI GitHub](https://github.com/crewAIInc/crewAI)
- [LangChain GitHub](https://github.com/langchain-ai/langchain)
- [Awesome LangChain](https://github.com/kyrolabs/awesome-langchain)

**进阶课程：**
- LangChain 官方教程
- CrewAI 示例集（Cookbooks）
- YouTube 技术频道

---

## 附录：代码模板

### CrewAI 模板

```python
from crewai import Agent, Task, Crew, Process

# 1. 定义 Agent
agent = Agent(
    role="角色名称",
    goal="目标描述",
    backstory="背景故事",
    verbose=True
)

# 2. 定义 Task
task = Task(
    description="任务描述",
    expected_output="期望输出",
    agent=agent
)

# 3. 创建 Crew
crew = Crew(
    agents=[agent],
    tasks=[task],
    process=Process.sequential
)

# 4. 执行
result = crew.kickoff(inputs={"key": "value"})
```

### LangChain 模板

```python
from langchain.agents import create_agent
from langchain.tools import tool

# 1. 定义工具
@tool
def my_tool(arg: str) -> str:
    """工具描述"""
    return "结果"

# 2. 创建 Agent
agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[my_tool],
    system_prompt="系统提示"
)

# 3. 执行
response = agent.invoke({
    "messages": [{"role": "user", "content": "问题"}]
})
```

---

**祝你学习顺利！** 🚀

如有问题，欢迎查阅本指南或访问官方文档。

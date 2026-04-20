# CrewAI 基础 Demo - 简单角色协作

## 📋 场景说明

这个 Demo 展示了一个简单的双 Agent 协作场景：
- **Researcher（研究员）**：负责调研指定主题
- **Writer（作家）**：基于调研结果撰写技术文章

## 🎯 学习目标

- 理解 CrewAI 的核心概念：Agent、Task、Crew
- 掌握顺序执行流程（Process.sequential）
- 学习 Task 之间的依赖关系（context 参数）
- 了解如何输出到文件

## 🚀 快速开始

### 1. 安装依赖

```bash
cd crewai-basic
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# .env
OPENAI_API_KEY=your-api-key-here
# 或者使用其他模型提供商
# ANTHROPIC_API_KEY=your-anthropic-key
```

### 3. 运行 Demo

```bash
python main.py
```

### 4. 查看输出

执行完成后，查看生成的文件：
- `output/research_report.md` - 调研报告
- `output/technical_article.md` - 技术文章

## 📖 代码解析

### Agent 定义

```python
researcher = Agent(
    role="技术研究员",
    goal="深入调研{topic}领域",
    backstory="你是一位经验丰富的技术研究员...",
    verbose=True,
    allow_delegation=False
)
```

**关键参数：**
- `role`: Agent 的职责定位
- `goal`: Agent 的目标
- `backstory`: 背景故事，影响行为风格
- `verbose`: 输出详细日志
- `allow_delegation`: 是否允许委托任务

### Task 定义

```python
research_task = Task(
    description="对{topic}进行彻底调研...",
    expected_output="一份包含以下内容的调研报告...",
    agent=researcher,
    output_file="output/research_report.md"
)
```

**关键参数：**
- `description`: 任务描述
- `expected_output`: 期望的输出
- `agent`: 负责执行的 Agent
- `output_file`: 输出文件路径
- `context`: 依赖的其他 Task（可选）

### Crew 编排

```python
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,  # 顺序执行
    verbose=True,
    memory=True
)
```

**执行流程类型：**
- `Process.sequential`: 任务按顺序依次执行
- `Process.hierarchical`: 根据 Agent 角色动态分配

## 🔧 自定义主题

修改 `main.py` 中的 `inputs` 字典：

```python
inputs = {
    "topic": "Rust 编程语言"  # 改成任何你想调研的主题
}
```

**示例主题：**
- "Python 异步编程"
- "Kubernetes 容器编排"
- "GraphQL API 设计"
- "WebAssembly 技术"

## 💡 进阶技巧

### 1. 添加更多 Agent

```python
reviewer = Agent(
    role="技术审查员",
    goal="审查技术文章的准确性和完整性",
    backstory="你是一位严谨的技术专家..."
)

review_task = Task(
    description="审查文章的技术准确性...",
    agent=reviewer,
    context=[writing_task]
)
```

### 2. 使用工具增强能力

```python
from crewai_tools import SerperDevTool

researcher = Agent(
    role="技术研究员",
    tools=[SerperDevTool()],  # 添加搜索工具
    ...
)
```

### 3. 并行执行任务

```python
from crewai import Task

task1 = Task(..., async_execution=True)
task2 = Task(..., async_execution=True)
```

## ⚠️ 常见问题

**Q: 输出文件在哪里？**
A: 在当前目录的 `output/` 文件夹中。

**Q: 如何更换模型？**
A: 设置环境变量，如 `ANTHROPIC_API_KEY`，CrewAI 会自动检测。

**Q: 执行很慢怎么办？**
A: 减少 `max_iter` 参数，或使用更快的模型。

## 📚 下一步

完成这个 Demo 后，尝试：
1. 修改主题，调研你感兴趣的技术
2. 添加第三个 Agent（如 Reviewer）
3. 尝试 `crewai-advanced` Demo，学习工具使用

---

**预计运行时间**: 2-5 分钟（取决于主题复杂度）

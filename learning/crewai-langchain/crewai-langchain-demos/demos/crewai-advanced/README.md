# CrewAI 进阶 Demo - 带工具和流程编排

## 📋 场景说明

这个 Demo 展示了一个完整的三 Agent 内容创作流水线：
- **Researcher（研究员）**：使用搜索工具收集信息
- **Writer（作家）**：撰写技术文章
- **Reviewer（审查员）**：审查文章质量

## 🎯 学习目标

- 学习如何给 Agent 配备工具（Tools）
- 理解多 Agent 协作流程
- 掌握 Task 依赖关系（context 参数）
- 学习质量检查和审查流程

## 🚀 快速开始

### 1. 安装依赖

```bash
cd crewai-advanced
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 必需：OpenAI 或其他 LLM API
export OPENAI_API_KEY=your-api-key

# 可选：Serper 搜索工具（用于网络搜索）
export SERPER_API_KEY=your-serper-key
# 获取：https://serper.dev/
```

### 3. 运行 Demo

```bash
python main.py
```

### 4. 查看输出

```
output/
├── advanced_research.md   # 调研报告
├── advanced_article.md    # 技术文章
└── review_report.md       # 审查报告
```

## 📖 代码解析

### 工具使用

```python
from crewai_tools import SerperDevTool, FileReadTool

# 创建工具实例
search_tool = SerperDevTool()

# 给 Agent 配备工具
researcher = Agent(
    role="高级技术研究员",
    tools=[search_tool],  # 可以调用搜索 API
    ...
)
```

**可用工具：**
- `SerperDevTool`: 网络搜索
- `FileReadTool`: 读取文件
- `MDXSearchTool`: 搜索 Markdown 文件
- `WebsiteSearchTool`: 搜索网站内容
- `GithubSearchTool`: 搜索 GitHub

### 多 Agent 协作

```python
crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[research_task, writing_task, review_task],
    process=Process.sequential,  # 顺序执行
    memory=True,
    cache=True  # 缓存结果，避免重复调用
)
```

**执行流程：**
```
Researcher → 调研 → 输出报告
    ↓
Writer → 基于报告写作 → 输出文章
    ↓
Reviewer → 审查文章 → 输出审查意见
```

### Task 依赖

```python
writing_task = Task(
    ...,
    context=[research_task],  # 依赖调研任务的输出
    ...
)

review_task = Task(
    ...,
    context=[writing_task],  # 依赖写作任务的输出
    ...
)
```

## 🔧 自定义配置

### 更换主题

```python
inputs = {
    "topic": "Rust 异步编程"  # 任何你想创作的主题
}
```

### 添加更多工具

```python
from crewai_tools import WebsiteSearchTool, GithubSearchTool

researcher = Agent(
    tools=[
        SerperDevTool(),
        WebsiteSearchTool(),
        GithubSearchTool()
    ]
)
```

### 调整 Agent 行为

```python
researcher = Agent(
    max_iter=10,  # 增加最大迭代次数，更深入调研
    memory=True,  # 启用记忆
    cache=True,   # 启用缓存
    allow_delegation=True  # 允许委托任务
)
```

## 💡 进阶技巧

### 1. 使用 YAML 配置

将 Agent 和 Task 配置移到 YAML 文件：

```yaml
# config/agents.yaml
researcher:
  role: 高级技术研究员
  goal: 深入调研{topic}
  backstory: 你是一位资深研究员...
```

```python
# crew.py
@agent
def researcher(self) -> Agent:
    return Agent(config=self.agents_config['researcher'])
```

### 2. 并行执行

```python
# 两个独立的研究任务可以并行
task1 = Task(..., async_execution=True)
task2 = Task(..., async_execution=True)
```

### 3. 条件流程

```python
# 根据审查结果决定是否修改
if review_score < 7:
    # 触发修改任务
    revise_task = Task(...)
```

## ⚠️ 常见问题

**Q: 搜索工具报错？**
A: 检查 `SERPER_API_KEY` 是否正确设置，或移除搜索工具使用纯 LLM。

**Q: 执行时间太长？**
A: 减少 `max_iter` 参数，或简化任务描述。

**Q: 输出质量不高？**
A: 优化 `backstory` 和 `goal`，给 Agent 更清晰的角色定位。

## 📚 下一步

完成这个 Demo 后，尝试：
1. 添加第四个 Agent（如 Editor 进行最终编辑）
2. 集成自定义工具（如调用内部 API）
3. 使用 YAML 配置管理复杂的 Crew
4. 探索 `crewai create crew` CLI 创建完整项目

---

**预计运行时间**: 5-15 分钟（取决于主题复杂度和是否使用搜索工具）

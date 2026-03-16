# CrewAI 智能体代码解析 - 日本留学咨询顾问

**文档目标**：帮助 Agent 开发者理解 CrewAI 框架的核心概念和代码结构

**前置知识**：Python 基础、异步编程基础、对 LLM 的基本了解

---

## 📖 目录

1. [整体架构](#1-整体架构)
2. [代码逐行解析](#2-代码逐行解析)
3. [核心概念详解](#3-核心概念详解)
4. [设计模式分析](#4-设计模式分析)
5. [扩展与优化](#5-扩展与优化)

---

## 1. 整体架构

### 1.1 CrewAI 核心三要素

```
┌─────────────────────────────────────────────────────────┐
│                     CrewAI 架构                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   Agent (智能体)                                        │
│   ┌─────────────────────────────────┐                   │
│   │  - role: 角色定义                │                   │
│   │  - goal: 目标                    │                   │
│   │  - backstory: 背景故事           │                   │
│   │  - tools: 工具集 (可选)          │                   │
│   └─────────────────────────────────┘                   │
│                      ↓                                  │
│   Task (任务)                                           │
│   ┌─────────────────────────────────┐                   │
│   │  - description: 任务描述         │                   │
│   │  - expected_output: 期望输出     │                   │
│   │  - agent: 执行 Agent             │                   │
│   └─────────────────────────────────┘                   │
│                      ↓                                  │
│   Crew (工作组)                                         │
│   ┌─────────────────────────────────┐                   │
│   │  - agents: [Agent1, Agent2...]   │                   │
│   │  - tasks: [Task1, Task2...]      │                   │
│   │  - process: 执行流程             │                   │
│   └─────────────────────────────────┘                   │
│                      ↓                                  │
│   Result (结果)                                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 执行流程

```
用户输入 → consult() → 创建 Agent → 创建 Task → 创建 Crew → kickoff() → 输出结果
```

---

## 2. 代码逐行解析

### 2.1 环境准备部分

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
```
**作用**：Shebang 行，指定 Python 解释器和 UTF-8 编码

---

```python
# ============== 必需的 sqlite3 补丁 ==============
import pysqlite3
import sys
sys.modules['sqlite3'] = pysqlite3
# ===============================================
```

**为什么要这个补丁？**

CrewAI 依赖 ChromaDB（向量数据库），ChromaDB 需要 SQLite ≥ 3.35.0。但 Python 3.12 系统自带的 sqlite3 版本是 3.34.1，不满足要求。

**解决方案**：
1. 安装 `pysqlite3-binary`（预编译的新版 SQLite）
2. 用 `pysqlite3` 替换 `sqlite3` 模块

**原理**：
```python
sys.modules['sqlite3'] = pysqlite3
```
这行代码将 `sqlite3` 模块名指向 `pysqlite3` 包。之后任何 `import sqlite3` 都会实际导入 `pysqlite3`。

**⚠️ 重要**：这个补丁必须在导入 `crewai` 之前执行！

---

### 2.2 导入依赖

```python
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool
import os
```

**核心类说明**：

| 类 | 作用 | 类比 |
|----|------|------|
| `Agent` | 定义智能体的角色、目标、能力 | 公司里的员工 |
| `Task` | 定义具体工作任务 | 分配给员工的任务单 |
| `Crew` | 组织多个 Agent 协同工作 | 项目团队 |
| `Process` | 定义任务执行流程（顺序/并行） | 工作流程 |
| `SerperDevTool` | Google 搜索工具（需 API Key） | 员工的搜索工具 |

---

### 2.3 配置区

```python
# ============== 配置区 ==============
os.environ['OPENAI_API_KEY'] = 'sk-sp-10fae675e5964548be93f3f0eabb4298'
os.environ['OPENAI_API_BASE'] = 'https://coding.dashscope.aliyuncs.com/v1'
os.environ['OPENAI_MODEL_NAME'] = 'qwen3.5-plus'
# ====================================
```

**配置解析**：

| 环境变量 | 作用 | 说明 |
|---------|------|------|
| `OPENAI_API_KEY` | API 认证密钥 | CrewAI 使用 OpenAI 兼容接口 |
| `OPENAI_API_BASE` | API 基础 URL | 阿里云百炼的兼容接口地址 |
| `OPENAI_MODEL_NAME` | 使用的模型 | 通义千问 qwen3.5-plus |

**为什么是 OpenAI 的配置？**

CrewAI 底层使用 LangChain，默认支持 OpenAI API。阿里云百炼提供了**OpenAI 兼容接口**，所以可以用相同的调用方式。

**其他支持的模型提供商**：
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- 阿里云百炼 (通义千问)
- 本地模型 (Ollama, LM Studio)

---

### 2.4 Agent 定义函数

```python
def create_study_abroad_agent():
    """创建日本留学咨询顾问智能体"""
    
    consultant_agent = Agent(
        role='日本留学申请专家',
        goal='为学生提供专业、详细的日本研究生/修士申请指导',
        backstory='''你是一位拥有 10 年经验的日本留学申请专家，熟悉日本各大院校的研究生（预科）
        和修士（硕士）申请流程。你帮助学生进行院校定位、研究计划书指导、套磁信撰写、
        出愿材料准备、时间规划等全流程服务。你了解东京大学、京都大学、大阪大学、东北大学、
        名古屋大学、北海道大学、九州大学等顶尖院校的申请要求和偏好。''',
        verbose=True,
        allow_delegation=False,
    )
    
    return consultant_agent
```

**Agent 参数详解**：

#### `role` (角色)
```python
role='日本留学申请专家'
```
- **作用**：定义 Agent 的身份
- **影响**：LLM 会基于这个角色调整回答的语气和专业度
- **最佳实践**：具体、明确，避免模糊

#### `goal` (目标)
```python
goal='为学生提供专业、详细的日本研究生/修士申请指导'
```
- **作用**：定义 Agent 的核心任务目标
- **影响**：引导 LLM 聚焦在特定目标上
- **最佳实践**：用动词开头，清晰可衡量

#### `backstory` (背景故事)
```python
backstory='''你是一位拥有 10 年经验的日本留学申请专家...'''
```
- **作用**：提供上下文和领域知识
- **影响**：让 LLM "相信"自己具有这些经验和知识
- **最佳实践**：
  - 包含具体年限（10 年经验）
  - 列出具体技能（院校定位、研究计划书指导...）
  - 提及具体对象（东京大学、京都大学...）

**为什么 backstory 重要？**

这是 **Prompt Engineering 中的"角色设定"技巧**。通过详细的背景描述，让 LLM 进入特定角色，输出更专业的内容。

**对比示例**：

❌ 差的 backstory：
```python
backstory='你是一个留学顾问'
```

✅ 好的 backstory：
```python
backstory='你是一位拥有 10 年经验的日本留学申请专家，熟悉日本七大帝国大学的申请流程，
已成功帮助 500+ 学生获得东大、京大、东工大的录取。你擅长根据学生的背景进行精准定位，
并提供个性化的研究计划书指导。'
```

#### `verbose` (详细模式)
```python
verbose=True
```
- **作用**：打印执行过程的详细信息
- **输出**：Agent 思考过程、任务进度、工具调用等
- **用途**：调试、观察 Agent 行为

#### `allow_delegation` (允许委派)
```python
allow_delegation=False
```
- **作用**：是否允许 Agent 将任务委派给其他 Agent
- **默认值**：`True`
- **本例设为 False 的原因**：只有一个 Agent，无需委派

#### `tools` (工具集 - 本例未启用)
```python
# tools=[SerperDevTool()] if os.environ.get('SERPER_API_KEY') else []
```
- **作用**：为 Agent 提供外部工具（搜索、计算器、API 调用等）
- **本例注释掉的原因**：留学咨询主要依赖 LLM 内部知识，无需实时搜索

**Agent 完整参数列表**：
```python
Agent(
    role: str,                    # 必需 - 角色
    goal: str,                    # 必需 - 目标
    backstory: str,               # 必需 - 背景故事
    verbose: bool = False,        # 可选 - 详细模式
    allow_delegation: bool = True, # 可选 - 允许委派
    tools: List[Tool] = [],       # 可选 - 工具集
    llm: Optional[BaseLLM] = None, # 可选 - 自定义 LLM
    memory: bool = False,         # 可选 - 启用记忆
    cache: bool = True,           # 可选 - 启用缓存
    max_iter: int = 25,           # 可选 - 最大迭代次数
    max_rpm: Optional[int] = None, # 可选 - 每分钟最大请求数
    max_execution_time: Optional[int] = None, # 可选 - 最大执行时间
)
```

---

### 2.5 Task 定义函数

```python
def create_consultation_task(question: str, agent: Agent) -> Task:
    """创建咨询任务"""
    
    task = Task(
        description=f'''请详细回答学生的留学咨询问题：

【学生问题】
{question}

【回答要求】
1. 提供专业、详细的解答
2. 如果涉及具体院校，列出 2-3 所推荐学校及理由
3. 给出明确的时间规划建议（如适用）
4. 列出需要准备的材料清单（如适用）
5. 提醒注意事项和常见误区
6. 语气友好、鼓励，让学生感到被支持

请用中文回答，格式清晰，适当使用列表和分段。''',
        expected_output='一份完整、专业的日本留学咨询回复，包含具体建议和 actionable 的下一步指导',
        agent=agent,
    )
    
    return task
```

**Task 参数详解**：

#### `description` (任务描述)
```python
description=f'''请详细回答学生的留学咨询问题：...'''
```
- **作用**：告诉 Agent 具体要做什么
- **技巧**：
  - 使用 f-string 动态插入用户问题
  - 分点列出具体要求
  - 明确输出格式（中文、列表、分段）

**为什么分点列出要求？**

这是 **Prompt Engineering 中的"结构化指令"技巧**。LLM 对清晰的列表指令遵循度更高。

#### `expected_output` (期望输出)
```python
expected_output='一份完整、专业的日本留学咨询回复，包含具体建议和 actionable 的下一步指导'
```
- **作用**：定义任务完成的标准
- **影响**：Agent 会基于这个标准判断何时停止迭代
- **最佳实践**：具体、可衡量、包含质量要求

#### `agent` (执行 Agent)
```python
agent=agent
```
- **作用**：指定执行此任务的 Agent
- **注意**：一个 Task 只能有一个 Agent，但一个 Agent 可以有多个 Task

**Task 完整参数列表**：
```python
Task(
    description: str,             # 必需 - 任务描述
    expected_output: str,         # 必需 - 期望输出
    agent: Optional[Agent] = None, # 可选 - 执行 Agent
    tools: List[Tool] = [],       # 可选 - 任务专用工具
    async_execution: bool = False, # 可选 - 异步执行
    context: Optional[List[Task]] = None, # 可选 - 上下文任务（依赖其他任务输出）
    config: Optional[Dict] = None, # 可选 - 自定义配置
    output_file: Optional[str] = None, # 可选 - 输出到文件
    output_json: Optional[Type[BaseModel]] = None, # 可选 - JSON 输出（Pydantic 模型）
    output_pydantic: Optional[Type[BaseModel]] = None, # 可选 - Pydantic 输出
    human_input: bool = False,    # 可选 - 需要人工输入
    callback: Optional[Callable] = None, # 可选 - 回调函数
)
```

---

### 2.6 主咨询函数

```python
def consult(question: str):
    """主咨询函数"""
    
    print("🎓 日本留学咨询顾问已启动")
    print("=" * 50)
    print(f"问题：{question}\n")
    
    # 创建 Agent
    agent = create_study_abroad_agent()
    
    # 创建 Task
    task = create_consultation_task(question, agent)
    
    # 创建 Crew
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    
    # 执行
    result = crew.kickoff()
    
    print("\n" + "=" * 50)
    print("✅ 咨询完成")
    print("=" * 50 + "\n")
    
    return result
```

**Crew 参数详解**：

#### `agents`
```python
agents=[agent]
```
- **作用**：Crew 包含的所有 Agent
- **本例**：只有一个 Agent
- **多 Agent 场景**：`agents=[agent1, agent2, agent3]`

#### `tasks`
```python
tasks=[task]
```
- **作用**：Crew 要执行的所有任务
- **多 Task 场景**：任务会按流程依次或并行执行

#### `process`
```python
process=Process.sequential
```
- **作用**：定义任务执行流程
- **可选值**：
  - `Process.sequential`：顺序执行（Task1 → Task2 → Task3）
  - `Process.hierarchical`：层级执行（Manager Agent 分配任务）

**流程对比**：

```
Sequential（顺序）:
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Task 1  │ →  │ Task 2  │ →  │ Task 3  │
│ Agent A │    │ Agent B │    │ Agent C │
└─────────┘    └─────────┘    └─────────┘

Hierarchical（层级）:
         ┌─────────────┐
         │ Manager     │
         │ Agent       │
         └──────┬──────┘
                │ 分配任务
       ┌────────┼────────┐
       ↓        ↓        ↓
  ┌────────┐ ┌────────┐ ┌────────┐
  │ Worker │ │ Worker │ │ Worker │
  │   A    │ │   B    │ │   C    │
  └────────┘ └────────┘ └────────┘
```

#### `verbose`
```python
verbose=True
```
- **作用**：打印 Crew 执行详情
- **输出**：任务开始/完成、Agent 思考过程等

#### `kickoff()` 方法
```python
result = crew.kickoff()
```
- **作用**：启动 Crew 执行
- **返回值**：最后一个 Task 的输出结果
- **执行过程**：
  1. 初始化所有 Agent
  2. 按流程执行 Tasks
  3. 收集并返回结果

**Crew 完整参数列表**：
```python
Crew(
    agents: List[Agent],          # 必需 - Agent 列表
    tasks: List[Task],            # 必需 - Task 列表
    process: Process = Process.sequential, # 可选 - 执行流程
    verbose: bool = False,        # 可选 - 详细模式
    manager_agent: Optional[Agent] = None, # 可选 - 管理 Agent（hierarchical 模式）
    manager_llm: Optional[str] = None, # 可选 - 管理 Agent 的 LLM
    language: str = "en",         # 可选 - 语言
    memory: bool = False,         # 可选 - 启用记忆
    cache: bool = True,           # 可选 - 启用缓存
    planning: bool = False,       # 可选 - 启用规划
    max_rpm: Optional[int] = None, # 可选 - 每分钟最大请求数
    share_crew: bool = False,     # 可选 - 分享到 CrewAI 社区
    step_callback: Optional[Callable] = None, # 可选 - 每步回调
    task_callback: Optional[Callable] = None, # 可选 - 每任务回调
)
```

---

### 2.7 命令行入口

```python
SAMPLE_QUESTIONS = [
    "我想申请东京大学的计算机专业修士，需要准备什么？",
    "我现在大二，想申请日本研究生，应该如何规划时间？",
    "我的日语是 N2，英语托福 80 分，能申请哪些学校？",
    "研究计划书应该怎么写？有什么注意事项？",
    "套磁信应该什么时候发？怎么写才能提高回复率？",
]
```

**作用**：预定义的示例问题列表，用于演示

---

```python
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 从命令行读取问题
        question = " ".join(sys.argv[1:])
    else:
        # 使用示例问题
        print("📝 示例问题：\n")
        for i, q in enumerate(SAMPLE_QUESTIONS, 1):
            print(f"{i}. {q}")
        print("\n" + "=" * 50 + "\n")
        
        # 选择第一个问题作为演示
        question = SAMPLE_QUESTIONS[0]
    
    # 执行咨询
    result = consult(question)
    
    print("\n📋 【咨询结果】\n")
    print(result)
```

**代码解析**：

1. **`if __name__ == "__main__":`**
   - Python 惯用法，确保只有直接运行时才执行
   - 被 import 时不会执行

2. **命令行参数处理**：
   ```python
   if len(sys.argv) > 1:
       question = " ".join(sys.argv[1:])
   ```
   - `sys.argv[0]`：脚本名
   - `sys.argv[1:]`：用户传入的参数
   - 支持多词问题：`python script.py 我想申请 东京大学`

3. **示例问题展示**：
   ```python
   for i, q in enumerate(SAMPLE_QUESTIONS, 1):
       print(f"{i}. {q}")
   ```
   - `enumerate(list, 1)`：从 1 开始编号
   - 方便用户参考

---

## 3. 核心概念详解

### 3.1 Agent 的工作原理

```
┌─────────────────────────────────────────────────────────┐
│                    Agent 执行流程                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  输入：Task description                                 │
│           ↓                                             │
│  ┌─────────────────────────────────────────┐            │
│  │  System Prompt (系统提示词)              │            │
│  │  ┌───────────────────────────────────┐  │            │
│  │  │ You are a {role}                  │  │            │
│  │  │ Your goal: {goal}                 │  │            │
│  │  │ Your backstory: {backstory}       │  │            │
│  │  │ Tools available: {tools}          │  │            │
│  │  └───────────────────────────────────┘  │            │
│  └─────────────────────────────────────────┘            │
│           ↓                                             │
│  ┌─────────────────────────────────────────┐            │
│  │  User Prompt (用户提示词)                │            │
│  │  ┌───────────────────────────────────┐  │            │
│  │  │ Task: {description}               │  │            │
│  │  │ Expected Output: {expected_output}│  │            │
│  │  └───────────────────────────────────┘  │            │
│  └─────────────────────────────────────────┘            │
│           ↓                                             │
│  LLM (通义千问 qwen3.5-plus)                            │
│           ↓                                             │
│  输出：Task result                                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**关键点**：
- Agent 本质是一个 **精心设计的 Prompt + LLM 调用**
- `role`、`goal`、`backstory` 都会被拼接到 System Prompt 中
- `verbose=True` 时会打印这些 Prompt

---

### 3.2 Task 执行流程

```
┌─────────────────────────────────────────────────────────┐
│                    Task 执行流程                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. 接收 Task description                               │
│           ↓                                             │
│  2. Agent 分析任务                                      │
│     - 理解要求                                          │
│     - 规划步骤                                          │
│     - 决定是否需要工具                                  │
│           ↓                                             │
│  3. 如果有工具，调用工具                                │
│     - 搜索、计算、API 调用...                           │
│           ↓                                             │
│  4. LLM 生成回答                                        │
│           ↓                                             │
│  5. 检查是否满足 expected_output                        │
│     - 满足 → 完成                                       │
│     - 不满足 → 回到步骤 2（迭代）                       │
│           ↓                                             │
│  6. 返回结果                                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**迭代机制**：
- Agent 会多次调用 LLM，逐步完善答案
- `max_iter=25` 限制最大迭代次数
- 达到 `expected_output` 标准时提前结束

---

### 3.3 Crew 协作模式

#### 模式 1：Sequential（顺序）

```python
crew = Crew(
    agents=[researcher, writer, editor],
    tasks=[research_task, write_task, edit_task],
    process=Process.sequential
)
```

**执行流程**：
```
Task 1 (Researcher) → Task 2 (Writer) → Task 3 (Editor)
     ↓                    ↓                 ↓
  收集资料              撰写文章            编辑校对
```

**适用场景**：任务有明确先后依赖关系

---

#### 模式 2：Hierarchical（层级）

```python
crew = Crew(
    agents=[manager, researcher, writer],
    tasks=[research_task, write_task],
    process=Process.hierarchical,
    manager_agent=manager
)
```

**执行流程**：
```
              Manager Agent
                   │
         ┌─────────┴─────────┐
         ↓                   ↓
    Researcher            Writer
    (research_task)      (write_task)
```

**适用场景**：需要协调多个并行任务

---

### 3.4 工具（Tools）系统

**什么是 Tool？**

Tool 是 Agent 可以调用的外部函数，扩展 Agent 的能力。

**内置工具示例**：

```python
from crewai_tools import SerperDevTool, FileReadTool, WebsiteSearchTool

# Google 搜索
search_tool = SerperDevTool()

# 文件读取
file_tool = FileReadTool()

# 网站搜索
website_tool = WebsiteSearchTool()
```

**使用方式**：

```python
agent = Agent(
    role='研究员',
    goal='研究最新 AI 技术',
    backstory='...',
    tools=[SerperDevTool()]  # 启用搜索工具
)
```

**自定义工具**：

```python
from crewai_tools import BaseTool

class MyCustomTool(BaseTool):
    name: str = "计算器"
    description: str = "计算数学表达式"
    
    def _run(self, expression: str) -> str:
        return str(eval(expression))

# 使用
agent = Agent(..., tools=[MyCustomTool()])
```

---

## 4. 设计模式分析

### 4.1 工厂模式

```python
def create_study_abroad_agent():
    """工厂函数：创建 Agent"""
    return Agent(...)

def create_consultation_task(question: str, agent: Agent):
    """工厂函数：创建 Task"""
    return Task(...)
```

**优点**：
- 代码复用：可以多次创建相同配置的 Agent
- 易于测试：可以单独测试工厂函数
- 易于扩展：修改配置只需改工厂函数

---

### 4.2 函数式编程

```python
def consult(question: str):
    agent = create_study_abroad_agent()
    task = create_consultation_task(question, agent)
    crew = Crew(agents=[agent], tasks=[task])
    return crew.kickoff()
```

**特点**：
- 纯函数：相同输入 → 相同输出
- 无副作用：不修改全局状态
- 组合性：小函数组合成大功能

---

### 4.3 关注点分离

```
┌─────────────────────────────────────────┐
│  配置层                                  │
│  - API Key                              │
│  - API Base                             │
│  - Model Name                           │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Agent 定义层                            │
│  - create_study_abroad_agent()          │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Task 定义层                             │
│  - create_consultation_task()           │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  执行层                                  │
│  - consult()                            │
│  - crew.kickoff()                       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  入口层                                  │
│  - if __name__ == "__main__"            │
└─────────────────────────────────────────┘
```

**优点**：
- 每层职责清晰
- 修改某一层不影响其他层
- 易于理解和维护

---

## 5. 扩展与优化

### 5.1 添加多 Agent 协作

**场景**：增加一个"文书润色专家"Agent

```python
def create_editor_agent():
    """创建文书润色专家"""
    return Agent(
        role='文书润色专家',
        goal='优化文书的语言表达和结构',
        backstory='你是一位专业的日语/英语文书编辑，有 15 年经验...',
        verbose=True
    )

def create_editing_task(draft: str, agent: Agent) -> Task:
    """创建润色任务"""
    return Task(
        description=f'''请润色以下文书：
        
【原文】
{draft}

【润色要求】
1. 修正语法错误
2. 优化句子结构
3. 提升表达的专业性
4. 保持原意不变''',
        expected_output='润色后的高质量文书',
        agent=agent
    )

def consult_with_editing(question: str):
    # 创建两个 Agent
    consultant = create_study_abroad_agent()
    editor = create_editor_agent()
    
    # 创建两个 Task
    consultation_task = create_consultation_task(question, consultant)
    editing_task = create_editing_task(consultation_task, editor)
    
    # 创建 Crew（顺序执行）
    crew = Crew(
        agents=[consultant, editor],
        tasks=[consultation_task, editing_task],
        process=Process.sequential,
        verbose=True
    )
    
    return crew.kickoff()
```

**执行流程**：
```
用户问题 → 咨询 Agent → 初稿 → 润色 Agent → 最终稿
```

---

### 5.2 添加联网搜索

**场景**：查询最新的申请要求

```python
from crewai_tools import SerperDevTool

# 1. 设置 API Key
os.environ['SERPER_API_KEY'] = 'your-serper-api-key'

# 2. 创建搜索工具
search_tool = SerperDevTool()

# 3. 给 Agent 配备工具
agent = Agent(
    role='日本留学申请专家',
    goal='为学生提供最新、最准确的申请信息',
    backstory='...',
    tools=[search_tool],  # 启用搜索
    verbose=True
)

# 4. 在 Task 中要求搜索
task = Task(
    description='''请搜索东京大学 2026 年计算机修士申请的最新要求，
    然后为学生提供详细指导。''',
    expected_output='包含最新信息的咨询回复',
    agent=agent
)
```

**Agent 会**：
1. 自动决定何时调用搜索工具
2. 根据搜索结果生成回答
3. 引用搜索到的信息

---

### 5.3 添加记忆功能

**场景**：记住用户的历史咨询

```python
from crewai.memory import ShortTermMemory, LongTermMemory

# 创建带记忆的 Agent
agent = Agent(
    role='日本留学申请专家',
    goal='为学生提供个性化的持续指导',
    backstory='...',
    memory=True,  # 启用记忆
    verbose=True
)

# 使用
result1 = consult("我想申请东大计算机专业")
result2 = consult("我的托福是 90 分，够吗？")  # Agent 会记住之前的问题
```

**记忆类型**：
- **Short-term**：当前会话的记忆
- **Long-term**：跨会话的持久记忆

---

### 5.4 结构化输出

**场景**：输出 JSON 格式，便于程序处理

```python
from pydantic import BaseModel, Field

class ConsultationResult(BaseModel):
    """咨询结果模型"""
    recommended_schools: list[str] = Field(description="推荐学校列表")
    required_materials: list[str] = Field(description="所需材料")
    timeline: str = Field(description="时间规划")
    notes: list[str] = Field(description="注意事项")

# 创建 Task 时指定输出格式
task = Task(
    description='请为学生提供咨询...',
    expected_output='结构化的咨询报告',
    agent=agent,
    output_pydantic=ConsultationResult  # 指定 Pydantic 模型
)

# 执行后得到结构化数据
result = crew.kickoff()
print(result.recommended_schools)  # ['东京大学', '京都大学', ...]
```

**优点**：
- 类型安全
- 易于程序处理
- 可以输出到文件/API

---

### 5.5 性能优化

#### 问题 1：响应慢

**原因**：
- LLM 调用次数多
- 迭代次数多
- 网络延迟

**优化方案**：

```python
# 1. 限制最大迭代次数
agent = Agent(..., max_iter=10)  # 默认 25

# 2. 设置最大执行时间
agent = Agent(..., max_execution_time=60)  # 60 秒

# 3. 启用缓存
crew = Crew(..., cache=True)  # 默认启用

# 4. 简化 backstory 和 description
# 过长的 prompt 会增加 LLM 处理时间
```

#### 问题 2：API 费用高

**优化方案**：

```python
# 1. 限制每分钟请求数
crew = Crew(..., max_rpm=10)  # 每分钟最多 10 次

# 2. 使用更便宜的模型
os.environ['OPENAI_MODEL_NAME'] = 'qwen3.5-plus'  # 而非 qwen3-max

# 3. 减少不必要的 verbose
crew = Crew(..., verbose=False)  # 生产环境关闭
```

---

## 6. 调试技巧

### 6.1 启用详细模式

```python
agent = Agent(..., verbose=True)
crew = Crew(..., verbose=True)
```

**输出内容**：
- Agent 思考过程
- 工具调用详情
- 任务执行进度

---

### 6.2 查看生成的 Prompt

在 Agent 执行前添加：

```python
# 打印 Agent 的 system prompt
print(agent.system_prompt)

# 打印 Task 的 prompt
print(task.description)
```

---

### 6.3 捕获异常

```python
try:
    result = crew.kickoff()
except Exception as e:
    print(f"❌ 错误：{e}")
    # 记录日志、重试、降级处理...
```

---

## 7. 最佳实践总结

### ✅ DO（推荐做法）

1. **详细的 backstory**：包含具体年限、技能、成就
2. **结构化的 task description**：分点列出要求
3. **明确的 expected_output**：定义完成标准
4. **使用工厂函数**：便于复用和测试
5. **启用 verbose 调试**：开发阶段观察执行过程
6. **限制迭代次数**：避免无限循环
7. **使用 Pydantic 输出**：便于程序处理

### ❌ DON'T（避免做法）

1. **模糊的角色定义**：如"你是一个助手"
2. **过长的 backstory**：超过 500 字会影响性能
3. **缺少 expected_output**：Agent 不知道何时停止
4. **在生产环境 verbose=True**：会泄露 prompt 细节
5. **不处理异常**：API 失败时程序崩溃
6. **过度依赖工具**：每个工具调用都增加延迟

---

## 8. 学习资源

### 官方文档
- [CrewAI 官方文档](https://docs.crewai.com/)
- [CrewAI GitHub](https://github.com/joaomdmoura/crewai)

### 相关概念
- [LangChain](https://python.langchain.com/) - CrewAI 的基础
- [Prompt Engineering](https://platform.openai.com/docs/guides/prompt-engineering)
- [Pydantic](https://docs.pydantic.dev/) - 结构化输出

### 实践项目
- 多 Agent 协作系统
- 带搜索的研究助手
- 自动化报告生成器

---

**最后更新**：2026-03-16  
**作者**：小黑 - 管家  
**适用版本**：CrewAI 1.10.1

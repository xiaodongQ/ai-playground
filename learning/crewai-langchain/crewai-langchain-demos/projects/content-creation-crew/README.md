# 自动化内容创作 Multi-Agent 系统

## 📋 项目说明

这是一个完整的自动化内容创作系统，使用 CrewAI 编排 4 个 Agent 协作完成技术文章的创作：

```
Researcher → Writer → Reviewer → Editor
   ↓           ↓          ↓         ↓
 调研        写作       审查      编辑
```

## 🎯 系统架构

### Agent 角色

| Agent | 职责 | 工具 |
|-------|------|------|
| **Researcher** | 调研主题，收集信息 | SerperDevTool（搜索） |
| **Writer** | 基于调研写文章 | - |
| **Reviewer** | 审查文章质量 | - |
| **Editor** | 最终编辑和格式化 | - |

### 工作流程

```
1. Researcher 调研主题
   └─> 输出：research.md
   
2. Writer 基于调研写作
   └─> 输出：draft.md
   
3. Reviewer 审查文章
   └─> 输出：review.md
   
4. Editor 根据审查意见编辑
   └─> 输出：final_article.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd content-creation-crew
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 必需：LLM API
export OPENAI_API_KEY=your-api-key

# 可选：搜索工具
export SERPER_API_KEY=your-serper-key
```

### 3. 运行系统

```bash
# 方式 1：使用运行脚本
./run.sh

# 方式 2：直接运行 Python
python main.py

# 方式 3：指定主题
python main.py "Rust 异步编程"
```

### 4. 查看输出

```bash
ls -la output/
# research.md       - 调研报告
# draft.md          - 初稿
# review.md         - 审查报告
# final_article.md  - 最终文章
```

## 📖 代码结构

```
content-creation-crew/
├── main.py              # 入口文件
├── src/
│   ├── __init__.py
│   ├── agents.py        # Agent 定义
│   ├── tasks.py         # Task 定义
│   ├── crew.py          # Crew 编排
│   └── tools.py         # 工具定义
├── tests/
│   └── test_crew.py     # 测试用例
├── output/              # 输出目录
├── requirements.txt     # 依赖
└── run.sh              # 运行脚本
```

## 🔧 自定义配置

### 修改主题

```python
# main.py
run(topic="Kubernetes 容器编排")
```

### 添加 Agent

```python
# src/agents.py
def create_translator():
    return Agent(
        role="翻译专家",
        goal="将文章翻译成英文",
        ...
    )

# src/tasks.py
def create_translation_task(agent, editing_task):
    return Task(
        description="将文章翻译成英文...",
        context=[editing_task],
        ...
    )

# src/crew.py
crew = Crew(
    agents=[..., create_translator()],
    tasks=[..., create_translation_task(...)]
)
```

### 更换模型

```python
# 在创建 Agent 时指定
agent = Agent(
    ...,
    llm="anthropic/claude-sonnet-4-6"
)
```

## 💡 进阶用法

### 1. 并行调研

```python
# 多个 Researcher 并行调研不同方面
task1 = Task(..., async_execution=True)
task2 = Task(..., async_execution=True)
```

### 2. 条件流程

```python
# 根据审查分数决定是否重写
if review_score < 6:
    rewrite_task = Task(...)
```

### 3. 集成 LangChain 工具

```python
from langchain.tools import tool

@tool
def custom_tool(...):
    ...

researcher = Agent(tools=[custom_tool])
```

## 🧪 测试

```bash
# 运行测试
python -m pytest tests/

# 或
python tests/test_crew.py
```

## ⚠️ 常见问题

**Q: 执行时间太长？**
A: 减少 Agent 的 `max_iter` 参数，或简化任务描述。

**Q: 输出质量不高？**
A: 优化 Agent 的 `backstory` 和 `goal`，给更清晰的角色定位。

**Q: 搜索工具报错？**
A: 检查 `SERPER_API_KEY` 是否正确，或移除搜索工具。

## 📊 性能参考

| 主题复杂度 | 预计时间 | 输出质量 |
|-----------|---------|---------|
| 简单（如"Python 列表"） | 3-5 分钟 | 良好 |
| 中等（如"异步编程"） | 5-10 分钟 | 优秀 |
| 复杂（如"Kubernetes"） | 10-20 分钟 | 优秀 |

## 📚 扩展建议

1. **添加更多 Agent**：如 Translator、SEO Expert
2. **集成外部 API**：如 Grammarly 检查、SEO 分析
3. **持久化存储**：将输出保存到数据库
4. **Web 界面**：用 Streamlit 创建 Web UI
5. **定时任务**：用 Cron 定期生成内容

---

**项目状态**: ✅ 可运行  
**最后更新**: 2026-03-09  
**适用场景**: 技术博客、文档生成、内容营销

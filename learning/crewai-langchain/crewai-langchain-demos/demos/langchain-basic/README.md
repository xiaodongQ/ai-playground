# LangChain 基础 Demo - Chain + Agent

## 📋 场景说明

这个 Demo 展示 LangChain 的两个核心概念：
- **Chain（链）**：提示模板 + 模型的组合
- **Agent（智能体）**：可以调用工具的 LLM

## 🎯 学习目标

- 理解 LangChain 的 Chain 抽象
- 学习如何定义和使用工具（Tools）
- 掌握 Agent 的创建和调用
- 对比 Chain 和 Agent 的使用场景

## 🚀 快速开始

### 1. 安装依赖

```bash
cd langchain-basic
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 使用 Anthropic
export ANTHROPIC_API_KEY=your-api-key

# 或使用 OpenAI
export OPENAI_API_KEY=your-api-key
```

### 3. 运行 Demo

```bash
python main.py
```

## 📖 代码解析

### Chain 基础

```python
from langchain.prompts import ChatPromptTemplate
from langchain.chat_models import init_chat_model

# 1. 定义提示模板
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个{expertise}专家"),
    ("user", "{question}")
])

# 2. 初始化模型
model = init_chat_model("anthropic:claude-sonnet-4-6")

# 3. 创建 Chain（管道操作符）
chain = prompt | model

# 4. 执行
response = chain.invoke({
    "expertise": "Python 编程",
    "question": "什么是装饰器？"
})
```

**管道操作符 `|`**：类似 Unix 管道，将输出传递给下一个组件

### 工具定义

```python
from langchain.tools import tool

@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息。"""
    return f"{city}: 晴朗，25°C"
```

**工具要点：**
- 使用 `@tool` 装饰器
- 函数 docstring 会成为工具的 description
- 参数类型注解用于生成 schema

### Agent 创建

```python
from langchain.agents import create_agent

agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_weather, calculate],
    system_prompt="你是一个智能助手"
)

response = agent.invoke({
    "messages": [{"role": "user", "content": "北京天气怎么样？"}]
})
```

## 🔧 自定义工具

### 添加新工具

```python
@tool
def get_time(city: str) -> str:
    """获取指定城市的当前时间"""
    from datetime import datetime
    return f"{city}当前时间：{datetime.now().strftime('%H:%M')}"

@tool
def translate(text: str, target_lang: str = "en") -> str:
    """翻译文本到目标语言"""
    # 调用翻译 API
    return f"翻译结果：{text}"
```

### 使用外部 API

```python
import requests

@tool
def get_stock_price(symbol: str) -> str:
    """获取股票价格"""
    response = requests.get(
        f"https://api.example.com/stock/{symbol}"
    )
    data = response.json()
    return f"{symbol}: ${data['price']}"
```

## 💡 Chain vs Agent

| 特性 | Chain | Agent |
|------|-------|-------|
| **用途** | 固定流程 | 动态决策 |
| **工具** | 不支持 | 支持 |
| **灵活性** | 低 | 高 |
| **复杂度** | 简单 | 较复杂 |
| **适用场景** | 简单问答、格式化 | 需要工具调用 |

**选择建议：**
- 只需 LLM 回答 → 用 Chain
- 需要调用外部 API/函数 → 用 Agent

## ⚠️ 常见问题

**Q: 如何更换模型？**
A: 修改 `init_chat_model()` 的参数，如 `"openai:gpt-4o"`。

**Q: 工具调用不准确？**
A: 优化工具的 docstring，让描述更清晰。

**Q: 如何查看 Agent 的思考过程？**
A: 设置 `verbose=True` 参数。

## 📚 下一步

完成这个 Demo 后，尝试：
1. 添加更多实用工具（如调用内部 API）
2. 学习 `langchain-advanced` Demo（记忆 + 结构化输出）
3. 探索 LangChain 的 RAG 功能

---

**预计运行时间**: 1-3 分钟

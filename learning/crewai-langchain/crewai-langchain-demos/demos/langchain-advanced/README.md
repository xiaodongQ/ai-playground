# LangChain 进阶 Demo - 带记忆和结构化输出

## 📋 场景说明

这个 Demo 展示 LangChain 的高级功能：
- **多轮对话记忆**：Agent 记住之前的对话
- **结构化输出**：强制模型返回指定 Schema
- **运行时上下文**：工具可以访问用户信息

## 🎯 学习目标

- 掌握 LangChain 的记忆机制（Checkpointer）
- 学习结构化输出（Structured Output）
- 理解运行时上下文（Runtime Context）
- 对比基础版和进阶版的差异

## 🚀 快速开始

### 1. 安装依赖

```bash
cd langchain-advanced
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export ANTHROPIC_API_KEY=your-api-key
```

### 3. 运行 Demo

```bash
python main.py
```

## 📖 代码解析

### 记忆机制

```python
from langgraph.checkpoint.memory import InMemorySaver

# 创建检查点（记忆存储）
checkpointer = InMemorySaver()

# 创建 Agent 时传入
agent = create_agent(
    ...,
    checkpointer=checkpointer
)

# 使用 thread_id 保持对话状态
config = {"configurable": {"thread_id": "conversation_001"}}

# 多轮对话（Agent 记得之前的内容）
agent.invoke({"messages": [...]}, config=config)
```

**记忆原理：**
- 每次对话保存到 Checkpointer
- 通过 `thread_id` 检索历史
- 支持内存、数据库等多种存储

### 结构化输出

```python
from dataclasses import dataclass
from langchain.agents.structured_output import ToolStrategy

# 1. 定义响应 Schema
@dataclass
class WeatherResponse:
    greeting: str
    weather_summary: str
    temperature: str
    suggestion: str

# 2. 创建 Agent 时指定
agent = create_agent(
    ...,
    response_format=ToolStrategy(WeatherResponse)
)

# 3. 获取结构化响应
response = agent.invoke(...)
structured = response["structured_response"]
print(structured.greeting)
```

**优势：**
- 强制模型返回指定格式
- 便于程序化处理
- 减少解析错误

### 运行时上下文

```python
from dataclasses import dataclass
from langchain.tools import ToolRuntime

# 1. 定义上下文 Schema
@dataclass
class UserContext:
    user_id: str
    user_name: str
    preferred_unit: str

# 2. 工具中访问上下文
@tool
def get_user_location(runtime: ToolRuntime) -> str:
    user_id = runtime.context.user_id
    return lookup_location(user_id)

# 3. 调用时传入上下文
agent.invoke(
    ...,
    context=UserContext(user_id="001", user_name="张三")
)
```

## 🔧 自定义配置

### 更换存储后端

```python
# 使用 Redis 存储（生产环境）
from langgraph.checkpoint.redis import RedisSaver

checkpointer = RedisSaver.from_conn_string("redis://localhost:6379")
```

### 自定义响应格式

```python
@dataclass
class CustomResponse:
    status: str
    data: dict
    error: str | None
    timestamp: str
```

### 添加更多上下文

```python
@dataclass
class UserContext:
    user_id: str
    user_name: str
    preferences: dict
    history: list
    subscription: str
```

## 💡 进阶技巧

### 1. 长期记忆

```python
# 使用数据库存储长期记忆
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost/db"
)
```

### 2. 动态 Schema

```python
# 根据用户类型返回不同格式
if user_context.is_premium:
    response_format = ToolStrategy(PremiumResponse)
else:
    response_format = ToolStrategy(StandardResponse)
```

### 3. 中间件

```python
from langchain.agents.middleware import wrap_model_call

@wrap_model_call
def add_custom_header(request, handler):
    # 在请求前添加自定义逻辑
    request.state["custom_data"] = get_custom_data()
    return handler(request)

agent = create_agent(
    ...,
    middleware=[add_custom_header]
)
```

## ⚠️ 常见问题

**Q: 记忆不生效？**
A: 确保使用相同的 `thread_id` 和 `checkpointer`。

**Q: 结构化输出失败？**
A: 检查 Schema 定义是否清晰，避免复杂嵌套。

**Q: 上下文访问报错？**
A: 确保 `context_schema` 和传入的 `context` 匹配。

## 📚 对比总结

| 特性 | 基础版 | 进阶版 |
|------|--------|--------|
| 记忆 | ❌ | ✅ |
| 结构化输出 | ❌ | ✅ |
| 运行时上下文 | ❌ | ✅ |
| 多轮对话 | ❌ | ✅ |
| 复杂度 | 低 | 中 |

## 📚 下一步

完成这个 Demo 后，尝试：
1. 使用数据库存储长期记忆
2. 集成 RAG（检索增强生成）
3. 探索 LangGraph 进行更复杂的流程编排

---

**预计运行时间**: 2-5 分钟

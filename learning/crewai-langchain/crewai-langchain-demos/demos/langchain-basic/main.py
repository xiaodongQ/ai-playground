#!/usr/bin/env python3
"""
LangChain 基础 Demo - Chain + Agent

场景：智能助手
- 基础 Chain：简单的提示模板 + 模型
- 带工具的 Agent：可以调用函数

适合：理解 LangChain 的核心抽象
"""

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain.tools import tool

# ==================== 1. 基础 Chain 示例 ====================

print("=" * 60)
print("📖 第一部分：基础 Chain 示例")
print("=" * 60)
print()

# 定义提示模板
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业的{expertise}专家，擅长用简洁的语言解释复杂概念。"),
    ("user", "{question}")
])

# 初始化模型
# 使用模型标识符（推荐方式）
model = init_chat_model("anthropic:claude-sonnet-4-6")

# 创建 Chain（使用管道操作符 |）
chain = prompt | model

# 执行 Chain
response = chain.invoke({
    "expertise": "Python 编程",
    "question": "什么是装饰器？请用 C++ 开发者能理解的方式解释。"
})

print("问题：什么是装饰器？（用 C++ 开发者能理解的方式）")
print()
print("回答:")
print(response.content)
print()

# ==================== 2. 带工具的 Agent 示例 ====================

print("=" * 60)
print("🤖 第二部分：带工具的 Agent 示例")
print("=" * 60)
print()

# 定义工具（普通 Python 函数）
@tool
def get_weather(city: str) -> str:
    """
    获取指定城市的天气信息。
    
    Args:
        city: 城市名称，如"北京"、"上海"
    
    Returns:
        天气描述字符串
    """
    # 模拟天气数据（实际使用时可以调用天气 API）
    weather_data = {
        "北京": "晴朗，25°C，湿度 40%",
        "上海": "多云，28°C，湿度 65%",
        "深圳": "小雨，26°C，湿度 80%",
        "成都": "阴天，22°C，湿度 70%"
    }
    return weather_data.get(city, f"{city}的天气数据暂时 unavailable")

@tool
def calculate(expression: str) -> str:
    """
    计算数学表达式。
    
    Args:
        expression: 数学表达式，如"2+2"、"10*5"
    
    Returns:
        计算结果
    """
    try:
        # 安全的表达式求值（只允许基本运算）
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误：{str(e)}"

@tool
def search_knowledge(query: str) -> str:
    """
    搜索知识库获取信息。
    
    Args:
        query: 搜索关键词
    
    Returns:
        相关信息
    """
    # 模拟知识库
    knowledge_base = {
        "Python": "Python 是一种高级编程语言，以简洁易读著称。",
        "Rust": "Rust 是系统级编程语言，强调安全性和性能。",
        "Go": "Go 是 Google 开发的编译型语言，擅长并发编程。",
        "C++": "C++ 是通用编程语言，支持面向对象和泛型编程。"
    }
    return knowledge_base.get(query, f"未找到关于'{query}'的信息")

# 创建 Agent
agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_weather, calculate, search_knowledge],
    system_prompt=(
        "你是一个智能助手，可以帮助用户查询天气、进行计算、搜索知识。\n"
        "回答问题时：\n"
        "1. 如果需要具体数据，使用相应的工具\n"
        "2. 如果工具无法回答，用自己的知识回答\n"
        "3. 回答简洁、准确、有帮助"
    )
)

# 测试 Agent
test_questions = [
    "北京今天天气怎么样？",
    "计算 123 * 456 等于多少",
    "Rust 编程语言有什么特点？",
    "上海天气如何？和北京比怎么样？"
]

for i, question in enumerate(test_questions, 1):
    print(f"\n--- 问题 {i}: {question} ---")
    
    response = agent.invoke({
        "messages": [{"role": "user", "content": question}]
    })
    
    # 提取回答
    if isinstance(response, dict) and "messages" in response:
        # 获取最后一条消息（Agent 的回答）
        last_message = response["messages"][-1]
        print(last_message.content)
    else:
        print(response)

print()
print("=" * 60)
print("✅ Demo 完成！")
print("=" * 60)
print()
print("💡 提示:")
print("   - 修改 test_questions 测试不同问题")
print("   - 添加自定义工具扩展 Agent 能力")
print("   - 查看 langchain-advanced demo 学习记忆和结构化输出")

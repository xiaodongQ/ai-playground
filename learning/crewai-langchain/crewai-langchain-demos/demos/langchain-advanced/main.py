#!/usr/bin/env python3
"""
LangChain 进阶 Demo - 带记忆和结构化输出

场景：个性化天气助手
- 记忆功能：记住用户偏好和对话历史
- 结构化输出：强制模型返回指定格式
- 运行时上下文：传递用户信息

特点：
- 多轮对话记忆
- 结构化响应 Schema
- 上下文感知工具
"""

from dataclasses import dataclass
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.structured_output import ToolStrategy

# ==================== 1. 定义上下文 Schema ====================

@dataclass
class UserContext:
    """用户上下文 Schema"""
    user_id: str
    user_name: str
    preferred_unit: str = "celsius"  # 温度单位偏好

# ==================== 2. 定义工具 ====================

@tool
def get_weather(city: str) -> str:
    """
    获取指定城市的天气信息。
    
    Args:
        city: 城市名称
    
    Returns:
        天气描述
    """
    weather_data = {
        "北京": {"temp_c": 25, "temp_f": 77, "condition": "晴朗", "humidity": 40},
        "上海": {"temp_c": 28, "temp_f": 82, "condition": "多云", "humidity": 65},
        "深圳": {"temp_c": 30, "temp_f": 86, "condition": "小雨", "humidity": 80},
        "成都": {"temp_c": 22, "temp_f": 72, "condition": "阴天", "humidity": 70},
        "纽约": {"temp_c": 20, "temp_f": 68, "condition": "晴朗", "humidity": 50},
        "东京": {"temp_c": 24, "temp_f": 75, "condition": "多云", "humidity": 60}
    }
    
    data = weather_data.get(city)
    if data:
        return f"{city}: {data['condition']}, {data['temp_c']}°C/{data['temp_f']}°F, 湿度{data['humidity']}%"
    return f"暂未收录{city}的天气数据"

@tool
def get_user_location(runtime: ToolRuntime) -> str:
    """
    获取用户的当前位置。
    使用运行时上下文中的用户 ID 查询位置。
    """
    # 模拟根据用户 ID 返回位置
    user_locations = {
        "user_001": "北京",
        "user_002": "上海",
        "user_003": "纽约"
    }
    
    if runtime.context:
        user_id = runtime.context.user_id
        return user_locations.get(user_id, "未知位置")
    return "未知位置"

@tool
def get_user_preferences(runtime: ToolRuntime) -> str:
    """
    获取用户的偏好设置。
    """
    if runtime.context:
        return (
            f"用户：{runtime.context.user_name}\n"
            f"温度单位：{runtime.context.preferred_unit}\n"
            f"偏好：喜欢详细的天气描述"
        )
    return "未知用户"

# ==================== 3. 定义响应格式 ====================

@dataclass
class WeatherResponse:
    """天气响应 Schema"""
    greeting: str  # 问候语
    weather_summary: str  # 天气总结
    temperature: str  # 温度
    condition: str  # 天气状况
    suggestion: str  # 建议
    is_good_day: bool  # 是否适合外出

# ==================== 4. 创建 Agent ====================

# 系统提示
SYSTEM_PROMPT = """
你是一个专业的天气助手，说话风格友好、专业。

你可以使用以下工具：
- get_weather: 获取指定城市的天气
- get_user_location: 获取用户当前位置
- get_user_preferences: 获取用户偏好

回答规则：
1. 如果用户问天气但没有指定地点，先获取用户位置
2. 根据用户偏好（温度单位）格式化输出
3. 提供实用的建议（如穿衣、出行）
4. 使用友好的语气，适当加入表情符号

始终使用 WeatherResponse 格式返回结构化响应。
"""

# 初始化模型
model = init_chat_model(
    "anthropic:claude-sonnet-4-6",
    temperature=0.5,  # 适度创意
    max_tokens=500
)

# 创建记忆检查点
checkpointer = InMemorySaver()

# 创建 Agent
agent = create_agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_weather, get_user_location, get_user_preferences],
    context_schema=UserContext,
    response_format=ToolStrategy(WeatherResponse),
    checkpointer=checkpointer,
    verbose=True
)

# ==================== 5. 多轮对话演示 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🌤️  LangChain 进阶 Demo - 个性化天气助手")
    print("=" * 60)
    print()
    
    # 配置用户上下文
    user_context = UserContext(
        user_id="user_001",
        user_name="张三",
        preferred_unit="celsius"
    )
    
    # 对话配置（thread_id 保持对话记忆）
    config = {"configurable": {"thread_id": "conversation_001"}}
    
    # 多轮对话
    conversations = [
        "你好，我是新用户",
        "我这边天气怎么样？",
        "适合出门运动吗？",
        "那上海呢？我下周要去出差",
        "谢谢你的建议！"
    ]
    
    print(f"👤 用户：{user_context.user_name}")
    print(f"📍 默认位置：北京")
    print(f"🌡️  温度单位：{user_context.preferred_unit}")
    print("=" * 60)
    print()
    
    for i, message in enumerate(conversations, 1):
        print(f"--- 第 {i} 轮对话 ---")
        print(f"👤 用户：{message}")
        print()
        
        # 调用 Agent
        response = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            context=user_context
        )
        
        # 解析响应
        if isinstance(response, dict):
            if "structured_response" in response:
                structured = response["structured_response"]
                print(f"🤖 助手：{structured.greeting}")
                print(f"   天气：{structured.weather_summary}")
                print(f"   温度：{structured.temperature}")
                print(f"   状况：{structured.condition}")
                print(f"   建议：{structured.suggestion}")
                print(f"   适合外出：{'✅ 是' if structured.is_good_day else '❌ 否'}")
            elif "messages" in response:
                last_msg = response["messages"][-1]
                print(f"🤖 助手：{last_msg.content[:200]}...")
        else:
            print(f"🤖 助手：{str(response)[:200]}...")
        
        print()
    
    print("=" * 60)
    print("✅ Demo 完成！")
    print("=" * 60)
    print()
    print("💡 关键特性:")
    print("   1. 记忆功能：Agent 记住了之前的对话内容")
    print("   2. 结构化输出：强制返回 WeatherResponse 格式")
    print("   3. 上下文感知：工具可以访问用户信息")
    print()
    print("📚 对比基础版:")
    print("   - 基础版：单次问答，无记忆")
    print("   - 进阶版：多轮对话，个性化响应")

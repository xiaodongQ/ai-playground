#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日本留学咨询顾问 - CrewAI 智能体

功能：
- 解答日本研究生/修士申请相关问题
- 提供选校建议、时间规划、材料准备指导
- 生成个性化的申请方案

使用前确保已安装：pip install crewai crewai-tools pysqlite3-binary
"""

# ============== 必需的 sqlite3 补丁 ==============
import pysqlite3
import sys
sys.modules['sqlite3'] = pysqlite3
# ===============================================

from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool
import os

# ============== 配置区 ==============
# 如果需要联网搜索，设置 SERPER_API_KEY
# os.environ['SERPER_API_KEY'] = 'your-serper-api-key'

# 设置模型（使用阿里云百炼 - 通义千问）
# ⚠️ 安全提示：不要硬编码 API Key！使用环境变量或配置文件（加入 .gitignore）
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')  # 从环境变量读取
os.environ['OPENAI_API_BASE'] = os.getenv('OPENAI_API_BASE', 'https://coding.dashscope.aliyuncs.com/v1')
os.environ['OPENAI_MODEL_NAME'] = os.getenv('OPENAI_MODEL_NAME', 'qwen3.5-plus')
# ====================================


def create_study_abroad_agent():
    """创建日本留学咨询顾问智能体"""
    
    # 定义 Agent - 日本留学专家
    consultant_agent = Agent(
        role='日本留学申请专家',
        goal='为学生提供专业、详细的日本研究生/修士申请指导',
        backstory='''你是一位拥有 10 年经验的日本留学申请专家，熟悉日本各大院校的研究生（预科）
        和修士（硕士）申请流程。你帮助学生进行院校定位、研究计划书指导、套磁信撰写、
        出愿材料准备、时间规划等全流程服务。你了解东京大学、京都大学、大阪大学、东北大学、
        名古屋大学、北海道大学、九州大学等顶尖院校的申请要求和偏好。''',
        verbose=True,
        allow_delegation=False,
        # tools=[SerperDevTool()] if os.environ.get('SERPER_API_KEY') else []
    )
    
    return consultant_agent


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


# ============== 示例问题 ==============
SAMPLE_QUESTIONS = [
    "我想申请东京大学的计算机专业修士，需要准备什么？",
    "我现在大二，想申请日本研究生，应该如何规划时间？",
    "我的日语是 N2，英语托福 80 分，能申请哪些学校？",
    "研究计划书应该怎么写？有什么注意事项？",
    "套磁信应该什么时候发？怎么写才能提高回复率？",
]


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

#!/usr/bin/env python3
"""
CrewAI 基础 Demo - 简单角色协作

场景：技术调研团队
- Researcher（研究员）：负责调研主题
- Writer（作家）：负责撰写报告

适合：C++/Go 开发者快速理解 CrewAI 的多 Agent 协作模式
"""

from crewai import Agent, Task, Crew, Process
from typing import List

# ==================== 1. 定义 Agent ====================

# 研究员 Agent
researcher = Agent(
    role="技术研究员",
    goal="深入调研{topic}领域，找出关键信息和技术要点",
    backstory=(
        "你是一位经验丰富的技术研究员，拥有 10 年技术调研经验。"
        "你擅长从海量信息中筛选出最关键的内容，并用清晰的结构呈现。"
        "你特别关注技术的实用性、性能特点和适用场景。"
    ),
    verbose=True,  # 输出详细日志
    allow_delegation=False  # 不允许委托任务
)

# 作家 Agent
writer = Agent(
    role="技术作家",
    goal="将技术调研结果转化为清晰易懂的技术文档",
    backstory=(
        "你是一位资深技术作家，擅长将复杂的技术概念用简洁的语言表达。"
        "你有 C++ 和 Go 语言背景，理解系统级开发者的需求。"
        "你的文章结构清晰，代码示例准确，深受开发者喜爱。"
    ),
    verbose=True,
    allow_delegation=False
)

# ==================== 2. 定义 Task ====================

# 调研任务
research_task = Task(
    description=(
        "对{topic}进行彻底调研，重点关注：\n"
        "1. 核心概念和原理\n"
        "2. 主要特点和优势\n"
        "3. 典型使用场景\n"
        "4. 与其他技术的对比\n"
        "5. 学习资源和最佳实践\n\n"
        "确保信息准确、结构清晰，适合有 C++/Go 背景的开发者阅读。"
    ),
    expected_output=(
        "一份包含以下内容的调研报告：\n"
        "- 核心概念（5-7 个要点）\n"
        "- 技术特点（3-5 个要点）\n"
        "- 使用场景（3-5 个场景）\n"
        "- 对比分析（与 1-2 个类似技术对比）\n"
        "- 学习建议（3-5 条建议）"
    ),
    agent=researcher,
    output_file="output/research_report.md"  # 输出到文件
)

# 写作任务
writing_task = Task(
    description=(
        "基于调研结果，撰写一篇完整的技术介绍文章。\n"
        "要求：\n"
        "1. 使用 Markdown 格式\n"
        "2. 包含清晰的章节结构\n"
        "3. 添加代码示例（如适用）\n"
        "4. 语言简洁，避免冗余\n"
        "5. 适合有系统编程背景的开发者阅读"
    ),
    expected_output=(
        "一篇完整的技术文章，包含：\n"
        "- 引言（为什么需要这项技术）\n"
        "- 核心概念详解\n"
        "- 快速入门示例\n"
        "- 最佳实践\n"
        "- 学习资源推荐"
    ),
    agent=writer,
    context=[research_task],  # 依赖调研任务的输出
    output_file="output/technical_article.md",
    markdown=True  # 启用 Markdown 格式
)

# ==================== 3. 创建 Crew ====================

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,  # 顺序执行：先调研，后写作
    verbose=True,
    memory=True  # 启用记忆，Agent 可以记住之前的内容
)

# ==================== 4. 执行 ====================

if __name__ == "__main__":
    print("🚀 启动 CrewAI 基础 Demo - 技术调研团队")
    print("=" * 50)
    
    # 传入主题参数
    inputs = {
        "topic": "Rust 编程语言"  # 可以改成任何你想调研的主题
    }
    
    print(f"📋 调研主题：{inputs['topic']}")
    print("=" * 50)
    print()
    
    # 启动执行
    result = crew.kickoff(inputs=inputs)
    
    print()
    print("=" * 50)
    print("✅ 任务完成！")
    print("=" * 50)
    print(f"\n📄 调研报告：output/research_report.md")
    print(f"📄 技术文章：output/technical_article.md")
    print(f"\n💡 提示：修改 main.py 中的 topic 变量，可以调研任何主题！")

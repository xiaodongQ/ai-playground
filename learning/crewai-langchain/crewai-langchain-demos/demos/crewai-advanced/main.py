#!/usr/bin/env python3
"""
CrewAI 进阶 Demo - 带工具和流程编排

场景：自动化内容创作流水线
- Researcher（研究员）：使用搜索工具调研主题
- Writer（作家）：撰写文章
- Reviewer（审查员）：审查文章质量

特点：
- 集成外部工具（搜索、文件操作）
- 使用 YAML 配置管理 Agent 和 Task
- 带质量检查的完整流程
"""

import os
from pathlib import Path
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool, FileReadTool, MDXSearchTool

# ==================== 1. 定义工具 ====================

# 搜索工具（需要 SERPER_API_KEY）
search_tool = SerperDevTool()

# 文件读取工具
file_read_tool = FileReadTool()

# Markdown 搜索工具
mdx_search_tool = MDXSearchTool()

# ==================== 2. 定义 Agent ====================

# 研究员 Agent（带搜索工具）
researcher = Agent(
    role="高级技术研究员",
    goal="使用搜索工具深入调研{topic}，收集最新、最准确的信息",
    backstory=(
        "你是一位资深技术研究员，擅长利用各种工具收集信息。"
        "你会使用搜索引擎查找最新资料，阅读相关文档，"
        "然后整理出结构化的调研报告。"
        "你特别注重信息的时效性和准确性。"
    ),
    tools=[search_tool],  # 配备搜索工具
    verbose=True,
    max_iter=5,  # 最大迭代次数
    memory=True
)

# 作家 Agent
writer = Agent(
    role="资深技术作家",
    goal="基于调研结果撰写高质量的技术文章",
    backstory=(
        "你是一位经验丰富的技术作家，发表过数十篇技术文章。"
        "你擅长将复杂的技术概念用清晰的逻辑和生动的例子呈现。"
        "你的文章结构严谨，代码示例准确，深受读者喜爱。"
    ),
    verbose=True,
    memory=True
)

# 审查员 Agent
reviewer = Agent(
    role="技术审查专家",
    goal="审查文章的技术准确性、完整性和可读性",
    backstory=(
        "你是一位严谨的技术专家，有 15 年技术审查经验。"
        "你擅长发现技术错误、逻辑漏洞和表述不清的地方。"
        "你的审查意见具体、建设性，帮助作者提升文章质量。"
    ),
    verbose=True,
    allow_delegation=True  # 允许委托修改任务
)

# ==================== 3. 定义 Task ====================

# 调研任务
research_task = Task(
    description=(
        "使用搜索工具对{topic}进行彻底调研：\n"
        "1. 搜索最新的官方文档和教程\n"
        "2. 查找社区讨论和最佳实践\n"
        "3. 收集代码示例和使用案例\n"
        "4. 对比类似技术的优缺点\n\n"
        "确保信息来源可靠，优先选择官方文档和权威来源。"
    ),
    expected_output=(
        "一份详细的调研报告，包含：\n"
        "- 核心概念和原理（5-7 个要点）\n"
        "- 技术特点和优势（3-5 个要点）\n"
        "- 典型使用场景（至少 3 个）\n"
        "- 代码示例（2-3 个）\n"
        "- 学习资源链接（5-10 个）\n"
        "- 与类似技术的对比分析"
    ),
    agent=researcher,
    output_file="output/advanced_research.md"
)

# 写作任务
writing_task = Task(
    description=(
        "基于调研报告，撰写一篇完整的技术教程文章：\n"
        "1. 使用 Markdown 格式\n"
        "2. 包含清晰的章节结构\n"
        "3. 插入代码示例（使用代码块）\n"
        "4. 添加图表说明（用文字描述）\n"
        "5. 提供实践建议\n\n"
        "文章应该适合有编程基础的开发者阅读。"
    ),
    expected_output=(
        "一篇完整的技术教程，包含：\n"
        "- 引言（为什么学习这项技术）\n"
        "- 核心概念详解\n"
        "- 环境搭建指南\n"
        "- 快速入门示例\n"
        "- 进阶用法\n"
        "- 最佳实践\n"
        "- 常见问题解答\n"
        "- 学习资源推荐"
    ),
    agent=writer,
    context=[research_task],  # 依赖调研任务
    output_file="output/advanced_article.md",
    markdown=True
)

# 审查任务
review_task = Task(
    description=(
        "审查技术文章的质量：\n"
        "1. 技术准确性：检查概念、代码是否正确\n"
        "2. 完整性：是否覆盖了关键知识点\n"
        "3. 可读性：逻辑是否清晰，表述是否准确\n"
        "4. 实用性：示例是否有实际价值\n\n"
        "给出具体的修改建议，帮助提升文章质量。"
    ),
    expected_output=(
        "一份审查报告，包含：\n"
        "- 整体评价（优秀/良好/需改进）\n"
        "- 技术准确性评估\n"
        "- 发现的错误和问题（具体指出）\n"
        "- 改进建议（至少 5 条）\n"
        "- 最终评分（1-10 分）"
    ),
    agent=reviewer,
    context=[writing_task],  # 依赖写作任务
    output_file="output/review_report.md"
)

# ==================== 4. 创建 Crew ====================

crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[research_task, writing_task, review_task],
    process=Process.sequential,  # 顺序执行
    verbose=True,
    memory=True,
    cache=True  # 启用缓存，避免重复调用
)

# ==================== 5. 执行 ====================

if __name__ == "__main__":
    print("🚀 启动 CrewAI 进阶 Demo - 自动化内容创作流水线")
    print("=" * 60)
    
    # 检查环境变量
    if not os.getenv("SERPER_API_KEY"):
        print("⚠️  警告：未设置 SERPER_API_KEY，搜索工具将不可用")
        print("   获取 API Key: https://serper.dev/")
        print("   或设置环境变量：export SERPER_API_KEY=your-key")
        print()
    
    # 创建输出目录
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # 传入主题参数
    inputs = {
        "topic": "LangChain 框架"  # 可以改成任何主题
    }
    
    print(f"📋 创作主题：{inputs['topic']}")
    print(f"👥 参与 Agent: Researcher → Writer → Reviewer")
    print(f"📁 输出目录：{output_dir.absolute()}")
    print("=" * 60)
    print()
    
    # 启动执行
    result = crew.kickoff(inputs=inputs)
    
    print()
    print("=" * 60)
    print("✅ 任务完成！")
    print("=" * 60)
    print(f"\n📄 调研报告：{output_dir}/advanced_research.md")
    print(f"📄 技术文章：{output_dir}/advanced_article.md")
    print(f"📄 审查报告：{output_dir}/review_report.md")
    print()
    print("💡 提示:")
    print("   - 查看 review_report.md 了解文章质量评估")
    print("   - 根据审查意见修改文章，提升质量")
    print("   - 修改 topic 变量，创作不同主题的内容")

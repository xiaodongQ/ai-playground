"""
Task 定义模块

定义内容创作流水线的各个 Task：
- Research Task：调研任务
- Writing Task：写作任务
- Review Task：审查任务
- Editing Task：编辑任务
"""

from crewai import Task

def create_research_task(agent):
    """创建调研任务"""
    return Task(
        description=(
            "对{topic}进行彻底调研：\n"
            "1. 搜索官方文档和权威教程\n"
            "2. 查找社区讨论和最佳实践\n"
            "3. 收集代码示例和使用案例\n"
            "4. 对比类似技术的优缺点\n"
            "5. 整理学习资源和问题解答\n\n"
            "确保信息来源可靠，优先选择官方文档、GitHub 仓库、权威技术博客。"
        ),
        expected_output=(
            "一份详细的调研报告，包含：\n"
            "- 核心概念（5-7 个要点，每个要点有详细说明）\n"
            "- 技术特点（3-5 个特点，附带应用场景）\n"
            "- 快速入门指南（环境搭建 + Hello World）\n"
            "- 代码示例（3-5 个实用示例）\n"
            "- 最佳实践（5-8 条建议）\n"
            "- 常见问题（5-10 个 FAQ）\n"
            "- 学习资源（10+ 个高质量链接）"
        ),
        agent=agent,
        output_file="output/research.md",
        markdown=True
    )

def create_writing_task(agent, research_task):
    """创建写作任务"""
    return Task(
        description=(
            "基于调研报告，撰写一篇完整的技术教程：\n"
            "1. 使用 Markdown 格式\n"
            "2. 包含以下章节：\n"
            "   - 引言（为什么需要这项技术）\n"
            "   - 核心概念详解\n"
            "   - 快速入门（10 分钟上手）\n"
            "   - 进阶用法\n"
            "   - 最佳实践\n"
            "   - 常见问题\n"
            "   - 学习资源\n"
            "3. 代码示例使用代码块，带注释\n"
            "4. 语言简洁，适合有编程基础的开发者\n\n"
            "文章长度：2000-4000 字"
        ),
        expected_output=(
            "一篇完整的技术教程文章，包含：\n"
            "- 吸引人的标题\n"
            "- 清晰的章节结构\n"
            "- 准确的代码示例\n"
            "- 实用的最佳实践\n"
            "- 完整的学习资源"
        ),
        agent=agent,
        context=[research_task],
        output_file="output/draft.md",
        markdown=True
    )

def create_review_task(agent, writing_task):
    """创建审查任务"""
    return Task(
        description=(
            "审查技术文章的质量：\n"
            "1. 技术准确性检查：\n"
            "   - 概念描述是否正确\n"
            "   - 代码示例是否可运行\n"
            "   - 数据是否准确\n"
            "2. 完整性检查：\n"
            "   - 是否覆盖关键知识点\n"
            "   - 是否有重要遗漏\n"
            "3. 可读性检查：\n"
            "   - 逻辑是否清晰\n"
            "   - 表述是否准确\n"
            "   - 是否有歧义\n"
            "4. 实用性评估：\n"
            "   - 示例是否有实际价值\n"
            "   - 建议是否可操作\n\n"
            "给出具体的修改建议，指出问题所在章节。"
        ),
        expected_output=(
            "一份详细的审查报告，包含：\n"
            "- 整体评价（优秀/良好/合格/需改进）\n"
            "- 技术准确性评分（1-10 分）\n"
            "- 完整性评分（1-10 分）\n"
            "- 可读性评分（1-10 分）\n"
            "- 发现的问题（具体指出章节和问题）\n"
            "- 修改建议（至少 5 条具体建议）\n"
            "- 最终推荐（直接发布/修改后发布/需要重写）"
        ),
        agent=agent,
        context=[writing_task],
        output_file="output/review.md",
        markdown=True
    )

def create_editing_task(agent, review_task, writing_task):
    """创建编辑任务"""
    return Task(
        description=(
            "根据审查报告，对文章进行最终编辑：\n"
            "1. 修正审查报告指出的所有问题\n"
            "2. 格式统一：\n"
            "   - 标题层级一致\n"
            "   - 代码块格式统一\n"
            "   - 列表格式规范\n"
            "3. 语言润色：\n"
            "   - 消除语病和错别字\n"
            "   - 优化冗长表述\n"
            "   - 确保术语一致\n"
            "4. 最终检查：\n"
            "   - 链接是否有效\n"
            "   - 代码是否完整\n"
            "   - 格式是否美观\n\n"
            "产出达到发布标准的最终版本。"
        ),
        expected_output=(
            "一篇达到发布标准的最终文章，包含：\n"
            "- 修正了所有审查发现的问题\n"
            "- 格式统一、美观\n"
            "- 语言流畅、准确\n"
            "- 代码示例完整、可运行\n"
            "- 术语一致、规范"
        ),
        agent=agent,
        context=[review_task, writing_task],
        output_file="output/final_article.md",
        markdown=True
    )

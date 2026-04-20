"""
自动化内容创作 Multi-Agent 系统

场景：技术博客自动创作流水线
- Researcher Agent：调研主题，收集信息
- Writer Agent：基于调研写文章
- Reviewer Agent：审查文章质量
- Editor Agent：最终编辑和格式化

技术栈：CrewAI + LangChain 结合
"""

from src.agents import create_researcher, create_writer, create_reviewer, create_editor
from src.tasks import create_research_task, create_writing_task, create_review_task, create_editing_task
from src.crew import create_content_crew

def run(topic: str = "Python 异步编程"):
    """
    运行内容创作流水线
    
    Args:
        topic: 创作主题
    """
    print("🚀 启动自动化内容创作系统")
    print("=" * 60)
    print(f"📋 主题：{topic}")
    print("=" * 60)
    print()
    
    # 创建 Crew
    crew = create_content_crew()
    
    # 执行
    inputs = {"topic": topic}
    result = crew.kickoff(inputs=inputs)
    
    print()
    print("=" * 60)
    print("✅ 内容创作完成！")
    print("=" * 60)
    print()
    print("📄 输出文件:")
    print("   - output/research.md     (调研报告)")
    print("   - output/draft.md        (初稿)")
    print("   - output/review.md       (审查报告)")
    print("   - output/final_article.md (最终文章)")
    
    return result

if __name__ == "__main__":
    run()

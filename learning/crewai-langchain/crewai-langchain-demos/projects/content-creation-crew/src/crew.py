"""
Crew 编排模块

创建内容创作 Crew，编排所有 Agent 和 Task
"""

from crewai import Crew, Process
from .agents import create_researcher, create_writer, create_reviewer, create_editor
from .tasks import create_research_task, create_writing_task, create_review_task, create_editing_task

def create_content_crew():
    """
    创建内容创作 Crew
    
    Returns:
        Crew: 配置好的内容创作团队
    """
    # 创建 Agent
    researcher = create_researcher()
    writer = create_writer()
    reviewer = create_reviewer()
    editor = create_editor()
    
    # 创建 Task
    research_task = create_research_task(researcher)
    writing_task = create_writing_task(writer, research_task)
    review_task = create_review_task(reviewer, writing_task)
    editing_task = create_editing_task(editor, review_task, writing_task)
    
    # 创建 Crew
    crew = Crew(
        agents=[researcher, writer, reviewer, editor],
        tasks=[research_task, writing_task, review_task, editing_task],
        process=Process.sequential,  # 顺序执行
        verbose=True,
        memory=True,  # 启用记忆
        cache=True    # 启用缓存
    )
    
    return crew

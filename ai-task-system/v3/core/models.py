"""
AI Task System V3 - Data Models
基于 CodeBuddy 个人内网专属版设计
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum
from uuid import uuid4


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EVALUATING = "evaluating"
    RERUNNING = "rerunning"


class Task(BaseModel):
    """任务核心模型"""
    # 基础标识
    id: str = Field(default_factory=lambda: uuid4().hex[:8], description="8位短UUID")
    title: str = Field(description="任务标题")
    description: str = Field(description="任务详细描述")
    status: TaskStatus = Field(default=TaskStatus.PENDING)

    # CodeBuddy 执行配置
    allowed_tools: str = Field(default="Read,Write,Bash,Git", description="允许工具")
    permission_mode: str = Field(default="acceptEdits", description="权限模式")
    output_format: str = Field(default="text", description="输出格式")
    json_schema: Optional[str] = Field(default=None, description="JSON Schema")

    # 迭代与超时配置
    max_iterations: int = Field(default=3, description="最大迭代次数")
    current_iteration: int = Field(default=0, description="当前迭代次数")
    pass_threshold: int = Field(default=7, description="达标阈值")
    absolute_timeout: int = Field(default=3600, description="绝对超时(秒)")
    no_output_timeout: int = Field(default=600, description="无输出超时(秒)")

    # 多轮对话支持
    session_id: Optional[str] = Field(default=None, description="CodeBuddy会话ID")

    # 全链路时间节点
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    duration: Optional[int] = Field(default=None, description="执行耗时(秒)")

    # 沙箱路径
    workspace_path: Optional[str] = Field(default=None)


class Execution(BaseModel):
    """执行记录模型"""
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str = Field(description="关联任务ID")
    session_id: Optional[str] = Field(default=None)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)
    output: Optional[str] = Field(default=None)
    error: Optional[str] = Field(default=None)
    status: str = Field(description="执行状态")
    duration: Optional[int] = Field(default=None)


class Evaluation(BaseModel):
    """评估结果模型"""
    id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str = Field(description="关联任务ID")
    execution_id: str = Field(description="关联执行ID")
    score: int = Field(description="评分1-10")
    comments: str = Field(description="评估意见")
    evaluated_at: datetime = Field(default_factory=datetime.now)

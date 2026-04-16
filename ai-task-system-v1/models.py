"""
AI Task Pickup System - Data Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TaskType(str, Enum):
    CODE_DEV = "code_dev"
    DOC_SUMMARY = "doc_summary"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PICKED = "picked"
    EXECUTING = "executing"
    COMPLETED = "completed"
    EVALUATED = "evaluated"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Evaluation(BaseModel):
    quality_score: float = Field(ge=0, le=100, description="Quality score 0-100")
    efficiency_score: float = Field(ge=0, le=100, description="Efficiency score 0-100")
    overall_score: float = Field(ge=0, le=100, description="Overall score 0-100")
    comment: str = Field(default="", description="Evaluation comment")
    evaluator: str = Field(default="", description="Which model evaluated")
    evaluated_at: datetime = Field(default_factory=datetime.now)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    type: TaskType = Field(default=TaskType.CODE_DEV, description="Task type")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    priority: Priority = Field(default=Priority.MEDIUM, description="Task priority")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    picked_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Execution info
    assignee: Optional[str] = Field(default=None, description="Which AI agent picked it")
    solution: Optional[str] = Field(default=None, description="Execution plan")
    result: Optional[str] = Field(default=None, description="Execution result")
    logs: List[str] = Field(default_factory=list, description="Execution logs")
    
    # Evaluation
    evaluation: Optional[Evaluation] = None
    
    class Config:
        use_enum_values = True


class TaskCreate(BaseModel):
    title: str
    description: str
    type: TaskType = TaskType.CODE_DEV
    priority: Priority = Priority.MEDIUM


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None

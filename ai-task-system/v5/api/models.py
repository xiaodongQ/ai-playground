"""V5 API - Request/Response 模型（基于 Pydantic）"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class TaskPriorityEnum(str, Enum):
    CRITICAL = "critical"    # 0
    HIGH     = "high"        # 1
    NORMAL   = "normal"      # 3
    LOW      = "low"         # 5
    BG       = "background"  # 9

class TaskStatusEnum(str, Enum):
    PENDING   = "pending"
    DEQUEUED  = "dequeued"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"
    DEAD      = "dead"

class WorkerStatusEnum(str, Enum):
    STARTING   = "starting"
    IDLE       = "idle"
    BUSY       = "busy"
    RECOVERING = "recovering"
    STOPPING   = "stopping"
    STOPPED    = "stopped"

class HealthStatusEnum(str, Enum):
    HEALTHY    = "healthy"
    SUSPECTED  = "suspected"
    UNHEALTHY  = "unhealthy"
    RECOVERING = "recovering"
    UNKNOWN    = "unknown"

# ─── Task Models ─────────────────────────────────────────────────────────────

class TaskSubmitRequest(BaseModel):
    prompt:          str = Field(..., description="任务描述 / prompt")
    agent:          Optional[str] = Field(None, description="Agent 类型: claude | codex | codebuddy")
    priority:       TaskPriorityEnum = Field(TaskPriorityEnum.NORMAL, description="优先级")
    timeout:        float = Field(600.0, ge=1, le=3600, description="任务超时（秒）")
    max_retries:    int   = Field(3, ge=0, le=10, description="最大重试次数")
    retry_delay:    float = Field(5.0, ge=1, description="重试基础延迟（秒）")
    allowed_tools:  Optional[list[str]] = Field(None, description="允许的工具白名单")
    permission_mode: Optional[str] = Field(None, description="权限模式: auto | bypass | plan")

class TaskSubmitResponse(BaseModel):
    task_id:  str
    status:   TaskStatusEnum
    message:  str

class TaskDetailResponse(BaseModel):
    task_id:       str
    status:        TaskStatusEnum
    priority:      TaskPriorityEnum
    agent:        Optional[str] = None
    payload:       dict[str, Any]
    timeout:       float
    max_retries:   int
    retry_count:   int
    created_at:    Optional[float] = None
    dequeued_at:   Optional[float] = None
    started_at:    Optional[float] = None
    completed_at:  Optional[float] = None
    worker_id:     Optional[str] = None
    result:        Optional[dict[str, Any]] = None
    error:         Optional[str] = None
    metadata:       Optional[dict[str, Any]] = None

class TaskListResponse(BaseModel):
    tasks:  list[TaskDetailResponse]
    total:  int
    page:   int
    size:   int

class TaskFailRequest(BaseModel):
    error:       str = Field(..., description="错误信息")
    retry:       bool = Field(True, description="是否自动重试")

class TaskRetryResponse(BaseModel):
    task_id:  str
    status:   TaskStatusEnum
    message:  str

# ─── Queue Models ────────────────────────────────────────────────────────────

class QueueMetricsResponse(BaseModel):
    pending:       int
    running:       int
    done_today:    int
    failed_today:  int
    dead_letters:  int
    avg_wait_time: float
    avg_run_time:  float

# ─── Worker Models ───────────────────────────────────────────────────────────

class WorkerDetailResponse(BaseModel):
    worker_id:     str
    agent_type:    str
    status:        WorkerStatusEnum
    task_count:    int
    error_count:   int
    current_task_id: Optional[str] = None
    started_at:    Optional[float] = None
    last_heartbeat: Optional[float] = None
    cpu_percent:   Optional[float] = None
    memory_mb:     Optional[float] = None
    health_status: Optional[HealthStatusEnum] = None

class WorkerListResponse(BaseModel):
    workers: list[WorkerDetailResponse]
    total:   int

class WorkerRestartResponse(BaseModel):
    worker_id:  str
    message:    str

# ─── Supervisor Models ────────────────────────────────────────────────────────

class SupervisorMetricsResponse(BaseModel):
    total_workers:      int
    healthy_workers:    int
    unhealthy_workers:  int
    recovered_count:     int
    last_health_check:  Optional[float] = None
    pool_uptime:        float

# ─── Route Models ────────────────────────────────────────────────────────────

class RouteRequest(BaseModel):
    prompt:     str = Field(..., description="任务描述")
    agent:     Optional[str] = Field(None, description="强制使用某 Agent")

class RouteResponse(BaseModel):
    agent:        str
    task_type:    str
    confidence:   float
    message:      str

# ─── Health / Info ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:    str  # "ok" | "degraded" | "unhealthy"
    version:   str
    uptime:    float
    workers:   int
    tasks:     dict[str, int]

# ─── Session Models ─────────────────────────────────────────────────────────

class SessionResponse(BaseModel):
    """单个会话的完整信息"""
    agent:        str
    session_id:   str
    status:       str          # "active" | "archived"
    created_at:   float
    last_used_at: float
    task_count:   int
    task_ids:      list[str]
    note:         str

class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total:     int

class SessionArchiveResponse(BaseModel):
    session_id: str
    archived:   bool
    message:    str

class SessionDeleteResponse(BaseModel):
    session_id: str
    deleted:    bool
    message:    str

class SessionStatsResponse(BaseModel):
    total:       int
    by_agent:    dict[str, int]
    by_status:   dict[str, int]

"""
Pydantic v2 data models and contracts for Alexa+ AI Agent.
Defines schemas for tasks, planning, tool calls, and conversation messages.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class PriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str = Field(..., description="Unique alphanumeric identifier for the task, e.g. TSK-101")
    title: str = Field(..., description="Clear, concise task title")
    description: Optional[str] = Field(None, description="Detailed description or context of the task")
    priority: PriorityEnum = Field(default=PriorityEnum.MEDIUM, description="Task urgency level")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status of the task")
    due_date: Optional[str] = Field(None, description="Due date or time (ISO string or readable date)")
    estimated_minutes: Optional[int] = Field(30, description="Estimated time required to complete in minutes")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


# Tool Input Schemas

class CreateTaskInput(BaseModel):
    title: str = Field(..., min_length=2, description="The name or title of the task to create")
    description: Optional[str] = Field(None, description="Optional description or details")
    priority: PriorityEnum = Field(default=PriorityEnum.MEDIUM, description="Priority: low, medium, high, or urgent")
    due_date: Optional[str] = Field(None, description="Due date/deadline, e.g., '2026-10-25' or 'tomorrow'")
    estimated_minutes: Optional[int] = Field(30, ge=5, le=1440, description="Estimated duration in minutes (5 to 1440)")


class ListTasksInput(BaseModel):
    status: Optional[TaskStatus] = Field(None, description="Filter by status: pending, in_progress, completed, cancelled")
    priority: Optional[PriorityEnum] = Field(None, description="Filter by priority: low, medium, high, urgent")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of tasks to return")


class GetTaskInput(BaseModel):
    task_id: Optional[str] = Field(None, description="Unique ID of the task, e.g., TSK-101")
    title: Optional[str] = Field(None, description="Partial or full title to search if task_id is unknown")


class UpdateTaskInput(BaseModel):
    task_id: str = Field(..., description="ID of the task to update (e.g. TSK-101)")
    title: Optional[str] = Field(None, description="New title if changing")
    description: Optional[str] = Field(None, description="New description if changing")
    priority: Optional[PriorityEnum] = Field(None, description="New priority: low, medium, high, urgent")
    due_date: Optional[str] = Field(None, description="New due date")
    status: Optional[TaskStatus] = Field(None, description="New status")
    estimated_minutes: Optional[int] = Field(None, ge=5, le=1440, description="New estimated duration in minutes")


class CompleteTaskInput(BaseModel):
    task_id: Optional[str] = Field(None, description="ID of the task to mark as completed")
    title: Optional[str] = Field(None, description="Title lookup if task ID is not provided")


class DeleteTaskInput(BaseModel):
    task_id: str = Field(..., description="ID of the task to delete")
    confirmed: bool = Field(False, description="Must be explicitly set to True after user confirmation")


class CreateDailyPlanInput(BaseModel):
    available_hours: float = Field(..., gt=0, le=24, description="Total hours available in the day (e.g. 4.0 or 8.0)")
    date: Optional[str] = Field(None, description="Date for the plan (defaults to today)")
    focus_area: Optional[str] = Field(None, description="Specific focus or objective for the day, e.g. 'Interview Prep'")


class DailyPlanItem(BaseModel):
    time_slot: str = Field(..., description="E.g., '09:00 - 10:00'")
    task_id: Optional[str] = None
    task_title: str
    priority: PriorityEnum
    duration_minutes: int
    notes: Optional[str] = None


class DailyPlan(BaseModel):
    date: str
    available_hours: float
    total_planned_minutes: int
    focus_area: Optional[str] = None
    schedule: List[DailyPlanItem] = []
    unplanned_tasks: List[str] = []
    summary: str


class GetProductivitySummaryInput(BaseModel):
    timeframe: str = Field(default="all", description="'today', 'week', or 'all'")


class ProductivitySummary(BaseModel):
    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    completion_rate_percent: float
    priority_breakdown: Dict[str, int]
    high_priority_pending: List[str]
    overdue_count: int
    insights: List[str]


# Agent Execution & Conversation Schemas

class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


class AgentResponse(BaseModel):
    response_text: str = Field(..., description="Agent natural-language answer grounded in tool execution")
    intent: str = Field("general_query", description="Identified user intent")
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    requires_confirmation: bool = Field(False, description="Whether the action is destructive and requires user confirmation")
    confirmation_prompt: Optional[str] = None
    missing_info: Optional[List[str]] = None
    model_mode: str = Field("mock_development", description="'bedrock_live' or 'mock_development'")
    conversation_id: str
    active_task_id: Optional[str] = None


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: f"msg-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}")
    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: Optional[List[ToolCallRecord]] = None
    model_mode: Optional[str] = None
    intent: Optional[str] = None

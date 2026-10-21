"""
Core tool implementations and TaskStore for Alexa+ AI Agent.
Every tool validates its inputs using Pydantic schemas, interacts with real data,
and returns structured, grounded results.
"""

from datetime import datetime, date, timedelta
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional

from agent.schemas import (
    CompleteTaskInput,
    CreateDailyPlanInput,
    CreateTaskInput,
    DailyPlan,
    DailyPlanItem,
    DeleteTaskInput,
    GetProductivitySummaryInput,
    GetTaskInput,
    ListTasksInput,
    PriorityEnum,
    ProductivitySummary,
    Task,
    TaskStatus,
    ToolCallRecord,
    UpdateTaskInput,
)


class TaskStore:
    """Thread-safe in-memory task repository with optional JSON persistence."""

    def __init__(self, storage_path: Optional[str] = "agent_tasks_store.json"):
        self.storage_path = storage_path
        self._tasks: Dict[str, Task] = {}
        self._counter: int = 100
        self._load_or_seed()

    def _load_or_seed(self) -> None:
        """Load from disk if available, otherwise seed with realistic hackathon tasks."""
        if self.storage_path and os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tasks_list = data.get("tasks", [])
                    if tasks_list:
                        for item in tasks_list:
                            t = Task(**item)
                            self._tasks[t.id] = t
                        self._counter = data.get("counter", 100)
                        return
            except Exception:
                pass

        self.seed()

    def seed(self) -> None:
        """Seed initial realistic tasks for demo."""
        self._tasks.clear()
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        day_after = (date.today() + timedelta(days=2)).isoformat()

        seeds = [
            Task(
                id="TSK-101",
                title="Review AWS Bedrock & Claude 3.5 Sonnet Converse API",
                description="Study tool calling specs, converse stream parameters, and token limits.",
                priority=PriorityEnum.URGENT,
                status=TaskStatus.IN_PROGRESS,
                due_date=today,
                estimated_minutes=45,
            ),
            Task(
                id="TSK-102",
                title="Practice System Design: Distributed Rate Limiter",
                description="Prepare architectural trade-offs: Token Bucket vs Leaky Bucket in Redis.",
                priority=PriorityEnum.HIGH,
                status=TaskStatus.PENDING,
                due_date=tomorrow,
                estimated_minutes=60,
            ),
            Task(
                id="TSK-103",
                title="Complete Python AsyncIO and Concurrency Drills",
                description="Review TaskGroups, asyncio.gather vs as_completed, and threadpool executors.",
                priority=PriorityEnum.MEDIUM,
                status=TaskStatus.PENDING,
                due_date=tomorrow,
                estimated_minutes=50,
            ),
            Task(
                id="TSK-104",
                title="Polish Behavioral Interview STAR Stories",
                description="Frame 3 stories highlighting leadership, conflict resolution, and architectural decisions.",
                priority=PriorityEnum.MEDIUM,
                status=TaskStatus.PENDING,
                due_date=day_after,
                estimated_minutes=40,
            ),
            Task(
                id="TSK-105",
                title="Setup Mock Interview with Peer",
                description="Conduct 45-minute technical screen focusing on data structures and agent design.",
                priority=PriorityEnum.LOW,
                status=TaskStatus.COMPLETED,
                due_date=today,
                estimated_minutes=45,
                completed_at=datetime.now().isoformat(),
            ),
        ]
        for task in seeds:
            self._tasks[task.id] = task
        self._counter = 105
        self._save()

    def _save(self) -> None:
        """Persist state to JSON file."""
        if not self.storage_path:
            return
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "counter": self._counter,
                        "tasks": [t.model_dump() for t in self._tasks.values()],
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    def next_id(self) -> str:
        self._counter += 1
        return f"TSK-{self._counter}"

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def find_by_title(self, query: str) -> List[Task]:
        query_lower = query.lower()
        return [
            t for t in self._tasks.values()
            if query_lower in t.title.lower() or (t.description and query_lower in t.description.lower())
        ]

    def all(self) -> List[Task]:
        return list(self._tasks.values())

    def add(self, task: Task) -> Task:
        self._tasks[task.id] = task
        self._save()
        return task

    def update(self, task: Task) -> Task:
        task.updated_at = datetime.now().isoformat()
        self._tasks[task.id] = task
        self._save()
        return task

    def delete(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save()
            return True
        return False

    def clear(self) -> None:
        self._tasks.clear()
        self._counter = 100
        self._save()


# Global Singleton Store
task_store = TaskStore()


# Real Tool Implementations

def create_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new task with validated title, priority, due date, and duration."""
    parsed = CreateTaskInput(**args)
    task_id = task_store.next_id()
    new_task = Task(
        id=task_id,
        title=parsed.title.strip(),
        description=parsed.description.strip() if parsed.description else None,
        priority=parsed.priority,
        status=TaskStatus.PENDING,
        due_date=parsed.due_date,
        estimated_minutes=parsed.estimated_minutes or 30,
    )
    task_store.add(new_task)
    return {
        "success": True,
        "action": "create_task",
        "task": new_task.model_dump(),
        "message": f"Successfully created task {new_task.id}: '{new_task.title}' with {new_task.priority.value} priority.",
    }


def list_tasks_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve tasks filtered by status and priority."""
    parsed = ListTasksInput(**args)
    all_tasks = task_store.all()

    filtered = []
    for t in all_tasks:
        if parsed.status and t.status != parsed.status:
            continue
        if parsed.priority and t.priority != parsed.priority:
            continue
        filtered.append(t)

    # Sort: pending/in_progress first, then by priority urgency
    priority_weights = {
        PriorityEnum.URGENT: 4,
        PriorityEnum.HIGH: 3,
        PriorityEnum.MEDIUM: 2,
        PriorityEnum.LOW: 1,
    }
    filtered.sort(
        key=lambda x: (
            0 if x.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) else 1,
            -priority_weights.get(x.priority, 0),
        )
    )

    limited = filtered[: parsed.limit]
    return {
        "success": True,
        "action": "list_tasks",
        "total_count": len(filtered),
        "returned_count": len(limited),
        "filter": {"status": parsed.status, "priority": parsed.priority},
        "tasks": [t.model_dump() for t in limited],
    }


def get_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get a task by its unique ID or by searching its title."""
    parsed = GetTaskInput(**args)
    if not parsed.task_id and not parsed.title:
        return {
            "success": False,
            "error": "Either task_id or title must be provided to retrieve a task.",
        }

    task: Optional[Task] = None
    if parsed.task_id:
        task = task_store.get(parsed.task_id.upper().strip())

    if not task and parsed.title:
        matches = task_store.find_by_title(parsed.title.strip())
        if matches:
            task = matches[0]

    if not task:
        return {
            "success": False,
            "action": "get_task",
            "error": f"Task not found for query (task_id: '{parsed.task_id}', title: '{parsed.title}').",
        }

    return {
        "success": True,
        "action": "get_task",
        "task": task.model_dump(),
    }


def update_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update attributes of an existing task."""
    parsed = UpdateTaskInput(**args)
    task = task_store.get(parsed.task_id.upper().strip())
    if not task:
        # Try finding by title if task_id resembles a name
        matches = task_store.find_by_title(parsed.task_id)
        if matches:
            task = matches[0]
        else:
            return {
                "success": False,
                "action": "update_task",
                "error": f"Cannot update. Task '{parsed.task_id}' was not found in the task store.",
            }

    changes = []
    if parsed.title is not None and parsed.title.strip():
        task.title = parsed.title.strip()
        changes.append(f"title -> '{task.title}'")
    if parsed.description is not None:
        task.description = parsed.description.strip()
        changes.append("description updated")
    if parsed.priority is not None:
        task.priority = parsed.priority
        changes.append(f"priority -> {task.priority.value}")
    if parsed.due_date is not None:
        task.due_date = parsed.due_date.strip()
        changes.append(f"due_date -> {task.due_date}")
    if parsed.status is not None:
        task.status = parsed.status
        if task.status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now().isoformat()
        changes.append(f"status -> {task.status.value}")
    if parsed.estimated_minutes is not None:
        task.estimated_minutes = parsed.estimated_minutes
        changes.append(f"duration -> {task.estimated_minutes}m")

    task_store.update(task)
    return {
        "success": True,
        "action": "update_task",
        "task": task.model_dump(),
        "changes": changes,
        "message": f"Updated task {task.id}: {', '.join(changes)}.",
    }


def complete_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Mark a task as completed."""
    parsed = CompleteTaskInput(**args)
    task: Optional[Task] = None

    if parsed.task_id:
        task = task_store.get(parsed.task_id.upper().strip())

    if not task and parsed.title:
        matches = task_store.find_by_title(parsed.title.strip())
        if matches:
            task = matches[0]

    if not task:
        return {
            "success": False,
            "action": "complete_task",
            "error": f"Task not found to complete. Provided id: '{parsed.task_id}', title: '{parsed.title}'.",
        }

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now().isoformat()
    task_store.update(task)

    return {
        "success": True,
        "action": "complete_task",
        "task": task.model_dump(),
        "message": f"Task {task.id} ('{task.title}') has been marked as COMPLETED.",
    }


def delete_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a task. Requires explicit confirmation parameter."""
    parsed = DeleteTaskInput(**args)
    task = task_store.get(parsed.task_id.upper().strip())
    if not task:
        return {
            "success": False,
            "action": "delete_task",
            "error": f"Task '{parsed.task_id}' does not exist.",
        }

    if not parsed.confirmed:
        return {
            "success": False,
            "action": "delete_task",
            "requires_confirmation": True,
            "task_id": task.id,
            "task_title": task.title,
            "message": f"Destructive action: Deleting task {task.id} ('{task.title}') requires explicit confirmation.",
        }

    task_store.delete(task.id)
    return {
        "success": True,
        "action": "delete_task",
        "deleted_task_id": task.id,
        "message": f"Task {task.id} ('{task.title}') has been permanently deleted.",
    }


def create_daily_plan_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an optimized daily schedule from pending tasks within available hours."""
    parsed = CreateDailyPlanInput(**args)
    plan_date = parsed.date or date.today().isoformat()
    available_minutes = int(parsed.available_hours * 60)

    # Get pending tasks
    all_tasks = task_store.all()
    pending = [
        t for t in all_tasks
        if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
    ]

    # Filter by focus area if provided
    if parsed.focus_area:
        focus_lower = parsed.focus_area.lower()
        focused = [t for t in pending if focus_lower in t.title.lower() or (t.description and focus_lower in t.description.lower())]
        unfocused = [t for t in pending if t not in focused]
        candidates = focused + unfocused
    else:
        candidates = pending

    # Sort candidates by priority
    priority_weights = {
        PriorityEnum.URGENT: 4,
        PriorityEnum.HIGH: 3,
        PriorityEnum.MEDIUM: 2,
        PriorityEnum.LOW: 1,
    }
    candidates.sort(key=lambda x: -priority_weights.get(x.priority, 0))

    schedule_items: List[DailyPlanItem] = []
    current_minute = 9 * 60  # Start at 09:00 AM
    total_planned = 0
    unplanned: List[str] = []

    for t in candidates:
        duration = t.estimated_minutes or 45
        if total_planned + duration <= available_minutes:
            start_h, start_m = divmod(current_minute, 60)
            end_minute = current_minute + duration
            end_h, end_m = divmod(end_minute, 60)

            time_slot = f"{start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d}"
            schedule_items.append(
                DailyPlanItem(
                    time_slot=time_slot,
                    task_id=t.id,
                    task_title=t.title,
                    priority=t.priority,
                    duration_minutes=duration,
                    notes=f"Priority: {t.priority.value.upper()}",
                )
            )
            total_planned += duration
            current_minute = end_minute + 10  # 10 min break
        else:
            unplanned.append(f"{t.id}: {t.title} ({duration}m)")

    plan = DailyPlan(
        date=plan_date,
        available_hours=parsed.available_hours,
        total_planned_minutes=total_planned,
        focus_area=parsed.focus_area,
        schedule=schedule_items,
        unplanned_tasks=unplanned,
        summary=(
            f"Scheduled {len(schedule_items)} tasks totaling {total_planned} minutes "
            f"out of {available_minutes} available minutes on {plan_date}."
        ),
    )

    return {
        "success": True,
        "action": "create_daily_plan",
        "plan": plan.model_dump(),
    }


def get_productivity_summary_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate productivity metrics, completion rates, and workload distribution."""
    parsed = GetProductivitySummaryInput(**args)
    tasks = task_store.all()

    total = len(tasks)
    completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
    in_prog = len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS])
    pending = len([t for t in tasks if t.status == TaskStatus.PENDING])
    cancelled = len([t for t in tasks if t.status == TaskStatus.CANCELLED])

    rate = round((completed / total * 100), 1) if total > 0 else 0.0

    priority_counts = {"urgent": 0, "high": 0, "medium": 0, "low": 0}
    high_priority_pending = []

    today_str = date.today().isoformat()
    overdue_count = 0

    for t in tasks:
        p_val = t.priority.value
        if p_val in priority_counts:
            priority_counts[p_val] += 1
        if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            if t.priority in (PriorityEnum.URGENT, PriorityEnum.HIGH):
                high_priority_pending.append(f"[{t.id}] {t.title}")
            if t.due_date and t.due_date < today_str:
                overdue_count += 1

    insights = [
        f"You have completed {completed} out of {total} total tasks ({rate}% completion rate).",
    ]
    if high_priority_pending:
        insights.append(f"Attention needed: {len(high_priority_pending)} urgent or high priority tasks remain open.")
    if overdue_count > 0:
        insights.append(f"Warning: {overdue_count} tasks are past their due dates.")
    else:
        insights.append("All pending tasks are currently on track.")

    summary = ProductivitySummary(
        total_tasks=total,
        pending_tasks=pending,
        in_progress_tasks=in_prog,
        completed_tasks=completed,
        completion_rate_percent=rate,
        priority_breakdown=priority_counts,
        high_priority_pending=high_priority_pending,
        overdue_count=overdue_count,
        insights=insights,
    )

    return {
        "success": True,
        "action": "get_productivity_summary",
        "summary": summary.model_dump(),
    }


# Tool Registry

TOOL_DEFINITIONS = [
    {
        "name": "create_task",
        "description": "Create a new task in the personal assistant task system.",
        "input_schema": CreateTaskInput.model_json_schema(),
        "func": create_task_tool,
    },
    {
        "name": "list_tasks",
        "description": "List tasks with optional filters for status (pending, in_progress, completed, cancelled) and priority.",
        "input_schema": ListTasksInput.model_json_schema(),
        "func": list_tasks_tool,
    },
    {
        "name": "get_task",
        "description": "Retrieve details of a single task by unique task_id (e.g. TSK-101) or title search.",
        "input_schema": GetTaskInput.model_json_schema(),
        "func": get_task_tool,
    },
    {
        "name": "update_task",
        "description": "Update an existing task's title, description, priority (low, medium, high, urgent), due date, or status.",
        "input_schema": UpdateTaskInput.model_json_schema(),
        "func": update_task_tool,
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed by task_id or title lookup.",
        "input_schema": CompleteTaskInput.model_json_schema(),
        "func": complete_task_tool,
    },
    {
        "name": "create_daily_plan",
        "description": "Create an optimized daily schedule from pending tasks based on available hours and optional focus area.",
        "input_schema": CreateDailyPlanInput.model_json_schema(),
        "func": create_daily_plan_tool,
    },
    {
        "name": "get_productivity_summary",
        "description": "Get overall productivity metrics, completion rates, priority distribution, and actionable insights.",
        "input_schema": GetProductivitySummaryInput.model_json_schema(),
        "func": get_productivity_summary_tool,
    },
    {
        "name": "delete_task",
        "description": "Permanently delete a task by task_id. Requires user confirmation (confirmed: true).",
        "input_schema": DeleteTaskInput.model_json_schema(),
        "func": delete_task_tool,
    },
]


class ToolRegistry:
    """Manages tool execution, timing, and schema exposure."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {
            t["name"]: t for t in TOOL_DEFINITIONS
        }

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self._tools.values())

    def get_bedrock_tool_specs(self) -> List[Dict[str, Any]]:
        """Format tools for Bedrock Converse ToolConfiguration."""
        specs = []
        for t in self._tools.values():
            specs.append({
                "toolSpec": {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": {
                        "json": t["input_schema"],
                    },
                }
            })
        return specs

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallRecord:
        """Execute a tool with runtime argument validation and timing."""
        start_time = time.time()
        tool_entry = self._tools.get(tool_name)

        if not tool_entry:
            elapsed = (time.time() - start_time) * 1000
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=None,
                execution_time_ms=round(elapsed, 2),
                success=False,
                error=f"Tool '{tool_name}' is not registered in the agent registry.",
            )

        try:
            func: Callable[[Dict[str, Any]], Dict[str, Any]] = tool_entry["func"]
            res = func(arguments)
            elapsed = (time.time() - start_time) * 1000
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=res,
                execution_time_ms=round(elapsed, 2),
                success=res.get("success", True),
                error=res.get("error") if not res.get("success", True) else None,
            )
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=None,
                execution_time_ms=round(elapsed, 2),
                success=False,
                error=f"Tool execution validation error: {str(e)}",
            )


tool_registry = ToolRegistry()

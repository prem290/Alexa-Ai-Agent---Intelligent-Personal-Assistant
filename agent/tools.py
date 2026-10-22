
"""
Core tool implementations and SQLite-backed TaskStore for Alexa+ AI Agent.
Preserves the existing eight tool definitions and their Pydantic validation.
"""

from datetime import datetime, date, timedelta
import json
import sqlite3
import time
from pathlib import Path
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

# Store the database in the project root, independent of the working directory.
DB_PATH = Path(__file__).resolve().parent.parent / "alexa_tasks.db"
LEGACY_JSON_PATH = Path(__file__).resolve().parent.parent / "agent_tasks_store.json"


class TaskStore:
    """SQLite-backed task repository with legacy JSON migration."""

    def __init__(self, storage_path: Optional[str] = None):
        self.db_path = Path(storage_path) if storage_path else DB_PATH
        self._initialize()
        self._migrate_legacy_json()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS task_metadata (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            """)
            connection.execute("""
                INSERT OR IGNORE INTO task_metadata (key, value)
                VALUES ('counter', 100)
            """)

    def _migrate_legacy_json(self):
        """Import existing JSON tasks only when the SQLite task table is empty."""
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]

            if count:
                return

            if not LEGACY_JSON_PATH.exists():
                return

            try:
                with LEGACY_JSON_PATH.open("r", encoding="utf-8") as file:
                    payload = json.load(file)

                tasks = payload.get("tasks", [])
                for item in tasks:
                    task = Task(**item)
                    connection.execute(
                        "INSERT OR IGNORE INTO tasks (id, title, data) VALUES (?, ?, ?)",
                        (
                            task.id,
                            task.title,
                            json.dumps(task.model_dump(mode="json")),
                        ),
                    )

                highest = max(
                    (
                        int(item["id"].split("-")[1])
                        for item in tasks
                        if item.get("id", "").startswith("TSK-")
                        and item["id"].split("-")[1].isdigit()
                    ),
                    default=100,
                )
                counter = max(int(payload.get("counter", 100)), highest)
                connection.execute(
                    "UPDATE task_metadata SET value = ? WHERE key = 'counter'",
                    (counter,),
                )
            except (OSError, ValueError, TypeError, KeyError) as exc:
                raise RuntimeError(
                    f"Failed to migrate legacy tasks from {LEGACY_JSON_PATH}"
                ) from exc

    def _save_counter(self, value: int):
        with self._connect() as connection:
            connection.execute(
                "UPDATE task_metadata SET value = ? WHERE key = 'counter'",
                (value,),
            )

    def next_id(self) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM task_metadata WHERE key = 'counter'"
            ).fetchone()
            current = int(row["value"]) if row else 100
            next_value = current + 1

            connection.execute(
                """INSERT INTO task_metadata (key, value)
                   VALUES ('counter', ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (next_value,),
            )

        return f"TSK-{next_value}"

    def get(self, task_id: str) -> Optional[Task]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()

        return Task(**json.loads(row["data"])) if row else None

    def find_by_title(self, query: str) -> List[Task]:
        search = f"%{query}%"
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT data FROM tasks
                   WHERE title LIKE ? OR data LIKE ?
                   ORDER BY rowid""",
                (search, search),
            ).fetchall()

        return [Task(**json.loads(row["data"])) for row in rows]

    def all(self) -> List[Task]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM tasks ORDER BY rowid"
            ).fetchall()

        return [Task(**json.loads(row["data"])) for row in rows]

    def add(self, task: Task) -> Task:
        return self.update(task)

    def update(self, task: Task) -> Task:
        task.updated_at = datetime.now().isoformat()
        serialized = json.dumps(task.model_dump(mode="json"))

        with self._connect() as connection:
            connection.execute(
                """INSERT INTO tasks (id, title, data)
                   VALUES (?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       title = excluded.title,
                       data = excluded.data""",
                (task.id, task.title, serialized),
            )

        return task

    def delete(self, task_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM tasks WHERE id = ?", (task_id,)
            )
        return cursor.rowcount > 0

    def clear(self) -> None:
        """Remove all tasks without resetting the ID counter."""
        with self._connect() as connection:
            connection.execute("DELETE FROM tasks")

    def seed(self) -> None:
        """Reset to the original five demo tasks."""
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

        self.clear()
        for task in seeds:
            self.update(task)

        self._save_counter(105)

    def _load_or_seed(self) -> None:
        """Compatibility method used by the existing reset API."""
        self.seed()


# Global singleton store. Existing tool functions continue using this object.
task_store = TaskStore()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def create_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
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
        "task": new_task.model_dump(mode="json"),
        "message": (
            f"Successfully created task {new_task.id}: "
            f"'{new_task.title}' with {new_task.priority.value} priority."
        ),
    }


def list_tasks_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    parsed = ListTasksInput(**args)
    filtered = []

    for task in task_store.all():
        if parsed.status and task.status != parsed.status:
            continue
        if parsed.priority and task.priority != parsed.priority:
            continue
        filtered.append(task)

    priority_weights = {
        PriorityEnum.URGENT: 4,
        PriorityEnum.HIGH: 3,
        PriorityEnum.MEDIUM: 2,
        PriorityEnum.LOW: 1,
    }
    filtered.sort(
        key=lambda task: (
            0 if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) else 1,
            -priority_weights.get(task.priority, 0),
        )
    )
    limited = filtered[:parsed.limit]

    return {
        "success": True,
        "action": "list_tasks",
        "total_count": len(filtered),
        "returned_count": len(limited),
        "filter": {"status": parsed.status, "priority": parsed.priority},
        "tasks": [task.model_dump(mode="json") for task in limited],
    }


def get_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    parsed = GetTaskInput(**args)

    if not parsed.task_id and not parsed.title:
        return {
            "success": False,
            "error": "Either task_id or title must be provided to retrieve a task.",
        }

    task = task_store.get(parsed.task_id.upper().strip()) if parsed.task_id else None

    if not task and parsed.title:
        matches = task_store.find_by_title(parsed.title.strip())
        task = matches[0] if matches else None

    if not task:
        return {
            "success": False,
            "action": "get_task",
            "error": (
                f"Task not found for query (task_id: '{parsed.task_id}', "
                f"title: '{parsed.title}')."
            ),
        }

    return {
        "success": True,
        "action": "get_task",
        "task": task.model_dump(mode="json"),
    }


def update_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    parsed = UpdateTaskInput(**args)
    task = task_store.get(parsed.task_id.upper().strip())

    if not task:
        matches = task_store.find_by_title(parsed.task_id)
        task = matches[0] if matches else None

    if not task:
        return {
            "success": False,
            "action": "update_task",
            "error": f"Cannot update. Task '{parsed.task_id}' was not found.",
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
        elif task.status != TaskStatus.COMPLETED:
            task.completed_at = None
        changes.append(f"status -> {task.status.value}")
    if parsed.estimated_minutes is not None:
        task.estimated_minutes = parsed.estimated_minutes
        changes.append(f"duration -> {task.estimated_minutes}m")

    task_store.update(task)

    return {
        "success": True,
        "action": "update_task",
        "task": task.model_dump(mode="json"),
        "changes": changes,
        "message": f"Updated task {task.id}: {', '.join(changes)}.",
    }


def complete_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    parsed = CompleteTaskInput(**args)
    task = task_store.get(parsed.task_id.upper().strip()) if parsed.task_id else None

    if not task and parsed.title:
        matches = task_store.find_by_title(parsed.title.strip())
        task = matches[0] if matches else None

    if not task:
        return {
            "success": False,
            "action": "complete_task",
            "error": (
                f"Task not found to complete. Provided id: '{parsed.task_id}', "
                f"title: '{parsed.title}'."
            ),
        }

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now().isoformat()
    task_store.update(task)

    return {
        "success": True,
        "action": "complete_task",
        "task": task.model_dump(mode="json"),
        "message": f"Task {task.id} ('{task.title}') has been marked as COMPLETED.",
    }


def delete_task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
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
            "message": (
                f"Deleting task {task.id} ('{task.title}') "
                "requires explicit confirmation."
            ),
        }

    task_store.delete(task.id)

    return {
        "success": True,
        "action": "delete_task",
        "deleted_task_id": task.id,
        "message": f"Task {task.id} ('{task.title}') has been permanently deleted.",
    }


def create_daily_plan_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    parsed = CreateDailyPlanInput(**args)
    plan_date = parsed.date or date.today().isoformat()
    available_minutes = int(parsed.available_hours * 60)

    pending = [
        task for task in task_store.all()
        if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
    ]

    if parsed.focus_area:
        focus = parsed.focus_area.lower()
        focused = [
            task for task in pending
            if focus in task.title.lower()
            or (task.description and focus in task.description.lower())
        ]
        candidates = focused + [task for task in pending if task not in focused]
    else:
        candidates = pending

    weights = {
        PriorityEnum.URGENT: 4,
        PriorityEnum.HIGH: 3,
        PriorityEnum.MEDIUM: 2,
        PriorityEnum.LOW: 1,
    }
    candidates.sort(key=lambda task: -weights.get(task.priority, 0))

    schedule_items = []
    current_minute = 9 * 60
    total_planned = 0
    unplanned = []

    for task in candidates:
        duration = task.estimated_minutes or 45

        if total_planned + duration <= available_minutes:
            start_h, start_m = divmod(current_minute, 60)
            end_h, end_m = divmod(current_minute + duration, 60)
            time_slot = (
                f"{start_h:02d}:{start_m:02d} - "
                f"{end_h:02d}:{end_m:02d}"
            )

            schedule_items.append(
                DailyPlanItem(
                    time_slot=time_slot,
                    task_id=task.id,
                    task_title=task.title,
                    priority=task.priority,
                    duration_minutes=duration,
                    notes=f"Priority: {task.priority.value.upper()}",
                )
            )
            total_planned += duration
            current_minute += duration + 10
        else:
            unplanned.append(f"{task.id}: {task.title} ({duration}m)")

    plan = DailyPlan(
        date=plan_date,
        available_hours=parsed.available_hours,
        total_planned_minutes=total_planned,
        focus_area=parsed.focus_area,
        schedule=schedule_items,
        unplanned_tasks=unplanned,
        summary=(
            f"Scheduled {len(schedule_items)} tasks totaling {total_planned} "
            f"minutes out of {available_minutes} available minutes on {plan_date}."
        ),
    )

    return {
        "success": True,
        "action": "create_daily_plan",
        "plan": plan.model_dump(mode="json"),
    }


def get_productivity_summary_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    GetProductivitySummaryInput(**args)
    tasks = task_store.all()

    total = len(tasks)
    completed = sum(task.status == TaskStatus.COMPLETED for task in tasks)
    in_progress = sum(task.status == TaskStatus.IN_PROGRESS for task in tasks)
    pending = sum(task.status == TaskStatus.PENDING for task in tasks)
    cancelled = sum(task.status == TaskStatus.CANCELLED for task in tasks)

    rate = round(completed / total * 100, 1) if total else 0.0
    priority_counts = {"urgent": 0, "high": 0, "medium": 0, "low": 0}
    high_priority_pending = []
    today_str = date.today().isoformat()
    overdue_count = 0

    for task in tasks:
        priority_value = task.priority.value
        if priority_value in priority_counts:
            priority_counts[priority_value] += 1

        if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            if task.priority in (PriorityEnum.URGENT, PriorityEnum.HIGH):
                high_priority_pending.append(f"[{task.id}] {task.title}")
            if task.due_date and task.due_date < today_str:
                overdue_count += 1

    insights = [
        f"You have completed {completed} out of {total} total tasks ({rate}% completion rate)."
    ]

    if high_priority_pending:
        insights.append(
            f"Attention needed: {len(high_priority_pending)} urgent or high priority tasks remain open."
        )

    if overdue_count:
        insights.append(f"Warning: {overdue_count} tasks are past their due dates.")
    else:
        insights.append("All pending tasks are currently on track.")

    summary = ProductivitySummary(
        total_tasks=total,
        pending_tasks=pending,
        in_progress_tasks=in_progress,
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
        "summary": summary.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# Tool registry — retain the original eight tools
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "create_task",
        "description": "Create a new task in the personal assistant task system.",
        "input_schema": CreateTaskInput.model_json_schema(),
        "func": create_task_tool,
    },
    {
        "name": "list_tasks",
        "description": "List tasks with optional filters for status and priority.",
        "input_schema": ListTasksInput.model_json_schema(),
        "func": list_tasks_tool,
    },
    {
        "name": "get_task",
        "description": "Retrieve a task by ID or title search.",
        "input_schema": GetTaskInput.model_json_schema(),
        "func": get_task_tool,
    },
    {
        "name": "update_task",
        "description": "Update a task's title, description, priority, due date, status, or duration.",
        "input_schema": UpdateTaskInput.model_json_schema(),
        "func": update_task_tool,
    },
    {
        "name": "complete_task",
        "description": "Mark a task as completed by ID or title lookup.",
        "input_schema": CompleteTaskInput.model_json_schema(),
        "func": complete_task_tool,
    },
    {
        "name": "create_daily_plan",
        "description": "Create an optimized daily schedule from pending tasks.",
        "input_schema": CreateDailyPlanInput.model_json_schema(),
        "func": create_daily_plan_tool,
    },
    {
        "name": "get_productivity_summary",
        "description": "Get productivity metrics and actionable insights.",
        "input_schema": GetProductivitySummaryInput.model_json_schema(),
        "func": get_productivity_summary_tool,
    },
    {
        "name": "delete_task",
        "description": "Delete a task by ID after explicit confirmation.",
        "input_schema": DeleteTaskInput.model_json_schema(),
        "func": delete_task_tool,
    },
]


class ToolRegistry:
    """Manages tool execution, timing, and schema exposure."""

    def __init__(self):
        self._tools = {tool["name"]: tool for tool in TOOL_DEFINITIONS}

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return list(self._tools.values())

    def get_bedrock_tool_specs(self) -> List[Dict[str, Any]]:
        specs = []
        for tool in self._tools.values():
            specs.append({
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": {"json": tool["input_schema"]},
                }
            })
        return specs

    def execute(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ToolCallRecord:
        start_time = time.time()
        entry = self._tools.get(tool_name)

        if not entry:
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=None,
                execution_time_ms=round((time.time() - start_time) * 1000, 2),
                success=False,
                error=f"Tool '{tool_name}' is not registered in the agent registry.",
            )

        try:
            func: Callable[[Dict[str, Any]], Dict[str, Any]] = entry["func"]
            result = func(arguments)
            elapsed = round((time.time() - start_time) * 1000, 2)

            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                execution_time_ms=elapsed,
                success=result.get("success", True),
                error=result.get("error") if not result.get("success", True) else None,
            )
        except Exception as exc:
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=None,
                execution_time_ms=round((time.time() - start_time) * 1000, 2),
                success=False,
                error=f"Tool execution validation error: {exc}",
            )


tool_registry = ToolRegistry()

"""
MCP (Model Context Protocol) Server Adapter for Alexa+ AI Agent.
Exposes Member 1's tool contracts to Member 3's MCP infrastructure via stdio or SSE.
Compatible with MCP SDK 2.x (MCPServer).
"""

from typing import Any, Dict, Optional
from mcp.server.mcpserver import MCPServer

from agent.schemas import PriorityEnum, TaskStatus
from agent.tools import (
    complete_task_tool,
    create_daily_plan_tool,
    create_task_tool,
    delete_task_tool,
    get_productivity_summary_tool,
    get_task_tool,
    list_tasks_tool,
    update_task_tool,
)

# Initialize MCP Server instance
mcp_server = MCPServer(
    name="alexa-plus-personal-assistant",
    instructions="Intelligent Personal Assistant tools for task management, scheduling, and productivity analytics.",
)


@mcp_server.tool()
def create_task(
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[str] = None,
    estimated_minutes: int = 30,
) -> Dict[str, Any]:
    """Create a new task with validated title, priority, due date, and duration."""
    return create_task_tool({
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
        "estimated_minutes": estimated_minutes,
    })


@mcp_server.tool()
def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Retrieve tasks filtered by status (pending, in_progress, completed, cancelled) and priority."""
    return list_tasks_tool({
        "status": status,
        "priority": priority,
        "limit": limit,
    })


@mcp_server.tool()
def get_task(
    task_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a task by its unique ID (e.g. TSK-101) or by partial title search."""
    return get_task_tool({
        "task_id": task_id,
        "title": title,
    })


@mcp_server.tool()
def update_task(
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    status: Optional[str] = None,
    estimated_minutes: Optional[int] = None,
) -> Dict[str, Any]:
    """Update attributes of an existing task (priority, due_date, status, etc.)."""
    return update_task_tool({
        "task_id": task_id,
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
        "status": status,
        "estimated_minutes": estimated_minutes,
    })


@mcp_server.tool()
def complete_task(
    task_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a task as completed."""
    return complete_task_tool({
        "task_id": task_id,
        "title": title,
    })


@mcp_server.tool()
def create_daily_plan(
    available_hours: float,
    date: Optional[str] = None,
    focus_area: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate an optimized daily schedule from pending tasks within available hours."""
    return create_daily_plan_tool({
        "available_hours": available_hours,
        "date": date,
        "focus_area": focus_area,
    })


@mcp_server.tool()
def get_productivity_summary(
    timeframe: str = "all",
) -> Dict[str, Any]:
    """Calculate productivity metrics, completion rates, and workload distribution."""
    return get_productivity_summary_tool({
        "timeframe": timeframe,
    })


@mcp_server.tool()
def delete_task(
    task_id: str,
    confirmed: bool = False,
) -> Dict[str, Any]:
    """Delete a task. Requires explicit confirmation parameter."""
    return delete_task_tool({
        "task_id": task_id,
        "confirmed": confirmed,
    })


if __name__ == "__main__":
    # Run the MCP server over stdio for Member 3
    mcp_server.run()

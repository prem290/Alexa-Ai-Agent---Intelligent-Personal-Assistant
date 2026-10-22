"""
FastAPI Server providing REST & SSE endpoints for the Alexa+ AI Agent.
Enables communication between the Agent Intelligence core, the React demo frontend,
and teammate integrations.
"""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.agent import alexa_agent
from agent.config import config
from agent.conversation import conversation_manager
from agent.schemas import AgentResponse
from agent.tools import (
    get_productivity_summary_tool,
    task_store,
    tool_registry,
)

app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="Backend API service for Member 1's Alexa+ AI Agent module.",
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt or follow-up instruction")
    conversation_id: Optional[str] = Field(None, description="Existing or new conversation session ID")


class DirectToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Report health and AI model configuration status."""
    return {
        "status": "healthy",
        "app": config.APP_NAME,
        "version": config.APP_VERSION,
        "is_bedrock_configured": config.is_bedrock_configured,
        "model_id": config.BEDROCK_MODEL_ID,
        "model_mode": "bedrock_live" if config.is_bedrock_configured else "mock_development",
        "aws_region": config.AWS_REGION,
        "force_dev_mode": config.FORCE_DEV_MODE,
    }


@app.post("/api/chat", response_model=AgentResponse)
def chat_endpoint(request: ChatRequest) -> AgentResponse:
    """Invoke the agent with user natural language input."""
    try:
        response = alexa_agent.invoke(
            message=request.message,
            conversation_id=request.conversation_id,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """Retrieve message history for a conversation."""
    history = alexa_agent.get_conversation_history(conversation_id)
    return {
        "conversation_id": conversation_id,
        "message_count": len(history),
        "messages": history,
    }


@app.delete("/api/conversations/{conversation_id}")
def clear_conversation(conversation_id: str) -> Dict[str, Any]:
    """Clear conversation history and state."""
    alexa_agent.clear_conversation(conversation_id)
    return {
        "success": True,
        "message": f"Conversation {conversation_id} has been reset.",
    }


@app.get("/api/tasks")
def list_all_tasks() -> Dict[str, Any]:
    """Return all current tasks from the task store."""
    tasks = task_store.all()
    return {
        "total": len(tasks),
        "tasks": [t.model_dump() for t in tasks],
    }


@app.get("/api/tools")
def list_registered_tools() -> Dict[str, Any]:
    """Expose available tool contracts and schemas."""
    tools = tool_registry.list_tools()
    return {
        "count": len(tools),
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in tools
        ],
    }


@app.post("/api/tools/execute")
def execute_tool_direct(request: DirectToolRequest) -> Dict[str, Any]:
    """Execute a tool directly by name and arguments."""
    record = tool_registry.execute(request.tool_name, request.arguments)
    return record.model_dump()


@app.get("/api/productivity")
def get_productivity() -> Dict[str, Any]:
    """Return live productivity metrics."""
    return get_productivity_summary_tool({"timeframe": "all"})


@app.post("/api/tasks/reset")
def reset_tasks() -> Dict[str, Any]:
    """Reset the task store to initial seed demo data."""
    task_store.clear()
    task_store._load_or_seed()
    return {
        "success": True,
        "message": "Task store reset to demo seed state.",
        "task_count": len(task_store.all()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent.server:app", host=config.HOST, port=config.PORT, reload=True)

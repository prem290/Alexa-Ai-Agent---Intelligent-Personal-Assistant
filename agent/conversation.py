"""
Conversation management, state tracking, and reference resolution for Alexa+ AI Agent.
Handles multi-turn dialogue, pronoun resolution, and contextual follow-ups.
"""

from datetime import datetime
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from agent.schemas import ChatMessage, DailyPlan, Task, ToolCallRecord


class ClarificationState(BaseModel):
    """Tracks pending clarification needed before tool execution."""
    goal: str
    missing_fields: List[str]
    collected_data: Dict[str, str] = Field(default_factory=dict)


class ConfirmationState(BaseModel):
    """Tracks destructive operations requiring user confirmation."""
    action: str
    target_id: str
    target_title: str
    original_args: Dict[str, str] = Field(default_factory=dict)


class ConversationSession:
    """Maintains state for a single conversation session."""

    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.messages: List[ChatMessage] = []
        self.created_at: str = datetime.now().isoformat()
        
        # Entity and context memory
        self.last_referenced_task_id: Optional[str] = None
        self.last_created_task_id: Optional[str] = None
        self.last_daily_plan: Optional[DailyPlan] = None
        self.pending_clarification: Optional[ClarificationState] = None
        self.pending_confirmation: Optional[ConfirmationState] = None

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[ToolCallRecord]] = None,
        model_mode: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            model_mode=model_mode,
            intent=intent,
        )
        self.messages.append(msg)
        return msg

    def update_task_context_from_record(self, record: ToolCallRecord) -> None:
        """Inspect tool execution record and update active entity pointers."""
        if not record.success or not record.result:
            return

        res = record.result
        if record.tool_name == "create_task" and "task" in res:
            t_id = res["task"].get("id")
            if t_id:
                self.last_created_task_id = t_id
                self.last_referenced_task_id = t_id
        elif record.tool_name in ("get_task", "update_task", "complete_task") and "task" in res:
            t_id = res["task"].get("id")
            if t_id:
                self.last_referenced_task_id = t_id
        elif record.tool_name == "create_daily_plan" and "plan" in res:
            try:
                self.last_daily_plan = DailyPlan(**res["plan"])
            except Exception:
                pass

    def resolve_task_reference(self, text: str, all_tasks: List[Task]) -> Optional[str]:
        """
        Resolve task ID from user text:
        1. Explicit ID like 'TSK-101' or 'tsk-102'.
        2. Pronouns ('it', 'that', 'this', 'the task we created', 'the interview task').
        3. Fuzzy semantic title match ('my python task', 'interview prep').
        """
        text_lower = text.lower()

        # 1. Direct explicit ID check
        id_match = re.search(r"\b(tsk-\d+)\b", text_lower)
        if id_match:
            return id_match.group(1).upper()

        # 2. Pronoun / anaphora references
        pronoun_triggers = [
            "change its priority",
            "make it",
            "move that task",
            "move it",
            "complete that task",
            "complete it",
            "delete it",
            "that task",
            "the task we created earlier",
            "the task we just made",
            "that one",
        ]
        for trigger in pronoun_triggers:
            if trigger in text_lower:
                if self.last_referenced_task_id:
                    return self.last_referenced_task_id
                if self.last_created_task_id:
                    return self.last_created_task_id

        # 3. Keyword / title matching across all tasks
        for task in all_tasks:
            # Check key tokens from task title
            tokens = [w for w in re.findall(r"\w+", task.title.lower()) if len(w) > 3]
            for token in tokens:
                if token in text_lower:
                    # Found relevant task
                    return task.id

        # 4. Fallback to last referenced if vague
        if "its " in text_lower or " it " in text_lower or text_lower.endswith(" it"):
            return self.last_referenced_task_id

        return None


class ConversationManager:
    """Global manager for conversation sessions."""

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: Optional[str] = None) -> ConversationSession:
        if not session_id:
            session_id = f"sess-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:17]}"
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(session_id)
        return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[ConversationSession]:
        return self._sessions.get(session_id)

    def clear(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]


conversation_manager = ConversationManager()

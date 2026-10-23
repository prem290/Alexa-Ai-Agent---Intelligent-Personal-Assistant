
"""
Main Agent orchestrator for Alexa+ AI Agent — Intelligent Personal Assistant.
Handles conversation context, Bedrock integration, mock responses,
and contextual development-mode fallbacks.
"""

import logging
from typing import List, Optional

from agent.bedrock_provider import BedrockAgentProvider
from agent.config import config
from agent.conversation import conversation_manager
from agent.mock_provider import MockAgentProvider
from agent.schemas import AgentResponse

logger = logging.getLogger("alexa_agent")
logging.basicConfig(level=logging.INFO)


class AlexaPlusAgent:
    """Orchestrates conversations with Bedrock and the development provider."""

    def __init__(self):
        self.mock_provider = MockAgentProvider()
        self.bedrock_provider = BedrockAgentProvider()

    @staticmethod
    def _is_generic_welcome(text: str) -> bool:
        """Identify the generic introduction returned by the mock provider."""
        normalized = (text or "").lower()
        indicators = [
            "here are a few things you can ask me",
            "i can help you plan your day",
            "show me my pending tasks",
        ]
        return sum(indicator in normalized for indicator in indicators) >= 2

    @staticmethod
    def _contextual_development_response(message: str) -> str:
        """
        Provide contextual guidance when the mock provider returns only
        its generic introduction. This is a development fallback, not an LLM.
        """
        text = message.strip().lower()

        if any(word in text for word in [
            "hello", "hi", "hey", "good morning",
            "good afternoon", "good evening",
        ]):
            return (
                "Hello! I'm Alexa+, your personal productivity assistant. "
                "I'm doing well, thanks for asking! What would you like to "
                "work on today?"
            )

        if any(phrase in text for phrase in [
            "what should i focus on",
            "today's plan",
            "todays plan",
            "plan my day",
            "focus on today",
        ]):
            return (
                "## Your plan for today\n\n"
                "1. **Review your priorities:** Identify your most urgent "
                "assignments and upcoming deadlines.\n"
                "2. **Choose one important task:** Start with the assignment "
                "that has the nearest deadline or greatest impact.\n"
                "3. **Work in focused sessions:** Try 25–50 minutes of work "
                "followed by a short break.\n"
                "4. **Review your progress:** At the end of the day, note "
                "what you completed and what needs attention tomorrow.\n\n"
                "I don't have enough verified schedule information to "
                "confirm your actual classes or deadlines. Share them and "
                "I'll help you organize a more specific plan."
            )

        if any(word in text for word in [
            "assignment", "prioritize", "prioritise", "deadline",
        ]):
            return (
                "## Let's prioritize your assignments\n\n"
                "1. **Urgent:** Start with work due today or tomorrow.\n"
                "2. **High impact:** Next, handle assignments that carry "
                "more marks or require substantial effort.\n"
                "3. **Upcoming:** Schedule work due later this week.\n"
                "4. **Quick wins:** Complete short tasks between longer "
                "focus sessions.\n\n"
                "I don't yet have verified details of every assignment. "
                "Send me your assignment names, deadlines, and estimated "
                "effort, and I'll rank them in the right order."
            )

        if any(word in text for word in [
            "pending task", "pending tasks", "my tasks", "to-do", "todo",
        ]):
            return (
                "I can help you review your pending tasks, but this "
                "development fallback cannot reliably retrieve live task "
                "records. Please open the Tasks section to see the tasks "
                "returned by your backend."
            )

        if any(word in text for word in [
            "interview", "technical preparation", "technical interview",
        ]):
            return (
                "## Technical interview preparation\n\n"
                "- Review data structures and algorithms.\n"
                "- Practice explaining time and space complexity.\n"
                "- Revise core concepts relevant to the role.\n"
                "- Prepare to explain your projects, design decisions, "
                "and challenges.\n"
                "- Solve a few timed coding problems and review mistakes.\n\n"
                "Tell me the role, interview date, and topics you're "
                "preparing for, and I'll help create a focused plan."
            )

        if any(word in text for word in [
            "productivity summary", "productivity report", "my productivity",
        ]):
            return (
                "I can help you review your productivity. Check the "
                "dashboard for the task information currently available. "
                "For an accurate summary, the backend needs to provide "
                "the current task completion and productivity metrics."
            )

        return (
            "I understand your message. I'm currently running in "
            "**development mode**, so my responses are limited and "
            "aren't generated by a live language model. Try asking me "
            "to plan your day, prioritize assignments, or prepare for "
            "a technical interview. For open-ended AI responses, configure "
            "and verify your Amazon Bedrock integration."
        )

    def invoke(
        self,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> AgentResponse:
        """Process a user message and return an AgentResponse."""

        if not message or not message.strip():
            raise ValueError("Message cannot be empty.")

        session = conversation_manager.get_or_create(conversation_id)
        session.add_message(role="user", content=message)

        response: AgentResponse
        previous_mode = "unknown"

        if config.is_bedrock_configured:
            try:
                history = [
                    {"role": item.role, "content": item.content}
                    for item in session.messages[:-1]
                ]

                logger.info(
                    "Invoking Bedrock: conversation_id=%s message_length=%d",
                    session.session_id,
                    len(message),
                )

                response = self.bedrock_provider.invoke(
                    user_message=message,
                    conversation_history=history,
                    conversation_id=session.session_id,
                )
                previous_mode = "bedrock_live"

            except Exception:
                logger.exception(
                    "Bedrock invocation failed; using development fallback."
                )
                response = self.mock_provider.invoke(message, session)
                previous_mode = "mock_development (bedrock_fallback)"

        else:
            logger.info(
                "Bedrock is not configured; using mock provider."
            )
            response = self.mock_provider.invoke(message, session)
            previous_mode = "mock_development"

        # Replace only the known generic mock introduction.
        # Do not override useful responses from either provider.
        if self._is_generic_welcome(response.response_text):
            logger.warning(
                "Generic welcome detected; applying contextual fallback."
            )
            response.response_text = self._contextual_development_response(
                message
            )

        if previous_mode == "mock_development (bedrock_fallback)":
            response.model_mode = previous_mode
        elif previous_mode == "mock_development":
            response.model_mode = previous_mode

        logger.info(
            "Agent completed: mode=%s intent=%s response_length=%d",
            response.model_mode,
            response.intent,
            len(response.response_text or ""),
        )

        session.add_message(
            role="assistant",
            content=response.response_text,
            tool_calls=response.tool_calls,
            model_mode=response.model_mode,
            intent=response.intent,
        )

        return response

    def get_conversation_history(self, conversation_id: str) -> List[dict]:
        """Return the message history for a conversation."""
        session = conversation_manager.get(conversation_id)

        if not session:
            return []

        return [item.model_dump() for item in session.messages]

    def clear_conversation(self, conversation_id: str) -> None:
        """Clear the selected conversation."""
        conversation_manager.clear(conversation_id)


# Global singleton
alexa_agent = AlexaPlusAgent()

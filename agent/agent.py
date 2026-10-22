"""
Main Agent orchestrator for Alexa+ AI Agent — Intelligent Personal Assistant.
Binds together NLU, tool selection, conversation context, Bedrock integration,
and deterministic development mode.
"""

import logging
from typing import Any, Dict, List, Optional

from agent.bedrock_provider import BedrockAgentProvider
from agent.config import config
from agent.conversation import ConversationSession, conversation_manager
from agent.mock_provider import MockAgentProvider
from agent.schemas import AgentResponse, ToolCallRecord

logger = logging.getLogger("alexa_agent")
logging.basicConfig(level=logging.INFO)


class AlexaPlusAgent:
    """
    Intelligent Personal Assistant AI Agent.
    Manages multi-turn conversation context, dynamic tool routing,
    Amazon Bedrock invocation, and deterministic development fallback.
    """

    def __init__(self):
        self.mock_provider = MockAgentProvider()
        self.bedrock_provider = BedrockAgentProvider()

    def invoke(
        self,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> AgentResponse:
        """
        Main agent invocation method.
        Accepts user message string, resolves conversation session,
        executes reasoning loop, runs validated tools, and returns grounded response.
        """
        session = conversation_manager.get_or_create(conversation_id)
        session.add_message(role="user", content=message)

        response: AgentResponse

        # Determine whether to use Bedrock or deterministic mock
        if config.is_bedrock_configured:
            try:
                history = [
                    {"role": m.role, "content": m.content}
                    for m in session.messages[:-1]
                ]
                response = self.bedrock_provider.invoke(
                    user_message=message,
                    conversation_history=history,
                    conversation_id=session.session_id,
                )
            except Exception as e:
                logger.warning(
                    "Bedrock invocation failed (%s). Falling back to deterministic dev mode.",
                    str(e),
                )
                response = self.mock_provider.invoke(message, session)
                response.model_mode = "mock_development (bedrock_fallback)"
                response.response_text = (
                    f"> *[Notice: Amazon Bedrock fallback engaged: {str(e)}]*\n\n"
                    + response.response_text
                )
        else:
            response = self.mock_provider.invoke(message, session)

        # Record assistant reply and tools in session history
        session.add_message(
            role="assistant",
            content=response.response_text,
            tool_calls=response.tool_calls,
            model_mode=response.model_mode,
            intent=response.intent,
        )

        return response

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a given session."""
        session = conversation_manager.get(conversation_id)
        if not session:
            return []
        return [m.model_dump() for m in session.messages]

    def clear_conversation(self, conversation_id: str) -> None:
        """Reset conversation session."""
        conversation_manager.clear(conversation_id)


# Global Singleton Agent
alexa_agent = AlexaPlusAgent()

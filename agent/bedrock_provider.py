"""
Amazon Bedrock Converse API provider with native tool calling.
Connects to Claude 3.5 Sonnet / Haiku on AWS Bedrock when credentials are available.
"""

from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from agent.config import config
from agent.prompts import SYSTEM_PROMPT
from agent.schemas import AgentResponse, ToolCallRecord
from agent.tools import tool_registry


class BedrockAgentProvider:
    """Invokes Amazon Bedrock Converse API with native tool calling."""

    def __init__(self):
        self.region = config.AWS_REGION
        self.model_id = config.BEDROCK_MODEL_ID
        self._client = None

    def _get_client(self):
        if self._client is None:
            kwargs = {"region_name": self.region}
            if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
                kwargs["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
                kwargs["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY
                if config.AWS_SESSION_TOKEN:
                    kwargs["aws_session_token"] = config.AWS_SESSION_TOKEN
            self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def invoke(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        conversation_id: str,
    ) -> AgentResponse:
        """Execute a conversation turn via Bedrock Converse API with tool execution loop."""
        client = self._get_client()

        # Build messages payload
        messages = []
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({
                "role": role,
                "content": [{"text": msg["content"]}]
            })
        messages.append({
            "role": "user",
            "content": [{"text": user_message}]
        })

        tool_specs = tool_registry.get_bedrock_tool_specs()
        tool_config = {
            "tools": tool_specs,
            "toolChoice": {"auto": {}}
        }

        tool_records: List[ToolCallRecord] = []
        max_turns = 5
        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            response = client.converse(
                modelId=self.model_id,
                messages=messages,
                system=[{"text": SYSTEM_PROMPT}],
                inferenceConfig={
                    "maxTokens": config.MAX_TOKENS,
                    "temperature": config.TEMPERATURE,
                },
                toolConfig=tool_config,
            )

            stop_reason = response.get("stopReason")
            output_msg = response["output"]["message"]
            messages.append(output_msg)

            # Check if model requested tool execution
            tool_requests = []
            for item in output_msg.get("content", []):
                if "toolUse" in item:
                    tool_requests.append(item["toolUse"])

            if not tool_requests or stop_reason == "end_turn":
                # Final response text
                final_text = ""
                for item in output_msg.get("content", []):
                    if "text" in item:
                        final_text += item["text"]
                
                return AgentResponse(
                    response_text=final_text.strip(),
                    intent="bedrock_reasoning",
                    tool_calls=tool_records,
                    model_mode="bedrock_live",
                    conversation_id=conversation_id,
                )

            # Execute requested tools
            tool_results = []
            for req in tool_requests:
                tool_name = req["name"]
                tool_args = req.get("input", {})
                tool_use_id = req["toolUseId"]

                record = tool_registry.execute(tool_name, tool_args)
                tool_records.append(record)

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": record.result if record.success else {"error": record.error}}],
                        "status": "success" if record.success else "error"
                    }
                })

            # Append tool results back into dialogue for grounded completion
            messages.append({
                "role": "user",
                "content": tool_results
            })

        return AgentResponse(
            response_text="Completed maximum reasoning turns.",
            intent="tool_execution",
            tool_calls=tool_records,
            model_mode="bedrock_live",
            conversation_id=conversation_id,
        )

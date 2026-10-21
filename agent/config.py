"""
Configuration management for Alexa+ AI Agent.
Supports Amazon Bedrock and deterministic development mode.
"""

from typing import Optional
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    # Application Info
    APP_NAME: str = "Alexa+ AI Agent — Intelligent Personal Assistant"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["*"]
    
    # AWS Bedrock Settings
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_SESSION_TOKEN: Optional[str] = None
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    BEDROCK_FALLBACK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # Agent Intelligence Settings
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.2
    
    # Development / Mock Mode
    # If True or if AWS credentials are not configured, use explicitly labeled deterministic mock provider
    FORCE_DEV_MODE: bool = False
    
    # Persistence
    DATA_STORE_PATH: Optional[str] = "agent_tasks_store.json"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    @property
    def is_bedrock_configured(self) -> bool:
        """Check if real AWS Bedrock credentials and configuration are available."""
        if self.FORCE_DEV_MODE:
            return False
        has_keys = bool(self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY)
        has_env_keys = bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
        return has_keys or has_env_keys


config = AgentConfig()

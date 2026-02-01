"""Configuration management for botburrow-agents."""

from __future__ import annotations

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ActivationMode(str, Enum):
    """Runner activation mode."""

    NOTIFICATION = "notification"  # Process inbox items only
    EXPLORATION = "exploration"  # Discover new content only
    HYBRID = "hybrid"  # Both notification and exploration


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="BOTBURROW_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Hub API
    hub_url: str = Field(default="http://localhost:8000", description="Botburrow Hub API URL")
    hub_api_key: str | None = Field(default=None, description="API key for Hub authentication")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")

    # R2/S3
    r2_endpoint: str = Field(default="", description="R2/S3 endpoint URL")
    r2_access_key: str = Field(default="", description="R2/S3 access key")
    r2_secret_key: str = Field(default="", description="R2/S3 secret key")
    r2_bucket: str = Field(default="agent-artifacts", description="R2/S3 bucket name")

    # Runner settings
    runner_id: str = Field(default="runner-1", description="Unique runner identifier")
    runner_mode: ActivationMode = Field(
        default=ActivationMode.HYBRID, description="Runner activation mode"
    )
    poll_interval: int = Field(default=30, description="Coordinator poll interval in seconds")
    activation_timeout: int = Field(default=300, description="Max activation time in seconds")
    max_iterations: int = Field(default=10, description="Max agentic loop iterations")

    # Coordinator settings
    min_activation_interval: int = Field(
        default=900, description="Minimum seconds between activations for staleness"
    )
    lock_ttl: int = Field(default=600, description="Redis lock TTL in seconds")

    # Sandbox settings
    sandbox_enabled: bool = Field(default=False, description="Enable Docker sandbox isolation")
    sandbox_image: str = Field(
        default="botburrow-sandbox:latest", description="Docker image for sandbox"
    )
    sandbox_memory: str = Field(default="2g", description="Sandbox memory limit")
    sandbox_cpu: str = Field(default="1.0", description="Sandbox CPU limit")

    # MCP settings
    mcp_timeout: int = Field(default=30, description="MCP server call timeout in seconds")

    # LLM defaults
    default_model: str = Field(default="claude-sonnet-4-20250514", description="Default LLM model")
    default_temperature: float = Field(default=0.7, description="Default LLM temperature")
    default_max_tokens: int = Field(default=4096, description="Default max output tokens")


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()

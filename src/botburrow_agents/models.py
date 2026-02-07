"""Data models for botburrow-agents.

Synced with agent-definitions schema v1.0.0:
https://github.com/ardenone/agent-definitions/blob/main/schemas/agent-config.schema.json
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# Agent Configuration Models


class BrainConfig(BaseModel):
    """LLM brain configuration."""

    model: str = "claude-sonnet-4-20250514"
    provider: str = "anthropic"
    temperature: float = 0.7
    max_tokens: int = 4096
    # Additional fields for native type agents
    api_base: str | None = None  # OpenAI-compatible API base URL
    api_key_env: str | None = None  # Environment variable containing API key


class ShellConfig(BaseModel):
    """Shell execution configuration."""

    enabled: bool = False
    allowed_commands: list[str] = Field(default_factory=list)
    blocked_patterns: list[str] = Field(default_factory=list)
    timeout_seconds: int = 120


class SpawningConfig(BaseModel):
    """Agent spawning configuration."""

    can_propose: bool = False
    allowed_templates: list[str] = Field(default_factory=list)


class CapabilityGrants(BaseModel):
    """Agent capability grants."""

    grants: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str | dict[str, Any]] = Field(default_factory=list)
    shell: ShellConfig = Field(default_factory=ShellConfig)
    spawning: SpawningConfig = Field(default_factory=SpawningConfig)


class DiscoveryConfig(BaseModel):
    """Discovery behavior configuration."""

    enabled: bool = False
    frequency: str = "staleness"  # staleness, hourly, daily
    respond_to_questions: bool = False
    respond_to_discussions: bool = False
    min_confidence: float = 0.7


class BehaviorLimitsConfig(BaseModel):
    """Behavior limits configuration."""

    max_daily_posts: int = 5
    max_daily_comments: int = 50
    max_responses_per_thread: int = 3
    min_interval_seconds: int = 60


class BehaviorConfig(BaseModel):
    """Agent behavior configuration."""

    respond_to_mentions: bool = True
    respond_to_replies: bool = True
    respond_to_dms: bool = True
    max_iterations: int = 10
    can_create_posts: bool = True
    # Deprecated: kept for backwards compatibility, use limits.max_daily_posts
    max_daily_posts: int = 5
    max_daily_comments: int = 50
    # New schema fields
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    limits: BehaviorLimitsConfig = Field(default_factory=BehaviorLimitsConfig)


class NetworkConfig(BaseModel):
    """Network access configuration (legacy, not in schema v1.0.0)."""

    enabled: bool = True
    allowed_hosts: list[str] = Field(default_factory=list)
    blocked_hosts: list[str] = Field(default_factory=list)


class InterestConfig(BaseModel):
    """Agent interests configuration."""

    topics: list[str] = Field(default_factory=list)
    communities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    follow_agents: list[str] = Field(default_factory=list)


class MemoryRememberConfig(BaseModel):
    """Memory remember configuration."""

    conversations_with: list[str] = Field(default_factory=list)
    projects_worked_on: bool = False
    decisions_made: bool = False
    feedback_received: bool = False


class MemoryRetrievalConfig(BaseModel):
    """Memory retrieval configuration."""

    strategy: str = "embedding_search"  # embedding_search, keyword, recent
    max_context_items: int = 10
    relevance_threshold: float = 0.7


class MemoryConfig(BaseModel):
    """Memory configuration."""

    enabled: bool = False
    remember: MemoryRememberConfig = Field(default_factory=MemoryRememberConfig)
    max_size_mb: int = 100
    retrieval: MemoryRetrievalConfig = Field(default_factory=MemoryRetrievalConfig)


class AgentConfig(BaseModel):
    """Complete agent configuration loaded from Git.

    Synced with agent-definitions schema v1.0.0:
    https://github.com/ardenone/agent-definitions/blob/main/schemas/agent-config.schema.json
    """

    # Required fields from schema
    name: str
    type: str = "claude-code"  # native, claude-code, goose, aider, custom
    brain: BrainConfig = Field(default_factory=BrainConfig)
    capabilities: CapabilityGrants = Field(default_factory=CapabilityGrants)

    # Optional fields from schema
    display_name: str | None = None
    description: str | None = None
    version: str | None = None  # Config schema version (e.g., "1.0.0")
    interests: InterestConfig = Field(default_factory=InterestConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    # Legacy fields (backwards compatibility)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    system_prompt: str = ""
    r2_path: str = ""  # Deprecated: kept for backwards compatibility
    cache_ttl: int = 300  # Seconds to cache config (default 5 min)

    def is_expired(self) -> bool:
        """Check if cached config is expired based on cache_ttl."""
        # This is checked by cache layer, not on the model
        return False


# Notification Models


class NotificationType(StrEnum):
    """Types of notifications from Hub."""

    MENTION = "mention"
    REPLY = "reply"
    FOLLOW = "follow"
    LIKE = "like"


class Notification(BaseModel):
    """Notification from Hub inbox."""

    id: str
    type: NotificationType
    post_id: str | None = None
    from_agent: str
    from_agent_name: str
    content: str
    created_at: datetime
    read: bool = False


# Task Models


class TaskType(StrEnum):
    """Types of tasks for runners."""

    INBOX = "inbox"  # Process notifications
    DISCOVERY = "discovery"  # Explore and engage


class Assignment(BaseModel):
    """Work assignment from coordinator to runner."""

    agent_id: str
    agent_name: str
    task_type: TaskType
    inbox_count: int = 0
    last_activated: datetime | None = None


# Agentic Loop Models


class ToolCall(BaseModel):
    """Tool call from LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result from tool execution."""

    output: str = ""
    error: str | None = None
    exit_code: int = 0
    skipped: bool = False
    blocked: bool = False
    fatal: bool = False


class Action(BaseModel):
    """Action from LLM reasoning."""

    is_tool_call: bool = False
    tool_calls: list[ToolCall] = Field(default_factory=list)
    content: str = ""


class LoopResult(BaseModel):
    """Result from agentic loop execution."""

    success: bool
    response: str = ""
    error: str | None = None
    iterations: int = 0
    tokens_used: int = 0
    tool_calls_made: int = 0


# Activation Result Models


class ActivationResult(BaseModel):
    """Result from agent activation."""

    agent_id: str
    agent_name: str
    success: bool
    posts_created: int = 0
    comments_created: int = 0
    notifications_processed: int = 0
    tokens_used: int = 0
    duration_seconds: float = 0.0
    error: str | None = None


# Context Models


class Message(BaseModel):
    """Chat message in context."""

    role: str  # system, user, assistant, tool
    content: str
    tool_call_id: str | None = None
    name: str | None = None


class Context(BaseModel):
    """Execution context for agentic loop."""

    messages: list[Message] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    complete: bool = False
    final_response: str = ""
    iterations: int = 0
    token_count: int = 0
    tool_history: list[dict[str, Any]] = Field(default_factory=list)
    posts_created: int = 0
    comments_created: int = 0

    def add_message(self, message: Message | dict[str, Any]) -> None:
        """Add a message to context."""
        if isinstance(message, dict):
            message = Message(**message)
        self.messages.append(message)

    def add_tool_result(self, tool_call_id: str, result: ToolResult) -> None:
        """Add tool result to context."""
        content = result.output if not result.error else f"Error: {result.error}"
        self.messages.append(Message(role="tool", content=content, tool_call_id=tool_call_id))
        self.tool_history.append({"id": tool_call_id, "result": result.model_dump()})


# Hub API Response Models


class Post(BaseModel):
    """Post from Hub."""

    id: str
    author_id: str
    author_name: str
    title: str | None = None
    content: str
    community: str | None = None
    parent_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class Thread(BaseModel):
    """Thread with posts from Hub."""

    root: Post
    comments: list[Post] = Field(default_factory=list)


class BudgetHealth(BaseModel):
    """Budget health status from Hub."""

    agent_id: str
    daily_limit: float
    daily_used: float
    monthly_limit: float
    monthly_used: float
    healthy: bool

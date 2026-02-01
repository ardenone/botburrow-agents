"""Data models for botburrow-agents."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Agent Configuration Models


class BrainConfig(BaseModel):
    """LLM brain configuration."""

    model: str = "claude-sonnet-4-20250514"
    provider: str = "anthropic"
    temperature: float = 0.7
    max_tokens: int = 4096


class CapabilityGrants(BaseModel):
    """Agent capability grants."""

    grants: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)


class BehaviorConfig(BaseModel):
    """Agent behavior configuration."""

    respond_to_mentions: bool = True
    respond_to_replies: bool = True
    max_iterations: int = 10
    can_create_posts: bool = True
    max_daily_posts: int = 5
    max_daily_comments: int = 50


class NetworkConfig(BaseModel):
    """Network access configuration."""

    enabled: bool = True
    allowed_hosts: list[str] = Field(default_factory=list)
    blocked_hosts: list[str] = Field(default_factory=list)


class AgentConfig(BaseModel):
    """Complete agent configuration loaded from R2."""

    name: str
    type: str = "claude-code"  # claude-code, goose, aider, opencode
    brain: BrainConfig = Field(default_factory=BrainConfig)
    capabilities: CapabilityGrants = Field(default_factory=CapabilityGrants)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    system_prompt: str = ""
    r2_path: str = ""


# Notification Models


class NotificationType(str, Enum):
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


class TaskType(str, Enum):
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
        self.messages.append(
            Message(role="tool", content=content, tool_call_id=tool_call_id)
        )
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

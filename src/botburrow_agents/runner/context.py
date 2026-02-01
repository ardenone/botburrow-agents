"""Context builder for agent activations.

Builds the LLM context from distributed sources:
- System prompt from Git (agent-definitions repo)
- Thread history from Hub
- Notification data
- Available tools
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from botburrow_agents.models import (
    AgentConfig,
    Context,
    Message,
    Notification,
    NotificationType,
    Post,
    Thread,
)

if TYPE_CHECKING:
    from botburrow_agents.clients.git import GitClient
    from botburrow_agents.clients.hub import HubClient

logger = structlog.get_logger(__name__)


# Core tools available to all agents (OpenClaw-style minimal set)
CORE_TOOLS = [
    {
        "name": "Read",
        "description": "Read file contents from the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "Write",
        "description": "Write content to a file in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "Edit",
        "description": "Edit a file by replacing text",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_text": {
                    "type": "string",
                    "description": "Text to find and replace",
                },
                "new_text": {
                    "type": "string",
                    "description": "Text to replace with",
                },
            },
            "required": ["file_path", "old_text", "new_text"],
        },
    },
    {
        "name": "Bash",
        "description": "Execute a bash command in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '**/*.py')",
                }
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "Grep",
        "description": "Search for text in files",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Path to search in (file or directory)",
                },
            },
            "required": ["pattern"],
        },
    },
]

# Hub-specific tools for social interaction
HUB_TOOLS = [
    {
        "name": "hub_post",
        "description": "Create a post or comment in the Hub",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Post content in markdown",
                },
                "reply_to": {
                    "type": "string",
                    "description": "Post ID to reply to (optional)",
                },
                "community": {
                    "type": "string",
                    "description": "Community to post in (e.g., 'm/general')",
                },
                "title": {
                    "type": "string",
                    "description": "Post title (for new posts, not replies)",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "hub_search",
        "description": "Search posts in the Hub",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "community": {
                    "type": "string",
                    "description": "Filter by community (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "hub_get_thread",
        "description": "Get full thread context for a post",
        "parameters": {
            "type": "object",
            "properties": {
                "post_id": {
                    "type": "string",
                    "description": "ID of the post to get thread for",
                }
            },
            "required": ["post_id"],
        },
    },
]


class ContextBuilder:
    """Builds execution context for agent activations."""

    def __init__(self, hub: HubClient, git: GitClient) -> None:
        self.hub = hub
        self.git = git

    async def build_for_notification(
        self,
        agent: AgentConfig,
        notification: Notification,
    ) -> Context:
        """Build context for processing a notification.

        Args:
            agent: Agent configuration
            notification: The notification to process

        Returns:
            Context ready for agentic loop
        """
        context = Context()

        # 1. System prompt
        context.add_message(Message(role="system", content=agent.system_prompt))

        # 2. Thread history (if notification has a post)
        if notification.post_id:
            thread = await self.hub.get_thread(notification.post_id)
            thread_text = self._format_thread(thread)
            context.add_message(
                Message(
                    role="user",
                    content=f"## Thread Context\n\n{thread_text}",
                )
            )

        # 3. The notification itself
        notification_text = self._format_notification(notification)
        context.add_message(
            Message(
                role="user",
                content=f"## New Notification\n\n{notification_text}\n\n"
                f"Please respond appropriately. If no response is needed, "
                f"say 'No response needed.'",
            )
        )

        # 4. Available tools
        context.tools = self._get_tools(agent)

        return context

    async def build_for_exploration(
        self,
        agent: AgentConfig,
    ) -> Context:
        """Build context for exploration/discovery mode.

        Args:
            agent: Agent configuration

        Returns:
            Context ready for agentic loop
        """
        context = Context()

        # 1. System prompt
        context.add_message(Message(role="system", content=agent.system_prompt))

        # 2. Exploration instructions
        exploration_prompt = self._build_exploration_prompt(agent)
        context.add_message(Message(role="user", content=exploration_prompt))

        # 3. Feed of relevant posts
        feed = await self.hub.get_discovery_feed(
            communities=agent.behavior.can_create_posts
            and ["m/general"]
            or [],
            keywords=[],  # Could extract from agent interests
            exclude_responded=True,
            limit=10,
        )

        if feed:
            feed_text = self._format_feed(feed)
            context.add_message(
                Message(
                    role="user",
                    content=f"## Recent Posts\n\n{feed_text}",
                )
            )
        else:
            context.add_message(
                Message(
                    role="user",
                    content="No new posts found that match your interests.",
                )
            )

        # 4. Available tools
        context.tools = self._get_tools(agent)

        return context

    def _format_thread(self, thread: Thread) -> str:
        """Format a thread for context."""
        lines = []

        # Root post
        root = thread.root
        lines.append(f"**{root.author_name}** ({root.created_at.strftime('%Y-%m-%d %H:%M')}):")
        if root.title:
            lines.append(f"### {root.title}")
        lines.append(root.content)
        lines.append("")

        # Comments
        for comment in thread.comments:
            lines.append(f"> **{comment.author_name}** ({comment.created_at.strftime('%H:%M')}):")
            lines.append(f"> {comment.content}")
            lines.append("")

        return "\n".join(lines)

    def _format_notification(self, notification: Notification) -> str:
        """Format a notification for context."""
        type_labels = {
            NotificationType.MENTION: "You were mentioned",
            NotificationType.REPLY: "Someone replied to you",
            NotificationType.FOLLOW: "Someone followed you",
            NotificationType.LIKE: "Someone liked your post",
        }

        lines = [
            f"**Type**: {type_labels.get(notification.type, notification.type.value)}",
            f"**From**: {notification.from_agent_name}",
            f"**Time**: {notification.created_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "**Content**:",
            notification.content,
        ]

        return "\n".join(lines)

    def _format_feed(self, posts: list[Post]) -> str:
        """Format a feed of posts for context."""
        lines = []
        for i, post in enumerate(posts, 1):
            lines.append(f"### {i}. {post.title or '(No title)'}")
            lines.append(f"**By**: {post.author_name} in {post.community or 'general'}")
            lines.append(f"**ID**: {post.id}")
            lines.append("")
            # Truncate long content
            content = post.content[:500] + "..." if len(post.content) > 500 else post.content
            lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _build_exploration_prompt(self, agent: AgentConfig) -> str:
        """Build exploration mode instructions."""
        return f"""You are {agent.name}, exploring the Hub to find interesting content to engage with.

## Your Role
You're browsing for posts you can meaningfully contribute to based on your expertise and interests.

## Guidelines
- Only respond if you have genuine value to add
- Don't respond to posts that already have good answers
- Prefer questions over general discussions
- Stay within your area of expertise
- Be helpful and constructive

## What to Do
1. Review the recent posts below
2. If you find one worth responding to, use the `hub_post` tool to reply
3. If nothing is worth responding to, simply say "Nothing to engage with right now."

## Your Limits
- Maximum {agent.behavior.max_daily_posts} new posts per day
- Maximum {agent.behavior.max_daily_comments} comments per day
"""

    def _get_tools(self, agent: AgentConfig) -> list[dict[str, Any]]:
        """Get available tools for an agent."""
        tools = []

        # Always include hub tools
        tools.extend(HUB_TOOLS)

        # Add core tools based on agent type
        if agent.type in ["claude-code", "goose", "aider", "opencode"]:
            tools.extend(CORE_TOOLS)

        # Add MCP tools based on grants
        for grant in agent.capabilities.grants:
            mcp_tools = self._grant_to_tools(grant)
            tools.extend(mcp_tools)

        return tools

    def _grant_to_tools(self, grant: str) -> list[dict[str, Any]]:
        """Convert a capability grant to tool definitions."""
        # Parse grant format: service:scope:resource
        parts = grant.split(":")

        if len(parts) < 2:
            return []

        service = parts[0]
        scope = parts[1] if len(parts) > 1 else "*"

        if service == "github":
            return self._github_tools(scope)
        elif service == "aws":
            return self._aws_tools(parts)
        elif service == "postgres":
            return self._postgres_tools(parts)

        return []

    def _github_tools(self, scope: str) -> list[dict[str, Any]]:
        """Get GitHub MCP tools based on scope."""
        tools = []

        if scope in ["read", "*"]:
            tools.append({
                "name": "mcp_github_get_file",
                "description": "Get file contents from a GitHub repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "Repository (owner/repo)"},
                        "path": {"type": "string", "description": "File path"},
                    },
                    "required": ["repo", "path"],
                },
            })
            tools.append({
                "name": "mcp_github_list_prs",
                "description": "List pull requests in a repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "state": {"type": "string", "enum": ["open", "closed", "all"]},
                    },
                    "required": ["repo"],
                },
            })

        if scope in ["write", "*"]:
            tools.append({
                "name": "mcp_github_create_pr",
                "description": "Create a pull request",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "head": {"type": "string"},
                        "base": {"type": "string"},
                    },
                    "required": ["repo", "title", "head", "base"],
                },
            })
            tools.append({
                "name": "mcp_github_create_issue",
                "description": "Create an issue",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["repo", "title"],
                },
            })

        return tools

    def _aws_tools(self, parts: list[str]) -> list[dict[str, Any]]:
        """Get AWS MCP tools based on grant."""
        if len(parts) < 3:
            return []

        service = parts[1]  # e.g., "s3"
        scope = parts[2]  # e.g., "read"

        if service == "s3":
            tools = []
            if scope in ["read", "*"]:
                tools.append({
                    "name": "mcp_aws_s3_get",
                    "description": "Get object from S3",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string"},
                            "key": {"type": "string"},
                        },
                        "required": ["bucket", "key"],
                    },
                })
            if scope in ["write", "*"]:
                tools.append({
                    "name": "mcp_aws_s3_put",
                    "description": "Put object to S3",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bucket": {"type": "string"},
                            "key": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["bucket", "key", "content"],
                    },
                })
            return tools

        return []

    def _postgres_tools(self, parts: list[str]) -> list[dict[str, Any]]:
        """Get PostgreSQL MCP tools based on grant."""
        if len(parts) < 3:
            return []

        database = parts[1]
        scope = parts[2]

        tools = []
        if scope in ["read", "*"]:
            tools.append({
                "name": f"mcp_postgres_{database}_query",
                "description": f"Execute a SELECT query on {database}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL SELECT query"},
                    },
                    "required": ["query"],
                },
            })

        return tools

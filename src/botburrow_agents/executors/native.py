"""Native executor - Direct LLM API calls without external CLI.

Implements ADR-030: Native orchestration type for headless CLI requirement.
Uses AgentLoop internally to execute agentic reasoning with direct API calls.

Advantages:
- No external CLI dependency (lighter containers, faster startup)
- Direct LLM API calls (works with any OpenAI-compatible endpoint)
- Perfect for free API sprints (spin up many agents when providers offer free credits)
- Model-agnostic (easily switch between providers/models)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from botburrow_agents.config import Settings
from botburrow_agents.executors.base import BaseExecutor, ExecutorResult
from botburrow_agents.models import AgentConfig

if TYPE_CHECKING:
    from botburrow_agents.clients.hub import HubClient

logger = structlog.get_logger(__name__)


class NativeExecutor(BaseExecutor):
    """Native executor using direct LLM API calls.

    This executor implements an internal OpenClaw-style agentic loop:
    1. LLM reasoning (direct API calls to Anthropic/OpenAI/etc.)
    2. Tool execution (via sandbox and MCP)
    3. Feed results back
    4. Iterate until complete or max iterations

    Unlike CLI executors, this has no external dependencies and can work
    with any OpenAI-compatible API endpoint.
    """

    @property
    def name(self) -> str:
        return "native"

    @property
    def runtime_command(self) -> list[str]:
        # No external CLI required
        return ["python", "-c", "pass"]

    def is_available(self) -> bool:
        """Native executor is always available (no external CLI required)."""
        return True

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__(settings)
        # Lazy import to avoid circular dependencies
        self._hub_client: HubClient | None = None
        self._loop: Any = None
        self._sandbox: Any = None

    async def build_command(
        self,
        _agent: AgentConfig,
        _prompt: str,
        _workspace: Path,
    ) -> list[str]:
        """Native executor doesn't use external commands."""
        return ["internal"]

    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        """Build environment for native execution.

        Sets up API keys for direct LLM calls.
        """
        env = self._get_base_env()

        # Anthropic API key
        if "anthropic_api_key" in credentials:
            env["ANTHROPIC_API_KEY"] = credentials["anthropic_api_key"]

        # OpenAI API key
        if "openai_api_key" in credentials:
            env["OPENAI_API_KEY"] = credentials["openai_api_key"]

        # Custom API base URL and key (for alternative providers)
        brain_api_base = agent.brain.model.split()[0] if " " in agent.brain.model else None
        if brain_api_base:
            env["NATIVE_API_BASE"] = brain_api_base

        api_key_env = agent.brain.provider.lower() + "_api_key"
        if api_key_env in credentials:
            env[api_key_env.upper()] = credentials[api_key_env]

        return env

    async def run(
        self,
        agent: AgentConfig,
        prompt: str,
        _workspace: Path,
        _credentials: dict[str, str],
        timeout: int | None = None,
    ) -> ExecutorResult:
        """Execute using native agentic loop.

        Args:
            agent: Agent configuration
            prompt: The prompt/task
            workspace: Working directory
            credentials: API keys
            timeout: Execution timeout

        Returns:
            ExecutorResult with output and metrics
        """
        timeout = timeout or self.settings.activation_timeout

        logger.info(
            "native_executor_starting",
            agent=agent.name,
            model=agent.brain.model,
            provider=agent.brain.provider,
        )

        try:
            # Lazy imports to avoid circular dependencies
            from botburrow_agents.clients.hub import HubClient
            from botburrow_agents.clients.redis import RedisClient
            from botburrow_agents.mcp.manager import MCPManager
            from botburrow_agents.models import Context, Message
            from botburrow_agents.runner.loop import AgentLoop
            from botburrow_agents.runner.sandbox import Sandbox

            # Initialize components
            if self._hub_client is None:
                self._hub_client = HubClient(self.settings)
            if self._sandbox is None:
                self._sandbox = Sandbox(agent, self.settings)
                await self._sandbox.start()

            # Build context with the prompt
            context = Context()

            # Add system prompt
            if agent.system_prompt:
                context.add_message(
                    Message(
                        role="system",
                        content=agent.system_prompt,
                    )
                )
            else:
                # Default system prompt for native execution
                context.add_message(
                    Message(
                        role="system",
                        content=self._get_default_system_prompt(agent),
                    )
                )

            # Add user message with the prompt
            context.add_message(
                Message(
                    role="user",
                    content=prompt,
                )
            )

            # Add available tools
            context.tools = self._get_available_tools(agent)

            # Create and run agentic loop
            redis = RedisClient(self.settings)
            await redis.connect()

            try:
                mcp_manager = MCPManager(self.settings)
                loop = AgentLoop(self._hub_client, self._sandbox, mcp_manager, self.settings)

                # Run the loop
                result = await loop.run(agent, context)

                await mcp_manager.close()
            finally:
                await redis.close()

            if result.success:
                logger.info(
                    "native_executor_completed",
                    agent=agent.name,
                    iterations=result.iterations,
                    tokens_used=result.tokens_used,
                    tool_calls=result.tool_calls_made,
                )

                return ExecutorResult(
                    success=True,
                    output=result.response,
                    tokens_input=result.tokens_used // 2,  # Approximate
                    tokens_output=result.tokens_used // 2,
                    artifacts={
                        "iterations": result.iterations,
                        "tool_calls": result.tool_calls_made,
                    },
                )
            else:
                logger.warning(
                    "native_executor_failed",
                    agent=agent.name,
                    error=result.error,
                )
                return ExecutorResult(
                    success=False,
                    output=result.response,
                    error=result.error,
                    tokens_input=result.tokens_used // 2,
                    tokens_output=result.tokens_used // 2,
                )

        except Exception as e:
            logger.error(
                "native_executor_error",
                agent=agent.name,
                error=str(e),
            )
            return ExecutorResult(
                success=False,
                error=str(e),
            )
        finally:
            # Clean up sandbox
            if self._sandbox:
                await self._sandbox.stop()
                self._sandbox = None

    def _get_default_system_prompt(self, agent: AgentConfig) -> str:
        """Get default system prompt for native execution."""
        capabilities = []
        if agent.capabilities.grants:
            capabilities.append(f"grants: {', '.join(agent.capabilities.grants)}")
        if agent.capabilities.skills:
            capabilities.append(f"skills: {', '.join(agent.capabilities.skills)}")

        caps_text = "\n  ".join(capabilities) if capabilities else "  (none)"

        return f"""You are {agent.name}, an autonomous AI agent participating in the Botburrow Hub.

## Your Capabilities
{caps_text}

## Available Tools
- hub_post: Create posts or comments on the Hub
- hub_search: Search for content on the Hub
- hub_get_thread: Get full thread context
- Read, Write, Edit: File operations
- Bash: Execute shell commands
- Glob, Grep: Search for files and content

## Instructions
- Be helpful and concise in your responses
- Use tools when needed to complete tasks
- When posting to the Hub, use hub_post with clear, well-formatted content
- Respect the conversation context and respond appropriately
- If you need more information, use the available tools to find it

## Model Configuration
- Provider: {agent.brain.provider}
- Model: {agent.brain.model}
- Temperature: {agent.brain.temperature}
"""

    def _get_available_tools(self, agent: AgentConfig) -> list[dict[str, Any]]:
        """Get list of tools available to the agent."""
        tools = [
            {
                "name": "hub_post",
                "description": "Create a new post or comment on the Hub",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The content to post",
                        },
                        "reply_to": {
                            "type": "string",
                            "description": "Post ID to reply to (optional, for comments)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Title for new posts (optional)",
                        },
                        "community": {
                            "type": "string",
                            "description": "Community to post in (optional)",
                        },
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "hub_search",
                "description": "Search for posts on the Hub",
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
                            "description": "Maximum results (default 10)",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "hub_get_thread",
                "description": "Get full thread with all comments",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "string",
                            "description": "Post ID to fetch",
                        },
                    },
                    "required": ["post_id"],
                },
            },
        ]

        # Add file/system tools if network access is enabled
        if agent.network.enabled:
            tools.extend(
                [
                    {
                        "name": "Read",
                        "description": "Read file contents",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to file to read",
                                },
                            },
                            "required": ["file_path"],
                        },
                    },
                    {
                        "name": "Write",
                        "description": "Write or create a file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to file to write",
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Content to write",
                                },
                            },
                            "required": ["file_path", "content"],
                        },
                    },
                    {
                        "name": "Edit",
                        "description": "Edit an existing file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to file to edit",
                                },
                                "old_text": {
                                    "type": "string",
                                    "description": "Text to replace",
                                },
                                "new_text": {
                                    "type": "string",
                                    "description": "New text",
                                },
                            },
                            "required": ["file_path", "old_text", "new_text"],
                        },
                    },
                    {
                        "name": "Bash",
                        "description": "Execute shell commands",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "Command to execute",
                                },
                            },
                            "required": ["command"],
                        },
                    },
                    {
                        "name": "Glob",
                        "description": "Find files by pattern",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "pattern": {
                                    "type": "string",
                                    "description": "Glob pattern (e.g., **/*.py)",
                                },
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
                                    "description": "Regex pattern to search for",
                                },
                                "path": {
                                    "type": "string",
                                    "description": "Directory to search in (optional)",
                                },
                            },
                            "required": ["pattern"],
                        },
                    },
                ]
            )

        return tools

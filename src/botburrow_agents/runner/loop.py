"""Agentic loop implementation.

Core reasoning + tool use cycle based on OpenClaw pattern:
1. LLM reasoning
2. Tool call (if any)
3. Feed result back
4. Iterate or complete
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import (
    Action,
    AgentConfig,
    Context,
    LoopResult,
    Message,
    ToolCall,
    ToolResult,
)

if TYPE_CHECKING:
    from botburrow_agents.clients.hub import HubClient
    from botburrow_agents.mcp.manager import MCPManager
    from botburrow_agents.runner.sandbox import Sandbox

logger = structlog.get_logger(__name__)


class AgentLoop:
    """Execute agent reasoning with tools.

    The agentic loop:
    1. Send context to LLM
    2. If LLM returns tool calls, execute them
    3. Add results to context
    4. Repeat until LLM returns text response or max iterations
    """

    def __init__(
        self,
        hub: HubClient,
        sandbox: Sandbox,
        mcp_manager: MCPManager | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.hub = hub
        self.sandbox = sandbox
        self.mcp_manager = mcp_manager
        self.settings = settings or get_settings()
        self._anthropic: AsyncAnthropic | None = None
        self._openai: AsyncOpenAI | None = None

    async def run(
        self,
        agent: AgentConfig,
        context: Context,
    ) -> LoopResult:
        """Execute the agentic loop.

        Args:
            agent: Agent configuration
            context: Initial context with system prompt and messages

        Returns:
            LoopResult with success status, response, and metrics
        """
        max_iterations = agent.behavior.max_iterations or self.settings.max_iterations
        tool_calls_made = 0

        logger.info(
            "loop_starting",
            agent_name=agent.name,
            max_iterations=max_iterations,
        )

        while context.iterations < max_iterations:
            context.iterations += 1

            # 1. LLM reasoning
            try:
                action = await self._reason(agent, context)
            except Exception as e:
                logger.error("reasoning_error", error=str(e))
                return LoopResult(
                    success=False,
                    error=f"LLM error: {e}",
                    iterations=context.iterations,
                    tokens_used=context.token_count,
                )

            # 2. Check for tool calls
            if action.is_tool_call:
                for tool_call in action.tool_calls:
                    tool_calls_made += 1
                    logger.debug(
                        "executing_tool",
                        tool=tool_call.name,
                        iteration=context.iterations,
                    )

                    # Execute tool
                    result = await self._execute_tool(agent, tool_call)

                    # Add result to context
                    context.add_tool_result(tool_call.id, result)

                    # Check for fatal error
                    if result.fatal:
                        return LoopResult(
                            success=False,
                            error=f"Fatal tool error: {result.error}",
                            iterations=context.iterations,
                            tokens_used=context.token_count,
                            tool_calls_made=tool_calls_made,
                        )

                # Add assistant message with tool calls
                context.add_message(
                    Message(
                        role="assistant",
                        content=action.content or "",
                    )
                )

            else:
                # No tool calls = final response
                logger.info(
                    "loop_completed",
                    agent_name=agent.name,
                    iterations=context.iterations,
                    tool_calls=tool_calls_made,
                )
                return LoopResult(
                    success=True,
                    response=action.content,
                    iterations=context.iterations,
                    tokens_used=context.token_count,
                    tool_calls_made=tool_calls_made,
                )

        # Hit iteration limit
        logger.warning(
            "loop_exceeded_iterations",
            agent_name=agent.name,
            max_iterations=max_iterations,
        )
        return LoopResult(
            success=False,
            error="Exceeded maximum iterations",
            iterations=context.iterations,
            tokens_used=context.token_count,
            tool_calls_made=tool_calls_made,
        )

    async def _reason(
        self,
        agent: AgentConfig,
        context: Context,
    ) -> Action:
        """Send context to LLM and get next action."""
        provider = agent.brain.provider.lower()

        if provider == "anthropic":
            return await self._reason_anthropic(agent, context)
        elif provider == "openai":
            return await self._reason_openai(agent, context)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    async def _reason_anthropic(
        self,
        agent: AgentConfig,
        context: Context,
    ) -> Action:
        """Reasoning with Anthropic Claude."""
        if self._anthropic is None:
            self._anthropic = AsyncAnthropic()

        # Convert messages to Anthropic format
        messages = []
        system_prompt = ""

        for msg in context.messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {  # type: ignore[dict-item]
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )

        # Convert tools to Anthropic format
        tools = []
        for tool in context.tools:
            tools.append(
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["parameters"],
                }
            )

        # Make API call
        response = await self._anthropic.messages.create(
            model=agent.brain.model,
            max_tokens=agent.brain.max_tokens,
            temperature=agent.brain.temperature,
            system=system_prompt,
            messages=messages,  # type: ignore[arg-type]
            tools=tools if tools else None,  # type: ignore[arg-type]
        )

        # Update token count
        context.token_count += response.usage.input_tokens + response.usage.output_tokens

        # Parse response
        tool_calls = []
        text_content = ""

        for block in response.content:
            if block.type == "text":
                text_content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        if tool_calls:
            return Action(is_tool_call=True, tool_calls=tool_calls, content=text_content)
        else:
            return Action(is_tool_call=False, content=text_content)

    async def _reason_openai(
        self,
        agent: AgentConfig,
        context: Context,
    ) -> Action:
        """Reasoning with OpenAI."""
        if self._openai is None:
            self._openai = AsyncOpenAI()

        # Convert messages to OpenAI format
        messages = []
        for msg in context.messages:
            if msg.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
            else:
                messages.append({"role": msg.role, "content": msg.content})

        # Convert tools to OpenAI format
        tools = []
        for tool in context.tools:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"],
                    },
                }
            )

        # Make API call
        response = await self._openai.chat.completions.create(
            model=agent.brain.model,
            max_tokens=agent.brain.max_tokens,
            temperature=agent.brain.temperature,
            messages=messages,  # type: ignore[arg-type]
            tools=tools if tools else None,  # type: ignore[arg-type]
        )

        # Update token count
        if response.usage:
            context.token_count += response.usage.total_tokens

        # Parse response
        choice = response.choices[0]
        message = choice.message

        if message.tool_calls:
            tool_calls = []
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,  # type: ignore[union-attr]
                        arguments=json.loads(tc.function.arguments),  # type: ignore[union-attr]
                    )
                )
            return Action(
                is_tool_call=True,
                tool_calls=tool_calls,
                content=message.content or "",
            )
        else:
            return Action(is_tool_call=False, content=message.content or "")

    async def _execute_tool(
        self,
        agent: AgentConfig,
        tool_call: ToolCall,
    ) -> ToolResult:
        """Execute a tool call."""
        tool_name = tool_call.name
        args = tool_call.arguments

        try:
            # Hub tools
            if tool_name == "hub_post":
                return await self._hub_post(agent, args)
            elif tool_name == "hub_search":
                return await self._hub_search(args)
            elif tool_name == "hub_get_thread":
                return await self._hub_get_thread(args)

            # Core tools (executed in sandbox)
            elif tool_name in ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]:
                return await self.sandbox.execute_tool(tool_name, args)

            # MCP tools (executed via MCPManager)
            elif tool_name.startswith("mcp_"):
                return await self._execute_mcp_tool(tool_name, args)

            else:
                return ToolResult(error=f"Unknown tool: {tool_name}")

        except Exception as e:
            logger.error("tool_execution_error", tool=tool_name, error=str(e))
            return ToolResult(error=str(e))

    async def _hub_post(
        self,
        agent: AgentConfig,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute hub_post tool."""
        content = args.get("content", "")
        reply_to = args.get("reply_to")
        community = args.get("community")
        title = args.get("title")

        try:
            if reply_to:
                post = await self.hub.create_comment(
                    agent_id=agent.name,
                    post_id=reply_to,
                    content=content,
                )
                return ToolResult(output=f"Comment posted successfully. ID: {post.id}")
            else:
                post = await self.hub.create_post(
                    agent_id=agent.name,
                    content=content,
                    title=title,
                    community=community,
                )
                return ToolResult(output=f"Post created successfully. ID: {post.id}")
        except Exception as e:
            return ToolResult(error=f"Failed to post: {e}")

    async def _hub_search(self, args: dict[str, Any]) -> ToolResult:
        """Execute hub_search tool."""
        query = args.get("query", "")
        community = args.get("community")
        limit = args.get("limit", 10)

        try:
            posts = await self.hub.search(
                query=query,
                community=community,
                limit=limit,
            )
            if not posts:
                return ToolResult(output="No results found.")

            results = []
            for post in posts:
                results.append(
                    f"- **{post.title or '(No title)'}** by {post.author_name}\n"
                    f"  ID: {post.id}\n"
                    f"  {post.content[:200]}..."
                )
            return ToolResult(output="\n\n".join(results))
        except Exception as e:
            return ToolResult(error=f"Search failed: {e}")

    async def _hub_get_thread(self, args: dict[str, Any]) -> ToolResult:
        """Execute hub_get_thread tool."""
        post_id = args.get("post_id", "")

        try:
            thread = await self.hub.get_thread(post_id)
            lines = [
                f"**{thread.root.author_name}**: {thread.root.content}",
                "",
                "Comments:",
            ]
            for comment in thread.comments:
                lines.append(f"> **{comment.author_name}**: {comment.content}")

            return ToolResult(output="\n".join(lines))
        except Exception as e:
            return ToolResult(error=f"Failed to get thread: {e}")

    async def _execute_mcp_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute an MCP server tool via MCPManager.

        Args:
            tool_name: Full tool name (e.g., mcp_github_create_pr)
            args: Tool arguments

        Returns:
            ToolResult with output or error
        """
        if self.mcp_manager is None:
            return ToolResult(error="MCPManager not available")

        try:
            # Call tool via MCPManager
            result = await self.mcp_manager.call_tool_by_name(tool_name, args)

            # Convert MCP result to ToolResult
            if result.get("error"):
                return ToolResult(error=str(result["error"]))

            # Format output
            output = result.get("result", {})
            if isinstance(output, dict):
                # Format dict output
                formatted = json.dumps(output, indent=2)
                return ToolResult(output=formatted)
            else:
                return ToolResult(output=str(output))

        except ValueError as e:
            # Invalid tool name format
            return ToolResult(error=str(e))
        except RuntimeError as e:
            # Server not running or initialized
            return ToolResult(error=f"MCP server error: {e}")
        except Exception as e:
            logger.error("mcp_tool_error", tool=tool_name, error=str(e))
            return ToolResult(error=f"MCP tool failed: {e}")

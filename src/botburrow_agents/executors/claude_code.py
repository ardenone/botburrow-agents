"""Claude Code executor.

Executes tasks using the Claude Code CLI (npx @anthropic/claude-code).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import structlog

from botburrow_agents.executors.base import BaseExecutor
from botburrow_agents.models import AgentConfig

logger = structlog.get_logger(__name__)


class ClaudeCodeExecutor(BaseExecutor):
    """Executor for Claude Code CLI.

    Claude Code is Anthropic's official coding assistant CLI.
    Supports:
    - Non-interactive (--print) mode
    - Custom system prompts (--system-prompt)
    - Allowed tools configuration
    - MCP server integration
    """

    @property
    def name(self) -> str:
        return "claude-code"

    @property
    def runtime_command(self) -> list[str]:
        return ["npx", "@anthropic/claude-code"]

    def is_available(self) -> bool:
        """Check if Claude Code CLI is available via npx."""
        return shutil.which("npx") is not None

    async def build_command(
        self,
        agent: AgentConfig,
        prompt: str,
        workspace: Path,
    ) -> list[str]:
        """Build Claude Code command.

        Args:
            agent: Agent configuration
            prompt: The prompt/task
            workspace: Working directory

        Returns:
            Command list
        """
        cmd = list(self.runtime_command)

        # Non-interactive mode
        cmd.extend(["--print"])

        # Model selection
        if agent.brain.model:
            cmd.extend(["--model", agent.brain.model])

        # System prompt (if not using default)
        if agent.system_prompt:
            # Write system prompt to temp file
            prompt_file = workspace / ".claude-system-prompt.md"
            prompt_file.write_text(agent.system_prompt)
            cmd.extend(["--system-prompt", str(prompt_file)])

        # Max tokens
        if agent.brain.max_tokens:
            cmd.extend(["--max-tokens", str(agent.brain.max_tokens)])

        # Allowed tools
        allowed_tools = self._get_allowed_tools(agent)
        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        # The prompt/message
        cmd.extend(["--message", prompt])

        return cmd

    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        """Build environment for Claude Code.

        Args:
            agent: Agent configuration
            credentials: API keys

        Returns:
            Environment variables
        """
        env = self._get_base_env()

        # Anthropic API key
        if "anthropic_api_key" in credentials:
            env["ANTHROPIC_API_KEY"] = credentials["anthropic_api_key"]

        # Disable telemetry for headless operation
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

        # MCP configuration (if any MCP servers)
        if agent.capabilities.mcp_servers:
            mcp_config = self._build_mcp_config(agent, credentials)
            if mcp_config:
                env["CLAUDE_CODE_MCP_CONFIG"] = json.dumps(mcp_config)

        return env

    def _get_allowed_tools(self, _agent: AgentConfig) -> list[str]:
        """Get list of allowed tools for the agent."""
        # Default Claude Code tools
        default_tools = [
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            "Task",
            "WebFetch",
        ]

        # Filter based on agent settings if needed
        # For now, return all defaults
        return default_tools

    def _build_mcp_config(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Build MCP server configuration.

        Returns config in Claude Code's expected format.
        """
        mcp_servers = {}

        for server_name in agent.capabilities.mcp_servers:
            if server_name == "github":
                mcp_servers["github"] = {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": credentials.get(
                            "github_pat", ""
                        ),
                    },
                }
            elif server_name == "brave":
                mcp_servers["brave-search"] = {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
                    "env": {
                        "BRAVE_API_KEY": credentials.get("brave_api_key", ""),
                    },
                }
            elif server_name == "filesystem":
                mcp_servers["filesystem"] = {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
                }

        if mcp_servers:
            return {"mcpServers": mcp_servers}
        return {}

    def _parse_metrics(self, output: str) -> dict[str, Any]:
        """Parse Claude Code output for metrics."""
        metrics: dict[str, Any] = {
            "tokens_input": 0,
            "tokens_output": 0,
            "files_modified": [],
        }

        # Look for token usage in output
        # Claude Code outputs usage info in a specific format
        token_pattern = r"Tokens used: (\d+) input, (\d+) output"
        match = re.search(token_pattern, output)
        if match:
            metrics["tokens_input"] = int(match.group(1))
            metrics["tokens_output"] = int(match.group(2))

        # Look for file modifications
        file_pattern = r"(?:Created|Modified|Wrote|Edited): (.+)"
        for match in re.finditer(file_pattern, output):
            metrics["files_modified"].append(match.group(1).strip())

        return metrics

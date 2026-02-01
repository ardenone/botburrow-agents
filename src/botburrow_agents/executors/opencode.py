"""OpenCode executor.

Executes tasks using the OpenCode CLI.
OpenCode is a TUI-based coding assistant with LLM support.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import structlog

from botburrow_agents.executors.base import BaseExecutor
from botburrow_agents.models import AgentConfig

logger = structlog.get_logger(__name__)


class OpenCodeExecutor(BaseExecutor):
    """Executor for OpenCode CLI.

    OpenCode is an open-source coding assistant.
    Supports:
    - Multiple LLM providers
    - TUI interface (we use headless mode)
    - LSP integration
    """

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def runtime_command(self) -> list[str]:
        return ["opencode"]

    def is_available(self) -> bool:
        """Check if OpenCode CLI is available."""
        return shutil.which("opencode") is not None

    async def build_command(
        self,
        agent: AgentConfig,
        prompt: str,
        _workspace: Path,
    ) -> list[str]:
        """Build OpenCode command.

        Args:
            agent: Agent configuration
            prompt: The prompt/task
            workspace: Working directory

        Returns:
            Command list
        """
        cmd = list(self.runtime_command)

        # Headless/non-interactive mode
        cmd.append("--headless")

        # Model configuration
        if agent.brain.model:
            cmd.extend(["--model", agent.brain.model])

        # Provider
        if agent.brain.provider:
            cmd.extend(["--provider", agent.brain.provider.lower()])

        # The prompt/message
        cmd.extend(["--prompt", prompt])

        # Output format
        cmd.extend(["--output-format", "json"])

        return cmd

    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        """Build environment for OpenCode.

        Args:
            agent: Agent configuration
            credentials: API keys

        Returns:
            Environment variables
        """
        env = self._get_base_env()

        provider = agent.brain.provider.lower()

        if provider == "anthropic":
            if "anthropic_api_key" in credentials:
                env["ANTHROPIC_API_KEY"] = credentials["anthropic_api_key"]
        elif provider == "openai":
            if "openai_api_key" in credentials:
                env["OPENAI_API_KEY"] = credentials["openai_api_key"]
        elif provider == "ollama" and "ollama_url" in credentials:
            env["OLLAMA_HOST"] = credentials["ollama_url"]

        # OpenCode-specific settings
        env["OPENCODE_NO_TUI"] = "1"
        env["OPENCODE_AUTO_APPROVE"] = "1"

        return env

    def _parse_metrics(self, output: str) -> dict[str, Any]:
        """Parse OpenCode output for metrics."""
        metrics: dict[str, Any] = {
            "tokens_input": 0,
            "tokens_output": 0,
            "files_modified": [],
        }

        # Try to parse JSON output
        try:
            import json

            data = json.loads(output)
            if "usage" in data:
                metrics["tokens_input"] = data["usage"].get("prompt_tokens", 0)
                metrics["tokens_output"] = data["usage"].get("completion_tokens", 0)
            if "files_modified" in data:
                metrics["files_modified"] = data["files_modified"]
            return metrics
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback to regex parsing
        token_pattern = r"Tokens: (\d+) in, (\d+) out"
        match = re.search(token_pattern, output)
        if match:
            metrics["tokens_input"] = int(match.group(1))
            metrics["tokens_output"] = int(match.group(2))

        # Look for file modifications
        file_patterns = [
            r"Modified: (.+)",
            r"Created: (.+)",
            r"Wrote: (.+)",
        ]
        for pattern in file_patterns:
            for match in re.finditer(pattern, output):
                metrics["files_modified"].append(match.group(1).strip())

        return metrics

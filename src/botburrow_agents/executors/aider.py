"""Aider executor.

Executes tasks using the Aider CLI (aider --message).
Aider is optimized for code editing and git integration.
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


class AiderExecutor(BaseExecutor):
    """Executor for Aider CLI.

    Aider is Paul Gauthier's coding assistant optimized for
    code editing with git integration.

    Supports:
    - Multiple LLM providers
    - Auto-commits
    - Various edit formats (diff, whole, udiff)
    - Architect mode for planning
    """

    @property
    def name(self) -> str:
        return "aider"

    @property
    def runtime_command(self) -> list[str]:
        return ["aider"]

    def is_available(self) -> bool:
        """Check if Aider CLI is available."""
        return shutil.which("aider") is not None

    async def build_command(
        self,
        agent: AgentConfig,
        prompt: str,
        _workspace: Path,
    ) -> list[str]:
        """Build Aider command.

        Args:
            agent: Agent configuration
            prompt: The prompt/task
            workspace: Working directory

        Returns:
            Command list
        """
        cmd = list(self.runtime_command)

        # Model (Aider uses provider/model format)
        model = self._format_model(agent)
        cmd.extend(["--model", model])

        # The message/prompt
        cmd.extend(["--message", prompt])

        # Auto-approve changes (for headless operation)
        cmd.append("--yes")

        # Don't manage git (we handle it separately)
        cmd.append("--no-git")

        # Edit format (default to diff for efficiency)
        # Could be extracted from agent.capabilities.grants in the future
        cmd.extend(["--edit-format", "diff"])

        # No streaming for headless
        cmd.append("--no-stream")

        # Map tokens (for context)
        cmd.extend(["--map-tokens", "2048"])

        return cmd

    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        """Build environment for Aider.

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
        elif provider == "deepseek" and "deepseek_api_key" in credentials:
            env["DEEPSEEK_API_KEY"] = credentials["deepseek_api_key"]

        # Aider-specific settings
        env["AIDER_NO_AUTO_COMMITS"] = "1"  # We handle commits
        env["AIDER_DARK_MODE"] = "1"

        return env

    def _format_model(self, agent: AgentConfig) -> str:
        """Format model name for Aider.

        Aider uses provider/model format for non-default providers.
        """
        provider = agent.brain.provider.lower()
        model = agent.brain.model

        # Anthropic models can be used directly
        if provider == "anthropic":
            return model

        # OpenAI models can be used directly
        if provider == "openai":
            return model

        # Other providers need prefix
        if provider == "deepseek":
            return f"deepseek/{model}"

        if provider == "ollama":
            return f"ollama/{model}"

        return model

    def _parse_metrics(self, output: str) -> dict[str, Any]:
        """Parse Aider output for metrics."""
        metrics: dict[str, Any] = {
            "tokens_input": 0,
            "tokens_output": 0,
            "files_modified": [],
        }

        # Aider outputs token costs
        token_pattern = r"Tokens: ([\d,]+) sent, ([\d,]+) received"
        match = re.search(token_pattern, output)
        if match:
            metrics["tokens_input"] = int(match.group(1).replace(",", ""))
            metrics["tokens_output"] = int(match.group(2).replace(",", ""))

        # Look for file modifications
        file_patterns = [
            r"Applied edit to (.+)",
            r"Wrote (.+)",
            r"Created (.+)",
        ]
        for pattern in file_patterns:
            for match in re.finditer(pattern, output):
                file_path = match.group(1).strip()
                if file_path not in metrics["files_modified"]:
                    metrics["files_modified"].append(file_path)

        return metrics

"""Goose executor.

Executes tasks using the Goose CLI (goose session start).
Goose supports multiple LLM providers and extensions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog
import yaml

from botburrow_agents.executors.base import BaseExecutor
from botburrow_agents.models import AgentConfig

logger = structlog.get_logger(__name__)


class GooseExecutor(BaseExecutor):
    """Executor for Goose CLI.

    Goose is Block's open-source coding assistant.
    Supports:
    - Multiple LLM providers (Anthropic, OpenAI, Ollama)
    - Extensions for additional capabilities
    - Profile-based configuration
    """

    @property
    def name(self) -> str:
        return "goose"

    @property
    def runtime_command(self) -> list[str]:
        return ["goose"]

    async def build_command(
        self,
        agent: AgentConfig,
        prompt: str,
        _workspace: Path,
    ) -> list[str]:
        """Build Goose command.

        Args:
            agent: Agent configuration
            prompt: The prompt/task
            workspace: Working directory

        Returns:
            Command list
        """
        cmd = list(self.runtime_command)

        # Session mode with message
        cmd.extend(["session", "start"])

        # Profile (created in build_env)
        cmd.extend(["--profile", agent.name])

        # The message/prompt
        cmd.extend(["--message", prompt])

        # Non-interactive mode
        cmd.append("--no-interactive")

        return cmd

    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        """Build environment for Goose.

        Also creates the Goose profile configuration file.

        Args:
            agent: Agent configuration
            credentials: API keys

        Returns:
            Environment variables
        """
        env = self._get_base_env()

        # Provider-specific API keys
        provider = agent.brain.provider.lower()

        if provider == "anthropic":
            if "anthropic_api_key" in credentials:
                env["ANTHROPIC_API_KEY"] = credentials["anthropic_api_key"]
        elif provider == "openai":
            if "openai_api_key" in credentials:
                env["OPENAI_API_KEY"] = credentials["openai_api_key"]
        elif provider == "ollama" and "ollama_url" in credentials:
            env["OLLAMA_HOST"] = credentials["ollama_url"]

        # Create profile configuration
        profile_config = self._build_profile_config(agent, credentials)
        profile_path = Path.home() / ".config" / "goose" / "profiles.yaml"
        profile_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing profiles and add/update
        existing: dict[str, Any] = {}
        if profile_path.exists():
            existing = yaml.safe_load(profile_path.read_text()) or {}

        existing[agent.name] = profile_config
        profile_path.write_text(yaml.dump(existing))

        return env

    def _build_profile_config(
        self,
        agent: AgentConfig,
        _credentials: dict[str, str],
    ) -> dict[str, Any]:
        """Build Goose profile configuration."""
        provider = agent.brain.provider.lower()

        config: dict[str, Any] = {
            "provider": provider,
            "model": agent.brain.model,
        }

        # Extensions
        extensions = []

        # Developer extension (always enabled for coding)
        extensions.append({
            "name": "developer",
            "enabled": True,
        })

        # Add extensions based on MCP servers
        for server in agent.capabilities.mcp_servers:
            if server == "github":
                extensions.append({
                    "name": "github",
                    "enabled": True,
                })
            elif server == "brave":
                extensions.append({
                    "name": "web-search",
                    "enabled": True,
                })

        if extensions:
            config["extensions"] = extensions

        # System prompt
        if agent.system_prompt:
            config["system_prompt"] = agent.system_prompt

        return config

    def _parse_metrics(self, output: str) -> dict[str, Any]:
        """Parse Goose output for metrics."""
        metrics: dict[str, Any] = {
            "tokens_input": 0,
            "tokens_output": 0,
            "files_modified": [],
        }

        # Goose outputs token usage in specific format
        token_pattern = r"Token usage: (\d+) prompt, (\d+) completion"
        match = re.search(token_pattern, output)
        if match:
            metrics["tokens_input"] = int(match.group(1))
            metrics["tokens_output"] = int(match.group(2))

        # Look for file modifications
        file_patterns = [
            r"Writing to (.+)",
            r"Created file: (.+)",
            r"Modified: (.+)",
        ]
        for pattern in file_patterns:
            for match in re.finditer(pattern, output):
                metrics["files_modified"].append(match.group(1).strip())

        return metrics

"""Git client for loading agent configurations from git repository.

Implements ADR-028: Load agent configs directly from git instead of R2.
R2 is now only for binary assets (avatars, images).

Synced with agent-definitions schema v1.0.0:
https://github.com/jedarden/agent-definitions/blob/main/schemas/agent-config.schema.json
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import (
    AgentConfig,
    BehaviorConfig,
    BehaviorLimitsConfig,
    BrainConfig,
    CapabilityGrants,
    DiscoveryConfig,
    InterestConfig,
    MemoryConfig,
    MemoryRememberConfig,
    MemoryRetrievalConfig,
    ShellConfig,
    SpawningConfig,
)

logger = structlog.get_logger(__name__)

# Default GitHub repository for agent definitions
# NOTE: This is a fallback default. The actual repo is configured via
# the agent-definitions-repos ConfigMap in Kubernetes (per ADR-028)
DEFAULT_GITHUB_REPO = "jedarden/agent-definitions"
DEFAULT_GITHUB_BRANCH = "main"

# GitHub raw URL pattern
GITHUB_RAW_URL = "https://raw.githubusercontent.com"


class GitClient:
    """Client for loading agent configs from git.

    Supports two modes:
    1. Local filesystem: When configs are cloned via git-sync sidecar
    2. GitHub API: Direct fetch from GitHub with caching
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._http_client: httpx.AsyncClient | None = None

        # Config source settings
        self.repo = os.environ.get("AGENT_DEFINITIONS_REPO", f"{DEFAULT_GITHUB_REPO}")
        self.branch = os.environ.get("AGENT_DEFINITIONS_BRANCH", DEFAULT_GITHUB_BRANCH)
        self.local_path = os.environ.get("AGENT_DEFINITIONS_PATH", "/configs/agent-definitions")

    @property
    def use_local(self) -> bool:
        """Check if using local filesystem (git-sync mode)."""
        return os.path.exists(self.local_path)

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_local_path(self, agent_id: str, filename: str = "config.yaml") -> Path:
        """Get local filesystem path for an agent config."""
        return Path(self.local_path) / "agents" / agent_id / filename

    def _get_github_url(self, agent_id: str, filename: str = "config.yaml") -> str:
        """Get GitHub raw URL for an agent config."""
        return f"{GITHUB_RAW_URL}/{self.repo}/{self.branch}/agents/{agent_id}/{filename}"

    async def _fetch_from_github(self, url: str) -> str:
        """Fetch content from GitHub raw URL."""
        client = self._get_http_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    async def get_agent_config(self, agent_id: str) -> dict[str, Any]:
        """Get agent config YAML.

        Args:
            agent_id: Agent identifier

        Returns:
            Parsed YAML dict

        Raises:
            FileNotFoundError: If config not found
        """
        if self.use_local:
            path = self._get_local_path(agent_id, "config.yaml")
            if not path.exists():
                raise FileNotFoundError(f"Agent config not found: {path}")
            return yaml.safe_load(path.read_text())
        else:
            url = self._get_github_url(agent_id, "config.yaml")
            try:
                content = await self._fetch_from_github(url)
                return yaml.safe_load(content)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise FileNotFoundError(f"Agent config not found: {url}") from e
                raise

    async def get_system_prompt(self, agent_id: str) -> str:
        """Get agent system prompt.

        Args:
            agent_id: Agent identifier

        Returns:
            System prompt content (empty string if not found)
        """
        if self.use_local:
            path = self._get_local_path(agent_id, "system-prompt.md")
            if path.exists():
                return path.read_text()
            return ""
        else:
            url = self._get_github_url(agent_id, "system-prompt.md")
            try:
                return await self._fetch_from_github(url)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.debug("no_system_prompt", agent_id=agent_id)
                    return ""
                raise

    async def get_skill(self, skill_name: str) -> str:
        """Get skill instructions.

        Args:
            skill_name: Name of the skill

        Returns:
            SKILL.md contents

        Raises:
            FileNotFoundError: If skill not found
        """
        if self.use_local:
            path = Path(self.local_path) / "skills" / skill_name / "SKILL.md"
            if not path.exists():
                raise FileNotFoundError(f"Skill not found: {skill_name}")
            return path.read_text()
        else:
            url = f"{GITHUB_RAW_URL}/{self.repo}/{self.branch}/skills/{skill_name}/SKILL.md"
            try:
                return await self._fetch_from_github(url)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise FileNotFoundError(f"Skill not found: {skill_name}") from e
                raise

    async def list_agents(self) -> list[str]:
        """List available agent IDs.

        Returns:
            List of agent identifiers
        """
        if self.use_local:
            agents_dir = Path(self.local_path) / "agents"
            if not agents_dir.exists():
                return []
            return sorted(
                [
                    d.name
                    for d in agents_dir.iterdir()
                    if d.is_dir() and (d / "config.yaml").exists()
                ]
            )
        else:
            # For GitHub mode, we'd need to use the GitHub API
            # For now, return empty list - cache should handle this
            logger.warning("list_agents_not_supported_for_github_mode")
            return []

    async def list_skills(self) -> list[str]:
        """List available skills.

        Returns:
            List of skill names
        """
        if self.use_local:
            skills_dir = Path(self.local_path) / "skills"
            if not skills_dir.exists():
                return []
            return sorted(
                [d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
            )
        else:
            logger.warning("list_skills_not_supported_for_github_mode")
            return []

    async def load_agent_config(self, agent_id: str) -> AgentConfig:
        """Load complete agent configuration.

        Parses all fields from agent-definitions schema v1.0.0.
        Uses Pydantic's model_validate to handle unknown fields gracefully.

        Args:
            agent_id: Agent identifier

        Returns:
            Fully populated AgentConfig

        Note:
            This is a workaround that uses Pydantic's flexible parsing to handle
            schema changes without requiring manual field-by-field updates.
            Unknown fields in the YAML are silently ignored (not causing errors).
            For a proper solution, implement schema version tracking and migration.
        """
        config_data = await self.get_agent_config(agent_id)
        system_prompt = await self.get_system_prompt(agent_id)

        # WORKAROUND: Use Pydantic's model_validate with ** unpacking
        # This handles:
        # 1. Known schema fields properly validated
        # 2. Unknown fields ignored (not errors)
        # 3. New optional fields work automatically

        # Prepare nested dicts for Pydantic validation
        # Pass through as-is and let Pydantic handle validation with defaults
        brain_data = config_data.get("brain", {}) or {}
        caps_data = config_data.get("capabilities", {}) or {}
        interests_data = config_data.get("interests", {}) or {}
        behavior_data = config_data.get("behavior", {}) or {}
        memory_data = config_data.get("memory", {}) or {}

        # Extract nested configs
        shell_data = caps_data.get("shell", {}) or {}
        spawning_data = caps_data.get("spawning", {}) or {}
        discovery_data = behavior_data.get("discovery", {}) or {}
        limits_data = behavior_data.get("limits", {}) or {}
        remember_data = memory_data.get("remember", {}) or {}
        retrieval_data = memory_data.get("retrieval", {}) or {}

        # Use Pydantic's model_validate which handles extra_fields gracefully
        brain = BrainConfig.model_validate(brain_data) if brain_data else BrainConfig()

        capabilities = CapabilityGrants(
            grants=caps_data.get("grants", []),
            skills=caps_data.get("skills", []),
            mcp_servers=caps_data.get("mcp_servers", []),
            shell=ShellConfig.model_validate(shell_data) if shell_data else ShellConfig(),
            spawning=SpawningConfig.model_validate(spawning_data) if spawning_data else SpawningConfig(),
        )

        interests = InterestConfig.model_validate(interests_data) if interests_data else InterestConfig()

        behavior = BehaviorConfig(
            respond_to_mentions=behavior_data.get("respond_to_mentions", True),
            respond_to_replies=behavior_data.get("respond_to_replies", True),
            respond_to_dms=behavior_data.get("respond_to_dms", True),
            max_iterations=behavior_data.get("max_iterations", 10),
            can_create_posts=behavior_data.get("can_create_posts", True),
            max_daily_posts=behavior_data.get("max_daily_posts", 5),
            max_daily_comments=behavior_data.get("max_daily_comments", 50),
            discovery=DiscoveryConfig.model_validate(discovery_data) if discovery_data else DiscoveryConfig(),
            limits=BehaviorLimitsConfig.model_validate(limits_data) if limits_data else BehaviorLimitsConfig(),
        )

        memory = MemoryConfig(
            enabled=memory_data.get("enabled", False),
            remember=MemoryRememberConfig.model_validate(remember_data) if remember_data else MemoryRememberConfig(),
            max_size_mb=memory_data.get("max_size_mb", 100),
            retrieval=MemoryRetrievalConfig.model_validate(retrieval_data) if retrieval_data else MemoryRetrievalConfig(),
        )

        return AgentConfig(
            name=config_data.get("name", agent_id),
            type=config_data.get("type", "claude-code"),
            brain=brain,
            capabilities=capabilities,
            interests=interests,
            behavior=behavior,
            memory=memory,
            display_name=config_data.get("display_name"),
            description=config_data.get("description"),
            version=config_data.get("version"),
            system_prompt=system_prompt,
            cache_ttl=config_data.get("cache_ttl", 300),
            r2_path="",  # Deprecated
        )

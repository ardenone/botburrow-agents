"""Git client for loading agent configurations from git repository.

Implements ADR-028: Load agent configs directly from git instead of R2.
R2 is now only for binary assets (avatars, images).

Synced with agent-definitions schema v1.0.0:
https://github.com/ardenone/agent-definitions/blob/main/schemas/agent-config.schema.json
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
DEFAULT_GITHUB_REPO = "ardenone/agent-definitions"
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

        Args:
            agent_id: Agent identifier

        Returns:
            Fully populated AgentConfig
        """
        config_data = await self.get_agent_config(agent_id)
        system_prompt = await self.get_system_prompt(agent_id)

        # Parse brain configuration
        brain_data = config_data.get("brain", {})
        brain = BrainConfig(
            model=brain_data.get("model", "claude-sonnet-4-20250514"),
            provider=brain_data.get("provider", "anthropic"),
            temperature=brain_data.get("temperature", 0.7),
            max_tokens=brain_data.get("max_tokens", 4096),
            api_base=brain_data.get("api_base"),
            api_key_env=brain_data.get("api_key_env"),
        )

        # Parse capabilities configuration
        caps_data = config_data.get("capabilities", {})
        shell_data = caps_data.get("shell", {})
        spawning_data = caps_data.get("spawning", {})

        capabilities = CapabilityGrants(
            grants=caps_data.get("grants", []),
            skills=caps_data.get("skills", []),
            mcp_servers=caps_data.get("mcp_servers", []),
            shell=ShellConfig(
                enabled=shell_data.get("enabled", False),
                allowed_commands=shell_data.get("allowed_commands", []),
                blocked_patterns=shell_data.get("blocked_patterns", []),
                timeout_seconds=shell_data.get("timeout_seconds", 120),
            ),
            spawning=SpawningConfig(
                can_propose=spawning_data.get("can_propose", False),
                allowed_templates=spawning_data.get("allowed_templates", []),
            ),
        )

        # Parse interests configuration
        interests_data = config_data.get("interests", {})
        interests = InterestConfig(
            topics=interests_data.get("topics", []),
            communities=interests_data.get("communities", []),
            keywords=interests_data.get("keywords", []),
            follow_agents=interests_data.get("follow_agents", []),
        )

        # Parse behavior configuration
        behavior_data = config_data.get("behavior", {})
        discovery_data = behavior_data.get("discovery", {})
        limits_data = behavior_data.get("limits", {})

        behavior = BehaviorConfig(
            respond_to_mentions=behavior_data.get("respond_to_mentions", True),
            respond_to_replies=behavior_data.get("respond_to_replies", True),
            respond_to_dms=behavior_data.get("respond_to_dms", True),
            max_iterations=behavior_data.get("max_iterations", 10),
            can_create_posts=behavior_data.get("can_create_posts", True),
            # Legacy fields for backwards compatibility
            max_daily_posts=behavior_data.get("max_daily_posts", 5),
            max_daily_comments=behavior_data.get("max_daily_comments", 50),
            # New schema fields
            discovery=DiscoveryConfig(
                enabled=discovery_data.get("enabled", False),
                frequency=discovery_data.get("frequency", "staleness"),
                respond_to_questions=discovery_data.get("respond_to_questions", False),
                respond_to_discussions=discovery_data.get("respond_to_discussions", False),
                min_confidence=discovery_data.get("min_confidence", 0.7),
            ),
            limits=BehaviorLimitsConfig(
                max_daily_posts=limits_data.get("max_daily_posts", 5),
                max_daily_comments=limits_data.get("max_daily_comments", 50),
                max_responses_per_thread=limits_data.get("max_responses_per_thread", 3),
                min_interval_seconds=limits_data.get("min_interval_seconds", 60),
            ),
        )

        # Parse memory configuration
        memory_data = config_data.get("memory", {})
        remember_data = memory_data.get("remember", {})
        retrieval_data = memory_data.get("retrieval", {})

        memory = MemoryConfig(
            enabled=memory_data.get("enabled", False),
            remember=MemoryRememberConfig(
                conversations_with=remember_data.get("conversations_with", []),
                projects_worked_on=remember_data.get("projects_worked_on", False),
                decisions_made=remember_data.get("decisions_made", False),
                feedback_received=remember_data.get("feedback_received", False),
            ),
            max_size_mb=memory_data.get("max_size_mb", 100),
            retrieval=MemoryRetrievalConfig(
                strategy=retrieval_data.get("strategy", "embedding_search"),
                max_context_items=retrieval_data.get("max_context_items", 10),
                relevance_threshold=retrieval_data.get("relevance_threshold", 0.7),
            ),
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

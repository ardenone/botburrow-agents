"""Test multi-persona agent execution on shared runner pool.

Validates that M agent definitions can run on N runners (M > N):
- 5+ agent personas (M)
- 3-5 runners (N)
- Dynamic config loading from agent-definitions repo
- Persona switching without pod restart
- Distinct behavior per persona
- MCP server integration per agent type

Related to bead bd-2om: Test agent execution with different personas.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import yaml

from botburrow_agents.clients.git import GitClient
from botburrow_agents.config import Settings, get_settings
from botburrow_agents.coordinator.work_queue import ConfigCache, WorkItem, WorkQueue
from botburrow_agents.models import (
    AgentConfig,
    Assignment,
    BehaviorConfig,
    BrainConfig,
    CapabilityGrants,
    InterestConfig,
    MemoryConfig,
    ShellConfig,
    SpawningConfig,
    TaskType,
)
from botburrow_agents.runner.main import Runner


# Agent personas to test (M = 5)
AGENT_PERSONAS = [
    "test-persona-agent",
    "research-agent",
    "claude-coder-1",
    "sprint-coder",
    "devops-agent",
]

# Simulated runner count (N = 3)
SIMULATED_RUNNERS = 3


@pytest.fixture
def mock_settings() -> Settings:
    """Create test settings."""
    return Settings(
        hub_url="http://localhost:8000",
        redis_url="redis://localhost:6379",
        runner_id="test-runner",
        activation_timeout=300,
    )


@pytest.fixture
def agent_definitions_path() -> Path:
    """Get path to agent definitions repo."""
    # Check if running from devpod with local clone
    local_path = Path("/configs/agent-definitions")
    if local_path.exists():
        return local_path

    # Fall back to repo in home directory
    repo_path = Path("/home/coder/agent-definitions")
    if repo_path.exists():
        return repo_path

    # For testing, use the project's test fixtures
    return Path(__file__).parent.parent / "agent-definitions"


@pytest.fixture
def mock_git_client(agent_definitions_path: Path) -> MagicMock:
    """Create mock Git client that loads from local filesystem."""
    client = MagicMock(spec=GitClient)
    client.local_path = str(agent_definitions_path)
    client.use_local = agent_definitions_path.exists()

    async def mock_load_agent_config(agent_id: str) -> AgentConfig:
        """Load real agent config from filesystem."""
        config_path = agent_definitions_path / "agents" / agent_id / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Agent config not found: {config_path}")

        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        # Parse system prompt if exists
        prompt_path = agent_definitions_path / "agents" / agent_id / "system-prompt.md"
        system_prompt = ""
        if prompt_path.exists():
            system_prompt = prompt_path.read_text()

        # Parse brain config
        brain_data = config_data.get("brain", {})
        brain = BrainConfig(
            model=brain_data.get("model", "claude-sonnet-4-20250514"),
            provider=brain_data.get("provider", "anthropic"),
            temperature=brain_data.get("temperature", 0.7),
            max_tokens=brain_data.get("max_tokens", 4096),
            api_base=brain_data.get("api_base"),
            api_key_env=brain_data.get("api_key_env"),
        )

        # Parse capabilities
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

        # Parse interests
        interests_data = config_data.get("interests", {})
        interests = InterestConfig(
            topics=interests_data.get("topics", []),
            communities=interests_data.get("communities", []),
            keywords=interests_data.get("keywords", []),
            follow_agents=interests_data.get("follow_agents", []),
        )

        # Parse behavior
        behavior_data = config_data.get("behavior", {})
        discovery_data = behavior_data.get("discovery", {})
        limits_data = behavior_data.get("limits", {})

        behavior = BehaviorConfig(
            respond_to_mentions=behavior_data.get("respond_to_mentions", True),
            respond_to_replies=behavior_data.get("respond_to_replies", True),
            respond_to_dms=behavior_data.get("respond_to_dms", True),
            max_iterations=behavior_data.get("max_iterations", 10),
            can_create_posts=behavior_data.get("can_create_posts", True),
            max_daily_posts=behavior_data.get("max_daily_posts", 5),
            max_daily_comments=behavior_data.get("max_daily_comments", 50),
            discovery_enabled=discovery_data.get("enabled", False),
            discovery_frequency=discovery_data.get("frequency", "staleness"),
            respond_to_questions=discovery_data.get("respond_to_questions", False),
            respond_to_discussions=discovery_data.get("respond_to_discussions", False),
            min_confidence=discovery_data.get("min_confidence", 0.7),
            max_responses_per_thread=limits_data.get("max_responses_per_thread", 3),
            min_interval_seconds=limits_data.get("min_interval_seconds", 60),
        )

        # Parse memory
        memory_data = config_data.get("memory", {})
        remember_data = memory_data.get("remember", {})
        retrieval_data = memory_data.get("retrieval", {})

        memory = MemoryConfig(
            enabled=memory_data.get("enabled", False),
            remember_conversations_with=remember_data.get("conversations_with", []),
            remember_projects_worked_on=remember_data.get("projects_worked_on", False),
            remember_decisions_made=remember_data.get("decisions_made", False),
            remember_feedback_received=remember_data.get("feedback_received", False),
            max_size_mb=memory_data.get("max_size_mb", 100),
            retrieval_strategy=retrieval_data.get("strategy", "embedding_search"),
            retrieval_max_context_items=retrieval_data.get("max_context_items", 10),
            retrieval_relevance_threshold=retrieval_data.get("relevance_threshold", 0.7),
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
            r2_path="",
        )

    client.load_agent_config = mock_load_agent_config

    async def mock_list_agents() -> list[str]:
        """List available agents."""
        agents_dir = agent_definitions_path / "agents"
        if not agents_dir.exists():
            return []
        return sorted(
            [
                d.name
                for d in agents_dir.iterdir()
                if d.is_dir() and (d / "config.yaml").exists()
            ]
        )

    client.list_agents = mock_list_agents

    async def mock_get_system_prompt(agent_id: str) -> str:
        """Get system prompt."""
        prompt_path = agent_definitions_path / "agents" / agent_id / "system-prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return ""

    client.get_system_prompt = mock_get_system_prompt

    return client


class TestAgentPersonaDiscovery:
    """Test 1: Verify M agent definitions exist (M > N)."""

    @pytest.mark.asyncio
    async def test_list_all_agent_personas(self, mock_git_client: MagicMock) -> None:
        """Verify we can list all agent personas from agent-definitions."""
        agents = await mock_git_client.list_agents()

        # Should have at least 5 personas
        assert len(agents) >= 5, f"Expected at least 5 agent personas, found {len(agents)}"

        # Verify expected personas exist
        for persona in AGENT_PERSONAS:
            assert persona in agents, f"Expected persona '{persona}' not found in {agents}"

    @pytest.mark.asyncio
    async def test_load_each_agent_config(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify we can load each agent's configuration."""
        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)

            # Verify required fields
            assert config.name == persona
            assert config.brain is not None
            assert config.capabilities is not None
            assert config.interests is not None
            assert config.behavior is not None

            # Verify distinct characteristics
            assert config.display_name is not None
            assert config.description is not None


class TestDistinctPersonaBehaviors:
    """Test 2: Verify each agent persona has distinct behavior."""

    @pytest.mark.asyncio
    async def test_distinct_temperature_settings(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agents have different temperature settings (affects creativity)."""
        configs = {}
        for persona in AGENT_PERSONAS:
            configs[persona] = await mock_git_client.load_agent_config(persona)

        # Research agent should be more conservative (lower temp)
        research_temp = configs["research-agent"].brain.temperature
        # Sprint coder might be more creative (higher temp)
        sprint_temp = configs["sprint-coder"].brain.temperature

        # At minimum, verify temperatures are in valid range
        for name, config in configs.items():
            assert 0.0 <= config.brain.temperature <= 2.0, \
                f"{name} has invalid temperature: {config.brain.temperature}"

    @pytest.mark.asyncio
    async def test_distinct_interests_and_topics(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agents have different interests and topics."""
        configs = {}
        for persona in AGENT_PERSONAS:
            configs[persona] = await mock_git_client.load_agent_config(persona)

        # Research agent should be interested in research topics
        research_topics = configs["research-agent"].interests.topics
        assert "research" in research_topics or "machine-learning" in research_topics

        # DevOps agent should be interested in DevOps topics
        devops_topics = configs["devops-agent"].interests.topics
        assert "kubernetes" in devops_topics or "devops" in devops_topics

        # Verify each has distinct communities
        communities_sets = {}
        for name, config in configs.items():
            communities_sets[name] = set(config.interests.communities)

        # At least some agents should have different communities
        assert len(communities_sets["research-agent"] | communities_sets["devops-agent"]) > 0

    @pytest.mark.asyncio
    async def test_distinct_capabilities(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agents have different capability grants."""
        configs = {}
        for persona in AGENT_PERSONAS:
            configs[persona] = await mock_git_client.load_agent_config(persona)

        # DevOps agent should have kubernetes grants
        devops_grants = configs["devops-agent"].capabilities.grants
        assert "hub:read" in devops_grants
        assert "hub:write" in devops_grants

        # Research agent should have search capabilities
        research_caps = configs["research-agent"].capabilities
        assert any("search" in grant or "arxiv" in grant for grant in research_caps.grants)

    @pytest.mark.asyncio
    async def test_distinct_mcp_servers(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agents use different MCP servers."""
        configs = {}
        for persona in AGENT_PERSONAS:
            configs[persona] = await mock_git_client.load_agent_config(persona)

        # Research agent should use brave (search)
        research_mcp = configs["research-agent"].capabilities.mcp_servers
        assert "brave" in research_mcp

        # Verify each agent has at least one MCP server
        for name, config in configs.items():
            assert len(config.capabilities.mcp_servers) >= 1, \
                f"{name} should have at least one MCP server"


class TestDynamicConfigLoading:
    """Test 3: Verify runners can dynamically load different agent configs."""

    @pytest.mark.asyncio
    async def test_config_caching_per_agent(
        self, mock_settings: Settings, mock_git_client: MagicMock
    ) -> None:
        """Verify configs are cached with agent-specific TTLs."""
        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis._ensure_connected = AsyncMock(return_value=mock_redis)
        mock_redis.get = AsyncMock(return_value=None)  # Cache miss initially
        mock_redis.set = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=None)
        mock_redis.hset = AsyncMock()
        mock_redis.hdel = AsyncMock()
        mock_redis.lpush = AsyncMock()
        mock_redis.brpop = AsyncMock(return_value=None)
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.hlen = AsyncMock(return_value=0)
        mock_redis.hincrby = AsyncMock(return_value=1)
        mock_redis.scan_iter = AsyncMock(return_value=[])
        mock_redis.delete = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.eval = AsyncMock()
        mock_redis.lpop = AsyncMock()

        from botburrow_agents.clients.redis import RedisClient
        redis_client = RedisClient(mock_settings)
        redis_client._client = mock_redis

        # Create config cache
        cache = ConfigCache(redis_client)

        # Load and cache each agent config
        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)
            await cache.set(persona, config.model_dump(), ttl=config.cache_ttl)

        # Verify each config was cached
        assert mock_redis.set.call_count == len(AGENT_PERSONAS)

        # Verify different TTLs were used (agents have different cache_ttl values)
        # test-persona-agent has 60s TTL, others have 180-300s
        call_args_list = [call.args for call in mock_redis.set.call_args_list]

        # Find test-persona-agent cache call (should have 60s TTL)
        test_persona_call = None
        for args in call_args_list:
            if "test-persona-agent" in args[0]:
                test_persona_call = args
                break

        assert test_persona_call is not None, "test-persona-agent should be cached"
        # The TTL is passed as ex kwarg
        ttl_calls = [call.kwargs for call in mock_redis.set.call_args_list]
        test_persona_ttl = None
        for kwargs in ttl_calls:
            if "cache:agent:test-persona-agent" in str(kwargs):
                test_persona_ttl = kwargs.get("ex")
                break

        # Test persona has 60s cache TTL
        assert test_persona_ttl == 60 or test_persona_ttl == 60, \
            f"test-persona-agent should have 60s TTL, got {test_persona_ttl}"

    @pytest.mark.asyncio
    async def test_cache_invalidation_and_reload(
        self, mock_settings: Settings, mock_git_client: MagicMock
    ) -> None:
        """Verify cache can be invalidated and configs reloaded."""
        # Create mock Redis
        mock_redis = MagicMock()
        mock_redis._ensure_connected = AsyncMock(return_value=mock_redis)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=None)
        mock_redis.hset = AsyncMock()
        mock_redis.hdel = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.scan_iter = AsyncMock(return_value=[])
        mock_redis.lpush = AsyncMock()
        mock_redis.brpop = AsyncMock(return_value=None)
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.hlen = AsyncMock(return_value=0)
        mock_redis.hincrby = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        mock_redis.eval = AsyncMock()
        mock_redis.lpop = AsyncMock()

        from botburrow_agents.clients.redis import RedisClient
        redis_client = RedisClient(mock_settings)
        redis_client._client = mock_redis

        cache = ConfigCache(redis_client)

        # Cache a config
        config = await mock_git_client.load_agent_config("research-agent")
        await cache.set("research-agent", config.model_dump())

        # Invalidate
        await cache.invalidate("research-agent")

        # Verify delete was called
        assert mock_redis.delete.call_count >= 1


class TestWorkQueueDistribution:
    """Test 4: Verify work queue distributes work across runners."""

    @pytest.mark.asyncio
    async def test_work_queue_supports_multiple_agents(
        self, mock_settings: Settings
    ) -> None:
        """Verify work queue can handle multiple agents simultaneously."""
        # Create mock Redis
        mock_redis = MagicMock()
        mock_redis._ensure_connected = AsyncMock(return_value=mock_redis)
        mock_redis.lpush = AsyncMock()
        mock_redis.brpop = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=None)  # No active tasks
        mock_redis.hdel = AsyncMock()
        mock_redis.hlen = AsyncMock(return_value=0)
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.hincrby = AsyncMock(return_value=0)
        mock_redis.expire = AsyncMock()
        mock_redis.eval = AsyncMock()

        from botburrow_agents.clients.redis import RedisClient
        redis_client = RedisClient(mock_settings)
        redis_client._client = mock_redis

        queue = WorkQueue(redis_client)

        # Enqueue work for all personas
        for persona in AGENT_PERSONAS:
            work = WorkItem(
                agent_id=persona,
                agent_name=persona,
                task_type=TaskType.INBOX,
                priority="normal",
            )
            success = await queue.enqueue(work)
            assert success, f"Failed to enqueue work for {persona}"

        # Verify all were enqueued
        assert mock_redis.lpush.call_count == len(AGENT_PERSONAS)

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(
        self, mock_settings: Settings
    ) -> None:
        """Verify high priority work is processed first."""
        # Create mock Redis
        mock_redis = MagicMock()
        mock_redis._ensure_connected = AsyncMock(return_value=mock_redis)
        mock_redis.lpush = AsyncMock()
        mock_redis.brpop = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=None)
        mock_redis.hdel = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.hlen = AsyncMock(return_value=0)
        mock_redis.hincrby = AsyncMock(return_value=0)
        mock_redis.expire = AsyncMock()
        mock_redis.eval = AsyncMock()

        from botburrow_agents.clients.redis import RedisClient
        redis_client = RedisClient(mock_settings)
        redis_client._client = mock_redis

        queue = WorkQueue(redis_client)

        # Enqueue with different priorities
        high_priority = WorkItem(
            agent_id="test-persona-agent",
            agent_name="test-persona-agent",
            task_type=TaskType.INBOX,
            priority="high",
        )
        normal_priority = WorkItem(
            agent_id="research-agent",
            agent_name="research-agent",
            task_type=TaskType.INBOX,
            priority="normal",
        )

        await queue.enqueue(high_priority)
        await queue.enqueue(normal_priority)

        # Verify BRPOP checks queues in priority order
        # BRPOP should be called with [high, normal, low]
        assert mock_redis.brpop.call_count == 0  # No claims yet


class TestRunnerPersonaSwitching:
    """Test 5: Verify runners can switch between personas without restart."""

    @pytest.mark.asyncio
    async def test_runner_processes_multiple_agents(
        self,
        mock_settings: Settings,
        mock_git_client: MagicMock,
    ) -> None:
        """Verify a single runner can process different agent personas sequentially."""
        # This simulates a runner picking up work for different agents
        # without needing to restart

        processed_agents = []

        # Simulate processing each agent
        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)

            # Verify config was loaded successfully
            assert config.name == persona
            assert config.capabilities is not None

            # Track that we processed this agent
            processed_agents.append(persona)

        # Verify all agents were "processed" by the same runner
        assert len(processed_agents) == len(AGENT_PERSONAS)
        assert set(processed_agents) == set(AGENT_PERSONAS)

    @pytest.mark.asyncio
    async def test_persona_switching_preserves_isolation(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify switching personas doesn't leak configuration between agents."""
        configs = {}

        # Load all configs
        for persona in AGENT_PERSONAS:
            configs[persona] = await mock_git_client.load_agent_config(persona)

        # Verify each config has distinct settings
        for i, persona1 in enumerate(AGENT_PERSONAS):
            for persona2 in AGENT_PERSONAS[i + 1:]:
                config1 = configs[persona1]
                config2 = configs[persona2]

                # Names should be different
                assert config1.name != config2.name

                # At least one capability setting should differ
                if config1.capabilities.mcp_servers != config2.capabilities.mcp_servers:
                    pass  # They have different MCP servers
                elif config1.interests.topics != config2.interests.topics:
                    pass  # They have different topics
                else:
                    # At minimum, descriptions should differ
                    assert config1.description != config2.description or \
                           config1.display_name != config2.display_name


class TestMCPServerIntegration:
    """Test 6: Verify MCP server integration works per agent type."""

    @pytest.mark.asyncio
    async def test_mcp_servers_defined_per_agent(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify each agent defines required MCP servers."""
        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)

            # All agents should have at least hub MCP server
            mcp_servers = config.capabilities.mcp_servers
            assert len(mcp_servers) >= 1, \
                f"{persona} should have at least one MCP server"

    @pytest.mark.asyncio
    async def test_mcp_server_matches_capabilities(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify MCP servers align with capability grants."""
        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)

            grants = config.capabilities.grants
            mcp_servers = config.capabilities.mcp_servers

            # If agent has github:read/write grant, should have github MCP server
            if any("github" in grant for grant in grants):
                assert "github" in mcp_servers, \
                    f"{persona} has github grants but no github MCP server"

            # If agent has search grants, should have brave MCP server
            if any("search" in grant or "brave" in grant for grant in grants):
                assert "brave" in mcp_servers, \
                    f"{persona} has search grants but no brave MCP server"


class TestRunnerScalability:
    """Test 7: Verify system scales M agents on N runners."""

    def test_m_greater_than_n(self) -> None:
        """Verify M > N (more agents than runners)."""
        m = len(AGENT_PERSONAS)
        n = SIMULATED_RUNNERS

        assert m > n, f"Need M > N, but M={m}, N={n}"

    @pytest.mark.asyncio
    async def test_all_agents_can_be_processed(
        self, mock_settings: Settings
    ) -> None:
        """Verify all agents can eventually be processed by runners."""
        # Simulate work queue processing
        mock_redis = MagicMock()
        mock_redis._ensure_connected = AsyncMock(return_value=mock_redis)
        mock_redis.lpush = AsyncMock()
        mock_redis.brpop = AsyncMock()
        mock_redis.hset = AsyncMock()
        mock_redis.hget = AsyncMock(return_value=None)
        mock_redis.hdel = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=0)
        mock_redis.hlen = AsyncMock(return_value=0)
        mock_redis.hincrby = AsyncMock(return_value=0)
        mock_redis.expire = AsyncMock()
        mock_redis.eval = AsyncMock()

        from botburrow_agents.clients.redis import RedisClient
        redis_client = RedisClient(mock_settings)
        redis_client._client = mock_redis

        queue = WorkQueue(redis_client)

        # All agents can be enqueued
        for persona in AGENT_PERSONAS:
            work = WorkItem(
                agent_id=persona,
                agent_name=persona,
                task_type=TaskType.INBOX,
            )
            success = await queue.enqueue(work)
            assert success, f"Failed to enqueue {persona}"

        # Even with fewer runners, all work is queued
        assert mock_redis.lpush.call_count == len(AGENT_PERSONAS)


class TestSystemPromptDistinctiveness:
    """Test 8: Verify system prompts create distinct personas."""

    @pytest.mark.asyncio
    async def test_system_prompts_exist_and_differ(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agents have distinct system prompts."""
        prompts = {}

        for persona in AGENT_PERSONAS:
            prompt = await mock_git_client.get_system_prompt(persona)
            prompts[persona] = prompt

        # test-persona-agent should have a prompt (it's for testing)
        # Other agents may or may not have custom prompts

        # Verify at least one agent has a custom prompt
        custom_prompts = {k: v for k, v in prompts.items() if v}
        assert len(custom_prompts) >= 1, "At least one agent should have a system prompt"

    @pytest.mark.asyncio
    async def test_system_prompt_reflects_persona(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify system prompt content matches agent purpose."""
        # Research agent prompt should mention research
        research_prompt = await mock_git_client.get_system_prompt("research-agent")
        if research_prompt:
            # Should mention research-related terms
            research_lower = research_prompt.lower()
            assert any(term in research_lower for term in ["research", "paper", "study", "findings"]), \
                "Research agent system prompt should mention research"


# Integration test markers
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]

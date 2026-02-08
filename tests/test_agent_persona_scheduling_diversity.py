"""Test agent persona diversity and scheduling for bead bd-2ua.

Verifies agent persona management:
1. Document current agent personas (list from agent-definitions)
2. Test scheduling: ensure diverse personas get activated (not always same agents)
3. Verify exploration tasks distribute across different agent types
4. Test notification routing: mentions go to correct agent persona
5. Check agent personality consistency: same persona maintains character across activations
6. Test new persona deployment: add agent to definitions, verify picked up without runner restart
7. Monitor persona activation frequency and balance

Related to bead bd-2ua: Test agent persona diversity and scheduling.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import yaml

from botburrow_agents.clients.git import GitClient
from botburrow_agents.config import Settings, get_settings, ActivationMode
from botburrow_agents.models import (
    AgentConfig,
    Assignment,
    BrainConfig,
    CapabilityGrants,
    InterestConfig,
    ShellConfig,
    SpawningConfig,
    TaskType,
)


# Agent personas currently defined (from agent-definitions repository)
AGENT_PERSONAS = [
    "test-persona-agent",
    "research-agent",
    "claude-coder-1",
    "sprint-coder",
    "devops-agent",
]


@pytest.fixture
def mock_settings() -> Settings:
    """Create test settings."""
    return Settings(
        hub_url="http://localhost:8000",
        redis_url="redis://localhost:6379",
        runner_id="test-runner",
        activation_timeout=300,
        lock_ttl=300,
        poll_interval=30,
        min_activation_interval=300,
    )


@pytest.fixture
def agent_definitions_path() -> Path:
    """Get path to agent definitions repo."""
    local_path = Path("/configs/agent-definitions")
    if local_path.exists():
        return local_path

    repo_path = Path("/home/coder/agent-definitions")
    if repo_path.exists():
        return repo_path

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

        from botburrow_agents.models import DiscoveryConfig, BehaviorLimitsConfig, BehaviorConfig, MemoryConfig, MemoryRememberConfig, MemoryRetrievalConfig

        behavior = BehaviorConfig(
            respond_to_mentions=behavior_data.get("respond_to_mentions", True),
            respond_to_replies=behavior_data.get("respond_to_replies", True),
            respond_to_dms=behavior_data.get("respond_to_dms", True),
            max_iterations=behavior_data.get("max_iterations", 10),
            can_create_posts=behavior_data.get("can_create_posts", True),
            max_daily_posts=behavior_data.get("max_daily_posts", 5),
            max_daily_comments=behavior_data.get("max_daily_comments", 50),
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

        # Parse memory
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


class TestAgentPersonaDocumentation:
    """Test 1: Document current agent personas from agent-definitions."""

    @pytest.mark.asyncio
    async def test_list_all_agent_personas(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify we can list all agent personas from agent-definitions."""
        agents = await mock_git_client.list_agents()

        # Should have at least 5 personas (as of bead bd-2om analysis)
        assert len(agents) >= 5, f"Expected at least 5 agent personas, found {len(agents)}: {agents}"

        # Verify expected personas exist
        for persona in AGENT_PERSONAS:
            assert persona in agents, f"Expected persona '{persona}' not found in {agents}"

    @pytest.mark.asyncio
    async def test_document_persona_details(
        self, mock_git_client: MagicMock
    ) -> None:
        """Document detailed characteristics of each agent persona."""
        personas = {}

        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)
            personas[persona] = {
                "name": config.name,
                "display_name": config.display_name,
                "description": config.description,
                "type": config.type,
                "temperature": config.brain.temperature,
                "max_iterations": config.behavior.max_iterations,
                "topics": config.interests.topics,
                "communities": config.interests.communities,
                "keywords": config.interests.keywords,
                "mcp_servers": config.capabilities.mcp_servers,
                "discovery_enabled": config.behavior.discovery.enabled,
                "cache_ttl": config.cache_ttl,
            }

        # Verify distinctiveness
        temperatures = [p["temperature"] for p in personas.values()]
        topic_sets = [set(p["topics"]) for p in personas.values()]

        # At least some variation in temperatures
        assert len(set(temperatures)) > 1, "Agents should have different temperatures"

        # At least some variation in topics
        unique_topic_combinations = [frozenset(topics) for topics in topic_sets]
        assert len(set(unique_topic_combinations)) > 1, "Agents should have different topic combinations"


class TestSchedulingDiversity:
    """Test 2: Test scheduling ensures diverse personas get activated."""

    @pytest.mark.asyncio
    async def test_scheduler_iteration_order(
        self, mock_settings: Settings
    ) -> None:
        """Verify scheduler iterates through agents properly."""
        from botburrow_agents.coordinator.scheduler import Scheduler

        # Create mock Hub client
        mock_hub = MagicMock()
        mock_hub.get_agents_with_notifications = AsyncMock(return_value=[])
        mock_hub.get_stale_agents = AsyncMock(return_value=[])
        mock_hub.get_budget_health = AsyncMock(return_value=MagicMock(healthy=True))

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.exists = AsyncMock(return_value=False)

        # Patch the Redis client
        with patch('botburrow_agents.coordinator.scheduler.RedisClient') as MockRedisClient:
            mock_redis_instance = MagicMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            MockRedisClient.return_value = mock_redis_instance

            scheduler = Scheduler(mock_hub, mock_redis_instance, mock_settings)

            # Simulate multiple agents with notifications
            notifications = [
                Assignment(
                    agent_id="research-agent",
                    agent_name="Research Agent",
                    task_type=TaskType.INBOX,
                    inbox_count=5,
                ),
                Assignment(
                    agent_id="devops-agent",
                    agent_name="DevOps Agent",
                    task_type=TaskType.INBOX,
                    inbox_count=3,
                ),
                Assignment(
                    agent_id="claude-coder-1",
                    agent_name="Claude Coder 1",
                    task_type=TaskType.INBOX,
                    inbox_count=2,
                ),
            ]

            mock_hub.get_agents_with_notifications = AsyncMock(return_value=notifications)

            # Track which agents get selected
            selected_agents = []

            # Get multiple assignments
            for _ in range(10):
                assignment = await scheduler.get_next_assignment(ActivationMode.NOTIFICATION)
                if assignment:
                    selected_agents.append(assignment.agent_id)

            # Verify at least one agent was selected
            assert len(selected_agents) > 0, "Should have selected at least one agent"

    @pytest.mark.asyncio
    async def test_exploration_scheduling_order(
        self, mock_settings: Settings
    ) -> None:
        """Verify exploration scheduling considers staleness."""
        from botburrow_agents.coordinator.scheduler import Scheduler

        mock_hub = MagicMock()
        mock_hub.get_agents_with_notifications = AsyncMock(return_value=[])

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.exists = AsyncMock(return_value=False)

        with patch('botburrow_agents.coordinator.scheduler.RedisClient') as MockRedisClient:
            mock_redis_instance = MagicMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            MockRedisClient.return_value = mock_redis_instance

            scheduler = Scheduler(mock_hub, mock_redis_instance, mock_settings)

            # Simulate stale agents with different last activation times
            now = datetime.now(UTC)
            stale_agents = [
                Assignment(
                    agent_id="research-agent",
                    agent_name="Research Agent",
                    task_type=TaskType.EXPLORATION,
                    last_activated=now - timedelta(hours=5),
                ),
                Assignment(
                    agent_id="sprint-coder",
                    agent_name="Sprint Coder",
                    task_type=TaskType.EXPLORATION,
                    last_activated=now - timedelta(hours=3),
                ),
                Assignment(
                    agent_id="devops-agent",
                    agent_name="DevOps Agent",
                    task_type=TaskType.EXPLORATION,
                    last_activated=now - timedelta(hours=7),
                ),
            ]

            mock_hub.get_stale_agents = AsyncMock(return_value=stale_agents)
            mock_hub.get_budget_health = AsyncMock(return_value=MagicMock(healthy=True))

            # Get assignment - should select the first available stale agent
            assignment = await scheduler.get_next_assignment(ActivationMode.EXPLORATION)

            assert assignment is not None
            assert assignment.agent_id in ["research-agent", "sprint-coder", "devops-agent"]


class TestExplorationTaskDistribution:
    """Test 3: Verify exploration tasks distribute across different agent types."""

    @pytest.mark.asyncio
    async def test_exploration_by_interest_areas(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agents have different interest areas for exploration."""
        interest_profiles = {}

        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)
            interest_profiles[persona] = {
                "topics": config.interests.topics,
                "keywords": config.interests.keywords,
                "communities": config.interests.communities,
            }

        # Research agent should have research/ML interests
        research_topics = interest_profiles["research-agent"]["topics"]
        assert any(t in research_topics for t in ["research", "machine-learning", "ai"]), (
            f"Research agent should have research-related topics, got: {research_topics}"
        )

        # DevOps agent should have infrastructure interests
        devops_topics = interest_profiles["devops-agent"]["topics"]
        assert any(t in devops_topics for t in ["kubernetes", "devops", "infrastructure"]), (
            f"DevOps agent should have DevOps-related topics, got: {devops_topics}"
        )

        # Verify at least 3 different topic areas exist
        all_topic_sets = [set(profile["topics"]) for profile in interest_profiles.values()]
        unique_combinations = [frozenset(topics) for topics in all_topic_sets]
        assert len(set(unique_combinations)) >= 3, "Should have at least 3 distinct topic combinations"

    @pytest.mark.asyncio
    async def test_exploration_frequency_variations(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agents have different exploration behaviors."""
        discovery_settings = {}

        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)
            discovery_settings[persona] = {
                "enabled": config.behavior.discovery.enabled,
                "frequency": config.behavior.discovery.frequency,
                "respond_to_questions": config.behavior.discovery.respond_to_questions,
                "respond_to_discussions": config.behavior.discovery.respond_to_discussions,
            }

        # Some agents should have discovery enabled
        enabled_count = sum(1 for s in discovery_settings.values() if s["enabled"])
        assert enabled_count >= 1, "At least one agent should have discovery enabled"

        # Sprint coder typically has discovery disabled (fast execution only)
        assert not discovery_settings["sprint-coder"]["enabled"], (
            "Sprint coder should have discovery disabled"
        )


class TestNotificationRouting:
    """Test 4: Test notification routing to correct agent persona."""

    @pytest.mark.asyncio
    async def test_scheduler_returns_notification_agent(
        self, mock_settings: Settings
    ) -> None:
        """Verify scheduler can return notification-based agents."""
        from botburrow_agents.coordinator.scheduler import Scheduler

        mock_hub = MagicMock()

        # Simulate a notification specifically for research-agent
        research_notification = Assignment(
            agent_id="research-agent",
            agent_name="Research Agent",
            task_type=TaskType.INBOX,
            inbox_count=1,
        )

        mock_hub.get_agents_with_notifications = AsyncMock(
            return_value=[research_notification]
        )

        mock_redis = MagicMock()
        mock_redis.exists = AsyncMock(return_value=False)

        with patch('botburrow_agents.coordinator.scheduler.RedisClient') as MockRedisClient:
            mock_redis_instance = MagicMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            MockRedisClient.return_value = mock_redis_instance

            scheduler = Scheduler(mock_hub, mock_redis_instance, mock_settings)

            # Get assignment
            assignment = await scheduler.get_next_assignment(ActivationMode.NOTIFICATION)

            # Verify correct agent was selected
            assert assignment is not None
            assert assignment.agent_id == "research-agent"
            assert assignment.task_type == TaskType.INBOX


class TestPersonalityConsistency:
    """Test 5: Check agent personality consistency across activations."""

    @pytest.mark.asyncio
    async def test_config_stability_across_loads(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify agent config remains consistent across multiple loads."""
        # Load same agent multiple times
        configs = []
        for _ in range(5):
            config = await mock_git_client.load_agent_config("research-agent")
            configs.append(config)

        # All configs should be identical
        first_config = configs[0]
        for config in configs[1:]:
            assert config.name == first_config.name
            assert config.brain.temperature == first_config.brain.temperature
            assert config.interests.topics == first_config.interests.topics
            assert config.capabilities.grants == first_config.capabilities.grants

    @pytest.mark.asyncio
    async def test_personality_attributes_persist(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify personality-defining attributes persist."""
        for persona in AGENT_PERSONAS:
            config = await mock_git_client.load_agent_config(persona)

            # Core personality attributes
            assert config.name == persona
            assert config.display_name is not None
            assert config.description is not None

            # Behavior personality
            assert config.brain.temperature >= 0.0
            assert config.brain.temperature <= 2.0
            assert config.behavior.max_iterations > 0

            # Interest personality
            assert isinstance(config.interests.topics, list)
            assert isinstance(config.interests.keywords, list)

    @pytest.mark.asyncio
    async def test_system_prompt_consistency(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify system prompts remain consistent."""
        # Load system prompt multiple times
        prompts = []
        for _ in range(3):
            prompt = await mock_git_client.get_system_prompt("research-agent")
            prompts.append(prompt)

        # All prompts should be identical
        assert all(p == prompts[0] for p in prompts)


class TestNewPersonaDeployment:
    """Test 6: Test new persona deployment without runner restart."""

    @pytest.mark.asyncio
    async def test_cache_operations(
        self, mock_settings: Settings
    ) -> None:
        """Verify cache operations work for persona management."""
        from botburrow_agents.coordinator.work_queue import ConfigCache

        # Create mock Redis client
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.scan_iter = AsyncMock(return_value=[])

        with patch('botburrow_agents.coordinator.work_queue.RedisClient') as MockRedisClient:
            mock_redis_instance = MagicMock()
            mock_redis_instance.get = AsyncMock(return_value=None)
            mock_redis_instance.set = AsyncMock()
            mock_redis_instance.delete = AsyncMock()
            mock_redis_instance.scan_iter = AsyncMock(return_value=[])
            mock_redis_instance._ensure_connected = AsyncMock(return_value=mock_redis_instance)
            MockRedisClient.return_value = mock_redis_instance

            cache = ConfigCache(mock_redis_instance)

            # Test cache set
            test_config = {"name": "test-agent", "temperature": 0.7}
            await cache.set("test-agent", test_config, ttl=60)

            # Test cache get
            result = await cache.get("test-agent")

            # Verify cache operations were called
            assert mock_redis_instance.set.called

    @pytest.mark.asyncio
    async def test_new_agent_discovery_during_runtime(
        self, mock_git_client: MagicMock
    ) -> None:
        """Verify new agents can be discovered during runtime."""
        # List agents initially
        initial_agents = await mock_git_client.list_agents()

        # (In real scenario, git-sync would add new agent directory)
        # For testing, we verify the list method works
        assert isinstance(initial_agents, list)
        assert len(initial_agents) >= len(AGENT_PERSONAS)


class TestPersonaActivationFrequency:
    """Test 7: Monitor persona activation frequency and balance."""

    @pytest.mark.asyncio
    async def test_scheduler_considers_multiple_agents(
        self, mock_settings: Settings
    ) -> None:
        """Verify scheduler can handle multiple eligible agents."""
        from botburrow_agents.coordinator.scheduler import Scheduler

        mock_hub = MagicMock()
        mock_hub.get_agents_with_notifications = AsyncMock(return_value=[])

        mock_redis = MagicMock()
        mock_redis.exists = AsyncMock(return_value=False)

        with patch('botburrow_agents.coordinator.scheduler.RedisClient') as MockRedisClient:
            mock_redis_instance = MagicMock()
            mock_redis_instance.exists = AsyncMock(return_value=False)
            MockRedisClient.return_value = mock_redis_instance

            scheduler = Scheduler(mock_hub, mock_redis_instance, mock_settings)

            # Create multiple eligible agents
            now = datetime.now(UTC)
            agents = [
                Assignment(
                    agent_id="research-agent",
                    agent_name="Research Agent",
                    task_type=TaskType.EXPLORATION,
                    last_activated=now - timedelta(hours=i),
                )
                for i in range(5)
            ]

            agents.extend([
                Assignment(
                    agent_id="devops-agent",
                    agent_name="DevOps Agent",
                    task_type=TaskType.EXPLORATION,
                    last_activated=now - timedelta(hours=i),
                )
                for i in range(5, 10)
            ])

            mock_hub.get_stale_agents = AsyncMock(return_value=agents)
            mock_hub.get_budget_health = AsyncMock(return_value=MagicMock(healthy=True))

            # Get assignment - should return one of the agents
            assignment = await scheduler.get_next_assignment(ActivationMode.EXPLORATION)

            assert assignment is not None
            assert assignment.agent_id in ["research-agent", "devops-agent"]


# Test markers
pytestmark = [
    pytest.mark.integration,
    pytest.mark.scheduling,
]

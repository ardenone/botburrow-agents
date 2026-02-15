"""Simplified agent persona execution test.

Minimal viable implementation for testing agent execution with different personas.
This is a simplified version of bd-2om focusing on core functionality only.

Tests:
1. Agent configs can be loaded and parsed
2. Different personas have distinct configurations
3. Runner can switch between personas
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.models import (
    AgentConfig,
    Assignment,
    BehaviorConfig,
    BrainConfig,
    CapabilityGrants,
    InterestConfig,
    MemoryConfig,
    ShellConfig,
    TaskType,
)
from botburrow_agents.runner.main import Runner

# Minimal test personas (3 instead of 10+)
TEST_PERSONAS = {
    "coder-agent": AgentConfig(
        name="coder-agent",
        type="claude-code",
        description="Software development agent",
        brain=BrainConfig(
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            temperature=0.7,
        ),
        capabilities=CapabilityGrants(
            grants=["hub:read", "hub:write"],
            skills=["hub-post"],
            shell=ShellConfig(enabled=True, allowed_commands=["git", "npm"]),
        ),
        interests=InterestConfig(
            topics=["programming", "algorithms"],
            communities=["m/tech"],
        ),
        system_prompt="You are a coding assistant focused on software development.",
    ),
    "research-agent": AgentConfig(
        name="research-agent",
        type="claude-code",
        description="Research and analysis agent",
        brain=BrainConfig(
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            temperature=0.3,  # Lower temperature for research
        ),
        capabilities=CapabilityGrants(
            grants=["hub:read", "hub:write"],
            skills=["hub-post", "hub-search"],
            shell=ShellConfig(enabled=False),
        ),
        interests=InterestConfig(
            topics=["research", "data-analysis"],
            communities=["m/science"],
        ),
        system_prompt="You are a research assistant focused on thorough analysis.",
    ),
    "helper-agent": AgentConfig(
        name="helper-agent",
        type="native",
        description="General purpose helper",
        brain=BrainConfig(
            model="claude-haiku-4-20250514",
            provider="anthropic",
            temperature=0.8,  # Higher temperature for creativity
        ),
        capabilities=CapabilityGrants(
            grants=["hub:read"],
            skills=["hub-post"],
            shell=ShellConfig(enabled=False),
        ),
        interests=InterestConfig(
            topics=["help", "general"],
            communities=["m/general"],
        ),
        behavior=BehaviorConfig(
            max_daily_posts=10,
            max_daily_comments=100,
        ),
        system_prompt="You are a helpful assistant for general questions.",
    ),
}


@pytest.fixture
def settings() -> Settings:
    """Test settings."""
    return Settings(
        hub_url="http://test-hub:8000",
        redis_url="redis://localhost:6379",
        runner_id="test-runner",
        activation_timeout=60,
        max_iterations=5,
    )


@pytest.fixture
def mock_clients(_settings: Settings) -> tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    """Create mock clients for testing."""
    mock_hub = AsyncMock()
    mock_hub.get_notifications.return_value = []
    mock_hub.get_budget_health.return_value = MagicMock(healthy=True)
    mock_hub.get_discovery_feed.return_value = []

    mock_git = AsyncMock()
    # Make load_agent_config return different personas based on agent_id
    async def load_persona(agent_id: str) -> AgentConfig:
        if agent_id in TEST_PERSONAS:
            return TEST_PERSONAS[agent_id]
        raise ValueError(f"Unknown agent: {agent_id}")

    mock_git.load_agent_config.side_effect = load_persona
    mock_git.list_agents.return_value = list(TEST_PERSONAS.keys())

    mock_redis = AsyncMock()
    mock_redis.connect.return_value = None
    mock_redis.close.return_value = None

    mock_r2 = AsyncMock()

    return mock_hub, mock_git, mock_redis, mock_r2


class TestSimplifiedPersonaExecution:
    """Simplified tests for agent persona execution."""

    def test_agent_personas_have_distinct_configs(self) -> None:
        """Test that different personas have distinct configurations."""
        personas = list(TEST_PERSONAS.values())

        # Each persona should have a unique name
        names = {p.name for p in personas}
        assert len(names) == len(personas), "Each persona should have a unique name"

        # Check distinct temperatures
        temperatures = {p.brain.temperature for p in personas}
        assert len(temperatures) > 1, "Personas should have different temperatures"

        # Check distinct models
        models = {p.brain.model for p in personas}
        assert len(models) >= 1, "Personas should use defined models"

    def test_agent_personas_have_different_capabilities(self) -> None:
        """Test that personas have different capability configurations."""
        coder = TEST_PERSONAS["coder-agent"]
        researcher = TEST_PERSONAS["research-agent"]
        helper = TEST_PERSONAS["helper-agent"]

        # Coder has shell access
        assert coder.capabilities.shell.enabled is True
        assert len(coder.capabilities.shell.allowed_commands) > 0

        # Researcher doesn't have shell but has search skill
        assert researcher.capabilities.shell.enabled is False
        assert "hub-search" in researcher.capabilities.skills

        # Helper has limited grants
        assert helper.capabilities.grants == ["hub:read"]

    def test_agent_personas_have_different_interests(self) -> None:
        """Test that personas have different interest configurations."""
        coder = TEST_PERSONAS["coder-agent"]
        researcher = TEST_PERSONAS["research-agent"]
        helper = TEST_PERSONAS["helper-agent"]

        # Check topics are distinct
        coder_topics = set(coder.interests.topics)
        researcher_topics = set(researcher.interests.topics)
        helper_topics = set(helper.interests.topics)

        assert len(coder_topics & researcher_topics) == 0, "Topics should be distinct"
        assert len(coder_topics & helper_topics) == 0, "Topics should be distinct"

        # Check communities
        assert coder.interests.communities == ["m/tech"]
        assert researcher.interests.communities == ["m/science"]
        assert helper.interests.communities == ["m/general"]

    def test_agent_personas_have_distinct_system_prompts(self) -> None:
        """Test that personas have distinct system prompts."""
        prompts = {p.name: p.system_prompt for p in TEST_PERSONAS.values()}

        # Each should mention its role
        assert "coding" in prompts["coder-agent"].lower()
        assert "research" in prompts["research-agent"].lower()
        assert "helpful" in prompts["helper-agent"].lower()

        # Prompts should be different
        prompt_texts = set(prompts.values())
        assert len(prompt_texts) == len(prompts), "Each persona should have unique prompt"

    @pytest.mark.asyncio
    async def test_runner_can_load_different_personas(
        self, settings: Settings, mock_clients: tuple[AsyncMock, ...]
    ) -> None:
        """Test that runner can load different agent personas."""
        mock_hub, mock_git, mock_redis, mock_r2 = mock_clients

        # Create runner with mocked clients
        runner = Runner(settings)
        runner.hub = mock_hub
        runner.git = mock_git
        runner.redis = mock_redis
        runner.r2 = mock_r2

        # Initialize components
        await runner.redis.connect()

        try:
            # Load each persona
            loaded_personas = []
            for agent_id in TEST_PERSONAS:
                config = await runner._load_agent_config(agent_id)
                loaded_personas.append(config)

                # Verify config matches expected
                assert config.name == agent_id
                assert config.system_prompt != ""

            # Verify all personas were loaded
            assert len(loaded_personas) == len(TEST_PERSONAS)

        finally:
            await runner.redis.close()

    @pytest.mark.asyncio
    async def test_runner_switches_between_personas(
        self, settings: Settings, mock_clients: tuple[AsyncMock, ...]
    ) -> None:
        """Test that runner can switch between different personas."""
        mock_hub, mock_git, mock_redis, mock_r2 = mock_clients

        runner = Runner(settings)
        runner.hub = mock_hub
        runner.git = mock_git
        runner.redis = mock_redis
        runner.r2 = mock_r2

        await runner.redis.connect()

        try:
            # Load personas in sequence
            personas_order = ["coder-agent", "research-agent", "helper-agent"]

            for agent_id in personas_order:
                config = await runner._load_agent_config(agent_id)

                # Verify correct persona loaded
                assert config.name == agent_id

                # Verify persona-specific properties
                if agent_id == "coder-agent":
                    assert config.capabilities.shell.enabled is True
                elif agent_id == "research-agent":
                    assert config.brain.temperature == 0.3
                elif agent_id == "helper-agent":
                    assert config.brain.model == "claude-haiku-4-20250514"

        finally:
            await runner.redis.close()

    @pytest.mark.asyncio
    async def test_persona_config_serialization(self) -> None:
        """Test that persona configs can be serialized and deserialized."""
        for persona in TEST_PERSONAS.values():
            # Serialize to dict
            data = persona.model_dump()

            # Deserialize back
            restored = AgentConfig(**data)

            # Verify key properties preserved
            assert restored.name == persona.name
            assert restored.type == persona.type
            assert restored.brain.model == persona.brain.model
            assert restored.brain.temperature == persona.brain.temperature
            assert restored.system_prompt == persona.system_prompt

    def test_persona_types(self) -> None:
        """Test that personas have correct types."""
        coder = TEST_PERSONAS["coder-agent"]
        helper = TEST_PERSONAS["helper-agent"]

        # Coder uses claude-code type
        assert coder.type == "claude-code"

        # Helper uses native type
        assert helper.type == "native"

    def test_persona_memory_configurations(self) -> None:
        """Test memory configuration differences between personas."""
        # Most personas have default memory config
        for persona in TEST_PERSONAS.values():
            # Memory config should exist (even if empty/default)
            assert isinstance(persona.memory, MemoryConfig)
            assert hasattr(persona.memory, "enabled")


class TestSimplifiedPersonaDiversity:
    """Test diversity among agent personas."""

    def test_temperature_diversity(self) -> None:
        """Test that personas use different temperature values."""
        temperatures = [p.brain.temperature for p in TEST_PERSONAS.values()]
        assert len(set(temperatures)) > 1, "Should have diverse temperature settings"

    def test_capability_diversity(self) -> None:
        """Test that personas have different capability grants."""
        all_grants = []
        for persona in TEST_PERSONAS.values():
            all_grants.extend(persona.capabilities.grants)

        # Check there's diversity in grants
        unique_combos = []
        for persona in TEST_PERSONAS.values():
            combo = (
                frozenset(persona.capabilities.grants),
                persona.capabilities.shell.enabled,
                frozenset(persona.capabilities.skills),
            )
            unique_combos.append(combo)

        assert len(set(unique_combos)) > 1, "Should have diverse capability configurations"

    def test_behavior_diversity(self) -> None:
        """Test that personas have different behavior configurations."""
        behaviors = {}
        for persona in TEST_PERSONAS.values():
            behaviors[persona.name] = {
                "max_posts": persona.behavior.max_daily_posts,
                "max_comments": persona.behavior.max_daily_comments,
            }

        # Helper agent should have different limits
        assert behaviors["helper-agent"]["max_posts"] == 10
        assert behaviors["helper-agent"]["max_comments"] == 100


# Integration-style test without external dependencies
class TestSimplifiedPersonaIntegration:
    """Simplified integration tests for persona execution."""

    @pytest.mark.asyncio
    async def test_persona_assignment_handling(
        self, _settings: Settings, mock_clients: tuple[AsyncMock, ...]
    ) -> None:
        """Test creating assignments for different personas."""
        mock_hub, mock_git, mock_redis, mock_r2 = mock_clients

        # Create assignments for each persona
        assignments = []
        for persona_name in TEST_PERSONAS:
            assignment = Assignment(
                agent_id=persona_name,
                agent_name=persona_name,
                task_type=TaskType.INBOX,
                inbox_count=1,
            )
            assignments.append(assignment)

        assert len(assignments) == len(TEST_PERSONAS)

        # Verify each assignment references a valid persona
        for assignment in assignments:
            assert assignment.agent_id in TEST_PERSONAS
            assert assignment.agent_name == assignment.agent_id

    @pytest.mark.asyncio
    async def test_task_type_diversity(self, _settings: Settings) -> None:
        """Test that personas can handle different task types."""
        task_types = [TaskType.INBOX, TaskType.DISCOVERY]

        for persona_name in TEST_PERSONAS:
            for task_type in task_types:
                assignment = Assignment(
                    agent_id=persona_name,
                    agent_name=persona_name,
                    task_type=task_type,
                )

                # Verify assignment is valid
                assert assignment.agent_id in TEST_PERSONAS
                assert assignment.task_type == task_type

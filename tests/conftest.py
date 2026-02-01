"""Pytest fixtures for botburrow-agents tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest
from fakeredis import aioredis as fakeredis

from botburrow_agents.config import Settings
from botburrow_agents.models import (
    AgentConfig,
    Assignment,
    BehaviorConfig,
    BrainConfig,
    CapabilityGrants,
    Notification,
    NotificationType,
    Post,
    TaskType,
    Thread,
)


@pytest.fixture
def settings() -> Settings:
    """Test settings."""
    return Settings(
        hub_url="http://test-hub:8000",
        hub_api_key="test-key",
        redis_url="redis://localhost:6379",
        r2_endpoint="https://test.r2.cloudflarestorage.com",
        r2_access_key="test-access",
        r2_secret_key="test-secret",
        r2_bucket="test-bucket",
        runner_id="test-runner-1",
        poll_interval=5,
        activation_timeout=60,
        max_iterations=5,
    )


@pytest.fixture
def agent_config() -> AgentConfig:
    """Test agent configuration."""
    return AgentConfig(
        name="test-agent",
        type="claude-code",
        brain=BrainConfig(
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            temperature=0.7,
            max_tokens=4096,
        ),
        capabilities=CapabilityGrants(
            grants=["hub:read", "hub:write", "github:read"],
            skills=["hub-post", "hub-search"],
            mcp_servers=["hub", "github"],
        ),
        behavior=BehaviorConfig(
            respond_to_mentions=True,
            respond_to_replies=True,
            max_iterations=10,
            can_create_posts=True,
        ),
        system_prompt="You are test-agent, a helpful assistant.",
    )


@pytest.fixture
def assignment(agent_config: AgentConfig) -> Assignment:
    """Test assignment."""
    return Assignment(
        agent_id=agent_config.name,
        agent_name=agent_config.name,
        task_type=TaskType.INBOX,
        inbox_count=5,
    )


@pytest.fixture
def notification() -> Notification:
    """Test notification."""
    from datetime import datetime

    return Notification(
        id="notif-123",
        type=NotificationType.MENTION,
        post_id="post-456",
        from_agent="other-agent",
        from_agent_name="Other Agent",
        content="@test-agent What do you think about this?",
        created_at=datetime.now(UTC),
        read=False,
    )


@pytest.fixture
def post() -> Post:
    """Test post."""
    from datetime import datetime

    return Post(
        id="post-456",
        author_id="other-agent",
        author_name="Other Agent",
        title="Test Post",
        content="This is a test post with @test-agent mention.",
        community="m/general",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def thread(post: Post) -> Thread:
    """Test thread."""
    from datetime import datetime

    comment = Post(
        id="comment-789",
        author_id="commenter",
        author_name="Commenter",
        content="I agree!",
        parent_id=post.id,
        created_at=datetime.now(UTC),
    )
    return Thread(root=post, comments=[comment])


@pytest.fixture
def mock_hub_client() -> AsyncMock:
    """Mock HubClient."""
    mock = AsyncMock()
    mock.get_notifications.return_value = []
    mock.get_agents_with_notifications.return_value = []
    mock.get_stale_agents.return_value = []
    mock.get_budget_health.return_value = MagicMock(healthy=True)
    return mock


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Mock RedisClient."""
    mock = AsyncMock()
    mock.connect.return_value = None
    mock.close.return_value = None
    mock.exists.return_value = False
    mock.set.return_value = True
    mock.get.return_value = None
    mock.delete.return_value = 1
    return mock


@pytest.fixture
def mock_r2_client(agent_config: AgentConfig) -> AsyncMock:
    """Mock R2Client."""
    mock = AsyncMock()
    mock.load_agent_config.return_value = agent_config
    mock.list_skills.return_value = ["hub-post", "hub-search"]
    return mock


@pytest.fixture
def mock_git_client(agent_config: AgentConfig) -> AsyncMock:
    """Mock GitClient."""
    mock = AsyncMock()
    mock.load_agent_config.return_value = agent_config
    mock.list_skills.return_value = ["hub-post", "hub-search"]
    mock.list_agents.return_value = ["test-agent"]
    mock.get_skill.return_value = "# Test Skill\n\nInstructions here."
    mock.get_system_prompt.return_value = agent_config.system_prompt
    mock.use_local = False
    return mock


@pytest.fixture
async def fake_redis() -> AsyncGenerator[fakeredis.FakeRedis, None]:
    """Fake Redis for testing with Lua scripting support."""
    # Enable Lua scripting for eval/evalsha commands used in locks
    try:
        # Try with lupa-based Lua support
        import lupa  # noqa: F401
        redis = fakeredis.FakeRedis(decode_responses=True)
    except ImportError:
        # Fall back to fakeredis without Lua - some lock tests will be skipped
        redis = fakeredis.FakeRedis(decode_responses=True)
    yield redis
    await redis.aclose()

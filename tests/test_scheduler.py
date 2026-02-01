"""Tests for scheduler module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from botburrow_agents.config import ActivationMode
from botburrow_agents.coordinator.scheduler import PriorityQueue, Scheduler
from botburrow_agents.models import Assignment, TaskType


class TestScheduler:
    """Tests for Scheduler class."""

    @pytest.fixture
    def scheduler(self, settings, mock_hub_client, mock_redis_client):
        """Create scheduler with mocks."""
        return Scheduler(
            hub=mock_hub_client,
            redis=mock_redis_client,
            settings=settings,
        )

    @pytest.mark.asyncio
    async def test_get_notification_assignment(
        self, scheduler, mock_hub_client
    ):
        """Test getting notification assignment."""
        mock_hub_client.get_agents_with_notifications.return_value = [
            Assignment(
                agent_id="agent-1",
                agent_name="Agent One",
                task_type=TaskType.INBOX,
                inbox_count=5,
            ),
        ]

        assignment = await scheduler.get_next_assignment(ActivationMode.NOTIFICATION)

        assert assignment is not None
        assert assignment.agent_id == "agent-1"
        assert assignment.task_type == TaskType.INBOX

    @pytest.mark.asyncio
    async def test_get_exploration_assignment(
        self, scheduler, mock_hub_client
    ):
        """Test getting exploration assignment."""
        mock_hub_client.get_agents_with_notifications.return_value = []
        mock_hub_client.get_stale_agents.return_value = [
            Assignment(
                agent_id="agent-2",
                agent_name="Agent Two",
                task_type=TaskType.DISCOVERY,
                last_activated=datetime.now(UTC) - timedelta(hours=2),
            ),
        ]

        assignment = await scheduler.get_next_assignment(ActivationMode.EXPLORATION)

        assert assignment is not None
        assert assignment.agent_id == "agent-2"
        assert assignment.task_type == TaskType.DISCOVERY

    @pytest.mark.asyncio
    async def test_hybrid_prefers_notifications(
        self, scheduler, mock_hub_client
    ):
        """Test hybrid mode prefers notifications over exploration."""
        mock_hub_client.get_agents_with_notifications.return_value = [
            Assignment(
                agent_id="notif-agent",
                agent_name="Notification Agent",
                task_type=TaskType.INBOX,
                inbox_count=3,
            ),
        ]
        mock_hub_client.get_stale_agents.return_value = [
            Assignment(
                agent_id="stale-agent",
                agent_name="Stale Agent",
                task_type=TaskType.DISCOVERY,
            ),
        ]

        assignment = await scheduler.get_next_assignment(ActivationMode.HYBRID)

        assert assignment.agent_id == "notif-agent"
        assert assignment.task_type == TaskType.INBOX

    @pytest.mark.asyncio
    async def test_hybrid_falls_back_to_exploration(
        self, scheduler, mock_hub_client
    ):
        """Test hybrid falls back to exploration when no notifications."""
        mock_hub_client.get_agents_with_notifications.return_value = []
        mock_hub_client.get_stale_agents.return_value = [
            Assignment(
                agent_id="stale-agent",
                agent_name="Stale Agent",
                task_type=TaskType.DISCOVERY,
            ),
        ]

        assignment = await scheduler.get_next_assignment(ActivationMode.HYBRID)

        assert assignment.agent_id == "stale-agent"
        assert assignment.task_type == TaskType.DISCOVERY

    @pytest.mark.asyncio
    async def test_skips_locked_agents(
        self, scheduler, mock_hub_client, mock_redis_client
    ):
        """Test skips agents that are already locked."""
        mock_hub_client.get_agents_with_notifications.return_value = [
            Assignment(
                agent_id="locked-agent",
                agent_name="Locked Agent",
                task_type=TaskType.INBOX,
                inbox_count=1,
            ),
            Assignment(
                agent_id="available-agent",
                agent_name="Available Agent",
                task_type=TaskType.INBOX,
                inbox_count=1,
            ),
        ]

        # First agent is locked
        mock_redis_client.exists.side_effect = [True, False]

        assignment = await scheduler.get_next_assignment(ActivationMode.NOTIFICATION)

        assert assignment.agent_id == "available-agent"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_work(
        self, scheduler, mock_hub_client
    ):
        """Test returns None when no work available."""
        mock_hub_client.get_agents_with_notifications.return_value = []
        mock_hub_client.get_stale_agents.return_value = []

        assignment = await scheduler.get_next_assignment(ActivationMode.HYBRID)

        assert assignment is None

    @pytest.mark.asyncio
    async def test_queue_stats(self, scheduler, mock_hub_client):
        """Test queue statistics."""
        mock_hub_client.get_agents_with_notifications.return_value = [
            Assignment(agent_id="a1", agent_name="A1", task_type=TaskType.INBOX),
            Assignment(agent_id="a2", agent_name="A2", task_type=TaskType.INBOX),
        ]
        mock_hub_client.get_stale_agents.return_value = [
            Assignment(agent_id="a3", agent_name="A3", task_type=TaskType.DISCOVERY),
        ]

        stats = await scheduler.get_queue_stats()

        assert stats["notification_queue"] == 2
        assert stats["exploration_queue"] == 1


class TestSchedulerDailyLimits:
    """Tests for daily limit checking."""

    @pytest.fixture
    def scheduler(self, settings, mock_hub_client, mock_redis_client):
        """Create scheduler with mocks."""
        return Scheduler(
            hub=mock_hub_client,
            redis=mock_redis_client,
            settings=settings,
        )

    @pytest.mark.asyncio
    async def test_skips_over_budget_agent(
        self, scheduler, mock_hub_client, mock_redis_client
    ):
        """Test skips agents that are over budget."""
        mock_hub_client.get_stale_agents.return_value = [
            Assignment(
                agent_id="budget-agent",
                agent_name="Budget Agent",
                task_type=TaskType.DISCOVERY,
            ),
        ]
        mock_hub_client.get_budget_health.return_value = AsyncMock(healthy=False)
        mock_redis_client.exists.return_value = False

        assignment = await scheduler.get_next_assignment(ActivationMode.EXPLORATION)

        assert assignment is None
        mock_hub_client.get_budget_health.assert_called_once_with("budget-agent")

    @pytest.mark.asyncio
    async def test_allows_agent_when_budget_check_fails(
        self, scheduler, mock_hub_client, mock_redis_client
    ):
        """Test allows agent when budget check errors."""
        mock_hub_client.get_stale_agents.return_value = [
            Assignment(
                agent_id="error-agent",
                agent_name="Error Agent",
                task_type=TaskType.DISCOVERY,
            ),
        ]
        mock_hub_client.get_budget_health.side_effect = Exception("API error")
        mock_redis_client.exists.return_value = False

        assignment = await scheduler.get_next_assignment(ActivationMode.EXPLORATION)

        # Should still allow the agent when budget check fails
        assert assignment is not None
        assert assignment.agent_id == "error-agent"


class TestPriorityQueue:
    """Tests for PriorityQueue."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Mock Redis client."""
        mock = AsyncMock()
        mock._ensure_connected = AsyncMock(return_value=mock)
        mock.zadd = AsyncMock()
        mock.zpopmin = AsyncMock()
        mock.zrem = AsyncMock()
        mock.zcard = AsyncMock()
        return mock

    @pytest.fixture
    def queue(self, mock_redis: AsyncMock) -> PriorityQueue:
        """Create PriorityQueue with mock."""
        return PriorityQueue(mock_redis)

    @pytest.mark.asyncio
    async def test_add_notification(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test adding to notification queue."""
        await queue.add_notification("agent-1", 5)

        mock_redis.zadd.assert_called_once()
        call_args = mock_redis.zadd.call_args
        assert call_args[0][0] == "queue:notifications"
        # Score should be -5 (higher inbox = higher priority)
        assert call_args[0][1] == {"agent-1": -5}

    @pytest.mark.asyncio
    async def test_add_exploration_with_timestamp(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test adding to exploration queue with last activated time."""
        last_activated = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        await queue.add_exploration("agent-2", last_activated)

        mock_redis.zadd.assert_called_once()
        call_args = mock_redis.zadd.call_args
        assert call_args[0][0] == "queue:exploration"
        # Score should be timestamp
        assert call_args[0][1] == {"agent-2": last_activated.timestamp()}

    @pytest.mark.asyncio
    async def test_add_exploration_never_activated(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test adding to exploration queue when never activated."""
        await queue.add_exploration("agent-3", None)

        mock_redis.zadd.assert_called_once()
        call_args = mock_redis.zadd.call_args
        # Score should be 0 (highest priority)
        assert call_args[0][1] == {"agent-3": 0}

    @pytest.mark.asyncio
    async def test_pop_notification(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test popping from notification queue."""
        mock_redis.zpopmin.return_value = [("agent-1", -5)]

        result = await queue.pop_notification()

        assert result == "agent-1"
        mock_redis.zpopmin.assert_called_once_with("queue:notifications")

    @pytest.mark.asyncio
    async def test_pop_notification_empty(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test popping from empty notification queue."""
        mock_redis.zpopmin.return_value = []

        result = await queue.pop_notification()

        assert result is None

    @pytest.mark.asyncio
    async def test_pop_exploration(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test popping from exploration queue."""
        mock_redis.zpopmin.return_value = [("agent-2", 0)]

        result = await queue.pop_exploration()

        assert result == "agent-2"
        mock_redis.zpopmin.assert_called_once_with("queue:exploration")

    @pytest.mark.asyncio
    async def test_remove(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test removing agent from all queues."""
        await queue.remove("agent-1")

        assert mock_redis.zrem.call_count == 2
        mock_redis.zrem.assert_any_call("queue:notifications", "agent-1")
        mock_redis.zrem.assert_any_call("queue:exploration", "agent-1")

    @pytest.mark.asyncio
    async def test_get_queue_lengths(
        self,
        queue: PriorityQueue,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting queue lengths."""
        mock_redis.zcard.side_effect = [10, 5]

        notif_len, explore_len = await queue.get_queue_lengths()

        assert notif_len == 10
        assert explore_len == 5
        mock_redis.zcard.assert_any_call("queue:notifications")
        mock_redis.zcard.assert_any_call("queue:exploration")

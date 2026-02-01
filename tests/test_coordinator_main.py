"""Tests for coordinator main module.

Tests the Coordinator class, including:
- Startup and shutdown
- Leader election
- Polling loops
- Health checks
- Stats logging
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.coordinator.main import Coordinator


class TestCoordinatorInit:
    """Tests for Coordinator initialization."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            redis_url="redis://localhost:6379",
            poll_interval=30,
        )

    def test_coordinator_init_with_settings(self, settings: Settings) -> None:
        """Test coordinator initialization with settings."""
        coordinator = Coordinator(settings)
        assert coordinator.settings == settings
        assert coordinator.instance_id
        assert coordinator._running is False

    def test_coordinator_init_without_settings(self) -> None:
        """Test coordinator initialization without settings uses defaults."""
        coordinator = Coordinator()
        assert coordinator.settings is not None
        assert coordinator.settings.hub_url == "http://localhost:8000"

    def test_coordinator_components_initialized(self, settings: Settings) -> None:
        """Test that coordinator components are initialized."""
        coordinator = Coordinator(settings)
        assert coordinator.hub is not None
        assert coordinator.redis is not None
        assert coordinator.r2 is not None
        assert coordinator.scheduler is not None
        assert coordinator.assigner is not None


class TestCoordinatorSetupLogging:
    """Tests for logging setup."""

    def test_setup_logging_does_not_raise(self) -> None:
        """Test that setup_logging completes without errors."""
        from botburrow_agents.coordinator.main import setup_logging
        setup_logging()  # Should not raise


class TestCoordinatorShutdown:
    """Tests for coordinator shutdown handling."""

    @pytest.fixture
    def coordinator(self, settings: Settings) -> Coordinator:
        """Create test coordinator."""
        return Coordinator(settings)

    def test_handle_shutdown_sets_flags(self, coordinator: Coordinator) -> None:
        """Test that shutdown handler sets flags correctly."""
        coordinator._running = True
        coordinator._handle_shutdown()
        assert coordinator._running is False
        assert coordinator._shutdown_event.is_set()


class TestCoordinatorPoll:
    """Tests for polling functionality."""

    @pytest.fixture
    def coordinator(self, settings: Settings) -> Coordinator:
        """Create test coordinator."""
        return Coordinator(settings)

    @pytest.mark.asyncio
    async def test_enqueue_work_with_work_queue(
        self, coordinator: Coordinator
    ) -> None:
        """Test enqueuing work with WorkQueue."""
        from botburrow_agents.models import Assignment, TaskType

        # Mock the work queue
        coordinator.work_queue = AsyncMock()
        coordinator.work_queue.enqueue = AsyncMock(return_value=True)

        assignment = Assignment(
            agent_id="test-agent",
            agent_name="Test Agent",
            task_type=TaskType.INBOX,
        )

        await coordinator._enqueue_work(assignment, priority="high")

        coordinator.work_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_work_without_work_queue(
        self, coordinator: Coordinator
    ) -> None:
        """Test enqueuing work without WorkQueue logs warning."""
        from botburrow_agents.models import Assignment, TaskType

        coordinator.work_queue = None
        assignment = Assignment(
            agent_id="test-agent",
            agent_name="Test Agent",
            task_type=TaskType.INBOX,
        )

        # Should not raise, just log
        await coordinator._enqueue_work(assignment, priority="high")


class TestGetAssignment:
    """Tests for get_assignment method."""

    @pytest.fixture
    def coordinator(self, settings: Settings) -> Coordinator:
        """Create test coordinator."""
        return Coordinator(settings)

    @pytest.mark.asyncio
    async def test_get_assignment_returns_assignment(
        self, coordinator: Coordinator
    ) -> None:
        """Test get_assignment returns assignment when available."""
        from botburrow_agents.models import Assignment, TaskType

        coordinator.assigner.heartbeat = AsyncMock()
        coordinator.scheduler.get_next_assignment = AsyncMock(
            return_value=Assignment(
                agent_id="test",
                agent_name="Test",
                task_type=TaskType.INBOX,
            )
        )
        coordinator.assigner.try_claim = AsyncMock(return_value=True)

        result = await coordinator.get_assignment("runner-1", "hybrid")

        assert result is not None
        assert result.agent_id == "test"

    @pytest.mark.asyncio
    async def test_get_assignment_returns_none_when_no_work(
        self, coordinator: Coordinator
    ) -> None:
        """Test get_assignment returns None when no work."""
        coordinator.assigner.heartbeat = AsyncMock()
        coordinator.scheduler.get_next_assignment = AsyncMock(return_value=None)

        result = await coordinator.get_assignment("runner-1", "hybrid")

        assert result is None


class TestPrewarmConfigCache:
    """Tests for config cache prewarming."""

    @pytest.fixture
    def coordinator(self, settings: Settings) -> Coordinator:
        """Create test coordinator."""
        return Coordinator(settings)

    @pytest.mark.asyncio
    async def test_prewarm_without_config_cache(self, coordinator: Coordinator) -> None:
        """Test prewarm without config cache returns early."""
        coordinator.config_cache = None
        # Should not raise
        await coordinator._prewarm_config_cache()

    @pytest.mark.asyncio
    async def test_prewarm_with_leader_election(self, coordinator: Coordinator) -> None:
        """Test prewarm respects leader election."""
        coordinator.config_cache = AsyncMock()
        coordinator.leader_election = AsyncMock()
        coordinator.leader_election.is_leader = False
        coordinator.leader_election.try_become_leader = AsyncMock(return_value=False)
        coordinator.r2 = AsyncMock()
        coordinator.r2.list_agents = AsyncMock(return_value=[])

        await coordinator._prewarm_config_cache()

        # Should skip prewarm when not leader
        coordinator.config_cache.prewarm.assert_not_called()

    @pytest.mark.asyncio
    async def test_prewarm_with_agents(self, coordinator: Coordinator) -> None:
        """Test prewarm with agent list."""
        coordinator.config_cache = AsyncMock()
        coordinator.config_cache.prewarm = AsyncMock(return_value=3)
        coordinator.leader_election = AsyncMock()
        coordinator.leader_election.is_leader = False
        coordinator.leader_election.try_become_leader = AsyncMock(return_value=True)
        coordinator.r2 = AsyncMock()
        coordinator.r2.list_agents = AsyncMock(return_value=["agent1", "agent2", "agent3"])

        await coordinator._prewarm_config_cache()

        coordinator.config_cache.prewarm.assert_called_once()


class TestMain:
    """Tests for main entry point."""

    def test_main_command_exists(self) -> None:
        """Test that main command is callable."""
        from botburrow_agents.coordinator.main import main
        assert callable(main)

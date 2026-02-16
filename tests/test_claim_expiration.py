"""Integration tests for claim expiration system.

Tests the full claim lifecycle:
- Claim creation with heartbeat
- Automatic heartbeat renewal
- Stale claim expiration
- Graceful shutdown claim release
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.coordinator.assigner import Assigner
from botburrow_agents.models import Assignment, TaskType


@pytest.fixture
def claim_settings() -> Settings:
    """Test settings with short timeouts for faster tests."""
    return Settings(
        hub_url="http://test-hub:8000",
        redis_url="redis://localhost:6379",
        lock_ttl=600,
        poll_interval=30,
        activation_timeout=300,
        claim_heartbeat_interval=1,  # 1 second for fast tests
        claim_expiration_threshold=3,  # 3 seconds expiration
        stale_claim_check_interval=1,  # 1 second checks
    )


@pytest.fixture
def mock_hub() -> AsyncMock:
    """Mock HubClient."""
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock RedisClient with claim heartbeat support."""
    mock = AsyncMock()
    mock.set = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock(return_value=1)
    mock._ensure_connected = AsyncMock(return_value=mock)
    mock.scan = AsyncMock(side_effect=[(0, [])])  # Default: no locks
    return mock


@pytest.fixture
def assigner(
    mock_hub: AsyncMock,
    mock_redis: AsyncMock,
    claim_settings: Settings,
) -> Assigner:
    """Create Assigner with mocks."""
    return Assigner(mock_hub, mock_redis, claim_settings)


@pytest.fixture
def assignment() -> Assignment:
    """Test assignment."""
    return Assignment(
        agent_id="test-agent-1",
        agent_name="Test Agent",
        task_type=TaskType.INBOX,
        inbox_count=5,
    )


class TestClaimLifecycle:
    """Test full claim lifecycle."""

    @pytest.mark.asyncio
    async def test_claim_creates_heartbeat(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
        assignment: Assignment,
    ) -> None:
        """Test that claiming creates initial heartbeat."""
        mock_redis.set.return_value = True

        await assigner.try_claim(assignment, "runner-1")

        # Verify heartbeat was created
        heartbeat_calls = [
            call for call in mock_redis.set.call_args_list
            if "claim:heartbeat:" in str(call)
        ]
        assert len(heartbeat_calls) >= 1

    @pytest.mark.asyncio
    async def test_claim_renewal_updates_heartbeat(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that claim renewal updates heartbeat timestamp."""
        import json

        mock_redis.get.side_effect = [
            "runner-1",  # Lock owner
            json.dumps({"agent_id": "agent-1", "runner_id": "runner-1"}),  # Activation data
        ]

        success = await assigner.renew_claim("agent-1", "runner-1")

        assert success is True
        # Verify heartbeat was updated
        assert mock_redis.set.call_count >= 2

    @pytest.mark.asyncio
    async def test_release_cleans_up_heartbeat(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
        mock_hub: AsyncMock,  # noqa: ARG002
    ) -> None:
        """Test that releasing a claim cleans up heartbeat."""
        mock_redis.get.return_value = "runner-1"
        mock_redis.delete.return_value = 1

        await assigner.release("agent-1", "runner-1")

        # Verify heartbeat key was deleted
        delete_calls = [call[0][0] for call in mock_redis.delete.call_args_list]
        assert any("claim:heartbeat:" in key for key in delete_calls)


class TestStaleClaimExpiration:
    """Test stale claim expiration."""

    @pytest.mark.asyncio
    async def test_expired_heartbeat_triggers_cleanup(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that expired heartbeat causes claim to be cleaned up."""
        mock_redis.scan.side_effect = [(0, ["agent_lock:stale-agent"])]
        # First get for heartbeat (returns None = expired)
        # Second get for lock owner
        mock_redis.get.side_effect = [None, "runner-1"]

        cleaned = await assigner.cleanup_stale_claims()

        assert cleaned == 1
        # Verify lock was deleted
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_valid_heartbeat_prevents_cleanup(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that valid heartbeat prevents claim cleanup."""
        mock_redis.scan.side_effect = [(0, ["agent_lock:active-agent"])]
        # Heartbeat exists (not expired)
        mock_redis.get.return_value = "2024-02-16T12:00:00"

        cleaned = await assigner.cleanup_stale_claims()

        assert cleaned == 0

    @pytest.mark.asyncio
    async def test_cleanup_handles_multiple_claims(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test cleanup handles mix of stale and active claims."""
        mock_redis.scan.side_effect = [
            (0, ["agent_lock:stale-1", "agent_lock:active-1", "agent_lock:stale-2"]),
        ]
        # First agent: no heartbeat (stale)
        # Second agent: has heartbeat (active)
        # Third agent: no heartbeat (stale)
        mock_redis.get.side_effect = [
            None, "runner-1",  # stale-1
            "2024-02-16T12:00:00",  # active-1
            None, "runner-2",  # stale-2
        ]

        cleaned = await assigner.cleanup_stale_claims()

        assert cleaned == 2


class TestClaimRenewalFailure:
    """Test claim renewal failure scenarios."""

    @pytest.mark.asyncio
    async def test_renew_claim_fails_when_lock_stolen(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test renewal fails if lock was stolen by another runner."""
        # Lock is now owned by a different runner
        mock_redis.get.return_value = "runner-2"

        success = await assigner.renew_claim("agent-1", "runner-1")

        assert success is False

    @pytest.mark.asyncio
    async def test_renew_claim_fails_when_lock_expired(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test renewal fails if lock has already expired."""
        # Lock no longer exists
        mock_redis.get.return_value = None

        success = await assigner.renew_claim("agent-1", "runner-1")

        assert success is False


class TestMetrics:
    """Test claim metrics recording."""

    @pytest.mark.asyncio
    async def test_claim_renewal_records_metrics(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that claim renewal records metrics."""
        import json

        mock_redis.get.side_effect = [
            "runner-1",
            json.dumps({"agent_id": "agent-1"}),
        ]

        with patch("botburrow_agents.coordinator.assigner.record_claim_renewal") as mock_metric:
            await assigner.renew_claim("agent-1", "runner-1")
            mock_metric.assert_called_once_with("agent-1", success=True)

    @pytest.mark.asyncio
    async def test_stale_cleanup_records_metrics(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that stale claim cleanup records metrics."""
        mock_redis.scan.side_effect = [(0, ["agent_lock:stale-1"])]
        mock_redis.get.side_effect = [None, "runner-1"]

        with patch("botburrow_agents.coordinator.assigner.record_stale_claim_cleanup") as mock_metric:
            await assigner.cleanup_stale_claims()
            mock_metric.assert_called_once_with(1)

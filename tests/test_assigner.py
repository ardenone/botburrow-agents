"""Tests for Assigner."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.coordinator.assigner import Assigner
from botburrow_agents.models import (
    ActivationResult,
    Assignment,
    TaskType,
)


@pytest.fixture
def assigner_settings() -> Settings:
    """Test settings for Assigner."""
    return Settings(
        hub_url="http://test-hub:8000",
        redis_url="redis://localhost:6379",
        lock_ttl=600,
        poll_interval=30,
        activation_timeout=300,
    )


@pytest.fixture
def mock_hub() -> AsyncMock:
    """Mock HubClient."""
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock RedisClient."""
    mock = AsyncMock()
    mock.set = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock(return_value=1)
    mock._ensure_connected = AsyncMock()
    return mock


@pytest.fixture
def assigner(
    mock_hub: AsyncMock,
    mock_redis: AsyncMock,
    assigner_settings: Settings,
) -> Assigner:
    """Create Assigner with mocks."""
    return Assigner(mock_hub, mock_redis, assigner_settings)


@pytest.fixture
def assignment() -> Assignment:
    """Test assignment."""
    return Assignment(
        agent_id="test-agent-1",
        agent_name="Test Agent",
        task_type=TaskType.INBOX,
        inbox_count=5,
    )


class TestAssignerClaim:
    """Tests for claim functionality."""

    @pytest.mark.asyncio
    async def test_try_claim_success(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
        assignment: Assignment,
    ) -> None:
        """Test successfully claiming an agent."""
        mock_redis.set.return_value = True

        result = await assigner.try_claim(assignment, "runner-1")

        assert result is True
        # First call should be the lock acquisition
        mock_redis.set.assert_any_call(
            f"agent_lock:{assignment.agent_id}",
            "runner-1",
            ex=600,
            nx=True,
        )

    @pytest.mark.asyncio
    async def test_try_claim_failure_already_locked(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
        assignment: Assignment,
    ) -> None:
        """Test failing to claim an already locked agent."""
        mock_redis.set.return_value = False

        result = await assigner.try_claim(assignment, "runner-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_try_claim_tracks_assignment(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
        assignment: Assignment,
    ) -> None:
        """Test that claiming tracks the assignment metadata."""
        mock_redis.set.return_value = True

        await assigner.try_claim(assignment, "runner-1")

        # Check that _track_assignment was called
        # Expect 3 set calls: lock, activation metadata, and heartbeat
        assert mock_redis.set.call_count == 3


class TestAssignerRelease:
    """Tests for release functionality."""

    @pytest.mark.asyncio
    async def test_release_success(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
        mock_hub: AsyncMock,
    ) -> None:
        """Test releasing an agent successfully."""
        mock_redis.get.return_value = "runner-1"
        mock_redis.delete.return_value = 1

        result = await assigner.release("agent-1", "runner-1")

        assert result is True
        # Check that the lock was deleted (may be among multiple delete calls)
        mock_redis.delete.assert_any_call("agent_lock:agent-1")
        mock_hub.update_agent_activation.assert_called_once_with("agent-1")

    @pytest.mark.asyncio
    async def test_release_failure_not_owner(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test failing to release when not the lock owner."""
        mock_redis.get.return_value = "runner-2"

        result = await assigner.release("agent-1", "runner-1")

        assert result is False
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_release_with_result(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
        mock_hub: AsyncMock,  # noqa: ARG002
    ) -> None:
        """Test releasing with an activation result."""
        mock_redis.get.return_value = "runner-1"
        mock_redis.delete.return_value = 1
        mock_redis._ensure_connected.return_value = mock_redis

        result_obj = ActivationResult(
            agent_id="agent-1",
            agent_name="Agent 1",
            success=True,
            posts_created=1,
            comments_created=2,
            duration_seconds=5.0,
        )

        await assigner.release("agent-1", "runner-1", result_obj)

        # Verify result was recorded via lpush
        mock_redis.lpush.assert_called_once()


class TestAssignerExtendLock:
    """Tests for extending lock TTL."""

    @pytest.mark.asyncio
    async def test_extend_lock_success(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test extending lock TTL."""
        mock_redis._ensure_connected.return_value = mock_redis
        mock_redis.eval.return_value = 1

        result = await assigner.extend_lock("agent-1", "runner-1", 300)

        assert result is True
        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_lock_failure_not_owner(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test failing to extend lock when not owner."""
        mock_redis._ensure_connected.return_value = mock_redis
        mock_redis.eval.return_value = 0

        result = await assigner.extend_lock("agent-1", "runner-1", 300)

        assert result is False


class TestAssignerHeartbeat:
    """Tests for runner heartbeats."""

    @pytest.mark.asyncio
    async def test_heartbeat(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test recording a runner heartbeat."""
        await assigner.heartbeat("runner-1", "busy")

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        value = call_args[0][1]
        assert key == "runner:heartbeat:runner-1"
        data = json.loads(value)
        assert data["runner_id"] == "runner-1"
        assert data["status"] == "busy"
        assert "timestamp" in data


class TestAssignerGetActiveRunners:
    """Tests for getting active runners."""

    @pytest.mark.asyncio
    async def test_get_active_runners(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting list of active runners."""
        mock_redis._ensure_connected.return_value = mock_redis
        # Simulate scan returning keys and then ending
        mock_redis.scan.side_effect = [
            (0, ["runner:heartbeat:runner-1", "runner:heartbeat:runner-2"]),
        ]
        mock_redis.get.side_effect = [
            json.dumps({"runner_id": "runner-1", "status": "active"}),
            json.dumps({"runner_id": "runner-2", "status": "busy"}),
        ]

        runners = await assigner.get_active_runners()

        assert len(runners) == 2
        assert runners[0]["runner_id"] == "runner-1"
        assert runners[1]["runner_id"] == "runner-2"


class TestAssignerGetLockedAgents:
    """Tests for getting locked agents."""

    @pytest.mark.asyncio
    async def test_get_locked_agents(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting list of locked agents."""
        mock_redis._ensure_connected.return_value = mock_redis
        mock_redis.scan.side_effect = [
            (0, ["agent_lock:agent-1", "agent_lock:agent-2"]),
        ]
        mock_redis.get.side_effect = ["runner-1", "runner-2"]
        mock_redis.ttl.side_effect = [500, 400]

        locked = await assigner.get_locked_agents()

        assert len(locked) == 2
        assert locked[0]["agent_id"] == "agent-1"
        assert locked[0]["owner"] == "runner-1"
        assert locked[0]["ttl_seconds"] == 500


class TestAssignerGetRecentResults:
    """Tests for getting recent activation results."""

    @pytest.mark.asyncio
    async def test_get_recent_results(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test getting recent activation results."""
        mock_redis._ensure_connected.return_value = mock_redis
        mock_redis.lrange.return_value = [
            json.dumps(
                {
                    "agent_id": "agent-1",
                    "success": True,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ),
            json.dumps(
                {
                    "agent_id": "agent-2",
                    "success": False,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ),
        ]

        results = await assigner.get_recent_results(limit=10)

        assert len(results) == 2
        assert results[0]["agent_id"] == "agent-1"
        assert results[1]["success"] is False
        mock_redis.lrange.assert_called_once_with("activation:results", 0, 9)


class TestAssignerClaimRenewal:
    """Tests for claim heartbeat renewal."""

    @pytest.mark.asyncio
    async def test_renew_claim_success(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test successfully renewing a claim."""
        mock_redis.get.side_effect = ["runner-1", json.dumps({"agent_id": "agent-1"})]
        mock_redis._ensure_connected.return_value = mock_redis

        result = await assigner.renew_claim("agent-1", "runner-1")

        assert result is True
        # Verify heartbeat was updated
        assert mock_redis.set.call_count >= 2  # Heartbeat + activation metadata

    @pytest.mark.asyncio
    async def test_renew_claim_failure_not_owner(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test failing to renew claim when not the owner."""
        mock_redis.get.return_value = "runner-2"

        result = await assigner.renew_claim("agent-1", "runner-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_renew_claim_updates_heartbeat_timestamp(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that renewing claim updates heartbeat timestamp."""
        mock_redis.get.side_effect = ["runner-1", json.dumps({"agent_id": "agent-1"})]
        mock_redis._ensure_connected.return_value = mock_redis

        await assigner.renew_claim("agent-1", "runner-1")

        # Verify heartbeat key was set with expiration
        heartbeat_calls = [
            call for call in mock_redis.set.call_args_list
            if "claim:heartbeat:" in str(call)
        ]
        assert len(heartbeat_calls) >= 1


class TestAssignerStaleClaimCleanup:
    """Tests for stale claim cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_claims_success(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test cleaning up stale claims."""
        mock_redis._ensure_connected.return_value = mock_redis
        # Simulate finding a lock without a heartbeat
        mock_redis.scan.side_effect = [(0, ["agent_lock:agent-1"])]
        mock_redis.get.side_effect = [None, "runner-1"]  # No heartbeat, then owner

        result = await assigner.cleanup_stale_claims()

        assert result == 1  # One stale claim cleaned
        # Verify lock was deleted
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_stale_claims_no_stale_claims(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test cleanup when no stale claims exist."""
        mock_redis._ensure_connected.return_value = mock_redis
        # Simulate finding a lock with a valid heartbeat
        mock_redis.scan.side_effect = [(0, ["agent_lock:agent-1"])]
        mock_redis.get.side_effect = ["heartbeat-timestamp"]  # Valid heartbeat

        result = await assigner.cleanup_stale_claims()

        assert result == 0  # No stale claims

    @pytest.mark.asyncio
    async def test_cleanup_stale_claims_multiple(
        self,
        assigner: Assigner,
        mock_redis: AsyncMock,
    ) -> None:
        """Test cleaning up multiple stale claims."""
        mock_redis._ensure_connected.return_value = mock_redis
        # Simulate finding two locks without heartbeats
        mock_redis.scan.side_effect = [(0, ["agent_lock:agent-1", "agent_lock:agent-2"])]
        mock_redis.get.side_effect = [
            None, "runner-1",  # agent-1: no heartbeat, owner runner-1
            None, "runner-2",  # agent-2: no heartbeat, owner runner-2
        ]

        result = await assigner.cleanup_stale_claims()

        assert result == 2  # Two stale claims cleaned

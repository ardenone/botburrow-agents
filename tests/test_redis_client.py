"""Tests for RedisClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botburrow_agents.clients.redis import RedisClient, RedisLock
from botburrow_agents.config import Settings


@pytest.fixture
def redis_settings() -> Settings:
    """Test settings for Redis."""
    return Settings(
        redis_url="redis://localhost:6379",
        lock_ttl=600,
        poll_interval=30,
    )


class TestRedisClientConnection:
    """Tests for RedisClient connection management."""

    @pytest.mark.asyncio
    async def test_connect_creates_client(self, redis_settings: Settings) -> None:
        """Test that connect creates a Redis client."""
        client = RedisClient(redis_settings)

        with patch("botburrow_agents.clients.redis.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_from_url.return_value = mock_redis

            await client.connect()

            mock_from_url.assert_called_once_with(
                redis_settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_closes_client(self, redis_settings: Settings) -> None:
        """Test that close closes the Redis client."""
        client = RedisClient(redis_settings)
        mock_redis = AsyncMock()
        client._redis = mock_redis

        await client.close()

        mock_redis.close.assert_called_once()
        assert client._redis is None

    @pytest.mark.asyncio
    async def test_ensure_connected_connects_if_not_connected(
        self, redis_settings: Settings
    ) -> None:
        """Test that _ensure_connected connects if not already connected."""
        client = RedisClient(redis_settings)

        with patch.object(client, "connect", new_callable=AsyncMock) as mock_connect:
            mock_redis = AsyncMock()
            client._redis = None

            async def set_redis() -> None:
                client._redis = mock_redis

            mock_connect.side_effect = set_redis

            result = await client._ensure_connected()

            mock_connect.assert_called_once()
            assert result == mock_redis


class TestRedisClientBasicOperations:
    """Tests for basic Redis operations."""

    @pytest.fixture
    def client_with_mock_redis(self, redis_settings: Settings) -> tuple[RedisClient, AsyncMock]:
        """Create a client with a mocked Redis instance."""
        client = RedisClient(redis_settings)
        mock_redis = AsyncMock()
        client._redis = mock_redis
        return client, mock_redis

    @pytest.mark.asyncio
    async def test_get(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test get operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.get.return_value = "test-value"

        result = await client.get("test-key")

        mock_redis.get.assert_called_once_with("test-key")
        assert result == "test-value"

    @pytest.mark.asyncio
    async def test_set(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test set operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.set.return_value = True

        result = await client.set("test-key", "test-value", ex=300, nx=True)

        mock_redis.set.assert_called_once_with("test-key", "test-value", ex=300, nx=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_set_returns_false_when_nx_fails(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test set returns False when nx=True and key exists."""
        client, mock_redis = client_with_mock_redis
        mock_redis.set.return_value = None

        result = await client.set("existing-key", "value", nx=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test delete operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.delete.return_value = 1

        result = await client.delete("test-key")

        mock_redis.delete.assert_called_once_with("test-key")
        assert result == 1

    @pytest.mark.asyncio
    async def test_exists(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test exists operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.exists.return_value = 1

        result = await client.exists("test-key")

        mock_redis.exists.assert_called_once_with("test-key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test exists returns False when key doesn't exist."""
        client, mock_redis = client_with_mock_redis
        mock_redis.exists.return_value = 0

        result = await client.exists("nonexistent-key")

        assert result is False

    @pytest.mark.asyncio
    async def test_incr(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test incr operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.incr.return_value = 5

        result = await client.incr("counter")

        mock_redis.incr.assert_called_once_with("counter")
        assert result == 5

    @pytest.mark.asyncio
    async def test_expire(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test expire operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.expire.return_value = True

        result = await client.expire("test-key", 300)

        mock_redis.expire.assert_called_once_with("test-key", 300)
        assert result is True


class TestRedisClientListOperations:
    """Tests for Redis list operations."""

    @pytest.fixture
    def client_with_mock_redis(self, redis_settings: Settings) -> tuple[RedisClient, AsyncMock]:
        """Create a client with a mocked Redis instance."""
        client = RedisClient(redis_settings)
        mock_redis = AsyncMock()
        client._redis = mock_redis
        return client, mock_redis

    @pytest.mark.asyncio
    async def test_lpush(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test lpush operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.lpush.return_value = 3

        result = await client.lpush("queue", "item1", "item2")

        mock_redis.lpush.assert_called_once_with("queue", "item1", "item2")
        assert result == 3

    @pytest.mark.asyncio
    async def test_rpush(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test rpush operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.rpush.return_value = 2

        result = await client.rpush("queue", "item")

        mock_redis.rpush.assert_called_once_with("queue", "item")
        assert result == 2

    @pytest.mark.asyncio
    async def test_brpop(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test brpop operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.brpop.return_value = ("queue", "item")

        result = await client.brpop("queue", timeout=30)

        mock_redis.brpop.assert_called_once_with("queue", timeout=30)
        assert result == ("queue", "item")

    @pytest.mark.asyncio
    async def test_brpop_timeout(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test brpop returns None on timeout."""
        client, mock_redis = client_with_mock_redis
        mock_redis.brpop.return_value = None

        result = await client.brpop("queue", timeout=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_llen(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test llen operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.llen.return_value = 5

        result = await client.llen("queue")

        mock_redis.llen.assert_called_once_with("queue")
        assert result == 5


class TestRedisClientHashOperations:
    """Tests for Redis hash operations."""

    @pytest.fixture
    def client_with_mock_redis(self, redis_settings: Settings) -> tuple[RedisClient, AsyncMock]:
        """Create a client with a mocked Redis instance."""
        client = RedisClient(redis_settings)
        mock_redis = AsyncMock()
        client._redis = mock_redis
        return client, mock_redis

    @pytest.mark.asyncio
    async def test_hset(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test hset operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.hset.return_value = 1

        result = await client.hset("hash", "field", "value")

        mock_redis.hset.assert_called_once_with("hash", "field", "value")
        assert result == 1

    @pytest.mark.asyncio
    async def test_hget(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test hget operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.hget.return_value = "value"

        result = await client.hget("hash", "field")

        mock_redis.hget.assert_called_once_with("hash", "field")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_hgetall(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test hgetall operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.hgetall.return_value = {"field1": "value1", "field2": "value2"}

        result = await client.hgetall("hash")

        mock_redis.hgetall.assert_called_once_with("hash")
        assert result == {"field1": "value1", "field2": "value2"}

    @pytest.mark.asyncio
    async def test_hdel(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test hdel operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.hdel.return_value = 2

        result = await client.hdel("hash", "field1", "field2")

        mock_redis.hdel.assert_called_once_with("hash", "field1", "field2")
        assert result == 2


class TestRedisClientPubSub:
    """Tests for Redis pub/sub operations."""

    @pytest.fixture
    def client_with_mock_redis(self, redis_settings: Settings) -> tuple[RedisClient, AsyncMock]:
        """Create a client with a mocked Redis instance."""
        client = RedisClient(redis_settings)
        mock_redis = AsyncMock()
        client._redis = mock_redis
        return client, mock_redis

    @pytest.mark.asyncio
    async def test_publish(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test publish operation."""
        client, mock_redis = client_with_mock_redis
        mock_redis.publish.return_value = 3

        result = await client.publish("channel", "message")

        mock_redis.publish.assert_called_once_with("channel", "message")
        assert result == 3

    @pytest.mark.asyncio
    async def test_subscribe(
        self, client_with_mock_redis: tuple[RedisClient, AsyncMock]
    ) -> None:
        """Test subscribe operation."""
        client, mock_redis = client_with_mock_redis
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        # Make pubsub() return synchronously (not a coroutine)
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        result = await client.subscribe("channel")

        mock_redis.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_called_once_with("channel")
        assert result == mock_pubsub


class TestRedisLock:
    """Tests for RedisLock."""

    @pytest.fixture
    def mock_client(self, redis_settings: Settings) -> RedisClient:
        """Create a mock Redis client."""
        client = RedisClient(redis_settings)
        client._redis = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_acquire_success(self, mock_client: RedisClient) -> None:
        """Test acquiring lock successfully."""
        mock_client._redis.set.return_value = True
        lock = RedisLock(mock_client, "test-lock", "owner-1", 600)

        result = await lock.acquire()

        assert result is True
        assert lock.acquired is True
        mock_client._redis.set.assert_called_once_with(
            "test-lock", "owner-1", nx=True, ex=600
        )

    @pytest.mark.asyncio
    async def test_acquire_failure(self, mock_client: RedisClient) -> None:
        """Test failing to acquire lock (already held)."""
        mock_client._redis.set.return_value = None
        lock = RedisLock(mock_client, "test-lock", "owner-1", 600)

        result = await lock.acquire()

        assert result is False
        assert lock.acquired is False

    @pytest.mark.asyncio
    async def test_release_when_owned(self, mock_client: RedisClient) -> None:
        """Test releasing lock when we own it."""
        mock_client._redis.set.return_value = True
        mock_client._redis.eval.return_value = 1
        lock = RedisLock(mock_client, "test-lock", "owner-1", 600)

        await lock.acquire()
        result = await lock.release()

        assert result is True
        assert lock.acquired is False
        mock_client._redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_when_not_owned(self, mock_client: RedisClient) -> None:
        """Test releasing lock when we don't own it."""
        mock_client._redis.set.return_value = True
        mock_client._redis.eval.return_value = 0
        lock = RedisLock(mock_client, "test-lock", "owner-1", 600)

        await lock.acquire()
        result = await lock.release()

        assert result is False

    @pytest.mark.asyncio
    async def test_release_when_not_acquired(self, mock_client: RedisClient) -> None:
        """Test releasing lock when never acquired."""
        lock = RedisLock(mock_client, "test-lock", "owner-1", 600)

        result = await lock.release()

        assert result is False
        mock_client._redis.eval.assert_not_called()

    @pytest.mark.asyncio
    async def test_extend_success(self, mock_client: RedisClient) -> None:
        """Test extending lock TTL."""
        mock_client._redis.set.return_value = True
        mock_client._redis.eval.return_value = 1
        lock = RedisLock(mock_client, "test-lock", "owner-1", 600)

        await lock.acquire()
        result = await lock.extend(300)

        assert result is True

    @pytest.mark.asyncio
    async def test_extend_when_not_acquired(self, mock_client: RedisClient) -> None:
        """Test extending lock when not acquired."""
        lock = RedisLock(mock_client, "test-lock", "owner-1", 600)

        result = await lock.extend(300)

        assert result is False


class TestRedisClientLockContextManager:
    """Tests for lock context manager."""

    @pytest.mark.asyncio
    async def test_lock_context_manager_acquires_and_releases(
        self, redis_settings: Settings
    ) -> None:
        """Test lock context manager acquires and releases lock."""
        client = RedisClient(redis_settings)
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        client._redis = mock_redis

        async with client.lock("test-lock", "owner-1") as lock:
            assert lock.acquired is True

        # Verify release was called
        assert mock_redis.eval.called

    @pytest.mark.asyncio
    async def test_acquire_lock_method(self, redis_settings: Settings) -> None:
        """Test acquire_lock method."""
        client = RedisClient(redis_settings)
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        client._redis = mock_redis

        lock = await client.acquire_lock("test-lock", "owner-1", 600)

        assert lock.acquired is True
        mock_redis.set.assert_called_once_with(
            "test-lock", "owner-1", nx=True, ex=600
        )

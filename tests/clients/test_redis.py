"""Tests for Redis client."""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis

from botburrow_agents.clients.redis import RedisClient, RedisLock
from botburrow_agents.config import Settings

# Check if Lua scripting is available (needed for eval command in lock tests)
try:
    import lupa  # noqa: F401

    HAS_LUA = True
except ImportError:
    HAS_LUA = False

requires_lua = pytest.mark.skipif(
    not HAS_LUA, reason="Requires lupa for Lua scripting support in fakeredis"
)


@pytest.fixture
async def redis_client_with_fake(
    settings: Settings, fake_redis: fakeredis.FakeRedis
) -> RedisClient:
    """Create a Redis client backed by fakeredis."""
    client = RedisClient(settings)
    client._redis = fake_redis
    return client


class TestRedisClientBasicOperations:
    """Tests for basic Redis operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_client_with_fake: RedisClient) -> None:
        """Test setting and getting a value."""
        await redis_client_with_fake._ensure_connected()

        await redis_client_with_fake.set("test-key", "test-value")
        result = await redis_client_with_fake.get("test-key")

        assert result == "test-value"

    @pytest.mark.asyncio
    async def test_set_with_expiry(self, redis_client_with_fake: RedisClient) -> None:
        """Test setting a value with expiry."""
        await redis_client_with_fake._ensure_connected()

        result = await redis_client_with_fake.set("expiring-key", "value", ex=60)

        assert result is True
        # Key should exist
        assert await redis_client_with_fake.exists("expiring-key")

    @pytest.mark.asyncio
    async def test_set_nx_succeeds_when_not_exists(
        self, redis_client_with_fake: RedisClient
    ) -> None:
        """Test NX flag when key doesn't exist."""
        await redis_client_with_fake._ensure_connected()

        result = await redis_client_with_fake.set("new-key", "value", nx=True)

        assert result is True
        assert await redis_client_with_fake.get("new-key") == "value"

    @pytest.mark.asyncio
    async def test_set_nx_fails_when_exists(self, redis_client_with_fake: RedisClient) -> None:
        """Test NX flag when key already exists."""
        await redis_client_with_fake._ensure_connected()

        # Set initial value
        await redis_client_with_fake.set("existing-key", "original")

        # Try to set with NX
        result = await redis_client_with_fake.set("existing-key", "new", nx=True)

        assert result is False
        # Original value should be preserved
        assert await redis_client_with_fake.get("existing-key") == "original"

    @pytest.mark.asyncio
    async def test_delete(self, redis_client_with_fake: RedisClient) -> None:
        """Test deleting a key."""
        await redis_client_with_fake._ensure_connected()

        await redis_client_with_fake.set("to-delete", "value")
        result = await redis_client_with_fake.delete("to-delete")

        assert result == 1
        assert not await redis_client_with_fake.exists("to-delete")

    @pytest.mark.asyncio
    async def test_exists(self, redis_client_with_fake: RedisClient) -> None:
        """Test checking if key exists."""
        await redis_client_with_fake._ensure_connected()

        assert not await redis_client_with_fake.exists("nonexistent")

        await redis_client_with_fake.set("exists", "value")
        assert await redis_client_with_fake.exists("exists")

    @pytest.mark.asyncio
    async def test_incr(self, redis_client_with_fake: RedisClient) -> None:
        """Test incrementing a counter."""
        await redis_client_with_fake._ensure_connected()

        result1 = await redis_client_with_fake.incr("counter")
        result2 = await redis_client_with_fake.incr("counter")
        result3 = await redis_client_with_fake.incr("counter")

        assert result1 == 1
        assert result2 == 2
        assert result3 == 3


class TestRedisClientListOperations:
    """Tests for Redis list operations."""

    @pytest.mark.asyncio
    async def test_lpush_and_llen(self, redis_client_with_fake: RedisClient) -> None:
        """Test pushing to and getting length of list."""
        await redis_client_with_fake._ensure_connected()

        await redis_client_with_fake.lpush("mylist", "item1")
        await redis_client_with_fake.lpush("mylist", "item2", "item3")

        length = await redis_client_with_fake.llen("mylist")
        assert length == 3

    @pytest.mark.asyncio
    async def test_rpush(self, redis_client_with_fake: RedisClient) -> None:
        """Test pushing to right of list."""
        await redis_client_with_fake._ensure_connected()

        await redis_client_with_fake.rpush("rlist", "first")
        await redis_client_with_fake.rpush("rlist", "second")

        length = await redis_client_with_fake.llen("rlist")
        assert length == 2


class TestRedisClientHashOperations:
    """Tests for Redis hash operations."""

    @pytest.mark.asyncio
    async def test_hset_and_hget(self, redis_client_with_fake: RedisClient) -> None:
        """Test setting and getting hash field."""
        await redis_client_with_fake._ensure_connected()

        await redis_client_with_fake.hset("myhash", "field1", "value1")
        result = await redis_client_with_fake.hget("myhash", "field1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_hgetall(self, redis_client_with_fake: RedisClient) -> None:
        """Test getting all hash fields."""
        await redis_client_with_fake._ensure_connected()

        await redis_client_with_fake.hset("fullhash", "f1", "v1")
        await redis_client_with_fake.hset("fullhash", "f2", "v2")

        result = await redis_client_with_fake.hgetall("fullhash")

        assert result == {"f1": "v1", "f2": "v2"}

    @pytest.mark.asyncio
    async def test_hdel(self, redis_client_with_fake: RedisClient) -> None:
        """Test deleting hash field."""
        await redis_client_with_fake._ensure_connected()

        await redis_client_with_fake.hset("delhash", "field", "value")
        await redis_client_with_fake.hdel("delhash", "field")

        result = await redis_client_with_fake.hget("delhash", "field")
        assert result is None


class TestRedisLock:
    """Tests for distributed locking."""

    @pytest.mark.asyncio
    async def test_lock_acquisition(self, redis_client_with_fake: RedisClient) -> None:
        """Test acquiring a lock."""
        await redis_client_with_fake._ensure_connected()

        lock = await redis_client_with_fake.acquire_lock("test-lock", "owner-1", ttl=60)

        assert lock.acquired is True

    @pytest.mark.asyncio
    async def test_lock_prevents_duplicate(self, redis_client_with_fake: RedisClient) -> None:
        """Test that lock prevents second acquisition."""
        await redis_client_with_fake._ensure_connected()

        lock1 = await redis_client_with_fake.acquire_lock("exclusive-lock", "owner-1", ttl=60)
        lock2 = await redis_client_with_fake.acquire_lock("exclusive-lock", "owner-2", ttl=60)

        assert lock1.acquired is True
        assert lock2.acquired is False

    @requires_lua
    @pytest.mark.asyncio
    async def test_lock_release(self, redis_client_with_fake: RedisClient) -> None:
        """Test releasing a lock."""
        await redis_client_with_fake._ensure_connected()

        lock = await redis_client_with_fake.acquire_lock("release-lock", "owner-1", ttl=60)
        assert lock.acquired is True

        released = await lock.release()
        assert released is True
        assert lock.acquired is False

        # Now another owner can acquire
        lock2 = await redis_client_with_fake.acquire_lock("release-lock", "owner-2", ttl=60)
        assert lock2.acquired is True

    @requires_lua
    @pytest.mark.asyncio
    async def test_lock_context_manager(self, redis_client_with_fake: RedisClient) -> None:
        """Test lock as context manager."""
        await redis_client_with_fake._ensure_connected()

        async with redis_client_with_fake.lock("ctx-lock", "owner-1") as lock:
            assert lock.acquired is True
            # Do work while holding lock
            await redis_client_with_fake.set("protected-resource", "modified")

        # Lock should be released after context
        lock2 = await redis_client_with_fake.acquire_lock("ctx-lock", "owner-2", ttl=60)
        assert lock2.acquired is True

    @requires_lua
    @pytest.mark.asyncio
    async def test_lock_extend(self, redis_client_with_fake: RedisClient) -> None:
        """Test extending lock TTL."""
        await redis_client_with_fake._ensure_connected()

        lock = await redis_client_with_fake.acquire_lock("extend-lock", "owner-1", ttl=30)
        assert lock.acquired is True

        # Extend the lock
        extended = await lock.extend(additional_ttl=60)
        assert extended is True

    @requires_lua
    @pytest.mark.asyncio
    async def test_lock_release_only_by_owner(self, redis_client_with_fake: RedisClient) -> None:
        """Test that only owner can release lock."""
        await redis_client_with_fake._ensure_connected()

        # Acquire lock as owner-1
        lock1 = RedisLock(redis_client_with_fake, "owned-lock", "owner-1", 60)
        await lock1.acquire()
        assert lock1.acquired is True

        # Try to release as different owner
        lock2 = RedisLock(redis_client_with_fake, "owned-lock", "owner-2", 60)
        lock2._acquired = True  # Pretend we acquired it

        released = await lock2.release()
        # Should fail because we don't own it
        assert released is False

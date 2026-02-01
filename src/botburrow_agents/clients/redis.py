"""Redis client for coordination and locking."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
import structlog

from botburrow_agents.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class RedisLock:
    """Async context manager for distributed lock."""

    def __init__(
        self,
        client: RedisClient,
        key: str,
        owner: str,
        ttl: int,
    ) -> None:
        self.client = client
        self.key = key
        self.owner = owner
        self.ttl = ttl
        self._acquired = False

    async def acquire(self) -> bool:
        """Try to acquire the lock."""
        r = await self.client._ensure_connected()
        result = await r.set(
            self.key,
            self.owner,
            nx=True,
            ex=self.ttl,
        )
        self._acquired = result is not None
        if self._acquired:
            logger.debug("lock_acquired", key=self.key, owner=self.owner)
        return self._acquired

    async def release(self) -> bool:
        """Release the lock if we own it."""
        if not self._acquired:
            return False

        # Only release if we still own it (Lua script for atomicity)
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        r = await self.client._ensure_connected()
        result = await r.eval(script, 1, self.key, self.owner)
        released = bool(result == 1)
        if released:
            logger.debug("lock_released", key=self.key, owner=self.owner)
        else:
            logger.warning("lock_not_owned", key=self.key, owner=self.owner)
        self._acquired = False
        return released

    async def extend(self, additional_ttl: int | None = None) -> bool:
        """Extend lock TTL if we own it."""
        if not self._acquired:
            return False

        ttl = additional_ttl or self.ttl
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('expire', KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        r = await self.client._ensure_connected()
        result = await r.eval(script, 1, self.key, self.owner, ttl)
        return bool(result == 1)

    @property
    def acquired(self) -> bool:
        """Check if lock is currently held."""
        return self._acquired


class RedisClient:
    """Redis client for coordination.

    Used for:
    - Distributed locking (agent assignments)
    - Work queue (optional, for push-based coordination)
    - Caching (optional)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            logger.info("redis_connected", url=self.settings.redis_url)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def _ensure_connected(self) -> redis.Redis:
        """Ensure Redis is connected."""
        if self._redis is None:
            await self.connect()
        return self._redis  # type: ignore

    async def acquire_lock(
        self,
        key: str,
        owner: str,
        ttl: int | None = None,
    ) -> RedisLock:
        """Create and acquire a distributed lock.

        Args:
            key: Lock key name
            owner: Owner identifier (usually runner_id)
            ttl: Lock TTL in seconds

        Returns:
            RedisLock instance (check .acquired property)
        """
        await self._ensure_connected()
        ttl = ttl or self.settings.lock_ttl
        lock = RedisLock(self, key, owner, ttl)
        await lock.acquire()
        return lock

    @asynccontextmanager
    async def lock(
        self,
        key: str,
        owner: str,
        ttl: int | None = None,
    ) -> AsyncGenerator[RedisLock, None]:
        """Context manager for distributed lock.

        Usage:
            async with redis.lock("agent:abc", "runner-1") as lock:
                if lock.acquired:
                    # Do work
                    pass
        """
        lock = await self.acquire_lock(key, owner, ttl)
        try:
            yield lock
        finally:
            await lock.release()

    async def get(self, key: str) -> str | None:
        """Get a value."""
        r = await self._ensure_connected()
        return await r.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        """Set a value.

        Args:
            key: Key name
            value: Value to set
            ex: Expiry in seconds
            nx: Only set if not exists

        Returns:
            True if value was set
        """
        r = await self._ensure_connected()
        result = await r.set(key, value, ex=ex, nx=nx)
        return result is not None

    async def delete(self, key: str) -> int:
        """Delete a key."""
        r = await self._ensure_connected()
        return await r.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        r = await self._ensure_connected()
        return await r.exists(key) > 0

    async def incr(self, key: str) -> int:
        """Increment a counter."""
        r = await self._ensure_connected()
        return await r.incr(key)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiry."""
        r = await self._ensure_connected()
        return await r.expire(key, seconds)

    # Queue operations

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to left of list."""
        r = await self._ensure_connected()
        return await r.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        """Push values to right of list."""
        r = await self._ensure_connected()
        return await r.rpush(key, *values)

    async def brpop(
        self, key: str, timeout: int = 0
    ) -> tuple[str, str] | None:
        """Blocking pop from right of list.

        Args:
            key: List key
            timeout: Timeout in seconds (0 = block forever)

        Returns:
            Tuple of (key, value) or None if timeout
        """
        r = await self._ensure_connected()
        result = await r.brpop(key, timeout=timeout)
        return result

    async def llen(self, key: str) -> int:
        """Get list length."""
        r = await self._ensure_connected()
        return await r.llen(key)

    # Hash operations

    async def hset(self, key: str, field: str, value: str) -> int:
        """Set hash field."""
        r = await self._ensure_connected()
        return await r.hset(key, field, value)

    async def hget(self, key: str, field: str) -> str | None:
        """Get hash field."""
        r = await self._ensure_connected()
        return await r.hget(key, field)

    async def hgetall(self, key: str) -> dict[str, str]:
        """Get all hash fields."""
        r = await self._ensure_connected()
        return await r.hgetall(key)

    async def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields."""
        r = await self._ensure_connected()
        return await r.hdel(key, *fields)

    # Pub/Sub (optional, for real-time coordination)

    async def publish(self, channel: str, message: str) -> int:
        """Publish message to channel."""
        r = await self._ensure_connected()
        return await r.publish(channel, message)

    async def subscribe(self, channel: str) -> Any:
        """Subscribe to channel."""
        r = await self._ensure_connected()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

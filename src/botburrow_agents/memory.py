"""Memory store for agent context persistence.

Uses Redis for hot cache (sorted set by timestamp) and R2 for durable persistence.
Supports retrieval strategies: recent, keyword, embedding_search.

Retrieval strategies:
- recent: N most recently stored items (default)
- keyword: Items with matching keywords in content
- embedding_search: Falls back to keyword (no vector store configured)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from botburrow_agents.models import MemoryItem

if TYPE_CHECKING:
    from botburrow_agents.clients.r2 import R2Client
    from botburrow_agents.clients.redis import RedisClient

logger = structlog.get_logger(__name__)

# Redis key templates
_INDEX_KEY = "memory:{agent_id}:index"          # sorted set: score=timestamp, member=item_id
_ITEM_KEY = "memory:{agent_id}:item:{item_id}"  # string: JSON-serialised MemoryItem

# Maximum items to keep in the Redis index per agent (trim older entries)
_MAX_REDIS_ITEMS = 1000


class MemoryStore:
    """Stores and retrieves agent memories across sessions.

    Storage layout:
    - Redis sorted set ``memory:{agent_id}:index`` (score = UNIX timestamp)
    - Redis string keys ``memory:{agent_id}:item:{uuid}`` (JSON)
    - R2 objects ``agents/{agent_id}/memories/{uuid}.json`` (durable fallback)

    Both Redis writes and R2 writes are best-effort: failures are logged but
    never raise so that a storage outage cannot break the agent loop.
    """

    def __init__(self, redis: RedisClient, r2: R2Client) -> None:
        self.redis = redis
        self.r2 = r2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def save(
        self,
        agent_id: str,
        key: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        """Persist a memory item for an agent.

        Args:
            agent_id: Agent identifier (agent.name)
            key: Logical key, e.g. ``interaction:notif-abc``
            content: Human-readable memory text
            metadata: Optional extra fields (notification_id, etc.)

        Returns:
            The saved MemoryItem
        """
        item_id = str(uuid.uuid4())
        now = datetime.utcnow()
        item = MemoryItem(
            id=item_id,
            agent_id=agent_id,
            key=key,
            content=content,
            created_at=now,
            metadata=metadata or {},
        )
        item_json = item.model_dump_json()
        timestamp = now.timestamp()

        # Redis – hot cache
        try:
            index_key = _INDEX_KEY.format(agent_id=agent_id)
            item_key = _ITEM_KEY.format(agent_id=agent_id, item_id=item_id)
            await self.redis.set(item_key, item_json)
            await self.redis.zadd(index_key, {item_id: timestamp})
            # Trim to keep only the most recent _MAX_REDIS_ITEMS entries
            await self.redis.zremrangebyrank(index_key, 0, -(_MAX_REDIS_ITEMS + 1))
        except Exception as exc:
            logger.warning("memory_redis_save_failed", agent_id=agent_id, error=str(exc))

        # R2 – durable persistence
        try:
            r2_key = f"agents/{agent_id}/memories/{item_id}.json"
            await self.r2.put_object(r2_key, item_json)
        except Exception as exc:
            logger.warning("memory_r2_save_failed", agent_id=agent_id, error=str(exc))

        logger.debug("memory_saved", agent_id=agent_id, key=key, item_id=item_id)
        return item

    async def retrieve(
        self,
        agent_id: str,
        query: str = "",
        strategy: str = "recent",
        max_items: int = 10,
    ) -> list[MemoryItem]:
        """Retrieve memories for an agent.

        Args:
            agent_id: Agent identifier
            query: Query text used by keyword / embedding strategies
            strategy: ``recent``, ``keyword``, or ``embedding_search``
            max_items: Maximum number of items to return

        Returns:
            List of MemoryItem, most relevant / most recent first
        """
        if strategy == "recent":
            return await self._retrieve_recent(agent_id, max_items)
        elif strategy in ("keyword", "embedding_search"):
            # embedding_search falls back to keyword: no vector store is configured
            return await self._retrieve_keyword(agent_id, query, max_items)
        else:
            logger.warning("unknown_memory_strategy", strategy=strategy)
            return await self._retrieve_recent(agent_id, max_items)

    # ------------------------------------------------------------------
    # Internal retrieval helpers
    # ------------------------------------------------------------------

    async def _retrieve_recent(self, agent_id: str, max_items: int) -> list[MemoryItem]:
        """Return the N most recently stored memories."""
        try:
            index_key = _INDEX_KEY.format(agent_id=agent_id)
            item_ids = await self.redis.zrevrange(index_key, 0, max_items - 1)

            if not item_ids:
                # Redis index is empty – try loading from R2
                return await self._load_from_r2(agent_id, max_items)

            items: list[MemoryItem] = []
            for item_id in item_ids:
                item_key = _ITEM_KEY.format(agent_id=agent_id, item_id=item_id)
                item_json = await self.redis.get(item_key)
                if item_json:
                    try:
                        items.append(MemoryItem.model_validate_json(item_json))
                    except Exception as exc:
                        logger.warning("memory_parse_error", item_id=item_id, error=str(exc))
            return items

        except Exception as exc:
            logger.warning("memory_redis_retrieve_failed", agent_id=agent_id, error=str(exc))
            return await self._load_from_r2(agent_id, max_items)

    async def _retrieve_keyword(
        self,
        agent_id: str,
        query: str,
        max_items: int,
    ) -> list[MemoryItem]:
        """Return memories whose content matches keywords in *query*."""
        pool_size = min(max_items * 5, 100)
        candidates = await self._retrieve_recent(agent_id, pool_size)

        if not query or not candidates:
            return candidates[:max_items]

        keywords = {w for w in query.lower().split() if len(w) > 2}
        if not keywords:
            return candidates[:max_items]

        def score(item: MemoryItem) -> int:
            lower = item.content.lower()
            return sum(1 for kw in keywords if kw in lower)

        scored = sorted(candidates, key=score, reverse=True)
        matched = [item for item in scored if score(item) > 0]
        return (matched or candidates)[:max_items]

    async def _load_from_r2(self, agent_id: str, max_items: int) -> list[MemoryItem]:
        """Load memories from R2 when Redis cache is empty, and warm Redis."""
        try:
            prefix = f"agents/{agent_id}/memories/"
            keys = await self.r2.list_objects(prefix)
            if not keys:
                return []

            # Keys are UUID-named; sort lexicographically (UUIDs are time-ordered)
            recent_keys = sorted(keys)[-max_items:]
            items: list[MemoryItem] = []
            for r2_key in recent_keys:
                try:
                    item_json = await self.r2.get_text(r2_key)
                    item = MemoryItem.model_validate_json(item_json)
                    items.append(item)
                    # Warm Redis cache
                    await self._warm_redis(agent_id, item, item_json)
                except Exception as exc:
                    logger.warning("memory_r2_item_load_failed", key=r2_key, error=str(exc))

            items.sort(key=lambda x: x.created_at, reverse=True)
            return items[:max_items]

        except Exception as exc:
            logger.warning("memory_r2_list_failed", agent_id=agent_id, error=str(exc))
            return []

    async def _warm_redis(self, agent_id: str, item: MemoryItem, item_json: str) -> None:
        """Populate Redis with a single memory item loaded from R2."""
        try:
            item_key = _ITEM_KEY.format(agent_id=agent_id, item_id=item.id)
            index_key = _INDEX_KEY.format(agent_id=agent_id)
            await self.redis.set(item_key, item_json)
            await self.redis.zadd(index_key, {item.id: item.created_at.timestamp()})
        except Exception as exc:
            logger.warning("memory_redis_warm_failed", agent_id=agent_id, error=str(exc))

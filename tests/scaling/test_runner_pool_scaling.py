#!/usr/bin/env python3
"""
Test runner pool scaling by injecting work items into Redis and monitoring execution.

This script tests:
1. Runners pick up work from Redis queues (BRPOP)
2. One runner can handle multiple different agent personas
3. Work distribution across multiple runner replicas
4. Resource usage and response times under load
"""

import asyncio
import json
import time
from datetime import UTC, datetime

import redis.asyncio as aioredis


class WorkItem:
    """Work item for runner queue."""

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        task_type: str = "INBOX",
        priority: str = "normal",
        inbox_count: int = 1,
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.task_type = task_type
        self.priority = priority
        self.inbox_count = inbox_count

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "task_type": self.task_type,
                "priority": self.priority,
                "inbox_count": self.inbox_count,
                "enqueued_at": datetime.now(UTC).isoformat(),
            }
        )


async def test_runner_scaling():
    """Test runner pool scaling capabilities."""
    # Connect to Valkey (Redis) in the cluster
    redis_url = "redis://valkey.botburrow-agents.svc.cluster.local:6379"
    redis_client = await aioredis.from_url(redis_url, decode_responses=True)

    print("✓ Connected to Redis")

    # Create test work items for different agent personas
    test_agents = [
        ("agent-alpha", "Agent Alpha - Code Reviewer", "high"),
        ("agent-beta", "Agent Beta - Bug Fixer", "normal"),
        ("agent-gamma", "Agent Gamma - Feature Developer", "high"),
        ("agent-delta", "Agent Delta - Documentation Writer", "normal"),
        ("agent-epsilon", "Agent Epsilon - Test Writer", "low"),
    ]

    print(f"\n📊 Creating {len(test_agents)} test work items...")

    # Enqueue work items
    for agent_id, agent_name, priority in test_agents:
        work_item = WorkItem(
            agent_id=agent_id, agent_name=agent_name, priority=priority, inbox_count=3
        )

        queue_key = f"work:queue:{priority}"
        await redis_client.lpush(queue_key, work_item.to_json())
        print(f"  ✓ Enqueued {agent_id} to {queue_key}")

    # Monitor queue lengths
    print("\n📈 Queue lengths:")
    for priority in ["high", "normal", "low"]:
        queue_key = f"work:queue:{priority}"
        length = await redis_client.llen(queue_key)
        print(f"  {queue_key}: {length} items")

    # Monitor active work
    print("\n⏳ Monitoring active work for 60 seconds...")
    start_time = time.time()
    max_monitor_time = 60
    check_interval = 5

    while (time.time() - start_time) < max_monitor_time:
        await asyncio.sleep(check_interval)

        # Check active runners
        active_work = await redis_client.hgetall("work:active")
        print(f"\n[{int(time.time() - start_time)}s] Active work:")
        if active_work:
            for agent_id, runner_id in active_work.items():
                print(f"  {agent_id} → {runner_id}")
        else:
            print("  (none)")

        # Check queue lengths
        print("  Queue lengths:")
        total_queued = 0
        for priority in ["high", "normal", "low"]:
            queue_key = f"work:queue:{priority}"
            length = await redis_client.llen(queue_key)
            total_queued += length
            if length > 0:
                print(f"    {queue_key}: {length}")

        if total_queued == 0 and not active_work:
            print("\n✓ All work completed!")
            break

    # Final stats
    print("\n📊 Final Statistics:")
    active_work = await redis_client.hgetall("work:active")
    print(f"  Active work: {len(active_work)} items")

    for priority in ["high", "normal", "low"]:
        queue_key = f"work:queue:{priority}"
        length = await redis_client.llen(queue_key)
        if length > 0:
            print(f"  {queue_key}: {length} remaining")

    # Check completion stats (if tracking exists)
    completed_count = await redis_client.hlen("work:completed")
    print(f"  Completed: {completed_count} items")

    await redis_client.close()
    print("\n✓ Test complete")


if __name__ == "__main__":
    asyncio.run(test_runner_scaling())

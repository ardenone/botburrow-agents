#!/usr/bin/env python3
"""Simplified leader election verification script.

This script verifies the core leader election functionality without requiring
a full Kubernetes deployment. It tests the LeaderElection class in isolation.

Run: python scripts/verify_leader_election.py

Exit codes:
    0 - All verifications passed
    1 - Verification failed
"""

from __future__ import annotations

import asyncio
import sys

import structlog

# Add src to path
sys.path.insert(0, "/home/coder/botburrow-agents/src")

from botburrow_agents.clients.redis import RedisClient
from botburrow_agents.coordinator.work_queue import LeaderElection
from botburrow_agents.config import get_settings


def setup_logging() -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def verify_leader_election() -> bool:
    """Verify leader election functionality.

    Tests:
    1. Only one instance becomes leader
    2. Leadership refresh works
    3. New leader is elected when current releases
    4. Multiple instances compete correctly
    """
    logger = structlog.get_logger(__name__)
    settings = get_settings()

    # Create Redis connection
    redis = RedisClient(settings)
    await redis.connect()

    try:
        # Clean up any existing leader key
        r = await redis._ensure_connected()
        await r.delete(LeaderElection.LEADER_KEY)
        logger.info("leader_election_verification_start")

        # Test 1: Single instance becomes leader
        logger.info("test_1_single_instance_leader")
        instance1 = LeaderElection(redis, "instance-1")
        is_leader = await instance1.try_become_leader()

        if not is_leader:
            logger.error("test_1_failed_instance_not_leader")
            return False
        logger.info("test_1_passed_instance_became_leader")

        # Verify the leader key in Redis
        current_leader = await r.get(LeaderElection.LEADER_KEY)
        if current_leader != "instance-1":
            logger.error(
                "test_1_failed_leader_mismatch",
                expected="instance-1",
                actual=current_leader,
            )
            return False
        logger.info("test_1_passed_leader_key_correct")

        # Test 2: Second instance cannot become leader
        logger.info("test_2_second_instance_cannot_become_leader")
        instance2 = LeaderElection(redis, "instance-2")
        is_leader = await instance2.try_become_leader()

        if is_leader:
            logger.error("test_2_failed_second_instance_became_leader")
            return False
        logger.info("test_2_passed_second_instance_not_leader")

        # Test 3: First instance refreshes leadership
        logger.info("test_3_leadership_refresh")
        is_leader = await instance1.try_become_leader()

        if not is_leader:
            logger.error("test_3_failed_leader_lost_leadership")
            return False
        logger.info("test_3_passed_leadership_refreshed")

        # Test 4: Verify TTL is set correctly
        logger.info("test_4_verify_ttl")
        ttl = await r.ttl(LeaderElection.LEADER_KEY)
        if ttl <= 0 or ttl > LeaderElection.HEARTBEAT_TTL:
            logger.error("test_4_failed_ttl_invalid", ttl=ttl)
            return False
        logger.info("test_4_passed_ttl_valid", ttl=ttl)

        # Test 5: Release leadership and second instance becomes leader
        logger.info("test_5_release_leadership_new_leader_elected")
        await instance1.release_leadership()

        # Verify leader key is gone
        current_leader = await r.get(LeaderElection.LEADER_KEY)
        if current_leader is not None:
            logger.error("test_5_failed_leader_key_not_deleted", leader=current_leader)
            return False
        logger.info("test_5_passed_leadership_released")

        # Now instance2 should become leader
        is_leader = await instance2.try_become_leader()
        if not is_leader:
            logger.error("test_5_failed_second_instance_did_not_become_leader")
            return False
        logger.info("test_5_passed_new_leader_elected")

        # Verify instance2 is the leader
        current_leader = await r.get(LeaderElection.LEADER_KEY)
        if current_leader != "instance-2":
            logger.error(
                "test_5_failed_leader_mismatch_after_election",
                expected="instance-2",
                actual=current_leader,
            )
            return False
        logger.info("test_5_passed_correct_leader_elected")

        # Cleanup
        await instance2.release_leadership()
        await r.delete(LeaderElection.LEADER_KEY)

        logger.info("leader_election_verification_all_tests_passed")
        return True

    except Exception as e:
        logger.error("verification_exception", error=str(e))
        return False
    finally:
        await redis.close()


async def verify_work_queue_deduplication() -> bool:
    """Verify work queue deduplication logic.

    Tests:
    1. Duplicate work items are rejected
    2. Active task tracking prevents duplicates
    """
    logger = structlog.get_logger(__name__)
    settings = get_settings()

    # Create Redis connection
    redis = RedisClient(settings)
    await redis.connect()

    try:
        from botburrow_agents.coordinator.work_queue import (
            ACTIVE_TASKS,
            WorkQueue,
            WorkItem,
        )
        from botburrow_agents.models import TaskType

        r = await redis._ensure_connected()

        # Clean up test data
        await r.delete(WorkQueue QUEUE_HIGH)
        await r.delete(WorkQueue.QUEUE_NORMAL)
        await r.delete(WorkQueue.QUEUE_LOW)
        await r.delete(ACTIVE_TASKS)

        logger.info("work_queue_deduplication_verification_start")

        work_queue = WorkQueue(redis, settings)

        # Test 1: Enqueue work item
        logger.info("test_1_enqueue_work_item")
        work_item = WorkItem(
            agent_id="test-agent-1",
            agent_name="Test Agent 1",
            task_type=TaskType.INBOX,
            priority="high",
        )
        enqueued = await work_queue.enqueue(work_item)

        if not enqueued:
            logger.error("test_1_failed_work_not_enqueued")
            return False
        logger.info("test_1_passed_work_enqueued")

        # Test 2: Try to enqueue duplicate (should fail)
        logger.info("test_2_duplicate_rejected")
        duplicate_item = WorkItem(
            agent_id="test-agent-1",  # Same agent_id
            agent_name="Test Agent 1",
            task_type=TaskType.INBOX,
            priority="high",
        )
        enqueued = await work_queue.enqueue(duplicate_item)

        if enqueued:
            logger.error("test_2_failed_duplicate_was_accepted")
            return False
        logger.info("test_2_passed_duplicate_rejected")

        # Test 3: Force enqueue should work
        logger.info("test_3_force_enqueue")
        enqueued = await work_queue.enqueue(duplicate_item, force=True)

        if not enqueued:
            logger.error("test_3_failed_force_enqueue_failed")
            return False
        logger.info("test_3_passed_force_enqueue_worked")

        # Cleanup
        await r.delete(WorkQueue.QUEUE_HIGH)
        await r.delete(WorkQueue.QUEUE_NORMAL)
        await r.delete(WorkQueue.QUEUE_LOW)
        await r.delete(ACTIVE_TASKS)

        logger.info("work_queue_deduplication_verification_all_tests_passed")
        return True

    except Exception as e:
        logger.error("verification_exception", error=str(e))
        return False
    finally:
        await redis.close()


async def main() -> int:
    """Main entry point."""
    setup_logging()
    logger = structlog.get_logger(__name__)

    logger.info("starting_simplified_verification")

    # Verify leader election
    leader_election_ok = await verify_leader_election()
    if not leader_election_ok:
        logger.error("leader_election_verification_failed")
        return 1

    # Verify work queue deduplication
    work_queue_ok = await verify_work_queue_deduplication()
    if not work_queue_ok:
        logger.error("work_queue_deduplication_verification_failed")
        return 1

    logger.info("all_verifications_passed")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

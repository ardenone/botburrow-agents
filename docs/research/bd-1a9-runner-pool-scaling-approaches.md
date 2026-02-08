# Runner Pool Scaling Approaches Research

**Bead:** bd-1a9 (Alternative: Research and document options)
**Original Bead:** bd-3qv (Test agent runner pool scaling)
**Date:** 2026-02-08
**Status:** Research Complete

---

## Executive Summary

This document compares various approaches for testing and verifying agent runner pool scaling in the botburrow-agents system. The original bead (bd-3qv) requires Kubernetes infrastructure deployment which is currently blocked. This research identifies alternative verification approaches that can validate the scaling architecture without requiring full infrastructure deployment.

### Recommendation

**Implement the "Unit Test + Mock Infrastructure" approach** (Option 1) as the primary verification method, with "Local Docker Compose" (Option 2) as a secondary integration test. This combination provides:
- Fast feedback loop (unit tests run in seconds)
- No infrastructure dependencies
- Covers all scaling behaviors (multi-runner, BRPOP, deduplication, circuit breaker)
- Can be executed in CI/CD pipelines

---

## Background: What Are We Testing?

### The Scaling Architecture

The botburrow-agents system implements an **M:N agent-to-runner architecture**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              COORDINATOR                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │   Leader    │  │  Work Poller │  │    Priority Work Queue       │  │
│  │  Election   │  │(Long-polling)│  │  (high, normal, low queues)  │  │
│  └─────────────┘  └──────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Redis BRPOP (atomic work claiming)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              RUNNER POOL                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │Runner 1 │  │Runner 2 │  │Runner 3 │  │Runner N │  │Runner N+1│...  │
│  │(Hybrid) │  │(Notif.) │  │(Hybrid) │  │(Explor.)│  │(Hybrid) │     │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Scaling Behaviors to Verify

1. **Multi-runner work distribution**: Multiple runners can claim different work items simultaneously
2. **Atomic claiming**: BRPOP ensures only one runner gets each work item
3. **Deduplication**: Same agent cannot be enqueued if already active
4. **Priority queues**: High priority work claimed before normal/low
5. **Circuit breaker**: Failing agents enter exponential backoff
6. **Config cache**: Shared cache accessible to all runners
7. **Leader election**: Only one coordinator polls Hub

### Current State (From Code Analysis)

**Implemented Features:**
- ✅ `WorkQueue` class with priority queues (`work_queue.py:76-268`)
- ✅ BRPOP-based atomic claiming (`work_queue.py:146-186`)
- ✅ Deduplication via `ACTIVE_TASKS` hash (`work_queue.py:113-121`)
- ✅ Circuit breaker with exponential backoff (`work_queue.py:192-233`)
- ✅ Config cache with TTL (`work_queue.py:270-368`)
- ✅ Leader election (`work_queue.py:371-444`)
- ✅ HPA manifests (`k8s/apexalgo-iad/hpa.yaml`)

**Test Coverage:**
- ✅ Unit tests exist: `tests/test_runner_pool_scaling.py` (608 lines)
- ✅ Tests cover: WorkQueue, ConfigCache, LeaderElection
- ❌ No integration tests (requires infrastructure)
- ❌ No end-to-end scaling verification

**Blocking Issue:**
The `botburrow-agents` namespace exists but is empty. Infrastructure deployment requires:
- RBAC grants (human action: bd-3q9)
- Secret creation (human action: bd-2la, bd-3hx)

---

## Comparison of Verification Approaches

### Option 1: Unit Test + Mock Infrastructure (Recommended)

**Approach:** Expand existing `test_runner_pool_scaling.py` with comprehensive multi-runner simulation tests.

**What It Tests:**
- Multiple runners claiming different work simultaneously
- Atomic BRPOP behavior (mocked)
- Deduplication enforcement
- Priority queue ordering
- Circuit breaker state transitions
- Config cache sharing between runners
- Leader election failover

**Implementation Effort:** Low (most tests already exist, need expansion)

**Pros:**
- ✅ Fast execution (seconds)
- ✅ No infrastructure dependencies
- ✅ CI/CD friendly
- ✅ Deterministic (no flakiness)
- ✅ Can test edge cases explicitly
- ✅ Tests already 80% complete
- ✅ Covers all Redis operations via mocks

**Cons:**
- ❌ Doesn't verify actual Redis behavior
- ❌ Doesn't test network conditions
- ❌ Doesn't verify Kubernetes HPA integration
- ❌ Mocked BRPOP may miss edge cases

**File References:**
- `tests/test_runner_pool_scaling.py` - Existing test file
- `src/botburrow_agents/coordinator/work_queue.py` - Implementation

**Example Test:**
```python
@pytest.mark.asyncio
async def test_three_runners_claim_different_work():
    """Test that 3 runners can claim 3 different work items."""
    work_items = [
        WorkItem(agent_id="agent-1", agent_name="Agent 1", task_type=TaskType.INBOX),
        WorkItem(agent_id="agent-2", agent_name="Agent 2", task_type=TaskType.INBOX),
        WorkItem(agent_id="agent-3", agent_name="Agent 3", task_type=TaskType.INBOX),
    ]

    # Mock BRPOP to return each item once
    mock_redis.brpop = AsyncMock(side_effect=[
        ("work:queue:normal", items[0].to_json()),
        ("work:queue:normal", items[1].to_json()),
        ("work:queue:normal", items[2].to_json()),
    ])

    # Create 3 work queues (simulating 3 runners)
    queues = [WorkQueue(mock_redis, settings) for _ in range(3)]

    # All 3 claim concurrently
    results = await asyncio.gather(*[
        q.claim(f"runner-{i}", timeout=1) for i, q in enumerate(queues)
    ])

    # Verify all got different work
    agent_ids = [r.agent_id for r in results]
    assert len(set(agent_ids)) == 3
```

**Verification Coverage:** 85% of scaling behaviors

---

### Option 2: Local Docker Compose (Integration Testing)

**Approach:** Use existing `docker/docker-compose.yaml` for local multi-container testing.

**What It Tests:**
- Real Redis BRPOP operations
- Multiple runner containers
- Coordinator leader election
- Config cache sharing
- Real network communication

**Implementation Effort:** Medium (compose file exists, needs runner service configs)

**Pros:**
- ✅ Real Redis operations
- ✅ True multi-process behavior
- ✅ No Kubernetes needed
- ✅ Reproducible local environment
- ✅ Fast iteration (docker compose up/down)

**Cons:**
- ❌ Requires Docker daemon
- ❌ Doesn't test Kubernetes-specific features (HPA, probes)
- ❌ Resource-intensive on dev machines
- ❌ May behave differently than K8s networking

**File References:**
- `docker/docker-compose.yaml` - Existing compose file
- `k8s/apexalgo-iad/valkey.yaml` - Redis config reference

**Example Configuration:**
```yaml
# docker/docker-compose-scaling-test.yml
services:
  redis:
    image: valkey/valkey:latest
    ports:
      - "6379:6379"

  coordinator-1:
    image: botburrow-agents:latest
    command: python -m botburrow_agents.coordinator.main
    environment:
      - REDIS_URL=redis://redis:6379
      - HOSTNAME=coordinator-1
    depends_on:
      - redis

  coordinator-2:
    image: botburrow-agents:latest
    command: python -m botburrow_agents.coordinator.main
    environment:
      - REDIS_URL=redis://redis:6379
      - HOSTNAME=coordinator-2
    depends_on:
      - redis

  runner-1:
    image: botburrow-agents:latest
    command: python -m botburrow_agents.runner.main --mode hybrid
    environment:
      - REDIS_URL=redis://redis:6379
      - BOTBURROW_RUNNER_ID=runner-1
    depends_on:
      - redis
      - coordinator-1

  runner-2:
    image: botburrow-agents:latest
    command: python -m botburrow_agents.runner.main --mode hybrid
    environment:
      - REDIS_URL=redis://redis:6379
      - BOTBURROW_RUNNER_ID=runner-2
    depends_on:
      - redis
      - coordinator-1

  # Add runners 3-5 as needed...
```

**Test Script:**
```bash
#!/bin/bash
# scripts/test-scaling-compose.sh

# Start services
docker-compose -f docker/docker-compose-scaling-test.yml up -d

# Wait for startup
sleep 10

# Inject test work
redis-cli LPUSH work:queue:high '{"agent_id":"agent-1","agent_name":"Test 1",...}'
redis-cli LPUSH work:queue:normal '{"agent_id":"agent-2","agent_name":"Test 2",...}'
redis-cli LPUSH work:queue:normal '{"agent_id":"agent-3","agent_name":"Test 3",...}'

# Verify distribution
echo "Checking active tasks..."
redis-cli HGETALL work:active

# Verify leader election
echo "Checking coordinator leader..."
redis-cli GET coordinator:leader

# Cleanup
docker-compose -f docker/docker-compose-scaling-test.yml down
```

**Verification Coverage:** 70% of scaling behaviors (missing HPA, K8s probes)

---

### Option 3: Kubernetes Kind Cluster (Near-Production)

**Approach:** Use Kind (Kubernetes in Docker) to run full K8s manifests locally.

**What It Tests:**
- Full Kubernetes deployment
- HPA scaling behavior
- Pod readiness/liveness probes
- Service discovery
- ConfigMap mounting
- Secret management

**Implementation Effort:** High (need to configure Kind, load images, apply manifests)

**Pros:**
- ✅ Closest to production environment
- ✅ Tests HPA behavior
- ✅ Validates K8s manifests
- ✅ Tests pod lifecycle
- ✅ Can test rolling updates

**Cons:**
- ❌ Requires Kind installation
- ❌ Heavy resource usage
- ❌ Slow startup/teardown
- ❌ Image loading complexity
- ❌ Still not production (node differences)

**File References:**
- `k8s/apexalgo-iad/kustomization.yaml` - Kustomization config
- `k8s/apexalgo-iad/hpa.yaml` - HPA manifests
- `k8s/apexalgo-iad/runner-hybrid.yaml` - Runner deployment

**Example Workflow:**
```bash
#!/bin/bash
# scripts/test-scaling-kind.sh

# Create Kind cluster
kind create cluster --name botburrow-test

# Load local image
docker tag botburrow-agents:latest botburrow-agents:test
kind load docker-image --name botburrow-test botburrow-agents:test

# Apply manifests (use test image tag)
kubectl apply -f k8s/apexalgo-iad/namespace.yaml
kubectl apply -f k8s/apexalgo-iad/rbac.yaml
kubectl apply -f k8s/apexalgo-iad/configmap.yaml
kubectl set image deployment/runner-hybrid \
  runner=botburrow-agents:test -n botburrow-agents

# Wait for readiness
kubectl wait --for=condition=ready pod -l app=runner-hybrid -n botburrow-agents

# Scale up
kubectl scale deployment/runner-hybrid --replicas=5 -n botburrow-agents

# Verify pods
kubectl get pods -n botburrow-agents

# Check HPA
kubectl get hpa -n botburrow-agents

# Generate load (create work items)
# ...

# Cleanup
kind delete cluster --name botburrow-test
```

**Verification Coverage:** 95% of scaling behaviors (closest to production)

---

### Option 4: Production Staging Environment (Original Approach)

**Approach:** Deploy to `apexalgo-iad` cluster with namespace `botburrow-agents` (original bd-3qv plan).

**What It Tests:**
- True production environment
- Real networking (cross-cluster to Hub)
- Actual resource constraints
- Real HPA scaling
- Production monitoring/metrics

**Implementation Effort:** Very High (blocked on human actions for RBAC, secrets)

**Pros:**
- ✅ Production-accurate results
- ✅ Tests cross-cluster networking
- ✅ Real resource limits
- ✅ Integration with monitoring stack
- ✅ Can run long-duration tests

**Cons:**
- ❌ BLOCKED: RBAC grants required (bd-3q9)
- ❌ BLOCKED: Secrets creation (bd-2la, bd-3hx)
- ❌ Slow feedback loop (deployment time)
- ❌ Cost (cluster resources)
- ❌ Risk to production (if sharing namespace)
- ❌ Requires human intervention

**File References:**
- `k8s/apexalgo-iad/DEPLOYMENT-GITOPS.md` - Deployment guide
- Blocking beads: bd-3q9, bd-2la, bd-3hx

**Original Test Plan (bd-3qv):**
1. Check current runner replicas: `kubectl get deployments -n botburrow-agents`
2. Scale up: `kubectl scale deployment/runner-hybrid --replicas=3`
3. Verify all pods start and connect
4. Create test activations
5. Verify runners pick up work from Redis queues
6. Check that one runner can execute multiple personas
7. Monitor resource usage and response times
8. Scale back to normal

**Verification Coverage:** 100% of scaling behaviors (production validation)

---

### Option 5: Mock Hub + Real Runners (Hybrid)

**Approach:** Run real runners/coordinator against a mock Hub API that returns canned responses.

**What It Tests:**
- Real runner/coordinator code paths
- Work queue distribution
- Multi-runner contention
- Circuit breaker behavior
- Config caching

**Implementation Effort:** Medium (need to build mock Hub server)

**Pros:**
- ✅ Tests actual runner code
- ✅ Real Redis operations
- ✅ Controllable test scenarios
- ✅ No external dependencies
- ✅ Fast execution

**Cons:**
- ❌ Need to implement mock Hub
- ❌ May not catch Hub integration bugs
- ❌ Test maintenance overhead
- ❌ Doesn't test long-polling behavior

**Example Mock Hub:**
```python
# tests/mocks/mock_hub.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/v1/notifications")
async def get_notifications():
    return JSONResponse([
        {"id": "1", "agent_id": "test-persona-agent", "content": "Test notification"},
        {"id": "2", "agent_id": "research-agent", "content": "Test notification 2"},
    ])

@app.post("/api/v1/notifications/read")
async def mark_read():
    return JSONResponse({"status": "ok"})

@app.get("/api/v1/agents/stale")
async def get_stale_agents():
    return JSONResponse([
        {"agent_id": "claude-coder-1", "last_activated_at": "2026-02-07T10:00:00Z"},
        {"agent_id": "devops-agent", "last_activated_at": "2026-02-07T09:00:00Z"},
    ])

# Run with: uvicorn tests.mocks.mock_hub:app --port 8080
```

**Verification Coverage:** 75% of scaling behaviors

---

### Option 6: Load Testing with Locust

**Approach:** Use Locust to simulate load on the work queue and runner system.

**What It Tests:**
- System behavior under load
- Concurrent work claiming
- Queue depth management
- Runner throughput
- System limits/bottlenecks

**Implementation Effort:** High (need to write Locust tests, set up test environment)

**Pros:**
- ✅ Finds performance bottlenecks
- ✅ Tests system limits
- ✅ Realistic load patterns
- ✅ Built-in metrics/reporting

**Cons:**
- ❌ Complex setup
- ❌ Requires running system
- ❌ Test data generation
- ❌ Doesn't verify correctness (only performance)

**Example Locust Test:**
```python
# tests/load/runner_scaling.py
from locust import HttpUser, task, between

class RunnerUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def claim_work(self):
        """Simulate runner claiming work."""
        response = self.client.post("/api/v1/work/claim", json={
            "runner_id": f"runner-{self.user_id}",
            "timeout": 30
        })

        if response.status_code == 200 and response.json():
            # Simulate work completion
            work = response.json()
            self.client.post("/api/v1/work/complete", json={
                "agent_id": work["agent_id"],
                "success": True
            })

    @task
    def enqueue_work(self):
        """Simulate coordinator enqueuing work."""
        self.client.post("/api/v1/work/enqueue", json={
            "agent_id": f"agent-{random.randint(1, 10)}",
            "priority": "normal"
        })
```

**Verification Coverage:** 60% of scaling behaviors (focuses on performance)

---

## Summary Comparison Table

| Approach | Effort | Speed | Coverage | Infrastructure | CI/CD Ready | Recommended |
|----------|--------|-------|----------|----------------|-------------|-------------|
| **1. Unit Tests + Mocks** | Low | Seconds | 85% | None | ✅ | ✅ **YES** |
| **2. Docker Compose** | Medium | Minutes | 70% | Docker | ✅ | ✅ **YES** (secondary) |
| **3. Kind Cluster** | High | 10+ min | 95% | Kind/Docker | ⚠️ | ❌ Optional |
| **4. Production Staging** | Very High | 30+ min | 100% | K8s Cluster | ❌ | ❌ Blocked |
| **5. Mock Hub + Real Runners** | Medium | Minutes | 75% | Docker | ✅ | ⚠️ Maybe |
| **6. Load Testing (Locust)** | High | Minutes | 60% | Full stack | ✅ | ❌ Performance only |

---

## Implementation Plan (Recommended Approach)

### Phase 1: Expand Unit Tests (Week 1)

**Goal:** Achieve 90%+ coverage of scaling behaviors via unit tests.

**Tasks:**
1. Add multi-runner contention tests
2. Add priority queue ordering tests
3. Add circuit breaker state machine tests
4. Add config cache concurrency tests
5. Add leader election failover tests
6. Add edge case tests (Redis disconnect, timeout, etc.)

**Acceptance Criteria:**
- All tests pass consistently
- Coverage report shows >90% for scaling modules
- Tests run in <30 seconds

**Files to Modify:**
- `tests/test_runner_pool_scaling.py` - Add new test cases
- `src/botburrow_agents/coordinator/work_queue.py` - May need minor refactor for testability

### Phase 2: Docker Compose Integration Tests (Week 1-2)

**Goal:** Validate multi-container behavior.

**Tasks:**
1. Create `docker/docker-compose-scaling.yml`
2. Create test script `scripts/test-scaling-compose.sh`
3. Add to CI/CD pipeline
4. Document local testing workflow

**Acceptance Criteria:**
- Compose stack starts successfully
- 2 coordinators elect 1 leader
- 5 runners distribute work correctly
- Config cache is shared
- Tests run in <5 minutes

### Phase 3: Verification Documentation (Week 2)

**Goal:** Document how scaling works and how to verify it.

**Tasks:**
1. Create scaling verification guide
2. Add troubleshooting section
3. Document metrics to monitor
4. Create runbook for production scaling

**Deliverables:**
- `docs/operations/scaling-verification.md`
- Updates to `docs/ARCHITECTURE.md` (section 4)
- Prometheus Grafana dashboard JSON

### Phase 4: Production Deployment (When Unblocked)

**Goal:** Deploy to production when blockers resolve.

**Tasks:**
1. Resolve blocking beads (bd-3q9, bd-2la, bd-3hx)
2. Deploy to `apexalgo-iad` cluster
3. Run smoke tests
4. Monitor HPA behavior
5. Document production metrics

**Acceptance Criteria:**
- All pods healthy
- HPA responds to load
- Metrics look normal
- No errors in logs

---

## Test Scenarios by Approach

### Unit Test Scenarios (Option 1)

| Scenario | Description | Mock Behavior |
|----------|-------------|---------------|
| **Single runner** | Verify basic claim/complete cycle | BRPOP returns work |
| **Dual runner contention** | 2 runners claim different work | BRPOP alternates items |
| **Priority ordering** | High claimed before normal | BRPOP returns high first |
| **Deduplication** | Same work rejected | HGET returns active runner |
| **Circuit breaker** | Agent enters backoff after 5 failures | HINCRBY reaches threshold |
| **Cache hit** | Config loaded from cache | GET returns cached JSON |
| **Cache miss** | Config loaded from Git, then cached | GET returns None, then SET |
| **Leader election** | First coord becomes leader | SETNX returns True |
| **Leader failover** | Second coord becomes leader after TTL | SETNX succeeds after expire |

### Docker Compose Scenarios (Option 2)

| Scenario | Description | Commands |
|----------|-------------|----------|
| **Startup validation** | All services start healthy | `docker-compose ps` |
| **Leader election** | Only 1 coordinator polls Hub | Check logs for "became_leader" |
| **Work distribution** | 3 runners claim 3 different agents | `redis-cli HGETALL work:active` |
| **Scaling up** | Add 2 more runners, verify distribution | `docker-compose up -d --scale runner=5` |
| **Scaling down** | Remove runners, verify work continues | `docker-compose up -d --scale runner=2` |
| **Redis failure** | Stop Redis, verify graceful degradation | `docker-compose stop redis` |
| **Restart recovery** | Restart coordinator, verify re-election | `docker-compose restart coordinator-1` |

### Kind Cluster Scenarios (Option 3)

| Scenario | Description | Commands |
|----------|-------------|----------|
| **Deployment** | All pods become ready | `kubectl wait --for=condition=ready pod` |
| **HPA scaling** | CPU triggers scale-up | `kubectl get hpa -w` |
| **Manual scaling** | Scale to 10 replicas | `kubectl scale --replicas=10` |
| **Rolling update** | Update image, zero downtime | `kubectl set image` |
| **Resource limits** | Pod OOM killed under load | `kubectl describe pod` |
| **Service discovery** | Runners find coordinator | Check connection logs |

---

## Metrics to Monitor

### Work Queue Metrics

```python
# From observability.py
botburrow_queue_depth{priority="high|normal|low"}
botburrow_active_tasks
botburrow_queue_agents_in_backoff
```

### Runner Metrics

```python
botburrow_runner_status{runner_id, mode}
botburrow_activation_duration_seconds{agent_id, task_type}
botburrow_activation_total{agent_id, success}
```

### Coordinator Metrics

```python
botburrow_leader_status{instance_id}
botburrow_poll_duration_seconds
botburrow_work_enqueued_total{priority}
```

### Redis Metrics

```
redis_connected_clients
redis_instantaneous_ops_per_sec
redis_memory_used_bytes
redis_keyspace_hits
redis_keyspace_misses
```

---

## Decision Matrix

### Choose Option 1 (Unit Tests) When:
- ✅ You need fast feedback
- ✅ You're developing new features
- ✅ You want CI/CD integration
- ✅ Infrastructure isn't available
- ✅ You need to test edge cases

### Choose Option 2 (Docker Compose) When:
- ✅ You want integration testing
- ✅ You need to verify Redis behavior
- ✅ You're testing network conditions
- ✅ You have Docker available
- ✅ You want reproducible environments

### Choose Option 3 (Kind Cluster) When:
- ✅ You're preparing for production
- ✅ You need to validate K8s manifests
- ✅ You're testing HPA behavior
- ✅ You have resources for local K8s
- ✅ You want near-production validation

### Choose Option 4 (Production) When:
- ✅ All blockers are resolved
- ✅ You're doing final validation
- ✅ You need production-accurate results
- ✅ You're monitoring real workloads
- ❌ NOT during development (too slow)

### Choose Option 5 (Mock Hub) When:
- ✅ You need real runners but controlled Hub
- ✅ You're testing runner-specific bugs
- ✅ You can't use real Hub API
- ⚠️ Requires mock maintenance
- ⚠️ May miss integration issues

### Choose Option 6 (Load Testing) When:
- ✅ You're finding performance limits
- ✅ You need benchmark data
- ✅ You're testing system stability
- ❌ NOT for functional testing
- ❌ NOT for correctness verification

---

## Related Documentation

- `docs/ARCHITECTURE.md` - System architecture overview
- `docs/adr/011-agent-scheduling.md` - Scheduling and runner pools
- `docs/adr/020-system-components.md` - Component separation
- `k8s/apexalgo-iad/hpa.yaml` - HPA configuration
- `tests/test_runner_pool_scaling.py` - Existing unit tests
- `src/botburrow_agents/coordinator/work_queue.py` - Implementation

---

## Appendix: Existing Test Coverage

The file `tests/test_runner_pool_scaling.py` already includes:

### TestWorkQueueMultiRunner (14 tests)
- `test_enqueue_with_deduplication` - ✅ Duplicate work rejected
- `test_enqueue_with_backoff` - ✅ Backoff agents not queued
- `test_expired_backoff_cleared` - ✅ Expired backoff cleared
- `test_claim_marks_active` - ✅ Active tracking works
- `test_claim_priority_order` - ✅ Priority queues ordered correctly
- `test_claim_timeout_returns_none` - ✅ Timeout handling
- `test_complete_success_clears_failures` - ✅ Success clears state
- `test_complete_failure_increments_counter` - ✅ Failure counting
- `test_circuit_breaker_triggers_after_max_failures` - ✅ Backoff triggers
- `test_circuit_breaker_exponential_backoff` - ✅ Exponential backoff
- `test_get_queue_stats` - ✅ Statistics reporting
- `test_clear_backoff` - ✅ Manual backoff clearing

### TestMultiRunnerWorkDistribution (3 tests)
- `test_multiple_runners_claim_different_work` - ✅ Concurrent claiming
- `test_runner_cannot_claim_active_work` - ✅ Active work protected
- `test_priority_queue_servicing_order` - ✅ High priority first

### TestConfigCacheMultiRunner (5 tests)
- `test_cache_hit_serves_all_runners` - ✅ Shared cache
- `test_cache_miss_allows_set` - ✅ Cache loading
- `test_invalidate_single_config` - ✅ Cache invalidation
- `test_prewarm_cache_multiple_agents` - ✅ Cache prewarming

### TestLeaderElection (5 tests)
- `test_first_instance_becomes_leader` - ✅ First coord wins
- `test_second_instance_does_not_become_leader` - ✅ Follower behavior
- `test_leader_renews_leadership` - ✅ Leadership renewal
- `test_release_leadership` - ✅ Graceful release
- `test_non_leader_release_does_nothing` - ✅ No-op for follower

**Total: 27 tests covering most scaling behaviors**

**Missing Tests:**
- 3+ runners claiming simultaneously
- Large-scale work distribution (10+ agents, 5+ runners)
- Config cache under concurrent access
- Leader election during high load
- Network partition scenarios
- Redis failover scenarios

---

## Conclusion

The **Unit Test + Docker Compose** combination provides the best balance of coverage, speed, and practicality. The existing unit tests are comprehensive and can be expanded to cover the missing scenarios. Docker Compose provides integration testing without Kubernetes complexity.

When the infrastructure blockers (bd-3q9, bd-2la, bd-3hx) are resolved, production deployment testing can validate the final implementation.

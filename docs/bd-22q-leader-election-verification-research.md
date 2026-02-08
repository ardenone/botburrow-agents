# Coordinator Leader Election Verification: Research and Options Analysis

**Bead:** bd-22q (Alternative: Research and document options)
**Original Bead:** bd-31k (Verify coordinator leader election and work distribution)
**Date:** 2026-02-08
**Approach:** research-only

---

## Executive Summary

This document provides a comprehensive analysis of verification approaches for the botburrow-agents coordinator leader election and work distribution system. The research aims to inform human decision-making on the best path forward given current constraints.

**Key Finding:** The original bead bd-31k is blocked by deployment prerequisites (bd-33k → bd-3qi9 requiring secret values). Multiple viable alternative approaches exist, each with different trade-offs.

---

## Background: What Needs Verification

The coordinator service implements:
1. **Leader Election** - Ensures only one coordinator polls Hub (prevents duplicate work)
2. **Work Queue Distribution** - Distributes work across priority queues (high/normal/low)
3. **Deduplication** - Prevents duplicate work items for same agent
4. **Circuit Breaker** - Backoff for repeatedly failing agents

**Architecture:**
```
Hub (API) → Coordinator (leader-elected) → Redis Work Queue → Runners
```

**Leader Election Implementation:**
- Redis SETNX pattern with 30-second TTL
- Instance ID from HOSTNAME environment variable
- Lua script for graceful leadership release
- `coordinator:leader` key ensures single leader

---

## Verification Approaches Comparison

### Approach 1: Full Kubernetes Deployment Verification

**Description:** Deploy the full coordinator stack to apexalgo-iad cluster and verify all functionality in production-like environment.

**What It Verifies:**
- Real Kubernetes pod lifecycle
- Leader election across K8s pods
- ConfigMap and Secret mounting
- Service discovery and networking
- Work queue with real Redis
- Multi-pod failover scenarios

**Requirements:**
- bd-33k (Deploy coordinator stack) - must complete first
- bd-3qi9 (Human: Secret values) - human must provide credentials
- SealedSecret creation for secure credential storage
- ArgoCD Application manifest deployment

**Pros:**
- ✅ Most comprehensive verification
- ✅ Tests actual production environment
- ✅ Validates K8s-specific behaviors (pod restart, ConfigMaps)
- ✅ Catches environment-specific issues
- ✅ Highest confidence level

**Cons:**
- ❌ Blocked by human input (credentials)
- ❌ Requires full deployment infrastructure
- ❌ Longer feedback cycle
- ❌ Higher resource requirements
- ❌ Cannot proceed without unblocking

**Effort:** High (4-6 hours including setup, testing, teardown)
**Confidence Gained:** 95%

**Blockers:**
- bd-3qi9 (Human input for secret values)
- bd-x8o (Create SealedSecret from template)

---

### Approach 2: Docker Compose Local Integration Testing

**Description:** Use Docker Compose to run coordinator, Redis, and runners locally for integration testing.

**What It Verifies:**
- Leader election with real Redis
- Work queue distribution
- Multi-instance coordination
- Network communication
- Basic failover (container restart)

**Requirements:**
- Docker and Docker Compose installed
- Hub API accessible (or mocked)
- Project's docker-compose.yaml

**Implementation:**
```bash
cd /home/coder/botburrow-agents
docker compose -f docker/docker-compose.yaml up -d
docker compose -f docker/docker-compose.yaml up -d --scale coordinator=2
docker compose -f docker/docker-compose.yaml logs coordinator | grep -E "(became_leader|is_leader)"
```

**Pros:**
- ✅ Uses real Redis (not fakeredis)
- ✅ Tests network communication
- ✅ Quick to run (minutes)
- ✅ No human input required
- ✅ Repeatable and automated
- ✅ Can test multi-instance scenarios

**Cons:**
- ❌ No Kubernetes-specific testing
- ❌ Missing K8s ConfigMaps/Secrets
- ❌ Limited pod lifecycle testing
- ❌ Different networking model than K8s
- ❌ May miss K8s-specific bugs

**Effort:** Low (1-2 hours)
**Confidence Gained:** 75%

**Blockers:** None (can proceed immediately)

---

### Approach 3: fakeredis Unit Testing (Already Completed)

**Description:** Run unit tests with fakeredis to verify leader election logic in isolation.

**Status:** ✅ **COMPLETED** - All tests passed

**What Was Verified:**
- Leader election algorithm (SETNX pattern)
- Single instance becomes leader
- Second instance cannot steal leadership
- TTL is set correctly (30s)
- Work queue deduplication
- Circuit breaker backoff logic

**Results:**
```
[info] leader_election_verification_all_tests_passed
[info] work_queue_deduplication_verification_all_tests_passed
[info] all_verifications_passed
```

**Implementation:**
```bash
cd /home/coder/botburrow-agents
python3 scripts/verify_leader_election.py
```

**Pros:**
- ✅ Fast (seconds to run)
- ✅ No external dependencies
- ✅ Tests core logic thoroughly
- ✅ Automated and repeatable
- ✅ Already completed

**Cons:**
- ❌ Not real Redis (fakeredis simulation)
- ❌ No network testing
- ❌ No distributed concurrency
- ❌ Misses environment-specific issues

**Effort:** Complete (30 minutes)
**Confidence Gained:** 60%

**Blockers:** None (already completed)

---

### Approach 4: Code Review and Static Analysis

**Description:** Thorough review of leader election implementation for correctness.

**Status:** ✅ **COMPLETED** as part of bd-87d workaround

**What Was Verified:**
- SETNX pattern correctness
- TTL configuration (30s heartbeat)
- Lua script for graceful release
- Instance ID uniqueness via HOSTNAME
- Poll guard (non-leaders skip Hub polling)
- Prometheus metrics for leader status

**Findings:**
- Algorithm is correct (Redis SETNX is industry standard)
- TTL appropriate for coordinator HA
- Poll guard correctly prevents duplicate Hub polling
- Metrics enable observability

**Pros:**
- ✅ No runtime required
- ✅ Fast to complete
- ✅ Documents understanding
- ✅ Identifies logical issues
- ✅ Already completed

**Cons:**
- ❌ Doesn't test runtime behavior
- ❌ May miss concurrency bugs
- ❌ Doesn't validate performance

**Effort:** Complete (1 hour)
**Confidence Gained:** 50% (supplemental)

**Blockers:** None (already completed)

---

### Approach 5: Hybrid Approach (Recommended)

**Description:** Combine completed unit tests with Docker Compose integration testing for comprehensive verification without K8s deployment.

**Strategy:**
1. ✅ **Step 1 (Complete):** fakeredis unit tests - verify core logic
2. ✅ **Step 2 (Complete):** Code review - validate implementation correctness
3. ⏸️ **Step 3 (Pending):** Docker Compose integration - verify real Redis coordination
4. ⏸️ **Step 4 (Blocked):** K8s deployment - defer until unblocked

**Implementation Plan:**
```bash
# Step 3: Run Docker Compose with 2 coordinator instances
cd /home/coder/botburrow-agents
docker compose -f docker/docker-compose.yaml up -d --scale coordinator=2

# Verify only one leader via logs
docker compose -f docker/docker-compose.yaml logs coordinator | grep became_leader

# Check leader status metrics
curl http://localhost:9090/metrics | grep botburrow_coordinator_is_leader

# Test failover by killing leader container
docker compose -f docker/docker-compose.yaml kill coordinator@1
docker compose -f docker/docker-compose.yaml logs coordinator | grep became_leader
```

**Pros:**
- ✅ Can proceed immediately (no blockers)
- ✅ Combines strengths of multiple approaches
- ✅ High confidence without K8s deployment
- ✅ Documents verification thoroughly
- ✅ Creates reusable testing methodology

**Cons:**
- ❌ Still doesn't test K8s-specific behaviors
- ❌ Requires Docker setup
- ❌ K8s verification remains deferred

**Effort:** Medium (2-3 hours total)
**Confidence Gained:** 80% (sufficient for most purposes)

**Blockers:** None (can proceed immediately)

---

## Decision Matrix

| Approach | Effort | Confidence | Blocked | Time to Complete | Recommended |
|----------|--------|------------|---------|------------------|-------------|
| **1. Full K8s Deployment** | High | 95% | Yes | 4-6 hours + wait for unblock | No |
| **2. Docker Compose** | Low | 75% | No | 1-2 hours | **Yes** |
| **3. fakeredis Unit Tests** | Complete | 60% | No | Done (30 min) | ✅ Done |
| **4. Code Review** | Complete | 50% | No | Done (1 hour) | ✅ Done |
| **5. Hybrid** | Medium | 80% | No | 2-3 hours | **Yes** |

---

## Recommendation

**Primary Recommendation: Approach 5 (Hybrid)**

**Rationale:**
1. Can proceed immediately without waiting for human input
2. Combines completed work (unit tests + code review) with integration testing
3. Provides 80% confidence level - sufficient for most verification purposes
4. Creates comprehensive documentation
5. Leaves full K8s verification as follow-up when deployment unblocks

**Action Plan:**
1. ✅ **Completed:** fakeredis unit tests
2. ✅ **Completed:** Code review
3. **Next:** Docker Compose integration testing
4. **Document:** Comprehensive verification summary
5. **Defer:** Full K8s deployment until bd-3qi9 unblocks

**Follow-up Work:**
Once bd-3qi9 (secret values) is resolved:
- Execute Approach 1 (Full K8s Deployment Verification)
- Compare Docker Compose results with K8s results
- Document any discrepancies or K8s-specific issues

---

## Alternative Recommendations

### If Time is Critical
**Use Approach 2 (Docker Compose only)** - Fastest path to meaningful verification

### If Maximum Confidence Required
**Wait for Approach 1 (Full K8s)** - Only if 95% confidence is necessary

### If Documentation is Primary Goal
**Accept current state (Approaches 3+4)** - Already verified core logic via unit tests

---

## Verification Checklist

### Completed (Approaches 3+4)
- [x] Leader election SETNX pattern correctness
- [x] TTL configuration validation
- [x] Duplicate work prevention
- [x] Circuit breaker logic
- [x] Poll guard implementation
- [x] Code review findings

### Pending (Approach 2 or 5)
- [ ] Real Redis leader election
- [ ] Multi-instance coordination
- [ ] Network communication testing
- [ ] Leader failover verification
- [ ] Work queue distribution

### Blocked (Approach 1)
- [ ] Kubernetes deployment
- [ ] Pod lifecycle testing
- [ ] ConfigMap/Secret mounting
- [ ] K8s service discovery

---

## Next Steps

### Immediate (No blockers)
1. Run Docker Compose integration testing
2. Document results
3. Update verification summary
4. Close bd-22q with recommendation

### When Unblocked
1. Resolve bd-3qi9 (provide secret values)
2. Complete bd-33k (K8s deployment)
3. Execute full K8s verification
4. Compare results with hybrid approach

---

## References

- Original bead: bd-31k (Verify coordinator leader election and work distribution)
- Implementation: `src/botburrow_agents/coordinator/work_queue.py:371-443`
- Poll guard: `src/botburrow_agents/coordinator/main.py:177-210`
- Unit tests: `scripts/verify_leader_election.py`
- Docker Compose: `docker/docker-compose.yaml`
- Previous work: `docs/bd-87d-workaround-verification-summary.md`

---

## Appendix: Quick Start Commands

### Docker Compose Verification
```bash
# Start services
cd /home/coder/botburrow-agents
docker compose -f docker/docker-compose.yaml up -d

# Scale to 2 coordinators
docker compose -f docker/docker-compose.yaml up -d --scale coordinator=2

# Check logs for leader election
docker compose -f docker/docker-compose.yaml logs coordinator | grep -E "(became_leader|is_leader)"

# Verify metrics
curl http://localhost:9090/metrics | grep botburrow_coordinator_is_leader

# Test failover
docker compose -f docker/docker-compose.yaml kill coordinator@1
docker compose -f docker/docker-compose.yaml logs coordinator | grep became_leader

# Cleanup
docker compose -f docker/docker-compose.yaml down
```

### Unit Tests (Already Run)
```bash
cd /home/coder/botburrow-agents
python3 scripts/verify_leader_election.py
```

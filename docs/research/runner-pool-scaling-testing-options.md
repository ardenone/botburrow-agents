# Runner Pool Scaling Testing: Approach Comparison

**Original Bead:** bd-3qv - Test agent runner pool scaling
**Research Bead:** bd-1a9 - Alternative: Research and document options
**Date:** 2026-02-08
**Status:** Research Complete

---

## Executive Summary

The botburrow-agents system uses a **1:Many scaling model** where each runner can handle multiple agent personas via a Redis-based work queue. Testing this scaling capability presents challenges because the full infrastructure requires:

- Botburrow Hub API access
- Cloudflare R2 storage credentials
- Forgejo and GitHub tokens
- Valkey/Redis deployment
- Git repository for agent definitions

This document compares **4 testing approaches** with implementation details, pros/cons, and recommendations.

---

## Background: How Runner Pool Scaling Works

### Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│ Coordinator │────▶│   Valkey    │◀────│   Runners    │
│   (Leader)  │     │  (Redis)    │     │   (1-N)      │
└─────────────┘     └─────────────┘     └──────────────┘
       │                  │                     │
       │                  │                     │
       ▼                  ▼                     ▼
  ┌─────────┐      ┌──────────┐         ┌──────────┐
  │   Hub   │      │   Work   │         │  Agents  │
  │   API   │      │  Queues  │         │ Execution│
  └─────────┘      └──────────┘         └──────────┘
```

### Key Scaling Properties

1. **Horizontal Scaling**: Runners scale via Kubernetes HPA (min 3, max 20 replicas)
2. **Work Distribution**: BRPOP (blocking Redis) for atomic work claiming
3. **Deduplication**: Only one runner can work on an agent at a time
4. **Priority Queues**: High/Normal/Low priority levels
5. **Leader Election**: Only one coordinator polls Hub (prevents duplicate work)

### What We Need to Test

1. **Multi-runner coordination**: Multiple runners claim different work without conflicts
2. **Deduplication**: Same agent cannot be claimed by two runners simultaneously
3. **Priority handling**: High-priority work is claimed before low-priority
4. **Circuit breaker**: Failed agents enter backoff correctly
5. **Config caching**: All runners share cached agent configs
6. **Resource usage**: CPU/memory behavior under load

---

## Option 1: Full Infrastructure Deployment

**Description:** Deploy the complete botburrow-agents stack to a Kubernetes cluster with all external dependencies.

### Implementation Steps

```bash
# 1. Create namespace
kubectl create namespace botburrow-agents

# 2. Create required secrets
kubectl create secret generic botburrow-agents-secrets \
  --from-literal=HUB_API_KEY="$HUB_API_KEY" \
  --from-literal=R2_ENDPOINT="$R2_ENDPOINT" \
  --from-literal=R2_ACCESS_KEY="$R2_ACCESS_KEY" \
  --from-literal=R2_SECRET_KEY="$R2_SECRET_KEY" \
  --from-literal=FORGEJO_USER="$FORGEJO_USER" \
  --from-literal=FORGEJO_TOKEN="$FORGEJO_TOKEN" \
  --from-literal=GITHUB_USER="$GITHUB_USER" \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  -n botburrow-agents

# 3. Deploy core infrastructure
kubectl apply -f k8s/apexalgo-iad/valkey.yaml
kubectl apply -f k8s/apexalgo-iad/configmap.yaml
kubectl apply -f k8s/apexalgo-iad/coordinator.yaml
kubectl apply -f k8s/apexalgo-iad/runner-hybrid.yaml
kubectl apply -f k8s/apexalgo-iad/hpa.yaml

# 4. Scale runners for testing
kubectl scale deployment/runner-hybrid -n botburrow-agents --replicas=3

# 5. Verify work distribution
kubectl logs -n botburrow-agents -l app=runner-hybrid --tail=100

# 6. Monitor resource usage
kubectl top pods -n botburrow-agents
```

### Pros

- **Production-like**: Tests actual runtime behavior
- **End-to-end**: Covers full integration stack
- **Real metrics**: Actual resource usage, latency, throughput
- **Hub integration**: Tests real API interactions
- **Reveals real issues**: Finds problems that mocks miss

### Cons

- **Secret management**: Requires 8+ external credentials
- **Slow iteration**: Deployment cycles take minutes
- **Cost**: Uses cluster resources, may incur billing
- **Complex setup**: Multiple interdependent services
- **Hard to debug**: Limited visibility into distributed systems
- **Dependency on external services**: Hub availability affects tests

### When to Use

- **Pre-production validation**: Before releasing to production
- **Performance testing**: Load testing with realistic traffic
- **Infrastructure verification**: Validating ArgoCD/Kubernetes configs

### Estimated Effort

- **Setup**: 2-4 hours (secret gathering, deployment)
- **Test execution**: 1-2 hours
- **Debugging**: Variable (depends on issues found)

---

## Option 2: Docker Compose Local Testing

**Description:** Use the existing `docker/docker-compose.yaml` for local development and testing.

### Implementation Steps

```bash
# 1. Navigate to docker directory
cd /home/coder/botburrow-agents/docker

# 2. Set environment variables
export HUB_URL="${HUB_URL:-http://host.docker.internal:8000}"
export REDIS_URL="redis://valkey:6379/0"
export AGENT_DEFINITIONS_REPO="jedarden/agent-definitions"
export AGENT_DEFINITIONS_BRANCH="main"

# 3. Build and start services
docker-compose up --build -d

# 4. Scale runners for testing
docker-compose up --scale runner=3

# 5. View logs
docker-compose logs -f runner

# 6. Test work distribution
# Simulate Hub API calls to enqueue work
curl -X POST http://localhost:8000/test/enqueue \
  -d '{"agent_id": "test-agent-1", "priority": "high"}'
```

### Pros

- **Quick iteration**: Restart services in seconds
- **Local debugging**: Full access to logs, filesystem
- **No external secrets**: Uses mock Hub or host.docker.internal
- **Low cost**: Runs locally, no cluster usage
- **Existing infrastructure**: docker-compose.yaml already exists

### Cons

- **Not production-like**: Different networking, resource constraints
- **Mock Hub required**: Need to simulate Hub API endpoints
- **Limited scale**: Can't test large-scale scenarios (20+ runners)
- **Single-machine**: Doesn't test distributed failure modes
- **Docker Desktop dependency**: Requires Docker daemon

### When to Use

- **Development testing**: Quick feedback during development
- **Integration testing**: Before deploying to cluster
- **CI/CD pipeline**: Automated tests in GitHub Actions

### Estimated Effort

- **Setup**: 30 minutes (environment variables, build)
- **Test execution**: 30 minutes
- **Total**: ~1 hour

### Existing Files

- `/home/coder/botburrow-agents/docker/docker-compose.yaml` - Compose stack definition

---

## Option 3: Unit/Integration Testing with Mocks

**Description:** Extend existing test suite with comprehensive scaling tests using mocked external dependencies.

### Implementation Steps

```python
# tests/test_runner_pool_scaling.py

import pytest
from unittest.mock import AsyncMock, patch
from botburrow_agents.coordinator.work_queue import WorkQueue
from botburrow_agents.runner.main import Runner

@pytest.mark.asyncio
async def test_multiple_runners_claim_different_work():
    """Verify multiple runners can claim different agents concurrently"""
    # Setup: Create 5 mock work items
    # Action: Start 3 mock runners
    # Assert: Each runner claims different work, no conflicts

@pytest.mark.asyncio
async def test_single_agent_deduplication():
    """Verify same agent cannot be claimed by two runners"""
    # Setup: Enqueue single agent
    # Action: Start 2 runners simultaneously
    # Assert: Only one runner successfully claims

@pytest.mark.asyncio
async def test_priority_queue_ordering():
    """Verify high-priority work is claimed before low-priority"""
    # Setup: Mix of high/normal/low priority work
    # Action: Start runner
    # Assert: High priority claimed first

@pytest.mark.asyncio
async def test_circuit_breaker_backoff():
    """Verify failed agents enter backoff correctly"""
    # Setup: Mock 5 consecutive failures
    # Action: Attempt to claim work
    # Assert: Agent in backoff, exponential delay applied

@pytest.mark.asyncio
async def test_config_cache_sharing():
    """Verify all runners share cached agent configs"""
    # Setup: One runner loads agent config
    # Action: Second runner needs same config
    # Assert: Cache hit, no Git fetch needed
```

```bash
# Run scaling tests
pytest tests/test_runner_pool_scaling.py -v
pytest tests/test_work_queue.py -v
pytest tests/integration/test_activation_flow.py -v
```

### Pros

- **Fast execution**: Tests run in seconds
- **Deterministic**: Full control over mock behavior
- **No secrets required**: All external services mocked
- **CI-friendly**: Easy to run in GitHub Actions
- **Isolated**: No dependency on external infrastructure
- **Comprehensive coverage**: Can test edge cases, error conditions

### Cons

- **Not production-like**: Mocks may not match real behavior
- **False confidence**: Tests may pass but real system fails
- **Maintenance burden**: Mocks must stay in sync with real APIs
- **Limited observability**: No real resource metrics
- **Missing integration issues**: Doesn't catch integration bugs

### When to Use

- **TDD workflow**: Write tests before implementation
- **Regression testing**: Ensure changes don't break functionality
- **CI/CD gate**: Fast feedback on pull requests
- **Edge case testing**: Test rare failure modes

### Estimated Effort

- **Setup**: 1-2 hours (test infrastructure)
- **Test writing**: 2-4 hours (comprehensive scenarios)
- **Maintenance**: Ongoing (update mocks with API changes)

### Existing Files

- `/home/coder/botburrow-agents/tests/test_work_queue.py` - Existing work queue tests
- `/home/coder/botburrow-agents/tests/test_runner_pool_scaling.py` - Scaling tests (partial)

---

## Option 4: Staging Environment with Reduced Scope

**Description:** Create a minimal staging namespace with only essential services, using test credentials and sandboxed external dependencies.

### Implementation Steps

```bash
# 1. Create staging namespace
kubectl create namespace botburrow-agents-staging

# 2. Deploy minimal infrastructure (no Hub, mock services only)
kubectl apply -f k8s/staging/valkey.yaml
kubectl apply -f k8s/staging/coordinator.yaml
kubectl apply -f k8s/staging/runner-hybrid.yaml

# 3. Use test/secrets with limited permissions
# - Test Hub API endpoint (read-only or sandboxed)
# - Test R2 bucket (separate from production)
# - Test Forgejo instance (or use public repos)

# 4. Deploy mock Hub service (optional)
kubectl apply -f k8s/staging/mock-hub.yaml

# 5. Run scaling tests
kubectl scale deployment/runner-hybrid -n botburrow-agents-staging --replicas=5

# 6. Monitor and collect metrics
kubectl logs -n botburrow-agents-staging -l app=runner-hybrid --tail=500
```

### Pros

- **Balanced approach**: More realistic than mocks, less risky than production
- **Isolated**: Separate namespace prevents production impact
- **Reduced credentials**: Can use limited-scope test credentials
- **Cluster context**: Tests real Kubernetes behavior (HPA, networking)
- **Reusable**: Can become permanent staging environment

### Cons

- **Still requires cluster**: Uses cluster resources
- **Some secrets needed**: Even test credentials require management
- **Mock Hub behavior**: May not match production exactly
- **Maintenance**: Staging environment needs updates
- **Complexity**: More moving parts than unit tests

### When to Use

- **Pre-production validation**: Final check before production
- **Feature testing**: Test new features in isolated environment
- **Demonstration**: Show system behavior to stakeholders

### Estimated Effort

- **Initial setup**: 2-3 hours (staging manifests, test credentials)
- **Test execution**: 1 hour
- **Maintenance**: Ongoing (sync with production changes)

---

## Comparison Matrix

| Criterion | Option 1: Full Infra | Option 2: Docker Compose | Option 3: Unit Tests | Option 4: Staging |
|-----------|---------------------|--------------------------|---------------------|-------------------|
| **Setup Time** | 2-4 hours | 30 minutes | 1-2 hours | 2-3 hours |
| **Execution Speed** | Slow (minutes) | Medium (seconds) | Fast (seconds) | Slow (minutes) |
| **Realism** | ★★★★★ | ★★★☆☆ | ★★☆☆☆ | ★★★★☆ |
| **Cost** | High (cluster) | Low (local) | None | Medium (cluster) |
| **Secrets Required** | 8+ | 0-2 | 0 | 2-4 |
| **Debuggability** | ★★☆☆☆ | ★★★★★ | ★★★★☆ | ★★★☆☆ |
| **CI/CD Friendly** | ★★☆☆☆ | ★★★★☆ | ★★★★★ | ★★☆☆☆ |
| **Maintenance** | Low | Low | High | Medium |
| **Can Test HPA** | Yes | No | No | Yes |
| **Can Test Real Hub** | Yes | No (mocked) | No (mocked) | Yes (test) |
| **Parallel Execution** | No | No | Yes | No |

---

## Recommendation

### For Maximum Coverage: **Hybrid Approach**

Combine all four approaches in a testing pyramid:

```
           ┌─────────────────────┐
           │   Option 1: Full   │  ← Pre-production validation
           │   Infrastructure    │     (before releases)
           └─────────────────────┘
                  ▲
           ┌─────────────────────┐
           │  Option 4: Staging │  ← Feature testing
           │   Environment       │     (new features)
           └─────────────────────┘
                  ▲
           ┌─────────────────────┐
           │  Option 2: Docker   │  ← Development testing
           │    Compose Local    │     (during dev)
           └─────────────────────┘
                  ▲
           ┌─────────────────────┐
           │ Option 3: Unit/     │  ← TDD + CI/CD
           │ Integration Tests   │     (every commit)
           └─────────────────────┘
```

### Implementation Priority

**Immediate (this week):**
1. **Extend Option 3**: Complete `test_runner_pool_scaling.py` with:
   - Multi-runner concurrent claiming test
   - Deduplication verification
   - Priority queue ordering
   - Circuit breaker behavior
   - Config cache sharing

**Short-term (this month):**
2. **Implement Option 2**: Enhance `docker/docker-compose.yaml` with:
   - Mock Hub service for work enqueueing
   - Multiple runner replicas
   - Test scripts for scaling validation

**Long-term (quarter):**
3. **Create Option 4**: Build staging environment for:
   - Pre-release validation
   - Feature testing
   - Performance benchmarks

**As needed:**
4. **Option 1**: Use full infrastructure deployment for:
   - Final pre-production validation
   - Performance/load testing
   - Infrastructure verification

---

## Testing Checklist

Regardless of approach, ensure these scenarios are covered:

- [ ] **Single runner**: Baseline functionality
- [ ] **Multiple runners**: 2+ runners claiming work concurrently
- [ ] **Deduplication**: Same agent not claimed twice
- [ ] **Priority queues**: High before normal before low
- [ ] **Circuit breaker**: Exponential backoff after failures
- [ ] **Config caching**: Shared cache across runners
- [ ] **Leader election**: Only one coordinator polls Hub
- [ ] **Scale up**: Adding runners mid-operation
- [ ] **Scale down**: Removing runners gracefully
- [ ] **Failure recovery**: Runner crash handling
- [ ] **Resource limits**: CPU/memory constraints
- [ ] **Network partition**: Valkey connectivity loss

---

## Related Files

- `/home/coder/botburrow-agents/tests/test_runner_pool_scaling.py` - Main scaling test file
- `/home/coder/botburrow-agents/tests/test_work_queue.py` - Work queue unit tests
- `/home/coder/botburrow-agents/docker/docker-compose.yaml` - Local development stack
- `/home/coder/botburrow-agents/k8s/apexalgo-iad/hpa.yaml` - HorizontalPodAutoscaler config
- `/home/coder/botburrow-agents/k8s/apexalgo-iad/runner-hybrid.yaml` - Runner deployment
- `/home/coder/botburrow-agents/src/botburrow_agents/coordinator/work_queue.py` - Queue implementation
- `/home/coder/botburrow-agents/src/botburrow_agents/runner/main.py` - Runner implementation

---

## Appendix: Existing Test Coverage

The project already has these tests:

```bash
# Work queue tests
pytest tests/test_work_queue.py -v
# - test_work_enqueue
# - test_work_claim
# - test_priority_ordering
# - test_deduplication
# - test_circuit_breaker
# - test_config_cache
# - test_leader_election

# Runner scaling tests (partial)
pytest tests/test_runner_pool_scaling.py -v
# - test_single_runner_work_claiming
# - test_multi_runner_work_distribution

# Integration tests
pytest tests/integration/test_activation_flow.py -v
```

**Status:** The existing tests cover basic scenarios but need enhancement for comprehensive scaling validation.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (bd-1a9)

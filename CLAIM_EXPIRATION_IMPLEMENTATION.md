# Claim Expiration Implementation

## Overview

This document describes the implementation of automatic claim expiration for stale worker assignments (bead bd-288u).

## Problem

Workers that crash or exit abnormally can leave beads in assigned state indefinitely, causing other workers to starve. This was discovered in bd-8q53 where all 12 open beads were stuck with stale assignees.

## Solution

Implemented a claim heartbeat system with automatic expiration:

1. **Claim Heartbeat System** - Workers automatically renew claims every 2-3 minutes
2. **Auto-release Stale Claims** - Claims without heartbeat for 10+ minutes are automatically cleaned up
3. **Graceful Shutdown** - Workers release claims when shutting down
4. **Configurable Timeouts** - All intervals are configurable via settings

## Architecture

### Components Modified

#### 1. Configuration (`config.py`)
Added three new settings:
- `claim_heartbeat_interval` (default: 120s) - How often workers renew claims
- `claim_expiration_threshold` (default: 600s) - When claims are considered stale
- `stale_claim_check_interval` (default: 60s) - How often to check for stale claims

#### 2. Assigner (`coordinator/assigner.py`)
- `renew_claim()` - Renews claim heartbeat to prevent expiration
- `cleanup_stale_claims()` - Scans for and removes stale claims
- Enhanced `_track_assignment()` - Creates initial heartbeat when claiming
- Enhanced `_cleanup_assignment()` - Removes heartbeat when releasing

#### 3. Runner (`runner/main.py`)
- `_claim_renewal_loop()` - Background task that renews claims during activations
- `_stale_claim_cleanup_loop()` - Background task that periodically cleans stale claims
- Enhanced `_activate_agent()` - Starts/stops claim renewal task
- Enhanced shutdown handler - Releases claims on graceful shutdown

#### 4. Observability (`observability.py`)
New Prometheus metrics:
- `botburrow_claim_renewals_total` - Total claim renewals (success/failed)
- `botburrow_stale_claims_cleaned_total` - Total stale claims cleaned
- `botburrow_active_claims` - Current number of active claims

### Data Flow

```
Worker Starts Activation
    ↓
Claim Agent (creates lock + heartbeat)
    ↓
Start Claim Renewal Task
    ↓
Every 2 minutes: Renew Heartbeat
    ↓
Activation Completes
    ↓
Stop Claim Renewal Task
    ↓
Release Claim (delete lock + heartbeat)
```

### Stale Claim Cleanup

```
Cleanup Task (runs every 60s)
    ↓
Scan all agent_lock:* keys
    ↓
For each lock:
    ↓
Check claim:heartbeat:* exists
    ↓
If NO heartbeat → Delete lock + cleanup
    ↓
If has heartbeat → Skip
```

## Redis Keys

- `agent_lock:{agent_id}` - Claim lock (TTL: 600s)
- `claim:heartbeat:{agent_id}` - Heartbeat timestamp (TTL: 600s)
- `agent:activation:{agent_id}` - Activation metadata with last_heartbeat

## Configuration Examples

### Fast Expiration (for testing)
```python
Settings(
    claim_heartbeat_interval=10,      # Renew every 10 seconds
    claim_expiration_threshold=30,    # Expire after 30 seconds
    stale_claim_check_interval=5,     # Check every 5 seconds
)
```

### Production (recommended)
```python
Settings(
    claim_heartbeat_interval=120,     # Renew every 2 minutes
    claim_expiration_threshold=600,   # Expire after 10 minutes
    stale_claim_check_interval=60,    # Check every 60 seconds
)
```

## Testing

### Unit Tests (`tests/test_assigner.py`)
- `TestAssignerClaimRenewal` - Tests for renew_claim()
- `TestAssignerStaleClaimCleanup` - Tests for cleanup_stale_claims()

### Integration Tests (`tests/test_claim_expiration.py`)
- `TestClaimLifecycle` - Full claim lifecycle tests
- `TestStaleClaimExpiration` - Expiration behavior tests
- `TestClaimRenewalFailure` - Failure scenario tests
- `TestMetrics` - Metrics recording tests

## Graceful Shutdown

Workers handle SIGINT/SIGTERM signals:
1. Set `_running = False`
2. Cancel background tasks
3. Release active claim (if any)
4. Close connections

This ensures claims are released even during planned shutdowns.

## Metrics & Observability

Monitor claim health via Prometheus:

```promql
# Claim renewal success rate
rate(botburrow_claim_renewals_total{status="success"}[5m]) /
rate(botburrow_claim_renewals_total[5m])

# Stale claims cleaned over time
rate(botburrow_stale_claims_cleaned_total[5m])

# Active claims
botburrow_active_claims
```

## Edge Cases Handled

1. **Worker crash** - Heartbeat expires → cleanup removes lock
2. **Network partition** - Renewal fails → heartbeat expires → cleanup
3. **Lock stolen** - Renewal detects and fails gracefully
4. **Multiple workers** - Cleanup is idempotent, safe to run on all workers
5. **Graceful shutdown** - Claims released explicitly before exit

## Success Criteria

✅ Workers auto-renew claims every 2-3 minutes
✅ Stale claims auto-expire after 10+ minutes
✅ Workers release claims on shutdown
✅ No manual intervention needed
✅ Comprehensive test coverage
✅ Prometheus metrics for monitoring

## Future Enhancements

1. Leader-based cleanup (only one worker does cleanup)
2. Heartbeat jitter to avoid thundering herd
3. Adaptive expiration threshold based on activation duration
4. Dead letter queue for repeatedly failing agents

# Bead Health Check System

**Status:** Implemented (bd-2wni)
**Created:** 2026-02-16
**Related:** bd-8q53 (Worker starvation incident)

## Overview

The bead health check system detects and automatically recovers from stuck beads before worker starvation occurs.

### What It Detects

1. **Unclaimed in_progress beads** (P0 severity)
   - Beads with `status=in_progress` but `claimed_by=null`
   - Violates state machine invariant
   - Causes worker starvation (workers cannot claim beads already in_progress)

2. **Expired claims** (P1 severity)
   - Beads with claims older than 1 hour
   - Indicates crashed or hung workers
   - Alert threshold: > 3 expired claims

3. **Low claim success rate** (P1 severity)
   - Overall claim success rate < 50%
   - Indicates systemic issues
   - Creates incident bead for investigation

### Auto-Recovery

When invalid states are detected:
1. **Log violation** with bead details
2. **Reset bead** to "open" status
3. **Create incident bead** (type: human, priority: P0 or P1)
4. **Alert monitoring system** (via incident bead)

## Components

### 1. Health Check Script

**File:** `scripts/bead-health-check.sh`

**Usage:**
```bash
# Check only (no fixes)
./scripts/bead-health-check.sh --workspace=/path/to/project --check-only

# Auto-fix issues
./scripts/bead-health-check.sh --workspace=/path/to/project --auto-fix

# Check current workspace
cd ~/botburrow-agents
../scripts/bead-health-check.sh --workspace=$(pwd) --auto-fix
```

**Features:**
- Detects all three violation types
- Auto-fixes unclaimed beads and expired claims
- Creates incident beads with full context
- Colored output for readability
- Safe to run anytime (idempotent)

**Exit Codes:**
- `0` - All checks passed, no issues
- `1` - Issues detected (check output for details)

### 2. Worker Integration

Health checks run automatically at worker startup:

**File:** `scripts/bead-worker.sh` (modified)

**Behavior:**
```bash
# Workers run health check before processing beads
main() {
    log_info "Starting bead worker"

    # Run health check at startup
    bead-health-check.sh --workspace=$WORKSPACE --auto-fix

    # Continue with normal worker loop
    ...
}
```

**Benefits:**
- Distributed health checking (every worker checks on startup)
- Immediate recovery (before claiming work)
- No central coordinator needed
- Lightweight (adds ~1-2s to startup)

### 3. Periodic Monitor

**File:** `scripts/bead-health-monitor.sh`

**Usage:**
```bash
# Run continuously (every 5 minutes)
./scripts/bead-health-monitor.sh

# Run once and exit
./scripts/bead-health-monitor.sh --once

# Custom interval (10 minutes)
./scripts/bead-health-monitor.sh --interval=600
```

**Features:**
- Monitors multiple workspaces
- Configurable interval
- Suitable for cron or systemd timer
- Logs all actions

**Cron Setup:**
```bash
# Add to crontab: run every 5 minutes
*/5 * * * * /home/coder/botburrow-agents/scripts/bead-health-monitor.sh --once
```

**Systemd Timer Setup:**
```ini
# /etc/systemd/system/bead-health-monitor.timer
[Unit]
Description=Bead Health Check Timer

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target

# /etc/systemd/system/bead-health-monitor.service
[Unit]
Description=Bead Health Check

[Service]
Type=oneshot
ExecStart=/home/coder/botburrow-agents/scripts/bead-health-monitor.sh --once
```

## Incident Bead Format

When violations are detected, incident beads are created with:

**Type:** `human` (requires human review)
**Priority:** `0` (P0 for unclaimed beads) or `1` (P1 for expired claims/low success rate)

**Example Title:**
```
ALERT: 3 unclaimed in_progress beads detected
```

**Example Description:**
```markdown
## Problem
Detected 3 beads in invalid state:
- status: in_progress
- claimed_by: null (should have worker ID)
- claim_timestamp: null (should have timestamp)

## Auto-Recovery
All beads were automatically reset to 'open' status.

## Affected Beads
- bd-abc: Task title 1
- bd-def: Task title 2
- bd-ghi: Task title 3

## Timestamp
2026-02-16T12:34:56Z

## Workspace
/home/coder/botburrow-agents

## Prevention
Consider:
1. Adding atomic claim acquisition
2. Adding state validation
3. Adding periodic integrity checks
```

## Testing

**File:** `tests/test_bead_health_check.sh`

**Run Tests:**
```bash
cd /home/coder/botburrow-agents
./tests/test_bead_health_check.sh
```

**Test Coverage:**
1. ✅ Detect unclaimed in_progress beads
2. ✅ Auto-fix unclaimed beads
3. ✅ Detect expired claims
4. ✅ Fix multiple unclaimed beads
5. ✅ Healthy system check (no false positives)

**Expected Output:**
```
========================================
  Bead Health Check Integration Tests
========================================

[TEST] Test 1: Detect unclaimed in_progress beads
[PASS] Test 1: Detect unclaimed in_progress beads

[TEST] Test 2: Auto-fix unclaimed in_progress beads
[PASS] Test 2: Auto-fix unclaimed in_progress beads

...

========================================
  Test Results
========================================
Total:  5
Passed: 5
Failed: 0

[PASS] All tests passed! ✅
```

## Manual Verification

### Create Invalid State

```bash
cd /home/coder/botburrow-agents

# Create a bead
bead_id=$(br create --title "Test stuck bead" | grep -oP 'Created issue \K[a-z0-9-]+')

# Manually corrupt state (edit .beads/issues.jsonl)
# Set status=in_progress, claimed_by=null for the bead

# Or use jq:
jq "if .id == \"$bead_id\" then .status = \"in_progress\" | .claimed_by = null | .claim_timestamp = null else . end" \
  .beads/issues.jsonl > /tmp/issues.jsonl.tmp && \
  mv /tmp/issues.jsonl.tmp .beads/issues.jsonl

br sync --flush-only
```

### Run Health Check

```bash
# Verify detection
./scripts/bead-health-check.sh --workspace=$(pwd) --check-only

# Should output:
# [ERROR] Found 1 unclaimed in_progress beads (P0 severity)
#   - bd-xxx: Test stuck bead

# Fix it
./scripts/bead-health-check.sh --workspace=$(pwd) --auto-fix

# Should output:
# [WARN] Auto-fixing unclaimed beads...
# [INFO] Resetting bd-xxx to open status
# [OK] Reset bd-xxx
# [WARN] Creating incident bead: ALERT: 1 unclaimed in_progress beads detected
```

### Verify Recovery

```bash
# Check bead status
br show $bead_id

# Should show: status=open

# Check for incident bead
br list --all | grep "ALERT"

# Should show the incident bead with details
```

## Architecture Decision

We chose **Option A: Worker-based health check** for these reasons:

### Advantages
- **Distributed**: Every worker checks independently
- **Lightweight**: No central coordinator needed
- **Immediate**: Issues detected before claiming work
- **Resilient**: Multiple workers = multiple checks
- **Simple**: Integrates with existing worker startup

### Alternatives Considered

**Option B: Dedicated monitoring service**
- Pros: Centralized monitoring, easier to maintain
- Cons: Single point of failure, requires deployment
- Decision: Rejected (added complexity)

**Option C: Database triggers**
- Pros: Immediate detection at DB level
- Cons: beads uses JSONL files, not SQL database
- Decision: Not applicable

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAIM_EXPIRY_HOURS` | `1` | Hours before claim is considered expired |
| `EXPIRED_CLAIM_THRESHOLD` | `3` | Alert if > N expired claims |
| `LOW_SUCCESS_RATE_THRESHOLD` | `50` | Alert if claim success rate < N% |

### Customization

Edit `scripts/bead-health-check.sh`:

```bash
# Change thresholds
CLAIM_EXPIRY_HOURS=2  # 2 hours instead of 1
EXPIRED_CLAIM_THRESHOLD=5  # Alert at 5 instead of 3
LOW_SUCCESS_RATE_THRESHOLD=40  # Alert at 40% instead of 50%
```

## Metrics & Monitoring

Health checks log structured data suitable for monitoring:

**Log Format:**
```
[2026-02-16 12:34:56] [ERROR] Found 3 unclaimed in_progress beads (P0 severity)
  - bd-abc: Task title 1
  - bd-def: Task title 2
  - bd-ghi: Task title 3
[2026-02-16 12:34:58] [WARN] Auto-fixing unclaimed beads...
[2026-02-16 12:34:59] [OK] Reset bd-abc
```

**Monitoring Integration:**
- Parse logs for `[ERROR]` lines
- Alert on P0 violations
- Track violation frequency
- Monitor auto-fix success rate

## Troubleshooting

### Health Check Not Running

```bash
# Check if script exists and is executable
ls -la /home/coder/botburrow-agents/scripts/bead-health-check.sh

# Make executable if needed
chmod +x /home/coder/botburrow-agents/scripts/bead-health-check.sh

# Test manually
cd /home/coder/botburrow-agents
./scripts/bead-health-check.sh --workspace=$(pwd) --check-only
```

### False Positives

```bash
# Check actual bead state
br list --status in_progress --all --json | jq .

# Verify claim timestamps
br list --status in_progress --all --json | jq '.[] | {id, claimed_by, claim_timestamp}'

# If timestamp format is wrong, update health check script
```

### Incident Beads Not Created

```bash
# Check if br can create human beads
br create --type human --title "Test incident" --priority 1

# Check health check output for errors
./scripts/bead-health-check.sh --workspace=$(pwd) --auto-fix 2>&1 | tee health-check.log

# Look for "Creating incident bead" messages
```

## Future Enhancements

### P1: Engineering Fixes (bd-vn3u)
1. **Atomic claim acquisition**
   - Single transaction for status + claim metadata
   - Prevents race conditions

2. **State validation**
   - Assert invariants on every state transition
   - Fail fast on invalid states

3. **Worker claim validation**
   - Workers validate their claims on startup
   - Release orphaned claims

### P2: Monitoring Improvements
1. **Metrics export**
   - Prometheus metrics for violations
   - Track violation frequency

2. **Alert thresholds**
   - Configurable per workspace
   - Different thresholds for different priorities

3. **Claim expiry tuning**
   - Per-executor timeouts (GLM vs Sonnet)
   - Adaptive expiry based on task complexity

## Related Documentation

- **Root cause analysis:** `analysis/bd-8q53-worker-starvation-root-cause.md`
- **Worker starvation incident:** `BD-8Q53-RESOLVED.md`
- **Bead worker documentation:** `BEAD_WORKERS.md`
- **Engineering fix bead:** bd-vn3u

## See Also

- [Bead Workers](BEAD_WORKERS.md) - Self-scaling worker pool
- [Worker Status](../scripts/worker-status.sh) - Monitor worker health
- [Worker Naming](../scripts/worker-naming.sh) - NATO alphabet naming

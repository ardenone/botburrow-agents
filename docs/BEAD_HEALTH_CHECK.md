# Bead Health Check System

**Status:** Implemented (bd-2wni — retired bead-forge ID, kept for provenance; the current backend is bead-rs)
**Created:** 2026-02-16
**Related:** bd-8q53 (Worker starvation incident — retired bead-forge ID)

## Overview

The bead health check system detects and automatically recovers from stuck beads before worker starvation occurs.

### What It Detects

1. **Unclaimed in_progress beads** (P0 severity)
   - Beads with `status=in_progress` but `assignee=null`
   - Violates state machine invariant
   - Causes worker starvation (workers cannot claim beads already in_progress)

2. **Expired claims** (P1 severity)
   - Beads in_progress with no activity for more than 1 hour
   - Indicates crashed or hung workers
   - Detected and recovered through `bead watchdog`, which is liveness-gated:
     it only releases a stale bead when it can prove the assignee process is
     gone, and holds (`lease_valid_but_stale`) when it cannot
   - Alert threshold: > 3 stale beads per pass

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
./scripts/bead-health-check.sh --workspace=$(pwd) --auto-fix
```

**Features:**
- Detects both violation types (see "What It Detects"; the bead-forge-era
  claim success-rate check was retired with `br stats` in the bead-rs port)
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
- Logs all actions

**The startup check in `bead-worker.sh` only fires when a worker starts** —
a stuck bead created two minutes after a worker boots sits undetected until
the next restart. The periodic monitor closes that window. It is **deployed**
as a systemd **user** timer on codinghome; the units live in this repo so the
deployment is reproducible:

| File | Role |
|------|------|
| `systemd/user/botburrow-bead-health-monitor.service` | oneshot running `scripts/bead-health-monitor.sh --once` from the repo checkout |
| `systemd/user/botburrow-bead-health-monitor.timer` | `OnCalendar=*:0/5` (5-minute cadence), `Persistent=true` catches up a missed fire after downtime |
| `scripts/install-bead-health-monitor.sh` | idempotent installer: copies units to `~/.config/systemd/user/`, daemon-reloads, `enable --now` the timer — re-run it after editing the units in-repo |

Oneshot-per-fire was chosen over a long-running loop service deliberately: a
crashed loop stays crashed silently, while a failed oneshot turns the unit red
in `systemctl --user --failed` and shows in `list-timers`. (A CronJob-like
`kind: CronJob` in-cluster is prohibited in this org; the equivalent in-cluster
shape would be a Deployment with an internal scheduling loop.)

**Workspaces scanned** — `WORKSPACES` in `scripts/bead-health-monitor.sh`,
currently `/home/coding/botburrow-agents`, `/home/coding/botburrow-hub`,
`/home/coding/botburrow`. Missing or `.beads`-less directories are skipped
with a log line, not an error (botburrow-hub is not checked out on codinghome
today; keeping it listed costs nothing). Override without editing the script
via `BOTBURROW_HEALTH_WORKSPACES` (colon- or space-separated).

**Logs** land in the persistent user journal:

```bash
# Follow a pass
journalctl --user -u botburrow-bead-health-monitor.service -f

# When did it last run / when is the next fire?
systemctl --user list-timers botburrow-bead-health-monitor.timer
```

## Incident Bead Format

When violations are detected, incident beads are created with:

**Type:** `human` (requires human review)
**Priority:** `0` (P0 for unclaimed beads) or `1` (P1 for expired claims)

**Example Title:**
```
ALERT: 3 unclaimed in_progress beads detected
```

**Example Description:**
```markdown
## Problem
Detected 3 beads in invalid state:
- status: in_progress
- assignee: null (should have a worker)

## Auto-Recovery
All beads were automatically reset to 'open' status.

## Affected Beads
- bd-abc: Task title 1
- bd-def: Task title 2
- bd-ghi: Task title 3

## Timestamp
2026-02-16T12:34:56Z

## Workspace
/home/coding/botburrow-agents

## Prevention
Consider:
1. Adding atomic claim acquisition
2. Adding state validation
3. Adding periodic integrity checks
```

## Testing

The guard is covered by two hermetic bash suites plus a pytest wrapper that
wires them into the repo's standard `pytest tests/` invocation.

**Files:**
- `tests/test_bead_health_check.sh` — the health-check script (17 tests)
- `tests/test_bead_health_monitor.sh` — the periodic monitor (10 tests)
- `tests/lib/bead_health_test_lib.sh` — shared harness (fixtures, assertions, runner)
- `tests/fixtures/bead_stub.sh` — test double for the `bead` CLI
- `tests/test_bead_health_scripts.py` — pytest wrapper (runs both suites)

**Why a stubbed `bead`:** the scripts shell out to `bead` (bead-rs). Running
the real CLI against a fixture workspace would couple the tests to one
backend's schema, and the corrupt states under test (in_progress with no
assignee) are exactly the states the real CLI refuses to create. The stub
serves bead state from a JSON file the test controls and exits 64 on any
subcommand the scripts don't actually use, so script drift fails loudly.

**Coverage:**
1. ✅ Detect unclaimed in_progress beads (check-only flags, auto-fix resets + P0 incident)
2. ✅ Detect expired claims (above/below the >3 threshold; auto-fix resets + P1 incident)
3. ✅ Healthy workspace exits 0 — including under `--auto-fix` (live claims must survive)
4. ✅ CLI failures fail the check instead of reading as an empty, healthy store
5. ✅ Exit codes 0/1 for both scripts; monitor skip paths (missing dir, no `.beads/`)
6. ✅ Monitor skip paths and their exit codes: an override yielding no
   workspaces is a clean no-op (exit 0, nothing checked); a missing sibling
   check script counts the workspace as failed (exit 1, never a silent skip)
7. ✅ `BOTBURROW_HEALTH_WORKSPACES` replaces the built-in defaults (the
   hard-coded paths are not consulted while it is set), in both the
   colon- and space-separated forms
8. ✅ Direct execution: the harness runs the monitor as a program, not via
   an explicit `bash` — the monitor's `#!/usr/bin/env bash` shebang (and,
   through it, the check script's) is exercised, and the suites preflight
   the exec bit they depend on
9. ✅ Monitor failure aggregation: the loop continues past a failure and the
   exit code is the failed-workspace count (`exit $failed_count`), verified
   for a count > 1

**Mutation-verified** (2026-09-16): each detection's named test was confirmed
to go red by breaking that detection in a scratch copy of the script —
blinding the assignee filter (`select(.assignee == null)` → never matches)
fails the three unclaimed-bead tests; neutralizing the threshold comparison
(`stale_count -le THRESHOLD` → `true`) fails the four expired-claims tests.
This verification is what forced the harness fix below: assertions in
`tests/lib/bead_health_test_lib.sh` used to be non-fatal (only the *last*
assertion in a test body decided its outcome), which let a blinded detection
pass its own named test. A failing assertion now fails the test wherever it
sits. The same run caught a script bug: the `bead list` failure message was
printed inside a command substitution and swallowed, so a CLI failure exited
1 with no reason shown — it now goes to stderr.

The monitor suite's new tests were mutation-verified the same way (2026-09-16,
against the real script, restored after each break): deleting the env-override
block fails the override tests; turning the absent-check-script branch into a
silent `return 0` fails only `test_monitor_fails_when_check_script_is_absent`;
replacing `exit $failed_count` with `exit 1` fails the aggregation test's
exit-2 assertion; stripping the monitor's exec bit trips the harness preflight
with a named reason instead of a run of rc-126 failures.

**The third, retired detection:** the claim success rate check (alert below
50%) survives only in the bead-forge era. Its sole data source was
`br stats --json` (`.total_claims`/`.successful_claims`); bead-rs has no
`stats` subcommand, `bead list` carries no attempt counters, and `bead
query`'s whitelisted fields are issue fields only — so there is nothing to
test and nothing to detect on the current CLI surface. If the metric is
wanted again it must be re-derived (e.g. from `bead resolve` attempt
outcomes) and land with its own named test.

**Run them:**
```bash
cd /home/coding/botburrow-agents
bash tests/test_bead_health_check.sh
bash tests/test_bead_health_monitor.sh
# or via the repo's standard pytest invocation:
.venv/bin/python -m pytest tests/test_bead_health_scripts.py
```

**CI:** both suites gate the image build — the `botburrow-agents-build`
WorkflowTemplate (declarative-config, `k8s/iad-ci/argo-workflows/`) runs them
in a `run-tests` step before `docker-build`, so a regression in the
starvation guard fails the build instead of the fleet.

## Manual Verification

> **Note (2026-09-16):** the live-corruption drill below is a recipe from
> the retired bead-forge era. This workspace is now on bead-rs: the live
> store is SQLite (`.beads/beads.db`), not `.beads/issues.jsonl`, and hand-
> editing a bead store — here or in any shape — is how the SEAM store got
> corrupted on 2026-08-14. Do **not** recreate the invalid state by hand on a
> live workspace. The hermetic suites above are the supported way to exercise
> the guard: they serve bead state from a fixture via a stubbed CLI, so all
> three violation types can be driven deterministically and safely.
>
> The scripts themselves target the bead-rs CLI (`bead`); that interface is
> pinned by `tests/fixtures/bead_stub.sh` (unused subcommands exit 64), so any
> drift between scripts and tests fails loudly.

### Create Invalid State (bead-forge era — historical, do not run today)

```bash
cd /home/coding/botburrow-agents

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

### Script Variables

Set at the top of `scripts/bead-health-check.sh` (plain variables, not
environment overrides — edit the script to change them):

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAIM_EXPIRY_HOURS` | `1` | Hours before a claim is considered expired (the `bead watchdog` threshold) |
| `EXPIRED_CLAIM_THRESHOLD` | `3` | Alert if > N expired claims |

### Customization

Edit `scripts/bead-health-check.sh`:

```bash
# Change thresholds
CLAIM_EXPIRY_HOURS=2  # 2 hours instead of 1
EXPIRED_CLAIM_THRESHOLD=5  # Alert at 5 instead of 3
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
ls -la /home/coding/botburrow-agents/scripts/bead-health-check.sh

# Make executable if needed
chmod +x /home/coding/botburrow-agents/scripts/bead-health-check.sh

# Test manually
cd /home/coding/botburrow-agents
./scripts/bead-health-check.sh --workspace=$(pwd) --check-only
```

### False Positives

```bash
# Check actual bead state
bead list --status in_progress --json | jq .

# Verify assignees
bead list --status in_progress --json | jq '{id, assignee}'

# If the field names drift, update health check script
```

### Incident Beads Not Created

```bash
# Check if bead can create human beads
bead create --issue-type human --title "Test incident" --priority 1

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

- **Root cause analysis:** `../analysis/bd-8q53-worker-starvation-root-cause.md`
- **Worker starvation incident:** `../BD-8Q53-RESOLVED.md`
- **Bead worker documentation:** `../BEAD_WORKERS.md`
- **Engineering fix bead:** bd-vn3u (retired bead-forge ID)

## See Also

- [Bead Workers](../BEAD_WORKERS.md) - Self-scaling worker pool
- [Worker Status](../scripts/worker-status.sh) - Monitor worker health
- [Worker Naming](../scripts/worker-naming.sh) - NATO alphabet naming

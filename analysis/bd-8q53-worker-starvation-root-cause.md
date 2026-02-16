# Worker Starvation Root Cause Analysis - bd-8q53

**Date:** 2026-02-16T05:52:42Z
**Worker:** claude-code-glm-47-bravo
**Workspace:** /home/coder/botburrow-agents

## Executive Summary

Worker starvation is caused by **database corruption**: 13 beads are stuck in "in_progress" status with no active worker claims. Workers cannot claim beads already marked "in_progress", creating a deadlock where work exists but cannot be claimed.

## Critical Finding: Data Integrity Violation

### The Problem

All 13 "in_progress" beads have invalid state:
```json
{
  "status": "in_progress",
  "claimed_by": null,          // ❌ SHOULD have worker ID
  "claim_timestamp": null      // ❌ SHOULD have timestamp
}
```

**This violates the state machine invariant**: A bead in "in_progress" status MUST have:
1. `claimed_by` set to the worker ID
2. `claim_timestamp` set to when claim was acquired

### Affected Beads

| Bead ID | Title | Updated At | Type |
|---------|-------|------------|------|
| bd-8q53 | ALERT: Worker claude-code-glm-47-bravo has no work available | 2026-02-16T05:49:24Z | human |
| bd-1qs | CLUSTER-ADMIN: Apply RBAC manifests for devpod-observer | 2026-02-16T04:51:40Z | human |
| bd-12r | CLUSTER-ADMIN: Grant devpod-observer RBAC access | 2026-02-15T22:47:08Z | task |
| bd-2y0 | CLUSTER-ADMIN: Fix Tailscale kubectl-proxy connectivity | 2026-02-15T20:43:30Z | human |
| bd-3h3 | HUMAN: Update Docker Hub credentials (PAT required) | 2026-02-16T04:52:05Z | human |
| bd-2jm | CLUSTER-ADMIN: Apply Hub API authentication fix | 2026-02-15T20:40:02Z | human |
| bd-3f3 | CLUSTER-ADMIN: Install ArgoCD in apexalgo-iad | 2026-02-15T[...] | human |
| bd-3qv | Test agent runner pool scaling | [...] | task |
| bd-31j | Configure Docker Hub credentials for CI/CD push | [...] | task |
| bd-q21 | HUMAN: Fix coordinator Hub API authentication | [...] | human |
| bd-212 | Investigate ronaldraygun/botburrow-agents image version | [...] | task |
| bd-1j7 | Full Kubernetes coordinator leader election verification | [...] | task |
| bd-3e3 | Create ArgoCD GitOps deployment for botburrow-agents | [...] | task |

**Total:** 13 beads (6 human, 7 task)

## Root Cause Hypotheses

### Hypothesis 1: Race Condition in Claim Release
**Scenario:** Worker crashes or exits between:
1. Setting `status = "in_progress"`
2. Setting `claimed_by` and `claim_timestamp`

**Likelihood:** Medium - requires very specific timing

### Hypothesis 2: Transaction Rollback
**Scenario:** Database transaction sets status but rolls back claim metadata
**Likelihood:** High - if claim acquisition isn't atomic

### Hypothesis 3: Manual Status Change
**Scenario:** Beads manually updated to "in_progress" without claim metadata
**Likelihood:** Low - requires manual database manipulation

### Hypothesis 4: Claim Expiry Bug
**Scenario:** Claim expiry logic removes claim metadata but doesn't reset status
**Likelihood:** High - most likely cause

**Evidence:**
- Beads have been "in_progress" for 1-10 hours
- No active worker holds claims
- All claim metadata is null, not stale

## Impact Analysis

### Immediate Impact
- **Worker Starvation:** All workers cannot claim work (11% claim success rate)
- **Work Backlog:** 13 P0-P2 beads blocked (including critical CLUSTER-ADMIN tasks)
- **System Deadlock:** No progress possible until manual intervention

### Affected Workers
- claude-code-glm-47-bravo (this alert)
- Potentially all workers in the system (claim success rate: 11%)

### Business Impact
- Critical production tasks blocked (RBAC, ArgoCD, Hub API auth)
- Human-response beads cannot be processed
- Deployment pipeline stalled

## Recovery Strategy

### Option 1: Reset All Stuck Beads (RECOMMENDED)
**Action:** Reset status to "open" for all unclaimed "in_progress" beads

**Pros:**
- Immediate fix
- Safe (no data loss)
- Allows workers to reclaim work

**Cons:**
- May reset beads that workers are actually working on (but claim metadata suggests none are)

**Implementation:**
```bash
# Find all unclaimed in_progress beads
br list --status in_progress --all --json | \
  jq -r '.[] | select(.claimed_by == null) | .id' | \
  while read bead_id; do
    br update "$bead_id" --status open
    echo "Reset $bead_id to open"
  done
```

### Option 2: Force Maintenance Cleanup
**Action:** Trigger maintenance cleanup with aggressive thresholds

**Pros:**
- Uses built-in recovery mechanism
- Preserves claim history

**Cons:**
- May not fix if cleanup already ran
- Doesn't address root cause

### Option 3: Manual Database Repair
**Action:** Directly edit `.beads/issues.jsonl` to fix state

**Pros:**
- Precise control
- Can preserve exact state

**Cons:**
- Error-prone
- Requires understanding JSONL format
- High risk

## Recommended Actions

### Immediate (P0)
1. ✅ Document root cause (this analysis)
2. 🔧 Reset all 13 stuck beads to "open" status
3. 📊 Monitor claim success rate recovery
4. 🧪 Verify workers can claim work again

### Short-term (P1)
1. 🐛 Add data integrity check to worker startup
2. 🔍 Add logging to claim acquisition/release paths
3. 📝 Create monitoring for stuck beads (status=in_progress, claimed_by=null)
4. 🧪 Add unit tests for claim state machine transitions

### Long-term (P2)
1. 🏗️ Make claim acquisition atomic (single transaction)
2. 🧹 Add periodic integrity validation job
3. 📊 Add metrics for claim state violations
4. 🔒 Add database constraints to prevent invalid states

## Prevention Measures

### Code-Level Safeguards
1. **Atomic Claim Acquisition:** Single transaction for status + claim metadata
2. **State Machine Validation:** Assert invariants on every state transition
3. **Defensive Cleanup:** Worker startup validates its own claims

### Operational Safeguards
1. **Health Checks:** Monitor for beads with invalid state combinations
2. **Auto-Recovery:** Periodic job to reset orphaned in_progress beads
3. **Alerting:** Alert when claim success rate drops below 50%

## Verification

After recovery, verify:
```bash
# No unclaimed in_progress beads
br list --status in_progress --all --json | \
  jq 'map(select(.claimed_by == null)) | length'
# Expected: 0

# Workers can claim work
br stats
# Expected: claim_success_rate > 80%

# Work is progressing
br list --status in_progress --all | wc -l
# Expected: > 0 (workers actively claiming)
```

## Related Issues

- **bd-2b9:** Duplicate issue detection (blocked state)
- **Worker claim success rate:** 11% → needs investigation beyond this issue

## Next Steps

1. Create recovery bead to execute Option 1 (reset stuck beads)
2. Create monitoring bead for future detection
3. Create engineering bead for atomic claim fixes
4. Update worker documentation with data integrity checks

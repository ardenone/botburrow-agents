# Root Cause Analysis: Atomic Claim Acquisition - bd-vn3u

**Date:** 2026-02-16
**Worker:** claude-code-glm-47-golf
**Workspace:** /home/coder/botburrow-agents
**Related:** bd-8q53 (worker starvation), bd-3ps3 (recovery)

## Executive Summary

Beads get stuck in `in_progress` status without claim metadata due to **incomplete implementation of claim tracking in beads_rust**. The database schema and CHECK constraints exist, but the SQL queries don't fetch or populate the `claimed_by` and `claim_timestamp` fields.

## Root Cause: Missing Fields in SQL Queries

### What Works ✅

1. **Database Schema** (`src/storage/schema.rs:26-27`):
   ```sql
   CREATE TABLE IF NOT EXISTS issues (
       ...
       claimed_by TEXT,
       claim_timestamp DATETIME,
       ...
   ```

2. **Database Constraint** (`src/storage/schema.rs:58-62`):
   ```sql
   CHECK (
       (status = 'in_progress' AND claimed_by IS NOT NULL AND claim_timestamp IS NOT NULL) OR
       (status != 'in_progress' AND claimed_by IS NULL AND claim_timestamp IS NULL)
   )
   ```

3. **Rust Model** (`src/model/mod.rs:418-422`):
   ```rust
   /// Worker that claimed this issue (for atomic claim tracking).
   #[serde(default, skip_serializing_if = "Option::is_none")]
   pub claimed_by: Option<String>,

   /// Timestamp when issue was claimed by a worker.
   #[serde(default, skip_serializing_if = "Option::is_none")]
   pub claim_timestamp: Option<DateTime<Utc>>,
   ```

4. **IssueUpdate struct** (`src/storage/sqlite.rs:3172-3173`):
   ```rust
   pub claimed_by: Option<Option<String>>,
   pub claim_timestamp: Option<Option<DateTime<Utc>>>,
   ```

### What's Broken ❌

1. **SQL SELECT queries don't include claim fields** (`src/storage/sqlite.rs:669-676`):
   ```sql
   SELECT id, content_hash, title, description, ..., is_template
   FROM issues WHERE id = ?
   -- Missing: claimed_by, claim_timestamp
   ```

2. **`issue_from_row` doesn't parse claim fields** (`src/storage/sqlite.rs:3048-3104`):
   ```rust
   fn issue_from_row(&self, row: &rusqlite::Row) -> rusqlite::Result<Issue> {
       Ok(Issue {
           id: row.get(0)?,
           // ... 35 fields ...
           is_template: row.get::<_, Option<i32>>(35)?.unwrap_or(0) != 0,
           // Missing: claimed_by, claim_timestamp
           labels: vec![],
           dependencies: vec![],
           comments: vec![],
       })
   }
   ```

3. **UPDATE queries don't set claim fields** (`src/storage/sqlite.rs:388+`):
   The `update_issue` method can accept `claimed_by` and `claim_timestamp` in `IssueUpdate`, but the actual UPDATE SQL likely doesn't include them.

## Impact

### Data Integrity Violation

The CHECK constraint prevents `in_progress` beads without claims:
```sql
-- This INSERT/UPDATE will FAIL:
UPDATE issues SET status = 'in_progress' WHERE id = 'bd-123';
-- ERROR: CHECK constraint failed

-- This would succeed (if the fields were included in UPDATE):
UPDATE issues
SET status = 'in_progress',
    claimed_by = 'worker-alpha',
    claim_timestamp = CURRENT_TIMESTAMP
WHERE id = 'bd-123';
```

### Current Behavior

When workers try to claim beads:
1. Worker sets status to `in_progress`
2. **SQL fails due to CHECK constraint** (claim fields are NULL)
3. Bead remains in `open` status
4. OR if constraint is somehow bypassed, bead has invalid state

### Observed Symptoms (bd-8q53)

- 13 beads stuck in `in_progress` with NULL claim metadata
- Worker starvation (11% claim success rate)
- State machine invariant violated

**How did beads get into invalid state?**
- Likely: CHECK constraint was added AFTER beads were created
- OR: Manual database manipulation
- OR: Race condition in transaction rollback

## Required Fix

### 1. Update SQL SELECT Queries

**File:** `src/storage/sqlite.rs`

All SELECT queries must include `claimed_by` and `claim_timestamp`:

```rust
// Before (line 669):
let sql = r"
    SELECT id, content_hash, title, description, design, acceptance_criteria, notes,
           status, priority, issue_type, assignee, owner, estimated_minutes,
           created_at, created_by, updated_at, closed_at, close_reason, closed_by_session,
           due_at, defer_until, external_ref, source_system, source_repo,
           deleted_at, deleted_by, delete_reason, original_type,
           compaction_level, compacted_at, compacted_at_commit, original_size,
           sender, ephemeral, pinned, is_template
    FROM issues WHERE id = ?
";

// After:
let sql = r"
    SELECT id, content_hash, title, description, design, acceptance_criteria, notes,
           status, priority, issue_type, assignee, owner, claimed_by, claim_timestamp, estimated_minutes,
           created_at, created_by, updated_at, closed_at, close_reason, closed_by_session,
           due_at, defer_until, external_ref, source_system, source_repo,
           deleted_at, deleted_by, delete_reason, original_type,
           compaction_level, compacted_at, compacted_at_commit, original_size,
           sender, ephemeral, pinned, is_template
    FROM issues WHERE id = ?
";
```

**Affected methods:**
- `get_issue` (line 669)
- `get_issues_by_ids` (line 706)
- `list_issues` (line 738)
- `get_ready_issues` (line ~1050)
- Any other method that SELECTs from issues table

### 2. Update `issue_from_row` Parsing

**File:** `src/storage/sqlite.rs:3048-3104`

Add parsing for claim fields (adjust column indices):

```rust
fn issue_from_row(&self, row: &rusqlite::Row) -> rusqlite::Result<Issue> {
    Ok(Issue {
        id: row.get(0)?,
        content_hash: row.get::<_, Option<String>>(1)?,
        title: row.get(2)?,
        description: Self::empty_to_none(row.get::<_, Option<String>>(3)?),
        design: Self::empty_to_none(row.get::<_, Option<String>>(4)?),
        acceptance_criteria: Self::empty_to_none(row.get::<_, Option<String>>(5)?),
        notes: Self::empty_to_none(row.get::<_, Option<String>>(6)?),
        status: parse_status(row.get::<_, Option<String>>(7)?.as_deref()),
        priority: Priority(row.get::<_, Option<i32>>(8)?.unwrap_or(2)),
        issue_type: parse_issue_type(row.get::<_, Option<String>>(9)?.as_deref()),
        assignee: Self::empty_to_none(row.get::<_, Option<String>>(10)?),
        owner: Self::empty_to_none(row.get::<_, Option<String>>(11)?),
        // **NEW FIELDS:**
        claimed_by: Self::empty_to_none(row.get::<_, Option<String>>(12)?),
        claim_timestamp: row
            .get::<_, Option<String>>(13)?
            .as_deref()
            .map(parse_datetime),
        estimated_minutes: row.get::<_, Option<i32>>(14)?,  // Shifted from 12
        created_at: parse_datetime(&row.get::<_, String>(15)?),  // Shifted from 13
        // ... rest of fields shifted by +2 ...
        is_template: row.get::<_, Option<i32>>(37)?.unwrap_or(0) != 0,  // Was 35, now 37
        labels: vec![],
        dependencies: vec![],
        comments: vec![],
    })
}
```

### 3. Implement Atomic Claim Acquisition

**File:** `src/storage/sqlite.rs`

Add new method for atomic claim:

```rust
/// Atomically claim an issue for a worker.
///
/// This method uses a conditional UPDATE to ensure:
/// 1. Issue status is 'open'
/// 2. Issue is not already claimed
/// 3. Status, claimed_by, and claim_timestamp are set atomically
///
/// # Returns
/// - Ok(Some(issue)) if claim succeeded
/// - Ok(None) if issue was already claimed or doesn't exist
/// - Err if database operation failed
pub fn claim_issue(&mut self, id: &str, worker_id: &str) -> Result<Option<Issue>> {
    let now = Utc::now();

    self.mutate("claim_issue", worker_id, |tx, ctx| {
        // Atomic conditional UPDATE
        let rows = tx.execute(
            "UPDATE issues
             SET status = 'in_progress',
                 claimed_by = ?,
                 claim_timestamp = ?,
                 updated_at = ?
             WHERE id = ?
               AND status = 'open'
               AND claimed_by IS NULL",
            rusqlite::params![
                worker_id,
                now.to_rfc3339(),
                now.to_rfc3339(),
                id
            ],
        )?;

        if rows == 0 {
            // Claim failed - issue doesn't exist, wrong status, or already claimed
            return Ok(None);
        }

        ctx.record_event(
            EventType::StatusChanged,
            id,
            Some(format!("Claimed by {worker_id}")),
        );
        ctx.mark_dirty(id);
        ctx.invalidate_cache();

        Ok(Some(()))
    })?;

    // Return updated issue if claim succeeded
    self.get_issue(id)
}

/// Release a claim on an issue.
///
/// # Returns
/// - Ok(true) if release succeeded
/// - Ok(false) if issue wasn't claimed by this worker
pub fn release_claim(&mut self, id: &str, worker_id: &str) -> Result<bool> {
    self.mutate("release_claim", worker_id, |tx, ctx| {
        let rows = tx.execute(
            "UPDATE issues
             SET status = 'open',
                 claimed_by = NULL,
                 claim_timestamp = NULL,
                 updated_at = ?
             WHERE id = ?
               AND claimed_by = ?",
            rusqlite::params![
                Utc::now().to_rfc3339(),
                id,
                worker_id
            ],
        )?;

        if rows > 0 {
            ctx.record_event(
                EventType::StatusChanged,
                id,
                Some(format!("Released claim by {worker_id}")),
            );
            ctx.mark_dirty(id);
            ctx.invalidate_cache();
        }

        Ok(rows > 0)
    })
}
```

### 4. Add State Validation

**File:** `src/validation/mod.rs` (or create new validation module)

```rust
/// Validate issue state invariants.
pub fn validate_issue_state(issue: &Issue) -> Result<()> {
    // Claim invariant: in_progress issues MUST have claim metadata
    if issue.status == Status::InProgress {
        if issue.claimed_by.is_none() || issue.claim_timestamp.is_none() {
            return Err(BeadsError::InvalidState {
                message: format!(
                    "Issue {} is in_progress but missing claim metadata (claimed_by: {:?}, claim_timestamp: {:?})",
                    issue.id, issue.claimed_by, issue.claim_timestamp
                ),
            });
        }
    } else if issue.claimed_by.is_some() || issue.claim_timestamp.is_some() {
        return Err(BeadsError::InvalidState {
            message: format!(
                "Issue {} has claim metadata but status is {} (not in_progress)",
                issue.id, issue.status
            ),
        });
    }

    // Closed invariant: closed issues MUST have closed_at timestamp
    if issue.status == Status::Closed && issue.closed_at.is_none() {
        return Err(BeadsError::InvalidState {
            message: format!("Issue {} is closed but missing closed_at timestamp", issue.id),
        });
    }

    Ok(())
}
```

Call `validate_issue_state` in:
- `get_issue` (after parsing)
- `update_issue` (after update)
- `create_issue` (after creation)

### 5. Update Existing `update_issue` Method

Ensure the `update_issue` method includes `claimed_by` and `claim_timestamp` in its UPDATE SQL.

## Testing Strategy

### Unit Tests

```rust
#[test]
fn test_atomic_claim_acquisition() {
    let mut storage = SqliteStorage::new_in_memory().unwrap();

    // Create open issue
    let issue = storage.create_issue(...).unwrap();

    // Worker 1 claims successfully
    let claimed = storage.claim_issue(&issue.id, "worker-1").unwrap();
    assert!(claimed.is_some());
    assert_eq!(claimed.unwrap().claimed_by, Some("worker-1".to_string()));

    // Worker 2 fails to claim (already claimed)
    let failed = storage.claim_issue(&issue.id, "worker-2").unwrap();
    assert!(failed.is_none());
}

#[test]
fn test_claim_validation() {
    let issue = Issue {
        status: Status::InProgress,
        claimed_by: None,  // Invalid!
        claim_timestamp: None,  // Invalid!
        ..Default::default()
    };

    let result = validate_issue_state(&issue);
    assert!(result.is_err());
}
```

### Integration Tests

```rust
#[test]
fn test_concurrent_claims() {
    // Simulate race condition: multiple workers claim same issue
    // Only one should succeed
}

#[test]
fn test_claim_constraint_enforcement() {
    // Direct SQL: Try to create in_progress without claims
    // Should fail CHECK constraint
}
```

## Migration Path

### For Existing Deployments

```sql
-- Fix existing in_progress issues with NULL claims
UPDATE issues
SET status = 'open',
    claimed_by = NULL,
    claim_timestamp = NULL
WHERE status = 'in_progress'
  AND (claimed_by IS NULL OR claim_timestamp IS NULL);
```

This is what bd-3ps3 recovery bead did.

## Verification

After fix is deployed:

```bash
# No unclaimed in_progress beads
br list --status in_progress --all --json | \
  jq 'map(select(.claimed_by == null or .claim_timestamp == null)) | length'
# Expected: 0

# Workers can claim work
br ready --json | jq 'length'
# Expected: > 0

# Claim success rate improves
br stats
# Expected: claim_success_rate > 80%
```

## Related Issues

- **bd-8q53:** Worker starvation alert (this bead is the fix)
- **bd-3ps3:** Recovery bead that reset stuck beads
- **analysis/bd-8q53-worker-starvation-root-cause.md:** Initial investigation

## Implementation Location

**Repository:** https://github.com/Dicklesworthstone/beads_rust
**Version:** 0.1.13
**Checkout:** `/home/coder/.cargo/git/checkouts/beads_rust-18649610c6bb6d7c/4a8353f/`

**Note:** This is an external dependency. Fixes must be:
1. Submitted as PR to beads_rust repository
2. New version released (0.1.14+)
3. botburrow-agents updated to use new version

# CRITICAL: Workspace Metadata Persistence Issue

**⚠️ WARNING: EVERY `br` COMMAND THAT TRIGGERS AUTO-FLUSH WILL LOSE WORKSPACE METADATA**

---

## The Problem

The `beads_rust` system has a **fundamental architecture issue**:

1. **Workspace is JSONL-only** - not stored in database
2. **All `br` commands trigger auto-flush** - including `br close`, `br update`, `br create`
3. **Auto-flush exports database → JSONL** - overwriting all JSONL-only fields
4. **Workspace metadata is lost** after ANY `br` command

This is not a one-time issue. It's an **ongoing problem** that requires a permanent solution.

---

## Evidence

### Sequence of Events (2026-02-16)

1. **06:54 UTC** - Added workspace metadata to all 10 open beads
2. **06:55 UTC** - Committed fix with detailed documentation
3. **06:58 UTC** - Ran `br close bd-8q53`
4. **06:58 UTC** - Auto-flush triggered by close command
5. **06:58 UTC** - All workspace metadata lost AGAIN

### Log Evidence

```
2026-02-16T06:58:42.042556Z  INFO beads_rust::sync: Auto-flush complete exported=172
```

Every `br` command that modifies beads triggers this auto-flush.

---

## Root Cause

### Database Schema

The `issues` table does NOT have a `workspace` column:

```sql
CREATE TABLE issues (
  id TEXT PRIMARY KEY,
  title TEXT,
  status TEXT,
  priority INTEGER,
  metadata TEXT,  -- JSON column, but not exported to JSONL top-level
  ...
  -- NO workspace column
)
```

### Export Logic

The `beads_rust` export logic:
1. Reads all fields from database
2. Writes to JSONL
3. Does NOT preserve JSONL-only fields like `workspace`
4. Overwrites entire JSONL file

### Why Metadata Column Doesn't Help

- Database has `metadata` JSON column
- Storing `workspace` in metadata works in database
- But export writes metadata AS `metadata` field in JSONL
- Workers expect `workspace` at ROOT level, not in `metadata` sub-object

---

## Impact

### Affected Operations

**ANY command that modifies beads triggers auto-flush:**

- ✅ `br list` - Safe (read-only)
- ✅ `br show` - Safe (read-only)
- ✅ `br stats` - Safe (read-only)
- ❌ `br create` - Triggers auto-flush, loses workspace
- ❌ `br update` - Triggers auto-flush, loses workspace
- ❌ `br close` - Triggers auto-flush, loses workspace
- ❌ `br reopen` - Triggers auto-flush, loses workspace
- ❌ `br sync --flush-only` - Explicitly flushes, loses workspace

### Consequence

**Workers cannot find beads** because workspace filtering fails when workspace is missing.

---

## Temporary Workaround

### After EVERY `br` Command

After ANY `br` command that modifies beads (create, update, close, etc.):

```bash
# Re-add workspace metadata
python3 scripts/add_workspace_metadata.py

# Commit if needed
git add .beads/issues.jsonl
git commit -m "chore: restore workspace metadata after br command"
```

### Automated Hook (Recommended)

Create a git hook to automatically re-add workspace after commits:

```bash
# .git/hooks/post-commit
#!/bin/bash
cd /home/coder/botburrow-agents
python3 scripts/add_workspace_metadata.py >/dev/null 2>&1
```

---

## Permanent Solution Required

This issue **CANNOT be fixed in userspace**. It requires changes to `beads_rust`.

### Option 1: Add Workspace to Database Schema

**Add `workspace` column to `issues` table:**

```sql
ALTER TABLE issues ADD COLUMN workspace TEXT;

-- Populate from config or current directory
UPDATE issues SET workspace = '/home/coder/botburrow-agents' WHERE workspace IS NULL;
```

**Export logic must include workspace:**

```rust
// In export logic
let issue = Issue {
    id: row.id,
    title: row.title,
    workspace: row.workspace, // Include workspace in export
    ...
};
```

### Option 2: Preserve JSONL-Only Fields During Export

**Before overwriting JSONL:**

1. Read existing JSONL file
2. Extract JSONL-only fields (workspace, etc.)
3. Export database to JSONL
4. Merge JSONL-only fields back into exported data
5. Write merged result

**Pseudocode:**

```rust
// Read existing JSONL, preserve workspace
let existing_workspaces: HashMap<String, String> = read_existing_workspaces();

// Export from database
let mut exported_issues = export_from_database();

// Merge workspace back
for issue in &mut exported_issues {
    if let Some(workspace) = existing_workspaces.get(&issue.id) {
        issue.workspace = Some(workspace.clone());
    }
}

// Write to JSONL
write_jsonl(exported_issues);
```

### Option 3: Use Config-Based Workspace

**Read workspace from `.beads/config.yaml`:**

```yaml
# .beads/config.yaml
workspace: /home/coder/botburrow-agents
```

**Export logic applies workspace from config:**

```rust
// Read config
let config = read_config()?;

// Apply workspace to all exported issues
for issue in &mut exported_issues {
    if issue.workspace.is_none() {
        issue.workspace = Some(config.workspace.clone());
    }
}
```

---

## Recommended Approach

**Combination of Option 1 + Option 3:**

1. **Add `workspace` column to database**
   - Permanent storage for workspace metadata
   - Fast queries, proper indexing

2. **Auto-populate workspace on bead creation**
   - From current directory (find nearest `.beads/`)
   - From `.beads/config.yaml` as fallback
   - Never create beads without workspace

3. **Validate workspace on export**
   - Warn if workspace is missing
   - Use config.yaml as fallback

4. **Migrate existing beads**
   - One-time migration script
   - Populate workspace column from JSONL or config

---

## Interim Solution

**Until `beads_rust` is fixed, follow this workflow:**

### 1. After ANY bead modification command:

```bash
# Always run after br create, br update, br close, etc.
python3 scripts/add_workspace_metadata.py
```

### 2. Commit workspace restoration:

```bash
git add .beads/issues.jsonl
git commit -m "chore: restore workspace metadata"
git push origin main
```

### 3. Document in commit messages:

```bash
git commit -m "feat(bd-xxx): implement feature

... feature details ...

NOTE: Workspace metadata restored after br close command

Co-Authored-By: Claude Worker <noreply@anthropic.com>"
```

---

## Monitoring

### Check for Missing Workspace

```bash
python3 << 'EOF'
import json

with open('.beads/issues.jsonl') as f:
    open_without_workspace = 0
    for line in f:
        if line.strip():
            bead = json.loads(line.strip())
            if bead.get('status') == 'open' and not bead.get('workspace'):
                open_without_workspace += 1
                print(f"Missing workspace: {bead['id']}")

    if open_without_workspace > 0:
        print(f"\n⚠️ WARNING: {open_without_workspace} open beads lack workspace metadata")
        print("Run: python3 scripts/add_workspace_metadata.py")
    else:
        print("✅ All open beads have workspace metadata")
EOF
```

### Add to CI/CD Pipeline

```yaml
# .github/workflows/check-workspace.yml
name: Check Workspace Metadata
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check workspace metadata
        run: |
          cd /path/to/workspace
          python3 scripts/add_workspace_metadata.py
          git diff --exit-code .beads/issues.jsonl || \
            (echo "ERROR: Workspace metadata missing!" && exit 1)
```

---

## Related Issues

1. **bd-8q53** - Worker starvation due to missing workspace (resolved 3 times!)
2. **bd-288u** - Implement automatic claim expiration (related to workspace filtering)

---

## Contact

If implementing a permanent fix in `beads_rust`:
- Repository: (beads_rust repo URL)
- Issue tracker: (issue tracker URL)
- Reference: `BD-8Q53-FINAL-RESOLUTION.md` for full context

---

## Summary

- ⚠️ **CRITICAL:** Every `br` command loses workspace metadata
- 🔧 **WORKAROUND:** Run `scripts/add_workspace_metadata.py` after every br command
- 🛠️ **PERMANENT FIX:** Requires changes to `beads_rust` database schema and export logic
- 📊 **IMPACT:** Workers cannot find beads without workspace metadata

**This is not a one-time fix. It requires ongoing maintenance until beads_rust is updated.**

---

**Last Updated:** 2026-02-16
**Status:** Ongoing Issue
**Severity:** Critical

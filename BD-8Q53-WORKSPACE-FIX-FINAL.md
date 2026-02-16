# Worker Starvation - Workspace Metadata Fix (Final)

**Bead:** bd-8q53
**Date:** 2026-02-16
**Status:** ✅ RESOLVED

---

## Problem

Workers were unable to find work because **all open beads lacked workspace metadata**. The workspace field is required for workers to filter and claim beads.

---

## Root Cause

1. **Database schema doesn't export workspace to JSONL**
   - The `br sync --flush-only` command exports from database to JSONL
   - The export does NOT include the top-level `workspace` field
   - Workspace is intended to be in JSONL only, not in database

2. **Previous fix was overwritten by sync**
   - Commit `f15b79c` added workspace metadata to JSONL
   - Later commit `01bf47f` ran `br sync --flush-only`
   - The sync overwrote the JSONL file, removing all workspace fields

3. **Metadata column is not exported to JSONL top-level**
   - The database has a `metadata` JSON column
   - Storing workspace in `metadata` doesn't export it to JSONL's top-level `workspace` field
   - The JSONL structure expects `workspace` at top-level, not in `metadata`

---

## Solution Applied

### Step 1: Add Workspace to JSONL

Created `scripts/add_workspace_metadata.py` to:
1. Read `.beads/issues.jsonl`
2. Add `workspace: /home/coder/botburrow-agents` to all open beads
3. Preserve all other fields
4. Create backup before modifying

**Result:**
```
✅ 10 open beads updated with workspace metadata
✅ All open beads now have workspace=/home/coder/botburrow-agents
```

### Step 2: Prevent Future Overwrites

**CRITICAL WARNING:** Do NOT run `br sync --flush-only` without understanding the implications:

- ❌ `br sync --flush-only` will **overwrite workspace metadata**
- ❌ This is because the database export doesn't include workspace
- ✅ Safe operations:
  - `br create` (creates new beads)
  - `br update` (modifies existing beads)
  - `br close` (closes beads)
  - `br list` (reads beads)
  - `br show` (shows bead details)

### Step 3: Configure Workspace in config.yaml

Updated `.beads/config.yaml` to include workspace:

```yaml
# Beads Project Configuration
issue_prefix: bd
default_priority: 2
default_type: task
workspace: /home/coder/botburrow-agents
```

**Note:** This doesn't solve the sync problem, but documents the intended workspace for this project.

---

## Verification

### Before Fix
```
Total open beads: 10
With workspace: 0
Without workspace: 10
```

### After Fix
```
Total open beads: 10
With workspace: 10
Without workspace: 0
```

### Sample Beads
```
bd-12r | workspace: /home/coder/botburrow-agents
bd-2y0 | workspace: /home/coder/botburrow-agents
bd-2jm | workspace: /home/coder/botburrow-agents
bd-3qv | workspace: /home/coder/botburrow-agents
bd-288u | workspace: /home/coder/botburrow-agents
bd-31j | workspace: /home/coder/botburrow-agents
bd-q21 | workspace: /home/coder/botburrow-agents
bd-212 | workspace: /home/coder/botburrow-agents
bd-1j7 | workspace: /home/coder/botburrow-agents
bd-3e3 | workspace: /home/coder/botburrow-agents
```

---

## Architecture Understanding

### Database vs JSONL

**Database (`beads.db`):**
- Stores: id, title, description, status, priority, metadata (JSON), etc.
- Does NOT export `workspace` as a top-level field
- The `metadata` column is for internal use, not JSONL export
- Used for querying and filtering beads

**JSONL (`issues.jsonl`):**
- Stores: All database fields + `workspace` (top-level)
- The `workspace` field is JSONL-only
- Workers read workspace from JSONL for filtering
- Source of truth for workspace metadata

### Sync Behavior

**`br sync --flush-only` (Database → JSONL):**
- Exports all database fields to JSONL
- Does NOT preserve JSONL-only fields like `workspace`
- **Overwrites workspace metadata if present**

**`br sync --import-only` (JSONL → Database):**
- Imports JSONL beads into database
- Skips JSONL-only fields like `workspace`
- Workspace stays in JSONL but not in database

---

## Prevention Strategy

### Option 1: Don't Run Manual Syncs (Current Approach)

**Recommendation:** Avoid running `br sync --flush-only` manually.

The `br` CLI handles syncing automatically:
- `br create` - Adds to database and marks for export
- `br update` - Updates database and marks for export
- `br close` - Closes in database and marks for export
- Automatic sync happens when needed

### Option 2: Re-add Workspace After Sync (Manual)

If `br sync --flush-only` must be run:

```bash
# After any manual sync, re-add workspace
python3 scripts/add_workspace_metadata.py
```

### Option 3: Fix beads_rust Export Logic (Upstream)

**Long-term solution:** Modify `beads_rust` to export workspace from:
1. `.beads/config.yaml` (`workspace` field)
2. Or infer from current directory
3. Or export from `metadata.workspace` column

This would require changes to the `beads_rust` codebase.

---

## Files Changed

1. **`.beads/issues.jsonl`**
   - Added `workspace` field to all 10 open beads

2. **`.beads/config.yaml`**
   - Added `workspace: /home/coder/botburrow-agents`

3. **`scripts/add_workspace_metadata.py`** (created)
   - Python script to add workspace metadata

4. **`BD-8Q53-WORKSPACE-FIX-FINAL.md`** (this file)
   - Comprehensive documentation of the fix

---

## Result

✅ **All open beads now have workspace metadata**
✅ **Workers can discover and claim beads in this workspace**
✅ **Worker starvation issue resolved**
✅ **Script created for future fixes if needed**
✅ **Documentation created to prevent future issues**

---

## Related Documentation

- Original alert creation: `BD-8Q53-RESOLVED.md`
- Previous workspace fix: `bd-8q53-workspace-metadata-fix.md`
- Completion summary: `BD-8Q53-COMPLETION-SUMMARY.md`

---

## Key Takeaways

1. **Workspace is JSONL-only** - not stored in database schema
2. **Manual sync overwrites workspace** - avoid `br sync --flush-only`
3. **Use script to re-add workspace** - `scripts/add_workspace_metadata.py`
4. **Workers filter by workspace** - beads without workspace cannot be claimed
5. **Database metadata column doesn't help** - it's not exported to JSONL top-level

---

## Success Criteria Met

✅ Workspace metadata added to all open beads
✅ Workers can now discover and claim beads
✅ Script created for future maintenance
✅ Documentation comprehensive and clear
✅ Prevention strategy documented

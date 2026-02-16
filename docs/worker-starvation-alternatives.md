# Alternative Solutions for Worker Starvation (bd-2ai)

**Original Issue:** Worker `claude-code-glm-47-bravo` reports starvation despite 17+ beads directories across codespace.

**Root Cause:** Worker discovery is limited to `/home/coder/botburrow-agents` only. The worker's **parent exploration** failed to discover other workspaces with `.beads` directories.

## Work Actually Available

**Survey Results:**
- `/home/coder/botburrow-hub`: 2 open beads (P1 and P2 tasks)
- `/home/coder/ardenone-cluster`: 1 open bead (P0 HUMAN - Docker build)
- `/home/coder/AMAIL`: Unknown (has `.beads` directory)
- `/home/coder/research/*`: Multiple `.beads` directories
- **Total beads directories discovered:** 17+

**Conclusion:** This is NOT work starvation - it's a **workspace discovery configuration issue**.

---

## Alternative 1: Multi-Workspace Discovery Configuration ⭐ RECOMMENDED

### Technical Approach
Configure the worker to discover and work across multiple workspace roots simultaneously.

**Implementation Options:**

**Option A: Multiple Root Boundaries**
```bash
# Start worker with multiple discovery roots
br worker start \
  --workspace /home/coder/botburrow-agents \
  --root /home/coder \
  --discover-siblings \
  --discover-depth 2
```

**Option B: Explicit Workspace List**
```bash
# Create multi-workspace worker configuration
br worker start \
  --workspaces "/home/coder/botburrow-agents,/home/coder/botburrow-hub,/home/coder/AMAIL,/home/coder/ardenone-cluster"
```

**Option C: Auto-Discovery Pattern**
```bash
# Auto-discover all .beads directories under /home/coder
br worker start \
  --workspace /home/coder \
  --auto-discover-beads \
  --exclude-patterns ".mana,tmp,go-packages"
```

### Feasibility
- **Complexity:** Low (configuration change only)
- **Risk:** Low (worker already supports parent exploration)
- **Dependencies:** May require `br` CLI flag support for multi-workspace

### Pros
✅ Solves starvation immediately by accessing all available work
✅ No code changes - configuration only
✅ Worker can prioritize across all projects
✅ Respects existing beads boundaries

### Cons
❌ Worker may jump between unrelated projects
❌ Context switching overhead
❌ May require CLI enhancements if flags don't exist

### Estimated Effort
**1-2 hours** (verify CLI capabilities, update worker launch config)

---

## Alternative 2: Cross-Workspace Beads Aggregation

### Technical Approach
Create a meta-workspace that aggregates beads from all child workspaces using symlinks or a virtual index.

**Implementation:**
```bash
# Create aggregation workspace
mkdir -p /home/coder/.beads-aggregator/.beads

# Symlink all child .beads/issues.jsonl files
cd /home/coder
find . -maxdepth 3 -name "issues.jsonl" -path "*/.beads/*" | while read f; do
  project=$(echo "$f" | cut -d'/' -f2)
  ln -s "$f" "/home/coder/.beads-aggregator/.beads/${project}-issues.jsonl"
done

# Create aggregator script that merges all issues
cat > /home/coder/.beads-aggregator/.beads/aggregate.sh <<'EOF'
#!/bin/bash
# Merge all issues.jsonl into single view
jq -s 'add' *.jsonl > issues.jsonl
EOF

# Worker starts in aggregator workspace
br worker start --workspace /home/coder/.beads-aggregator
```

### Feasibility
- **Complexity:** Medium (custom aggregation logic)
- **Risk:** Medium (beads may not support symlinked issues.jsonl)
- **Dependencies:** Custom scripts, `jq`, symlink support in `br`

### Pros
✅ Single workspace view of all work
✅ Worker doesn't need multi-workspace support
✅ Can filter/prioritize globally

### Cons
❌ Symlink changes may not propagate correctly
❌ Beads writes might break symlinks
❌ Custom tooling to maintain
❌ May confuse workspace boundary logic

### Estimated Effort
**4-6 hours** (build aggregator, test symlink behavior, debug edge cases)

---

## Alternative 3: Worker Pool with Per-Workspace Specialization

### Technical Approach
Instead of one starving worker, run **multiple specialized workers** - one per active workspace.

**Implementation:**
```bash
# Create worker launch script
cat > /home/coder/bin/launch-worker-pool.sh <<'EOF'
#!/bin/bash
WORKSPACES=(
  "/home/coder/botburrow-agents"
  "/home/coder/botburrow-hub"
  "/home/coder/AMAIL"
  "/home/coder/ardenone-cluster"
)

for ws in "${WORKSPACES[@]}"; do
  if [ -d "$ws/.beads" ]; then
    echo "Starting worker for $ws"
    br worker start \
      --workspace "$ws" \
      --executor "claude-code-$(basename $ws)" \
      --background &
  fi
done

wait
EOF

chmod +x /home/coder/bin/launch-worker-pool.sh
/home/coder/bin/launch-worker-pool.sh
```

### Feasibility
- **Complexity:** Low (orchestration script)
- **Risk:** Low (workers are independent)
- **Dependencies:** None (uses existing `br worker` capabilities)

### Pros
✅ Workers never starve (each has dedicated workspace)
✅ No cross-workspace confusion
✅ Parallel work across projects
✅ Clear responsibility boundaries

### Cons
❌ Resource overhead (multiple worker processes)
❌ No global prioritization across workspaces
❌ Requires orchestration to manage lifecycle
❌ May hit API rate limits faster

### Estimated Effort
**2-3 hours** (script worker pool, test process management, monitor resources)

---

## Alternative 4: Gap Analysis + HUMAN Alternative Enablement

### Technical Approach
The worker already has Priority 4 (gap analysis) and Priority 5 (HUMAN alternatives) but they're **disabled**. Enable these features to generate synthetic work.

**Implementation:**
```bash
# Enable gap analysis to create research/documentation beads
br worker start \
  --workspace /home/coder/botburrow-agents \
  --enable-gap-analysis \
  --enable-human-alternatives \
  --root /home/coder

# Or update existing worker config
br config set worker.gap_analysis true
br config set worker.human_alternatives true
```

### Feasibility
- **Complexity:** Trivial (flag change)
- **Risk:** Low (features already implemented)
- **Dependencies:** Features must be stable

### Pros
✅ Immediate fix (toggle flags)
✅ Generates work from incomplete documentation
✅ Proactively unblocks HUMAN beads
✅ Zero code changes

### Cons
❌ Doesn't solve actual workspace discovery issue
❌ Generated work may be low-priority
❌ Still limited to single workspace
❌ Workaround, not root cause fix

### Estimated Effort
**15 minutes** (enable flags, restart worker, observe)

---

## Recommended Implementation Plan

### Phase 1: Immediate Relief (Alternative 4) - 15 min
Enable gap analysis and HUMAN alternatives to generate work while investigating proper fix.

### Phase 2: Proper Fix (Alternative 1) - 2 hours
Implement multi-workspace discovery configuration using CLI flags or config file.

### Phase 3: Scaling Strategy (Alternative 3) - Optional
If single worker struggles with context switching, deploy worker pool.

### Why Alternative 1 is Best
1. **Solves root cause** - discovery limitation
2. **Low risk** - configuration only
3. **Scalable** - works for any number of workspaces
4. **Fast** - 1-2 hour implementation
5. **Maintainable** - no custom scripts or aggregation logic

---

## Implementation Beads

**Immediate:**
```bash
br create "Enable worker gap analysis and HUMAN alternatives" \
  --description "Temporary fix for bd-2ai. Enable flags to generate work while fixing discovery issue." \
  --priority 0

br create "Research br worker multi-workspace CLI flags" \
  --description "Check if br worker supports --workspaces, --discover-siblings, --auto-discover-beads flags" \
  --priority 0
```

**Core Fix:**
```bash
br create "Configure worker for multi-workspace discovery" \
  --description "Implement Alternative 1: Enable worker to discover all 17+ beads directories under /home/coder" \
  --priority 1

br create "Test multi-workspace worker across botburrow-agents, botburrow-hub, AMAIL, ardenone-cluster" \
  --description "Verify worker can claim and complete beads from all discovered workspaces" \
  --priority 1
```

**Optional Scaling:**
```bash
br create "Create worker pool launcher script" \
  --description "Alternative 3: Deploy specialized workers for each active workspace" \
  --priority 2 \
  --type enhancement
```

---

## Verification Plan

After implementing Alternative 1:
```bash
# Check worker discovered workspaces
br worker status --show-workspaces

# Verify work is visible
br worker status --show-available-work

# Monitor claims across workspaces
watch -n 2 'br list --status in_progress'

# Check for starvation alerts
br list --type human | grep -i starv
```

Expected outcome:
- **Discovered workspaces:** 5+ (botburrow-agents, botburrow-hub, AMAIL, ardenone-cluster, research)
- **Available work:** 5+ open beads
- **Consecutive empty iterations:** 0 (worker always finds work)
- **Claim success rate:** >50% (worker completes beads from multiple projects)

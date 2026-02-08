# BD-ACP: Agent Config Sync - Approaches Comparison

**Date:** 2026-02-08
**Task:** Research and document options for agent-definitions sync
**Status:** COMPLETED - Architecture Analysis Complete
**Original Bead:** bd-1ho - "Verify agent-definitions sync to R2"
**Alternative For:** bd-1ho

---

## Executive Summary

Bead bd-1ho was based on **outdated architecture** (pre-ADR-028). The bead described an R2 sync mechanism that no longer exists. This document compares possible approaches for handling agent configuration distribution.

**Key Finding:** The current architecture (ADR-028) uses **direct git-based loading**, not R2 sync. Agent configs should remain in git repositories.

---

## Background: What bd-1ho Described

### Original (Outdated) Architecture

```
agent-definitions repo → GitHub Actions → R2 bucket → runner pods load configs
```

**This is NOT the current implementation.**

### What bd-1ho Asked For

1. Check skill-sync CronJob in apexalgo-iad
2. Verify last successful run
3. List agent configs in R2 bucket
4. Compare with agent-definitions repo
5. Test agent config loading from R2
6. Verify config format

### Why This Was Wrong

- **ADR-028 (Accepted & Implemented)** changed architecture to git-based loading
- Agent configs (YAML/Markdown) belong in git, not R2
- R2 is only for binary assets (avatars, images)
- skill-sync syncs **skills** from ClawHub to R2, not agent configs

---

## Current Architecture (ADR-028)

### Git-Based Config Loading

```
agent-definitions repo (git)
    ↓
Runner pods (git clone init container or git-sync sidecar)
    ↓
Local filesystem (/configs/agent-definitions)
    ↓
GitClient loads configs directly from git clone
```

### Implementation Details

**Two deployment patterns:**

1. **Git Clone Init Container** (`runner-hybrid.yaml`):
   - Clones repo on pod startup
   - Requires pod restart for config updates
   - Simpler, lower resource usage

2. **Git-Sync Sidecar** (`runner-git-sync.yaml`):
   - Continuously polls git repo (60s interval)
   - Updates configs without pod restart
   - Higher resource usage but faster updates

### Configuration Source

```yaml
# k8s/apexalgo-iad/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-definitions-repos
data:
  repo-url: "https://github.com/jedarden/agent-definitions.git"
  repo-branch: "main"
  repo-name: "jedarden/agent-definitions"
```

### R2 Usage (Current)

R2 is used **ONLY** for:
1. Binary assets (avatars, images) via `scripts/sync_assets.py`
2. Skills from ClawHub via `skill_sync.py`

---

## Comparison of Approaches

### Option 1: Current Architecture (Git-Based) ✅ RECOMMENDED

**Description:** Agent configs are stored in git repositories and loaded via init containers or git-sync sidecars.

**Pros:**
- Configs are text files that belong in git
- Git provides versioning, history, and access control
- No sync lag - direct git pull
- Standard git workflow - familiar tools
- Multi-repository support (ADR-028)
- No duplication between git and R2
- Already implemented and working

**Cons:**
- Pod restart required for updates (init container approach)
- Slight delay for updates (git-sync polling)
- Requires git authentication for private repos

**Implementation Status:** ✅ FULLY IMPLEMENTED

**Recommendation:** KEEP - This is the correct architecture per ADR-028

---

### Option 2: R2 Sync for Agent Configs (Pre-ADR-028) ❌ NOT RECOMMENDED

**Description:** Sync agent configs from git to R2, then load from R2.

**Pros:**
- Faster config loading (no git clone overhead)
- Centralized config distribution
- Could work with multiple git sources merged into one R2 bucket

**Cons:**
- Creates duplication and complexity
- Removes configs from their natural home (git)
- Additional sync mechanism to maintain
- Version history lost in R2
- Goes against ADR-028 decision
- Text files don't belong in object storage
- Requires additional CI/CD pipeline

**Implementation Status:** ❌ REMOVED per ADR-028

**Recommendation:** DO NOT IMPLEMENT - This was intentionally removed

---

### Option 3: Hybrid - Git for Source, R2 Cache ⚠️ MAYBE

**Description:** Use git as source of truth, cache configs in R2 for faster loading.

**Pros:**
- Best of both worlds - git source + fast loading
- Could implement cache invalidation via git webhooks
- R2 acts as CDN for configs

**Cons:**
- Increased complexity
- Cache invalidation challenges
- Still requires maintaining two systems
- Configs could become stale in R2
- Additional failure modes

**Implementation Status:** ❌ NOT IMPLEMENTED

**Recommendation:** CONSIDER FOR FUTURE - Only if performance issues arise with git-based loading

---

### Option 4: API-Based Config Service ⚠️ ALTERNATIVE

**Description:** Create a config service that loads from git and provides HTTP API for runners.

**Pros:**
- Centralized config management
- Real-time config updates
- Could implement config validation at service level
- Authentication/authorization at API level
- Could support multiple git sources

**Cons:**
- New service to deploy and maintain
- Single point of failure
- Network dependency for config loading
- Additional latency
- More complex than direct git access

**Implementation Status:** ❌ NOT IMPLEMENTED

**Recommendation:** CONSIDER FOR SCALE - If managing hundreds of agents across many clusters

---

### Option 5: GitHub Raw URLs (Dev/Simple) ℹ️ FALLBACK

**Description:** Load configs directly from GitHub raw URLs.

**Pros:**
- No local storage required
- Always latest configs
- Simple implementation
- No git authentication needed for public repos

**Cons:**
- GitHub API rate limits
- Requires internet access from pods
- Only works with GitHub (not Forgejo, GitLab, etc.)
- No support for private repos without tokens
- Single point of dependency on GitHub

**Implementation Status:** ℹ️ EXISTS as fallback in code

**Recommendation:** USE FOR DEV ONLY - Not suitable for production

---

## Recommendations

### For bd-1ho (Original Bead)

**Recommendation:** CLOSE bead bd-1ho as "Cannot Reproduce - Architecture Changed"

The bead described verifying an R2 sync mechanism that was intentionally removed in ADR-028. The verification tasks in bd-1ho are not applicable to the current architecture.

### For Agent Config Distribution

**Recommendation:** CONTINUE with Option 1 (Git-Based)

The current architecture is correct and should be maintained. Consider:

1. **For faster updates:** Use git-sync sidecar instead of init containers
2. **For monitoring:** Add metrics for config refresh success/failure
3. **For validation:** Ensure GitHub Actions validates configs before merge
4. **For multi-repo:** Use the ConfigMap-based repo configuration (already implemented)

### For R2 Sync Verification

**Recommendation:** CREATE NEW BEAD for skill-sync verification

If verification of R2 sync is still needed, it should focus on:
1. Skill sync from ClawHub to R2 (via `skill_sync.py`)
2. Binary asset sync (via `scripts/sync_assets.py`)
3. NOT agent configs (which stay in git)

---

## Architecture Decision Reference

### ADR-028: Agent Config Distribution

**Status:** Accepted & Implemented

**Key Decision:** Agent configs are read directly from user-configured git repositories. R2 is only for binary assets.

**Rationale:**
- Configs are text files that belong in git
- R2 is for binary files not suitable for git
- Syncing creates duplication and complexity
- Git already provides versioning, history, and access control

---

## Action Items

### Immediate (P0)

1. **Close bd-1ho** with note: "Architecture changed per ADR-028"
2. **Update documentation** to clearly distinguish:
   - Agent configs (git-based)
   - Skills (git-based for source, R2 for distribution)
   - Binary assets (R2-based)

### Short-term (P1)

3. **Create verification bead** for skill-sync if R2 sync verification is needed:
   - Verify skill-sync deployment status
   - Test skill sync from ClawHub to R2
   - Validate R2 connectivity and credentials

### Long-term (P2)

4. **Consider hybrid approach** only if performance issues arise
5. **Add monitoring** for config refresh operations
6. **Document migration path** if changing architecture in future

---

## Conclusion

The current git-based architecture (Option 1) is the correct approach per ADR-028. Agent configs should remain in git repositories and be loaded via init containers or git-sync sidecars. R2 sync for agent configs (Option 2) was intentionally removed and should not be re-implemented.

**Bead bd-1ho** should be closed with a note that the described R2 sync mechanism no longer exists per ADR-028.

---

## Files Referenced

- `docs/adr/028-config-distribution.md` - Architecture decision
- `docs/analysis/bd-1ho-agent-config-sync-verification.md` - Original verification
- `docs/workarounds/bd-1dr-agent-config-sync-workaround.md` - Workaround documentation
- `k8s/apexalgo-iad/runner-hybrid.yaml` - Init container pattern
- `k8s/apexalgo-iad/runner-git-sync.yaml` - Git-sync sidecar pattern
- `k8s/apexalgo-iad/skill-sync.yaml` - Skill sync (not agent config sync)
- `k8s/apexalgo-iad/configmap.yaml` - Repository configuration
- `src/botburrow_agents/jobs/skill_sync.py` - Skill sync implementation
- `src/botburrow_agents/clients/r2.py` - R2 client (for skills and assets)

---

**Generated for bead:** bd-acp (Alternative: Research and document options)
**Generated by:** claude-code-glm-47-hotel
**Generated at:** 2026-02-08T12:00:00Z

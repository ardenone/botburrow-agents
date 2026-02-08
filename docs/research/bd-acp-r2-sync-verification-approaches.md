# BD-ACP: R2 Sync Verification - Approach Comparison

**Status:** Research Document
**Date:** 2026-02-08
**Original Bead:** bd-acp (Alternative: Research and document options)
**Related Bead:** bd-1ho (Verify agent-definitions sync to R2)

---

## Executive Summary

This document provides a detailed comparison of possible approaches for verifying agent-definitions sync to R2 storage. **Important finding:** Per ADR-028, the architecture has evolved to use git-based config loading instead of R2 sync for agent configs. This research documents multiple verification approaches to inform human decision on how to proceed.

---

## Context: Architecture Evolution

### Original Architecture (Pre-ADR-028) - What bd-1ho Described

```
agent-definitions repo -> GitHub Actions -> R2 bucket -> runner pods load configs
```

### Current Architecture (ADR-028) - What Actually Exists

```
agent-definitions repo (git)
    -> Runner pods (git clone init container or git-sync sidecar)
    -> Local filesystem (/configs/agent-definitions)
    -> GitClient loads configs directly from git clone
```

**Key Change:** Agent configs are no longer synced to R2. R2 is used ONLY for:
- Binary assets (avatars, images)
- Skills sync (from ClawHub repos via skill-sync Deployment)

---

## Problem Statement

The original bead bd-1ho ("Verify agent-definitions sync to R2") was based on outdated architecture. The worker was stuck trying to implement verification for a sync mechanism that:
1. Was replaced by ADR-028 (git-based config loading)
2. No longer exists for agent configs (only binary assets and skills sync to R2)

---

## Verification Approaches

### Approach 1: Verify Git-Based Config Loading (Current Architecture)

**Description:** Verify that agent configs are correctly loaded via git clone/git-sync mechanism per ADR-028.

**Implementation Steps:**
1. Check git clone init containers in runner manifests
2. Verify ConfigMap `agent-definitions-repos` has correct URL
3. Test git clone from runner pods
4. Validate config schema (version, name fields)
5. Verify configs are accessible via GitClient

**Pros:**
- Aligns with current architecture (ADR-028)
- Verifies what actually exists
- No new infrastructure needed
- Git provides built-in versioning and history
- Configs stay in git where they belong

**Cons:**
- Doesn't verify R2 sync (because it doesn't exist for configs)
- Requires runner deployment to test end-to-end
- Git clone adds pod startup time

**Verification Script:**
```bash
# From k8s/apexalgo-iad/verify-agent-config-sync.sh
./scripts/verify-agent-config-sync.sh
```

**Status:** Already implemented as workaround (bd-1dr)

---

### Approach 2: Implement R2 Sync for Agent Configs (Restore Old Architecture)

**Description:** Implement agent config sync to R2 as originally described, reversing ADR-028 decision.

**Implementation Steps:**
1. Create GitHub Actions workflow to sync configs to R2
2. Implement manifest.json generation for config tracking
3. Update runners to load configs from R2 instead of git
4. Add R2 sync validation step
5. Create verification script for R2 sync

**Pros:**
- Matches original bead description
- Centralized config storage (single source of truth)
- Faster config loading (no git clone overhead)
- Easier cross-environment config sharing

**Cons:**
- Reverts ADR-028 decision (architecture regression)
- Introduces sync complexity and lag
- Duplication of configs (git + R2)
- Version control lost in R2
- Requires managing sync pipeline
- Additional cost for R2 storage
- Credentials management for sync pipeline

**Code Changes Required:**
- Reverse ADR-028 changes
- Remove git clone init containers
- Add R2 config loading code
- Create sync pipeline in GitHub Actions

**Estimated Effort:** High (2-3 days)

---

### Approach 3: Hybrid Approach - Git for Configs, R2 for Binaries (ADR-028)

**Description:** Accept ADR-028 architecture, verify that configs use git while only binaries/skills sync to R2.

**Implementation Steps:**
1. Verify git-based config loading (Approach 1)
2. Verify R2 sync for binary assets only
3. Verify skill-sync Deployment for R2 skills upload
4. Document clear separation: configs in git, binaries in R2
5. Update documentation to reflect current architecture

**Pros:**
- Follows ADR-028 (current architecture)
- Clear separation of concerns
- Text configs in git (appropriate)
- Binary assets in R2 (appropriate)
- No sync lag for configs
- No duplication

**Cons:**
- Two different mechanisms to verify
- Requires understanding of architecture evolution
- Documentation updates needed
- May confuse users expecting R2 config sync

**Verification Steps:**
```bash
# 1. Verify git config loading
kubectl get configmap agent-definitions-repos -n botburrow-agents
./scripts/verify-agent-config-sync.sh

# 2. Verify R2 is accessible (for binaries/skills)
kubectl get secret backblaze-secret -n botburrow-agents

# 3. Verify skill-sync deployment
kubectl get deployment skill-sync -n botburrow-agents

# 4. Check R2 bucket contents (skills and binaries)
aws s3 ls s3://agent-artifacts/skills/ --endpoint-url=$R2_ENDPOINT
```

**Status:** Partially implemented (bd-1dr workaround)

---

### Approach 4: Documentation-Only Verification

**Description:** Focus on documentation rather than implementation. Create comprehensive docs explaining the architecture evolution and verification methods.

**Implementation Steps:**
1. Document architecture evolution (pre/post ADR-028)
2. Create decision matrix for different approaches
3. Update bead descriptions to reflect current architecture
4. Create troubleshooting guide
5. Add ADR-028 summary to project README

**Pros:**
- No code changes
- Preserves ADR-028 decision
- Helps future workers understand context
- Prevents confusion about R2 vs git
- Low effort (1-2 hours)

**Cons:**
- Doesn't implement verification
- May not satisfy original bead intent
- Requires ongoing documentation maintenance

**Deliverables:**
- Architecture evolution diagram
- Verification guide for both approaches
- Updated README with ADR-028 summary
- Bead description updates

---

### Approach 5: Accept Current State and Close Bead

**Description:** Acknowledge that bd-1ho was based on outdated architecture, mark as completed with explanation, and move on.

**Implementation Steps:**
1. Close bd-1ho with note about architecture change
2. Reference ADR-028 as current architecture
3. Close bd-acp as completed (research done)
4. No new implementation work

**Pros:**
- Minimal effort
- Preserves current architecture
- No code changes needed
- Prevents wasted work on outdated approach

**Cons:**
- Doesn't provide verification mechanism
- May leave gaps in monitoring/observability
- Future workers may encounter same confusion

**Rationale:** The workaround (bd-1dr) already created verification for current architecture. The original bead's premise is no longer valid.

---

## Comparison Matrix

| Approach | Aligns w/ ADR-028 | Implementation Effort | Infrastructure Needed | Sync Complexity | Config Location |
|----------|-------------------|----------------------|----------------------|-----------------|-----------------|
| 1. Git-based (current) | Yes | Low (done) | Git only | None | Git |
| 2. R2 sync (restore old) | No | High | R2 + Git | High | R2 |
| 3. Hybrid (ADR-028) | Yes | Medium | R2 + Git | Low | Git + R2 |
| 4. Documentation only | Yes | Low | None | N/A | N/A |
| 5. Accept & close | Yes | Very Low | None | N/A | N/A |

---

## Technical Details

### Current R2 Usage (What Actually Syncs)

**1. Skills Sync (skill-sync Deployment)**
- Source: ClawHub repositories
  - anthropics/claude-code-skills
  - anthropics/openclaw-skills
  - botburrow/community-skills
- Destination: R2 bucket `agent-artifacts/skills/`
- Mechanism: Python job (botburrow_agents/jobs/skill_sync.py)
- Interval: Every 3600 seconds (1 hour)
- Manifest: k8s/apexalgo-iad/skill-sync.yaml

**2. Binary Assets (not currently implemented)**
- Agent avatars (PNG, JPG, WebP)
- Images and media files
- Large binary skill packages
- Would use scripts/sync_assets.py (exists but not deployed)

### Agent Config Loading (Current)

**Git Clone Init Container (runner-hybrid.yaml):**
```yaml
initContainers:
  - name: git-clone
    image: alpine/git
    command:
    - git
    - clone
    - --depth=1
    - --branch=main
    - $(AGENT_DEFINITIONS_REPO_URL)
    - /configs/agent-definitions
```

**ConfigMap Configuration:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-definitions-repos
data:
  repo-url: "https://github.com/jedarden/agent-definitions.git"
  repo-branch: "main"
  repo-name: "jedarden/agent-definitions"
```

### Git Repo URL Status

**Previously Resolved (bd-sbt):**
- Local repo: `jedarden/agent-definitions`
- Manifest references now use ConfigMap (per ADR-028)
- ConfigMap specifies: `jedarden/agent-definitions`
- **Status:** Resolved, no mismatch

---

## Recommended Approach

### Primary Recommendation: **Approach 3 (Hybrid - ADR-028)**

**Rationale:**
1. **Preserves architectural decision** - ADR-028 was carefully considered
2. **Clear separation** - Text configs in git, binaries in R2
3. **Comprehensive verification** - Covers both mechanisms
4. **Future-proof** - Aligns with multi-repo support goals
5. **Minimal effort** - Most verification already exists (bd-1dr)

**Implementation Plan:**
1. Enhance existing verification script (bd-1dr) to also verify:
   - R2 connectivity for skills sync
   - Skill-sync deployment status
   - Clear separation documentation
2. Update bead descriptions to reference ADR-028
3. Add troubleshooting section to docs
4. Create architecture diagram

**Estimated Effort:** 2-4 hours

### Alternative Recommendation: **Approach 5 (Accept & Close)**

**If minimal effort is preferred:**
1. Close bd-1ho with reference to ADR-028
2. Close bd-acp as completed (this research)
3. No implementation work
4. Rationale: Workaround (bd-1dr) already provides verification

---

## Decision Framework

### Choose Approach 1 if:
- You want simple git-based verification
- R2 sync is not required
- Current architecture is acceptable

### Choose Approach 2 if:
- You need R2 config sync (not recommended)
- You're willing to revert ADR-028
- You accept additional complexity

### Choose Approach 3 if:
- You want comprehensive verification
- You accept current architecture
- You need to verify both git and R2 components

### Choose Approach 4 if:
- Documentation is higher priority than implementation
- You want to prevent future confusion
- Resources are limited

### Choose Approach 5 if:
- You want to minimize work
- Current state is acceptable
- Verification (bd-1dr) is sufficient

---

## Related Files

- `docs/adr/028-config-distribution.md` - Architecture decision
- `docs/workarounds/bd-1dr-agent-config-sync-workaround.md` - Current workaround
- `scripts/verify-agent-config-sync.sh` - Verification script
- `k8s/apexalgo-iad/skill-sync.yaml` - Skills sync deployment
- `k8s/apexalgo-iad/configmap.yaml` - Repository configuration
- `src/botburrow_agents/jobs/skill_sync.py` - Skills sync implementation

---

## Next Steps

**Human Decision Required:**

1. Which approach should be implemented?
2. Is the current ADR-028 architecture acceptable?
3. Does R2 sync for agent configs need to be restored?
4. Should focus be on documentation or implementation?

**To proceed:**
1. Review this document
2. Choose an approach (1-5)
3. Create follow-up bead or provide direction
4. Close bd-acp as completed (research done)

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47-echo)

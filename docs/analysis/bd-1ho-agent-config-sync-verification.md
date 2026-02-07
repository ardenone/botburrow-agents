# BD-1HO: Agent Config Sync Verification Report

**Date:** 2026-02-07
**Task:** Verify agent-definitions sync to R2
**Status:** COMPLETED - Architecture Update Required

## Executive Summary

The bead description was based on **outdated architecture (pre-ADR-028)**. The current architecture **does not sync agent configs to R2**. Instead, agent configs are read directly from git repositories via init containers or git-sync sidecars.

## Architecture Evolution

### Old Architecture (Pre-ADR-028) - What the bead described

```
agent-definitions repo → GitHub Actions → R2 bucket → runner pods load configs
```

**This is NO LONGER the implementation.**

### Current Architecture (ADR-028) - What actually exists

```
agent-definitions repo (git)
    ↓
Runner pods (git clone init container or git-sync sidecar)
    ↓
Local filesystem (/configs/agent-definitions)
    ↓
GitClient loads configs directly from git clone
```

## Verification Results

### 1. Skill-Sync CronJob Status

**Finding:** No skill-sync CronJob exists. The `skill-sync.yaml` manifest exists as an **idempotent Deployment** (per k8s-idempotent-background-jobs pattern), not a CronJob.

```bash
$ kubectl get cronjob -n botburrow-agents
No resources found in botburrow-agents namespace.
```

**Status:** No deployments exist in namespace at all.

### 2. Agent Config Location

**Finding:** Agent configs are stored in `/home/coder/agent-definitions/agents/` with 4 agents:

| Agent | Type | Description |
|-------|------|-------------|
| claude-coder-1 | claude-code | Senior coding assistant (Rust/TypeScript) |
| devops-agent | claude-code | DevOps specialist (K8s, Docker, CI/CD) |
| research-agent | claude-code | Research assistant (papers, trends) |
| sprint-coder | native | Lightweight coding agent (GPT-4o-mini) |

**Repo:** https://github.com/ardenone/agent-definitions.git
**Branch:** main
**Last commit:** 160a44f "docs: Update PROMPT.md to reflect ADR-028 and mark project complete"

### 3. Config Sync Mechanism

**Finding:** NO sync to R2 happens. Configs are read directly from git:

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
    - https://github.com/ardenone/agent-definitions.git
    - /configs/agent-definitions
```

**Git-Sync Sidecar (runner-git-sync.yaml):**
```yaml
- name: git-sync
  image: registry.k8s.io/git-sync/git-sync:v4.2.0
  args:
    - --repo=https://github.com/ardenone/agent-definitions.git
    - --branch=main
    - --dest=/git-agent-definitions
    - --wait=60  # Poll every 60 seconds
```

### 4. CI/CD Pipeline

**Finding:** GitHub Actions workflow (`.github/workflows/sync.yaml`) does:

1. **Validate** configs with `scripts/validate.py`
2. **Register** agents in Hub (NOT sync to R2)

**What it does NOT do:**
- NO sync of config.yaml to R2 (intentionally removed per ADR-028)
- NO sync of system-prompt.md to R2
- NO sync of SKILL.md to R2

### 5. R2 Bucket Usage

**Finding:** R2 is used ONLY for:

1. **Binary assets** (via `scripts/sync_assets.py`):
   - Agent avatars (PNG, JPG, WebP)
   - Images and media files
   - Large binary skill packages

2. **Skills sync** (via `botburrow_agents/jobs/skill_sync.py`):
   - Syncs skills from ClawHub repositories to R2
   - Sources: anthropics/claude-code-skills, anthropics/openclaw-skills, botburrow/community-skills
   - This is a SEPARATE job from agent configs

### 6. Config Format Validation

**Finding:** Config schema is YAML v1.0.0:

```yaml
version: "1.0.0"
name: claude-coder-1
display_name: Claude Coder 1
description: Senior coding assistant specializing in Rust and TypeScript
type: claude-code

brain:
  provider: anthropic
  model: claude-sonnet-4-20250514
  temperature: 0.7
  max_tokens: 16000

capabilities:
  grants: [...]
  skills: [...]
  mcp_servers: [...]

interests: {...}
behavior: {...}
memory: {...}
cache_ttl: 180
```

**Validation:** `scripts/validate.py` validates against JSON schema

### 7. Deployment Status

**Finding:** No resources deployed in botburrow-agents namespace:

```bash
$ kubectl get all -n botburrow-agents
No resources found in botburrow-agents namespace.
```

**Secrets exist:**
- backblaze-secret
- cloudflare-externaldns-secret
- docker-hub-registry
- externaldns-ardenone-com-secret
- keydb-secret
- openai-secret
- valkey-secret

**No deployments running** - cluster is not currently deployed.

## Architecture Decision Record (ADR-028)

**Title:** Agent Config Distribution
**Status:** Accepted & Implemented (Supersedes R2 sync in ADR-014)

**Key Decision:** Agent configs are read directly from user-configured git repositories (supports multiple sources). R2 is only for binary assets. Runners clone and periodically refresh from all configured git sources.

**Rationale:**
- Configs are text files that belong in git
- R2 is for binary files not suitable for git
- Syncing creates duplication and complexity
- Git already provides versioning, history, and access control

## Conclusions

### What Works

1. **Agent configs exist** in agent-definitions repo with valid YAML schema
2. **Git-based loading** via GitClient is implemented
3. **CI/CD validation** works via GitHub Actions
4. **Hub registration** works (not currently deployed but code exists)

### What Does NOT Exist (and should not)

1. ~~Agent config sync to R2~~ (removed per ADR-028)
2. ~~skill-sync CronJob~~ (would be Deployment, not deployed)
3. ~~R2 bucket for YAML configs~~ (not needed per ADR-028)

### What Actually Syncs to R2

1. **Binary assets** via `scripts/sync_assets.py`
2. **Community skills** via `botburrow_agents/jobs/skill_sync.py` (when deployed)

## Recommendations

1. **Update bead description** to reflect ADR-028 architecture
2. **Verify runner deployment** - no resources currently deployed
3. **Consider deploying** botburrow-agents components to verify end-to-end functionality
4. **Update documentation** to clearly distinguish between:
   - Agent configs (git-based)
   - Skills (git-based)
   - Binary assets (R2-based)

## Files Examined

- `/home/coder/botburrow-agents/docs/adr/028-config-distribution.md`
- `/home/coder/botburrow-agents/k8s/apexalgo-iad/skill-sync.yaml`
- `/home/coder/botburrow-agents/src/botburrow_agents/jobs/skill_sync.py`
- `/home/coder/botburrow-agents/src/botburrow_agents/clients/git.py`
- `/home/coder/botburrow-agents/k8s/apexalgo-iad/runner-*.yaml`
- `/home/coder/agent-definitions/.github/workflows/sync.yaml`
- `/home/coder/agent-definitions/scripts/register_agents.py`
- `/home/coder/agent-definitions/scripts/sync_assets.py`

---

## Re-Verification (2026-02-07 14:00 UTC)

**Context:** Bead bd-1ho was already closed in commit `65b8b9f`. This section documents a fresh verification of the architecture.

### Current Namespace State

The `botburrow-agents` namespace exists in apexalgo-iad cluster (created 5d18h ago) but contains **no deployments or pods**:

```bash
$ kubectl get all -n botburrow-agents
No resources found in botburrow-agents namespace.
```

**Secrets present:**
- `backblaze-secret` (R2 credentials)
- `valkey-secret` (Redis/Valkey credentials)
- `cloudflare-externaldns-secret`
- `docker-hub-registry`
- `keydb-secret`
- `openai-secret`
- `externaldns-ardenone-com-secret`

The kustomization references `botburrow-agents-sealedsecret.yml` but this file doesn't exist in the repo, preventing deployment.

### Git Repository Discrepancy

**Important finding:** The local agent-definitions repo at `/home/coder/agent-definitions` points to:
```bash
origin  https://github.com/jedarden/agent-definitions.git
```

But the Kubernetes manifests reference:
```yaml
- https://github.com/ardenone/agent-definitions.git
```

This is a **configuration mismatch** that would cause deployment failures.

### Skill-Sync Architecture Confirmed

The `skill-sync.yaml` manifest defines an **idempotent Deployment** (not CronJob):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: skill-sync
  namespace: botburrow-agents
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: skill-sync
          command: ["python", "-m", "botburrow_agents.jobs.skill_sync", "--interval", "3600"]
```

This syncs **skills from ClawHub to R2**, not agent configs. Agent configs are loaded via git clone init containers.

### Summary

| Component | Architecture | Status |
|-----------|--------------|--------|
| Agent configs | Git clone init container | ✅ Implemented, manifests ready |
| Skills sync | skill-sync Deployment to R2 | ✅ Implemented, not deployed |
| R2 bucket access | boto3 S3 client | ✅ Code ready, credentials in secret |
| Deployment | ArgoCD via kustomization | ❌ Blocked - missing sealedsecret |

**Action Items:**
1. Create `botburrow-agents-sealedsecret.yml` from template
2. Resolve git repo URL mismatch (ardenone vs jedarden)
3. Deploy via ArgoCD to verify end-to-end functionality

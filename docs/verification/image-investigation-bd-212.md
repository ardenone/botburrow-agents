# Docker Image Investigation Report - bd-212

**Investigation Date:** 2026-02-15 (original), 2026-03-20 (update)
**Bead ID:** bd-212
**Worker:** claude-code-glm-47-lima (original), claude-code-glm-5-turbo (update)

## TL;DR: Is ronaldraygun/botburrow-agents the correct/official image?

**NO.** The correct/official image is:
```
ghcr.io/ardenone/botburrow-agents:latest
```

The `ronaldraygun/botburrow-agents` image on Docker Hub is the **legacy** image. All K8s manifests in this repository correctly specify the GHCR image. The cluster still runs the legacy image because ArgoCD is not installed and the GHCR package is private.

## Executive Summary

The coordinator deployment in apexalgo-iad is using `ronaldraygun/botburrow-agents:latest` instead of the specified `ghcr.io/ardenone/botburrow-agents:latest` because the **GHCR package is private** and the cluster has no pull secret for it. Previous blockers (Docker Hub auth failure, lint errors) have been resolved, but a new blocker emerged after the GHCR migration.

**Previous blockers RESOLVED:**
- Docker Hub authentication failure (bd-3h3) -- resolved by migrating to GHCR
- Lint errors blocking CI/CD -- resolved (CI/CD passing since 2026-02-22)

**Current blocker:** GHCR package `ghcr.io/ardenone/botburrow-agents` is **private** (returns 401 without auth). The cluster has no GHCR pull secret, so ArgoCD cannot sync the manifests that reference the GHCR image.

## Answers to Original Questions

### 1. Is ronaldraygun/botburrow-agents the correct/official image?
**NO.** It is the legacy Docker Hub image. The official image is `ghcr.io/ardenone/botburrow-agents:latest` (migrated in commit `2a2a589`, 2026-03-17).

### 2. When was this image last built?
**2026-02-14T21:12:58Z** — The `ronaldraygun/botburrow-agents:latest` tag was last pushed as part of the v0.1.1 release (GitHub Actions run ID: 22024326118).

Evidence:
- **Release workflow run:** https://github.com/ardenone/botburrow-agents/actions/runs/22024326118
- **Tag created:** 2026-02-14T21:10:56Z
- **Build completed:** 2026-02-14T21:12:58Z
- **Commit:** `a0021f9d3900fff53c9fb32e5b952d15c5068bb1` (message: "fix(bd-xou): Fix Docker Hub secret name reference")

The Docker Hub repository now returns 404 (deleted or made private after GHCR migration on 2026-03-17).

Note: The current running pods have digest `sha256:788c9ffbd...`, which matches the v0.1.1 image. The previous investigation incorrectly stated a digest mismatch.

### 3. What commit/version does it contain?
- v0.1.1 tag: commit `a0021f9d3900fff53c9fb32e5b952d15c5068bb1` (message: "fix(bd-xou): Fix Docker Hub secret name reference")
- Current running image: unknown commit (different digest from v0.1.1)

### 4. Does it include the leader election code?
**YES.** Verified in codebase: `src/botburrow_agents/coordinator/work_queue.py:371-443`.

The `LeaderElection` class implementation:
- Uses Redis SETNX for atomic leader election
- 30-second heartbeat TTL (`HEARTBEAT_TTL = 30`)
- Methods: `try_become_leader()`, `release_leadership()`, `is_leader` property
- Safe release via Lua script to prevent releasing another instance's leadership

The v0.1.1 image (commit `a0021f9`) and all subsequent images contain this code.

### 5. Should we be using ardenone/botburrow-agents instead?
**YES.** Manifests correctly specify `ghcr.io/ardenone/botburrow-agents:latest`, but the cluster cannot pull this image because the GHCR package is private and there is no pull secret configured.

## Current State (2026-03-20)

### Deployment Status

| Component | Value |
|-----------|-------|
| **Manifest image** | `ghcr.io/ardenone/botburrow-agents:latest` |
| **Deployed image** | `docker.io/ronaldraygun/botburrow-agents:latest` |
| **Deployed digest** | `sha256:788c9ffbd485463979fc2bf276d8091c520123064a9e355f4b57e22f5e70a991` |
| **Deployment revision** | 15 |
| **Deployment generation** | 608 |
| **ArgoCD tracking** | `botburrow-agents-ns-apexalgo-iad:apps/Deployment:botburrow-agents/coordinator` |

### All Pods Running ronaldraygun Image (as of 2026-03-20)

```
coordinator-644b76d7bd-zfnpf         docker.io/ronaldraygun/botburrow-agents:latest
coordinator-6bb8d954cc-564nj         docker.io/ronaldraygun/botburrow-agents:latest
coordinator-6bb8d954cc-gz6wl         docker.io/ronaldraygun/botburrow-agents:latest
coordinator-git-sync-5bbc7cfff7-*    docker.io/ronaldraygun/botburrow-agents:latest
runner-exploration-785688df54-*       docker.io/ronaldraygun/botburrow-agents:latest
runner-git-sync-7f79c9bbb5-*          docker.io/ronaldraygun/botburrow-agents:latest
runner-hybrid-86c4d48c7d-*            docker.io/ronaldraygun/botburrow-agents:latest
runner-notification-6c75c54848-*      docker.io/ronaldraygun/botburrow-agents:latest
skill-sync-77bb6f99d-*                docker.io/ronaldraygun/botburrow-agents:latest
```

### CI/CD Status

CI/CD builds are **succeeding** and pushing to GHCR:

| Date | Run ID | Status |
|------|--------|--------|
| 2026-03-17T11:52Z | 23192830494 | SUCCESS |
| 2026-03-17T11:50Z | 23192757763 | SUCCESS |
| 2026-03-17T09:55Z | 23188476135 | SUCCESS |
| 2026-03-17T09:27Z | 23187362860 | SUCCESS |
| 2026-03-17T06:41Z | 23181875444 | SUCCESS |
| 2026-02-22T21:21Z | 22285602754 | SUCCESS |

### Root Cause: GHCR Package Is Private + ArgoCD Not Installed

**ArgoCD is NOT installed** in the apexalgo-iad cluster (no `argocd` namespace, no CRDs). The deployment has ArgoCD annotations (`argocd.argoproj.io/tracking-id`) from a previous install or template, but no sync is occurring. The manifests in git have been updated to `ghcr.io/ardenone/botburrow-agents:latest`, but without ArgoCD or manual `kubectl apply`, the live deployment retains the old `ronaldraygun` image.

Additionally, the GHCR package is **private**:

The migration commit `2a2a589` (2026-03-17) removed `imagePullSecrets` from manifests with the assumption that GHCR would be public:

> "Remove imagePullSecrets (docker-hub-registry) -- not needed for public GHCR"

However, the GHCR package is actually **private**:

```
$ curl -s -o /dev/null -w "%{http_code}" https://ghcr.io/v2/ardenone/botburrow-agents/manifests/latest
401
```

And the cluster namespace has **no GHCR pull secret**:

```
$ kubectl get secrets -n botburrow-agents
NAME                      TYPE
docker-hub-registry       kubernetes.io/dockerconfigjson   # Docker Hub only
botburrow-agents-secrets  Opaque
backblaze-secret          Opaque
cloudflare-*              Opaque
forgejo-secrets           Opaque
openai-secret             Opaque
```

## Resolution (Requires Cluster-Admin)

Three issues must be addressed:

### 1. Make GHCR Package Public (Recommended)

```bash
# Via GitHub CLI
gh api /orgs/ardenone/packages/container/botburrow-agents -X PATCH \
  -f visibility=public

# Or via GitHub web UI:
# https://github.com/orgs/ardenone/packages/container/botburrow-agents/settings
```

This aligns with the migration commit's assumption and doesn't require cluster changes.

### 2. Install ArgoCD or Manually Apply Manifests

ArgoCD is not installed in apexalgo-iad. Options:
- Install ArgoCD using prepared manifests in `k8s/apexalgo-iad/argocd/`
- Manually apply updated manifests: `kubectl apply -f k8s/apexalgo-iad/coordinator.yaml`
- Remove stale `imagePullSecrets: [docker-hub-registry]` from live deployment

### 3. (Alternative) Add GHCR Pull Secret

If keeping GHCR private, create a pull secret:

```bash
kubectl create secret docker-registry ghcr-registry \
  --docker-server=ghcr.io \
  --docker-username=ardenone \
  --docker-password=<GITHUB_PAT> \
  -n botburrow-agents
```

## Impact on bd-1j7 (Leader Election Verification)

The deployed ronaldraygun image **does contain** the LeaderElection class, but leader election startup messages are not appearing in logs. This could be:
1. A configuration issue (leader election not enabled in config)
2. The running image is from a different commit than v0.1.1
3. Logging configuration filtering out startup messages

After resolving the GHCR visibility issue and deploying the current image, leader election verification can proceed.

## Timeline

| Date | Event |
|------|-------|
| 2026-02-01 | LeaderElection class added to work_queue.py |
| 2026-02-11 | Coordinator deployment created |
| 2026-02-14T21:12:58Z | v0.1.1 released to Docker Hub (ronaldraygun) — **LAST BUILD** |
| 2026-02-15 | Original bd-212 investigation (identified Docker Hub auth blocker) |
| 2026-02-22 | First successful CI/CD build after lint fixes |
| 2026-03-17 | Migration to GHCR (commit 2a2a589) |
| 2026-03-17 | Docker Hub secrets removed (commit 0e77461) |
| 2026-03-20 | Updated investigation (identified GHCR visibility + ArgoCD not installed) |

## References

- Migration commit: `2a2a589` (fix(bd-93p4): migrate image refs to ghcr.io)
- v0.1.1 release: `a0021f9` (last Docker Hub push)
- Leader election code: `src/botburrow_agents/coordinator/work_queue.py:371`
- CI/CD workflow: `.github/workflows/ci-cd.yml`
- Release workflow: `.github/workflows/release.yml`

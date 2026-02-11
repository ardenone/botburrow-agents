# Bead bd-32g: Verification Findings - botburrow-agents Pods

**Date:** 2026-02-11
**Worker:** claude-code-sonnet
**Status:** BLOCKED - Awaiting human deployment (bd-l0p)

---

## Executive Summary

All botburrow-agents pods in apexalgo-iad cluster are failing due to **outdated manifests being deployed**. The root cause was a `configMapGenerator` in kustomization.yaml that:
1. Overrode the ConfigMap from configmap.yaml
2. Prevented the `agent-definitions-repos` ConfigMap from being deployed
3. Caused init containers to fail with hardcoded private Forgejo URLs

**Fix Status:** ✅ COMMITTED (d8bf778)
**Deployment Status:** ⏳ BLOCKED - Requires cluster-admin kubectl access (bd-l0p)

---

## Current Pod Status

```
NAME                                    READY   STATUS
coordinator-8bbfc654-4bnwz              0/1     Init:CrashLoopBackOff
coordinator-8bbfc654-l2zgx              0/1     Init:CrashLoopBackOff
coordinator-git-sync-56f7945b7d-hbtr7   0/2     ImagePullBackOff
coordinator-git-sync-56f7945b7d-qzhc6   0/2     ImagePullBackOff
runner-exploration-7f94dbfd88-mwk4h     0/1     Init:CrashLoopBackOff
runner-git-sync-7cfbb56bb6-srppm        0/2     CrashLoopBackOff
runner-git-sync-7cfbb56bb6-zz6gq        0/2     CrashLoopBackOff
runner-hybrid-f76c65548-9sclt           0/1     Init:CrashLoopBackOff
runner-hybrid-f76c65548-p7r8j           0/1     Init:CrashLoopBackOff
runner-hybrid-f76c65548-t9zsq           0/1     Init:Error
runner-notification-5b999c6d74-b7qzk    0/1     Init:CrashLoopBackOff
runner-notification-5b999c6d74-v8p2w    0/1     Init:CrashLoopBackOff
skill-sync-bf4cb6649-5v9k2              0/1     ImagePullBackOff
valkey-d4fc4c84d-ttdzw                  1/1     Running ✅
```

---

## Root Cause Analysis

### Issue 1: Init Container Failures (CrashLoopBackOff)

**Error:**
```
fatal: could not read Username for 'https://github.com': No such device or address
```

**Cause:**
Init containers are trying to clone from:
```bash
http://forgejo.forgejo.svc.cluster.local/ardenone/agent-definitions.git
```

This is a **private Forgejo repository** that requires authentication, but no credentials are provided.

**Why this URL:**
The deployed manifest has a hardcoded git clone command:
```yaml
initContainers:
  - command:
    - git
    - clone
    - --depth=1
    - --branch=main
    - http://forgejo.forgejo.svc.cluster.local/ardenone/agent-definitions.git  # ❌ WRONG
    - /configs/agent-definitions
```

**Expected behavior:**
The manifest in the repo uses environment variables from the `agent-definitions-repos` ConfigMap:
```yaml
env:
  - name: AGENT_DEFINITIONS_REPO_URL
    valueFrom:
      configMapKeyRef:
        name: agent-definitions-repos  # ❌ This ConfigMap is MISSING in cluster
        key: repo-url
```

### Issue 2: ImagePullBackOff (skill-sync, git-sync)

**Error:**
```
Failed to pull image "docker.io/ronaldraygun/botburrow-agents:latest":
pull access denied, repository does not exist or may require authorization
```

**Cause:**
The deployed manifest references the OLD image registry:
- Deployed: `docker.io/ronaldraygun/botburrow-agents:latest` ❌
- Expected: `ghcr.io/botburrow/botburrow-agents:latest` ✅

### Issue 3: Missing ConfigMap

**Missing:**
```
kubectl get configmap agent-definitions-repos -n botburrow-agents
Error from server (NotFound): configmaps "agent-definitions-repos" not found
```

**Cause:**
The `kustomization.yaml` had a `configMapGenerator` section that:
1. Overrode the `botburrow-agents-config` ConfigMap from configmap.yaml
2. Prevented other ConfigMaps in configmap.yaml from being included (agent-definitions-repos, agent-permissions)

**Evidence:**
```yaml
# kustomization.yaml (OLD VERSION - BEFORE FIX)
resources:
  - configmap.yaml  # This includes 3 ConfigMaps

configMapGenerator:
  - name: botburrow-agents-config  # ❌ This OVERRIDES the one in configmap.yaml
    literals:
      - HUB_URL=https://hub.botburrow.internal
      - ...
```

When kustomize runs, the generator **replaces** the entire `botburrow-agents-config` from configmap.yaml, and the other 2 ConfigMaps (agent-definitions-repos, agent-permissions) are ignored.

---

## Fix Applied (Commit d8bf778)

### Changes Made

**File:** `k8s/apexalgo-iad/kustomization.yaml`

**Before:**
```yaml
configMapGenerator:
  - name: botburrow-agents-config
    literals:
      - HUB_URL=https://hub.botburrow.internal
      - REDIS_URL=redis://valkey.botburrow-agents.svc.cluster.local:6379
      # ... 12 more values
```

**After:**
```yaml
# ConfigMaps are defined in configmap.yaml and include:
# - botburrow-agents-config (application configuration)
# - agent-definitions-repos (git repository configuration)
# - agent-permissions (RBAC permissions)
#
# Note: Do NOT use configMapGenerator here as it overrides configmap.yaml
# and prevents agent-definitions-repos from being deployed.
```

### Verification of Fix

**Test 1: Kustomize build produces all 3 ConfigMaps**
```bash
kubectl kustomize k8s/apexalgo-iad/ | grep -c "kind: ConfigMap"
# Output: 3 ✅
```

**Test 2: agent-definitions-repos ConfigMap is present**
```bash
kubectl kustomize k8s/apexalgo-iad/ | grep -A 5 "name: agent-definitions-repos"
# Output:
metadata:
  name: agent-definitions-repos
  namespace: botburrow-agents
data:
  repo-url: "https://github.com/jedarden/agent-definitions.git"
  repo-branch: "main"
  repo-name: "jedarden/agent-definitions"
```

**Test 3: All images use ghcr.io**
```bash
kubectl kustomize k8s/apexalgo-iad/ | grep "image:" | sort | uniq
# Output:
image: alpine/git:latest
image: ghcr.io/botburrow/botburrow-agents:latest  ✅
image: valkey/valkey:8-alpine
```

---

## Deployment Blocked

### Why Deployment Cannot Proceed

**RBAC Constraint:**
- Devpods use `devpod-observer` ServiceAccount
- This ServiceAccount has **read-only** access (intentional security model)
- Cannot create/update Deployments or ConfigMaps

**Evidence:**
```bash
kubectl auth can-i apply deployments -n botburrow-agents
# Output: no
```

**Anti-Pattern:**
Creating a human bead requesting RBAC write access would violate the **GitOps workflow**:
- ❌ Don't request cluster write access from devpod
- ✅ Use GitOps: commit → ArgoCD → deploy
- ✅ Or use kubectl from a cluster-admin machine

### Solution: Human Bead Created

**Bead ID:** bd-l0p
**Title:** HUMAN: Deploy botburrow-agents manifests with kubectl (cluster-admin required)

**Recommended action:**
```bash
cd /home/coder/botburrow-agents
git pull  # Get commit d8bf778
kubectl apply -k k8s/apexalgo-iad/ --context=apexalgo-iad
kubectl get pods -n botburrow-agents  # Verify
```

**Dependencies:**
- bd-32g (this bead) blocked by bd-l0p

---

## Expected Outcome After Deployment

### ConfigMaps
```bash
kubectl get configmaps -n botburrow-agents
# Expected:
NAME                       DATA   AGE
agent-definitions-repos    3      <new>  ✅
agent-permissions          1      50m    ✅
botburrow-agents-config    14     50m    ✅ (updated values)
```

### Pods
```bash
kubectl get pods -n botburrow-agents
# Expected: All Running or ContainerCreating (no CrashLoopBackOff)
NAME                                    READY   STATUS
coordinator-*                           1/1     Running
coordinator-git-sync-*                  2/2     Running
runner-exploration-*                    1/1     Running
runner-git-sync-*                       2/2     Running
runner-hybrid-*                         1/1     Running
runner-notification-*                   1/1     Running
skill-sync-*                            1/1     Running
valkey-*                                1/1     Running
```

### Init Container Logs
```bash
kubectl logs coordinator-* -c git-clone -n botburrow-agents
# Expected:
Cloning into '/configs/agent-definitions'...
remote: Enumerating objects: ...
Receiving objects: 100% (123/123), done.
# ✅ Successful clone from GitHub (not Forgejo)
```

---

## Timeline

1. **2026-02-11 03:23** - Started investigation (bd-32g)
2. **2026-02-11 03:24** - Identified kustomization.yaml configMapGenerator issue
3. **2026-02-11 03:25** - Fixed kustomization.yaml (removed configMapGenerator)
4. **2026-02-11 03:26** - Verified kustomize build produces all 3 ConfigMaps
5. **2026-02-11 03:27** - Committed fix to GitHub (d8bf778)
6. **2026-02-11 03:29** - Created human bead bd-l0p for deployment
7. **2026-02-11 03:29** - Blocked bd-32g on bd-l0p

---

## Related Documentation

- **Workaround Guide:** `k8s/apexalgo-iad/WORKARSUMMARY-argocd-bypass.md`
- **ArgoCD Research:** `docs/research/bd-2z6-argocd-deployment-approaches.md`
- **Deployment Guide:** `DEPLOYMENT-SIMPLIFIED.md`

---

## Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| **Root cause identified** | ✅ | kustomization.yaml configMapGenerator conflict |
| **Fix developed** | ✅ | Removed configMapGenerator |
| **Fix verified** | ✅ | kustomize build produces correct output |
| **Fix committed** | ✅ | Commit d8bf778 |
| **Deployment** | ⏳ | Blocked - awaiting human bd-l0p |
| **Pod verification** | ⏳ | Pending deployment |

**Next Action:** Human with cluster-admin access runs `kubectl apply -k k8s/apexalgo-iad/`

**Estimated time to resolution:** 7 minutes (2 min kubectl apply + 5 min pod startup)

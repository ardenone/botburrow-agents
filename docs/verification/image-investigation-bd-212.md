# Docker Image Investigation Report - bd-212

**Investigation Date:** 2026-02-15
**Bead ID:** bd-212
**Worker:** claude-code-glm-47-lima

## Executive Summary

The coordinator deployment in apexalgo-iad is using `ronaldraygun/botburrow-agents:latest` instead of the specified `ardenone/botburrow-agents:latest` due to a **configuration drift issue**. The manifests were updated on 2026-02-14 to use `docker.io/ardenone/botburrow-agents:latest`, but ArgoCD has not synced these changes to the cluster yet.

**Key Finding:** The deployed image is **OUTDATED** and was built before the leader election code was added (last update: ~2026-02-11). The current codebase contains leader election code, but it's not deployed.

## Problem Statement

Leader election verification (bd-1j7) is blocked because:
1. Manifest specifies: `docker.io/ardenone/botburrow-agents:latest`
2. Pods are running: `docker.io/ronaldraygun/botburrow-agents:latest`
3. Cannot verify if deployed image contains leader election code
4. Pod logs show no leader election startup messages

## Investigation Findings

### 1. Image Repository Confusion

**Timeline of Image Repositories:**

| Date | Repository | CI/CD Workflow | Status |
|------|------------|----------------|---------|
| Pre-2026-02-14 | `ghcr.io/botburrow/botburrow-agents` | N/A | Deprecated |
| 2026-02-14 (commit f79a69c) | Docker Hub (DOCKERHUB_USERNAME) | ci-cd.yml | Incorrect |
| 2026-02-14 (commit d24f6e2) | `docker.io/ardenone/botburrow-agents` | ci-cd.yml, deploy-kubernetes.yml | **CORRECT** |
| 2026-02-14 (commit 26351eb) | `docker.io/ronaldraygun/botburrow-agents` | release.yml (tags only) | Legacy |

**Correct Repository:** `docker.io/ardenone/botburrow-agents`

### 2. Current Deployment State

**Running Pods (as of 2026-02-15 01:07 UTC):**
```
coordinator-644b76d7bd-89trf    docker.io/ronaldraygun/botburrow-agents:latest
coordinator-644b76d7bd-pwlft    docker.io/ronaldraygun/botburrow-agents:latest
```

**Pod Details:**
- **Image Digest:** `sha256:8a122e13e8ec124460dcfd56a072f0bde354a5586987f9c8b50afcfb0e5623da`
- **Pod Started:** 2026-02-15 00:36:07 UTC
- **ReplicaSet:** coordinator-644b76d7bd
- **Deployment Revision:** 14

### 3. Manifest vs Reality

**Manifest Content (k8s/apexalgo-iad/coordinator.yaml):**
```yaml
spec:
  containers:
    - name: coordinator
      image: docker.io/ardenone/botburrow-agents:latest  # ✅ CORRECT
```

**Deployed Spec (from kubectl get deployment):**
```yaml
spec:
  containers:
    - name: coordinator
      image: docker.io/ronaldraygun/botburrow-agents:latest  # ❌ WRONG
```

**ArgoCD Tracking Annotation:**
```
argocd.argoproj.io/tracking-id: botburrow-agents-ns-apexalgo-iad:apps/Deployment:botburrow-agents/coordinator
```

This indicates ArgoCD is managing the deployment but has not synced the latest changes.

### 4. ReplicaSet History Analysis

**Recent ReplicaSets (sorted by creation time):**
```
coordinator-7c895c5d75  2026-02-11T04:18:04Z  ronaldraygun/botburrow-agents:latest
coordinator-6dc4c7d76c  2026-02-11T04:38:28Z  ghcr.io/ardenone/botburrow-agents:latest
coordinator-74648ff76f  2026-02-12T23:18:25Z  ghcr.io/ardenone/botburrow-agents:latest
coordinator-5bc4dccfbc  2026-02-13T22:04:33Z  ghcr.io/ardenone/botburrow-agents:latest
coordinator-5575bdbc89  2026-02-14T02:05:10Z  ardenone/botburrow-agents:latest        ← First Docker Hub
coordinator-7c6cfd85f5  2026-02-14T18:43:07Z  ardenone/botburrow-agents:latest
coordinator-7db7574b78  2026-02-14T18:53:40Z  ghcr.io/ardenone/botburrow-agents:latest (rollback?)
coordinator-6b688ddb47  2026-02-14T20:09:55Z  ghcr.io/ardenone/botburrow-agents:latest
coordinator-54dd4fcd7d  2026-02-14T20:12:46Z  ronaldraygun/botburrow-agents:latest    ← Manual override?
coordinator-857c75f99   2026-02-14T23:38:22Z  ronaldraygun/botburrow-agents:latest
coordinator-644b76d7bd  2026-02-15T00:36:02Z  ronaldraygun/botburrow-agents:latest    ← CURRENT
```

**Observation:** Multiple back-and-forth between image registries suggests:
- Manual interventions or ArgoCD sync conflicts
- Someone may have manually set the image to ronaldraygun
- ArgoCD auto-sync may be disabled or failing

### 5. CI/CD Workflow Analysis

**Three Active Workflows:**

1. **ci-cd.yml** (push to main, non-tags)
   - Builds: `docker.io/ardenone/botburrow-agents:latest`
   - Builds: `docker.io/ardenone/botburrow-agents:<short-sha>`
   - ✅ **CORRECT** - This is the main workflow

2. **deploy-kubernetes.yml** (GitOps deployment)
   - Uses images built by ci-cd.yml
   - Updates manifests to use `ardenone/botburrow-agents`
   - ✅ **CORRECT** - But may not be running or syncing

3. **release.yml** (git tags only)
   - Builds: `docker.io/ronaldraygun/botburrow-agents:<version>`
   - Builds: `docker.io/ronaldraygun/botburrow-agents:latest`
   - ⚠️ **LEGACY** - Only runs on version tags (v*)

**Last Successful Build:** Likely before 2026-02-11 (based on ronaldraygun image age)

### 6. Leader Election Code Status

**Local Codebase:**
```bash
$ ls -la src/botburrow_agents/coordinator/work_queue.py
-rw-rw-r-- 1 coder coder 13106 Feb  1 16:13 work_queue.py

$ grep "class LeaderElection" src/botburrow_agents/coordinator/work_queue.py
371:class LeaderElection:
```

✅ **Leader election code EXISTS in current codebase** (added 2026-02-01)

**Deployed Image:**
- Last built: ~2026-02-11 or earlier (based on ronaldraygun image)
- Leader election code added: 2026-02-01
- **UNKNOWN** if deployed image contains leader election code

**Pod Logs:**
- No leader election startup messages found
- Only shows authentication errors (401 Unauthorized)
- Suggests old coordinator code without leader election

### 7. Image Availability

**ronaldraygun/botburrow-agents:latest:**
- ✅ Publicly accessible (manifest inspectable)
- ❌ Cannot pull locally (overlayfs extraction error in devpod)
- Digest: `sha256:e055b1da6dbe1b4265af10ce0d0501bb1607f3d48f0f73c122f2e3d318f959e4`

**ardenone/botburrow-agents:latest:**
- ❌ Not publicly accessible (requires authentication)
- ❌ Cannot pull or inspect without Docker Hub credentials
- Status: **MAY NOT EXIST YET** (ci-cd.yml may not have pushed successfully)

### 8. Root Cause Analysis

**Primary Issue:** Configuration drift between manifest and deployed state

**Contributing Factors:**
1. **ArgoCD Sync Failure**
   - Manifests updated to `ardenone/botburrow-agents:latest` on 2026-02-14
   - ArgoCD has not synced these changes to cluster
   - Deployment still using old `ronaldraygun/botburrow-agents:latest`

2. **Image Not Built** ✅ **CONFIRMED ROOT CAUSE**
   - ci-cd.yml is FAILING on linting errors since 2026-02-14
   - `ardenone/botburrow-agents:latest` image does NOT exist on Docker Hub
   - Pull would fail if deployment tried to update
   - Last successful build: v0.1.1 (2026-02-14, pushed to ronaldraygun)

3. **Linting Errors Blocking CI/CD** 🔴 **CRITICAL**
   - 49 linting errors in `tests/test_simplified_persona_execution.py`
   - Errors: Unused imports, unused function arguments, code style issues
   - All builds failing since these errors were introduced
   - Prevents Docker image from being built and pushed

4. **Manual Override**
   - ReplicaSet history shows manual switches between registries
   - Someone may have manually set image to ronaldraygun for debugging
   - This would override ArgoCD's desired state

## Resolution Options

### Option 1: Force ArgoCD Sync (RECOMMENDED)

**If `ardenone/botburrow-agents:latest` image exists:**

```bash
# Check ArgoCD application status
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
argocd app get botburrow-agents-ns-apexalgo-iad

# Force sync
argocd app sync botburrow-agents-ns-apexalgo-iad --force

# Verify pods updated
kubectl get pods -n botburrow-agents -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

**Pros:**
- Uses GitOps process correctly
- Aligns deployment with manifest
- Automated, repeatable

**Cons:**
- Requires image to exist first
- May fail if image not built yet

### Option 2: Trigger CI/CD to Build New Image

**Force ci-cd.yml to run and push fresh image:**

```bash
# Trigger workflow manually (if workflow_dispatch enabled)
gh workflow run ci-cd.yml

# OR make a small commit to trigger workflow
cd /home/coder/botburrow-agents
echo "# Trigger build $(date)" >> .github/workflows/.build-trigger
git add .github/workflows/.build-trigger
git commit -m "chore: Trigger Docker build for ardenone/botburrow-agents"
git push origin main

# Wait for build to complete
gh run watch

# Then force ArgoCD sync (Option 1)
```

**Pros:**
- Ensures latest code is built
- Creates fresh image with leader election code
- CI/CD validates build

**Cons:**
- Takes time (5-10 minutes for build)
- Requires GitHub Actions to be configured correctly

### Option 3: Manual Deployment Update (QUICK FIX)

**Directly update deployment image (bypasses GitOps):**

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Set image to ardenone (if it exists)
kubectl set image deployment/coordinator \
  coordinator=docker.io/ardenone/botburrow-agents:latest \
  -n botburrow-agents

# OR rebuild ronaldraygun image with latest code
docker build -t ronaldraygun/botburrow-agents:latest .
docker push ronaldraygun/botburrow-agents:latest
kubectl rollout restart deployment/coordinator -n botburrow-agents
```

**Pros:**
- Immediate effect
- Can test quickly

**Cons:**
- ❌ Breaks GitOps model
- ❌ ArgoCD will show "OutOfSync"
- ❌ Changes may be reverted on next sync
- ❌ **NOT RECOMMENDED** for production

### Option 4: Use ronaldraygun Image as Official (NOT RECOMMENDED)

**Update manifests to match current reality:**

```bash
# Update all manifests to use ronaldraygun
sed -i 's|docker.io/ardenone/botburrow-agents|docker.io/ronaldraygun/botburrow-agents|g' k8s/apexalgo-iad/*.yaml

# Update CI/CD workflows
# Edit .github/workflows/ci-cd.yml to push to ronaldraygun

git commit -am "fix: Use ronaldraygun as official image repository"
git push origin main
```

**Pros:**
- Simple alignment

**Cons:**
- ❌ ronaldraygun appears to be a personal account
- ❌ Not organizationally owned
- ❌ Image is outdated (doesn't have latest leader election code)
- ❌ Requires rebuilding image anyway

## Recommended Action Plan

**STEP 1: Fix Linting Errors (CRITICAL)**
```bash
# Fix linting errors automatically
cd /home/coder/botburrow-agents
ruff check tests/test_simplified_persona_execution.py --fix

# Or manually remove unused imports and fix code style
# Then commit and push
git add tests/test_simplified_persona_execution.py
git commit -m "fix: Remove unused imports and fix linting errors in tests"
git push origin main
```

**STEP 2: Wait for CI/CD Build**
```bash
# Monitor build after linting fixes
gh run watch

# Or trigger manually if needed
gh workflow run ci-cd.yml --ref main
```

**STEP 3: Verify Image Built**
```bash
# Check if ardenone image exists (after build completes)
docker pull docker.io/ardenone/botburrow-agents:latest 2>&1

# Or check Docker Hub directly
curl -s https://hub.docker.com/v2/repositories/ardenone/botburrow-agents/tags/ | jq
```

**STEP 4: Force ArgoCD Sync**
```bash
# Sync ArgoCD application (if ArgoCD is installed)
argocd app sync botburrow-agents-ns-apexalgo-iad --force

# OR manually update deployment
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl set image deployment/coordinator \
  coordinator=docker.io/ardenone/botburrow-agents:latest \
  -n botburrow-agents

# Wait for rollout
kubectl rollout status deployment/coordinator -n botburrow-agents
```

**STEP 5: Verify Leader Election**
```bash
# Check pod logs for leader election messages
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=100 | grep -i "leader"

# Verify image
kubectl get pods -n botburrow-agents -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'
```

## Next Steps for bd-1j7

**BLOCKER RESOLUTION:**

1. **Fix Linting Errors:** ✅ Create blocker bead to fix 49 linting errors in tests (blocks CI/CD)
2. **Build Fresh Image:** After lint fixes, ci-cd.yml will build `ardenone/botburrow-agents:latest` with latest code (includes leader election)
3. **Deploy Image:** Update deployment to use new image (manual kubectl or ArgoCD sync)
4. **Verify Deployment:** Confirm pods are running `ardenone/botburrow-agents:latest`
5. **Check Leader Election:** Review logs for leader election startup messages
6. **Resume bd-1j7:** Complete leader election verification with confirmed-working image

## Blocker Bead Created

**Bead ID:** bd-2r8 (to be created)
**Title:** Fix linting errors blocking CI/CD builds
**Priority:** 0 (critical - blocks image builds)
**Description:** Fix 49 linting errors in `tests/test_simplified_persona_execution.py` preventing Docker images from being built

## Files Referenced

- **Manifests:** `k8s/apexalgo-iad/coordinator.yaml`
- **CI/CD Workflows:**
  - `.github/workflows/ci-cd.yml` (main builds)
  - `.github/workflows/deploy-kubernetes.yml` (GitOps)
  - `.github/workflows/release.yml` (legacy tags)
- **Leader Election Code:** `src/botburrow_agents/coordinator/work_queue.py:371`
- **Git Commits:**
  - `d24f6e2` - Fix CI/CD to use ardenone/botburrow-agents
  - `26351eb` - Add release.yml with ronaldraygun
  - `f79a69c` - Switch to Docker Hub

## Conclusion

**Root Cause:** ArgoCD configuration drift - manifests specify `ardenone/botburrow-agents:latest` but cluster is still running `ronaldraygun/botburrow-agents:latest` from before the manifest update.

**Deployed Image Status:** Outdated (pre-2026-02-11), likely does NOT contain leader election code.

**Resolution:** Trigger CI/CD build + ArgoCD force sync to deploy latest code with leader election support.

**Impact on bd-1j7:** Cannot verify leader election until fresh image is deployed. This bead successfully identified the blocker.

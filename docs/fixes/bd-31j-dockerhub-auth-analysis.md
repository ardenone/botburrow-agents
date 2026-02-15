# Docker Hub Authentication Failure Analysis - bd-31j

**Date:** 2026-02-15
**Worker:** claude-code-glm-47-lima
**Bead:** bd-31j

## Problem Statement

CI/CD workflow fails when attempting to push Docker images to Docker Hub with error:

```
ERROR: failed to push docker.io/ardenone/botburrow-agents:8b7b76d:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

## Root Cause Analysis

### Evidence
1. **GitHub Secrets Configured:** ✅
   - `DOCKERHUB_USERNAME` exists (set 2026-02-02)
   - `DOCKERHUB_PASSWORD` exists (set 2026-02-02)

2. **Authentication Attempt:** ✅
   - Workflow successfully authenticates to Docker Hub
   - `docker/login-action@v3` completes without error

3. **Push Failure:** ❌
   - Error message: `insufficient_scope: authorization failed`
   - Occurs during `docker/build-push-action@v5` push step

### Root Cause
The `DOCKERHUB_PASSWORD` secret likely contains a **regular account password** instead of a **Personal Access Token (PAT)** with write permissions.

**Why this fails:**
- Docker Hub deprecated password authentication for automated systems in 2020
- Regular passwords have limited API scope, blocking push operations
- Personal Access Tokens (PATs) are required for CI/CD push access
- Even if password works for login, it lacks `repository:write` scope for push

## Resolution Options

### Option 1: Update GitHub Secret with Docker Hub PAT ✅ RECOMMENDED

**Pros:**
- Simple fix - only requires updating one GitHub secret
- No code changes needed
- Maintains existing workflow structure
- Uses Docker Hub's recommended authentication method
- Allows granular permission control via PAT scopes

**Cons:**
- Requires access to Docker Hub account (`ardenone`)
- Requires access to GitHub repository settings
- PAT needs manual rotation/management

**Implementation Steps:**
1. **Create Docker Hub Personal Access Token:**
   - Log in to Docker Hub as `ardenone`
   - Navigate to Account Settings → Security → Access Tokens
   - Click "New Access Token"
   - Name: `github-actions-botburrow-agents`
   - Permissions: `Read, Write, Delete` (or `Read & Write` minimum)
   - Copy the generated token (shown only once!)

2. **Ensure Docker Hub Repository Exists:**
   - Go to https://hub.docker.com/u/ardenone
   - Check if `ardenone/botburrow-agents` repository exists
   - If not, create it:
     - Click "Create Repository"
     - Name: `botburrow-agents`
     - Visibility: Public (recommended) or Private
     - Click "Create"

3. **Update GitHub Secret:**
   - Go to https://github.com/ardenone/botburrow-agents/settings/secrets/actions
   - Click on `DOCKERHUB_PASSWORD` → "Update secret"
   - Paste the new PAT token
   - Click "Update secret"

4. **Verify GitHub Secret (Already Correct):**
   - `DOCKERHUB_USERNAME` should be: `ardenone` ✅

5. **Trigger Workflow:**
   - Push a commit to main branch
   - Or manually trigger via GitHub Actions UI
   - Monitor build job: https://github.com/ardenone/botburrow-agents/actions

**Expected Result:**
- Docker build completes successfully
- Images pushed to `docker.io/ardenone/botburrow-agents:latest` and `docker.io/ardenone/botburrow-agents:<sha>`

---

### Option 2: Switch to GitHub Container Registry (GHCR)

**Pros:**
- No external account management (uses GitHub)
- Automatic authentication via `GITHUB_TOKEN`
- Better integration with GitHub repos
- Higher rate limits for public images
- No need for separate secrets management

**Cons:**
- Requires workflow modifications
- Changes image registry URL (affects deployments)
- May require updating Kubernetes manifests
- Migration effort if existing images are in Docker Hub

**Implementation Steps:**
1. **Update `.github/workflows/ci-cd.yml`:**

```yaml
# BEFORE (lines 71-75):
- name: Log in to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKERHUB_USERNAME }}
    password: ${{ secrets.DOCKERHUB_PASSWORD }}

# AFTER:
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

2. **Update image tags (lines 90-92):**

```yaml
# BEFORE:
tags: |
  docker.io/ardenone/${{ env.IMAGE_NAME }}:${{ steps.version.outputs.tag }}
  docker.io/ardenone/${{ env.IMAGE_NAME }}:latest

# AFTER:
tags: |
  ghcr.io/ardenone/${{ env.IMAGE_NAME }}:${{ steps.version.outputs.tag }}
  ghcr.io/ardenone/${{ env.IMAGE_NAME }}:latest
```

3. **Update Kubernetes manifests** (if applicable):
   - Search for `docker.io/ardenone/botburrow-agents`
   - Replace with `ghcr.io/ardenone/botburrow-agents`

4. **Set GHCR visibility** (one-time):
   - Go to https://github.com/ardenone/botburrow-agents/pkgs/container/botburrow-agents/settings
   - Set visibility to Public (if desired)

---

### Option 3: Use Private Container Registry

**Pros:**
- Full control over registry infrastructure
- Can use cluster-local registry (faster pulls)
- No external dependencies
- Custom retention policies

**Cons:**
- Requires infrastructure setup and maintenance
- Additional operational overhead
- Storage costs
- Requires authentication management

**Implementation:** (Not recommended for this use case - overkill)

---

## Recommended Approach

**Primary Recommendation: Option 1** - Update GitHub secret with Docker Hub PAT

**Reasoning:**
1. Minimal changes - only updates one secret
2. Workflow already designed for Docker Hub
3. No code changes required
4. Quick resolution (5-10 minutes)
5. Aligns with Docker Hub's recommended practices

**Fallback: Option 2** - If Docker Hub access is unavailable or PAT creation is blocked, migrate to GHCR.

---

## Testing Plan

### After Implementing Option 1:
```bash
# 1. Trigger workflow manually
gh workflow run ci-cd.yml

# 2. Monitor workflow
gh run watch

# 3. Check Docker Hub for images
# Visit: https://hub.docker.com/r/ardenone/botburrow-agents/tags

# 4. Pull image locally to verify
docker pull ardenone/botburrow-agents:latest
docker inspect ardenone/botburrow-agents:latest
```

### After Implementing Option 2 (GHCR):
```bash
# 1. Trigger workflow
gh workflow run ci-cd.yml

# 2. Monitor workflow
gh run watch

# 3. Check GHCR for images
# Visit: https://github.com/ardenone/botburrow-agents/pkgs/container/botburrow-agents

# 4. Pull image locally
docker pull ghcr.io/ardenone/botburrow-agents:latest
docker inspect ghcr.io/ardenone/botburrow-agents:latest
```

---

## Human Action Required

This issue requires **HUMAN intervention** because:
1. Access to Docker Hub account (`ardenone`) is needed to create PAT
2. Access to GitHub repository settings is needed to update secrets
3. Decision between Option 1 (Docker Hub PAT) vs Option 2 (GHCR migration)

**No worker can complete this autonomously** - manual credential management required.

---

## Related Beads
- **bd-x11** - Fix linting errors blocking CI/CD builds (depends on this)
- **bd-212** - Image investigation (depends on this)
- **bd-1j7** - Leader election verification (depends on this)

---

## Workflow References
- Workflow file: `.github/workflows/ci-cd.yml`
- Failed run: https://github.com/ardenone/botburrow-agents/actions/runs/22040749901
- Docker Hub docs: https://docs.docker.com/security/for-developers/access-tokens/
- GHCR docs: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry

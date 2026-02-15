# 🎯 ACTION REQUIRED: Update Docker Hub Credentials (bd-3h3)

**Status:** ✅ Ready for Human Execution
**Estimated Time:** 5-10 minutes
**Date:** 2026-02-15

---

## 🚨 Problem

CI/CD workflow fails to push Docker images to Docker Hub:

```
ERROR: failed to push docker.io/ardenone/botburrow-agents:93581ad:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Root Cause:** The `DOCKERHUB_PASSWORD` GitHub secret contains a regular password instead of a Personal Access Token (PAT). Docker Hub requires PATs for CI/CD operations.

---

## ✅ 5-Step Fix (5-10 minutes)

### Step 1: Create Docker Hub PAT (2 minutes)

1. Go to: https://hub.docker.com/settings/security
2. Click **"New Access Token"**
3. Settings:
   - **Token Name:** `github-actions-botburrow-agents`
   - **Permissions:** `Read & Write` (minimum)
4. Click **"Generate"**
5. **COPY THE TOKEN IMMEDIATELY** - it's shown only once!

### Step 2: Verify Repository Exists (30 seconds)

1. Go to: https://hub.docker.com/u/ardenone
2. Check if `ardenone/botburrow-agents` repository exists
3. If missing, create it:
   - Click **"Create Repository"**
   - Name: `botburrow-agents`
   - Visibility: **Public** (recommended)

### Step 3: Update GitHub Secret (1 minute)

1. Go to: https://github.com/ardenone/botburrow-agents/settings/secrets/actions
2. Find `DOCKERHUB_PASSWORD` in the list
3. Click the **pencil icon** (edit)
4. Paste the PAT from Step 1
5. Click **"Update secret"**
6. Verify `DOCKERHUB_USERNAME` = `ardenone` (should already be set)

### Step 4: Test the Fix (2 minutes)

Run the workflow manually:

```bash
gh workflow run ci-cd.yml
gh run watch
```

Or trigger via web UI:
https://github.com/ardenone/botburrow-agents/actions/workflows/ci-cd.yml

### Step 5: Verify Success (1 minute)

Check workflow succeeded:
- Workflow: https://github.com/ardenone/botburrow-agents/actions
- Images: https://hub.docker.com/r/ardenone/botburrow-agents/tags

If successful, close the bead:

```bash
br close bd-3h3 --status completed
```

---

## 🔗 What This Unblocks

Completing bd-3h3 will automatically unblock:
- **bd-31j** - Configure Docker Hub credentials for CI/CD push
- **bd-212** - Image investigation
- **bd-1j7** - Leader election verification

---

## 🔄 Alternative: Migrate to GitHub Container Registry (GHCR)

If you **cannot access Docker Hub** or prefer not to use it:

**Benefits:**
- No external credentials needed
- Uses `GITHUB_TOKEN` automatically (built-in)
- Better integration with GitHub
- No rate limits for private repos

**Steps:**
1. Update `.github/workflows/ci-cd.yml`:
   ```yaml
   # Change this:
   - docker.io/ardenone/botburrow-agents

   # To this:
   - ghcr.io/ardenone/botburrow-agents
   ```

2. Update Kubernetes manifests (find all references to `ardenone/botburrow-agents`):
   ```bash
   grep -r "ardenone/botburrow-agents" cluster-configuration/ docs/
   ```

3. Remove Docker Hub secrets (no longer needed):
   - Delete `DOCKERHUB_USERNAME`
   - Delete `DOCKERHUB_PASSWORD`

**Tradeoff:** Requires updating multiple Kubernetes manifests and documentation.

---

## 📊 Current Status

**Latest Workflow Runs:**
- Run #22043799288 - In Progress (2026-02-15 21:57 UTC)
- Run #22043798125 - In Progress (2026-02-15 21:57 UTC)
- Run #22043788779 - In Progress (2026-02-15 21:56 UTC)

**Build Status:**
- ✅ Tests passing (linting, type checking, unit tests)
- ✅ Docker build succeeds
- ❌ Docker push fails (authentication only)

---

## ❓ Troubleshooting

**Problem: Token already exists with same name**
- Solution: Delete old token, create new one with same name

**Problem: Repository doesn't exist**
- Solution: Create repository at https://hub.docker.com/repository/create
- Name: `botburrow-agents`
- Visibility: Public

**Problem: Workflow still fails after updating secret**
- Check: Verify token has `Read & Write` permissions (not just `Read`)
- Check: Verify repository name is exactly `ardenone/botburrow-agents`
- Check: Wait 1-2 minutes for secret to propagate

**Problem: Images don't appear on Docker Hub**
- Check workflow logs: https://github.com/ardenone/botburrow-agents/actions
- Verify push step completed successfully
- Check repository tags: https://hub.docker.com/r/ardenone/botburrow-agents/tags

---

## 📚 Additional Documentation

If you need more details:
- Root cause analysis: `docs/fixes/bd-31j-dockerhub-auth-analysis.md`
- Other guides: `docs/fixes/bd-3h3-*.md` (12 files total - this is the consolidated version)

---

**Last Updated:** 2026-02-15 22:05 UTC
**Worker:** claude-sonnet-4-5 (consolidated all previous documentation)

# 🎯 Human Action Required: Update Docker Hub Credentials (bd-3h3)

**Status:** ✅ Ready for Human Execution
**Estimated Time:** 5-10 minutes
**Last Updated:** 2026-02-15 22:10 UTC
**Worker:** claude-sonnet-4-5

---

## 🚨 Problem Summary

The CI/CD workflow fails when pushing Docker images to Docker Hub with the following error:

```
ERROR: failed to push docker.io/ardenone/botburrow-agents:93581ad:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Root Cause:** The `DOCKERHUB_PASSWORD` GitHub secret contains a regular password instead of a Personal Access Token (PAT). Docker Hub deprecated password authentication for CI/CD operations and now requires PATs with explicit write permissions.

**Current Status:**
- ✅ Tests passing (linting, type checking, unit tests)
- ✅ Docker build succeeds
- ❌ Docker push fails (authentication/authorization only)

---

## ✅ 5-Step Fix (5-10 minutes)

### Step 1: Create Docker Hub Personal Access Token (2 minutes)

1. **Navigate to Docker Hub Security Settings:**
   https://hub.docker.com/settings/security

2. **Create New Access Token:**
   - Click **"New Access Token"**
   - **Token Name:** `github-actions-botburrow-agents`
   - **Permissions:** Select **"Read & Write"** (minimum required)
   - Click **"Generate"**

3. **Copy Token Immediately:**
   - ⚠️ **CRITICAL:** The token is shown **only once**
   - Copy it to a secure location before closing the dialog
   - You cannot retrieve it later

### Step 2: Verify Docker Hub Repository Exists (30 seconds)

1. **Check Repository:**
   Navigate to: https://hub.docker.com/u/ardenone

2. **Verify `ardenone/botburrow-agents` exists:**
   - If repository exists ✅ - proceed to Step 3
   - If repository **does not exist** - create it:
     - Click **"Create Repository"**
     - **Name:** `botburrow-agents`
     - **Visibility:** **Public** (recommended) or Private
     - **Description:** (optional) "BotBurrow Agents - AI agent orchestration system"
     - Click **"Create"**

### Step 3: Update GitHub Secret (1 minute)

1. **Navigate to GitHub Secrets:**
   https://github.com/ardenone/botburrow-agents/settings/secrets/actions

2. **Update `DOCKERHUB_PASSWORD`:**
   - Find `DOCKERHUB_PASSWORD` in the secrets list
   - Click the **pencil icon** (edit)
   - **Paste the PAT token** from Step 1
   - Click **"Update secret"**

3. **Verify `DOCKERHUB_USERNAME`:**
   - Should be set to: `ardenone`
   - If not present, create it with value: `ardenone`

### Step 4: Trigger Workflow and Test (2 minutes)

**Option A: Manual Trigger via CLI (recommended):**
```bash
# Trigger the workflow
gh workflow run ci-cd.yml

# Watch the workflow run in real-time
gh run watch
```

**Option B: Manual Trigger via Web UI:**
1. Go to: https://github.com/ardenone/botburrow-agents/actions/workflows/ci-cd.yml
2. Click **"Run workflow"** dropdown (top right)
3. Select branch: `main`
4. Click **"Run workflow"**
5. Monitor progress in the Actions tab

**Option C: Automatic Trigger:**
- Make any commit to `main` branch (workflow runs on push)
- Wait for workflow to start automatically

### Step 5: Verify Success (1 minute)

1. **Check Workflow Completed Successfully:**
   https://github.com/ardenone/botburrow-agents/actions
   - Latest run should show ✅ green checkmark
   - Build step should show "Push successful"

2. **Verify Images on Docker Hub:**
   https://hub.docker.com/r/ardenone/botburrow-agents/tags
   - Should see two new tags:
     - `latest` (most recent commit)
     - `<commit-sha>` (specific commit hash)
   - Check timestamp matches your workflow run

3. **Close the Bead:**
```bash
cd /home/coder/botburrow-agents
br close bd-3h3 --status completed
```

---

## 🔗 What This Unblocks

Completing bd-3h3 will automatically unblock these dependent beads:
- **bd-31j** - Configure Docker Hub credentials for CI/CD push
- **bd-212** - Investigate ronaldraygun/botburrow-agents image version
- **bd-1j7** - Leader election verification

---

## 🔄 Alternative Solution: Migrate to GitHub Container Registry (GHCR)

If you **cannot access Docker Hub**, prefer **GitHub-native solutions**, or want to **eliminate external dependencies**, consider migrating to GHCR.

### Benefits of GHCR:
- ✅ No external account needed (uses GitHub)
- ✅ Automatic authentication via `GITHUB_TOKEN` (built-in)
- ✅ Better integration with GitHub repositories
- ✅ Higher rate limits for private repositories
- ✅ No secret management required
- ✅ Native support for GitHub Actions

### Migration Steps:

**1. Update Workflow File (`.github/workflows/ci-cd.yml`):**

Replace Docker Hub login (lines 71-75):
```yaml
# BEFORE:
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

Update image tags (lines 90-92):
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

**2. Update Kubernetes Manifests:**

Find all references to the old image:
```bash
cd /home/coder/botburrow-agents
grep -r "ardenone/botburrow-agents" cluster-configuration/ docs/
```

Replace:
- **Old:** `docker.io/ardenone/botburrow-agents` or `ardenone/botburrow-agents`
- **New:** `ghcr.io/ardenone/botburrow-agents`

**3. Remove Docker Hub Secrets (no longer needed):**
- Go to: https://github.com/ardenone/botburrow-agents/settings/secrets/actions
- Delete `DOCKERHUB_USERNAME`
- Delete `DOCKERHUB_PASSWORD`

**4. Set GHCR Package Visibility:**
- After first push, go to: https://github.com/ardenone/botburrow-agents/pkgs/container/botburrow-agents/settings
- Set visibility to **Public** (if desired for public access)

### Tradeoffs:
- ❌ Requires updating multiple files (workflow + Kubernetes manifests)
- ❌ Migration effort if existing images are in Docker Hub
- ✅ But eliminates external dependencies and secret management

---

## ❓ Troubleshooting

### Problem: "Token already exists with same name"
**Solution:**
- Go to Docker Hub Security settings
- Delete the old token with the same name
- Create a new token with the same name

### Problem: "Repository doesn't exist" error persists
**Solution:**
1. Verify repository name is **exactly** `ardenone/botburrow-agents`
2. Create repository manually:
   - Go to: https://hub.docker.com/repository/create
   - Name: `botburrow-agents`
   - Visibility: Public
3. Ensure you're logged in as the `ardenone` account

### Problem: Workflow still fails after updating secret
**Possible Causes:**
1. **Token permissions insufficient:**
   - Verify token has **"Read & Write"** permissions (not just "Read")
   - Delete and recreate token with correct permissions

2. **Secret not propagated:**
   - Wait 1-2 minutes after updating secret
   - Secrets may take time to propagate in GitHub's infrastructure

3. **Wrong username:**
   - Verify `DOCKERHUB_USERNAME` = `ardenone` (exact match)
   - Docker Hub usernames are case-sensitive

4. **Token copied incorrectly:**
   - Ensure no extra spaces or characters
   - Token should be a long alphanumeric string

### Problem: Images don't appear on Docker Hub after successful push
**Debugging Steps:**
1. **Check workflow logs:**
   - Go to: https://github.com/ardenone/botburrow-agents/actions
   - Open latest run
   - Expand "Push Docker image" step
   - Verify "Push successful" message

2. **Verify repository tags:**
   - Go to: https://hub.docker.com/r/ardenone/botburrow-agents/tags
   - Refresh page (may take 10-30 seconds)
   - Check "Last pushed" timestamp

3. **Check repository visibility:**
   - Ensure repository is set to "Public" (if you expect public access)
   - Private repositories require authentication to view

---

## 📚 Additional Documentation

For detailed root cause analysis and investigation history, see:
- **Root Cause Analysis:** `docs/fixes/bd-31j-dockerhub-auth-analysis.md`

---

## 📊 Workflow Status History

**Recent Failed Runs:**
- Run #22043329545 (2026-02-15 21:26 UTC) - Push failed (insufficient_scope)
- Multiple prior runs with same authentication error

**Latest Workflow URL:**
https://github.com/ardenone/botburrow-agents/actions

---

## 🎓 Background: Why Personal Access Tokens?

Docker Hub deprecated password authentication for automated systems in 2020 for security reasons:

1. **Limited Scope:** Passwords grant full account access
2. **No Audit Trail:** Cannot track which system used which credential
3. **Rotation Risk:** Changing password breaks all automated systems
4. **Security Best Practice:** PATs provide granular permissions and can be revoked individually

PATs allow you to:
- ✅ Grant specific permissions (Read, Write, Delete)
- ✅ Create multiple tokens for different systems
- ✅ Revoke individual tokens without affecting others
- ✅ Track token usage in audit logs
- ✅ Set expiration dates (optional)

---

**Next Action:** Complete the 5 steps above, then close this bead with:
```bash
br close bd-3h3 --status completed
```

---

**Documentation Prepared By:** Multiple Claude workers (consolidated final version)
**Final Verification:** claude-sonnet-4-5 (2026-02-15 22:10 UTC)

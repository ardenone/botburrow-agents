# Docker Hub PAT Update Guide (bd-3h3)

## Status: REQUIRES HUMAN ACTION

**Created:** 2026-02-15
**Bead ID:** bd-3h3
**Blocked Beads:** bd-31j, bd-x11, bd-212, bd-1j7

## Problem Summary
CI/CD workflow fails to push Docker images due to authentication error:
```
ERROR: push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Root Cause:** `DOCKERHUB_PASSWORD` secret likely contains a regular password instead of a Personal Access Token (PAT), which Docker Hub requires for automated operations.

## ✅ Step-by-Step Resolution (RECOMMENDED: Option 1)

### Step 1: Create Docker Hub Personal Access Token

1. **Log in to Docker Hub:**
   - Navigate to: https://hub.docker.com/settings/security
   - Sign in with your `ardenone` account credentials

2. **Create New Access Token:**
   - Click **"New Access Token"** button
   - Fill in details:
     - **Access Token Description:** `github-actions-botburrow-agents`
     - **Access permissions:** `Read & Write` (minimum required)
   - Click **"Generate"**

3. **CRITICAL: Copy Token Immediately**
   - Token is shown **ONLY ONCE**
   - Copy it to a secure temporary location (password manager, secure note)
   - Format: `dckr_pat_XXXXXXXXXXXXXXXXXXXX`

### Step 2: Verify Repository Exists

1. **Check if repository exists:**
   - Navigate to: https://hub.docker.com/u/ardenone
   - Look for `botburrow-agents` repository

2. **If repository does NOT exist:**
   - Click **"Create Repository"**
   - Repository Name: `botburrow-agents`
   - Visibility: **Public** (recommended for open-source)
   - Description: `BotBurrow Agents - Autonomous agent system`
   - Click **"Create"**

### Step 3: Update GitHub Secret

1. **Navigate to GitHub Repository Secrets:**
   - Go to: https://github.com/ardenone/botburrow-agents/settings/secrets/actions
   - (Or: Repository → Settings → Secrets and variables → Actions)

2. **Update DOCKERHUB_PASSWORD Secret:**
   - Find `DOCKERHUB_PASSWORD` in the list
   - Click the **pencil icon** (Update) next to it
   - Paste the PAT token from Step 1
   - Click **"Update secret"**

3. **Verify DOCKERHUB_USERNAME:**
   - Find `DOCKERHUB_USERNAME` in the list
   - It should contain: `ardenone`
   - If incorrect, update it

### Step 4: Test the Fix

**Option A: Manual Workflow Trigger**
```bash
# From your local machine or devpod
gh workflow run ci-cd.yml
gh run watch
```

**Option B: Push a Commit**
```bash
cd /home/coder/botburrow-agents
git commit --allow-empty -m "test: trigger Docker Hub push with new PAT

Co-Authored-By: Claude Worker <noreply@anthropic.com>"
git push origin main
```

**Option C: Via GitHub UI**
- Go to: https://github.com/ardenone/botburrow-agents/actions/workflows/ci-cd.yml
- Click **"Run workflow"** → **"Run workflow"**

### Step 5: Verify Success

1. **Check Workflow Status:**
   - Navigate to: https://github.com/ardenone/botburrow-agents/actions
   - Find the latest "Build and Deploy" run
   - Verify "Build Docker Images" job completes successfully
   - Look for output: `Successfully pushed docker.io/ardenone/botburrow-agents:XXXXXXX`

2. **Verify Image on Docker Hub:**
   - Go to: https://hub.docker.com/r/ardenone/botburrow-agents/tags
   - Confirm you see:
     - Tag: `latest`
     - Tag: `<commit-sha>` (e.g., `8b7b76d`)
     - Recent push timestamp

3. **Test Pull (Optional):**
   ```bash
   docker pull ardenone/botburrow-agents:latest
   docker images | grep botburrow-agents
   ```

## Success Criteria ✅

- [ ] Docker Hub PAT created with Read & Write permissions
- [ ] `ardenone/botburrow-agents` repository exists on Docker Hub
- [ ] `DOCKERHUB_PASSWORD` GitHub secret updated with PAT
- [ ] CI/CD workflow runs successfully
- [ ] Docker images pushed to Docker Hub
- [ ] Images visible at https://hub.docker.com/r/ardenone/botburrow-agents/tags

## Alternative: Option 2 - Migrate to GitHub Container Registry (GHCR)

If you **cannot access Docker Hub** or prefer GitHub-native solution:

### Pros:
- No external account management
- Uses `GITHUB_TOKEN` (automatic authentication)
- Better GitHub integration
- Higher rate limits

### Cons:
- Requires workflow modifications
- Changes image URLs (affects deployments)

### Implementation:
See detailed steps in `docs/fixes/bd-31j-dockerhub-auth-analysis.md` → "Option 2: Migrate to GHCR"

**Key Changes Required:**
1. Update `.github/workflows/ci-cd.yml` to use `ghcr.io/ardenone/botburrow-agents`
2. Update Kubernetes manifests to reference new image URL
3. No secrets management needed (uses `GITHUB_TOKEN`)

## Troubleshooting

### Issue: "Token authentication failed"
**Cause:** Token was copied incorrectly or expired
**Fix:** Regenerate PAT and update secret again

### Issue: "Repository does not exist"
**Cause:** `ardenone/botburrow-agents` not created on Docker Hub
**Fix:** Create repository (Step 2 above)

### Issue: "Insufficient permissions"
**Cause:** PAT created with `Read-only` instead of `Read & Write`
**Fix:** Delete PAT, create new one with correct permissions

### Issue: "Workflow still fails after updating secret"
**Cause:** GitHub Actions may cache old secret temporarily
**Fix:**
1. Wait 2-3 minutes for secret propagation
2. Re-run workflow: `gh run rerun <run-id>`

## Timeline Estimate

- **Step 1-3:** 5-10 minutes (manual)
- **Step 4-5:** 5-10 minutes (automated + verification)
- **Total:** 10-20 minutes

## Next Steps After Resolution

Once CI/CD is working:
1. Close bead `bd-3h3`: `br close bd-3h3 --status completed`
2. Unblock dependent beads:
   - `bd-31j` - Configure Docker Hub credentials
   - `bd-x11` - Fix linting errors
   - `bd-212` - Image investigation
   - `bd-1j7` - Leader election verification

## References

- **Docker Hub PAT Docs:** https://docs.docker.com/security/for-developers/access-tokens/
- **GitHub Secrets Docs:** https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
- **Failed Workflow Run:** https://github.com/ardenone/botburrow-agents/actions/runs/22040749901
- **Analysis Document:** docs/fixes/bd-31j-dockerhub-auth-analysis.md

---

**Created by:** Claude Worker (claude-code-glm-47-lima)
**Date:** 2026-02-15
**Bead:** bd-3h3 (HUMAN: Update Docker Hub credentials)

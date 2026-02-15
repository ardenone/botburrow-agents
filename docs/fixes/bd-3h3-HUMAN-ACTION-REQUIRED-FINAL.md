# 🚨 HUMAN ACTION REQUIRED: Docker Hub PAT Update (bd-3h3)

**Status:** ✅ All Worker Prep Complete - Ready for Human Execution
**Last Verified:** 2026-02-15 22:05 UTC
**Estimated Time:** 5-10 minutes

---

## ⚡ Quick Action Checklist

Follow these 5 steps to resolve the Docker Hub authentication issue:

### Step 1: Create Docker Hub Personal Access Token (PAT)
- **URL:** https://hub.docker.com/settings/security
- Click **"New Access Token"**
- **Token Name:** `github-actions-botburrow-agents`
- **Permissions:** `Read & Write`
- Click **"Generate"**
- **⚠️ COPY TOKEN IMMEDIATELY** (shown only once!)

### Step 2: Verify Repository Exists
- **URL:** https://hub.docker.com/u/ardenone
- Verify `ardenone/botburrow-agents` repository exists
- If missing, create it:
  - Click **"Create Repository"**
  - Name: `botburrow-agents`
  - Visibility: **Public** (recommended)

### Step 3: Update GitHub Secret
- **URL:** https://github.com/ardenone/botburrow-agents/settings/secrets/actions
- Find `DOCKERHUB_PASSWORD` in the list
- Click **pencil icon** (Update)
- Paste the PAT from Step 1
- Click **"Update secret"**
- Verify `DOCKERHUB_USERNAME` = `ardenone`

### Step 4: Test the Fix
```bash
# Trigger workflow manually
gh workflow run ci-cd.yml
gh run watch

# Or push a test commit
git commit --allow-empty -m "test: verify Docker Hub PAT"
git push origin main
```

### Step 5: Verify Success & Close Bead
```bash
# Check workflow status
gh run list --workflow=ci-cd.yml --limit 1

# Verify images on Docker Hub
# Visit: https://hub.docker.com/r/ardenone/botburrow-agents/tags
# Should see: latest and <commit-sha> tags

# Close the bead
br close bd-3h3 --status completed
```

---

## 🔍 Current Status

**Error (Confirmed 2026-02-15 21:26 UTC):**
```
ERROR: failed to push docker.io/ardenone/botburrow-agents:93581ad:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Latest Failed Run:** https://github.com/ardenone/botburrow-agents/actions/runs/22043329545

**Good News:**
- ✅ Tests passing (linting, type checking, unit tests)
- ✅ Docker build succeeds
- ✅ Only authentication step fails
- ✅ Root cause identified (password instead of PAT)

**Root Cause:** `DOCKERHUB_PASSWORD` secret contains a regular password instead of a Personal Access Token (PAT). Docker Hub requires PATs for CI/CD automation.

---

## 🔗 Blocked Beads

These beads will automatically unblock once bd-3h3 is resolved:
- **bd-31j** - Configure Docker Hub credentials for CI/CD push
- **bd-212** - Image investigation
- **bd-1j7** - Leader election verification

---

## 🆘 Alternative Solution: Migrate to GitHub Container Registry (GHCR)

If you **cannot access Docker Hub** or prefer GitHub-native solution:

**Benefits:**
- No external account management
- Uses `GITHUB_TOKEN` (automatic authentication)
- Better GitHub integration
- No secrets management needed

**Migration Steps:**
1. Update `.github/workflows/ci-cd.yml`:
   - Change image from `docker.io/ardenone/botburrow-agents` to `ghcr.io/ardenone/botburrow-agents`
   - Update login action to use `ghcr.io` with `GITHUB_TOKEN`

2. Update Kubernetes manifests to reference new image URL

3. No Docker Hub credentials needed

**Detailed Guide:** See `docs/fixes/bd-31j-dockerhub-auth-analysis.md` for full GHCR migration steps.

---

## ❓ Troubleshooting

### Issue: "Token authentication failed"
**Fix:** Regenerate PAT and update secret again. Ensure token was copied correctly.

### Issue: "Repository does not exist"
**Fix:** Create repository on Docker Hub (Step 2 above).

### Issue: "Insufficient permissions"
**Fix:** Delete PAT, create new one with `Read & Write` (not `Read-only`).

### Issue: "Workflow still fails after updating secret"
**Fix:** Wait 2-3 minutes for secret propagation, then re-run workflow.

---

## 📚 Reference Documentation

**Root Cause Analysis:**
- `docs/fixes/bd-31j-dockerhub-auth-analysis.md` (technical deep-dive)

**Detailed Guide:**
- `docs/fixes/bd-3h3-dockerhub-pat-update-guide.md` (comprehensive instructions)

**Docker Hub PAT Documentation:**
- https://docs.docker.com/security/for-developers/access-tokens/

**GitHub Secrets Documentation:**
- https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions

---

## ✅ Success Criteria

- [ ] Docker Hub PAT created with `Read & Write` permissions
- [ ] `ardenone/botburrow-agents` repository exists on Docker Hub
- [ ] `DOCKERHUB_PASSWORD` GitHub secret updated with PAT
- [ ] CI/CD workflow runs successfully
- [ ] Docker images pushed to Docker Hub
- [ ] Images visible at https://hub.docker.com/r/ardenone/botburrow-agents/tags
- [ ] Bead bd-3h3 closed as completed
- [ ] Blocked beads (bd-31j, bd-212, bd-1j7) automatically unblock

---

**Created by:** Automated Workers (claude-code-glm-47-lima, claude-code-glm-47-foxtrot, claude-sonnet-4-5)
**Last Updated:** 2026-02-15 22:05 UTC
**Bead:** bd-3h3 (HUMAN: Update Docker Hub credentials)
**Priority:** P0 (Critical - blocks CI/CD pipeline)

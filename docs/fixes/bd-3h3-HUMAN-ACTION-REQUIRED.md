# 🚨 HUMAN ACTION REQUIRED: Docker Hub PAT Update

**Bead ID:** bd-3h3
**Status:** Awaiting human credentials update
**Estimated Time:** 10-20 minutes
**Date:** 2026-02-15

## 📋 Quick Checklist

Complete these steps to resolve the Docker Hub authentication failure:

- [ ] **Step 1:** Create Docker Hub PAT at https://hub.docker.com/settings/security
  - Token name: `github-actions-botburrow-agents`
  - Permissions: **Read & Write** (minimum)
  - ⚠️ **CRITICAL:** Copy token immediately (shown only once!)

- [ ] **Step 2:** Verify repository exists at https://hub.docker.com/u/ardenone
  - Repository name: `botburrow-agents`
  - If missing, create it (Public visibility recommended)

- [ ] **Step 3:** Update GitHub secret at https://github.com/ardenone/botburrow-agents/settings/secrets/actions
  - Update `DOCKERHUB_PASSWORD` with the PAT from Step 1
  - Verify `DOCKERHUB_USERNAME` is set to `ardenone`

- [ ] **Step 4:** Test the fix
  - Option A: `gh workflow run ci-cd.yml && gh run watch`
  - Option B: Push empty commit to trigger workflow
  - Option C: Manually trigger via GitHub UI

- [ ] **Step 5:** Verify success at https://hub.docker.com/r/ardenone/botburrow-agents/tags
  - Confirm `latest` tag exists
  - Confirm commit SHA tag exists (e.g., `8b7b76d`)
  - Check recent push timestamp

## 🎯 Why This Is Required

**Current Issue:**
```
ERROR: failed to push docker.io/ardenone/botburrow-agents:8b7b76d:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Root Cause:**
The `DOCKERHUB_PASSWORD` GitHub secret likely contains a regular password instead of a Personal Access Token (PAT). Docker Hub requires PATs for automated push operations in CI/CD pipelines.

**Impact:**
- CI/CD workflows cannot push Docker images
- Blocks deployment automation
- Affects beads: bd-31j, bd-x11, bd-212, bd-1j7

## 📚 Detailed Guides

For step-by-step instructions with screenshots and troubleshooting:
- **Action Guide:** `docs/fixes/bd-3h3-dockerhub-pat-update-guide.md`
- **Analysis:** `docs/fixes/bd-31j-dockerhub-auth-analysis.md`

## 🔄 Alternative: Migrate to GitHub Container Registry (GHCR)

If you cannot access Docker Hub or prefer GitHub-native solution:

**Pros:**
- No external account management
- Uses `GITHUB_TOKEN` (automatic authentication)
- No secrets management needed

**Cons:**
- Requires workflow modifications
- Changes image URLs (affects deployments)

**Implementation:** See "Option 2" in `bd-31j-dockerhub-auth-analysis.md`

## ✅ After Completion

Once credentials are updated and workflow succeeds:

```bash
cd /home/coder/botburrow-agents

# Close this bead
br close bd-3h3 --status completed

# Dependent beads will automatically become unblocked:
# - bd-31j (Configure Docker Hub credentials)
# - bd-x11 (Fix linting errors)
# - bd-212 (Image investigation)
# - bd-1j7 (Leader election verification)

# Commit the status update
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-3h3): Docker Hub PAT updated - workflow verified

Co-Authored-By: Human <human@ardenone.com>"
git push origin main
```

## 🔗 Quick Links

- **Create PAT:** https://hub.docker.com/settings/security
- **Verify Repo:** https://hub.docker.com/u/ardenone
- **Update Secret:** https://github.com/ardenone/botburrow-agents/settings/secrets/actions
- **Trigger Workflow:** https://github.com/ardenone/botburrow-agents/actions/workflows/ci-cd.yml
- **Failed Run:** https://github.com/ardenone/botburrow-agents/actions/runs/22040749901

---

**Created by:** Claude Worker (claude-code-glm-47-lima)
**Worker Session:** claude-code-glm-47-foxtrot (verification)
**Date:** 2026-02-15

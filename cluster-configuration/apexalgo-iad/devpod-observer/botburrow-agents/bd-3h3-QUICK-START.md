# 🚨 bd-3h3: Docker Hub PAT Required (5 Minutes)

**Status:** ✅ Ready for Human Execution
**Bead:** bd-3h3
**Last Updated:** 2026-02-16 (verified by current worker)

---

## ⚡ Quick Summary

Your CI/CD workflow **builds successfully** but **fails to push** Docker images to Docker Hub because the `DOCKERHUB_PASSWORD` GitHub secret contains a regular password instead of a Personal Access Token (PAT).

**Error:**
```
insufficient_scope: authorization failed
```

**Fix:** Replace the password with a PAT (5 minutes)

---

## ✅ 5-Step Checklist (5 Minutes)

### 1. Create Docker Hub PAT (2 min)
1. Go to: https://hub.docker.com/settings/security
2. Click **"New Access Token"**
3. Name: `github-actions-botburrow-agents`
4. Permissions: **Read & Write** ⚠️ (not Read-only!)
5. Click **"Generate"**
6. **Copy token immediately** (shown only once)

### 2. Verify Repository (30 sec)
1. Go to: https://hub.docker.com/u/ardenone
2. Verify `ardenone/botburrow-agents` repository exists
3. If not, create it (Public visibility recommended)

### 3. Update GitHub Secret (1 min)
1. Go to: https://github.com/ardenone/botburrow-agents/settings/secrets/actions
2. Find `DOCKERHUB_PASSWORD`
3. Click pencil icon (edit)
4. **Paste the PAT** from step 1
5. Click **"Update secret"**

### 4. Test Workflow (1 min)
```bash
# Trigger workflow
gh workflow run ci-cd.yml

# Watch live
gh run watch
```

### 5. Verify & Close (1 min)
```bash
# Check workflow passed
# https://github.com/ardenone/botburrow-agents/actions

# Verify images on Docker Hub
# https://hub.docker.com/r/ardenone/botburrow-agents/tags

# Close bead
cd /home/coder/botburrow-agents
br close bd-3h3 --status completed
```

---

## 🔗 What This Unblocks

Completing bd-3h3 automatically unblocks:
- **bd-31j** - Configure Docker Hub credentials
- **bd-212** - Image investigation
- **bd-1j7** - Leader election verification

---

## 🔄 Alternative: Migrate to GitHub Container Registry

**Why GHCR?**
- ✅ No external account (uses GitHub)
- ✅ No secrets needed (uses `GITHUB_TOKEN`)
- ✅ Native GitHub integration

**See:** `docs/fixes/bd-3h3-HUMAN-ACTION-GUIDE.md` (full GHCR migration guide)

---

## 📚 Full Documentation

- **This Quick Start:** `cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/bd-3h3-QUICK-START.md`
- **Detailed Guide:** `docs/fixes/bd-3h3-HUMAN-ACTION-GUIDE.md` (9.4KB)
- **Root Cause:** `docs/fixes/bd-31j-dockerhub-auth-analysis.md` (7.3KB)
- **Final Status:** `docs/fixes/bd-3h3-FINAL-STATUS.md` (worker verification)

---

## ❓ Troubleshooting

**Workflow still fails after updating secret?**
- Wait 1-2 minutes (secret propagation delay)
- Verify token has **"Read & Write"** permissions (not Read-only)
- Check no extra spaces when pasting token

**Repository doesn't exist?**
- Create manually: https://hub.docker.com/repository/create
- Name: `botburrow-agents`
- Visibility: Public

**Token creation error?**
- Delete old token with same name first
- Create new token

---

**Estimated Time:** 5-10 minutes
**Worker:** Claude Sonnet 4.5 (session 2026-02-16)
**All Preparation:** ✅ Complete

# 🚨 HUMAN ACTION REQUIRED

**Bead:** bd-3h3 - Update Docker Hub credentials (PAT required)
**Status:** ✅ Ready for human action
**Time:** 5-10 minutes
**Last Verified:** 2026-02-16 04:02 UTC

---

## ⚡ Quick Summary

CI/CD workflow fails to push Docker images with error:
```
insufficient_scope: authorization failed
```

**Root Cause:** `DOCKERHUB_PASSWORD` secret contains a password, not a Personal Access Token (PAT).

**Latest Failed Run:** https://github.com/ardenone/botburrow-agents/actions/runs/22049644452

---

## 🎯 5-Step Fix (5-10 minutes)

### 1️⃣ Create Docker Hub PAT (2 min)
**URL:** https://hub.docker.com/settings/security

- Click **"New Access Token"**
- **Name:** `github-actions-botburrow-agents`
- **Permissions:** **Read & Write**
- Click **"Generate"**
- ⚠️ **Copy token immediately** (shown only once!)

### 2️⃣ Verify Repository (30 sec)
**URL:** https://hub.docker.com/u/ardenone

- Check if `ardenone/botburrow-agents` exists
- If NOT, create it (Public visibility)

### 3️⃣ Update GitHub Secret (1 min)
**URL:** https://github.com/ardenone/botburrow-agents/settings/secrets/actions

- Find `DOCKERHUB_PASSWORD`
- Click **pencil icon** (edit)
- Paste the PAT from step 1
- Click **"Update secret"**

### 4️⃣ Test Workflow (2 min)
```bash
cd /home/coder/botburrow-agents
gh workflow run ci-cd.yml
gh run watch
```

### 5️⃣ Close Bead (10 sec)
```bash
cd /home/coder/botburrow-agents
br close bd-3h3 --status completed
```

---

## 📚 Documentation

- **Quick Summary:** `docs/fixes/bd-3h3-ACTIONABLE-SUMMARY.md`
- **Detailed Guide:** `docs/fixes/bd-3h3-HUMAN-ACTION-GUIDE.md`
- **Root Cause:** `docs/fixes/bd-31j-dockerhub-auth-analysis.md`

---

## 🔄 Alternative: Migrate to GitHub Container Registry (GHCR)

If you prefer GitHub-native solutions:

**Benefits:**
- ✅ No external account needed
- ✅ Automatic authentication via `GITHUB_TOKEN`
- ✅ No secret management required

**See:** Full migration guide in `docs/fixes/bd-3h3-HUMAN-ACTION-GUIDE.md`

---

## 🔗 Blocked Beads

Completing bd-3h3 will unblock:
- **bd-31j** - Configure Docker Hub credentials
- **bd-212** - Image investigation
- **bd-1j7** - Leader election verification

---

**Worker:** Claude Sonnet 4.5
**Status:** ✅ ALL WORKER TASKS COMPLETE - READY FOR HUMAN

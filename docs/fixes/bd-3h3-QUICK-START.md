# 🚀 Quick Start: Fix Docker Hub Push (bd-3h3)

**Status:** ✅ READY FOR HUMAN ACTION
**Time Required:** 5-10 minutes
**Last Verified:** 2026-02-16 01:40 UTC

---

## ⚡ TL;DR

CI/CD fails to push Docker images because `DOCKERHUB_PASSWORD` is a regular password, not a Personal Access Token (PAT).

**Error:**
```
ERROR: insufficient_scope: authorization failed
```

**Fix:** Replace password with PAT (5 steps below)

---

## ✅ 5-Step Checklist

### ☐ Step 1: Create Docker Hub PAT (2 min)
1. Go to: https://hub.docker.com/settings/security
2. Click **"New Access Token"**
3. Name: `github-actions-botburrow-agents`
4. Permissions: **Read & Write**
5. Click **"Generate"**
6. **COPY TOKEN IMMEDIATELY** (shown only once!)

### ☐ Step 2: Verify Repository (30 sec)
1. Go to: https://hub.docker.com/u/ardenone
2. Check if `ardenone/botburrow-agents` exists
3. If missing: Create repository (name: `botburrow-agents`, visibility: Public)

### ☐ Step 3: Update GitHub Secret (1 min)
1. Go to: https://github.com/ardenone/botburrow-agents/settings/secrets/actions
2. Find `DOCKERHUB_PASSWORD`
3. Click pencil icon (edit)
4. Paste PAT from Step 1
5. Click **"Update secret"**

### ☐ Step 4: Test Workflow (2 min)
```bash
gh workflow run ci-cd.yml
gh run watch
```

### ☐ Step 5: Verify & Close (1 min)
1. Check workflow completed: https://github.com/ardenone/botburrow-agents/actions
2. Verify images on Docker Hub: https://hub.docker.com/r/ardenone/botburrow-agents/tags
3. Close bead:
```bash
cd /home/coder/botburrow-agents
br close bd-3h3 --status completed
```

---

## 🔓 What This Unblocks

- **bd-31j** - Configure Docker Hub credentials
- **bd-212** - Image version investigation
- **bd-1j7** - Leader election verification

---

## 📚 Full Documentation

- **Complete Guide:** `docs/fixes/bd-3h3-HUMAN-ACTION-GUIDE.md`
- **Root Cause Analysis:** `docs/fixes/bd-31j-dockerhub-auth-analysis.md`
- **Worker Status:** `docs/fixes/bd-3h3-WORKER-FINAL-STATUS.md`

---

## 🔄 Alternative: Migrate to GHCR

**Benefits:** No external secrets, uses `GITHUB_TOKEN`, better GitHub integration

**See:** Full GHCR migration guide in `bd-3h3-HUMAN-ACTION-GUIDE.md`

---

## ❓ Troubleshooting

**Q: Token permissions insufficient?**
A: Must be **"Read & Write"** (not Read-only)

**Q: Secret not working?**
A: Wait 1-2 minutes for GitHub secret propagation

**Q: Repository doesn't exist?**
A: Create at https://hub.docker.com/repository/create (name: `botburrow-agents`)

---

**Next Action:** Complete 5 steps above → Close bead

**Worker:** Claude Sonnet 4.5
**Verified:** 2026-02-16 01:40 UTC

# ⚡ Docker Hub PAT - 5 Minute Fix

**Status:** ❌ CI/CD failing - needs Docker Hub PAT update
**Last Error:** 2026-02-15 20:51 UTC - `insufficient_scope: authorization failed`

## 🎯 Action Required (5 minutes)

### Step 1: Create Docker Hub PAT (2 min)
```
1. Visit: https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Name: github-actions-botburrow-agents
4. Permissions: Read & Write
5. Click Generate
6. COPY TOKEN NOW (shown only once!)
```

### Step 2: Update GitHub Secret (1 min)
```
1. Visit: https://github.com/ardenone/botburrow-agents/settings/secrets/actions
2. Find DOCKERHUB_PASSWORD
3. Click pencil icon (Update)
4. Paste PAT token
5. Click Update
```

### Step 3: Test (2 min)
```bash
gh workflow run ci-cd.yml
gh run watch
```

### Step 4: Verify Success
```
Check: https://hub.docker.com/r/ardenone/botburrow-agents/tags
Should see: latest, 6d5f63b (or newer commit)
```

### Step 5: Close Bead
```bash
br close bd-3h3 --status completed
```

---

## 📊 Current Status

**Latest Failed Run:** [22042818897](https://github.com/ardenone/botburrow-agents/actions/runs/22042818897)

**Error Message:**
```
ERROR: failed to push docker.io/ardenone/botburrow-agents:6d5f63b:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Root Cause:** `DOCKERHUB_PASSWORD` secret contains regular password instead of PAT

**Blocked Beads:** bd-31j, bd-212, bd-1j7

---

## 📚 Full Documentation

- **Quick Reference:** `docs/fixes/bd-3h3-READY-FOR-HUMAN-ACTION.md`
- **Step-by-step Guide:** `docs/fixes/bd-3h3-dockerhub-pat-update-guide.md`
- **Root Cause Analysis:** `docs/fixes/bd-31j-dockerhub-auth-analysis.md`

---

**Updated:** 2026-02-15 20:52 UTC
**Bead:** bd-3h3

# bd-3h3 Quick Reference - Docker Hub PAT Update

**Status:** ✅ READY FOR HUMAN ACTION
**Last Verified:** 2026-02-16 (Current Session)
**Estimated Time:** 5-10 minutes

---

## 🎯 What You Need to Do

This bead requires **manual credential update** on Docker Hub and GitHub. All worker preparation is complete.

### The 5-Step Fix

#### 1. Create Docker Hub PAT (2 min)
🔗 https://hub.docker.com/settings/security
- Click "New Access Token"
- Name: `github-actions-botburrow-agents`
- Permissions: **Read & Write** ⚠️ (not Read-only)
- Copy token immediately (shown only once)

#### 2. Verify Repository (30 sec)
🔗 https://hub.docker.com/u/ardenone
- Confirm `ardenone/botburrow-agents` exists
- If not: Create → Public → Name: `botburrow-agents`

#### 3. Update GitHub Secret (1 min)
🔗 https://github.com/ardenone/botburrow-agents/settings/secrets/actions
- Find `DOCKERHUB_PASSWORD`
- Click edit (pencil icon)
- Paste PAT from step 1
- Save

#### 4. Test Workflow (2 min)
```bash
gh workflow run ci-cd.yml
gh run watch
```

#### 5. Verify & Close (1 min)
```bash
# Check Docker Hub for new images
# https://hub.docker.com/r/ardenone/botburrow-agents/tags

# Close bead
cd /home/coder/botburrow-agents
br close bd-3h3 --status completed
```

---

## 🚨 Current Error

```
ERROR: failed to push docker.io/ardenone/botburrow-agents:
push access denied, repository does not exist or may require authorization:
server message: insufficient_scope: authorization failed
```

**Root Cause:** `DOCKERHUB_PASSWORD` contains a regular password instead of a PAT.
Docker Hub requires PATs for CI/CD since 2020.

---

## 📚 Full Documentation

- **Detailed Guide:** `docs/fixes/bd-3h3-HUMAN-ACTION-GUIDE.md` (9.4KB)
- **Final Status:** `docs/fixes/bd-3h3-FINAL-STATUS.md` (9.2KB)
- **Root Cause:** `docs/fixes/bd-31j-dockerhub-auth-analysis.md` (7.3KB)
- **Worker Status:** `docs/fixes/bd-3h3-WORKER-FINAL-STATUS.md` (4.5KB)

---

## 🔗 What This Unblocks

Completing bd-3h3 will unblock:
- **bd-31j** - Configure Docker Hub credentials
- **bd-212** - Image investigation
- **bd-1j7** - Leader election verification

---

## 🔄 Alternative: Migrate to GHCR

If you prefer GitHub-native solutions:
- No Docker Hub account needed
- Uses built-in `GITHUB_TOKEN` (automatic)
- No secret management
- See full migration guide in `bd-3h3-HUMAN-ACTION-GUIDE.md`

---

## ⚠️ Why This is HUMAN-Only

Workers cannot:
- ❌ Access Docker Hub web UI
- ❌ Update GitHub repository secrets
- ❌ Generate PATs (requires human login)

Workers completed:
- ✅ Root cause analysis
- ✅ Documentation creation
- ✅ Error verification
- ✅ Alternative solutions research

---

**Next Action:** Execute 5-step checklist above, then close bead.

**Worker:** Claude Sonnet 4.5 (multiple verification sessions)
**Last Update:** 2026-02-16 03:50 UTC

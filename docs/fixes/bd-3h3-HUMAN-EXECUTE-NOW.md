# 🎯 EXECUTE NOW - Docker Hub PAT Update (bd-3h3)

**Status:** ✅ READY FOR HUMAN ACTION
**Time Required:** 5-10 minutes
**Last Verified:** 2026-02-15 21:35 UTC

---

## ⚡ Quick 5-Step Fix

### Step 1: Create Docker Hub PAT (2 minutes)
🔗 **Go to:** https://hub.docker.com/settings/security

1. Click **"New Access Token"**
2. **Description:** `github-actions-botburrow-agents`
3. **Permissions:** `Read & Write` (or `Read, Write, Delete`)
4. Click **"Generate"**
5. **COPY THE TOKEN IMMEDIATELY** (shown only once!)
   - Format: `dckr_pat_XXXXXXXXXXXXXXXXXXXX`

---

### Step 2: Verify Repository Exists (30 seconds)
🔗 **Go to:** https://hub.docker.com/u/ardenone

- [ ] Check if `botburrow-agents` repository exists
- [ ] **If NOT found:** Click "Create Repository"
  - Name: `botburrow-agents`
  - Visibility: Public
  - Click "Create"

---

### Step 3: Update GitHub Secret (1 minute)
🔗 **Go to:** https://github.com/ardenone/botburrow-agents/settings/secrets/actions

1. Find **`DOCKERHUB_PASSWORD`** in the list
2. Click the **pencil icon** (Update)
3. **Paste the PAT** from Step 1
4. Click **"Update secret"**
5. Verify **`DOCKERHUB_USERNAME`** = `ardenone` (should already be correct)

---

### Step 4: Test the Fix (2 minutes)
```bash
# Option A: Trigger workflow manually
gh workflow run ci-cd.yml
gh run watch

# Option B: Or via GitHub UI
# https://github.com/ardenone/botburrow-agents/actions/workflows/ci-cd.yml
# Click "Run workflow"
```

---

### Step 5: Verify Success (1 minute)
🔗 **Check workflow:** https://github.com/ardenone/botburrow-agents/actions

- [ ] Look for "Build and Deploy" workflow
- [ ] Verify "Build Docker Images" job shows: ✅ Success
- [ ] Look for output: `Successfully pushed docker.io/ardenone/botburrow-agents:XXXXXXX`

🔗 **Check images:** https://hub.docker.com/r/ardenone/botburrow-agents/tags

- [ ] Confirm you see `latest` tag
- [ ] Confirm you see commit SHA tag (e.g., `93581ad`)
- [ ] Check timestamp is recent

---

## ✅ Close the Bead

Once verified successful:
```bash
br close bd-3h3 --status completed
```

This will automatically unblock:
- bd-31j - Configure Docker Hub credentials
- bd-212 - Image investigation
- bd-1j7 - Leader election verification

---

## 🆘 Troubleshooting

**Problem: Token not working**
- Ensure permissions are `Read & Write` (not Read-only)
- Try generating a new token

**Problem: Repository not found**
- Create repository at https://hub.docker.com/repositories
- Name must be exactly `botburrow-agents`

**Problem: Workflow still fails**
- Wait 2-3 minutes for secret propagation
- Re-run workflow: `gh run rerun <run-id>`

---

## 📖 Detailed Documentation

If you need more context:
- **Quick Start:** docs/fixes/bd-3h3-READY-FOR-HUMAN-ACTION.md
- **Detailed Guide:** docs/fixes/bd-3h3-dockerhub-pat-update-guide.md
- **Root Cause:** docs/fixes/bd-31j-dockerhub-auth-analysis.md

---

## 🔄 Alternative: Migrate to GitHub Container Registry

If you **cannot access Docker Hub**, you can migrate to GHCR instead:
- Uses `GITHUB_TOKEN` (automatic authentication)
- No secrets management needed
- See Option 2 in detailed guide

---

**Last Updated:** 2026-02-15 21:35 UTC
**Worker:** claude-sonnet-4-5 (final verification)
**Bead:** bd-3h3

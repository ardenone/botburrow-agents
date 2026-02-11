# bd-13t Status Summary - Forgejo Manual Setup Required

**Bead:** bd-13t
**Status:** WAITING FOR HUMAN
**Priority:** P0 - Critical
**Timestamp:** 2026-02-11T05:00:00Z

## Current State

### Pod Failures Confirmed

All botburrow-agents pods are in CrashLoopBackOff/Init:Error state due to missing Forgejo repository:

```
coordinator-7c895c5d75-2c7h7   0/1   Init:Error   git clone failed
runner-exploration-*           0/1   Init:Error   git clone failed
runner-hybrid-*                0/1   Init:Error   git clone failed
runner-notification-*          0/1   Init:Error   git clone failed
```

### Root Cause (Verified)

Git clone failing with:
```
fatal: repository 'http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git/' not found
```

**Repository URL:** `http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git`
**Problem:** The `botburrow` organization and `agent-definitions` repository do not exist in Forgejo

## What You Need to Do

### Step 1: Access Forgejo

Navigate to: **https://botburrow-git.ardenone.com**

### Step 2: Get Admin Credentials

```bash
# From devpod (if you have kubectl access to forgejo namespace):
kubectl get secret -n forgejo forgejo-secrets -o jsonpath='{.data.ADMIN_USER}' | base64 -d
kubectl get secret -n forgejo forgejo-secrets -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d
```

**Alternative:** Check your password manager or secure notes for Forgejo admin credentials.

### Step 3: Create Organization and Repository

1. **Log in to Forgejo** at https://botburrow-git.ardenone.com
2. **Create `botburrow` organization:**
   - Click "+" → "New Organization"
   - Name: `botburrow`
   - Visibility: Public (recommended)
3. **Create `agent-definitions` repository under `botburrow`:**
   - Click "New Repository" in botburrow org
   - Name: `agent-definitions`
   - Enable "This repository is a mirror"
   - Mirror source: `https://github.com/jedarden/agent-definitions`
   - Sync interval: Every 8 hours
   - Create repository

### Step 4: Verify Success

From devpod, run:
```bash
# This should succeed after you create the repository:
git ls-remote http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git

# Expected output:
# <commit-hash>  HEAD
# <commit-hash>  refs/heads/main
```

### Step 5: Restart Pods (if needed)

```bash
kubectl delete pod -n botburrow-agents -l app=botburrow-agents --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig
```

Pods should now start successfully and pull the agent definitions.

## Detailed Guide

See: `bd-13t-forgejo-manual-setup-guide.md` for complete step-by-step instructions.

## Success Criteria

- [ ] Logged into Forgejo
- [ ] Created `botburrow` organization
- [ ] Created `agent-definitions` repository as GitHub mirror
- [ ] Verified `git ls-remote` works
- [ ] Pods start successfully (all init containers complete)

## Blocked Beads

This bead blocks:
- **bd-1co** - Update agent-definitions URLs to Forgejo (partially complete, waiting for Forgejo)
- **bd-32g** - Verify botburrow-agents pods start successfully (cannot verify until Forgejo is setup)

## Next Steps After Completion

Once you've completed the manual setup:
1. Respond in the statusline that bd-13t is complete
2. Workers will automatically pick up bd-32g to verify pod startup
3. Consider creating a follow-up bead to fix the automated mirror-setup sidecar

---

**WAITING FOR HUMAN ACTION** - This cannot be automated and requires manual Forgejo web UI access.

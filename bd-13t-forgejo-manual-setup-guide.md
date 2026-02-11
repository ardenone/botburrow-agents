# Forgejo Manual Setup Guide - bd-13t

**Status:** BLOCKED - Requires human intervention
**Priority:** P0 - Critical (blocks bd-1co and bd-32g)
**Date:** 2026-02-11

## Problem

Botburrow-agents pods cannot clone agent-definitions from Forgejo because:
1. The `botburrow` organization does not exist in Forgejo
2. The `agent-definitions` repository does not exist under `botburrow`
3. Automated mirror-setup sidecar is failing

## Required Manual Steps

### 1. Access Forgejo Web UI

Navigate to: **https://botburrow-git.ardenone.com**

### 2. Log In as Admin

**Credentials Location:**
- Admin credentials are stored in SealedSecret: `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/forgejo/forgejo-sealedsecret.yml`
- Secret name: `forgejo-secrets`
- Keys needed: `ADMIN_USER`, `ADMIN_PASSWORD`

**To retrieve credentials from the cluster:**

```bash
# From devpod (requires appropriate kubectl permissions):
kubectl get secret -n forgejo forgejo-secrets -o jsonpath='{.data.ADMIN_USER}' | base64 -d
kubectl get secret -n forgejo forgejo-secrets -o jsonpath='{.data.ADMIN_PASSWORD}' | base64 -d
```

**Alternative:** Check your password manager or secure notes for Forgejo admin credentials.

### 3. Create `botburrow` Organization

Once logged in:
1. Click the **"+"** icon in top-right corner
2. Select **"New Organization"**
3. Set organization name: `botburrow`
4. Set visibility: **Public** (recommended) or Private
5. Click **"Create Organization"**

### 4. Create `agent-definitions` Repository

Under the `botburrow` organization:
1. Click **"New Repository"**
2. Set repository name: `agent-definitions`
3. Set visibility: **Public** (recommended)
4. **CRITICAL:** Configure as a **mirror** from GitHub:
   - Enable "This repository is a mirror"
   - Set mirror source: `https://github.com/jedarden/agent-definitions`
   - Set sync interval: Every 8 hours (or as preferred)
   - If GitHub token is required, use token from `forgejo-secrets.GITHUB_TOKEN`
5. Click **"Create Repository"**

### 5. Verify Repository is Accessible

Test that the repository URL is accessible:

```bash
# From devpod or any cluster pod:
git ls-remote http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git

# Should output refs like:
# a1b2c3d4... HEAD
# a1b2c3d4... refs/heads/main
```

### 6. Trigger Pod Restart (if needed)

If pods are still in CrashLoopBackOff after repo creation:

```bash
# From workspace root:
cd /home/coder/ardenone-cluster
kubectl delete pod -n botburrow-agents -l app=botburrow-agents

# Or scale down and up:
kubectl scale deployment -n botburrow-agents botburrow-agents --replicas=0
kubectl scale deployment -n botburrow-agents botburrow-agents --replicas=1
```

## Validation Checklist

- [ ] Logged into Forgejo at https://botburrow-git.ardenone.com
- [ ] Created `botburrow` organization
- [ ] Created `agent-definitions` repository under `botburrow`
- [ ] Configured repository as mirror from GitHub
- [ ] Verified `git ls-remote` works from cluster
- [ ] Confirmed pods start successfully (bd-32g validation)

## Why This Manual Step is Necessary

The automated mirror-setup sidecar in the botburrow-agents deployment is currently failing due to:
1. **securityContext issues** - sidecar cannot write to `/data` volume
2. **Token generation failures** - `forgejo admin user generate-access-token` command failing
3. **API auth issues** - Cannot authenticate to Forgejo API to create org/repos

**Long-term fix:** Update the mirror-setup sidecar to properly handle permissions and token generation (tracked separately).

## Success Criteria

After completing these steps:
- `http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git` is accessible
- Pods successfully clone the repository on startup
- Bead bd-13t can be closed
- Bead bd-1co is unblocked
- Bead bd-32g can verify pod startup

## Related Beads

- **bd-13t** (this bead) - HUMAN: Manually setup Forgejo
- **bd-1co** - Update agent-definitions URLs to Forgejo (blocked by this)
- **bd-32g** - Verify botburrow-agents pods start successfully (depends on this)

## Follow-up Work

After manual setup, consider creating a bead to:
- Fix the automated mirror-setup sidecar for future repositories
- Document Forgejo admin workflows in ardenone-cluster repo
- Create a bootstrap Job for automated org/repo creation on fresh Forgejo installs

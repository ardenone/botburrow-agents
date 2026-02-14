# bd-2wsm Task Summary: Add Forgejo credentials to botburrow-agents init containers

**Date:** 2026-02-14
**Task:** Add Forgejo credentials to botburrow-agents init containers
**Status:** 🔶 PARTIALLY COMPLETE - Awaiting Human Input

## Completed Work

### 1. Configuration Updates ✅

**ConfigMap Changes (`k8s/apexalgo-iad/configmap.yaml`):**
- Changed `repo-url` from GitHub to Forgejo:
  - **Old:** `https://github.com/jedarden/agent-definitions.git`
  - **New:** `http://forgejo.forgejo.svc.cluster.local:3000/botburrow/agent-definitions.git`
- Updated `repo-name`:
  - **Old:** `jedarden/agent-definitions`
  - **New:** `botburrow/agent-definitions`
- Added detailed comments explaining URL format and credential usage

**Deployment Manifest Updates:**

**`coordinator-git-sync.yaml`:**
- Changed git-sync credentials from GitHub to Forgejo:
  - **Old:** `GIT_SYNC_USERNAME: GITHUB_USER`, `GIT_SYNC_PASSWORD: GITHUB_TOKEN`
  - **New:** `GIT_SYNC_USERNAME: FORGEJO_USER`, `GIT_SYNC_PASSWORD: FORGEJO_TOKEN`

**`runner-git-sync.yaml`:**
- Changed git-sync credentials from GitHub to Forgejo:
  - **Old:** `GIT_SYNC_USERNAME: GITHUB_USER`, `GIT_SYNC_PASSWORD: GITHUB_TOKEN`
  - **New:** `GIT_SYNC_USERNAME: FORGEJO_USER`, `GIT_SYNC_PASSWORD: FORGEJO_TOKEN`

### 2. Documentation Created ✅

Created comprehensive setup guide:
**`docs/forgejo-credentials-setup-bd-2wsm.md`**
- Prerequisites verification steps
- Token generation instructions (Forgejo UI and CLI)
- SealedSecret generation and deployment steps
- Troubleshooting guide
- Complete workflow from start to verification

### 3. Git Commits ✅

All changes committed and pushed to:
- **Repository:** `github.com/ardenone/botburrow-agents`
- **Commits:**
  1. `feat(bd-2wsm): Configure botburrow-agents to use Forgejo for agent-definitions`
  2. `chore(bd-2wsm): Create human bead for Forgejo credentials`

### 4. Human Bead Created ✅

**Bead bd-rip:** "HUMAN: Provide Forgejo credentials for botburrow-agents git-sync"
- **Labels:** human, forgejo, credentials
- **Priority:** 0 (critical)
- **Purpose:** Get actual Forgejo credential values needed for Secret

## Pending Work

### 1. Human Action Required 🔶

**Bead bd-rip** requires the following:

1. **FORGEJO_USER**: Forgejo username for authentication
   - Can be admin user or dedicated service account
   - Default value: `botburrow-agents`

2. **FORGEJO_TOKEN**: Forgejo access token with `read:repository` scope
   - Generate via Forgejo UI: https://botburrow-git.ardenone.com → Settings → Applications
   - Token name suggestion: `botburrow-agents-git-sync`

3. **REPO_EXISTS**: Confirmation that `botburrow/agent-definitions` exists in Forgejo
   - Log into Forgejo UI to verify
   - Create if missing (mirror from GitHub: jedarden/agent-definitions)

### 2. SealedSecret Generation (After Human Provides Credentials)

Once credentials are provided:

1. Update `botburrow-agents-sealedsecrets.yml.template` with actual values
2. Generate SealedSecret:
   ```bash
   kubeseal --format yaml < botburrow-agents-sealedsecrets.yml.template > botburrow-agents-sealedsecrets.yml
   ```
3. Apply to cluster:
   ```bash
   kubectl apply -f botburrow-agents-sealedsecrets.yml
   ```

### 3. Deployment to apexalgo-iad

After SealedSecret is ready:

1. Apply ConfigMap (if not already deployed):
   ```bash
   kubectl apply -f k8s/apexalgo-iad/configmap.yaml
   ```
2. Restart pods to pick up new configuration:
   ```bash
   kubectl delete pod -n botburrow-agents -l app.kubernetes.io/part-of=botburrow-agents
   ```
3. Verify pods start successfully:
   ```bash
   kubectl get pods -n botburrow-agents -w
   ```

## Verification Criteria

Task is complete when:

- [x] ConfigMap updated to point to Forgejo URL
- [x] Deployment manifests use FORGEJO_USER/FORGEJO_TOKEN
- [x] Documentation created for credential setup
- [x] Git commits pushed to GitHub
- [x] Human bead created for credential values
- [ ] Human provides FORGEJO_USER and FORGEJO_TOKEN
- [ ] SealedSecret generated and applied to apexalgo-iad
- [ ] ConfigMap applied to apexalgo-iad
- [ ] Pods restart and successfully clone repository
- [ ] git-sync logs show successful clone without authentication errors

## Related Beads

- **bd-2wsm** (this task) - Add Forgejo credentials to botburrow-agents init containers
- **bd-rip** (human input) - Provide Forgejo credentials for botburrow-agents git-sync
- **bd-13t** (closed) - HUMAN: Manually setup Forgejo botburrow org and agent-definitions repo
- **bd-157** (closed) - Fix Forgejo CrashLoopBackOff (s6-svscan permission denied)

## Files Modified

```
k8s/apexalgo-iad/
├── configmap.yaml                  (updated - Forgejo URL)
├── coordinator-git-sync.yaml       (updated - FORGEJO credentials)
└── runner-git-sync.yaml            (updated - FORGEJO credentials)

docs/
└── forgejo-credentials-setup-bd-2wsm.md   (new - comprehensive guide)
```

## Decision Rationale

**Why Option A (API Token) was chosen:**
1. **Simpler Setup:** Works with existing git-sync sidecar using HTTP
2. **No SSH Complexity:** Avoids SSH key management and mounting
3. **Easy Rotation:** Tokens can be regenerated via Forgejo UI
4. **Fits Architecture:** git-sync already has GIT_SYNC_USERNAME/PASSWORD support

**Why ConfigMap Points to Forgejo:**
1. **Internal Primary:** Forgejo is the authoritative source for agent definitions
2. **Lower Latency:** Cluster-internal service access
3. **Independence:** Not dependent on external GitHub availability for read operations

## Next Steps

1. **Human:** Respond to bead bd-rip with Forgejo credentials
2. **Worker:** Generate and apply SealedSecret with credentials
3. **Worker:** Deploy ConfigMap to apexalgo-iad
4. **Worker:** Restart pods and verify successful clone
5. **Worker:** Close bead bd-2wsm

## Summary

This task reconfigured botburrow-agents to use Forgejo as the primary source for agent-definitions repository. The manifests and ConfigMap have been updated, and a human bead has been created to collect the required credential values. Once human provides credentials, the SealedSecret can be generated and deployed, completing the migration from GitHub to Forgejo for internal cluster access.

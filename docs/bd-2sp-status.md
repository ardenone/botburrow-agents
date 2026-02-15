## Verification Status - Ready for Human Action

**Problem Confirmed:** ✅
- Coordinator experiencing continuous 401 Unauthorized errors
- Errors occur every ~5 seconds when polling Hub API
- Root cause: Secret uses `HUB_API_KEY` but app expects `BOTBURROW_HUB_API_KEY`

**Current Logs (2026-02-15 19:01 UTC):**
```
[error] poll_error error="Client error '401 Unauthorized' for url
  'https://botburrow.ardenone.com/api/v1/notifications/poll?timeout=30&batch_size=100'"
```

**Coordinator Pods Status:**
```
coordinator-644b76d7bd-89trf            1/1     Running   0          18h
coordinator-644b76d7bd-pwlft            1/1     Running   0          18h
coordinator-git-sync-79db4b749c-4dz6d   2/2     Running   0          17h
coordinator-git-sync-79db4b749c-sbl4p   2/2     Running   0          17h
```

**Current Access Level:**
- ❌ Cannot edit secrets in botburrow-agents namespace
- ✅ Read-only access via devpod-observer service account
- Requires: cluster-admin or secret edit permissions

**Ready for Human Execution:**

All preparation work is complete. Three options are documented:

### Option 1: Automated Fix Script (RECOMMENDED)
```bash
# Run from machine with cluster-admin kubeconfig
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig
cd /home/coder/botburrow-agents
./scripts/fix-hub-auth.sh
```

### Option 2: Manual kubectl edit
```bash
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
# Rename: HUB_API_KEY → BOTBURROW_HUB_API_KEY
kubectl rollout restart deployment coordinator -n botburrow-agents
```

### Option 3: Grant devpod-observer secret edit permissions
See: `docs/hub-api-authentication-fix.md` for RBAC manifest

**Required Inputs:**
1. Valid Hub API key from https://botburrow.ardenone.com/admin
2. Cluster-admin kubectl access to apexalgo-iad

**Documentation:**
- Fix guide: `docs/hub-api-authentication-fix.md`
- Fix script: `scripts/fix-hub-auth.sh`
- Updated placeholder: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

**Next Action:** Execute one of the three options above with cluster-admin access.

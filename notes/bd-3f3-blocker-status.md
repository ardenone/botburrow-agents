# bd-3f3: ArgoCD Installation - BLOCKER STATUS

**Date:** 2026-08-02
**Status:** ❌ BLOCKED - Authentication Token Expired
**Bead ID:** bd-3f3

## Summary

All preparation work for ArgoCD installation in apexalgo-iad cluster is complete, but execution is blocked due to an expired authentication token in the admin kubeconfig.

## What's Ready ✅

1. ✅ All ArgoCD manifests prepared in `k8s/apexalgo-iad/argocd/`
   - install.sh (installation script)
   - applicationset.yaml (GitOps configuration)
   - ingress.yaml (Traefik ingress)
   - install.yaml (custom install manifest)
   - kustomization.yaml
   - namespace.yaml

2. ✅ Documentation complete in `docs/cluster-admin/`
   - bd-3f3-EXEC-NOW.md (quick start guide)
   - bd-3f3-READY-FOR-EXECUTION.md (comprehensive guide)
   - bd-3f3-VERIFY-READY.sh (verification script)

3. ✅ Cluster state verified
   - `devpod-observer` ServiceAccount exists (143 days old)
   - `botburrow-agents` namespace exists with 13 running pods
   - ArgoCD namespace does NOT exist (installation needed)

## The Blocker ❌

**Issue:** Admin kubeconfig authentication token expired

**Details:**
- Kubeconfig: `/home/coding/.kube/apexalgo-iad.kubeconfig`
- Current context: `apexalgo-apexalgo-iad`
- Token expiry: `2026-07-31 22:39:32 UTC`
- Current time: `2026-08-02 13:51:27 UTC`
- **Token expired ~1.6 days ago**

**Error:**
```
error: You must be logged in to the server (Unauthorized)
```

## Root Cause

The kubeconfig contains a static JWT token that has expired. According to CLAUDE.md documentation:

> Read/write (cloudspace-admin OIDC token, expires every ~3 days — regenerate from Spot UI)

The token was last updated on `2026-07-27T20:24:31Z` (from token `"updated_at"` claim) and expired 4 days later.

## Required Human Action 🔧

### Option 1: Regenerate Admin Token (Recommended)

1. Access the Rackspace Spot UI for the apexalgo-iad cloudspace
2. Generate a new cloudspace-admin OIDC token
3. Update `/home/coding/.kube/apexalgo-iad.kubeconfig` with the new token
4. Re-run this bead execution

### Option 2: Use OIDC Authentication

The kubeconfig has an OIDC context (`apexalgo-apexalgo-iad-oidc`) that uses interactive authentication:

```bash
export KUBECONFIG=/home/coding/.kube/apexalgo-iad.kubeconfig
kubectl config use-context apexalgo-apexalgo-iad-oidc
kubectl get pods  # Will trigger browser-based OIDC login
```

However, this requires interactive browser access which may not work in this environment.

## What Happens After Token is Refreshed

Once the admin kubeconfig has valid authentication, the installation can proceed:

1. **Grant cluster-admin to devpod-observer SA** (1 min)
   ```bash
   kubectl create clusterrolebinding devpod-observer-cluster-admin \
     --clusterrole=cluster-admin \
     --serviceaccount=devpod-observer:devpod-observer
   ```

2. **Execute installation script** (5-10 min)
   ```bash
   cd k8s/apexalgo-iad/argocd
   ./install.sh
   ```

3. **Monitor installation**
   ```bash
   kubectl get pods -n argocd -w
   ```

4. **Verify ArgoCD is running**
   ```bash
   kubectl get application -n argocd
   ```

5. **Revoke cluster-admin** (CRITICAL)
   ```bash
   kubectl delete clusterrolebinding devpod-observer-cluster-admin
   ```

## References

- Execution guide: `docs/cluster-admin/bd-3f3-EXEC-NOW.md`
- Cluster access docs: `/home/coding/CLAUDE.md` (section: "Kubernetes Access → apexalgo-iad")
- Bead context: bd-3f3 (type: human, requires cluster-admin)

## Next Steps

❗ **BEAD NOT CLOSED** - Awaiting human action to refresh authentication token

Once token is refreshed, re-run:
```bash
bf claim bd-3f3
cd /home/coding/botburrow-agents
# Re-execute the installation
```

---

**Note:** This bead cannot be completed without valid cluster-admin credentials. All preparation work is done and ready for immediate execution once authentication is restored.

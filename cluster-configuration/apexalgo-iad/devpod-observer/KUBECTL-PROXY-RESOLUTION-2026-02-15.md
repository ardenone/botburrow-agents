# kubectl-proxy Tailscale Connectivity Resolution

**Date:** 2026-02-15
**Bead:** bd-2y0
**Issue:** Tailscale kubectl-proxy connection timeouts to apexalgo-iad cluster
**Status:** ✅ RESOLVED

## Problem Summary

The Tailscale kubectl-proxy (ts-kubectl-apexalgo-iad-87pxw-0) was experiencing persistent connection timeouts when attempting to forward kubectl requests to the apexalgo-iad cluster. This blocked the ability to apply the Hub API authentication fix from bead bd-2jm.

### Symptoms
- HTTP health check to kubectl-proxy timed out after 10 seconds
- kubectl commands to apexalgo-iad cluster timed out after ~90 seconds
- Tailscale pod logs showed continuous "timeout opening connection" errors
- Error pattern: `timeout opening (TCP 100.79.107.110:XXXXX => 100.94.193.51:8001) to node [p/guc]; online=yes, lastRecv=15m0s`

### Root Cause
The Tailscale pod had lost active TCP connectivity to the remote kubectl-proxy endpoint (100.94.193.51:8001), despite the Tailscale mesh reporting the node as "online". The "lastRecv" timestamp showed no successful data receipt for 15+ minutes, indicating a stale connection state.

## Resolution

**Action Taken:** Restarted the Tailscale kubectl-proxy pod

```bash
# Delete pod to force restart
kubectl delete pod -n tailscale ts-kubectl-apexalgo-iad-87pxw-0

# Wait for pod to be recreated (StatefulSet)
kubectl wait --for=condition=Ready pod -n tailscale ts-kubectl-apexalgo-iad-87pxw-0

# Verify health endpoint
curl http://kubectl-apexalgo-iad.devpod.svc.cluster.local:8001/healthz
# Response: "ok"
```

**Result:** ✅ SUCCESS

### Post-Restart Verification

1. **Health Endpoint:** ✅ Responding correctly
   ```bash
   $ curl http://kubectl-apexalgo-iad.devpod.svc.cluster.local:8001/healthz
   ok
   ```

2. **Node Access:** ✅ Working
   ```bash
   $ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
   $ kubectl get nodes
   NAME                              STATUS   ROLES    AGE   VERSION
   prod-instance-17686206245940263   Ready    worker   29d   v1.33.0
   [... 18 nodes total ...]
   ```

3. **Namespace Access:** ✅ Working (monitoring namespace)
   ```bash
   $ kubectl get pods -n monitoring
   NAME           READY   STATUS    RESTARTS         AGE
   vector-87wk4   1/1     Running   23 (3d19h ago)   20d
   [... vector pods running ...]
   ```

4. **Secret Access:** ❌ RBAC Permission Denied (new blocker discovered)
   ```bash
   $ kubectl get secret -n botburrow botburrow-agents-secrets
   Error from server (Forbidden): secrets "botburrow-agents-secrets" is forbidden:
   User "system:serviceaccount:devpod-observer:devpod-observer" cannot get resource
   "secrets" in API group "" in the namespace "botburrow"
   ```

## New Blocker Discovered

**Issue:** The devpod-observer ServiceAccount has read-only access to the `monitoring` and `devpod-observer` namespaces, but **does NOT have access** to the `botburrow` namespace.

**Impact:** Cannot apply the Hub API authentication fix from bead bd-2jm, which requires editing the `botburrow-agents-secrets` Secret in the `botburrow` namespace.

**Next Steps:**
- Create new bead to grant devpod-observer RBAC permissions for botburrow namespace
- Apply RoleBinding to allow secret read/write in botburrow namespace
- Then proceed with bd-2jm Hub API fix

## Timeline

- **20:34 UTC:** Connection timeouts detected (lastRecv=10m+)
- **20:39 UTC:** Restart initiated
- **20:39:15 UTC:** Pod recreated and Running
- **20:39:20 UTC:** Health endpoint verified ✅
- **20:40 UTC:** kubectl commands verified ✅
- **20:40 UTC:** RBAC blocker discovered for botburrow namespace

## Related Documentation

- Kubectl-proxy deployment: `cluster-configuration/apexalgo-iad/devpod-observer/kubectl-proxy.yml`
- Tailscale egress config: `cluster-configuration/ardenone-cluster/devpod/apexalgo-iad-kubectl-egress.yml`
- RBAC permissions: `cluster-configuration/apexalgo-iad/devpod-observer/rbac.yml`
- Previous status: `cluster-configuration/apexalgo-iad/devpod-observer/KUBECTL-PROXY-STATUS.md`

## Lessons Learned

1. **Quick Resolution:** Simple pod restart resolved the Tailscale connectivity issue
2. **Transient Connectivity:** The issue appears to be a transient connection timeout in the Tailscale mesh, not a configuration problem
3. **RBAC Discovery:** Testing revealed missing RBAC permissions that weren't caught during initial setup
4. **Namespace Scope:** devpod-observer needs explicit RoleBindings per namespace for write access

## Recommendations

1. **Monitoring:** Add alerting for kubectl-proxy health endpoint failures
2. **RBAC Audit:** Review all namespaces where devpod-observer needs access
3. **Documentation:** Update CLAUDE.md with botburrow namespace access requirements
4. **Automation:** Consider automatic restart on health check failures

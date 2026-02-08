# Workaround: SealedSecret Creation for botburrow-agents

## Original Bead
- **Bead ID:** bd-1x8 (Create SealedSecret for botburrow-agents from template)
- **Status:** CLOSED (work not completed)
- **Alternative Bead:** bd-1fj (Use workaround approach)

## Problem Statement
The original approach was to create a SealedSecret from the template file `botburrow-agents-secret.yml.template` with real secret values. This requires:
1. Human input for secret values (HUB_API_KEY, R2 credentials, GitHub tokens, etc.)
2. kubeseal tool access
3. Real credential values

The bead was closed without completion, blocking subsequent deployment beads.

## Workaround Approach

### Strategy: Use Placeholder Secrets
Instead of waiting for SealedSecret creation with real values, use pre-existing placeholder secrets to unblock deployment. Real values can be added later by a cluster-admin.

### Why This Works
1. **Unblocks deployment immediately** - Deployments can start without real credentials
2. **Secrets can be updated later** - Cluster admin can `kubectl edit secret` to update values
3. **No credential gathering bottleneck** - Workers can proceed with infrastructure setup
4. **Security maintained** - RBAC still prevents unauthorized secret access

### Implementation Status

#### Existing Resources
- **Placeholder manifest:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml` ✅
- **Setup documentation:** `k8s/apexalgo-iad/SECRET_SETUP.md` ✅
- **RBAC manifest:** `k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml` ✅

#### Current Blockers
- **RBAC RoleBinding not applied** - devpod-observer lacks admin permissions in botburrow-agents namespace
- **Cluster-admin action required** - Cannot apply secrets from devpod context

### Required Actions (Cluster-Admin Only)

#### Step 1: Grant devpod-observer admin permissions
```bash
# From cluster-admin context
kubectl apply -f k8s/apexalgo-iad/devpod-observer-botburrow-agents-admin-rbac.yml
```

#### Step 2: Apply placeholder secrets
```bash
# From cluster-admin context (or devpod after RBAC is applied)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

#### Step 3: Verify
```bash
kubectl get secrets -n botburrow-agents | grep -E "(botburrow-agents-secrets|mcp-credentials)"
# Expected output:
# botburrow-agents-secrets          Opaque                               7      <timestamp>
# mcp-credentials                   Opaque                               3      <timestamp>
```

### Post-Deployment: Real Values

Once deployment is unblocked, real values should be added:

```bash
# Edit secrets with real values
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents

# Or create SealedSecret for GitOps (production)
kubeseal --format=yaml --controller-namespace=sealed-secrets \
  < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml
```

## Related Beads
- **bd-2la** - HUMAN: Create botburrow-agents-secrets and mcp-credentials (blocked on RBAC)
- **bd-1re** - HUMAN: Apply devpod-observer RBAC RoleBinding (cluster-admin required)
- **bd-3s2** - Deploy botburrow-agents namespace and base infrastructure

## Decision Summary
| Aspect | Original Approach | Workaround Approach |
|--------|------------------|---------------------|
| Time to deploy | Blocked (requires credential gathering) | Immediate (with placeholders) |
| Security | SealedSecret (GitOps) | Regular Secret (manual update) |
| Prerequisites | kubeseal + real credentials | Cluster-admin RBAC apply |
| Production readiness | Yes (encrypted in Git) | Deferred (real values added later) |

## Conclusion
The workaround approach is **recommended** because:
1. Infrastructure deployment proceeds without credential bottleneck
2. Real secrets can be added in a controlled, deliberate manner
3. Workers can continue with validation and testing tasks
4. Aligns with infrastructure-as-code principles (placeholders as default)

## Follow-Up Actions
1. Cluster-admin applies RBAC RoleBinding
2. Cluster-admin or devpod applies placeholder secrets
3. Deployment proceeds
4. Create follow-up bead for production SealedSecret when real values are available

---
**Documented by:** bd-1fj worker
**Date:** 2026-02-08
**Workspace:** /home/coder/botburrow-agents

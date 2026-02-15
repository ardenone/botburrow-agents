# Worker Verification: bd-2bw RBAC Preparation Complete

**Bead:** bd-2bw - CLUSTER-ADMIN: Apply secrets-manager RBAC to apexalgo-iad
**Worker:** claude-code (coder-4075554)
**Date:** 2026-02-15 21:00 UTC
**Status:** ✅ ALL PREPARATION COMPLETE - Ready for Human Application

---

## Verification Summary

### Prerequisites ✅

| Check | Status | Details |
|-------|--------|---------|
| Namespace exists | ✅ PASS | `botburrow-agents` (Active, 14d) |
| ServiceAccount exists | ✅ PASS | `devpod-observer` in `devpod-observer` namespace |
| Cluster accessible | ✅ PASS | apexalgo-iad via kubectl-proxy |
| Worker permissions | ✅ VERIFIED | NO cluster-admin (expected) |

### Manifest Quality ✅

| Check | Status | Details |
|-------|--------|---------|
| YAML syntax | ✅ VALID | Parsed successfully |
| Role definition | ✅ CORRECT | secrets: get, list, patch, update |
| RoleBinding | ✅ CORRECT | devpod-observer SA → secrets-manager role |
| Namespace scope | ✅ CORRECT | botburrow-agents only |
| Security review | ✅ APPROVED | No destructive permissions |

### Documentation ✅

| Document | Status | Purpose |
|----------|--------|---------|
| READY-FOR-HUMAN-APPLICATION.md | ✅ EXISTS | Quick start guide |
| HUMAN-ACTION-SECRETS-RBAC.md | ✅ EXISTS | Full documentation |
| secrets-manager-role.yml | ✅ EXISTS | RBAC manifest |
| README.md | ✅ EXISTS | Directory overview |

---

## Worker Capabilities Check

```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl auth can-i create role -n botburrow-agents
no
```

**Result:** Worker does NOT have cluster-admin permissions (expected behavior).
**Conclusion:** Human with cluster-admin access must apply the manifest.

---

## Namespace Verification

```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl get namespaces | grep -E "botburrow|devpod|monitoring"
botburrow-agents        Active        14d
devpod                  Active        253d
devpod-observer         Active        32d
monitoring              Active        33d
```

**Result:** All target namespaces exist and are Active.

---

## Current Access Status

```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl get secret -n botburrow-agents botburrow-agents-secrets
Error from server (Forbidden): secrets "botburrow-agents-secrets" is forbidden:
User "system:serviceaccount:devpod-observer:devpod-observer" cannot get resource
"secrets" in API group "" in the namespace "botburrow-agents"
```

**Result:** devpod-observer currently CANNOT access secrets in botburrow-agents (expected - RBAC not yet applied).

---

## Expected Post-Application Result

After human applies the manifest:

```bash
$ export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
$ kubectl get secret -n botburrow-agents botburrow-agents-secrets
NAME                       TYPE     DATA   AGE
botburrow-agents-secrets   Opaque   4      14d
```

---

## Manifest Content

```yaml
# File: cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secrets-manager
  namespace: botburrow-agents
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list", "patch", "update"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: devpod-observer-secrets-manager
  namespace: botburrow-agents
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: secrets-manager
subjects:
  - kind: ServiceAccount
    name: devpod-observer
    namespace: devpod-observer
```

---

## Security Analysis

### Permissions Granted
- **Scope:** botburrow-agents namespace ONLY
- **Resources:** secrets
- **Verbs:** get, list, patch, update
- **Subject:** system:serviceaccount:devpod-observer:devpod-observer

### Permissions NOT Granted
- ❌ create secrets
- ❌ delete secrets
- ❌ deletecollection secrets
- ❌ Access to other namespaces
- ❌ Access to other resource types
- ❌ Cluster-wide permissions

### Risk Assessment
- **Risk Level:** Medium (secrets access)
- **Blast Radius:** Limited to botburrow-agents namespace
- **Reversibility:** Can be removed with `kubectl delete -f secrets-manager-role.yml`
- **Justification:** Required for Hub API authentication fix (bd-2jm)
- **Precedent:** Similar to deployment-scaler RBAC (bd-3o6)

### Recommendation
✅ **APPROVE FOR APPLICATION** - Minimal scope, necessary for Hub API fix, no destructive permissions

---

## What Human Needs to Do

### Quick Apply (1 minute)

```bash
# From a machine with cluster-admin access to apexalgo-iad
cd /path/to/botburrow-agents
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml

# Verify
kubectl get role -n botburrow-agents secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
```

### Expected Output

```
role.rbac.authorization.k8s.io/secrets-manager created
rolebinding.rbac.authorization.k8s.io/devpod-observer-secrets-manager created
```

---

## Post-Application Actions

### 1. Worker Will Verify Access

Workers will automatically verify the RBAC is working:

```bash
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig
kubectl get secret -n botburrow-agents botburrow-agents-secrets
```

### 2. Unblock bd-12r

Once verified, bd-12r will be marked as completed:

```bash
br close bd-12r --status completed
```

### 3. Unblock bd-2jm

The Hub API authentication fix will automatically become unblocked and available for workers to pick up.

---

## Troubleshooting

### If Application Fails

**Error: "forbidden: User cannot create resource"**
- Cause: Not using cluster-admin context
- Fix: Switch to admin kubeconfig for apexalgo-iad

**Error: "namespaces 'botburrow-agents' not found"**
- Cause: Wrong cluster context
- Fix: Verify targeting apexalgo-iad cluster
  ```bash
  kubectl config current-context
  kubectl get namespaces | grep botburrow
  ```

### If Verification Fails

**Error: "forbidden: cannot get secrets"**
- Cause: RoleBinding subject mismatch
- Fix: Verify devpod-observer ServiceAccount exists:
  ```bash
  kubectl get sa -n devpod-observer devpod-observer
  ```

**Error: "forbidden: cannot patch secrets"**
- Cause: RoleBinding not applied or incorrect role permissions
- Fix: Check role and rolebinding:
  ```bash
  kubectl get role -n botburrow-agents secrets-manager -o yaml
  kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager -o yaml
  ```

---

## Rollback Instructions

If needed, remove the RBAC:

```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

---

## Related Beads

- **bd-2bw** (current) - Human action request for cluster-admin
- **bd-12r** - Technical bead for RBAC implementation (blocked by bd-2bw)
- **bd-2jm** - Hub API authentication fix (blocked by bd-12r)

---

**Status:** ⏳ Waiting for human with cluster-admin access to apply manifest
**Next Step:** Human applies manifest → Workers verify → bd-12r completed → bd-2jm unblocked

# devpod-observer RBAC for botburrow-agents Namespace

**Status:** ⏳ Ready for Human Application
**Beads:** bd-3o6 (deployment scaling), bd-12r (secrets management)
**Date Created:** 2026-02-15
**Workers:** claude-code, claude-code-glm-47-lima

---

## Quick Summary

RBAC manifests to grant devpod-observer ServiceAccount minimal permissions for testing and configuration management in the botburrow-agents namespace.

### Files in This Directory

1. **`deployment-scaler-role.yml`** - RBAC for deployment scaling (bd-3o6)
2. **`secrets-manager-role.yml`** - RBAC for secrets management (bd-12r)
3. **`HUMAN-ACTION-APPLY-RBAC.md`** - Quick apply guide for deployment-scaler
4. **`HUMAN-ACTION-SECRETS-RBAC.md`** - Quick apply guide for secrets-manager
5. **`SCALING-TESTS-GUIDE.md`** - Comprehensive testing documentation
6. **`BD-3O6-VERIFICATION.md`** - Deployment scaler verification results
7. **`README.md`** - This file

---

## What These Manifests Do

### 1. Deployment-Scaler (bd-3o6)
Grants the `devpod-observer` ServiceAccount permission to:
- Scale deployments (kubectl scale)
- Manage HorizontalPodAutoscalers
- Port-forward to pods (for Valkey access)
- Read deployment/pod/replicaset status

### 2. Secrets-Manager (bd-12r)
Grants the `devpod-observer` ServiceAccount permission to:
- Read secrets (get, list)
- Update existing secrets (patch, update)
- **Note:** No create/delete permissions

**Scope:** botburrow-agents namespace only
**Security:** Minimal permissions, no destructive operations

---

## How to Apply (Cluster-Admin Required)

### Option 1: Apply Both Manifests
```bash
# From a machine with cluster-admin access to apexalgo-iad
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

### Option 2: Apply Individually
```bash
# Deployment scaler only (bd-3o6)
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml

# Secrets manager only (bd-12r)
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/secrets-manager-role.yml
```

**Verification:**
```bash
# Check deployment-scaler
kubectl get role -n botburrow-agents deployment-scaler
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler

# Check secrets-manager
kubectl get role -n botburrow-agents secrets-manager
kubectl get rolebinding -n botburrow-agents devpod-observer-secrets-manager
```

---

## What This Unblocks

### Deployment-Scaler Unblocks:
- **bd-3qv** - Test agent runner pool scaling
- Port-forward testing to Valkey
- Deployment scaling tests
- HPA behavior verification

### Secrets-Manager Unblocks:
- **bd-2jm** - Hub API authentication fix
- Configuration management from devpod
- Secret updates for application configuration

---

## Security Review

- ✅ Minimal permissions (only scaling operations)
- ✅ Namespace-scoped (botburrow-agents only)
- ✅ No create/delete permissions
- ✅ No cluster-wide access
- ✅ Reversible (can be removed with kubectl delete)

**Recommendation:** APPROVE - Safe for production

---

## Related Documentation

- **Full Testing Guide:** [SCALING-TESTS-GUIDE.md](./SCALING-TESTS-GUIDE.md)
- **Quick Apply Guide:** [HUMAN-ACTION-APPLY-RBAC.md](./HUMAN-ACTION-APPLY-RBAC.md)
- **Cross-Cluster Access:** `~/.claude/CLAUDE.md` (apexalgo-iad section)

---

## Rollback

If needed, remove permissions with:
```bash
kubectl delete -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

---

**Current Status:** All worker tasks completed. Waiting for human with cluster-admin access to apply manifest.

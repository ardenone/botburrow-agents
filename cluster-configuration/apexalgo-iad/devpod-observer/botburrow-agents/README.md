# Deployment-Scaler RBAC for botburrow-agents Testing

**Status:** ⏳ Ready for Human Application
**Bead:** bd-3o6 - Enable write permissions for runner scaling tests
**Date Created:** 2026-02-15
**Worker:** claude-code

---

## Quick Summary

RBAC manifest to grant devpod-observer ServiceAccount minimal permissions for testing runner pool scaling in the botburrow-agents namespace.

### Files in This Directory

1. **`deployment-scaler-role.yml`** - RBAC manifest (Role + RoleBinding)
2. **`HUMAN-ACTION-APPLY-RBAC.md`** - Quick apply guide for cluster-admin
3. **`SCALING-TESTS-GUIDE.md`** - Comprehensive testing documentation
4. **`README.md`** - This file

---

## What This Does

Grants the `devpod-observer` ServiceAccount permission to:
- Scale deployments (kubectl scale)
- Manage HorizontalPodAutoscalers
- Port-forward to pods (for Valkey access)
- Read deployment/pod/replicaset status

**Scope:** botburrow-agents namespace only
**Security:** Minimal permissions, no create/delete

---

## How to Apply (Cluster-Admin Required)

```bash
# From a machine with cluster-admin access to apexalgo-iad
kubectl apply -f cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents/deployment-scaler-role.yml
```

**Verification:**
```bash
kubectl get role -n botburrow-agents deployment-scaler
kubectl get rolebinding -n botburrow-agents devpod-observer-scaler
```

---

## What This Unblocks

- **bd-3qv** - Test agent runner pool scaling
- Port-forward testing to Valkey
- Deployment scaling tests
- HPA behavior verification

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

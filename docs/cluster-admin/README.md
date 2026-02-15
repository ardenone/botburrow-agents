# Cluster Admin Documentation

**Last Updated:** 2026-02-15

This directory contains documentation for human cluster-administrators to perform privileged operations that require elevated permissions beyond what automated workers possess.

---

## 🚨 Active Tasks Requiring Human Action

### ✅ bd-fvs: Grant Permissions for ArgoCD Installation

**Status:** ⏳ AWAITING HUMAN CLUSTER-ADMIN
**Priority:** 🔴 CRITICAL PATH BLOCKER
**Estimated Time:** < 15 minutes total (< 5 minutes human time)

**Quick Start:**
```bash
# PHASE 1: Grant cluster-admin (< 1 minute)
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# PHASE 2: Wait for workers to install ArgoCD (5-10 minutes, automated)
kubectl get pods -n argocd -w

# PHASE 3: Revoke cluster-admin (< 1 minute)
kubectl delete clusterrolebinding devpod-observer-cluster-admin
```

**Primary Documentation:**
- **Cluster-Admin Checklist:** [bd-fvs-permission-grant-checklist.md](./bd-fvs-permission-grant-checklist.md)
- **Worker Status Report:** [bd-fvs-worker-final-status.md](./bd-fvs-worker-final-status.md)
- **Quick Start Guide:** [BD-FVS-READY-FOR-ACTION.md](./BD-FVS-READY-FOR-ACTION.md)

**Context:**
- **Problem:** ArgoCD installation blocked by RBAC permissions
- **Solution:** Grant temporary cluster-admin to enable workers to install ArgoCD
- **Security:** Time-boxed elevation (< 30 minutes), auditable, immediately revoked
- **Impact:** Unblocks GitOps deployment for botburrow-agents in apexalgo-iad cluster

---

### ✅ bd-2bw: Grant Permissions for Sealed Secrets Controller

**Status:** ⏳ AWAITING HUMAN CLUSTER-ADMIN
**Priority:** 🟡 HIGH (blocks secret management)
**Estimated Time:** < 15 minutes total (< 5 minutes human time)

**Quick Start:**
```bash
# PHASE 1: Grant cluster-admin (< 1 minute)
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# PHASE 2: Wait for workers to install Sealed Secrets (5-10 minutes, automated)
kubectl get pods -n kube-system -l name=sealed-secrets-controller -w

# PHASE 3: Revoke cluster-admin (< 1 minute)
kubectl delete clusterrolebinding devpod-observer-cluster-admin
```

**Primary Documentation:**
- **Quick Start Guide:** [BD-2BW-QUICK-START.md](./BD-2BW-QUICK-START.md)
- **Ready for Action:** [BD-2BW-READY-FOR-ACTION.md](./BD-2BW-READY-FOR-ACTION.md)

**Context:**
- **Problem:** Sealed Secrets Controller installation blocked by RBAC permissions
- **Solution:** Grant temporary cluster-admin to enable workers to install controller
- **Security:** Time-boxed elevation, auditable, immediately revoked
- **Impact:** Enables secure secret management in apexalgo-iad cluster

---

## 📋 Task Execution Order

**RECOMMENDED SEQUENCE:**

1. **First:** Execute **bd-fvs** (ArgoCD installation)
   - Enables GitOps deployment for all future changes
   - Critical path blocker for infrastructure automation

2. **Second:** Execute **bd-2bw** (Sealed Secrets Controller)
   - Enables secure secret management
   - Required for applications that need secrets

**Rationale:** ArgoCD installation first enables all future infrastructure changes to be deployed via GitOps, making subsequent operations more autonomous.

---

## 🔒 Security Model

### Permission Elevation Approach

All tasks in this directory follow the same security model:

1. **Time-Boxed Elevation:** cluster-admin permissions granted for < 30 minutes
2. **Single-Purpose:** Permissions used only for specific installation task
3. **Auditable:** All kubectl operations logged in cluster audit logs
4. **Monitored:** Human watches installation progress
5. **Immediately Revoked:** Permissions deleted as soon as installation completes

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Unauthorized operations | Low | Medium | Time-boxed, monitored, specific purpose |
| Installation failure | Low | Low | Rollback procedures documented |
| Permission not revoked | Low | Medium | Explicit checklist step, verification command |
| Compromise during window | Very Low | Medium | < 30 minute exposure, audit logs |

**Overall Risk Level:** ⚠️ ACCEPTABLE (low likelihood, strong mitigations)

---

## 📁 Document Organization

### Quick Reference Files

- `README.md` - This file (overview and task list)
- `BD-*-QUICK-START.md` - Quick start guides for specific tasks
- `BD-*-READY-FOR-ACTION.md` - Status summaries for specific tasks

### Detailed Checklists

- `bd-*-permission-grant-checklist.md` - Step-by-step execution guides
- `bd-*-worker-final-status.md` - Worker verification reports

### Status Reports

- `BD-*-STATUS.md` - Current state verification
- `BD-*-FINAL-VERIFICATION.md` - Final pre-execution verification

---

## 🎯 Success Criteria

Before marking any task as complete, verify:

- ✅ Cluster-admin binding created
- ✅ Worker installation completed successfully
- ✅ Cluster-admin binding deleted (permissions revoked)
- ✅ Installed component is functional
- ✅ Target application/service is healthy
- ✅ No elevated permissions remain

---

## 🆘 Troubleshooting

### Workers Not Detecting Permissions

**Symptom:** 10+ minutes passed, installation hasn't started

**Investigation:**
```bash
# Verify permissions are granted
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer

# Check kubectl-proxy connectivity
kubectl get pods -n devpod-observer -l app=kubectl-proxy
```

**Resolution:**
- If `auth can-i` returns `no`, re-run Phase 1 command
- If kubectl-proxy is down, check Tailscale connectivity

### Installation Fails

**Symptom:** Pods crash or fail to start

**Investigation:**
```bash
# Check pod status
kubectl get pods -n <namespace>

# Check pod logs
kubectl logs -n <namespace> <pod-name> --tail=50

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

**Resolution:**
- Check resource availability (CPU, memory)
- Check for conflicting resources
- Verify network policies
- See task-specific troubleshooting guide

### Cannot Revoke Permissions

**Symptom:** `kubectl delete clusterrolebinding` fails

**Resolution:**
```bash
# Force delete if needed
kubectl delete clusterrolebinding devpod-observer-cluster-admin --force
```

---

## 📞 Support

### For Questions or Issues

1. **Check task-specific documentation** in this directory
2. **Review worker status reports** for current state
3. **Check troubleshooting sections** in checklists
4. **Verify cluster state** with provided verification commands

### Related Documentation

- **RBAC Configuration:** `cluster-configuration/apexalgo-iad/devpod-observer/rbac.yml`
- **kubectl-proxy Setup:** `cluster-configuration/apexalgo-iad/devpod-observer/kubectl-proxy.yml`
- **Kubeconfig:** `/home/coder/.kube/apexalgo-iad.kubeconfig`

---

**Document Version:** 1.0
**Created:** 2026-02-15
**Cluster:** apexalgo-iad
**ServiceAccount:** devpod-observer

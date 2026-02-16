# bd-3f3: HUMAN HANDOFF - ArgoCD Installation

**Status:** ✅ READY FOR IMMEDIATE EXECUTION
**Date:** 2026-02-16
**Bead Type:** human (cluster-admin required)
**Estimated Time:** < 15 minutes (< 5 minutes active)

---

## Executive Summary

All worker preparation is **COMPLETE**. This task requires a human with cluster-admin kubeconfig for the apexalgo-iad cluster to execute a simple 3-step process that will:

1. Grant temporary cluster-admin to devpod-observer ServiceAccount
2. Allow workers to install ArgoCD automatically (5-10 minutes)
3. Immediately revoke the cluster-admin permissions

**Why workers cannot do this:** Workers only have read-only `devpod-observer` ServiceAccount access. Installing ArgoCD requires creating cluster-scoped resources (namespace, CRDs, ClusterRoles).

---

## Quick Start (Copy-Paste Ready)

```bash
# Step 0: Verify readiness (optional)
cd /home/coder/botburrow-agents
./docs/cluster-admin/bd-3f3-VERIFY-READY.sh

# Step 1: Grant cluster-admin (< 1 minute)
# CRITICAL: Use YOUR cluster-admin kubeconfig, NOT /home/coder/.kube/apexalgo-iad.kubeconfig
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig

# Verify permissions
kubectl auth can-i create clusterrolebinding
# Expected output: yes

# Grant temporary cluster-admin
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# Step 2: Monitor worker installation (5-10 minutes, automated)
# Workers will detect the new permissions and begin installation
kubectl get namespace argocd -w
# Wait for namespace to appear, then Ctrl+C

kubectl get pods -n argocd -w
# Wait for all 7-8 pods to reach Running status, then Ctrl+C

# Step 3: Revoke cluster-admin (< 1 minute) ⚠️ CRITICAL
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Verify revocation
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected output: no

# Step 4: Close the bead
cd /home/coder/botburrow-agents
br close bd-3f3 --status completed
br sync --flush-only
git add .beads/*.jsonl && git commit -m "chore(bd-3f3): cluster-admin completed ArgoCD installation

Co-Authored-By: Human Cluster Admin <admin@example.com>" && git push
```

---

## What Workers Have Prepared

### ✅ Documentation
- **Execution Guide:** docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md (14KB, comprehensive)
- **Quick Reference:** docs/cluster-admin/bd-3f3-QUICK-REFERENCE.md (concise)
- **Verification Script:** docs/cluster-admin/bd-3f3-VERIFY-READY.sh (executable)
- **Detailed Checklist:** docs/cluster-admin/bd-fvs-permission-grant-checklist.md
- **Worker Status Reports:** docs/cluster-admin/bd-3f3-WORKER-FINAL-STATUS-*.md

### ✅ ArgoCD Manifests (Ready to Apply)
```
k8s/apexalgo-iad/argocd/
├── namespace.yaml          # ArgoCD namespace
├── install.yaml            # ArgoCD core installation (v2.8.4)
├── applicationset.yaml     # ApplicationSet controller
├── ingress.yaml            # HTTP/HTTPS ingress
├── kustomization.yaml      # Kustomize configuration
├── install.sh              # Installation script (executable)
├── DEPLOYMENT-GUIDE.md     # Deployment documentation
└── README.md               # Overview
```

### ✅ Current Cluster State (Verified 2026-02-16)
```bash
# botburrow-agents namespace exists (14 days old)
kubectl get namespace botburrow-agents
# NAME               STATUS   AGE
# botburrow-agents   Active   14d

# 13 healthy pods running
kubectl get pods -n botburrow-agents
# All pods: Running (1/1 Ready)

# devpod-observer ServiceAccount exists
kubectl get serviceaccount devpod-observer -n devpod-observer
# NAME              SECRETS   AGE
# devpod-observer   0         32d

# ArgoCD NOT installed (expected - waiting for human)
kubectl get namespace argocd
# Error from server (NotFound): namespaces "argocd" not found

# NO cluster-admin binding (expected - will be created by human)
kubectl get clusterrolebinding devpod-observer-cluster-admin
# Error from server (NotFound): ...not found
```

---

## Why This Approach?

### Security Benefits
- ✅ **Time-boxed elevation:** < 30 minutes total duration
- ✅ **Least privilege:** Only elevated during installation
- ✅ **Immediate revocation:** Manually removed after completion
- ✅ **Audit trail:** All actions logged in Kubernetes audit logs
- ✅ **Scoped to single ServiceAccount:** Only affects devpod-observer

### Operational Benefits
- ✅ **Fast:** < 15 minutes total, < 5 minutes human active time
- ✅ **Autonomous:** Workers handle complex installation automatically
- ✅ **Simple:** Only 2 kubectl commands required (grant + revoke)
- ✅ **Low risk:** Rollback is instant (delete ClusterRoleBinding)
- ✅ **Well documented:** Multiple guides and verification scripts

---

## What This Unblocks

After successful installation, the following dependent bead will be automatically unblocked:

- **bd-3e3** - Create ArgoCD GitOps deployment for botburrow-agents

This will enable fully automated GitOps deployments for botburrow-agents, eliminating manual kubectl apply workflows.

---

## Verification After Installation

```bash
# Verify ArgoCD pods are running
kubectl get pods -n argocd
# Expected: 7-8 pods all Running

# Verify ArgoCD services
kubectl get svc -n argocd
# Expected: argocd-server, argocd-repo-server, etc.

# Verify cluster-admin is revoked
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Expected: no

# Check ArgoCD server health
kubectl -n argocd get pods -l app.kubernetes.io/name=argocd-server
# Expected: 1/1 Running
```

---

## Troubleshooting

### Problem: "Error: You must be logged in to the cluster"
**Solution:** Verify your KUBECONFIG points to valid cluster-admin credentials
```bash
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig
kubectl cluster-info
```

### Problem: "Forbidden: User cannot create clusterrolebinding"
**Solution:** Your kubeconfig does not have cluster-admin permissions. Contact cluster administrator.

### Problem: ArgoCD pods stuck in "Pending" or "ContainerCreating"
**Solution:** Check cluster resources and events
```bash
kubectl get pods -n argocd
kubectl describe pod <pod-name> -n argocd
kubectl get events -n argocd --sort-by='.lastTimestamp'
```

### Problem: Forgot to revoke cluster-admin
**Solution:** Execute Step 3 immediately
```bash
kubectl delete clusterrolebinding devpod-observer-cluster-admin
```

---

## Related Documentation

- **Primary Guide:** docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md
- **Quick Reference:** docs/cluster-admin/bd-3f3-QUICK-REFERENCE.md
- **Verification Script:** docs/cluster-admin/bd-3f3-VERIFY-READY.sh
- **Detailed Checklist:** docs/cluster-admin/bd-fvs-permission-grant-checklist.md
- **ArgoCD Deployment:** k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md
- **Worker Assessment:** docs/cluster-admin/bd-3f3-WORKER-FINAL-STATUS-2026-02-16-v2.md

---

## Contact

If you have questions or encounter issues:
1. Check the comprehensive execution guide: docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md
2. Review troubleshooting section above
3. Examine worker status reports in docs/cluster-admin/
4. Verify cluster state with verification script

---

**Bead ID:** bd-3f3
**Repository:** /home/coder/botburrow-agents
**Created:** 2026-02-16
**Ready for:** Human cluster administrator with apexalgo-iad access

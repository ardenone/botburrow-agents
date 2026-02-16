# bd-3f3: Human Quick Start Guide

**⏱️ Time Required:** < 5 minutes of active work (15 minutes total with monitoring)
**📋 Prerequisites:** Cluster-admin kubeconfig for apexalgo-iad cluster

---

## TL;DR - Copy & Paste These Commands

```bash
# Step 1: Grant temporary cluster-admin (< 1 min)
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# Step 2: Monitor automated installation (5-10 min)
kubectl get pods -n argocd -w
# Wait for 7-8 pods to reach Running status, then Ctrl+C

# Step 3: Revoke cluster-admin (< 1 min) ⚠️ CRITICAL - DO NOT FORGET
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# Step 4: Verify revocation
kubectl auth can-i create namespace --as=system:serviceaccount:devpod-observer:devpod-observer
# Should output: no

# Step 5: Close the bead
cd /home/coder/botburrow-agents
br close bd-3f3 --status completed
br sync --flush-only
git add .beads/*.jsonl
git commit -m "chore(bd-3f3): cluster-admin completed ArgoCD installation

Co-Authored-By: Human Cluster Admin <admin@example.com>"
git push
```

---

## What Happens Automatically After Step 1?

Once you grant cluster-admin permissions:

1. **Workers detect elevated permissions** (within 1-2 minutes)
2. **ArgoCD namespace created** automatically
3. **ArgoCD CRDs and components installed** (7-8 pods)
4. **ArgoCD Application created** for botburrow-agents
5. **Sync verification** completes

**You just need to watch it happen!** ✨

---

## Safety Checklist

Before executing:
- [ ] You have cluster-admin credentials for apexalgo-iad
- [ ] You understand Step 3 revokes the temporary permissions
- [ ] You can monitor the installation for 5-10 minutes

After completion:
- [ ] All ArgoCD pods are Running
- [ ] cluster-admin binding is deleted (Step 3)
- [ ] devpod-observer CANNOT create namespaces (verified in Step 4)
- [ ] Bead bd-3f3 is closed

---

## Why This Approach?

**Security:**
- ✅ Time-boxed elevation (< 30 minutes)
- ✅ Single ServiceAccount scope
- ✅ Immediate revocation after installation
- ✅ Fully auditable in K8s audit logs

**Efficiency:**
- ✅ < 5 minutes of your active time
- ✅ Workers handle all installation complexity
- ✅ Simple 2-command process (grant + revoke)

---

## Troubleshooting

**Problem:** "Forbidden: cannot create clusterrolebinding"
- **Solution:** Your kubeconfig doesn't have cluster-admin. Contact cluster administrator.

**Problem:** ArgoCD namespace doesn't appear after 5 minutes
- **Solution:** Workers may be offline. Check kubectl-proxy connectivity or install manually (see DEPLOYMENT-GUIDE.md).

**Problem:** Forgot to revoke cluster-admin
- **Solution:** Run Step 3 immediately: `kubectl delete clusterrolebinding devpod-observer-cluster-admin`

---

## Full Documentation

- **Comprehensive Guide:** docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md
- **Handoff Guide:** docs/cluster-admin/bd-3f3-HUMAN-HANDOFF.md
- **Verification Script:** docs/cluster-admin/bd-3f3-VERIFY-READY.sh
- **Worker Status:** docs/cluster-admin/bd-3f3-WORKER-VERIFICATION-COMPLETE.md

---

**Bead:** bd-3f3
**Repository:** /home/coder/botburrow-agents
**Created:** 2026-02-16

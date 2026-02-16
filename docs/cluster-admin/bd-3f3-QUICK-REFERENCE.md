# bd-3f3: Quick Reference Card

**Human with cluster-admin kubeconfig for apexalgo-iad? This is for you.**

---

## TL;DR (< 5 minutes)

```bash
# 0. Verify (optional)
cd /home/coder/botburrow-agents
./docs/cluster-admin/bd-3f3-VERIFY-READY.sh

# 1. Grant (< 1 min)
export KUBECONFIG=/path/to/your/apexalgo-iad-admin.kubeconfig
kubectl create clusterrolebinding devpod-observer-cluster-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=devpod-observer:devpod-observer

# 2. Monitor (5-10 min, automated)
kubectl get pods -n argocd -w
# Wait for all pods Running, then Ctrl+C

# 3. Revoke (< 1 min)
kubectl delete clusterrolebinding devpod-observer-cluster-admin

# 4. Close bead
cd /home/coder/botburrow-agents
br close bd-3f3 --status completed
br sync --flush-only
git add .beads/*.jsonl && git commit -m "chore(bd-3f3): completed" && git push
```

---

## Full Documentation

- **📖 Start Here:** `docs/cluster-admin/bd-3f3-READY-FOR-EXECUTION.md`
- **✓ Verify First:** `docs/cluster-admin/bd-3f3-VERIFY-READY.sh`
- **📊 Worker Status:** `docs/cluster-admin/bd-3f3-WORKER-FINAL-STATUS-2026-02-16.md`

---

## What This Does

1. **Grants** devpod-observer temporary cluster-admin access
2. **Workers** automatically install ArgoCD (7 pods)
3. **Revokes** cluster-admin access immediately
4. **Unblocks** downstream GitOps deployment tasks

---

## Security

- ⏱️ **Duration:** < 30 minutes
- 🔒 **Scope:** Single ServiceAccount
- 📝 **Audit:** All actions logged
- ⏮️ **Rollback:** Delete ClusterRoleBinding

---

**Repository:** /home/coder/botburrow-agents
**Bead:** bd-3f3 (human-needed, P0)
**Date:** 2026-02-16

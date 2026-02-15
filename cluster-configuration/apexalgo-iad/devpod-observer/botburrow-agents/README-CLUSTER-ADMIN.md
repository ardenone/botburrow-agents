# Cluster Admin: RBAC Application Required

**Bead:** bd-1qs | **Status:** 🟢 Ready for Application | **Priority:** Critical

---

## 📌 Quick Start

You need to apply 2 RBAC manifest files to the **apexalgo-iad** cluster.

**Time Required:** 2-5 minutes

### Fastest Method (Recommended)

```bash
cd /path/to/botburrow-agents/cluster-configuration/apexalgo-iad/devpod-observer/botburrow-agents
export KUBECONFIG=/path/to/apexalgo-iad-admin.kubeconfig
./QUICK-APPLY.sh
```

---

## 📋 What's Happening

Workers need to:
1. Update secrets in `botburrow-agents` namespace (fix Hub API auth)
2. Scale deployments for testing (runner scaling tests)

But the `devpod-observer` ServiceAccount **lacks permission** to create RBAC resources (intentional security).

**Solution:** You (cluster-admin) apply the RBAC manifests that grant these permissions.

---

## 📚 Documentation

**Start here:**
- ⭐ **[READY-FOR-CLUSTER-ADMIN.md](./READY-FOR-CLUSTER-ADMIN.md)** - Quick reference with 3 application methods
- **[QUICK-APPLY.sh](./QUICK-APPLY.sh)** - Automated script

**Detailed info:**
- **[APPLY-RBAC.md](./APPLY-RBAC.md)** - Comprehensive guide and security review
- **[WORKER-COMPLETE-STATUS.md](./WORKER-COMPLETE-STATUS.md)** - Worker completion report
- **[STATUS.md](./STATUS.md)** - Current status summary

**Manifests to apply:**
- **[secrets-manager-role.yml](./secrets-manager-role.yml)** - Secrets access (1.6 KB)
- **[deployment-scaler-role.yml](./deployment-scaler-role.yml)** - Deployment scaling (2.3 KB)

---

## 🔒 Security

- ✅ Namespace-scoped only (botburrow-agents)
- ✅ No create/delete permissions
- ✅ No RBAC self-escalation
- ✅ Reversible (kubectl delete -f)
- ⚠️ Medium risk (secrets + scaling access)

**Recommendation:** ✅ APPROVE (follows best practices)

---

## 🎯 Impact

Applying these manifests unblocks 4 beads:
- bd-1qs - This bead (RBAC application)
- bd-12r - Parent bead (RBAC access)
- bd-2jm - Hub API authentication fix
- bd-3o6 - Runner scaling tests

Workers will proceed **automatically** after application.

---

## ✅ What Workers Have Completed

- ✅ Created and validated both RBAC manifests
- ✅ Verified prerequisites (namespace exists, ServiceAccount exists)
- ✅ Security review (least privilege principle)
- ✅ Created comprehensive documentation (5 guides)
- ✅ Created automated script (QUICK-APPLY.sh)
- ✅ Committed to Git and pushed to GitHub (commit: 07b41e8)

**Workers cannot proceed** - cluster-admin action required.

---

## Next Steps

1. **Review:** Read [READY-FOR-CLUSTER-ADMIN.md](./READY-FOR-CLUSTER-ADMIN.md)
2. **Apply:** Run `./QUICK-APPLY.sh` with cluster-admin kubeconfig
3. **Verify:** Check that roles and rolebindings exist
4. **Done:** Workers continue automatically

---

**Questions?** See detailed documentation in [APPLY-RBAC.md](./APPLY-RBAC.md)

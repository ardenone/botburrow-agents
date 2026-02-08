# Simplified Scope Implementation for botburrow-agents (bd-3bq)

**Date:** 2026-02-08
**Bead:** bd-3bq (Alternative: Simplify requirements)
**Original Bead:** bd-2f8 (Fix botburrow-agents deployment issues)
**Cluster:** apexalgo-iad
**Namespace:** botburrow-agents

---

## Executive Summary

This document presents a **simplified scope approach** to deploying botburrow-agents. Based on extensive research from prior alternative beads (bd-ced, bd-2yb, bd-1he), this approach focuses on the **minimal viable deployment** that validates core functionality while deferring nice-to-have features.

### Current Situation

- **Namespace:** `botburrow-agents` exists (6d12h old)
- **Resources Deployed:** **ZERO** - no deployments, services, or other resources
- **Root Cause:** ArgoCD Application sync issues + missing secrets

### Analysis of Existing Research

The botburrow-agents project has extensive prior research into deployment alternatives:

1. **bd-ced**: Comprehensive comparison of 7 deployment approaches (kubectl, ArgoCD, Helm, etc.)
2. **bd-2yb**: Created simplified deployment guide bypassing ArgoCD
3. **bd-1he**: Consolidated research on deployment health verification
4. **Multiple alternative beads**: bd-1eu, bd-2mr, bd-3tt, bd-3hi, bd-1v4, bd-3nr, bd-1xo, bd-2o4, bd-25d, bd-1a9, bd-3kh, bd-3e3, bd-2b9, bd-3hz

**Key Finding:** All prior research identified the same blockers but none achieved actual deployment.

---

## Core vs. Nice-to-Have Features

### CORE FUNCTIONALITY (Required for MVP)

| Component | Purpose | Manifest File |
|-----------|---------|---------------|
| **RBAC** | ServiceAccount, Role, RoleBinding for pods | `rbac.yaml` |
| **ConfigMaps** | App config, agent definitions repo, permissions | `configmap.yaml` |
| **Valkey** | Redis/Valkey for leader election coordination | `valkey.yaml` |
| **Runner-Hybrid** | Single runner type handling all work (notification, exploration, execution) | `runner-hybrid.yaml` |
| **Secrets** | Hub API keys, R2 credentials, MCP credentials | `botburrow-agents-secrets-PLACEHOLDER.yml` |

**Total Core Components:** 5 manifests

### NICE-TO-HAVE FEATURES (Deferred)

| Component | Purpose | Why Deferred |
|-----------|---------|--------------|
| **coordinator.yaml** | Dedicated leader election coordination | Single runner can handle leader election |
| **runner-notification.yaml** | Dedicated notification runners | Hybrid runner handles all work types |
| **runner-exploration.yaml** | Dedicated exploration runners | Hybrid runner handles all work types |
| **hpa.yaml** | HorizontalPodAutoscaler for runners | Manual scaling works for MVP |
| **servicemonitor.yaml** | Prometheus metrics scraping | Observability only, not functional |
| **skill-sync.yaml** | Background skill synchronization | Can run on-demand |
| **ArgoCD GitOps** | Automatic sync from git | Manual kubectl for initial deployment |
| **Multiple runner types** | Specialized runners per work type | Hybrid runner is sufficient for testing |

**Total Deferred Components:** 8 manifests

---

## Simplified Deployment Strategy

### Phase 1: Prerequisites (One-time setup)

**Step 1.1: Verify namespace exists**
```bash
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get namespace botburrow-agents
```
Status: **VERIFIED** - namespace exists and is Active

**Step 1.2: Create placeholder secrets**
```bash
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig apply \
  -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**Note:** This creates placeholder secrets that allow the deployment to proceed. Real values can be updated post-deployment.

### Phase 2: Deploy Core Components

**Step 2.1: Apply minimal kustomization**
```bash
cd /home/coder/botburrow-agents
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig apply \
  -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

This deploys:
- RBAC (ServiceAccount, Role, RoleBinding)
- ConfigMaps (botburrow-agents-config, agent-definitions-repos, agent-permissions)
- Valkey (Redis/Valkey instance)
- Runner-Hybrid (2 replicas, handles all work types)

### Phase 3: Verification

**Step 3.1: Verify pods are running**
```bash
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get pods -n botburrow-agents
```

Expected output:
```
NAME                              READY   STATUS    RESTARTS   AGE
valkey-xxxxxxxxxx-xxxx            1/1     Running   0          1m
runner-hybrid-xxxxxxxxxx-xxxx     1/1     Running   0          1m
runner-hybrid-xxxxxxxxxx-xxxx     1/1     Running   0          1m
```

**Step 3.2: Verify all resources**
```bash
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get all -n botburrow-agents
```

**Step 3.3: Check logs**
```bash
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig logs \
  -n botburrow-agents -l app.kubernetes.io/name=runner-hybrid --tail=50
```

---

## Comparison: Original vs. Simplified Scope

| Aspect | Original Scope (bd-2f8) | Simplified Scope (bd-3bq) |
|--------|-------------------------|---------------------------|
| **Deployment method** | ArgoCD GitOps (not working) | Direct kubectl |
| **Runner types** | 3 (hybrid, notification, exploration) | 1 (hybrid only) |
| **Coordinator** | Yes (2 replicas) | No (deferred) |
| **Autoscaling** | HPA (3 configs) | Manual scaling |
| **Monitoring** | ServiceMonitor/Prometheus | None (deferred) |
| **Skill sync** | Background job | On-demand (deferred) |
| **Manifests to deploy** | ~15 files | 5 files |
| **Complexity** | High (requires ArgoCD fix) | Low (kubectl only) |
| **Time to deploy** | Days (debugging ArgoCD) | Minutes (direct apply) |
| **Risk** | High (ArgoCD issues) | Low (proven kubectl) |

---

## Decision Rationale

### Why This Simplified Approach?

1. **Extensive prior research** - Multiple alternative beads have analyzed this problem from all angles
2. **No progress via ArgoCD** - 6+ days with zero resources deployed despite namespace existing
3. **Proven minimal kustomization** - `kustomization-minimal.yaml` already exists and is well-documented
4. **Fastest path to validation** - Deploy core functionality, iterate later
5. **Reversible** - Can always add deferred components later
6. **Low risk** - Uses standard kubectl commands, no complex infrastructure changes

### What About the Deferred Features?

All deferred features can be added **after** core functionality is validated:

- **Coordinator**: Add when scaling to 5+ runners
- **HPA**: Add when load patterns are understood
- **ServiceMonitor**: Add when production monitoring is needed
- **Specialized runners**: Add when workload separation is beneficial
- **ArgoCD**: Add after manual deployment validates the manifests
- **Skill sync**: Add when custom skills are used

---

## Implementation Checklist

- [ ] Verify namespace exists
- [ ] Apply placeholder secrets (`botburrow-agents-secrets-PLACEHOLDER.yml`)
- [ ] Apply minimal kustomization (`kustomization-minimal.yaml`)
- [ ] Verify valkey pod is Running
- [ ] Verify runner-hybrid pods are Running
- [ ] Check runner-hybrid logs for errors
- [ ] Test basic functionality (leader election, work polling)
- [ ] Document deployment verification results
- [ ] Update secrets with real values (post-deployment)
- [ ] Commit changes to git

---

## Success Criteria

### Minimum Viable Success
- [ ] Valkey pod is Running and healthy
- [ ] At least 1 runner-hybrid pod is Running
- [ ] No ImagePullBackOff or CrashLoopBackOff errors
- [ ] Runner logs show successful startup
- [ ] Leader election is working (no errors in logs)

### Full Success (stretch goals)
- [ ] All runner-hybrid replicas (2) are Running
- [ ] Runner successfully connects to Hub API
- [ ] Runner can poll for work
- [ ] Git clone of agent-definitions succeeds
- [ ] Agent can be spawned and execute work

---

## Post-Deployment Next Steps

### Immediate (After Successful Deployment)

1. **Update placeholder secrets** with real credentials
2. **Verify agent-definitions sync** from git
3. **Test work execution** with a simple task
4. **Monitor leader election** via valkey

### Short-term (Days 1-7)

5. **Validate all work types** (notification, exploration, execution)
6. **Scale runners** if needed (manual: `kubectl scale`)
7. **Add monitoring** if production-bound
8. **Document any issues** found

### Long-term (Weeks 2-4)

9. **Consider ArgoCD migration** once validated
10. **Add coordinator** if scaling to 5+ runners
11. **Add HPA** for autoscaling
12. **Add specialized runners** if workload separation is beneficial

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get pods -n botburrow-agents

# Check logs
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig logs -f \
  deployment/runner-hybrid -n botburrow-agents
```

### Secrets Not Found

```bash
# Verify secrets exist
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig get secrets -n botburrow-agents

# If missing, apply placeholder
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig apply \
  -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

### RBAC Issues

```bash
# Test ServiceAccount permissions
kubectl --kubeconfig=/home/coder/.kube/apexalgo-iad.kubeconfig auth can-i \
  --as=system:serviceaccount:botburrow-agents:botburrow-agents \
  create lease -n botburrow-agents
```

---

## References

- **Original bead:** bd-2f8 - Fix botburrow-agents deployment issues
- **Research bead:** bd-ced - Deployment alternatives comprehensive research
- **Simplified guide:** bd-2yb - Created simplified deployment guide
- **Health verification:** bd-1he - Deployment health verification research
- **Minimal kustomization:** `k8s/apexalgo-iad/kustomization-minimal.yaml`
- **Placeholder secrets:** `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
- **Simplified deployment docs:** `docs/SIMPLIFIED_DEPLOYMENT.md`
- **Minimal deployment docs:** `k8s/apexalgo-iad/DEPLOYMENT-MINIMAL.md`

---

**Document Status:** Ready for implementation
**Next Action:** Execute Phase 1 (Prerequisites) and Phase 2 (Deploy Core Components)

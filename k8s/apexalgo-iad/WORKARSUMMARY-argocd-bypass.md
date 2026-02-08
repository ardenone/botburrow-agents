# Workaround Summary: ArgoCD Bypass for botburrow-agents Deployment

**Bead:** bd-cni (Alternative: Use workaround approach)
**Original Issue:** bd-1v9 - Fix botburrow-agents deployment via ArgoCD
**Date:** 2026-02-08
**Status:** READY FOR HUMAN ACTION

---

## Executive Summary

The botburrow-agents deployment is blocked because **ArgoCD is not installed** in the apexalgo-iad cluster, despite manifests being configured for ArgoCD GitOps. This document provides the workaround solution for immediate deployment.

## Root Cause

```
Expected: Git Push → ArgoCD → Kubernetes Deploy
Actual:   Git Push → [No ArgoCD] → Empty Namespace
```

**Evidence:**
- Namespace `botburrow-agents` exists with ArgoCD tracking annotation
- No resources deployed (`kubectl get all -n botburrow-agents` returns empty)
- ArgoCD CRDs not registered (`kubectl get applications.argoproj.io` fails)
- No ArgoCD namespace in cluster

## Immediate Workaround: Manual kubectl Deployment

### Option 1: Minimal Deployment (Recommended)

Deploy only core components for fastest time-to-running:

```bash
# Step 1: Create placeholder secrets (cluster-admin required)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Step 2: Deploy core stack
kubectl apply -k k8s/apexalgo-iad/ --context=apexalgo-iad

# Step 3: Verify
kubectl get pods -n botburrow-agents
```

**What gets deployed:**
- Namespace (already exists)
- RBAC (ServiceAccount, Role, RoleBinding)
- ConfigMap (application config)
- Valkey (Redis for coordination)
- Runner-Hybrid (single runner with all capabilities)

**Time to running:** ~5 minutes

### Option 2: Full Manual Deployment

Deploy all components without ArgoCD:

```bash
# Step 1: Create placeholder secrets
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Step 2: Apply all manifests
kubectl apply -f k8s/apexalgo-iad/rbac.yaml
kubectl apply -f k8s/apexalgo-iad/configmap.yaml
kubectl apply -f k8s/apexalgo-iad/valkey.yaml
kubectl apply -f k8s/apexalgo-iad/coordinator.yaml
kubectl apply -f k8s/apexalgo-iad/runner-hybrid.yaml
kubectl apply -f k8s/apexalgo-iad/runner-exploration.yaml
kubectl apply -f k8s/apexalgo-iad/runner-notification.yaml
kubectl apply -f k8s/apexalgo-iad/hpa.yaml
kubectl apply -f k8s/apexalgo-iad/servicemonitor.yaml
kubectl apply -f k8s/apexalgo-iad/skill-sync.yaml
kubectl apply -f k8s/apexalgo-iad/coordinator-git-sync.yaml
kubectl apply -f k8s/apexalgo-iad/runner-git-sync.yaml
```

**Time to running:** ~10 minutes

## Prerequisites

### Cluster Access Required

**From a machine with cluster-admin access to apexalgo-iad:**

```bash
# Verify you have cluster-admin
kubectl auth can-i create deployments -n botburrow-agents
kubectl auth can-i create secrets -n botburrow-agents
```

**Devpods CANNOT deploy** (intentional RBAC restriction):
- Devpods use `devpod-observer` ServiceAccount
- Read-only access for security
- Cannot create deployments, services, or secrets

### Secret Values

**Placeholder secrets** are provided for quick deployment. Update with real values post-deployment:

```bash
# Edit secrets after deployment
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents
```

**Required secret values:**
| Secret Key | Purpose | Source |
|------------|---------|--------|
| HUB_API_KEY | Botburrow Hub authentication | Generate at hub.botburrow.com |
| R2_ENDPOINT | Cloudflare R2 storage | Cloudflare dashboard |
| R2_ACCESS_KEY | R2 access credentials | Cloudflare dashboard |
| R2_SECRET_KEY | R2 secret credentials | Cloudflare dashboard |
| FORGEJO_USER | Forgejo username | Your Forgejo account |
| FORGEJO_TOKEN | Forgejo PAT | Generate in Forgejo settings |
| GITHUB_USER | GitHub username | Your GitHub account |
| GITHUB_TOKEN | GitHub PAT | Generate in GitHub settings |
| GITHUB_PAT | MCP GitHub access | Generate in GitHub settings |
| BRAVE_API_KEY | Brave Search API | Get from developer.brave.com |
| ANTHROPIC_API_KEY | Claude API | Get from console.anthropic.com |

## Verification

After deployment, verify the system is running:

```bash
# Check all resources
kubectl get all -n botburrow-agents

# Check pod status (should be Running)
kubectl get pods -n botburrow-agents

# Check logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner

# Check valkey is accessible
kubectl exec -n botburrow-agents valkey-0 -- redis-cli ping
# Expected response: PONG
```

## Troubleshooting

### Pods Not Starting

```bash
# Describe pod to see events
kubectl describe pod -n botburrow-agents <pod-name>

# Check for image pull errors
kubectl get pods -n botburrow-agents -o jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}'
```

### Secrets Missing

```bash
# Check secrets exist
kubectl get secrets -n botburrow-agents

# Re-create if missing
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

### RBAC Issues

```bash
# Check RBAC resources
kubectl get sa,role,rolebinding -n botburrow-agents

# Verify ServiceAccount has proper permissions
kubectl auth can-i list pods -n botburrow-agents --as=system:serviceaccount:botburrow-agents:botburrow-agents
```

## Post-Deployment: Configuration Updates

### Scaling (Manual until HPA is verified)

```bash
# Scale hybrid runners
kubectl scale deployment runner-hybrid --replicas=3 -n botburrow-agents

# Scale valkey (if needed)
kubectl scale statefulset valkey --replicas=1 -n botburrow-agents
```

### Updating Real Secrets

```bash
# Option 1: Edit in-place
kubectl edit secret botburrow-agents-secrets -n botburrow-agents

# Option 2: Re-create with real values
kubectl create secret generic botburrow-agents-secrets -n botburrow-agents \
  --from-literal=HUB_API_KEY="real-key-here" \
  --from-literal=R2_ENDPOINT="https://..." \
  --from-literal=R2_ACCESS_KEY="..." \
  --from-literal=R2_SECRET_KEY="..." \
  --from-literal=FORGEJO_USER="botburrow-agents" \
  --from-literal=FORGEJO_TOKEN="..." \
  --from-literal=GITHUB_USER="..." \
  --from-literal=GITHUB_TOKEN="..." \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart deployments to pick up new secrets
kubectl rollout restart deployment runner-hybrid -n botburrow-agents
```

### Accessing Logs

```bash
# Follow logs for all runners
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner -f

# Check specific pod
kubectl logs -n botburrow-agents <pod-name> --tail=100

# Check valkey logs
kubectl logs -n botburrow-agents valkey-0
```

## Next Steps After Workaround

### 1. Verify System Health

Run health checks and verify all components are functioning:
- Run `scripts/preflight-check.sh` if available
- Check pod metrics via `kubectl top pods -n botburrow-agents`
- Verify connectivity to external services (Hub, R2, Forgejo)

### 2. Plan for ArgoCD (Production)

The workaround gets you running immediately. For production, consider:

**Option A: Install ArgoCD**
- Install ArgoCD in apexalgo-iad cluster
- Configure ApplicationSet for botburrow-agents
- Convert to true GitOps workflow
- Reference: `docs/research/bd-2z6-argocd-deployment-approaches.md`

**Option B: Continue Manual Deployment**
- Document deployment procedures
- Use CI/CD for deployment automation
- Accept manual operations overhead

**Option C: Alternative GitOps (Flux)**
- Install Flux instead of ArgoCD
- Smaller footprint than ArgoCD
- CLI-focused workflow

### 3. Close Related Beads

Once workaround is deployed and verified:
- Close bd-1v9 (original issue) - resolved via workaround
- Close bd-cni (this bead) - workaround implemented
- Consider bd-2z6 (research) - can remain open as documentation

## Related Documentation

- `DEPLOYMENT-SIMPLIFIED.md` - Detailed simplified deployment guide
- `DEPLOYMENT-MINIMAL.md` - Minimal deployment for testing
- `SECRET_SETUP.md` - Detailed secrets configuration
- `RESEARCH-deployment-options-bd-32a.md` - Full deployment research
- `docs/research/bd-2z6-argocd-deployment-approaches.md` - ArgoCD approaches

## Quick Reference Commands

```bash
# Deploy (full process)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl apply -k k8s/apexalgo-iad/ --context=apexalgo-iad

# Check status
kubectl get pods -n botburrow-agents
kubectl get all -n botburrow-agents

# Logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner -f

# Scale
kubectl scale deployment runner-hybrid --replicas=3 -n botburrow-agents

# Restart
kubectl rollout restart deployment runner-hybrid -n botburrow-agents

# Cleanup (if needed)
kubectl delete namespace botburrow-agents
```

---

## Summary

| Aspect | Status | Action Required |
|--------|--------|-----------------|
| **Documentation** | ✅ Complete | None - all guides ready |
| **Manifests** | ✅ Valid | None - all manifests tested |
| **Secrets** | ⚠️ Placeholder | Human: Apply PLACEHOLDER secrets |
| **Deployment** | ⏳ Blocked | Human: Run kubectl apply |
| **Verification** | ⏳ Pending | Human: Verify pods running |

**Estimated time to deploy:** 5-10 minutes (with cluster-admin access)

**Who can deploy:** Anyone with cluster-admin access to apexalgo-iad cluster

**Where to deploy:** From any machine with kubectl configured for apexalgo-iad

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (bd-cni)

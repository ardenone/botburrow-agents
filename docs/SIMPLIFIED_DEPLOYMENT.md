# Simplified Deployment Guide for botburrow-agents

**Date:** 2026-02-08
**Bead:** bd-2yb (Alternative: Simplify requirements)
**Related:** bd-1v9 (Fix botburrow-agents deployment via ArgoCD)

## Problem Statement

The original ArgoCD deployment approach is not working - the namespace exists but contains zero resources. The ApplicationSet either doesn't exist or isn't syncing properly.

## Simplified Approach

**Bypass ArgoCD initially and deploy via kubectl directly.**

This simplified approach:
- Uses minimal viable components only
- Bypasses ArgoCD for initial deployment
- Can be migrated to ArgoCD later once validated

## Minimal Components

The minimal viable deployment includes only:

1. **RBAC** - ServiceAccount, Role, RoleBinding
2. **ConfigMaps** - botburrow-agents-config, agent-definitions-repos, agent-permissions
3. **Valkey** - Redis/Valkey for leader election
4. **Runner (Hybrid)** - Single runner deployment that handles all work types

**Deferred components (can add later):**
- Coordinator - optional for simple deployments
- HPA - manual scaling works fine initially
- ServiceMonitor - observability only
- Additional runners (notification, exploration) - single hybrid runner is sufficient
- Skill sync job - can run on-demand

## Prerequisites

1. **Access to apexalgo-iad cluster** with cluster-admin or namespace admin permissions
2. **kubectl configured** for apexalgo-iad cluster
3. **Docker Hub access** for images (already configured in manifests)

## Deployment Steps

### Step 1: Verify Namespace Exists

```bash
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig get namespace botburrow-agents
```

If it doesn't exist, create it:
```bash
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig create namespace botburrow-agents
```

### Step 2: Create Placeholder Secrets

The runner deployments require secrets. Apply the placeholder secrets first (cluster-admin required):

```bash
# From ardenone-cluster repo
cd /home/coder/ardenone-cluster
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig apply -f cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-sealedsecret.yml
```

Or use the placeholder secrets from botburrow-agents repo:
```bash
cd /home/coder/botburrow-agents
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
```

**IMPORTANT:** Update placeholder values post-deployment:
```bash
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig edit secret botburrow-agents-secrets -n botburrow-agents
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig edit secret mcp-credentials -n botburrow-agents
```

### Step 3: Deploy Minimal Components

Option A - Using Kustomize (recommended):
```bash
cd /home/coder/botburrow-agents
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig apply -k k8s/apexalgo-iad/ --kustomize=kustomization-minimal.yaml
```

Option B - Using individual manifests:
```bash
cd /home/coder/ardenone-cluster
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig apply -f cluster-configuration/apexalgo-iad/botburrow-agents/rbac.yaml
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig apply -f cluster-configuration/apexalgo-iad/botburrow-agents/configmap.yaml
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig apply -f cluster-configuration/apexalgo-iad/botburrow-agents/valkey.yaml
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig apply -f cluster-configuration/apexalgo-iad/botburrow-agents/runner-hybrid.yaml
```

### Step 4: Verify Deployment

```bash
# Check all resources
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig get all -n botburrow-agents

# Check pods are running
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig get pods -n botburrow-agents

# Check logs
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig logs -f deployment/runner-hybrid -n botburrow-agents
```

### Step 5: Test Connectivity

```bash
# Port-forward to test the health endpoint
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig port-forward -n botburrow-agents deployment/runner-hybrid 8080:9091

# In another terminal:
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

## Post-Deployment Actions

1. **Update placeholder secrets** with real credentials
2. **Verify agent definitions** are being cloned from git
3. **Scale runners** if needed: `kubectl scale deployment runner-hybrid --replicas=3 -n botburrow-agents`
4. **Add optional components** (coordinator, additional runners, HPA) as needed

## Migration to ArgoCD (Optional)

Once the deployment is validated, migrate to ArgoCD by:

1. Verify manifests exist in `ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/`
2. The ApplicationSet should automatically pick up the new resources
3. Verify sync status in ArgoCD UI
4. Once synced, future changes follow GitOps workflow

## Troubleshooting

### Pods Not Starting

Check pod logs:
```bash
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig logs -f deployment/runner-hybrid -n botburrow-agents
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig logs -f deployment/valkey -n botburrow-agents
```

### Secrets Not Found

Verify secrets exist:
```bash
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig get secrets -n botburrow-agents
```

### Git Clone Failing

Check agent-definitions ConfigMap:
```bash
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig get configmap agent-definitions-repos -n botburrow-agents -o yaml
```

### Permission Denied

Ensure the ServiceAccount has proper RBAC:
```bash
kubectl --kubeconfig=/path/to/apexalgo-iad.kubeconfig auth can-i --as=system:serviceaccount:botburrow-agents:botburrow-agents create lease -n botburrow-agents
```

## References

- Original bead: bd-1v9 - Fix botburrow-agents deployment via ArgoCD
- Investigation findings: `argocd-investigation-findings.md`
- Kustomization files: `k8s/apexalgo-iad/kustomization-*.yaml`

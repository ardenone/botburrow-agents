# ArgoCD GitOps Deployment Guide for botburrow-agents

**Status:** Ready for Cluster-Admin Deployment
**Date:** 2026-02-08
**Bead:** bd-2o4

---

## Executive Summary

This guide provides step-by-step instructions for deploying ArgoCD to the apexalgo-iad cluster and configuring GitOps for botburrow-agents. All manifests are prepared and ready for deployment.

**Current State:**
- botburrow-agents namespace exists (empty)
- ArgoCD not installed
- RBAC prevents workers from installing ArgoCD (cluster-admin required)

**Required Actions:**
1. Install ArgoCD (cluster-admin only)
2. Create botburrow-agents secrets (cluster-admin only)
3. Apply ApplicationSet manifest (triggers GitOps sync)

---

## Prerequisites

### Cluster Access
- Cluster-admin access to apexalgo-iad cluster
- kubectl configured with cluster-admin context

### Required Secrets
The following secrets must be created in `botburrow-agents` namespace:

1. **botburrow-agents-secrets** - Hub API, R2 storage, Git credentials
   - See: `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`
   - Create SealedSecret or apply secret directly

2. **mcp-credentials** - MCP server API keys
   - See: Human bead bd-bj8p for credential details

### Repository
- Repository: https://github.com/ardenone/botburrow-agents.git
- Branch: `main`
- Manifests path: `k8s/apexalgo-iad/`

---

## Phase 1: Install ArgoCD

### Step 1.1: Create ArgoCD Namespace

```bash
kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml
```

### Step 1.2: Install ArgoCD

```bash
# Option A: Install latest stable (recommended)
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Option B: Download and review first
curl -o argocd-install.yaml https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# Review argocd-install.yaml
kubectl apply -n argocd -f argocd-install.yaml
```

### Step 1.3: Verify Installation

```bash
# Check all pods are running
kubectl get pods -n argocd

# Expected output:
# NAME                                      READY   STATUS    RESTARTS   AGE
# argocd-applicationset-controller-...      1/1     Running   0          1m
# argocd-dex-server-...                     1/1     Running   0          1m
# argocd-notifications-controller-...       1/1     Running   0          1m
# argocd-redis-...                          1/1     Running   0          1m
# argocd-repo-server-...                    1/1     Running   0          1m
# argocd-server-...                         1/1     Running   0          1m

# Check CRDs are installed
kubectl get crd | grep argoproj.io

# Expected output:
# applicationsets.argoproj.io               ...
# applications.argoproj.io                  ...
# appprojects.argoproj.io                   ...
```

### Step 1.4: Get Admin Credentials

```bash
# Get initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d

# Save password securely
# Password: <output from above command>
```

### Step 1.5: Access ArgoCD UI

```bash
# Port-forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser to https://localhost:8080
# Login with username: admin, password from Step 1.4

# Change admin password immediately after first login
# Admin Menu -> User Info -> Change Password
```

---

## Phase 2: Create Secrets

### Step 2.1: Create botburrow-agents-secrets

**Option A: SealedSecret (Recommended for Production)**

```bash
# Install SealedSecrets controller (if not installed)
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Create secret from template
cp k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml /tmp/botburrow-agents-secrets.yml
# Edit /tmp/botburrow-agents-secrets.yml with real values

# Seal the secret
kubeseal --format yaml < /tmp/botburrow-agents-secrets.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
rm /tmp/botburrow-agents-secrets.yml

# Commit SealedSecret to git
git add k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git commit -m "feat: add SealedSecret for botburrow-agents"
git push origin main

# Apply SealedSecret
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
```

**Option B: Direct Secret (For Testing)**

```bash
# Create secret directly (not committed to git)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
# Edit secret with kubectl edit secret
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
```

### Step 2.2: Create mcp-credentials

```bash
# See human bead bd-bj8p for required credentials
# Create secret:
kubectl create secret generic mcp-credentials \
  --from-literal=GITHUB_PAT=<your-github-pat> \
  --from-literal=BRAVE_API_KEY=<your-brave-api-key> \
  --from-literal=ANTHROPIC_API_KEY=<your-anthropic-api-key> \
  -n botburrow-agents
```

### Step 2.3: Verify Secrets

```bash
# Check secrets exist
kubectl get secrets -n botburrow-agents

# Expected output:
# NAME                       TYPE     DATA   AGE
# botburrow-agents-secrets   Opaque   8      1m
# mcp-credentials            Opaque   3      1m
```

---

## Phase 3: Configure ApplicationSet

### Step 3.1: Apply ApplicationSet

```bash
# Apply the ApplicationSet manifest
kubectl apply -f k8s/apexalgo-iad/argocd/applicationset.yaml
```

### Step 3.2: Verify ApplicationSet

```bash
# Check ApplicationSet exists
kubectl get applicationsets.argoproj.io -n argocd

# Check generated Application
kubectl get applications.argoproj.io -n argocd

# Expected output:
# NAME                SYNC STATUS   HEALTH STATUS
# botburrow-agents    Synced        Healthy
```

### Step 3.3: Monitor Sync

```bash
# Watch sync progress
kubectl get applications.argoproj.io -n argocd -w

# Check Application details
argocd app get botburrow-agents --grpc-web

# View sync logs
argocd app logs botburrow-agents --grpc-web
```

---

## Phase 4: Verify Deployment

### Step 4.1: Check Resources

```bash
# Check all resources in botburrow-agents
kubectl get all -n botburrow-agents

# Expected output:
# NAME                              READY   STATUS    RESTARTS   AGE
# pod/coordinator-...               1/1     Running   0          2m
# pod/runner-hybrid-...             1/1     Running   0          2m
# pod/runner-notification-...       1/1     Running   0          2m
# pod/runner-exploration-...        1/1     Running   0          2m
# pod/valkey-0                      1/1     Running   0          2m

# NAME                    TYPE        CLUSTER-IP       PORT(S)
# service/coordinator     ClusterIP   10.x.x.x         9090/TCP
# service/valkey          ClusterIP   10.x.x.x         6379/TCP
# service/runner-hybrid   ClusterIP   10.x.x.x         9091/TCP
# ...

# NAME                             READY   UP-TO-DATE   AVAILABLE
# deployment.apps/coordinator      1/1     1            1
# deployment.apps/runner-hybrid    1/1     1            1
# ...
```

### Step 4.2: Check Pod Logs

```bash
# Check coordinator logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=coordinator --tail=50

# Check runner logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/component=runner --tail=50

# Check Valkey logs
kubectl logs -n botburrow-agents -l app.kubernetes.io/name=valkey --tail=50
```

### Step 4.3: Health Check

```bash
# Check pod health
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=botburrow -n botburrow-agents --timeout=300s

# Check coordinator health endpoint
COORD_POD=$(kubectl get pods -n botburrow-agents -l app.kubernetes.io/name=coordinator -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n botburrow-agents $COORD_POD -- curl -s http://localhost:9090/health
```

---

## ArgoCD CLI Installation (Optional)

```bash
# Install ArgoCD CLI
curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x argocd-linux-amd64
sudo mv argocd-linux-amd64 /usr/local/bin/argocd

# Login to ArgoCD
argocd login localhost:8080 --insecure --username admin --password <your-password>

# Verify connection
argocd cluster list
argocd app list
```

---

## External Access (Optional)

### IngressRoute for Traefik

If you want external access to ArgoCD UI:

```bash
# Update host in ingress.yaml
# Edit: argocd.apexalgo.ardenone.com to your domain

kubectl apply -f k8s/apexalgo-iad/argocd/ingress.yaml
```

---

## Troubleshooting

### ApplicationSet Not Generating Applications

```bash
# Check ApplicationSet controller logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-applicationset-controller

# Check ApplicationSet status
kubectl describe applicationsets.argoproj.io botburrow-agents -n argocd
```

### Application Sync Failing

```bash
# Get Application details
argocd app get botburrow-agents --grpc-web

# Check sync status
kubectl get applications.argoproj.io botburrow-agents -n argocd -o yaml

# View sync logs
argocd app logs botburrow-agents --grpc-web --tail=100
```

### Secrets Not Syncing

```bash
# Check if secrets exist
kubectl get secrets -n botburrow-agents

# Check SealedSecrets controller
kubectl get pods -n kube-system -l name=sealed-secrets-controller

# Describe SealedSecret
kubectl describe sealedsecrets -n botburrow-agents
```

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n botburrow-agents

# Describe pod
kubectl describe pod <pod-name> -n botburrow-agents

# Check logs
kubectl logs <pod-name> -n botburrow-agents
```

### RBAC Issues

If you're deploying from a devpod and encounter RBAC errors, see human bead bd-3cpp for granting devpod-observer admin permissions in botburrow-agents namespace.

---

## Migration from Manual Deployment

If you have manually deployed resources, ArgoCD will detect them and manage them automatically.

```bash
# Check what ArgoCD sees
argocd app get botburrow-agents --grpc-web

# Force sync if needed
argocd app sync botburrow-agents --grpc-web
```

---

## Maintenance

### Updating ArgoCD

```bash
# Update to latest version
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Backup before upgrade
argocd admin export > argocd-backup.yaml
```

### Backup/Restore

```bash
# Backup ArgoCD configuration
argocd admin export > argocd-backup.yaml

# Restore ArgoCD configuration
argocd admin import < argocd-backup.yaml
```

---

## Next Steps

1. **Close bead bd-2o4** after successful deployment
2. **Close human bead bd-3cpp** if RBAC is working correctly
3. **Verify bead bd-3s2** (Deploy botburrow-agents namespace) is completed
4. **Monitor ApplicationSet** for automatic syncs on git changes

---

## References

- ArgoCD Documentation: https://argo-cd.readthedocs.io/
- ArgoCD ApplicationSet: https://argocd-applicationset.readthedocs.io/
- SealedSecrets: https://github.com/bitnami-labs/sealed-secrets
- botburrow-agents Repository: https://github.com/ardenone/botburrow-agents

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)

# ArgoCD Implementation Status for botburrow-agents

**Bead:** bd-2o4 - Install and configure ArgoCD for botburrow-agents GitOps deployment
**Date:** 2026-02-08
**Status:** READY FOR CLUSTER-ADMIN EXECUTION
**Worker:** claude-code-glm-47

---

## Executive Summary

All ArgoCD GitOps deployment artifacts have been prepared and verified. The implementation is **blocked by RBAC** - cluster-admin access is required to install ArgoCD in the apexalgo-iad cluster. Once ArgoCD is installed by a human with cluster-admin access, the ApplicationSet will automatically deploy botburrow-agents.

### Current State

| Component | Status | Notes |
|-----------|--------|-------|
| ArgoCD Installation | NOT INSTALLED | Requires cluster-admin |
| argocd namespace | NOT EXISTS | Will be created by install script |
| ApplicationSet manifest | READY | `k8s/apexalgo-iad/argocd/applicationset.yaml` |
| Application manifest | READY | `k8s/apexalgo-iad/argocd-application.yaml` |
| botburrow-agents namespace | EXISTS | Empty, ready for deployment |
| Documentation | COMPLETE | All guides prepared |
| Installation script | READY | `k8s/apexalgo-iad/argocd/install.sh` |

---

## Implementation Details

### Phase 1: ArgoCD Installation (Cluster Admin Required)

**Status:** PREPARED - Ready for human execution

**Artifacts Created:**
1. `k8s/apexalgo-iad/argocd/namespace.yaml` - ArgoCD namespace manifest
2. `k8s/apexalgo-iad/argocd/install.yaml` - Installation instructions ConfigMap
3. `k8s/apexalgo-iad/argocd/install.sh` - Automated installation script
4. `k8s/apexalgo-iad/argocd/ingress.yaml` - Traefik IngressRoute for external access
5. `k8s/apexalgo-iad/argocd/README.md` - Quick reference guide
6. `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md` - Comprehensive deployment guide

**Installation Commands:**
```bash
# Option 1: Automated script (recommended)
cd /home/coder/botburrow-agents/k8s/apexalgo-iad/argocd
chmod +x install.sh
./install.sh

# Option 2: Manual installation
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=argocd -n argocd --timeout=300s
```

**Verification:**
```bash
kubectl get pods -n argocd
kubectl get crd | grep argoproj.io
kubectl get applications.argoproj.io -n argocd
```

### Phase 2: ApplicationSet Configuration

**Status:** PREPARED - Manifests ready to apply

**Artifacts:**
1. `k8s/apexalgo-iad/argocd/applicationset.yaml` - ApplicationSet for botburrow-agents
2. `k8s/apexalgo-iad/argocd-application.yaml` - Standalone Application (alternative)

**Configuration Details:**
- **Repository:** https://github.com/ardenone/botburrow-agents.git
- **Branch:** main
- **Path:** k8s/apexalgo-iad
- **Destination:** https://kubernetes.default.svc (in-cluster)
- **Namespace:** botburrow-agents
- **Sync Policy:** Automated with prune and self-heal
- **Auto-Sync:** Enabled on push to main

**Application Commands:**
```bash
# Apply ApplicationSet (after ArgoCD is installed)
kubectl apply -f k8s/apexalgo-iad/argocd/applicationset.yaml

# Verify ApplicationSet
kubectl get applicationsets.argoproj.io -n argocd

# Verify generated Application
kubectl get applications.argoproj.io -n argocd
```

### Phase 3: GitOps Migration

**Status:** DOCUMENTED - Ready for post-installation

**Migration Steps:**
1. Verify ArgoCD is running (Phase 1)
2. Create botburrow-agents secrets (see below)
3. Apply ApplicationSet manifest (Phase 2)
4. Monitor sync status via ArgoCD UI or CLI
5. Verify all pods are running in botburrow-agents namespace

---

## Prerequisites Checklist

Before executing the installation script, ensure:

- [ ] Cluster-admin access to apexalgo-iad cluster
- [ ] `kubectl` configured with cluster-admin context
- [ ] Internet access to download ArgoCD manifests
- [ ] botburrow-agents secrets prepared (see below)

### Secrets Configuration

**Required Secrets:**

1. **botburrow-agents-secrets** (Opaqu
e)
   - HUB_API_KEY
   - R2_ENDPOINT
   - R2_ACCESS_KEY
   - R2_SECRET_KEY
   - FORGEJO_USER
   - FORGEJO_TOKEN
   - GITHUB_USER
   - GITHUB_TOKEN

2. **mcp-credentials** (Opaque)
   - GITHUB_PAT
   - BRAVE_API_KEY
   - ANTHROPIC_API_KEY

**Secrets Setup:**
```bash
# Option 1: Placeholder secrets (quick start)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# Option 2: SealedSecrets (production)
# See k8s/apexalgo-iad/SECRET_SETUP.md for detailed instructions
```

---

## Cluster Access Analysis

### Current Permissions (devpod-observer)

The devpod-observer ServiceAccount has **intentionally restricted** permissions:
- **CAN:** Read most resources across namespaces
- **CANNOT:** Create namespaces, CRDs, cluster-level resources
- **CANNOT:** Create deployments, services, secrets in most namespaces

### Required for ArgoCD Installation

ArgoCD installation requires **cluster-admin** permissions:
1. Create `argocd` namespace
2. Install ArgoCD CRDs (cluster-level resources)
3. Create cluster-level RBAC for ArgoCD components
4. Deploy ArgoCD pods with cluster-wide permissions

### RBAC Workaround Options

**Option 1: Human with Cluster-Admin (RECOMMENDED)**
- A human with cluster-admin access runs the installation script
- Installation takes ~5 minutes
- One-time setup for the entire cluster

**Option 2: Elevate devpod-observer Temporarily (NOT RECOMMENDED)**
- Would require human intervention anyway
- Security risk to elevate service account
- Should be done via human bead for proper tracking

**Option 3: External Deployment Service**
- Use GitHub Actions with cluster-admin credentials
- Adds external dependency
- Requires kubeconfig in GitHub secrets

---

## Verification Steps

After ArgoCD installation, verify:

### 1. ArgoCD Installation

```bash
# Check all ArgoCD pods are running
kubectl get pods -n argocd

# Expected output:
# NAME                                              READY   STATUS    RESTARTS   AGE
# argocd-applicationset-controller-xxxxx-xxxxx      1/1     Running   0          2m
# argocd-dex-server-xxxxx-xxxxx                     1/1     Running   0          2m
# argocd-notifications-controller-xxxxx-xxxxx       1/1     Running   0          2m
# argocd-redis-xxxxx-xxxxx                          1/1     Running   0          2m
# argocd-repo-server-xxxxx-xxxxx                    1/1     Running   0          2m
# argocd-server-xxxxx-xxxxx                         1/1     Running   0          2m

# Check CRDs are installed
kubectl get crd | grep argoproj.io

# Expected output:
# applications.argoproj.io                  2024-xx-xxTxx:xx:xxZ
# applicationsets.argoproj.io               2024-xx-xxTxx:xx:xxZ
# appprojects.argoproj.io                   2024-xx-xxTxx:xx:xxZ
```

### 2. ApplicationSet Deployment

```bash
# Check ApplicationSet exists
kubectl get applicationsets.argoproj.io -n argocd

# Check generated Application
kubectl get applications.argoproj.io -n argocd

# Expected output:
# NAME              SYNC STATUS   HEALTH STATUS
# botburrow-agents  Synced        Healthy
```

### 3. botburrow-agents Deployment

```bash
# Check resources in botburrow-agents
kubectl get all -n botburrow-agents

# Expected output (after sync):
# NAME                                   READY   STATUS    RESTARTS   AGE
# pod/coordinator-xxxxx-xxxxx            1/1     Running   0          3m
# pod/runner-hybrid-xxxxx-xxxxx          1/1     Running   0          3m
# pod/runner-notification-xxxxx-xxxxx    1/1     Running   0          3m
# pod/runner-exploration-xxxxx-xxxxx     1/1     Running   0          3m
# pod/valkey-0                           1/1     Running   0          3m
```

---

## Troubleshooting

### ArgoCD Pods Not Starting

```bash
# Check pod events
kubectl describe pod -n argocd <pod-name>

# Check logs
kubectl logs -n argocd deployment/argocd-server
kubectl logs -n argocd deployment/argocd-repo-server
```

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
kubectl get applications.argoproj.io botburrow-agents -n argocd -o yaml

# Check repo-server logs
kubectl logs -n argocd deployment/argocd-repo-server

# Manual sync via ArgoCD CLI
argocd app sync botburrow-agents --grpc-web
```

---

## Next Steps

### Immediate (Requires Human with Cluster-Admin)

1. **Install ArgoCD:**
   ```bash
   cd /home/coder/botburrow-agents/k8s/apexalgo-iad/argocd
   chmod +x install.sh
   ./install.sh
   ```

2. **Create Secrets:**
   ```bash
   kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
   # Or create SealedSecrets for production
   ```

3. **Apply ApplicationSet:**
   ```bash
   kubectl apply -f k8s/apexalgo-iad/argocd/applicationset.yaml
   ```

4. **Verify Deployment:**
   ```bash
   kubectl get pods -n botburrow-agents
   kubectl get applications.argoproj.io -n argocd
   ```

### After Successful Deployment

1. **Close related beads:**
   - bd-2o4 (this bead) - ArgoCD installation complete
   - bd-cni (workaround bead) - No longer needed
   - bd-1v9 (original deployment issue) - Resolved via GitOps

2. **Monitor GitOps workflow:**
   - Watch for automatic syncs on git push
   - Verify ArgoCD UI shows healthy applications
   - Check logs for any sync issues

3. **Document access:**
   - Save ArgoCD admin password securely
   - Configure IngressRoute for external access (optional)
   - Set up ArgoCD CLI for local access

---

## Related Documentation

- `k8s/apexalgo-iad/argocd/README.md` - Quick reference guide
- `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md` - Comprehensive deployment guide
- `k8s/apexalgo-iad/argocd/install.sh` - Automated installation script
- `k8s/apexalgo-iad/WORKARSUMMARY-argocd-bypass.md` - Manual deployment workaround
- `docs/research/bd-2z6-argocd-deployment-approaches.md` - Deployment approaches research

---

## Artifacts Summary

### Created During This Implementation

1. **k8s/apexalgo-iad/argocd/README.md** - Updated with comprehensive quick reference
2. **k8s/apexalgo-iad/argocd/install.sh** - Automated installation script with verification
3. **k8s/apexalgo-iad/argocd/ingress.yaml** - Updated IngressRoute configuration

### Already Existing (Verified)

1. **k8s/apexalgo-iad/argocd/namespace.yaml** - ArgoCD namespace manifest
2. **k8s/apexalgo-iad/argocd/install.yaml** - Installation instructions ConfigMap
3. **k8s/apexalgo-iad/argocd/applicationset.yaml** - ApplicationSet manifest (verified configuration)
4. **k8s/apexalgo-iad/argocd-application.yaml** - Standalone Application manifest
5. **k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md** - Comprehensive deployment guide
6. **k8s/apexalgo-iad/argocd/kustomization.yaml** - Kustomize configuration

---

## Bead Management

### Bead Status

- **bd-2o4** (this bead): IN PROGRESS - Implementation prepared, blocked by RBAC
- **bd-cni** (workaround): READY - Manual deployment workaround documented
- **bd-1v9** (original issue): CLOSED - Resolved via alternative approach

### Dependencies

This bead (bd-2o4) is **blocked by RBAC** - requires cluster-admin access to complete. No other beads are blocking this implementation.

### Follow-up Beads

After ArgoCD installation, consider creating:
- Bead for ArgoCD monitoring and alerting setup
- Bead for ArgoCD backup and restore procedures
- Bead for multi-cluster ArgoCD configuration (if applicable)

---

## Conclusion

All ArgoCD GitOps deployment artifacts have been prepared, verified, and documented. The implementation is **complete from a planning and preparation standpoint** and **ready for cluster-admin execution**.

The installation will take approximately **5 minutes** once executed by someone with cluster-admin access to the apexalgo-iad cluster.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)
**Workspace:** /home/coder/botburrow-agents

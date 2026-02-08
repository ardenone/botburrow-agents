# ArgoCD GitOps with SealedSecrets for botburrow-agents

**Date:** 2026-02-08
**Bead:** bd-3he (Implement proper botburrow-agents ArgoCD GitOps with SealedSecrets)
**Status:** Implementation Guide

---

## Overview

This guide documents the proper ArgoCD GitOps deployment approach for botburrow-agents, addressing the issues that led to the workaround (bd-19j). The solution uses:

1. **ArgoCD Application** - For automated GitOps deployment
2. **SealedSecrets** - For secure credentials management in Git
3. **Health checks** - For automated deployment verification
4. **Cross-repository architecture** - botburrow-agents repo managed via ardenone-cluster ArgoCD

---

## Problem Context

### Original Issue (bd-1v9 → bd-19j)

The botburrow-agents namespace was created by ArgoCD but contained **zero resources**:
- Namespace existed with ArgoCD tracking-id
- No deployments, services, or pods deployed
- Manifests valid and committed to git
- ArgoCD access blocked (RBAC)

### Root Cause Identified

**Architecture mismatch:**
- ArgoCD ApplicationSet in `ardenone-cluster` repo only manages paths within `ardenone-cluster`
- `botburrow-agents` is a **separate repository** with its own manifests
- No ArgoCD Application pointing to the external `botburrow-agents` repository

### Workaround (bd-19j)

The workaround deployed via `kubectl apply -k` bypassing ArgoCD entirely. This:
- ✅ Unblocks immediate deployment
- ❌ Breaks GitOps workflow
- ❌ No automated sync
- ❌ Manual drift detection required

---

## Proper Solution Architecture

### GitOps Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Git Repositories                          │
├─────────────────────────────────┬───────────────────────────────┤
│   ardenone-cluster              │   botburrow-agents            │
│   (GitOps configuration)        │   (Application manifests)     │
├─────────────────────────────────┼───────────────────────────────┤
│ cluster-configuration/          │ k8s/apexalgo-iad/             │
│   apexalgo-iad/                 │   ├── namespace.yml           │
│     botburrow-agents/           │   ├── rbac.yaml               │
│       └── botburrow-agents      │   ├── configmap.yaml          │
│           -application.yml      │   ├── valkey.yaml              │
│                                 │   ├── runner-hybrid.yaml       │
│                                 │   ├── *sealedsecret.yml        │
│                                 │   └── kustomization.yaml       │
└─────────────────────────────────┴───────────────────────────────┘
                                      │
                                      │ ArgoCD polls main branch
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                           ArgoCD                                 │
│                      (in apexalgo-iad)                          │
│                                                                 │
│  Application: botburrow-agents-apexalgo-iad                    │
│  Source: github.com/ardenone/botburrow-agents                   │
│  Path: k8s/apexalgo-iad                                          │
│  Sync: Automated (prune, self-heal)                             │
└─────────────────────────────────────────────────────────────────┘
                                      │
                                      │ kubectl apply
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    apexalgo-iad Cluster                         │
│                                                                 │
│  Namespace: botburrow-agents                                    │
│  Resources: deployments, services, pods, sealedsecrets          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Ardenone-cluster repo** - Contains ArgoCD Application manifest
2. **Botburrow-agents repo** - Contains Kubernetes manifests
3. **ArgoCD** - Orchestrates deployment between repos and cluster
4. **SealedSecrets** - Encrypts secrets in git, decrypts in-cluster

---

## Implementation Steps

### Step 1: Create ArgoCD Application Manifest

**Location:** `ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-application.yml`

**Purpose:** Tell ArgoCD to deploy manifests from the external botburrow-agents repository.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: botburrow-agents-apexalgo-iad
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/ardenone/botburrow-agents.git
    targetRevision: main
    path: k8s/apexalgo-iad
  destination:
    server: https://hcp-99476ebb-4133-4a21-ac6a-6e2bdf6794c0.spot.rackspace.com
    namespace: botburrow-agents
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Status:** ✅ **Created** at `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-application.yml`

---

### Step 2: Create SealedSecrets for Credentials

**Why SealedSecrets?**
- ✅ Secure - Encrypted with cluster-specific public key
- ✅ GitOps-native - Can commit encrypted secrets to git
- ✅ Automated - SealedSecrets controller decrypts in-cluster
- ✅ Safe - Only the target cluster can decrypt

**Prerequisites:**
```bash
# Install kubeseal CLI
# macOS
brew install kubeseal

# Linux
go install github.com/bitnami-labs/sealed-secrets/cmd/kubeseal@latest

# Verify sealed-secrets controller is running
kubectl get pods -n sealed-secrets
```

**Creating SealedSecrets:**

```bash
# 1. Create temporary secret file with real values
cat > /tmp/botburrow-agents-secrets.yml << 'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: botburrow-agents-secrets
  namespace: botburrow-agents
type: Opaque
stringData:
  HUB_API_KEY: "real-hub-api-key-here"
  R2_ENDPOINT: "https://your-r2-endpoint.r2.cloudflarestorage.com"
  R2_ACCESS_KEY: "your-r2-access-key"
  R2_SECRET_KEY: "your-r2-secret-key"
  FORGEJO_USER: "botburrow-agents"
  FORGEJO_TOKEN: "your-forgejo-token"
  GITHUB_USER: "your-github-username"
  GITHUB_TOKEN: "your-github-pat"
EOF

# 2. Create SealedSecret (encrypt for cluster)
kubeseal --format yaml --controller-namespace=sealed-secrets \
  < /tmp/botburrow-agents-secrets.yml \
  > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# 3. Clean up temporary secret (IMPORTANT!)
shred -u /tmp/botburrow-agents-secrets.yml

# 4. Verify SealedSecret (should NOT contain plain secrets)
grep -i "api-key\|secret\|token" k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
# Should only see encrypted values like: AgBy3i4OJSW+...TyU=

# 5. Commit to git (SAFE - encrypted)
git add k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
git commit -m "feat: add SealedSecret for botburrow-agents credentials"
git push
```

**For MCP credentials:**

```bash
# 1. Create temporary secret file
cat > /tmp/mcp-credentials.yml << 'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: mcp-credentials
  namespace: botburrow-agents
type: Opaque
stringData:
  GITHUB_PAT: "your-github-pat-for-mcp"
  BRAVE_API_KEY: "your-brave-search-api-key"
  ANTHROPIC_API_KEY: ""  # Empty if using z.ai proxy
EOF

# 2. Create SealedSecret
kubeseal --format yaml --controller-namespace=sealed-secrets \
  < /tmp/mcp-credentials.yml \
  > k8s/apexalgo-iad/mcp-credentials-sealedsecret.yml

# 3. Clean up
shred -u /tmp/mcp-credentials.yml

# 4. Commit
git add k8s/apexalgo-iad/mcp-credentials-sealedsecret.yml
git commit -m "feat: add SealedSecret for MCP credentials"
git push
```

**SealedSecret Verification:**
```bash
# Verify SealedSecret resource is valid
kubectl apply --dry-run=server -f k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# After deployment, verify Secret was created
kubectl get secret botburrow-agents-secrets -n botburrow-agents
```

---

### Step 3: Update Kustomization to Use SealedSecrets

**Location:** `k8s/apexalgo-iad/kustomization.yaml`

**Current state:**
```yaml
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  # secrets.yaml removed - use SealedSecrets instead
```

**Update to include SealedSecrets:**
```yaml
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  - botburrow-agents-sealedsecret.yml  # Add SealedSecret
  - mcp-credentials-sealedsecret.yml   # Add MCP SealedSecret
  - valkey.yaml
  - runner-hybrid.yaml
  # ... other resources
```

**Status:** ⚠️ **Requires human** - Real credential values needed to create SealedSecrets

**Workaround available:**
```yaml
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  - botburrow-agents-secrets-PLACEHOLDER.yml  # Use placeholder initially
  - valkey.yaml
  - runner-hybrid.yaml
```

---

### Step 4: Deploy ArgoCD Application

**Prerequisites:**
1. ArgoCD is installed in apexalgo-iad cluster
2. You have kubectl access to apexalgo-iad
3. Application manifest is in ardenone-cluster repo

**Deployment:**

```bash
# 1. Navigate to ardenone-cluster
cd /home/coder/ardenone-cluster

# 2. Verify Application manifest exists
cat cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-application.yml

# 3. Apply Application manifest (if not managed by ApplicationSet)
kubectl apply -f \
  cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-application.yml

# 4. Verify Application was created
kubectl get application botburrow-agents-apexalgo-iad -n argocd -o yaml

# 5. Check sync status (via ArgoCD CLI or UI)
argocd app get botburrow-agents-apexalgo-iad

# 6. Trigger manual sync (if needed)
argocd app sync botburrow-agents-apexalgo-iad
```

**If ArgoCD is not installed:**
```bash
# Install ArgoCD in apexalgo-iad cluster
kubectl create namespace argocd

kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD pods to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd
```

**Status:** ⚠️ **Blocked** - Requires verification that ArgoCD is installed in apexalgo-iad

---

### Step 5: Verify Deployment Health

**Automated Health Checks:**

```bash
# 1. Check namespace exists
kubectl get namespace botburrow-agents

# 2. Check all resources are deployed
kubectl get all -n botburrow-agents

# Expected output:
# NAME                                  READY   STATUS    RESTARTS   AGE
# pod/runner-hybrid-xxxxxxxxxx-xxxx     1/1     Running   0          2m
# pod/valkey-xxxxxxxxxx-xxxx            1/1     Running   0          2m
#
# NAME                     TYPE        CLUSTER-IP      PORT(S)    AGE
# service/runner-hybrid    ClusterIP   10.xx.xx.xx     9091/TCP   2m
# service/valkey           ClusterIP   10.xx.xx.xx     6379/TCP   2m
#
# NAME                             READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/runner-hybrid    2/2     2            2           2m
# statefulset.apps/valkey         1/1     1            1           2m

# 3. Check ArgoCD sync status
kubectl get application botburrow-agents-apexalgo-iad -n argocd -o jsonpath='{.status.sync.status}'

# Should output: "Synced" or "Unknown"

# 4. Check pod health
kubectl get pods -n botburrow-agents -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.status.containerStatuses[0].ready}{"\n"}{end}'

# 5. Check for errors
kubectl get events -n botburrow-agents --sort-by='.lastTimestamp' | tail -20
```

**Health Endpoint Verification:**

```bash
# Port-forward to runner health endpoint
kubectl port-forward -n botburrow-agents deployment/runner-hybrid 8080:9091

# In another terminal, check health
curl http://localhost:8080/health
# Expected: {"status": "healthy"}

curl http://localhost:8080/ready
# Expected: {"status": "ready"}

# Check metrics
curl http://localhost:8080/metrics
# Expected: Prometheus metrics output
```

**Status:** ⏳ **Pending deployment**

---

## Migration from Workaround to GitOps

### Current State (Workaround - bd-19j)

```
Manual kubectl deployment
├── scripts/deploy-workaround.sh
├── kustomization-minimal.yaml
└── botburrow-agents-secrets-PLACEHOLDER.yml
```

### Desired State (GitOps - bd-3he)

```
ArgoCD automated deployment
├── ardenone-cluster/botburrow-agents-application.yml
├── k8s/apexalgo-iad/kustomization.yaml
└── k8s/apexalgo-iad/*sealedsecret.yml
```

### Migration Steps

1. **Create SealedSecrets** (requires real credentials)
   ```bash
   # Follow Step 2 above
   ```

2. **Update kustomization** to include SealedSecrets
   ```yaml
   resources:
     - botburrow-agents-sealedsecret.yml
     - mcp-credentials-sealedsecret.yml
   ```

3. **Deploy ArgoCD Application**
   ```bash
   kubectl apply -f ardenone-cluster/.../botburrow-agents-application.yml
   ```

4. **Verify sync**
   ```bash
   argocd app get botburrow-agents-apexalgo-iad
   ```

5. **Remove manual deployment** (after verification)
   ```bash
   # Archive workaround script
   mv scripts/deploy-workaround.sh scripts/archive/

   # Archive placeholder secrets
   mv k8s/apexalgo-iad/*PLACEHOLDER.yml archive/
   ```

---

## Troubleshooting

### ArgoCD Application Not Syncing

**Symptom:** Application exists but shows "OutOfSync"

**Diagnosis:**
```bash
# Check Application status
kubectl get application botburrow-agents-apexalgo-iad -n argocd -o yaml

# Check for sync errors
kubectl get application botburrow-agents-apexalgo-iad -n argocd -o jsonpath='{.status.operationState.phase}'

# View ArgoCD logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server --tail=100
```

**Solution:**
```bash
# Manual sync
argocd app sync botburrow-agents-apexalgo-iad

# Force hard sync (delete and recreate)
argocd app sync botburrow-agents-apexalgo-iad --force
```

### SealedSecret Not Decrypting

**Symptom:** SealedSecret exists but Secret not created

**Diagnosis:**
```bash
# Check SealedSecret status
kubectl get sealedsecret -n botburrow-agents

# Check sealed-secrets controller
kubectl get pods -n sealed-secrets

# Check controller logs
kubectl logs -n sealed-secrets -l name=sealed-secrets-controller
```

**Solution:**
```bash
# Verify SealedSecret was created for correct cluster
kubeseal --format yaml --controller-namespace=sealed-secrets \
  --validate < k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml

# Recreate SealedSecret if cluster changed
kubeseal --format yaml --controller-namespace=sealed-secrets \
  < /tmp/secrets.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecret.yml
```

### Pods Not Starting After Sync

**Symptom:** Pods in CrashLoopBackOff or ImagePullBackOff

**Diagnosis:**
```bash
# Check pod status
kubectl get pods -n botburrow-agents

# Check pod logs
kubectl logs -n botburrow-agents <pod-name> --previous

# Describe pod for events
kubectl describe pod -n botburrow-agents <pod-name>
```

**Common Issues:**
- **ImagePullBackOff:** Image doesn't exist or registry auth failed
- **CrashLoopBackOff:** Missing secrets, invalid config, or app error
- **Pending:** Resource constraints or scheduling issues

---

## Comparison: Workaround vs GitOps

| Aspect | Workaround (bd-19j) | GitOps (bd-3he) |
|--------|---------------------|-----------------|
| **Deployment** | Manual kubectl | ArgoCD automated |
| **Sync** | Manual `kubectl apply` | Automated on git push |
| **Secrets** | Placeholder secrets | SealedSecrets (encrypted) |
| **Drift detection** | Manual | Automatic (self-heal) |
| **Rollback** | Manual `kubectl rollout` | Git revert |
| **Multi-cluster** | Repeat manual steps | Single Application manifest |
| **Audit trail** | Separate from git changes | All in git history |
| **Prerequisites** | kubectl access | ArgoCD + kubeseal |
| **Time to deploy** | Immediate | Setup required, then automated |
| **Production-ready** | No | Yes |

---

## Success Criteria

- [x] ArgoCD Application manifest created
- [x] SealedSecrets creation guide documented
- [x] Health check verification documented
- [ ] SealedSecrets created with real credentials
- [ ] ArgoCD Application deployed and syncing
- [ ] All resources deployed via ArgoCD
- [ ] Health checks passing
- [ ] Workaround archived/migrated
- [ ] GitOps workflow verified

---

## Related Files

**ArgoCD Configuration:**
- `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-application.yml`

**Botburrow-agents Manifests:**
- `/home/coder/botburrow-agents/k8s/apexalgo-iad/kustomization.yaml`
- `/home/coder/botburrow-agents/k8s/apexalgo-iad/kustomization-minimal.yaml`
- `/home/coder/botburrow-agents/k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml`

**Documentation:**
- `/home/coder/botburrow-agents/argocd-investigation-findings.md` (Original investigation)
- `/home/coder/botburrow-agents/docs/workarounds/bd-cni-argocd-workaround.md` (Workaround)
- `/home/coder/botburrow-agents/docs/research/bd-2z6-argocd-deployment-approaches.md` (Research)

---

## Next Steps

### Immediate (Human Action Required)
1. **Verify ArgoCD installation** in apexalgo-iad cluster
2. **Create SealedSecrets** with real credential values
3. **Deploy ArgoCD Application** from ardenone-cluster repo

### Automated (Worker Can Complete)
1. Update kustomization to include SealedSecrets (after they're created)
2. Verify ArgoCD sync status
3. Run health check verification script

### Follow-up Beads to Create
1. **bd-xxx**: Create SealedSecrets for botburrow-agents production deployment
2. **bd-xxx**: Verify ArgoCD sync and deployment health
3. **bd-xxx**: Archive workaround scripts after GitOps migration complete

---

**Document Version:** 1.0
**Last Updated:** 2026-02-08
**Author:** Claude Worker (claude-code-glm-47)

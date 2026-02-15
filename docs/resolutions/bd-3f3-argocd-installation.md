# Resolution Document: bd-3f3 - ArgoCD Installation

**Status:** READY FOR CLUSTER-ADMIN DEPLOYMENT
**Created:** 2026-02-15
**Worker:** claude-code-glm-47-lima
**Bead:** bd-3f3

---

## Executive Summary

This document provides step-by-step instructions for installing ArgoCD in the apexalgo-iad cluster. All manifests are prepared and tested. The installation requires **cluster-admin** privileges that workers do not have.

**Current State:**
- ✅ botburrow-agents namespace exists and is HEALTHY
- ✅ All pods running (coordinator, runners, valkey)
- ✅ All secrets created (botburrow-agents-secrets, mcp-credentials)
- ✅ SealedSecrets controller running
- ❌ ArgoCD NOT installed (namespace 'argocd' does not exist)
- ✅ ArgoCD manifests prepared in `k8s/apexalgo-iad/argocd/`

---

## Prerequisites

### Required Access
- ✅ Cluster-admin access to apexalgo-iad cluster
- ✅ kubectl configured with cluster-admin context

### Verification Commands

```bash
# Set kubeconfig for apexalgo-iad cluster
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Verify cluster-admin permissions
kubectl auth can-i create namespace
# Expected: yes

kubectl auth can-i '*' '*' --all-namespaces
# Expected: yes

# Verify botburrow-agents is running
kubectl get all -n botburrow-agents
# Expected: All pods Running, deployments at desired replicas
```

---

## Option 1: Install ArgoCD (RECOMMENDED)

### Why This Option?
- Enables full GitOps workflow for botburrow-agents
- All manifests are prepared and tested
- Comprehensive deployment guide available
- Allows automated sync from Git repository
- Minimal risk - botburrow-agents is already running, ArgoCD just adds automation

### Phase 1: Install ArgoCD

#### Step 1.1: Create ArgoCD Namespace

```bash
cd /home/coder/botburrow-agents
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

kubectl apply -f k8s/apexalgo-iad/argocd/namespace.yaml
```

**Expected output:**
```
namespace/argocd created
```

#### Step 1.2: Install ArgoCD

```bash
# Install ArgoCD (stable release)
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

**Expected output:**
```
customresourcedefinition.apiextensions.k8s.io/applications.argoproj.io created
customresourcedefinition.apiextensions.k8s.io/applicationsets.argoproj.io created
customresourcedefinition.apiextensions.k8s.io/appprojects.argoproj.io created
serviceaccount/argocd-application-controller created
serviceaccount/argocd-applicationset-controller created
...
deployment.apps/argocd-server created
deployment.apps/argocd-repo-server created
...
```

#### Step 1.3: Verify Installation

```bash
# Wait for all ArgoCD pods to be running (2-3 minutes)
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=argocd -n argocd --timeout=300s

# Check all pods are running
kubectl get pods -n argocd
```

**Expected output:**
```
NAME                                      READY   STATUS    RESTARTS   AGE
argocd-applicationset-controller-...      1/1     Running   0          2m
argocd-dex-server-...                     1/1     Running   0          2m
argocd-notifications-controller-...       1/1     Running   0          2m
argocd-redis-...                          1/1     Running   0          2m
argocd-repo-server-...                    1/1     Running   0          2m
argocd-server-...                         1/1     Running   0          2m
argocd-application-controller-...         1/1     Running   0          2m
```

#### Step 1.4: Get Admin Credentials (Optional - for UI access)

```bash
# Get initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
echo

# Save password securely for UI access
# Username: admin
# Password: <output from above command>
```

### Phase 2: Apply ArgoCD Application

#### Step 2.1: Apply Application Manifest

```bash
cd /home/coder/botburrow-agents

# Apply the Application manifest
kubectl apply -f k8s/apexalgo-iad/argocd-application.yaml
```

**Expected output:**
```
application.argoproj.io/botburrow-agents created
```

#### Step 2.2: Verify Application Sync

```bash
# Check Application exists
kubectl get applications.argoproj.io -n argocd

# Expected output:
# NAME                SYNC STATUS   HEALTH STATUS
# botburrow-agents    Synced        Healthy

# Check Application details
kubectl describe application botburrow-agents -n argocd

# Watch sync progress (Ctrl+C to exit)
kubectl get applications.argoproj.io -n argocd -w
```

#### Step 2.3: Verify GitOps Automation

```bash
# Check that ArgoCD is managing existing resources
kubectl get all -n botburrow-agents -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.app\.kubernetes\.io/instance}{"\n"}{end}'

# All resources should show "botburrow-agents" as instance
```

### Phase 3: Verification

#### Step 3.1: Health Check

```bash
# Verify all resources are healthy
kubectl wait --for=condition=ready pod -l app.kubernetes.io/part-of=botburrow -n botburrow-agents --timeout=60s

# Check Application health
kubectl get application botburrow-agents -n argocd -o jsonpath='{.status.health.status}'
echo

# Expected: Healthy
```

#### Step 3.2: Test GitOps Automation

**Manual test (optional):**
1. Make a small change to a deployment in git (e.g., add an annotation)
2. Commit and push to main branch
3. Wait 3 minutes for ArgoCD to detect change
4. Verify ArgoCD auto-synced the change

```bash
# Watch for auto-sync
kubectl get application botburrow-agents -n argocd -w
```

### Success Criteria

✅ ArgoCD namespace created
✅ All ArgoCD pods Running
✅ Application "botburrow-agents" created
✅ Application sync status: "Synced"
✅ Application health status: "Healthy"
✅ All botburrow-agents pods still Running

---

## Option 2: Use ApplicationSet Instead

### Pros
- More flexible for multi-environment deployments
- ApplicationSet manifest already prepared

### Cons
- Slightly more complex configuration
- Overkill for single-environment deployment

### Instructions

Follow **Phase 1** from Option 1, then:

```bash
cd /home/coder/botburrow-agents
export KUBECONFIG=/home/coder/.kube/apexalgo-iad.kubeconfig

# Apply ApplicationSet instead of Application
kubectl apply -f k8s/apexalgo-iad/argocd/applicationset.yaml

# Verify ApplicationSet created Application
kubectl get applicationsets.argoproj.io -n argocd
kubectl get applications.argoproj.io -n argocd
```

---

## Option 3: Skip ArgoCD, Keep kubectl Workaround

### Pros
- No additional infrastructure needed
- Simpler operational model
- Current deployment is working

### Cons
- No GitOps automation
- Manual kubectl required for updates
- Defeats purpose of bd-3e3 (GitOps deployment)

### Instructions

Close bead bd-3f3 with status "wont-fix" and document kubectl as permanent approach.

---

## Troubleshooting

### ArgoCD Pods Not Starting

```bash
# Check pod status
kubectl get pods -n argocd

# Describe failed pod
kubectl describe pod <pod-name> -n argocd

# Check logs
kubectl logs <pod-name> -n argocd
```

### Application Not Syncing

```bash
# Check Application status
kubectl get application botburrow-agents -n argocd -o yaml | grep -A 20 status

# Check sync errors
kubectl describe application botburrow-agents -n argocd

# Manual sync (if needed)
kubectl patch application botburrow-agents -n argocd -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}' --type merge
```

### Access Denied Errors

```bash
# Verify cluster-admin permissions
kubectl auth can-i create namespace
kubectl auth can-i create deployment -n argocd

# If "no", you do not have cluster-admin access
# Contact cluster administrator
```

---

## Post-Installation

### Access ArgoCD UI (Optional)

```bash
# Port-forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser to https://localhost:8080
# Login with username: admin, password from Phase 1 Step 1.4

# Change admin password immediately
# Admin Menu -> User Info -> Change Password
```

### Enable Ingress (Optional)

```bash
# Update host in ingress.yaml to your domain
# Edit: argocd.apexalgo.ardenone.com

kubectl apply -f k8s/apexalgo-iad/argocd/ingress.yaml
```

---

## Next Steps

After successful ArgoCD installation:

1. ✅ Close bead bd-3f3 (CLUSTER-ADMIN: Install ArgoCD)
2. ✅ Close bead bd-3e3 (Create ArgoCD GitOps deployment) - now completed
3. ✅ Verify automated sync works on git changes
4. ✅ Document ArgoCD access credentials securely
5. ✅ Monitor ApplicationSet for health status

---

## References

- **Comprehensive Deployment Guide:** `k8s/apexalgo-iad/argocd/DEPLOYMENT-GUIDE.md`
- **ArgoCD Application:** `k8s/apexalgo-iad/argocd-application.yaml`
- **ArgoCD ApplicationSet:** `k8s/apexalgo-iad/argocd/applicationset.yaml`
- **ArgoCD Namespace:** `k8s/apexalgo-iad/argocd/namespace.yaml`
- **ArgoCD Documentation:** https://argo-cd.readthedocs.io/
- **Original Bead:** bd-3e3 (Create ArgoCD GitOps deployment for botburrow-agents)

---

## Contact

**Issue:** bd-3f3
**Workspace:** /home/coder/botburrow-agents
**Cluster:** apexalgo-iad
**Required Permissions:** cluster-admin

**Questions?** Update bead bd-3f3 with comments or create follow-up bead.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-15
**Author:** Claude Worker (claude-code-glm-47-lima)

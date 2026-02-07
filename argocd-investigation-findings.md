# ArgoCD Investigation: botburrow-agents Deployment Issue

**Date:** 2026-02-07
**Bead:** bd-1v9
**Cluster:** apexalgo-iad

## Problem Statement

The botburrow-agents namespace exists but contains zero resources (no coordinator, runners, valkey, or other deployments). ArgoCD should be managing this namespace via the ApplicationSet, but resources are not being deployed.

## Investigation Findings

### 1. Namespace Status
- Namespace `botburrow-agents` exists (age: 5d23h)
- Has ArgoCD tracking-id annotation: `argocd.argoproj.io/tracking-id: botburrow-agents-ns-apexalgo-iad:/Namespace:/botburrow-agents`
- This confirms ArgoCD ApplicationSet HAS created an Application for botburrow-agents
- Namespace phase is Active

### 2. Resource Status
```
$ kubectl get all -n botburrow-agents
No resources found in botburrow-agents namespace.
```

Expected resources (from manifests):
- `coordinator` Deployment
- `coordinator` Service
- `valkey` Deployment
- `valkey` Service
- Multiple runner deployments
- ConfigMaps: `botburrow-agents-config`, `agent-permissions`
- SealedSecret: `botburrow-agents-secrets`

### 3. Git Repository Status
All manifests are tracked in git and pushed to GitHub:
```
cluster-configuration/apexalgo-iad/botburrow-agents/
├── .gitkeep
├── botburrow-agents-sealedsecret.yml
├── botburrow-agents-secret.yml.template
├── configmap.yaml
├── coordinator-git-sync.yaml
├── coordinator.yaml
├── hpa.yaml
├── namespace.yml
├── rbac.yaml
├── runner-exploration.yaml
├── runner-git-sync.yaml
├── runner-hybrid.yaml
├── runner-notification.yaml
├── servicemonitor.yaml
├── skill-sync.yaml
└── valkey.yaml
```

Recent commits:
- `76876f94 chore(bd-1v9): trigger botburrow-agents sync to GitHub`
- `3331f411 fix(botburrow-agents): switch to Docker Hub images`
- `abe2bce9 fix(botburrow): add IngressRoute with externaldns and fix HUB_URL`

### 4. Comparison with Working Applications

**forgejo (working):**
- Namespace has tracking-id annotation
- Resources ARE deployed (deployment, service, pods)
- SealedSecret IS deployed and unsealed
```
$ kubectl get sealedsecret -n forgejo
NAME              STATUS   SYNCED   AGE
forgejo-secrets            True     5d5h
```

**botburrow-agents (broken):**
- Namespace has tracking-id annotation
- Resources are NOT deployed
- SealedSecret is NOT deployed

### 5. Manifest Validation
All manifests are syntactically valid:
```bash
$ kubectl apply --dry-run=client -f cluster-configuration/apexalgo-iad/botburrow-agents/configmap.yaml
configmap/botburrow-agents-config created (dry run)
configmap/agent-permissions created (dry run)

$ kubectl apply --dry-run=client -f cluster-configuration/apexalgo-iad/botburrow-agents/botburrow-agents-sealedsecret.yml
sealedsecret.bitnami.com/botburrow-agents-secrets created (dry run)
```

### 6. ApplicationSet Configuration
From `/home/coder/ardenone-cluster/cluster-configuration/apexalgo-iad/apexalgo-iad-applicationset.yml`:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: manifest-appset-apexalgo-iad
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/ardenone/ardenone-cluster
        revision: HEAD
        directories:
          - path: cluster-configuration/apexalgo-iad/*
  template:
    metadata:
      name: '{{path.basename}}-ns-apexalgo-iad'
    spec:
      source:
        repoURL: https://github.com/ardenone/ardenone-cluster
        targetRevision: HEAD
        path: '{{path}}'
        directory:
          recurse: true
          include: '{*.yaml,*.yml}'
          exclude: '{ignore/*,*application.yml}'
```

## Root Cause Analysis

**Primary Hypothesis:** The ArgoCD Application `botburrow-agents-ns-apexalgo-iad` exists and has synced the Namespace resource, but the Application sync has stalled or failed for the remaining resources.

**Possible causes:**
1. ArgoCD sync error preventing resource deployment
2. Resource dependency issues (e.g., SealedSecret controller not processing)
3. ArgoCD health check failures preventing sync completion
4. ApplicationSet needs manual refresh/sync trigger

## Required Actions (Need ArgoCD Access)

1. Check ArgoCD Application status:
   ```
   kubectl get application botburrow-agents-ns-apexalgo-iad -n argocd -o yaml
   ```

2. Check Application sync status and health:
   ```
   argocd app get botburrow-agents-ns-apexalgo-iad
   ```

3. Check for sync errors in Application status

4. Manually trigger a sync if needed:
   ```
   argocd app sync botburrow-agents-ns-apexalgo-iad
   ```

## Workaround (If ArgoCD Access Not Available)

As a temporary workaround, resources could be deployed directly via kubectl:
```bash
kubectl apply -f cluster-configuration/apexalgo-iad/botburrow-agents/
```

However, this would bypass ArgoCD GitOps and create a divergence between git state and cluster state.

## Human Bead Created

A human bead (bd-3mqz) has been created to request ArgoCD access for debugging.

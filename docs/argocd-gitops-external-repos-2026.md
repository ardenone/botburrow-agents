# ArgoCD GitOps Best Practices 2026: External Repositories

**Research Date**: February 2026
**Sources**: Official ArgoCD Documentation, Community Best Practices, Industry Articles

---

## Executive Summary

This document provides comprehensive best practices for managing external Git repositories with ArgoCD, including configuration patterns, sync wave strategies, SealedSecrets integration, and common pitfalls to avoid. All recommendations are based on official documentation and 2026 community standards.

---

## 1. Configuring ArgoCD Applications for External Git Repositories

### 1.1 Multiple Sources Feature (Specific Use Cases Only)

**Official Warning**: ArgoCD explicitly warns against abusing multiple sources:
> "If you find yourself using more than 2-3 items in the `sources` array then you are almost certainly abusing this feature."
> — [ArgoCD Documentation - Multiple Sources](https://argo-cd.readthedocs.io/en/latest/user-guide/multiple_sources/)

#### Valid Use Case: External Helm Chart + Custom Values

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-billing-app
  namespace: argocd
spec:
  project: default
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  sources:
    # External Helm chart
    - repoURL: 'https://prometheus-community.github.io/helm-charts'
      chart: prometheus
      targetRevision: 15.7.1
      helm:
        valueFiles:
        - $values/charts/prometheus/values.yaml
    # Your Git repository with values
    - repoURL: 'https://git.example.com/org/value-files.git'
      targetRevision: HEAD
      ref: values
```

**Critical Requirements**:
- The `$values` variable can only be used at the beginning of the value file path
- Its path is always relative to the root of the referenced source
- If the `path` field is set in the `$values` source, ArgoCD will attempt to generate resources from the git repository
- If the `path` field is not set, ArgoCD uses the repository solely as a source of value files
- Sources with the `ref` field set cannot include the `chart` field

### 1.2 Declarative Setup (Best Practice)

**Core GitOps Principle**: Store ALL ArgoCD Application manifests in Git.

```yaml
# Store this in Git, not created via UI/CLI
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: external-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/external-org/chart-repo.git
    targetRevision: HEAD
    path: manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**2026 Recommendation**:
> "Recovering an ArgoCD instance should take less than 5 minutes" when everything is declaratively stored in Git.
> — [Codefresh: Top 30 ArgoCD Anti-Patterns (2025)](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/)

**Recovery Process**:
1. Create a new cluster with Terraform/Pulumi/Crossplane
2. Install ArgoCD using Terraform/Helm
3. Point ArgoCD to your ApplicationSets or root app-of-apps file
4. Finished

---

## 2. Sync Waves and Resource Ordering Best Practices

### 2.1 Sync Wave Configuration

ArgoCD orders resources by:
1. **Phase** (pre-sync, sync, post-sync)
2. **Wave number** (lower first for creation, higher first for deletion)
3. **Kind** (namespaces first)
4. **Name**

#### Example Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-deployment
  annotations:
    argocd.argoproj.io/sync-wave: "0"
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  annotations:
    argocd.argoproj.io/sync-wave: "1"
```

### 2.2 Recommended Wave Pattern

| Wave | Resources | Description |
|------|-----------|-------------|
| **-2** | CRDs, Namespaces | Foundation resources |
| **-1** | SealedSecrets, ExternalSecrets | Secrets before applications |
| **0** | ConfigMaps, Secrets, PVs/PVCs | Configuration data |
| **1** | Deployments, StatefulSets, DaemonSets | Main applications |
| **2** | Services, IngressRoutes | Networking |
| **3** | Monitoring, Observability | Post-deployment resources |

**Default Delay**: 2 seconds between waves (configurable via `ARGOCD_SYNC_WAVE_DELAY`)

### 2.3 Critical Anti-Patterns to Avoid

> "Do not use sync-waves for database migrations (use a Database migration operator)"
> — [Codefresh Anti-Patterns #23](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/)

**Sync waves should NOT be used for**:
- Database migrations → Use a Database migration operator (e.g., AtlasGo)
- Long-running tasks with complex logic → Use Argo Workflows
- CI/CD pipeline recreation → Use proper CI/CD tools

**Proper Tool Selection**:
- **ArgoCD Sync Waves**: Idempotent, quick tasks (notifications, smoke tests)
- **Argo Workflows**: Complex orchestration with retries, fan-in/fan-out, artifact storage
- **Argo Rollouts**: Progressive delivery and automated rollbacks

---

## 3. SealedSecrets Integration with ArgoCD

### 3.1 Recommended Approach: Cluster-Based Secret Management

**ArgoCD Official Recommendation**:
> "We strongly recommend [cluster-based secret management] as it is more secure and provides a better user experience."
> — [ArgoCD Documentation - Secret Management](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/)

### 3.2 SealedSecrets Workflow

#### Step 1: Encrypt Secrets

```bash
# Create a secret
echo -n 'my-password' | kubectl create secret generic example-secret \
  --dry-run=client --from-file=password=/dev/stdin -o yaml > secret.yaml

# Seal the secret
kubeseal --format yaml -f secret.yaml > sealed-secret.yaml
```

#### Step 2: Deploy SealedSecret via ArgoCD

```yaml
# SealedSecret (SAFE to commit to Git)
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: app-secrets
  namespace: production
  annotations:
    argocd.argoproj.io/sync-wave: "-1"  # Deploy before applications
spec:
  encryptedData:
    password: AgBy8iO... # Encrypted, safe for Git
  template:
    metadata:
      name: app-secrets
      namespace: production
    type: Opaque
```

### 3.3 Key Benefits

| Benefit | Description |
|---------|-------------|
| **Kubernetes-native** | Integrates into Kubernetes workflows |
| **Prevents value overriding** | Encrypting secrets ensures values remain consistent |
| **Multi-cluster secret sharing** | Reuse same encrypted secret across clusters |
| **Secure GitOps** | Encrypted data in Git, no plain text secrets |

### 3.4 Alternative: External Secrets Operator

For external secret management systems (Vault, AWS Secrets Manager, etc.):

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "http://vault.vault:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "demo"
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-db-credentials
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
spec:
  refreshInterval: "20s"
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: mysql-credentials
  data:
    - secretKey: db_url
      remoteRef:
        key: mysql_credentials
        property: url
```

### 3.5 Why Cluster-Based Secret Management?

**vs Manifest Generation-Based (argocd-vault-plugin)**:
- **Security**: ArgoCD doesn't need access to secrets
- **User Experience**: Secret updates decoupled from app sync
- **Compatibility**: Works with "Rendered Manifests" pattern

**Manifest generation risks**:
- ArgoCD caches secrets in Redis (plaintext)
- Secret updates coupled with app sync operations
- Incompatible with rendered manifests pattern

---

## 4. Common Pitfalls with External Repositories

### Pitfall #1: Abusing Multi-Source Feature

**Problem**: Using multiple sources to group unrelated applications

**Solution**: Use ApplicationSets
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: external-apps
spec:
  generators:
  - git:
      repoURL: https://github.com/external-org/apps.git
      revision: HEAD
      directories:
      - path: apps/*
  template:
    spec:
      source:
        repoURL: '{{repoURL}}'
        targetRevision: HEAD
```

### Pitfall #2: Not Separating Config from Source Code

**Problem**: Mixing source code, manifests, and ArgoCD applications in one repo

**Solution**: Three-repository pattern
- **Repository A**: Application source code
- **Repository B**: Kubernetes manifests (Helm charts/Kustomize)
- **Repository C**: ArgoCD Application/ApplicationSet manifests

**Benefits**:
- Cleaner audit logs
- Prevents CI trigger loops
- Separate access control
- Independent versioning

### Pitfall #3: Hardcoding Helm/Kustomize Data

**Anti-Pattern**:
```yaml
# DON'T DO THIS
apiVersion: argoproj.io/v1alpha1
kind: Application
spec:
  source:
    helm:
      parameters:
      - name: "image.tag"
        value: "v1.2.3"
```

**Correct Approach**:
```yaml
# DO THIS
apiVersion: argoproj.io/v1alpha1
kind: Application
spec:
  source:
    helm:
      valueFiles:
      - values-production.yaml  # Stored in Git repo
```

### Pitfall #4: Using Dynamic/Unstable References

**Problem**: Using mutable tags like `HEAD` or `v1.2` for critical infrastructure

**Solution**: Use immutable references
```yaml
# SAFE
bases:
- github.com/argoproj/argo-cd//manifests/cluster-install?ref=v2.8.0

# RISKY
resources:
- github.com/argoproj/argo-cd//manifests/cluster-install
```

### Pitfall #5: Disabling Auto-Sync and Self-Heal

**Problem**: Disabling auto-sync to "lock down" production

**Impact**: Loses configuration drift detection - the main benefit of ArgoCD

**Solution**: Keep auto-sync enabled, enforce governance via:
- Protected branches
- Required pull request reviews
- CI/CD checks before merge

### Pitfall #6: App-of-Apps vs ApplicationSet Confusion

| Pattern | Use Case |
|---------|----------|
| **App-of-Apps** | Cluster bootstrapping, static groups |
| **ApplicationSet** | Dynamic generation, multi-cluster, multi-team |

**2026 Recommendation**: Prefer ApplicationSets over app-of-apps for most scenarios

### Pitfall #7: Using targetRevision for Promotions

**Problem**: Updating targetRevision field for environment promotion

**Solution**: Promote values/overlays, not Application manifests
- Copy values from QA overlay to Production overlay
- Application manifests remain static

### Pitfall #8: Creating Dynamic Applications

**Anti-Pattern**:
```bash
# DON'T DO THIS
my-app-cli new-app-name | argocd app create -f -
envsubst < my-app-template.yaml | kubectl apply -f -n argocd
```

**Solution**: Store all Application manifests in Git, use Git as single source of truth

### Pitfall #9: Using ArgoCD Parameter Overrides

**Problem**: Using `argocd app set` to override parameters

**Impact**: Goes against GitOps principles, destroys local testing

**Solution**: Store all parameters in Helm values or Kustomize overlays

---

## 5. ApplicationSet Best Practices for External Repositories

### 5.1 Git Generator

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: external-git-apps
spec:
  generators:
  - git:
      repoURL: https://github.com/external-org/apps.git
      revision: HEAD
      directories:
      - path: apps/*
  template:
    spec:
      project: default
      source:
        repoURL: '{{repoURL}}'
        targetRevision: '{{revision}}'
        path: '{{path}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{namespace}}'
```

**Note**: Git generator polls repositories every 3 minutes by default

### 5.2 Cluster Generator

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: multi-cluster-apps
spec:
  generators:
  - clusters: {}
  template:
    spec:
      source:
        repoURL: https://github.com/org/apps.git
        targetRevision: HEAD
        path: apps/myapp
      destination:
        server: '{{server}}'
        namespace: myapp
```

### 5.3 Matrix Generator

Combines multiple generators for complex scenarios:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: matrix-example
spec:
  generators:
  - matrix:
      generators:
      - git:
          repoURL: https://github.com/org/apps.git
          revision: HEAD
          directories:
          - path: apps/*
      - clusters:
          selector:
            matchLabels:
              environment: production
```

---

## 6. Private Repository Credential Management

### 6.1 SSH Authentication

```bash
# Add SSH known hosts
argocd cert add-ssh --known-hosts-string github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQAWgc9Qh5...

# Create secret with SSH key
kubectl create secret generic github-secret \
  --from-file=sshPrivateKey=./id_rsa \
  --from-file=sshKnownHosts=./known_hosts \
  -n argocd

# Reference in Application
apiVersion: argoproj.io/v1alpha1
kind: Application
spec:
  source:
    repoURL: git@github.com:org/private-repo.git
    targetRevision: HEAD
```

### 6.2 HTTPS Authentication

```bash
# Create secret with username/password
kubectl create secret generic private-repo \
  --from-literal=username=myuser \
  --from-literal=password=mypassword \
  -n argocd
```

### 6.3 Declarative Credential Templates

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: repo-creds-template
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repo-creds
type: Opaque
stringData:
  url: https://git.example.com/*
  username: myuser
  password: mypassword
```

---

## 7. Resource Health Checks for Custom Resources

### 7.1 Built-in Health Checks

ArgoCD provides built-in health assessment for standard Kubernetes types.

### 7.2 Custom Health Checks

For CRDs without built-in support:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  resource.customizations.health.bitnami.com_SealedSecret: |
    hs = {}
    if obj.status ~= nil then
      if obj.status.conditions ~= nil then
        for i, condition in ipairs(obj.status.conditions) do
          if condition.type == "Ready" and condition.status == "True" then
            hs.status = "Healthy"
            hs.message = condition.message
            return hs
          end
        end
      end
    end
    hs.status = "Progressing"
    hs.message = "Waiting for SealedSecret to be decrypted"
    return hs
```

### 7.3 Lua Script Health Check Example

```lua
hs = {}
if obj.status ~= nil then
  if obj.status.ready == true then
    hs.status = "Healthy"
    hs.message = "Resource is ready"
    return hs
  end
end
hs.status = "Progressing"
hs.message = "Waiting for resource to be ready"
return hs
```

---

## 8. Summary of Key Recommendations

| Area | Best Practice | Source |
|------|--------------|--------|
| **External Repos** | Use multiple sources only for Helm chart + values (2-3 items max) | [ArgoCD Docs](https://argo-cd.readthedocs.io/en/latest/user-guide/multiple_sources/) |
| **Application Management** | Use ApplicationSets instead of manual Applications | [Codefresh 2024](https://codefresh.io/blog/how-to-structure-your-argo-cd-repositories-using-application-sets/) |
| **Secret Management** | Use SealedSecrets/External Secrets (cluster-based) | [ArgoCD Docs](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/) |
| **Repository Structure** | Separate source code, manifests, and ArgoCD apps | [ArgoCD Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/) |
| **Sync Waves** | Use for resource ordering, not orchestration | [ArgoCD Docs](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/) |
| **Auto-Sync** | Keep enabled even in production | [Codefresh 2025](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/) |
| **Immutability** | Use commit SHA/tags, avoid mutable references | [ArgoCD Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/) |
| **Promotion** | Promote values/overlays, not targetRevision | [Codefresh 2025](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/) |
| **Declarative Setup** | Store ALL Application CRDs in Git | [Codefresh 2025](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/) |
| **DB Migrations** | Use Database migration operator, not sync-waves | [Codefresh Anti-Pattern #23](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/) |

---

## 9. Sources

1. [ArgoCD Official Documentation - Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
2. [ArgoCD Official Documentation - Multiple Sources](https://argo-cd.readthedocs.io/en/latest/user-guide/multiple_sources/)
3. [ArgoCD Official Documentation - Sync Phases and Waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
4. [ArgoCD Official Documentation - Secret Management](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/)
5. [ArgoCD Official Documentation - Declarative Setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
6. [ArgoCD Official Documentation - ApplicationSet Git Generator](https://argo-cd.readthedocs.io/en/latest/operator-manual/applicationset/Generators-Git/)
7. [ArgoCD Official Documentation - Resource Health](https://argo-cd.readthedocs.io/en/latest/operator-manual/health/)
8. [Codefresh: Top 30 ArgoCD Anti-Patterns to Avoid (August 2025)](https://codefresh.io/blog/argo-cd-anti-patterns-for-gitops/)
9. [Codefresh: Structuring ArgoCD Repositories with ApplicationSets (May 2024)](https://codefresh.io/blog/how-to-structure-your-argo-cd-repositories-using-application-sets/)
10. [Codefresh: ArgoCD Secrets Guide (February 2025)](https://codefresh.io/learn/argo-cd/argocd-secrets/)
11. [Akuity: Managing Application Dependencies with ArgoCD (March 2024)](https://akuity.io/blog/application-dependencies-with-argo-cd)
12. [OneUptime: How to Build ArgoCD Resource Health Checks (January 2026)](https://oneuptime.com/blog/post/2026-01-30-argocd-resource-health-checks/view)
13. [ArgoCD GitHub: ApplicationSet Generator Documentation](https://github.com/argoproj/applicationset/blob/master/docs/Generators-Git.md)
14. [GitOps Collection: ApplicationSet with Matrix Generator (April 2025)](https://blog.stderr.at/gitopscollection/2025-04-17-applicationset-defining-namespaces/)

---

## Appendix: Quick Reference

### A. Multi-Source Application Template

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: multi-source-app
  namespace: argocd
spec:
  sources:
  - repoURL: 'https://charts.helm.sh/stable'
    chart: nginx-ingress
    targetRevision: '1.0.0'
    helm:
      valueFiles:
      - $values/values.yaml
  - repoURL: 'https://github.com/org/values.git'
    targetRevision: HEAD
    ref: values
  destination:
    server: https://kubernetes.default.svc
    namespace: ingress
```

### B. SealedSecret with Sync Wave

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: app-secrets
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
spec:
  encryptedData:
    api-key: AgBy8iO...
  template:
    type: Opaque
```

### C. ApplicationSet Git Generator

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: git-generator-apps
spec:
  generators:
  - git:
      repoURL: https://github.com/org/apps.git
      revision: HEAD
      directories:
      - path: apps/*
  template:
    spec:
      project: default
      source:
        repoURL: '{{repoURL}}'
        targetRevision: '{{revision}}'
        path: '{{path}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

---

*Document maintained by: Claude (Anthropic)*
*Last updated: February 2026*

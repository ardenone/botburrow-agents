# Secrets Management Approaches for botburrow-agents

**Research Document for:** bd-2hq (Fix kustomization.yaml to remove secrets.yaml reference)
**Alternative Bead:** bd-31q
**Date:** 2026-02-08

## Problem Summary

The `kustomization.yaml` previously referenced `secrets.yaml` which contained placeholder values. This file was correctly deleted, but the reference remains and needs to be addressed. This document compares various approaches for managing secrets in this Kubernetes/GitOps deployment.

## Current State

**kustomization.yaml (lines 13-20):**
```yaml
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  # secrets.yaml removed - use botburrow-agents-sealedsecret.yml instead
  # To create SealedSecret from template:
  #   1. cp botburrow-agents-secret.yml.template botburrow-agents-secret.yml
  #   2. Fill in all REPLACE_* values
  #   3. kubeseal --format yaml < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml
  #   4. rm botburrow-agents-secret.yml
  # Then add botburrow-agents-sealedsecret.yml here
  - valkey.yaml
  ...
```

**Existing Files:**
- `botburrow-agents-secret.yml.template` - Template with REPLACE_* placeholders
- `botburrow-agents-secrets-PLACEHOLDER.yml` - Placeholder secrets for initial deployment

**Secrets Required:**
- `botburrow-agents-secrets`: HUB_API_KEY, R2 credentials, FORGEJO_TOKEN, GITHUB_TOKEN
- `mcp-credentials`: GITHUB_PAT, BRAVE_API_KEY, ANTHROPIC_API_KEY

---

## Option 1: Keep Current State (Comments Only)

**Description:** Leave kustomization.yaml as-is with commented instructions. Secrets must be manually created by cluster-admin.

**Implementation:**
- No changes needed - current state is already this approach
- Admin manually applies: `kubectl apply -f botburrow-agents-secrets-PLACEHOLDER.yml`
- Then updates values via `kubectl edit secret`

**Pros:**
- Zero code changes needed
- Secrets never touch git (even encrypted)
- Simple for clusters without SealedSecret controller
- Works with manual cluster-admin deployment workflow

**Cons:**
- Not true GitOps - secrets managed outside git
- No audit trail of secret changes
- Manual deployment required for secrets
- Secrets drift between environments possible
- Can't automate cluster provisioning

**Best For:**
- Development/staging clusters
- Manual deployment workflows
- Clusters without SealedSecret controller

---

## Option 2: SealedSecrets (GitOps-Native)

**Description:** Use Bitnami SealedSecrets for encrypted, commit-safe secrets in git.

**Implementation:**
```bash
# 1. Create from template
cp botburrow-agents-secret.yml.template botburrow-agents-secret.yml
# 2. Fill in values
# 3. Seal
kubeseal --format yaml < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml
# 4. Update kustomization.yaml
# Add: - botburrow-agents-sealedsecret.yml
# 5. Commit sealed secret
```

**Pros:**
- True GitOps - everything in git including secrets
- Encrypted at rest in git repository
- Automatic secret sync via ArgoCD
- Audit trail of secret changes
- Cluster-specific encryption (controller-only decryption)
- Zero manual steps after initial setup

**Cons:**
- Requires SealedSecret controller installed in cluster
- Requires controller certificate for sealing (cluster-specific)
- Can't share sealed secrets between clusters
- Additional infrastructure dependency
- Learning curve for kubeseal CLI

**Best For:**
- Production environments
- Multi-cluster GitOps deployments
- Teams wanting full automation
- Projects already using ArgoCD

---

## Option 3: External Secrets Operator

**Description:** Use External Secrets Operator to sync secrets from external vaults (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, etc.).

**Implementation:**
```yaml
# Create ExternalSecret manifest
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: botburrow-agents-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: botburrow-agents-secrets
  data:
    - secretKey: HUB_API_KEY
      remoteRef:
        key: botburrow-agents/hub-api-key
```

**Pros:**
- Centralized secret management
- Automatic secret rotation support
- No secrets in git (encrypted or plain)
- Works with existing secret vaults
- Fine-grained access control
- Audit logging in external systems

**Cons:**
- Requires external secret store (cost, complexity)
- Additional operator dependency
- External dependency (network, availability)
- More complex setup
- Provider lock-in potential

**Best For:**
- Organizations with existing secret vaults
- Enterprise environments with compliance requirements
- Multi-service deployments sharing secrets
- Scenarios requiring automatic rotation

---

## Option 4: Environment-Specific Kustomize Overlays

**Description:** Use Kustomize overlays with environment-specific secret generators.

**Implementation:**
```
bases/
  └── base/
      └── kustomization.yaml (no secrets)
overlays/
  ├── dev/
  │   ├── kustomization.yaml (secret generator for dev)
  │   └── secrets.env (dev values, gitignored)
  ├── staging/
  │   ├── kustomization.yaml (secret generator for staging)
  │   └── secrets.env (staging values, gitignored)
  └── prod/
      └── kustomization.yaml (references SealedSecrets)
```

**Pros:**
- Environment-specific configurations
- Flexible per-environment approaches
- Standard Kustomize pattern
- Clear separation of concerns

**Cons:**
- Secrets in .env files (gitignored) can be lost
- Manual secret management per environment
- No unified secret audit trail
- More complex directory structure
- .env files easily committed by mistake

**Best For:**
- Multi-environment deployments
- Teams familiar with Kustomize overlays
- Different secret strategies per environment

---

## Option 5: Manual Secret Reference Documentation

**Description:** Create comprehensive documentation for manual secret creation. Update kustomization with clear instructions.

**Implementation:**
```yaml
# kustomization.yaml
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  # SECRETS MANUAL SETUP REQUIRED
  # See: SECRETS.md for complete instructions
  - valkey.yaml
  ...
```

Add `SECRETS.md` with:
- Required secrets and their formats
- Creation commands for each secret type
- Validation steps
- Troubleshooting guide

**Pros:**
- Simple, no new dependencies
- Clear documentation for operators
- Flexible for any secret backend
- Low maintenance

**Cons:**
- Still manual secret creation
- Human error risk
- Not automated
- Deployment not reproducible

**Best For:**
- Small teams
- Development environments
- Situations with diverse secret backends

---

## Comparison Matrix

| Approach | GitOps Native | Automated Setup | External Deps | Secret Rotation | Security |
|----------|---------------|-----------------|---------------|-----------------|----------|
| Comments Only | ❌ | ❌ | None | Manual | Medium |
| SealedSecrets | ✅ | ✅ | Controller | Manual | High |
| External Secrets | ✅ | ✅ | Operator+Vault | Auto | Very High |
| Kustomize Overlays | Partial | ❌ | None | Manual | Medium |
| Documentation | ❌ | ❌ | None | Manual | Low |

---

## Recommended Approach

### For botburrow-agents: **Option 2 (SealedSecrets) with Option 1 Fallback**

**Rationale:**
1. **Primary:** Use SealedSecrets for production/deployed clusters
   - True GitOps alignment
   - Already using ArgoCD
   - SealedSecret controller likely available
   - Template already exists (`botburrow-agents-secret.yml.template`)

2. **Fallback:** Keep current comments for dev clusters
   - Allows development without SealedSecret controller
   - `botburrow-agents-secrets-PLACEHOLDER.yml` for quick setup

**Implementation Steps:**

```yaml
# kustomization.yaml - Proposed change
resources:
  - namespace.yaml
  - rbac.yaml
  - configmap.yaml
  # Production: Add sealed secrets below after creating with kubeseal
  # Dev/Testing: Apply botburrow-agents-secrets-PLACEHOLDER.yml manually
  # - botburrow-agents-sealedsecret.yml  # UNCOMMENT for production
  # - mcp-credentials-sealedsecret.yml    # UNCOMMENT for production
  - valkey.yaml
  ...
```

**Add to README.md:**
```markdown
## Secrets Setup

### Development (Quick Start)
```bash
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
```

### Production (SealedSecrets)
```bash
cd k8s/apexalgo-iad
cp botburrow-agents-secret.yml.template botburrow-agents-secret.yml
# Edit file with real values
kubeseal --format yaml < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml
rm botburrow-agents-secret.yml
# Uncomment sealed secrets in kustomization.yaml
git add botburrow-agents-sealedsecret.yml kustomization.yaml
```
```

---

## Next Steps (Human Decision Required)

1. **Choose primary approach** for your deployment environment
2. **For SealedSecrets:** Confirm controller is installed in apexalgo-iad cluster
3. **Update kustomization.yaml** based on chosen approach
4. **Update documentation** (README.md) with secret setup instructions
5. **Close bd-2hq** once kustomization.yaml is updated

---

## Appendix: Check for SealedSecret Controller

```bash
# Check if SealedSecret controller is installed
kubectl get deployment -n kube-system sealed-secrets-controller
# OR
kubectl get crd sealedsecrets.bitnami.com

# If not installed, install with:
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml
```

# SealedSecret Creation Options for botburrow-agents

**Research Document for:** bd-1dx (Alternative: Research and document options)
**Original Bead:** bd-1x8 (Create SealedSecret for botburrow-agents from template)
**Date:** 2026-02-08
**Status:** Ready for Human Decision

---

## Executive Summary

This document provides a comprehensive comparison of approaches for creating SealedSecrets for the botburrow-agents deployment. The original bead bd-1x8 was blocked due to requiring human input for secret values. This research documents multiple approaches to enable informed decision-making.

**Key Finding:** SealedSecret controller is **installed and operational** in the `sealed-secrets` namespace, and `kubeseal` CLI (v0.24.0) is available in the devpod environment.

---

## Current State Assessment

### Infrastructure Available
| Component | Status | Details |
|-----------|--------|---------|
| SealedSecret CRD | ✅ Installed | `sealedsecrets.bitnami.com` (created 2025-09-07) |
| SealedSecret Controller | ✅ Running | Deployment: `sealed-secrets-ardenone-cluster` in `sealed-secrets` namespace |
| kubeseal CLI | ✅ Available | Version 0.24.0 at `/usr/local/bin/kubeseal` |
| Template File | ✅ Exists | `k8s/apexalgo-iad/botburrow-agents-secret.yml.template` |
| Placeholder Secret | ✅ Exists | `k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml` |

### Required Secret Values
The template requires 10 secret values:
1. `HUB_API_KEY` - Botburrow Hub API key
2. `R2_ENDPOINT` - Cloudflare R2 endpoint URL
3. `R2_ACCESS_KEY` - R2 access key ID
4. `R2_SECRET_KEY` - R2 secret access key
5. `FORGEJO_USER` - Forgejo service account username
6. `FORGEJO_TOKEN` - Forgejo access token
7. `GITHUB_USER` - GitHub username
8. `GITHUB_TOKEN` - GitHub PAT with repo scope
9. `GITHUB_PAT` - GitHub PAT for MCP github server
10. `BRAVE_API_KEY` - Brave Search API key

---

## Option 1: Standard kubeseal CLI Workflow (Recommended)

### Description
Use the standard kubeseal CLI to create SealedSecrets from the template. This is the documented GitOps-native approach.

### Implementation Steps

```bash
# 1. Navigate to k8s directory
cd /home/coder/botburrow-agents/k8s/apexalgo-iad

# 2. Copy template and fill with real values
cp botburrow-agents-secret.yml.template botburrow-agents-secret.yml
# EDIT botburrow-agents-secret.yml with real credential values

# 3. Create SealedSecret (automatic controller detection)
kubeseal --format yaml < botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml

# 4. Secure cleanup
rm botburrow-agents-secret.yml
# Verify no plaintext secret remains
git status  # Should show only sealedsecret.yml as untracked

# 5. Update kustomization.yaml
# Add these lines to resources:
#   - botburrow-agents-sealedsecret.yml

# 6. Commit to git
git add botburrow-agents-sealedsecret.yml kustomization.yaml
git commit -m "feat: add SealedSecret for botburrow-agents"
```

### Pros
- ✅ **GitOps-native** - Everything version-controlled
- ✅ **Secure** - Encrypted at rest in git repository
- ✅ **Automated sync** - ArgoCD automatically applies changes
- ✅ **Audit trail** - All secret changes tracked in git history
- ✅ **Cluster-specific** - Only this cluster can decrypt
- ✅ **No manual steps** after initial setup
- ✅ **Tooling available** - kubeseal CLI already installed

### Cons
- ❌ **Requires real values** - Human must provide all 10 credential values
- ❌ **Single-cluster** - SealedSecrets are cluster-specific (can't share between clusters)
- ❌ **Controller dependency** - Requires SealedSecret controller operational
- ❌ **Initial effort** - One-time setup requires gathering all credentials

### Best For
- Production deployments
- Environments with SealedSecret controller
- Teams wanting full GitOps automation
- Situations where credentials are available

### Security Notes
- SealedSecrets use asymmetric encryption (RSA 4096-bit)
- Only the SealedSecret controller can decrypt (via private key)
- Encrypted data in git is safe to commit
- Controller certificate rotation required for key rotation

---

## Option 2: Placeholder Secrets with Deferred Real Values

### Description
Use placeholder secrets to unblock deployment immediately. Real values are added later by cluster-admin via `kubectl edit secret`. This is the **workaround approach** already documented in `bd-1fj-sealedsecret-workaround.md`.

### Implementation Steps

```bash
# 1. Apply placeholder secrets (cluster-admin only)
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# 2. Verify secrets exist
kubectl get secrets -n botburrow-agents

# 3. Deployment proceeds with placeholders

# 4. Later: Update with real values (cluster-admin)
kubectl edit secret botburrow-agents-secrets -n botburrow-agents
kubectl edit secret mcp-credentials -n botburrow-agents

# 5. Optional: Create SealedSecret later for GitOps
# Follow Option 1 steps when real values are available
```

### Pros
- ✅ **Immediate unblock** - No credential gathering bottleneck
- ✅ **Simple** - No encryption/kubeseal complexity
- ✅ **Flexible** - Secrets can be updated anytime
- ✅ **Quick start** - Infrastructure deployment proceeds
- ✅ **No special tooling** - Standard kubectl only

### Cons
- ❌ **Not GitOps** - Secret changes not tracked in git
- ❌ **Manual** - Requires cluster-admin intervention for updates
- ❌ **No audit trail** - Secret changes not logged
- ❌ **Drift risk** - Secrets may differ between environments
- ❌ **Security risk** - Potential for misplaced credentials during manual editing
- ❌ **Not reproducible** - Can't automate cluster provisioning

### Best For
- Development environments
- Quick proof-of-concept deployments
- Situations where credentials aren't immediately available
- Temporary unblocking while credentials are gathered

---

## Option 3: Multi-Stage Workflow (Placeholder → SealedSecret)

### Description
Hybrid approach: Start with placeholders for immediate deployment, then transition to SealedSecrets for production. This combines the speed of Option 2 with the GitOps benefits of Option 1.

### Implementation Steps

```bash
# === STAGE 1: Initial Deployment (Placeholders) ===

# 1. Apply placeholder secrets immediately
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# 2. Proceed with deployment validation
# Deployment unblocked, infrastructure proceeds

# === STAGE 2: Gather Credentials (Parallel Work) ===

# While deployment proceeds, gather real credentials:
# - Request HUB_API_KEY from Hub admin
# - Configure R2 access in Cloudflare dashboard
# - Generate Forgejo token
# - Create GitHub PATs
# - Get Brave API key

# === STAGE 3: Transition to SealedSecret (When Ready) ===

# 1. Create SealedSecret (from template with real values)
cp botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
# Edit with real values
kubeseal --format yaml < /tmp/botburrow-agents-secret.yml > botburrow-agents-sealedsecret.yml

# 2. Update kustomization.yaml to include sealedsecret
echo "  - botburrow-agents-sealedsecret.yml" >> kustomization.yaml

# 3. Commit SealedSecret
git add botburrow-agents-sealedsecret.yml kustomization.yaml
git commit -m "feat: add SealedSecret for botburrow-agents"

# 4. ArgoCD syncs automatically, replacing the placeholder secret

# 5. (Optional) Remove placeholder if desired
kubectl delete secret botburrow-agents-secrets -n botburrow-agents --ignore-not-found
```

### Pros
- ✅ **Best of both worlds** - Immediate unblock + eventual GitOps
- ✅ **Parallel work** - Credential gathering happens alongside deployment
- ✅ **Smooth transition** - No deployment downtime
- ✅ **Flexible timing** - Can transition when convenient
- ✅ **Risk mitigation** - Infrastructure validated before adding real credentials

### Cons
- ⚠️ **Two-stage process** - Requires coordination
- ⚠️ **Temporary manual state** - Brief period of non-GitOps secrets
- ⚠️ **Transition complexity** - Need to ensure proper switch-over

### Best For
- Production environments where credentials aren't immediately available
- Teams wanting GitOps but needing to start quickly
- Phased rollouts with gradual credential hardening
- Situations where credential approval workflows take time

---

## Option 4: Direct kubectl seal (Without Intermediate File)

### Description
Use a one-liner command that pipes the template directly to kubeseal without creating an intermediate file. This is a security hardening variant of Option 1.

### Implementation Steps

```bash
# Method A: Using heredoc (no file created)
kubeseal --format yaml --scope=strict <<EOF | tee botburrow-agents-sealedsecret.yml
apiVersion: v1
kind: Secret
metadata:
  name: botburrow-agents-secrets
  namespace: botburrow-agents
type: Opaque
stringData:
  HUB_API_KEY: "actual-value-here"
  R2_ENDPOINT: "https://actual.r2.cloudflarestorage.com"
  R2_ACCESS_KEY: "actual-access-key"
  R2_SECRET_KEY: "actual-secret-key"
  FORGEJO_USER: "botburrow-agents"
  FORGEJO_TOKEN: "actual-token"
  GITHUB_USER: "actual-username"
  GITHUB_TOKEN: "actual-gh-token"
EOF

# Method B: Using env vars with automatic templating
# Requires template file with ${VAR} placeholders
export HUB_API_KEY="actual-value"
export R2_ENDPOINT="https://actual.r2.cloudflarestorage.com"
# ... set other env vars ...
envsubst < botburrow-agents-secret.yml.template | kubeseal --format yaml > botburrow-agents-sealedsecret.yml
unset HUB_API_KEY R2_ENDPOINT  # Clear env vars immediately
```

### Pros
- ✅ **Enhanced security** - No plaintext secret file ever touches disk
- ✅ **Clean workflow** - Single command produces sealed result
- ✅ **Shell history safety** - With proper history control, values not logged
- ✅ **All GitOps benefits** - From Option 1

### Cons
- ❌ **Shell history risk** - Values may be logged in bash history
- ❌ **Complexity** - Requires careful shell handling
- ❌ **Error prone** - Typos in heredoc require retry
- ❌ **Still requires real values** - Same blocker as Option 1

### Best For
- Security-conscious teams
- Environments with strict no-plaintext policies
- Automated scripts where file cleanup is concern
- Teams comfortable with shell scripting

### Security Recommendations for This Approach
```bash
# Disable history before command
set +o history

# Run kubeseal command

# Re-enable history after
set -o history

# Or use HISTCONTROL
export HISTCONTROL=ignorespace
# Space-prefix commands to exclude from history
  kubeseal --format yaml <<EOF
```

---

## Option 5: External Secrets Operator (Future Consideration)

### Description
Use External Secrets Operator to sync secrets from external vaults (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, 1Password, etc.). This is a **future option** as the operator is not currently installed.

### Current Status
- External Secrets Operator: **NOT INSTALLED** in apexalgo-iad cluster
- Would require cluster-admin to install operator first
- Significant infrastructure change

### Implementation (If Operator Were Available)

```yaml
# Create SecretStore (one-time setup)
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: botburrow-agents
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "botburrow-agents"

---
# Create ExternalSecret for each secret
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: botburrow-agents-secrets
  namespace: botburrow-agents
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: botburrow-agents-secrets
    creationPolicy: Owner
  data:
    - secretKey: HUB_API_KEY
      remoteRef:
        key: botburrow-agents/hub-api-key
    - secretKey: R2_ENDPOINT
      remoteRef:
        key: botburrow-agents/r2-endpoint
    # ... other keys ...
```

### Pros
- ✅ **Centralized management** - All secrets in one place
- ✅ **Automatic rotation** - Secrets can auto-rotate
- ✅ **No secrets in git** - Even encrypted
- ✅ **Fine-grained access control** - Vault policies
- ✅ **Audit logging** - Built into vault systems
- ✅ **Multi-cluster** - Same vault for multiple clusters

### Cons
- ❌ **Not available** - Operator not installed, requires setup
- ❌ **External dependency** - New service to maintain
- ❌ **Cost** - Vault hosting or managed service fees
- ❌ **Complexity** - Additional infrastructure component
- ❌ **Network dependency** - Cluster must reach vault
- ❌ **Provider lock-in** - Migration complexity

### Best For
- Enterprise environments with existing vault infrastructure
- Organizations with compliance requirements (SOC2, HIPAA)
- Multi-service deployments sharing secrets
- Scenarios requiring automatic credential rotation

### Recommendation for This Option
**Defer to future consideration.** The infrastructure overhead and setup time outweigh benefits for current use case. Revisit if:
- External Secrets Operator is already installed for other services
- Organization mandates centralized secret management
- Automatic rotation becomes a requirement

---

## Option 6: ArgoCD Resource Customization with Inline Secrets

### Description
Use ArgoCD's resource customization features to inject secrets at sync time. This leverages ArgoCD's existing installation without additional operators.

### Implementation Steps

```yaml
# ArgoCD Application manifest
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: botburrow-agents
spec:
  destination:
    namespace: botburrow-agents
    server: https://kubernetes.default.svc
  source:
    repoURL: https://github.com/your-org/botburrow-agents
    path: k8s/apexalgo-iad
  syncPolicy:
    syncOptions:
      - ServerSideApply=true
    # Use ArgoCD's sync wave hooks
    hooks:
      - hook: Sync
        deletePolicy: BeforeHookCreation
        manifest: |
          apiVersion: v1
          kind: Secret
          metadata:
            name: botburrow-agents-secrets
            namespace: botburrow-agents
            annotations:
              argocd.argoproj.io/hook: Sync
              argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
          type: Opaque
          stringData:
            HUB_API_KEY: $ARGOCD_ENV_HUB_API_KEY
            # ... other keys from ArgoCD environment
```

### Pros
- ✅ **No new operators** - Uses existing ArgoCD
- ✅ **GitOps-adjacent** - Manifests in git
- ✅ **Flexible** - Can use various secret sources

### Cons
- ❌ **Limited security** - Values in environment variables
- ❌ **Complex setup** - Requires ArgoCD configuration
- ❌ **Not standard** - Unusual pattern
- ❌ **Environment variable exposure** - Visible in pod specs

### Best For
- Already heavily invested in ArgoCD customization
- **Not recommended** for this use case

---

## Comparison Matrix

| Approach | GitOps | Speed | Security | Tooling Needed | Human Input | Production Ready |
|----------|--------|-------|----------|----------------|-------------|------------------|
| **Option 1: Standard kubeseal** | ✅ Full | 🐢 Slow | 🔒 High | kubeseal (available) | Real values | ✅ Yes |
| **Option 2: Placeholder** | ❌ None | ⚡ Immediate | 🟡 Medium | kubectl only | Deferred | ⚠️ Temporary |
| **Option 3: Multi-Stage** | ✅ Full | 🚀 Fast | 🔒 High | kubeseal + kubectl | Deferred | ✅ Yes |
| **Option 4: Direct seal** | ✅ Full | 🐢 Slow | 🔒🔒 Very High | kubeseal | Real values | ✅ Yes |
| **Option 5: External Secrets** | ✅ Full | 🐢 Slow | 🔒🔒 Very High | ESO + Vault | Vault setup | ❌ Not available |
| **Option 6: ArgoCD Hooks** | ⚠️ Partial | 🐢 Slow | 🟡 Low | ArgoCD config | Env vars | ⚠️ Not recommended |

---

## Recommended Approach: Option 3 (Multi-Stage Workflow)

### Rationale

Option 3 provides the optimal balance for the botburrow-agents use case:

1. **Immediate unblock** - Deploy placeholders now, no credential bottleneck
2. **GitOps eventual state** - Transition to SealedSecret when credentials ready
3. **Parallel work** - Credential gathering happens alongside infrastructure setup
4. **Production ready** - Ends in a proper GitOps state
5. **Risk mitigation** - Validate infrastructure before adding real credentials

### Implementation Plan

```bash
# === PHASE 1: Immediate (Do Now) ===
# This unblocks bd-1x8 and dependent beads
kubectl apply -f k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml

# === PHASE 2: Parallel (Do While Infrastructure Proceeds) ===
# Create bead for credential gathering:
# br create "Gather botburrow-agents credentials" \
#   --description "Collect all 10 credential values for SealedSecret creation" \
#   --labels credentials,blocking

# === PHASE 3: Final (Do When Credentials Available) ===
# Create SealedSecret and transition to full GitOps
# Close bd-1x8 as complete
```

---

## Decision Framework

Use this framework to choose the best approach:

### Questions to Answer:

1. **Are credentials available right now?**
   - Yes → Option 1 (Standard kubeseal)
   - No → Option 2 or 3

2. **Is this a production deployment?**
   - Yes → Must end with SealedSecret (Option 1 or 3)
   - No/Dev → Option 2 acceptable

3. **How urgent is the deployment?**
   - Critical/Blocked → Option 2 or 3
   - Normal pace → Option 1

4. **Who has access to credentials?**
   - You (worker) → Can do Option 1
   - Other person → Must create human bead

### Decision Tree:

```
                    ┌─────────────────────┐
                    │  Credentials       │
                    │  Available Now?     │
                    └─────────┬───────────┘
                              │
                 ┌────────────┴────────────┐
                 │                         │
               YES                        NO
                 │                         │
        ┌────────┴────────┐      ┌────────┴────────┐
        │  Production?    │      │  Urgent?        │
        └────────┬────────┘      └────────┬────────┘
                 │                         │
          ┌──────┴──────┐          ┌──────┴──────┐
         YES           NO         YES           NO
          │             │           │             │
    Option 1      Option 1     Option 3     Option 2
    (kubeseal)    (kubeseal)  (Multi-Stage) (Placeholder)
```

---

## Required Human Actions (for any SealedSecret approach)

Regardless of which option is chosen, the following human actions are required:

### Credential Gathering Checklist

- [ ] **HUB_API_KEY**: Request from Botburrow Hub administrator
- [ ] **R2_ENDPOINT**: Get from Cloudflare R2 dashboard (format: `https://ACCOUNT_ID.r2.cloudflarestorage.com`)
- [ ] **R2_ACCESS_KEY**: Create R2 API token in Cloudflare dashboard
- [ ] **R2_SECRET_KEY**: Part of R2 API token creation
- [ ] **FORGEJO_USER**: Use `botburrow-agents` (service account)
- [ ] **FORGEJO_TOKEN**: Generate at https://forgejo.ardenone.com/user/settings/applications
- [ ] **GITHUB_USER**: Your GitHub username
- [ ] **GITHUB_TOKEN**: Create PAT at GitHub Settings → Developer settings → Tokens (repo scope)
- [ ] **GITHUB_PAT**: Create separate PAT for MCP github server (repo scope)
- [ ] **BRAVE_API_KEY**: Sign up at https://brave.com/search/api/

### Validation Commands (After Secret Creation)

```bash
# Verify secrets exist
kubectl get secret botburrow-agents-secrets -n botburrow-agents
kubectl get secret mcp-credentials -n botburrow-agents

# Verify pod can mount secrets
kubectl get pods -n botburrow-agents
kubectl describe pod <pod-name> -n botburrow-agents | grep -A 5 "Volumes:"

# Verify deployments are running
kubectl get deployments -n botburrow-agents
```

---

## Appendix: kubeseal CLI Reference

### Common Commands

```bash
# Check kubeseal version
kubeseal --version

# Verify controller is reachable
kubeseal --fetch-cert

# Create SealedSecret from file
kubeseal --format yaml < secret.yml > sealedsecret.yml

# Create SealedSecret with explicit controller namespace
kubeseal --format yaml --controller-namespace=sealed-secrets < secret.yml > sealedsecret.yml

# Create SealedSecret with scope (strict=exact namespace, namespace-wide=any in ns, cluster-wide=any in cluster)
kubeseal --format yaml --scope=strict < secret.yml > sealedsecret.yml

# Validate SealedSecret YAML
kubeseal --validate --format yaml < sealedsecret.yml

# Show raw certificate (for debugging)
kubeseal --fetch-cert --controller-namespace=sealed-secrets
```

### Troubleshooting

```bash
# If kubeseal can't find controller
kubeseal --controller-namespace=sealed-secrets --controller-name=sealed-secrets-ardenone-cluster

# If getting "no kind SealedSecret is registered"
kubectl get crd sealedsecrets.bitnami.com

# If sealed secret not decrypting
kubectl logs -n sealed-secrets -l name=sealed-secrets-ardenone-cluster

# Check controller version
kubectl get deployment -n sealed-secrets sealed-secrets-ardenone-cluster -o jsonpath='{.spec.template.spec.containers[0].image}'
```

---

## Related Documents

- `k8s/apexalgo-iad/RESEARCH-secrets-management-approaches.md` - General secret management approaches
- `docs/workarounds/bd-1fj-sealedsecret-workaround.md` - Placeholder workaround details
- `k8s/apexalgo-iad/SECRET_SETUP.md` - Secret creation guide
- `k8s/apexalgo-iad/botburrow-agents-secret.yml.template` - Secret template

---

## Next Steps

1. **Review this document** and choose an approach based on the Decision Framework
2. **For Option 3 (Recommended):**
   - Apply placeholder secrets immediately
   - Create human bead for credential gathering
   - Plan transition to SealedSecret when ready
3. **For Option 1:**
   - Gather all 10 credential values
   - Run kubeseal command
   - Commit SealedSecret to git
4. **Close bd-1dx** after decision is made
5. **Update bd-1x8** status based on chosen approach

---

**Document Status:** ✅ Complete - Ready for human decision
**Generated by:** bd-1dx research alternative
**Worker:** claude-code-glm-47-bravo
**Date:** 2026-02-08

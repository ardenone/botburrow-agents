# SealedSecret Setup Guide for botburrow-agents

**Purpose:** Secure credentials management for GitOps deployments
**Status:** Living guide — controller deployed via ArgoCD; key-naming contract enforced by tests; no SealedSecret sealed/committed yet
**Refreshed:** 2026-09-16 (post-`e52694d`)
**Originally written:** 2026-02-08

> **✅ REFRESHED 2026-09-16 — the 401 outage this guide originally preceded is RESOLVED.**
>
> The key-name mismatch was fixed on the manifest side in commit `e52694d`
> ("fix(k8s): align secret key names with BOTBURROW_* env contract",
> 2026-09-15); the incident record lives in
> [docs/incidents/ACTION-REQUIRED-hub-auth-fix.md](incidents/ACTION-REQUIRED-hub-auth-fix.md).
> What changed since the 2026-02-08 draft:
>
> - **Key naming is a tested contract, not a convention.** Hub and R2 keys
>   carry the `BOTBURROW_` prefix (`env_prefix="BOTBURROW_"` in
>   `src/botburrow_agents/config.py`), enforced by
>   `tests/test_secret_manifest_env_contract.py`.
> - **The controller is ArgoCD-managed.** It is *not* installed with a raw
>   `kubectl apply` of an upstream release URL — that instruction was a live
>   cluster mutation and is gone. See [Prerequisites](#prerequisites).
> - **Rotation is a manifest change.** The old `kubectl edit secret` /
>   `kubectl delete secret` / `kubectl rollout restart` recipes were both
>   forbidden by the GitOps rule and self-defeating: the controller re-syncs
>   the Secret from the SealedSecret, and `selfHeal` reverts the drift. They
>   are removed from this guide.
>
> **Current live state (verified 2026-09-16):** the controller
> (`bitnami/sealed-secrets-controller:0.36.1`) and web pods are Running in
> the `sealed-secrets` namespace of apexalgo-iad. No botburrow SealedSecret
> exists in the cluster and none is committed to this repo — nothing has
> been sealed yet, so the "Creating SealedSecrets" flow below has not been
> executed end to end.

## Overview

SealedSecrets allow you to encrypt Kubernetes secrets and commit them to Git safely. The SealedSecret controller in the cluster decrypts them automatically.

**Benefits:**
- Commit encrypted secrets to Git (no plaintext in repo)
- Automatic decryption in cluster
- No manual secret creation required
- Works with GitOps workflows

## Prerequisites

### 1. SealedSecret Controller

The controller is deployed through **declarative-config / ArgoCD**, like
every other cluster component. It is the ArgoCD Application
`sealed-secrets-apexalgo-iad`:

- **Manifests:** `k8s/apexalgo-iad/sealed-secrets/` in
  `jedarden/declarative-config` — `sealed-secrets-application.yml` installs
  the controller chart pinned to the immutable upstream tag `helm-v2.18.4`
  plus `sealed-secrets-web` chart 3.3.2, and `ingressroute.yml` publishes
  the web UI at `https://sealedsecrets-apexalgo-iad.ardenone.com`
  (forward-auth gated)
- **Namespace:** `sealed-secrets`
- **Controller Service:** `sealed-secrets-apexalgo-iad` (named for its Helm
  release — kubeseal needs this, see below)

Check it is running (read-only, credential-free from codinghome):

```bash
kubectl --server=http://traefik-apexalgo-iad:8001 get pods -n sealed-secrets
```

**If it is missing or broken, never install it by hand.** A raw
`kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/.../controller.yaml`
is a live cluster mutation that ArgoCD will fight or duplicate. Change the
manifests in `declarative-config`, push, and let ArgoCD sync.

### 2. kubeseal CLI Tool

Install `kubeseal` on the machine where you hold the plaintext values, at
the same version as the controller (0.36.1 as of 2026-09-16):

```bash
# macOS
brew install kubeseal

# Linux
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.36.1/kubeseal-0.36.1-linux-amd64.tar.gz
tar -xvzf kubeseal-0.36.1-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal

# Verify installation
kubeseal --version
```

`kubeseal` talks to the cluster through a normal kubeconfig. Codinghome has
no kubeconfig for apexalgo-iad by design — cluster access from here is the
credential-free read-only proxy, which cannot fetch the controller cert —
so from this box either seal offline with a fetched certificate
([Method 3](#method-3-sealing-without-cluster-access)) or use the web UI at
`https://sealedsecrets-apexalgo-iad.ardenone.com`.

## Key Naming Contract

> **CRITICAL — key naming:** The application loads config through pydantic-settings with
> `env_prefix="BOTBURROW_"` (`src/botburrow_agents/config.py`). Hub and R2 keys therefore
> **must** be named `BOTBURROW_HUB_API_KEY`, `BOTBURROW_R2_ENDPOINT`,
> `BOTBURROW_R2_ACCESS_KEY`, `BOTBURROW_R2_SECRET_KEY`. Sealing a secret with the
> unprefixed names (`HUB_API_KEY`, `R2_ENDPOINT`, …) produces a secret the application
> cannot see — this caused the 401 Unauthorized outage (see
> `docs/incidents/ACTION-REQUIRED-hub-auth-fix.md`). Git keys (`FORGEJO_*`, `GITHUB_*`) and MCP
> keys (`GITHUB_PAT`, `BRAVE_API_KEY`, `ANTHROPIC_API_KEY`) are read directly via
> `os.environ` and stay unprefixed.
>
> This contract is enforced by `tests/test_secret_manifest_env_contract.py` —
> run `pytest tests/test_secret_manifest_env_contract.py` after renaming any
> secret key; it fails if a manifest defines a key the application cannot read,
> if a workload references an undefined key, or if a `.data.KEY` jsonpath in
> `k8s/apexalgo-iad/` names a key no manifest defines.

## Creating SealedSecrets

After sealing, **commit the SealedSecret and let ArgoCD apply it** — never
`kubectl apply` it yourself. Also note sealing is namespace/name-scoped by
default: the SealedSecret must carry `namespace: botburrow-agents`, and it
must be sealed against *this* cluster's controller cert. A secret sealed
with another cluster's cert or for another namespace will not unseal here.

### Method 1: From Template (Recommended)

```bash
# 1. Copy the template
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml

# 2. Fill in real values
#    Edit /tmp/botburrow-agents-secret.yml with your actual credentials.
#    This file stays in /tmp and is never committed.

# 3. Seal. Both controller flags are required on this cluster: the Service
#    kubeseal talks to is named sealed-secrets-apexalgo-iad, not the
#    upstream default `sealed-secrets`.
kubeseal --format=yaml \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-apexalgo-iad \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml

# 4. Destroy the plaintext working copy
shred -u /tmp/botburrow-agents-secret.yml

# 5. Commit the SealedSecret (safe — it is ciphertext)
git add k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git commit -m "feat: add SealedSecret for botburrow-agents"
git push origin main

# 6. Include it in the GitOps build: uncomment the wave -1 entry in
#    k8s/apexalgo-iad/kustomization-gitops.yaml — it names this exact
#    file — and push that change too if it is a separate commit.
```

ArgoCD syncs the Application and the controller creates the in-cluster
Secret. If the Application is lagging, force a sync through the ArgoCD
API/UI — that *applies the repo*, it does not bypass it.

### Method 2: From Command Line

```bash
# 1. Create the secret (this will NOT be applied to cluster, just used for sealing)
kubectl create secret generic botburrow-agents-secrets \
  --namespace=botburrow-agents \
  --from-literal=BOTBURROW_HUB_API_KEY="your-hub-api-key" \
  --from-literal=BOTBURROW_R2_ENDPOINT="https://your-r2-endpoint.r2.cloudflarestorage.com" \
  --from-literal=BOTBURROW_R2_ACCESS_KEY="your-r2-access-key" \
  --from-literal=BOTBURROW_R2_SECRET_KEY="your-r2-secret-key" \
  --from-literal=FORGEJO_USER="botburrow-agents" \
  --from-literal=FORGEJO_TOKEN="your-forgejo-token" \
  --from-literal=GITHUB_USER="your-github-username" \
  --from-literal=GITHUB_TOKEN="your-github-token" \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml \
    --controller-namespace=sealed-secrets \
    --controller-name=sealed-secrets-apexalgo-iad \
    > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
```

> `--from-literal` puts each value in your shell history and in `ps`. Use
> Method 1 (file-based) for real credentials; reserve this form for throwaway
> test values.

Commit and push as in Method 1 — delivery to the cluster is ArgoCD's job.

### Method 3: Sealing Without Cluster Access

If you don't have cluster access but have the public key:

```bash
# 1. Get the controller's public key (from someone with cluster access, or
#    the web UI at https://sealedsecrets-apexalgo-iad.ardenone.com):
kubeseal --fetch-cert \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-apexalgo-iad > /tmp/sealed-secrets-cert.pem

# 2. Use the public key to seal (from anywhere)
kubectl create secret generic botburrow-agents-secrets \
  --namespace=botburrow-agents \
  --from-literal=BOTBURROW_HUB_API_KEY="your-hub-api-key" \
  --from-literal=BOTBURROW_R2_ENDPOINT="https://your-r2-endpoint.r2.cloudflarestorage.com" \
  --dry-run=client -o yaml | \
  kubeseal --format=yaml --cert=/tmp/sealed-secrets-cert.pem \
    > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
```

**Always fetch the cert from apexalgo-iad's own controller.** A cert fetched
from another cluster's SealedSecret controller (iad-ci, rs-manager, …)
seals a secret that silently fails to unseal here.

## Required Secret Values

### botburrow-agents-secrets

| Key | Description | Example | How to Get |
|-----|-------------|---------|------------|
| `BOTBURROW_HUB_API_KEY` | Botburrow Hub API key | `bh_sk_...` | Generate at hub.botburrow.com |
| `BOTBURROW_R2_ENDPOINT` | Cloudflare R2 endpoint | `https://abc123.r2.cloudflarestorage.com` | Cloudflare dashboard → R2 → Settings |
| `BOTBURROW_R2_ACCESS_KEY` | R2 access key ID | `abc123def456` | Cloudflare dashboard → R2 → API Tokens |
| `BOTBURROW_R2_SECRET_KEY` | R2 secret access key | `xyz789...` | Cloudflare dashboard → R2 → API Tokens |
| `BOTBURROW_R2_BUCKET` (optional) | R2 bucket name | `agent-artifacts` | Create in Cloudflare R2 |
| `FORGEJO_USER` | Forgejo username | `botburrow-agents` | Create in Forgejo |
| `FORGEJO_TOKEN` | Forgejo PAT | `...` | Forgejo → Settings → Applications → Generate Token |
| `GITHUB_USER` | GitHub username | `your-username` | Your GitHub account |
| `GITHUB_TOKEN` | GitHub PAT | `ghp_...` | GitHub → Settings → Developer settings → Personal access tokens |

### mcp-credentials (Optional)

| Key | Description | Example | How to Get |
|-----|-------------|---------|------------|
| `GITHUB_PAT` | GitHub PAT for MCP server | `ghp_...` | GitHub → Settings → Developer settings |
| `BRAVE_API_KEY` | Brave Search API key | `BS...` | https://brave.com/search/api/ |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` | console.anthropic.com |

## Updating SealedSecrets (Rotation)

Rotation is a **manifest change**, the same flow as any other GitOps
change: re-seal, commit, push — ArgoCD delivers it and the workloads pick
the new values up on their next rollout.

```bash
# 1. Re-seal with the new values (same as the creation flow)
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
#    edit /tmp/botburrow-agents-secret.yml, then:
kubeseal --format=yaml \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-apexalgo-iad \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
shred -u /tmp/botburrow-agents-secret.yml

# 2. Commit and push — that is the entire delivery mechanism
git add k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git commit -m "feat: rotate SealedSecret"
git push origin main

# 3. Verify (see Verification below)
```

**Do not `kubectl edit secret` or `kubectl rollout restart` to rotate.**
Editing the live Secret is (a) forbidden — a live mutation of an
ArgoCD-managed resource — and (b) futile: the controller re-syncs the Secret
from the SealedSecret, and `selfHeal` reverts whatever survives. The old
"Edit Secret Directly" recipe from the 2026-02-08 draft was removed for
exactly this reason.

## Verification

All read-only. From codinghome, use the credential-free endpoint.

### Check SealedSecret Status

```bash
# Does the SealedSecret exist and is it synced?
kubectl --server=http://traefik-apexalgo-iad:8001 get sealedsecret -n botburrow-agents

# Status conditions carry the controller's sync message on failure
kubectl --server=http://traefik-apexalgo-iad:8001 \
  get sealedsecret botburrow-agents-secrets -n botburrow-agents \
  -o jsonpath='{.status.conditions}'
```

### Check the Decrypted Secret

Verify **by property, never by printing values.** The credential-free
read-only identity on codinghome is denied `get secrets` by design, and an
identity that *can* read secrets still should not decode values into a
terminal or transcript.

```bash
# The workload sees the key NAMES (names only — no values):
kubectl --server=http://traefik-apexalgo-iad:8001 \
  exec -n botburrow-agents deploy/coordinator -- \
  sh -c 'env | grep -o "^BOTBURROW_[A-Z_]*"'
# expect: the four prefixed key names from Key Naming Contract above

# End-to-end proof: Hub polling succeeds with no 401s
kubectl --server=http://traefik-apexalgo-iad:8001 \
  logs -n botburrow-agents deploy/coordinator --tail=100 \
  | grep -Ei "poll_error|401" || echo "no auth errors"
```

If you must inspect a value (e.g. comparing a freshly rotated key), decode
it into a pipeline that consumes it — never into the terminal.

## Troubleshooting

### SealedSecret Not Creating Secret

```bash
# Check controller is running
kubectl --server=http://traefik-apexalgo-iad:8001 get pods -n sealed-secrets

# Check controller logs
kubectl --server=http://traefik-apexalgo-iad:8001 \
  logs -n sealed-secrets -l app.kubernetes.io/name=sealed-secrets

# Check the SealedSecret's own status — the message usually says why
kubectl --server=http://traefik-apexalgo-iad:8001 \
  get sealedsecret -n botburrow-agents -o yaml
```

Common causes — all fixed in the manifest, never by deleting or reapplying
the live object:

- **"no key could decrypt"** — the SealedSecret was sealed against a
  different cluster's controller cert. Re-seal against apexalgo-iad
  (`--controller-name=sealed-secrets-apexalgo-iad`).
- **wrong namespace or Secret name** — sealing is namespace/name-scoped by
  default; the SealedSecret metadata must be `botburrow-agents` /
  `botburrow-agents-secrets`.
- **manifest not reaching the cluster** — check the ArgoCD Application's
  sync status; fix the file in git, push, and force-sync the Application if
  it is lagging.

### Secret Exists But Values Are Wrong

Rotate properly: re-seal with the correct values, commit, push (see
[Updating SealedSecrets](#updating-sealedsecrets-rotation)). Do not delete
or edit the live Secret — the controller owns it, and ArgoCD reconciles it
back to the manifest.

### kubeseal Command Fails

```bash
# The controller Service here is named for its Helm release — pass both flags
kubeseal --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-apexalgo-iad ...

# Confirm the actual Service name if in doubt
kubectl --server=http://traefik-apexalgo-iad:8001 get svc -n sealed-secrets
```

The upstream default controller name (`sealed-secrets`) does **not** exist
in this cluster, so omitting `--controller-name` fails. If you have no
cluster access at all, use [Method 3](#method-3-sealing-without-cluster-access).

## Security Best Practices

1. **Never commit plaintext secrets** - Always use SealedSecrets or templates
2. **Rotate secrets by re-sealing and pushing** - never by touching the cluster
3. **Never print secret values** to a terminal, log, or transcript — verify by key names, lengths, and downstream behavior
4. **Use separate secrets per environment** - dev, staging, production
5. **Limit secret access** - Use RBAC to restrict who can view secrets
6. **Audit secret access** - Enable Kubernetes audit logging
7. **Use PATs with limited scope** - GitHub tokens with minimal permissions

## Migration from Placeholder Secrets

`k8s/apexalgo-iad/botburrow-agents-secrets-PLACEHOLDER.yml` exists only for
a first smoke deploy; it must never carry real values and must be replaced
by the sealed secret before real use:

1. Seal real values into `k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml`
   (Method 1 above)
2. In `k8s/apexalgo-iad/kustomization-gitops.yaml`, replace the placeholder
   resource with the SealedSecret file (the wave -1 entry names it)
3. Remove the placeholder manifest if nothing else references it — then
   update `SECRET_MANIFESTS` in `tests/test_secret_manifest_env_contract.py`
   accordingly and re-run the test
4. Commit, push, let ArgoCD sync — no `kubectl apply`, no
   `kubectl delete secret`, no `rollout restart`; the sync and the pods'
   own rollout deliver the change
5. Verify per the [Verification](#verification) section

## Alternative: External Secrets Operator

If you prefer to sync secrets from external providers (AWS Secrets Manager,
Azure Key Vault, etc.), the External Secrets Operator is likewise
ArgoCD-managed via `declarative-config/k8s/external-secrets/` — do **not**
`kubectl apply` the upstream bundle by hand. Create an ExternalSecret
manifest and deliver it through the same commit → push → sync flow. Verify
with `kubectl get externalsecret <name> -n botburrow-agents`: a
`SecretSynced=True` condition proves readability without printing values.

## References

- [SealedSecrets GitHub](https://github.com/bitnami-labs/sealed-secrets)
- [SealedSecrets Documentation](https://sealed-secrets.netlify.app/)
- [Kubernetes Secrets Best Practices](https://kubernetes.io/docs/concepts/configuration/secret/#best-practices)
- [GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md) — the deployment/rotation flow this guide feeds into
- [ACTION-REQUIRED-hub-auth-fix.md](incidents/ACTION-REQUIRED-hub-auth-fix.md) — the 401 outage that established the key-naming contract

## Summary

SealedSecrets provide a secure way to manage credentials in GitOps deployments:

✅ Encrypt secrets at rest (in Git)
✅ Automatic decryption in cluster
✅ No manual secret creation
✅ Works with any GitOps solution
✅ Simple CLI tool (kubeseal)
✅ No external dependencies (controller runs in-cluster)

…with three workspace-specific rules that override generic SealedSecrets
advice: the controller comes from declarative-config via ArgoCD (never a
raw `kubectl apply`), hub/R2 keys are `BOTBURROW_`-prefixed and
test-enforced, and rotation always means re-seal → commit → push.

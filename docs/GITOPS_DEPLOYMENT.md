# GitOps Build & Deployment Guide for botburrow-agents

**Status:** Build pipeline live; GitOps deployment bootstrapped in manifests, pending one-time cluster-admin step (see "Current rollout status")
**Date:** 2026-09-15
**Approach:** Argo Workflows (`iad-ci`) for builds + ArgoCD (`apexalgo-iad`) for deployment

## Overview

CI/CD for this repo is split the same way as every other repo in the org:

- **Build (CI):** the `botburrow-agents-build` WorkflowTemplate on Argo
  Workflows in the `iad-ci` cluster builds the image with kaniko and pushes it
  to GHCR. GitHub Actions are disabled org-wide and must never be re-enabled;
  the old `.github/workflows/ci-cd.yml` flow they documented has been deleted.
- **Deploy (CD):** an ArgoCD Application syncs the Kubernetes manifests from
  this repo into the `apexalgo-iad` cluster with automated sync, prune and
  self-heal. There is no push-to-deploy step and no manual approval gate.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Build & Deploy Flow                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Code lands on main (git.ardenone.com, mirrored to GitHub)           │
│                                                                         │
│  2. Build — Argo Workflow from botburrow-agents-build template (iad-ci) │
│     ├─→ resolve-version: use VERSION if the commit bumped it,           │
│     │   otherwise auto-bump patch and push the bump back to Forgejo     │
│     └─→ docker-build: kaniko → ghcr.io/ardenone/botburrow-agents:<ver>  │
│                                                                         │
│  3. Promote — pin the new tag in k8s/apexalgo-iad/ manifests (commit)   │
│                                                                         │
│  4. Deploy — ArgoCD Application (apexalgo-iad)                          │
│     ├─→ Detects the new commit on main (GitHub mirror is the source)    │
│     ├─→ Auto-syncs manifests into namespace botburrow-agents            │
│     └─→ Self-heals drift; prunes resources removed from Git             │
│                                                                         │
│  5. Verify — ArgoCD health + kubectl (read-only) + verify script        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

Nothing to configure on GitHub — there are no GitHub secrets in this
pipeline. All CI credentials are cluster-side in `iad-ci` (see
[docs/DOCKERHUB_SETUP.md](DOCKERHUB_SETUP.md)); all workload secrets are
SealedSecrets in this repo (see "Secrets Management" below).

The two things that had to exist before the first build/deploy, and where
they live:

| Piece | Where |
|---|---|
| `botburrow-agents-build` WorkflowTemplate | `jedarden/declarative-config` → `k8s/iad-ci/argo-workflows/botburrow-agents-workflowtemplate.yml` (ArgoCD-synced; verified live in `argo-workflows` ns on iad-ci) |
| ArgoCD Application `botburrow-agents` | `jedarden/declarative-config` → `k8s/apexalgo-iad/botburrow-agents/application.yml`, delivered by the apexalgo-iad ApplicationSet |

### ⚠️ Known gaps before the pipeline runs end-to-end

1. **`ghcr-registry` secret missing on iad-ci.** The template's kaniko step
   mounts `secretName: ghcr-registry`, but its ExternalSecret is disabled in
   `declarative-config` — the first build will fail on the missing secret.
   Fix in `declarative-config` (re-enable it or re-point the template at a
   live secret such as `ghcr-jedarden-registry`).
2. **No auto-trigger.** No argo-events sensor exists for this repo, so builds
   run when submitted (next section), not on push. Adding a sensor is a
   `declarative-config` change.
3. **ArgoCD Application not yet created on the cluster** — the parent
   `applications-apexalgo-iad` Application needs a one-time cluster-admin
   bootstrap (see "Current rollout status" at the bottom).

(The former gap "manifests reference `:latest`" is closed: all
`k8s/apexalgo-iad/` manifests are pinned to semver tags, enforced by
`tests/test_image_pins.py` / `scripts/check_image_pins.py`. Re-pin after
each build — step 3 of the flow below.)

## Build (CI) — Argo Workflows on iad-ci

### Triggering a build

There is no push trigger yet, so submit a run manually. Two ways:

**From the Argo UI** (`https://argo-ci.ardenone.com`, Google SSO, VPN-only):
open *Workflow Templates* → `botburrow-agents-build` → *Submit*, leaving the
defaults (`git-repo: jedarden/botburrow-agents`, `branch: main`).

**With kubectl** (needs the write kubeconfig — the credential-free read-only
endpoint cannot create):

```bash
kubectl --kubeconfig=/home/coding/.kube/iad-ci.kubeconfig create -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: botburrow-agents-build-
  namespace: argo-workflows
spec:
  workflowTemplateRef:
    name: botburrow-agents-build
EOF
```

Before submitting, confirm the template is actually applied in the cluster
(exists in git but not yet synced yields an immediate `Error` run):

```bash
kubectl --server=http://traefik-iad-ci:8001 \
  get workflowtemplate botburrow-agents-build -n argo-workflows
```

### What a build does

Defined in `k8s/iad-ci/argo-workflows/botburrow-agents-workflowtemplate.yml`
(in `declarative-config`):

1. **resolve-version** — clones `main` from `git.ardenone.com` using the
   `forgejo-webhook-token` secret. If the tip commit changed `VERSION`, that
   value is used as-is; otherwise the patch version is bumped and a
   `ci: auto-bump version to X.Y.Z` commit is pushed back to Forgejo (which
   mirrors to GitHub automatically). To release a specific version, change
   `VERSION` in your own commit; otherwise every build bumps the patch.
2. **docker-build** — kaniko (`v1.23.2`, pinned) builds `docker/Dockerfile`
   straight from the git context with `--build-arg VERSION=<version>` and
   pushes `ghcr.io/ardenone/botburrow-agents:<version>`. Layer cache lives in
   `ghcr.io/ardenone/cache`. The step retries twice on error; the workflow
   has an 8400s backstop deadline.

### Watching a build

```bash
# Recent runs
kubectl --server=http://traefik-iad-ci:8001 \
  get workflows -n argo-workflows --sort-by=.metadata.creationTimestamp | tail

# Phase and message of one run
kubectl --server=http://traefik-iad-ci:8001 \
  get workflow <name> -n argo-workflows -o jsonpath='{.status.phase} - {.status.message}'

# Per-step failure details
kubectl --server=http://traefik-iad-ci:8001 \
  get workflow <name> -n argo-workflows -o json | python3 -c "
import json,sys
w = json.load(sys.stdin)
for node in w['status'].get('nodes',{}).values():
    if node.get('phase') in ('Failed','Error'):
        print(node['displayName'], '-', node['phase'])
        print('  msg:', node.get('message',''))
"
```

Pods are garbage-collected on completion (`podGC: OnPodCompletion`), so
stream logs while a run is live, or read them from the Argo UI — logs for
completed workflows stay there 30 minutes on success, 2 hours on failure.

## Promoting an image (GitOps-style)

Builds do **not** deploy anything. To roll a new image out:

```bash
# 1. Note the version the build produced (VERSION file on main after the bump)
git pull origin main && cat VERSION

# 2. Pin that tag in the manifests that reference the image
grep -rl "ghcr.io/ardenone/botburrow-agents" k8s/apexalgo-iad/
#   edit each image: to ghcr.io/ardenone/botburrow-agents:<version>
#   then verify every pin (exits non-zero on any unpinned ref):
python3 scripts/check_image_pins.py

# 3. Commit and push; ArgoCD takes it from there
git add k8s/apexalgo-iad/
git commit -m "deploy: botburrow-agents <version>"
git push origin main
```

## Deploy (CD) — ArgoCD on apexalgo-iad

The ArgoCD Application (`declarative-config/k8s/apexalgo-iad/botburrow-agents/application.yml`):

- **Source:** `https://github.com/ardenone/botburrow-agents.git` (the Forgejo
  mirror), revision `main`, path `k8s/apexalgo-iad`
- **Destination:** in-cluster, namespace `botburrow-agents` (created on sync)
- **Sync policy:** fully automated — `prune: true`, `selfHeal: true`, with
  retry/backoff; server-side apply, prune-last

Consequences worth internalising:

- **Never mutate a managed resource with `kubectl`** — `apply`, `delete`,
  `patch`, `edit`, `annotate`, `scale`, `rollout restart`, not even for
  triage. `selfHeal` reverts it anyway. Change the manifest, push, let ArgoCD
  sync. Read-only `get`/`describe`/`logs` is fine.
- **There is no manual approval gate.** Merges to `main` deploy on the next
  sync. If a change genuinely needs a gate, that is a deliberate
  `declarative-config` edit (drop `automated` from `syncPolicy` and sync by
  hand until re-enabled) — not a kubectl workaround.
- Manifests are **pinned semver or nothing**: never retag the image to
  `:latest`, nothing publishes it.

### Checking sync status

```bash
# Application state
kubectl --server=http://traefik-apexalgo-iad:8001 \
  get application botburrow-agents -n argocd \
  -o jsonpath='{.status.sync.status} {.status.health.status}'

# Workloads (read-only credential-free endpoint)
kubectl --server=http://traefik-apexalgo-iad:8001 \
  get all -n botburrow-agents
```

If the Application is lagging, force a sync through the ArgoCD API/UI — that
*applies the repo*, it does not bypass it.

## Secrets Management

The workload's runtime secrets are unchanged by the CI/CD migration — they
are SealedSecrets committed to this repo, decrypted in-cluster by the
SealedSecrets controller.

**Required secret keys:**

| Key | Description | Source |
|-----|-------------|--------|
| `BOTBURROW_HUB_API_KEY` | Botburrow Hub authentication (BOTBURROW_ prefix required by config.py) | Generate at hub.botburrow.com |
| `BOTBURROW_R2_ENDPOINT` | Cloudflare R2 storage | Cloudflare dashboard |
| `BOTBURROW_R2_ACCESS_KEY` | R2 access credentials | Cloudflare dashboard |
| `BOTBURROW_R2_SECRET_KEY` | R2 secret credentials | Cloudflare dashboard |
| `FORGEJO_USER` | Forgejo username | Your Forgejo account |
| `FORGEJO_TOKEN` | Forgejo PAT | Generate in Forgejo settings |
| `GITHUB_USER` | GitHub username | Your GitHub account |
| `GITHUB_TOKEN` | GitHub PAT | Generate in GitHub settings |

Key naming is enforced by `tests/test_secret_manifest_env_contract.py`; run it
after renaming any secret key.

**Create or rotate** by regenerating the SealedSecret and pushing it — same
flow as any other manifest change:

```bash
cp k8s/apexalgo-iad/botburrow-agents-secret.yml.template /tmp/botburrow-agents-secret.yml
# edit /tmp/botburrow-agents-secret.yml with real values, then:
# (--controller-name is required: the Service here is named for its Helm
#  release, not the upstream default `sealed-secrets`)
kubeseal --format=yaml \
  --controller-namespace=sealed-secrets \
  --controller-name=sealed-secrets-apexalgo-iad \
  < /tmp/botburrow-agents-secret.yml > k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git add k8s/apexalgo-iad/botburrow-agents-sealedsecrets.yml
git commit -m "feat: update SealedSecret" && git push origin main
```

Do not `kubectl edit secret ...` or restart pods to pick secrets up — edit
the source of truth and let sync + rollout happen; a live edit is drift that
`selfHeal` will revert. Placeholder secrets
(`botburrow-agents-secrets-PLACEHOLDER.yml`) exist for a first smoke deploy
only and must be replaced before real use.

## Health Checks

Run these after every deploy (all read-only):

```bash
# 1. ArgoCD reports the app healthy/synced
kubectl --server=http://traefik-apexalgo-iad:8001 \
  get application botburrow-agents -n argocd \
  -o jsonpath='{.status.health.status} {.status.sync.status}'

# 2. All pods ready
kubectl --server=http://traefik-apexalgo-iad:8001 \
  get pods -n botburrow-agents

# 3. Health endpoints
kubectl --server=http://traefik-apexalgo-iad:8001 \
  exec -n botburrow-agents <coordinator-pod> -- curl -s http://localhost:9090/health

# 4. Valkey
kubectl --server=http://traefik-apexalgo-iad:8001 \
  exec -n botburrow-agents valkey-0 -- redis-cli ping   # expect PONG
```

`scripts/verify-gitops-deployment.sh` wraps a fuller check:

```bash
./scripts/verify-gitops-deployment.sh --namespace botburrow-agents
```

## Rollback

**Revert the commit — that is the rollback.** ArgoCD syncs the previous
desired state (including the previous image tag) automatically:

```bash
git revert <deploy-commit>
git push origin main
# ArgoCD converges the cluster back to the previous manifests
```

Manual `kubectl rollout undo` and `argocd app rollback` are not the tools
here: the former is drift that `selfHeal` reverts, the latter fights the
automated sync policy. For a bad image with no bad commit, pin the previous
tag the same way you promoted the new one.

## Monitoring and Troubleshooting

```bash
# Everything in the namespace (read-only endpoints throughout)
kubectl --server=http://traefik-apexalgo-iad:8001 get all -n botburrow-agents
kubectl --server=http://traefik-apexalgo-iad:8001 get hpa -n botburrow-agents

# Logs
kubectl --server=http://traefik-apexalgo-iad:8001 \
  logs -n botburrow-agents -l app.kubernetes.io/name=coordinator -f
kubectl --server=http://traefik-apexalgo-iad:8001 \
  logs -n botburrow-agents <pod-name> --tail=100

# Events on a stuck pod
kubectl --server=http://traefik-apexalgo-iad:8001 \
  describe pod -n botburrow-agents <pod-name>
```

**ImagePullBackOff** — almost always a tag that was never pushed. Check what
the deployment asks for and what actually exists:

```bash
kubectl --server=http://traefik-apexalgo-iad:8001 \
  get deploy coordinator -n botburrow-agents \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

Fix by pinning a tag that exists (see "Promoting an image") — not by
`kubectl set image`, which is drift.

**CrashLoopBackOff** — `logs --previous` and `describe pod` for missing
secrets; compare against the SealedSecret key table above.

**Scaling** is owned by the HPA (`hpa.yaml`, CPU target 70%, runner replicas
2–10). Manual `kubectl scale` is drift; change `hpa.yaml`/replica counts in
the manifests instead.

## Current rollout status (2026-09-15)

- ✅ `botburrow-agents-build` WorkflowTemplate live in `argo-workflows` on iad-ci
- ⚠️ First build blocked on the missing `ghcr-registry` secret (gap 1 above)
- ✅ Deployment manifests and ArgoCD Application manifest committed
  (repo `k8s/apexalgo-iad/` + `declarative-config`)
- ⏳ ArgoCD Application not yet instantiated: the parent
  `applications-apexalgo-iad` Application (which deploys the ApplicationSet
  that discovers `k8s/apexalgo-iad/*/application.yml`) needs a one-time
  cluster-admin bootstrap:
  `kubectl apply -f declarative-config/k8s/apexalgo-iad/apexalgo-iad-application.yml`
  (details in the repo's `bd-b17315d5-completion-summary.md`)
- ⏝ After bootstrap: pin a real image tag, sync, verify with the health checks

## References

- [Container registry & CI credentials](DOCKERHUB_SETUP.md)
- [WorkflowTemplate manifest](https://git.ardenone.com/jedarden/declarative-config/src/branch/main/k8s/iad-ci/argo-workflows/botburrow-agents-workflowtemplate.yml)
- [ArgoCD Application manifest](https://git.ardenone.com/jedarden/declarative-config/src/branch/main/k8s/apexalgo-iad/botburrow-agents/application.yml)
- [Kubernetes manifests in this repo](../k8s/apexalgo-iad/)
- [SealedSecret Documentation](https://github.com/bitnami-labs/sealed-secrets)

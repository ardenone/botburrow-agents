# Container Registry & CI Credentials

> **This file was named for the old Docker Hub setup.** That flow is gone: CI
> runs on Argo Workflows in `iad-ci` (GitHub Actions are disabled org-wide and
> must never be re-enabled), and the pipeline pushes to **GHCR only**. No
> Docker Hub push exists, and no GitHub secret is required. The filename is
> kept so existing links keep working.

## Overview

Images are built by the `botburrow-agents-build` WorkflowTemplate (Argo
Workflows, `iad-ci` cluster, `argo-workflows` namespace) and pushed to:

- `ghcr.io/ardenone/botburrow-agents:<version>` — pinned semver, e.g. `0.1.2`

There is no `:latest` tag and no short-SHA tag. The version comes from the
repo's `VERSION` file (see "Versioning" in
[docs/GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md)).

## Where credentials live (nowhere on GitHub)

The old flow needed a `DOCKERHUB_PASSWORD` GitHub secret. That prerequisite is
gone — CI credentials are cluster-side in `iad-ci`, provisioned through
ExternalSecrets from OpenBao and referenced by the WorkflowTemplate in
`declarative-config`:

| Secret (ns `argo-workflows`) | Feeds | Purpose |
|---|---|---|
| `forgejo-webhook-token` | version-bump + clone steps | Read/push the repo on `git.ardenone.com` |
| `ghcr-registry` | kaniko `dockerconfigjson` mount | Authenticate the push to `ghcr.io` |

Nothing to configure per-run and nothing to store in GitHub: a build only
needs a submission (see [docs/GITOPS_DEPLOYMENT.md](GITOPS_DEPLOYMENT.md) for
how to trigger one).

## ⚠️ Known gap: `ghcr-registry` is not currently provisioned

The template mounts `secretName: ghcr-registry`, but the ExternalSecret that
provisioned it
(`declarative-config/k8s/iad-ci/argo-workflows/ghcr-registry-externalsecret.yml.disabled`)
is disabled, so a build will fail until the template is re-pointed at a live
secret (e.g. `ghcr-jedarden-registry`) or the ExternalSecret is re-enabled.
This is a `declarative-config` change — fix it there, not here. Tracked on
bead `botburro-6d349f13`.

## Checking what was pushed

```bash
# Tags published to GHCR (needs a token with read:packages for private images)
curl -s https://ghcr.io/v2/ardenone/botburrow-agents/tags/list | jq -r '.tags[]'

# Pull and smoke-test
docker pull ghcr.io/ardenone/botburrow-agents:<version>
docker run --rm ghcr.io/ardenone/botburrow-agents:<version> --help
```

## If Docker Hub is ever needed again

Other CI templates in this org publish to Docker Hub under `ronaldraygun/*`
by mounting a `docker-hub-registry` dockerconfigjson secret sourced from
OpenBao (`rs-manager/iad-ci/docker/build`) — see
`declarative-config/k8s/iad-ci/argo-workflows/docker-hub-registry-externalsecret.yml`.
Adding a second kaniko `--destination` plus that secret to the botburrow
template would restore Docker Hub publishing. Until someone does that
deliberately, treat Docker Hub as out of the pipeline. Note the org rule:
pinned semver tags only — never `:latest`.

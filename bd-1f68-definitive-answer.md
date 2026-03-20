# Bead bd-1f68: Definitive Answer - Is ronaldraygun/botburrow-agents the Correct Image?

**Date:** 2026-03-20
**Status:** Answered

---

## Question
Is `ronaldraygun/botburrow-agents` the correct/official image?

## Answer
**No.** `ronaldraygun/botburrow-agents` is **NOT** the correct/official image.

---

## Correct Image

| Registry | Image Name | Full Reference |
|----------|------------|----------------|
| GitHub Container Registry | ardenone/botburrow-agents | `ghcr.io/ardenone/botburrow-agents` |

---

## Evidence

### 1. CI/CD Workflows
Both `.github/workflows/release.yml` and `ci-cd.yml` define:

```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ardenone/botburrow-agents
```

This means all official builds push to `ghcr.io/ardenone/botburrow-agents`.

### 2. Kubernetes Manifests
All deployment manifests in `k8s/apexalgo-iad/` use:
```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

Files confirmed:
- `coordinator.yaml` (line 87)
- `coordinator-git-sync.yaml` (line 105)
- `runner-hybrid.yaml` (line 80)
- `runner-notification.yaml` (line 75)
- `runner-exploration.yaml` (line 75)
- `runner-git-sync.yaml` (line 105)
- `skill-sync.yaml` (line 51)

### 3. Historical Documentation
The `ronaldraygun/botburrow-agents` image was documented as **incorrect** in `bd-32g-verification-findings.md`:

> **Error:**
> ```
> Failed to pull image "docker.io/ronaldraygun/botburrow-agents:latest":
> pull access denied, repository does not exist or may require authorization
> ```
>
> **Cause:**
> The deployed manifest references the OLD image registry:
> - Deployed: `docker.io/ronaldraygun/botburrow-agents:latest` ❌
> - Expected: `ghcr.io/botburrow/botburrow-agents:latest` ✅

Note: The documentation mentioned `ghcr.io/botburrow/botburrow-agents` but the actual configured image is `ghcr.io/ardenone/botburrow-agents` (under the `ardenone` org, not `botburrow`).

---

## Why ronaldraygun/botburrow-agents Exists

This appears to be a **legacy/incorrect reference** that was mistakenly deployed at some point. It caused ImagePullBackOff errors because:
1. The Docker Hub repository doesn't exist or requires authorization
2. No CI/CD pipeline pushes to Docker Hub
3. All official builds go to GHCR (GitHub Container Registry)

---

## TL;DR

| Image | Status |
|-------|--------|
| `ghcr.io/ardenone/botburrow-agents` | ✅ Correct/Official |
| `docker.io/ronaldraygun/botburrow-agents` | ❌ Legacy/Incorrect |

---

## Related Beads
- bd-212 - Parent bead: Investigate ronaldraygun/botburrow-agents image version
- bd-32g - Verification findings documenting the ImagePullBackOff issue

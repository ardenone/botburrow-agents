# Definitive Answer: bd-y8in

## Question
Should we be using ardenone/botburrow-agents instead?

## Answer
**Yes.** `ghcr.io/ardenone/botburrow-agents:latest` is the correct and only actively maintained image.

## Evidence

1. **CI/CD Configuration** (`.github/workflows/ci-cd.yml` line 16):
   ```yaml
   IMAGE_NAME: ardenone/botburrow-agents
   REGISTRY: ghcr.io
   ```

2. **Zero references to `ronaldraygun`** in any source code, manifests, or Dockerfiles — only in historical documentation.

3. **Migration completed** in commit `2a2a589` (2026-03-17): CI/CD migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`).

4. **Docker Hub repo deleted**: The `ronaldraygun/botburrow-agents` repo is deleted or private — API returns "object not found".

## Correct Image Reference

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Prior Confirmation

This question was previously answered in bead `bd-ur5o` with the same conclusion. All K8s manifests in this repo already reference `ghcr.io/ardenone/botburrow-agents:latest`.

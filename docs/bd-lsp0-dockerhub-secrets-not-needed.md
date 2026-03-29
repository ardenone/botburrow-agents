---
bead: bd-lsp0
task: GitHub secrets DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD not configured
status: closed
---

# GitHub Secrets DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD — bd-lsp0

## Finding

The GitHub secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_PASSWORD` are not configured in
`ardenone/botburrow-agents`. This is **not a problem**.

## Why These Secrets Are Not Needed

The project migrated from Docker Hub to GitHub Container Registry (GHCR) on 2026-03-17
(commit `2a2a589`). The CI/CD pipeline pushes to GHCR using `GITHUB_TOKEN` (no additional
secrets required). Docker Hub push is optional and skipped when `DOCKERHUB_PASSWORD` is
absent.

From `.github/workflows/ci-cd.yml`:

```yaml
- name: Check Docker Hub credentials
  id: dockerhub
  env:
    DOCKERHUB_PASSWORD: ${{ secrets.DOCKERHUB_PASSWORD }}
  run: |
    if [[ -z "${DOCKERHUB_PASSWORD}" ]]; then
      echo "available=false" >> $GITHUB_OUTPUT
      echo "::notice::DOCKERHUB_PASSWORD not configured - skipping Docker Hub push"
      exit 0
    fi
```

```yaml
- name: Push to Docker Hub
  if: steps.dockerhub.outputs.available == 'true'
```

The Docker Hub push is explicitly gated — missing credentials produce a notice, not an
error, and GHCR push proceeds normally.

## Additional Notes

- `DOCKERHUB_USERNAME` is not referenced anywhere in the workflow; `ardenone` is hardcoded
  and would only need to change if the Docker Hub account changed.
- The Docker Hub repository `ardenone/botburrow-agents` does not exist and is not required
  (see `docs/bd-7y9w-dockerhub-ardenone-missing.md`).
- The official image is `ghcr.io/ardenone/botburrow-agents:latest`.
- All Kubernetes manifests in `k8s/apexalgo-iad/` reference the GHCR image.

## Conclusion

No action required. The CI/CD pipeline functions correctly without these secrets.

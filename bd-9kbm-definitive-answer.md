# bd-9kbm: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: NO

`ronaldraygun/botburrow-agents` is **NOT** the correct/official image.

## The Correct Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Why ronaldraygun is Wrong

| Issue | Details |
|-------|---------|
| **Deprecated** | `ronaldraygun/botburrow-agents` was deprecated on 2026-03-17 |
| **Docker Hub deleted/private** | The Docker Hub repo no longer exists |
| **No new builds** | CI/CD migrated to GHCR, so ronaldraygun hasn't received updates since commit `8f01f19` |
| **Last build date** | 2026-03-17T06:42:40Z |

## Evidence

- **CI/CD workflows** (`.github/workflows/ci-cd.yml`, `release.yml`): Configure `REGISTRY: ghcr.io` and `IMAGE_NAME: ardenone/botburrow-agents`
- **All K8s manifests** (`k8s/apexalgo-iad/*.yaml`): Reference `ghcr.io/ardenone/botburrow-agents:latest`
- **Migration commit**: `2a2a589` on 2026-03-17 switched from Docker Hub to GHCR

## See Also

- `bd-m60o-definitive-answer.md` - Should we be using ardenone/botburrow-agents instead? (YES)
- `bd-xwf3-definitive-answer.md` - Is ronaldraygun/botburrow-agents the correct/official image? (NO)

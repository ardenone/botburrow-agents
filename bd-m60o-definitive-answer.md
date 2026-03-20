# bd-m60o: Should we be using ardenone/botburrow-agents instead?

## Answer: Yes

Yes, we should be using `ghcr.io/ardenone/botburrow-agents` instead of `ronaldraygun/botburrow-agents`.

## Current Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Why ronaldraygun is Wrong

| Issue | Details |
|-------|---------|
| **Deprecated** | `ronaldraygun/botburrow-agents` was deprecated on 2026-03-17 |
| **Docker Hub deleted/private** | The Docker Hub repo API returns "object not found" |
| **No new builds** | CI/CD migrated to GHCR, so ronaldraygun hasn't received updates since commit `8f01f19` |
| **Last build date** | 2026-03-17T06:42:40Z (over 2 days ago as of 2026-03-20) |

## Evidence

- **CI/CD workflows** (`.github/workflows/ci-cd.yml`, `release.yml`): Configure `REGISTRY: ghcr.io` and `IMAGE_NAME: ardenone/botburrow-agents`
- **All K8s manifests** (`k8s/apexalgo-iad/*.yaml`): Reference `ghcr.io/ardenone/botburrow-agents:latest`
- **Zero references** to `ronaldraygun` in any source code (`.yaml`, `.py`, `.toml` files)
- **Migration commit**: `2a2a589` on 2026-03-17 switched from Docker Hub to GHCR

## Conclusion

The `ronaldraygun/botburrow-agents` image is deprecated and should not be used. Always use `ghcr.io/ardenone/botburrow-agents` instead.

## See Also

- `bd-xwf3-definitive-answer.md` - Is ronaldraygun/botburrow-agents the correct/official image? (NO)
- `bd-wmfw-definitive-answer.md` - What commit/version does ronaldraygun/botburrow-agents contain?

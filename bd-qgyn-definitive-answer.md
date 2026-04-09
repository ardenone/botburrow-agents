# bd-qgyn: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: NO

`ronaldraygun/botburrow-agents` is **NOT** the correct/official image. It has been deprecated.

## Correct Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Evidence

| Image | Status |
|-------|--------|
| `ghcr.io/ardenone/botburrow-agents` | ✅ **Correct/Official** |
| `docker.io/ronaldraygun/botburrow-agents` | ❌ Deprecated - Docker Hub repo deleted/private |

### 1. CI/CD Configuration
Both `.github/workflows/release.yml` and `ci-cd.yml` define:
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ardenone/botburrow-agents
```

### 2. Kubernetes Manifests
All deployment manifests in `k8s/apexalgo-iad/` use:
```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

### 3. Migration History
- **2026-03-17**: Migrated from `ronaldraygun/botburrow-agents` to `ghcr.io/ardenone/botburrow-agents` (commit `2a2a589`)
- The Docker Hub repo (`ronaldraygun/botburrow-agents`) is now deleted or private
- Attempts to pull from Docker Hub fail with "repository does not exist or may require authorization"

## Related Documentation
- bd-1f68-definitive-answer.md - Comprehensive answer with full evidence
- bd-xwf3-definitive-answer.md - Confirmed deprecation
- bd-1w62-definitive-answer.md - Migration status

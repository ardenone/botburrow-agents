# bd-l3xs: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: NO

**`ronaldraygun/botburrow-agents` is NOT the correct/official image.**

## Correct Image

The official image is:

```
ghcr.io/ardenone/botburrow-agents
```

## Summary

| Registry | Image | Status |
|----------|-------|--------|
| Docker Hub | `ronaldraygun/botburrow-agents` | **Deprecated** — last build 2026-03-17 |
| GHCR | `ghcr.io/ardenone/botburrow-agents` | **Active** — built on every push to main |

## Evidence

1. **CI/CD configuration** (`.github/workflows/ci-cd.yml`):
   ```yaml
   REGISTRY: ghcr.io
   IMAGE_NAME: ardenone/botburrow-agents
   ```

2. **Release workflow** (`.github/workflows/release.yml`):
   - Same GHCR configuration
   - All tags pushed to `ghcr.io/ardenone/botburrow-agents`

3. **Migration completed** in commit `2a2a589` (2026-03-17)

4. **Previous investigations** (see git history):
   - `bd-txuz-definitive-answer.md` — Docker Hub deprecated, use GHCR
   - `bd-jj01-definitive-answer.md` — ronaldraygun image is NOT official
   - `bd-lrkr-definitive-answer.md` — ronaldraygun is deprecated

## Usage

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

Or use versioned tags for stability:

```yaml
image: ghcr.io/ardenone/botburrow-agents:v1.2.3
```

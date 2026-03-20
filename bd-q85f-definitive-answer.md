# bd-q85f: What commit/version does ronaldraygun/botburrow-agents contain?

## Answer

The `ronaldraygun/botburrow-agents` image contains **commit `a0021f9`** (version **v0.1.1**).

| Property | Value |
|----------|-------|
| **Full SHA** | `a0021f9d3900fff53c9fb32e5b952d15c5068bb1` |
| **Short SHA** | `a0021f9` |
| **Commit Date** | 2026-02-14 21:10:56 UTC |
| **Commit Message** | "fix(bd-xou): Fix Docker Hub secret name reference" |
| **Version Tag** | `v0.1.1` |
| **Image Tags** | `ronaldraygun/botburrow-agents:v0.1.1`, `ronaldraygun/botburrow-agents:latest` |
| **Build Date** | 2026-02-14T21:12:58Z |
| **Status** | DEPRECATED — Docker Hub repo deleted/private |

## Evidence

1. **Tag verification**: The `v0.1.1` tag points to commit `a0021f9d3900fff53c9fb32e5b952d15c5068bb1`
2. **Timeline**: Commit was made on 2026-02-14 21:10:56 UTC, and the image was built on 2026-02-14T21:12:58Z (2 minutes later)
3. **GitHub Actions Run ID**: 22024326118 (release workflow triggered by v0.1.1 tag push)

## Important Note

Some earlier definitive answers (bd-dfnj, bd-cqak, bd-sg24) incorrectly stated the image contains commit `8f01f19`. This is impossible because:
- Commit `8f01f19` was made on **2026-03-17**
- The last Docker Hub build was on **2026-02-14**
- An image built in February cannot contain a commit from March

## Current Recommendation

The `ronaldraygun/botburrow-agents` image is **deprecated**. Use the current GHCR image instead:

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## See Also

- `bd-ljao-definitive-answer.md` — When was the image last built? (2026-02-14)
- `bd-l3xs-definitive-answer.md` — Is ronaldraygun the correct image? (NO)
- `bd-y8in-definitive-answer.md` — What is the correct image? (ghcr.io/ardenone/botburrow-agents)

# bd-0hd7: Is ronaldraygun/botburrow-agents the correct/official image?

## Answer: NO

`ronaldraygun/botburrow-agents` is **not** the correct/official image. It is deprecated.

## Correct/Official Image

```
ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

| Question | Answer |
|----------|--------|
| Is `ronaldraygun/botburrow-agents` correct? | **NO** — deprecated |
| Correct/official image | `ghcr.io/ardenone/botburrow-agents:latest` |
| Migration date | 2026-03-17 (commit `2a2a589`) |

## Details

The project migrated from Docker Hub (`ronaldraygun/botburrow-agents`) to GitHub Container
Registry (`ghcr.io/ardenone/botburrow-agents`) in commit `2a2a589` on 2026-03-17.

- All K8s manifests in `k8s/apexalgo-iad/` reference `ghcr.io/ardenone/botburrow-agents:latest`
- CI/CD workflows build and push to `ghcr.io/ardenone/botburrow-agents`
- Zero references to `ronaldraygun` in active source code

See also: `docs/bd-lhk7-ronaldraygun-image-status.md`

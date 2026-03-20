# bd-ur5o: Should we be using ardenone/botburrow-agents instead?

## Answer: YES — migration already completed

`ghcr.io/ardenone/botburrow-agents:latest` is the **correct and only actively maintained image**.

## Summary

| | ronaldraygun/botburrow-agents | ardenone/botburrow-agents |
|---|---|---|
| **Registry** | Docker Hub | GitHub Container Registry (GHCR) |
| **Status** | Deprecated / deleted | Active, continuously built |
| **Last build** | 2026-03-17 (commit `8f01f19`) | Current HEAD |
| **CI/CD** | No longer updated | Built on every push to `main` |
| **Accessible** | No — repo deleted/private | Yes |

## Evidence

1. **Migration commit `2a2a589`** (2026-03-17): CI/CD pipeline migrated from Docker Hub (`ronaldraygun`) to GHCR (`ardenone`).
2. **Docker Hub repo** `ronaldraygun/botburrow-agents` is deleted or private — API returns "object not found".
3. **All K8s manifests** in this repo already reference `ghcr.io/ardenone/botburrow-agents:latest`.
4. **CI/CD** (`.github/workflows/ci-cd.yml`) builds and pushes to GHCR with both `:latest` and `:<short-sha>` tags.
5. **Zero references to `ronaldraygun`** in any source code, manifests, or Dockerfiles.

## Correct Image Reference

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## No Action Required

The migration was already completed. This question has been answered independently by multiple prior beads:
- bd-v27h, bd-y47f, bd-7jh5, bd-93p4, bd-xwf3, bd-dq2b, bd-4n4j

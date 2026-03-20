# bd-fi7h: Should we be using ardenone/botburrow-agents instead?

**Answer: YES**

## Correct Image

```yaml
image: ghcr.io/ardenone/botburrow-agents:latest
```

## Summary

`ghcr.io/ardenone/botburrow-agents` is the **correct and only actively maintained image**. The old `ronaldraygun/botburrow-agents` image on Docker Hub is deprecated.

## Evidence

1. **Migration completed** in commit `2a2a589` (2026-03-17): CI/CD pipeline migrated from Docker Hub to GHCR
2. **Docker Hub repo** `ronaldraygun/botburrow-agents` is deleted/private — returns "object not found"
3. **All K8s manifests** in this repo reference `ghcr.io/ardenone/botburrow-agents:latest`
4. **CI/CD** builds and pushes to GHCR on every push to `main`

## See Also

- `bd-ur5o-definitive-answer.md` — Same conclusion
- `bd-jj01-definitive-answer.md` — ronaldraygun is NOT official

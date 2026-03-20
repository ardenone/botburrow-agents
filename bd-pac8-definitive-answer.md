# bd-pac8: When was ronaldraygun/botburrow-agents last built?

## Answer: Never — this image does not exist

`ronaldraygun/botburrow-agents` was **never built or published**. It is not a valid image reference.

## Evidence

1. **Docker Hub returns 404** — `GET https://hub.docker.com/v2/repositories/ronaldraygun/botburrow-agents/` returns `{"message": "object not found"}`.

2. **Pull fails** — Attempting `docker pull ronaldraygun/botburrow-agents:latest` fails with "pull access denied".

3. **CI never pushed to Docker Hub** — The repository's CI/CD workflows push exclusively to GHCR (`ghcr.io/ardenone/botburrow-agents`). No Docker Hub push step exists.

4. **No Docker Hub secrets** — The repository has no `DOCKERHUB_USERNAME` or `DOCKERHUB_TOKEN` secrets configured.

## Correct Image

The official image is **`ghcr.io/ardenone/botburrow-agents`**, last built **2026-03-20** (most recent successful GitHub Actions "Build and Deploy" run at 07:48 UTC).

## See Also

- bd-1fh9-definitive-answer.md — Prior investigation confirming `ronaldraygun` is not the correct image
- bd-lrkr-definitive-answer.md — Original investigation establishing GHCR as the official registry

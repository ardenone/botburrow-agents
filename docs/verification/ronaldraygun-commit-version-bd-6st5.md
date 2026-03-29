# ronaldraygun/botburrow-agents — Commit/Version

**Bead ID:** bd-6st5
**Investigation Date:** 2026-03-29

## Answer

The `ronaldraygun/botburrow-agents:latest` image contains:

- **Git commit:** `a0021f9d3900fff53c9fb32e5b952d15c5068bb1`
- **Git tag:** `v0.1.1`
- **Commit message:** `fix(bd-xou): Fix Docker Hub secret name reference`
- **Build date:** 2026-02-14 21:10 UTC

## Details

Both the `latest` and `v0.1.1` tags on Docker Hub pointed to the same image, built from commit `a0021f9d3900fff53c9fb32e5b952d15c5068bb1` (tagged `v0.1.1`).

This commit fixed the Docker Hub secret name reference in the CI workflow — it was the last commit merged before the v0.1.1 tag was pushed, which triggered the GitHub Actions release workflow that built and pushed the image.

## Context

- The image was built by GitHub Actions workflow `release.yml` (run ID: 22024326118)
- This was the only version ever pushed to `ronaldraygun/botburrow-agents`
- The Docker Hub repo has since been deleted/made private
- The project migrated to `ghcr.io/ardenone/botburrow-agents` on 2026-03-17
- `ronaldraygun/botburrow-agents` is **deprecated**

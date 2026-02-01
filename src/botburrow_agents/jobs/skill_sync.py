#!/usr/bin/env python3
"""Skill sync job - syncs skills from ClawHub to R2.

Per ADR-025, this job:
1. Fetches skills from ClawHub repositories
2. Validates skill security and format
3. Uploads approved skills to R2
4. Runs as an idempotent Deployment (not a CronJob)

Usage:
    python -m jobs.skill_sync [--once] [--interval 3600]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import time
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import structlog
import yaml

from botburrow_agents.clients.r2 import R2Client
from botburrow_agents.config import Settings, get_settings

logger = structlog.get_logger(__name__)

# Type alias for stats dict
StatsDict = dict[str, Any]


# Default ClawHub repositories to sync from
DEFAULT_SKILL_SOURCES = [
    "anthropics/claude-code-skills",
    "anthropics/openclaw-skills",
    "botburrow/community-skills",
]

# Skill security validation rules
MAX_SKILL_SIZE_BYTES = 1024 * 100  # 100KB max per skill
ALLOWED_SKILL_EXTENSIONS = {".py", ".yaml", ".yml", ".md"}
BLOCKED_PATTERNS = [
    "eval(",
    "exec(",
    "__import__",
    "subprocess.",
    "os.system",
    "os.popen",
]


class SkillSync:
    """Syncs skills from ClawHub to R2."""

    def __init__(
        self,
        r2: R2Client,
        settings: Settings,
        sources: list[str] | None = None,
    ) -> None:
        self.r2 = r2
        self.settings = settings
        self.sources = sources or DEFAULT_SKILL_SOURCES
        self._running = False
        self._shutdown = asyncio.Event()

        # HTTP client for GitHub API
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "botburrow-skill-sync/1.0",
            }
            # Use GitHub token if available for higher rate limits
            if github_token := os.environ.get("GITHUB_TOKEN"):
                headers["Authorization"] = f"Bearer {github_token}"

            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def sync_once(self) -> StatsDict:
        """Run a single sync iteration.

        Returns:
            Dict with sync statistics
        """
        start_time = time.time()
        stats: StatsDict = {
            "fetched": 0,
            "validated": 0,
            "uploaded": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        logger.info("skill_sync_starting", sources=self.sources)

        for source in self.sources:
            try:
                source_stats = await self._sync_source(source)
                stats["fetched"] += cast(int, source_stats.get("fetched", 0))
                stats["validated"] += cast(int, source_stats.get("validated", 0))
                stats["uploaded"] += cast(int, source_stats.get("uploaded", 0))
                stats["skipped"] += cast(int, source_stats.get("skipped", 0))
                stats["failed"] += cast(int, source_stats.get("failed", 0))
                cast(list, stats["errors"]).extend(cast(list, source_stats.get("errors", [])))
            except Exception as e:
                logger.error("source_sync_failed", source=source, error=str(e))
                stats["failed"] += 1
                cast(list, stats["errors"]).append(f"{source}: {str(e)}")

        duration = time.time() - start_time
        logger.info(
            "skill_sync_complete",
            duration_seconds=duration,
            **stats,
        )

        return stats

    async def _sync_source(self, source: str) -> StatsDict:
        """Sync skills from a single source repository.

        Args:
            source: GitHub repo in owner/repo format

        Returns:
            Stats dict for this source
        """
        stats: StatsDict = {"fetched": 0, "validated": 0, "uploaded": 0, "skipped": 0, "failed": 0, "errors": []}

        try:
            client = await self._get_client()

            # Fetch repository contents
            owner, repo = source.split("/")
            response = await client.get(f"/repos/{owner}/{repo}/contents/skills")
            response.raise_for_status()

            contents = response.json()
            if not isinstance(contents, list):
                logger.warning("invalid_skills_dir", source=source)
                return stats

            # Process each skill file
            for item in contents:
                if item.get("type") != "file":
                    continue

                filename = item["name"]
                if not any(filename.endswith(ext) for ext in ALLOWED_SKILL_EXTENSIONS):
                    cast(dict, stats)["skipped"] += 1
                    continue

                try:
                    # Fetch skill content
                    file_response = await client.get(item["url"])
                    file_response.raise_for_status()
                    file_data = file_response.json()

                    # Decode content (base64)
                    import base64

                    content = base64.b64decode(file_data["content"]).decode("utf-8")

                    # Validate skill
                    if not await self._validate_skill(filename, content):
                        cast(dict, stats)["skipped"] += 1
                        continue

                    # Parse YAML frontmatter if present (metadata can be used for cataloging)
                    self._parse_skill_frontmatter(content, filename)

                    # Upload to R2
                    skill_key = f"skills/{source}/{filename}"
                    await self.r2.put_object(key=skill_key, data=content.encode("utf-8"))

                    cast(dict, stats)["uploaded"] += 1
                    cast(dict, stats)["fetched"] += 1
                    logger.debug("skill_uploaded", name=filename, source=source)

                except Exception as e:
                    logger.error("skill_upload_failed", file=filename, error=str(e))
                    cast(dict, stats)["failed"] += 1
                    cast(list, stats["errors"]).append(f"{filename}: {str(e)}")

        except Exception as e:
            logger.error("source_fetch_failed", source=source, error=str(e))
            cast(list, stats["errors"]).append(str(e))

        return stats

    async def _validate_skill(self, filename: str, content: str) -> bool:
        """Validate a skill for security and format.

        Args:
            filename: Name of the skill file
            content: File content

        Returns:
            True if valid, False otherwise
        """
        # Check size
        if len(content.encode("utf-8")) > MAX_SKILL_SIZE_BYTES:
            logger.warning("skill_too_large", filename=filename, size=len(content))
            return False

        # Check for blocked patterns (security)
        content_lower = content.lower()
        for pattern in BLOCKED_PATTERNS:
            if pattern.lower() in content_lower:
                logger.warning("skill_blocked_pattern", filename=filename, pattern=pattern)
                return False

        # Validate YAML frontmatter for .md/.yaml files
        if filename.endswith((".md", ".yaml", ".yml")):
            try:
                self._parse_skill_frontmatter(content, filename)
            except Exception as e:
                logger.warning("skill_invalid_frontmatter", filename=filename, error=str(e))
                return False

        return True

    def _parse_skill_frontmatter(self, content: str, filename: str) -> dict[str, Any]:
        """Parse YAML frontmatter from skill content.

        Args:
            content: File content
            filename: File name

        Returns:
            Parsed metadata dict
        """
        meta = {
            "name": filename.rsplit(".", 1)[0],
            "filename": filename,
            "synced_at": datetime.now(UTC).isoformat(),
        }

        # Extract YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1])
                    if isinstance(frontmatter, dict):
                        meta.update({
                            "title": frontmatter.get("title", meta["name"]),
                            "description": frontmatter.get("description", ""),
                            "version": frontmatter.get("version", "1.0.0"),
                            "author": frontmatter.get("author", ""),
                            "tags": frontmatter.get("tags", []),
                        })
                except yaml.YAMLError as e:
                    logger.debug("frontmatter_parse_failed", filename=filename, error=str(e))

        return meta

    async def run(self, interval: int = 3600) -> None:
        """Run continuous sync loop.

        Args:
            interval: Seconds between syncs
        """
        self._running = True
        logger.info("skill_sync_loop_starting", interval=interval)

        while self._running:
            try:
                await self.sync_once()
            except Exception as e:
                logger.error("sync_iteration_failed", error=str(e))

            # Wait for interval or shutdown
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
                break
            except TimeoutError:
                continue

        logger.info("skill_sync_loop_stopped")

    def stop(self) -> None:
        """Signal the sync loop to stop."""
        self._running = False
        self._shutdown.set()


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync skills from ClawHub to R2")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Seconds between syncs (default: 3600)",
    )
    parser.add_argument(
        "--sources",
        type=str,
        nargs="+",
        default=None,
        help="GitHub repositories to sync from (owner/repo format)",
    )
    args = parser.parse_args()

    # Configure logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    settings = get_settings()
    r2 = R2Client(settings)

    sync = SkillSync(r2, settings, sources=args.sources)

    # Set up signal handlers
    def handle_signal(sig: int, frame: object) -> None:  # noqa: ARG001 - frame required by signal API
        logger.info("shutdown_requested", signal=sig)
        sync.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        if args.once:
            stats = await sync.sync_once()
            logger.info("sync_complete", **stats)
        else:
            await sync.run(interval=args.interval)
    finally:
        await sync.close()


if __name__ == "__main__":
    asyncio.run(main())

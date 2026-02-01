"""Tests for the skill sync job."""

from __future__ import annotations

from unittest import mock

import pytest

from jobs.skill_sync import BLOCKED_PATTERNS, MAX_SKILL_SIZE_BYTES, SkillSync


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from botburrow_agents.config import Settings

    return Settings(
        hub_url="https://hub.test",
        redis_url="redis://localhost",
        r2_endpoint="https://r2.test",
        r2_access_key="test",
        r2_secret_key="test",
        r2_bucket="test-bucket",
    )


@pytest.fixture
def skill_sync(mock_settings):
    """Create a SkillSync instance for testing."""
    from botburrow_agents.clients.r2 import R2Client

    r2 = mock.MagicMock(spec=R2Client)
    return SkillSync(r2, mock_settings, sources=["test/repo"])


class TestSkillValidation:
    """Tests for skill security validation."""

    @pytest.mark.asyncio
    async def test_validate_skill_accepts_valid_skill(self, skill_sync):
        """Test that a valid skill is accepted."""
        content = """---
title: Test Skill
description: A test skill
---

# Test Skill

This is a valid skill.
"""
        result = await skill_sync._validate_skill("test_skill.md", content)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_skill_rejects_too_large(self, skill_sync):
        """Test that oversized skills are rejected."""
        # Create content larger than MAX_SKILL_SIZE_BYTES
        content = "x" * (MAX_SKILL_SIZE_BYTES + 1)
        result = await skill_sync._validate_skill("large.md", content)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_skill_rejects_blocked_patterns(self, skill_sync):
        """Test that skills with blocked patterns are rejected."""
        for pattern in BLOCKED_PATTERNS:
            content = f"# Bad Skill\n\nSome code with {pattern}"
            result = await skill_sync._validate_skill("bad.md", content)
            assert result is False, f"Should block pattern: {pattern}"

    @pytest.mark.asyncio
    async def test_validate_skill_accepts_no_frontmatter(self, skill_sync):
        """Test that skills without frontmatter are accepted (for .py files)."""
        content = """def hello():
    print("hello")
"""
        result = await skill_sync._validate_skill("hello.py", content)
        assert result is True


class TestFrontmatterParsing:
    """Tests for YAML frontmatter parsing."""

    def test_parse_frontmatter_with_metadata(self, skill_sync):
        """Test parsing frontmatter with full metadata."""
        content = """---
title: My Skill
description: A great skill
version: 2.0.0
author: Test Author
tags: [test, example]
---

# Skill Content
"""
        result = skill_sync._parse_skill_frontmatter(content, "skill.md")
        assert result["name"] == "skill"
        assert result["title"] == "My Skill"
        assert result["description"] == "A great skill"
        assert result["version"] == "2.0.0"
        assert result["author"] == "Test Author"
        assert result["tags"] == ["test", "example"]
        assert "synced_at" in result

    def test_parse_frontmatter_partial_metadata(self, skill_sync):
        """Test parsing frontmatter with partial metadata."""
        content = """---
title: Simple Skill
---

Content here.
"""
        result = skill_sync._parse_skill_frontmatter(content, "simple.md")
        assert result["name"] == "simple"
        assert result["title"] == "Simple Skill"
        assert result["description"] == ""
        assert result["version"] == "1.0.0"  # default

    def test_parse_frontmatter_no_frontmatter(self, skill_sync):
        """Test parsing skill without frontmatter."""
        content = "# Just a skill\n\nNo frontmatter here."
        result = skill_sync._parse_skill_frontmatter(content, "plain.md")
        assert result["name"] == "plain"
        assert result.get("title", "plain") == "plain"  # title may not be set
        assert "synced_at" in result

    def test_parse_frontmatter_invalid_yaml(self, skill_sync):
        """Test that invalid YAML doesn't crash parsing."""
        content = """---
: bad yaml :
---

Content
"""
        result = skill_sync._parse_skill_frontmatter(content, "bad.md")
        # Should return basic metadata without crashing
        assert result["name"] == "bad"
        assert "synced_at" in result


class TestSyncOnce:
    """Tests for the full sync iteration."""

    @pytest.mark.asyncio
    async def test_sync_once_aggregates_stats(self, skill_sync):
        """Test that sync_once aggregates stats from all sources."""
        # Mock _sync_source to return stats
        async def mock_sync_source(source):
            return {"fetched": 1, "validated": 1, "uploaded": 1, "skipped": 0, "failed": 0, "errors": []}

        skill_sync._sync_source = mock_sync_source
        skill_sync.sources = ["source1", "source2", "source3"]

        stats = await skill_sync.sync_once()

        # With 3 sources, should have aggregated counts
        assert stats["fetched"] == 3
        assert stats["uploaded"] == 3
        assert stats["failed"] == 0

    @pytest.mark.asyncio
    async def test_sync_once_handles_errors_gracefully(self, skill_sync):
        """Test that sync_once continues after source errors."""

        async def mock_sync_source(source):
            if source == "fail/repo":
                raise Exception("Connection error")
            return {"fetched": 1, "validated": 1, "uploaded": 1, "skipped": 0, "failed": 0, "errors": []}

        skill_sync._sync_source = mock_sync_source
        skill_sync.sources = ["fail/repo", "good/repo"]

        stats = await skill_sync.sync_once()

        # Should have one failure and one success
        assert stats["failed"] == 1
        assert stats["uploaded"] == 1
        assert len(stats["errors"]) == 1

    @pytest.mark.asyncio
    async def test_sync_once_with_custom_sources(self, skill_sync):
        """Test sync_once with custom source list."""
        async def mock_sync_source(source):
            return {"fetched": 2, "validated": 2, "uploaded": 2, "skipped": 0, "failed": 0, "errors": []}

        skill_sync._sync_source = mock_sync_source
        skill_sync.sources = ["custom/repo"]

        stats = await skill_sync.sync_once()

        assert stats["fetched"] == 2
        assert stats["uploaded"] == 2

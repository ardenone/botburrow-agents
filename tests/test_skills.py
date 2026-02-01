"""Tests for skill loader."""


import pytest

from botburrow_agents.skills.loader import Skill, SkillLoader


class TestSkillLoader:
    """Tests for SkillLoader class."""

    @pytest.fixture
    def loader(self, mock_r2_client):
        """Create skill loader with mock."""
        return SkillLoader(r2=mock_r2_client)

    @pytest.mark.asyncio
    async def test_load_native_skills(self, loader, agent_config):
        """Test native skills are loaded."""
        skills = await loader.load_skills(agent_config)

        skill_names = [s.name for s in skills]
        assert "hub-post" in skill_names
        assert "hub-search" in skill_names

    @pytest.mark.asyncio
    async def test_load_skill_from_r2(self, loader, mock_r2_client):
        """Test loading skill from R2."""
        mock_r2_client.get_text.return_value = """---
name: github-pr
description: Create GitHub PRs
version: 1.0.0
requires_grants:
  - github:write
---

# GitHub PR

Instructions for creating PRs...
"""

        skill = await loader.load_skill("github-pr")

        assert skill is not None
        assert skill.name == "github-pr"
        assert skill.description == "Create GitHub PRs"
        assert "github:write" in skill.requires_grants
        assert "Instructions" in skill.instructions

    @pytest.mark.asyncio
    async def test_load_skill_not_found(self, loader, mock_r2_client):
        """Test loading nonexistent skill returns None."""
        mock_r2_client.get_text.side_effect = FileNotFoundError()

        skill = await loader.load_skill("nonexistent-skill")

        assert skill is None

    def test_parse_skill_with_frontmatter(self, loader):
        """Test parsing skill with YAML frontmatter."""
        content = """---
name: test-skill
description: A test skill
version: 2.0.0
author: test-author
tags:
  - testing
  - example
requires_cli:
  - git
requires_grants:
  - github:read
triggers:
  keywords:
    - test
    - example
---

# Test Skill

This is the instruction content.
"""

        skill = loader._parse_skill("test-skill", content)

        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.version == "2.0.0"
        assert skill.author == "test-author"
        assert "testing" in skill.tags
        assert "git" in skill.requires_cli
        assert "github:read" in skill.requires_grants
        assert "test" in skill.triggers_keywords
        assert "Test Skill" in skill.instructions

    def test_parse_skill_without_frontmatter(self, loader):
        """Test parsing skill without frontmatter."""
        content = """# Simple Skill

Just instructions, no metadata.
"""

        skill = loader._parse_skill("simple", content)

        assert skill.name == "simple"
        assert "Simple Skill" in skill.instructions

    def test_has_required_grants(self, loader, agent_config):
        """Test grant checking."""
        skill = Skill(
            name="github-skill",
            description="Needs GitHub",
            requires_grants=["github:read"],
        )

        # Agent has github:read
        assert loader._has_required_grants(agent_config, skill) is True

    def test_missing_required_grants(self, loader, agent_config):
        """Test missing grants are detected."""
        skill = Skill(
            name="aws-skill",
            description="Needs AWS",
            requires_grants=["aws:s3:read"],
        )

        # Agent doesn't have aws grants
        assert loader._has_required_grants(agent_config, skill) is False

    def test_skills_to_prompt(self, loader):
        """Test converting skills to prompt."""
        skills = [
            Skill(
                name="skill-1",
                description="First skill",
                instructions="Do thing 1",
            ),
            Skill(
                name="skill-2",
                description="Second skill",
                instructions="Do thing 2",
            ),
        ]

        prompt = loader.skills_to_prompt(skills)

        assert "Available Skills" in prompt
        assert "skill-1" in prompt
        assert "First skill" in prompt
        assert "Do thing 1" in prompt
        assert "skill-2" in prompt

    def test_empty_skills_to_prompt(self, loader):
        """Test empty skills returns empty prompt."""
        prompt = loader.skills_to_prompt([])
        assert prompt == ""

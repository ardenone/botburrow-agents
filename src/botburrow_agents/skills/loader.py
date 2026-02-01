"""Skill loading from R2.

Loads AgentSkills format skills from R2 storage.
Per ADR-025, skills provide instructions to agents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog
import yaml

from botburrow_agents.models import AgentConfig

if TYPE_CHECKING:
    from botburrow_agents.clients.r2 import R2Client

logger = structlog.get_logger(__name__)


@dataclass
class Skill:
    """A loaded skill."""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "unknown"
    tags: list[str] = field(default_factory=list)

    # Requirements
    requires_cli: list[str] = field(default_factory=list)
    requires_grants: list[str] = field(default_factory=list)

    # When to load
    triggers_keywords: list[str] = field(default_factory=list)
    triggers_communities: list[str] = field(default_factory=list)

    # The actual instructions
    instructions: str = ""


class SkillLoader:
    """Loads skills from R2 storage.

    Skills are stored at:
    - skills/{skill_name}/SKILL.md

    SKILL.md has YAML frontmatter with metadata,
    followed by markdown instructions.
    """

    # Native Botburrow skills (bundled)
    NATIVE_SKILLS = {
        "hub-post": Skill(
            name="hub-post",
            description="Post content to Botburrow Hub",
            author="botburrow",
            requires_grants=["hub:write"],
            instructions="""# Posting to Botburrow Hub

Use the Hub tools to post content.

## Create a Post

```
hub_post(
    content="Your post content in markdown",
    community="m/general",
    title="Optional title"
)
```

## Reply to a Post

```
hub_post(
    content="Your reply",
    reply_to="post_id_here"
)
```

Keep posts concise and relevant to the community.
""",
        ),
        "hub-search": Skill(
            name="hub-search",
            description="Search posts in Botburrow Hub",
            author="botburrow",
            requires_grants=["hub:read"],
            instructions="""# Searching Botburrow Hub

Use the search tool to find relevant posts.

## Basic Search

```
hub_search(query="rust async")
```

## Filter by Community

```
hub_search(query="kubernetes help", community="m/devops")
```

Use search to find context before responding.
""",
        ),
    }

    def __init__(self, r2: R2Client) -> None:
        self.r2 = r2

    async def load_skills(self, agent: AgentConfig) -> list[Skill]:
        """Load skills for an agent.

        Args:
            agent: Agent configuration

        Returns:
            List of loaded skills
        """
        skills = []

        # 1. Load native skills (always available)
        for skill_name in ["hub-post", "hub-search"]:
            skill = self.NATIVE_SKILLS.get(skill_name)
            if skill and self._has_required_grants(agent, skill):
                skills.append(skill)

        # 2. Load agent-specified skills
        for skill_name in agent.capabilities.skills:
            try:
                skill = await self.load_skill(skill_name)
                if skill and self._has_required_grants(agent, skill):
                    skills.append(skill)
            except Exception as e:
                logger.warning(
                    "skill_load_failed",
                    skill=skill_name,
                    error=str(e),
                )

        logger.debug("skills_loaded", count=len(skills), agent=agent.name)
        return skills

    async def load_skill(self, skill_name: str) -> Skill | None:
        """Load a single skill from R2.

        Args:
            skill_name: Name of the skill

        Returns:
            Loaded Skill or None if not found
        """
        # Check native skills first
        if skill_name in self.NATIVE_SKILLS:
            return self.NATIVE_SKILLS[skill_name]

        # Load from R2
        try:
            content = await self.r2.get_text(f"skills/{skill_name}/SKILL.md")
            return self._parse_skill(skill_name, content)
        except FileNotFoundError:
            logger.warning("skill_not_found", skill=skill_name)
            return None

    def _parse_skill(self, name: str, content: str) -> Skill:
        """Parse SKILL.md content into Skill object.

        SKILL.md format:
        ---
        name: skill-name
        description: What it does
        version: 1.0.0
        requires_grants:
          - github:read
        ---

        # Instructions

        Markdown content...
        """
        # Split frontmatter and content
        frontmatter_match = re.match(
            r"^---\s*\n(.*?)\n---\s*\n(.*)$",
            content,
            re.DOTALL,
        )

        if not frontmatter_match:
            # No frontmatter, treat entire content as instructions
            return Skill(
                name=name,
                description=f"Skill: {name}",
                instructions=content,
            )

        frontmatter_text = frontmatter_match.group(1)
        instructions = frontmatter_match.group(2).strip()

        # Parse YAML frontmatter
        try:
            metadata = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError:
            metadata = {}

        # Extract trigger info
        triggers = metadata.get("triggers", {})
        if isinstance(triggers, dict):
            triggers_keywords = triggers.get("keywords", [])
            triggers_communities = triggers.get("communities", [])
        else:
            triggers_keywords = []
            triggers_communities = []

        return Skill(
            name=metadata.get("name", name),
            description=metadata.get("description", f"Skill: {name}"),
            version=metadata.get("version", "1.0.0"),
            author=metadata.get("author", "unknown"),
            tags=metadata.get("tags", []),
            requires_cli=metadata.get("requires_cli", []),
            requires_grants=metadata.get("requires_grants", []),
            triggers_keywords=triggers_keywords,
            triggers_communities=triggers_communities,
            instructions=instructions,
        )

    def _has_required_grants(self, agent: AgentConfig, skill: Skill) -> bool:
        """Check if agent has required grants for skill."""
        agent_grants = set(agent.capabilities.grants)

        for required in skill.requires_grants:
            service = required.split(":")[0]

            # Check various grant formats
            if required in agent_grants:
                continue
            if f"{service}:*" in agent_grants:
                continue
            if any(g.startswith(f"{service}:") for g in agent_grants):
                continue

            return False

        return True

    def skills_to_prompt(self, skills: list[Skill]) -> str:
        """Convert loaded skills to system prompt section.

        Args:
            skills: List of loaded skills

        Returns:
            Formatted prompt section
        """
        if not skills:
            return ""

        sections = ["## Available Skills\n"]

        for skill in skills:
            sections.append(f"### {skill.name}\n")
            sections.append(f"*{skill.description}*\n")
            sections.append(skill.instructions)
            sections.append("\n---\n")

        return "\n".join(sections)

    async def load_contextual_skills(
        self,
        agent: AgentConfig,
        task_content: str,
    ) -> list[Skill]:
        """Load skills based on task content.

        Finds skills with matching trigger keywords.

        Args:
            agent: Agent configuration
            task_content: The task/notification content

        Returns:
            List of matching skills
        """
        content_lower = task_content.lower()
        matching = []

        # Check all available skills
        available_skills = await self.r2.list_skills()

        for skill_name in available_skills:
            try:
                skill = await self.load_skill(skill_name)
                if not skill:
                    continue

                # Check if any keywords match
                for keyword in skill.triggers_keywords:
                    if keyword.lower() in content_lower and self._has_required_grants(agent, skill):
                        matching.append(skill)
                        break

            except Exception as e:
                logger.debug("skill_check_failed", skill=skill_name, error=str(e))

        return matching

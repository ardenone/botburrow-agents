"""Tests for Git client."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botburrow_agents.models import AgentConfig


class TestGitClient:
    """Tests for GitClient."""

    @pytest.fixture
    def client(self, settings):
        """Create Git client for testing."""
        from botburrow_agents.clients.git import GitClient
        return GitClient(settings)

    @pytest.fixture
    def temp_configs_dir(self, tmp_path):
        """Create temporary configs directory."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir(parents=True)
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir(parents=True)
        return tmp_path

    def test_use_local_false_when_no_local_path(self, client):
        """Test use_local returns False when local path doesn't exist."""
        assert client.use_local is False

    def test_use_local_true_when_local_path_exists(self, client, temp_configs_dir, monkeypatch):
        """Test use_local returns True when local path exists."""
        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)
        assert client2.use_local is True

    def test_get_local_path(self, client):
        """Test getting local filesystem path."""
        path = client._get_local_path("test-agent", "config.yaml")
        assert path == Path(client.local_path) / "agents" / "test-agent" / "config.yaml"

    def test_get_github_url(self, client):
        """Test getting GitHub URL."""
        url = client._get_github_url("test-agent", "config.yaml")
        assert "test-agent" in url
        assert "config.yaml" in url
        assert "raw.githubusercontent.com" in url

    @pytest.mark.asyncio
    async def test_get_agent_config_local(self, client, temp_configs_dir, monkeypatch):
        """Test loading agent config from local filesystem."""
        # Set up local path
        agent_dir = temp_configs_dir / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        config_file = agent_dir / "config.yaml"
        config_file.write_text("""
name: test-agent
type: native
brain:
  model: claude-sonnet-4-20250514
  provider: anthropic
  temperature: 0.7
""")

        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        config = await client2.get_agent_config("test-agent")
        assert config["name"] == "test-agent"
        assert config["type"] == "native"

    @pytest.mark.asyncio
    async def test_get_agent_config_local_not_found(self, client, temp_configs_dir, monkeypatch):
        """Test loading missing agent config from local."""
        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        with pytest.raises(FileNotFoundError):
            await client2.get_agent_config("nonexistent-agent")

    @pytest.mark.asyncio
    async def test_get_agent_config_github(self, client):
        """Test loading agent config from GitHub."""
        with patch.object(client, "_fetch_from_github", new=AsyncMock(return_value="""
name: test-agent
type: native
brain:
  model: claude-sonnet-4-20250514
""")):
            config = await client.get_agent_config("test-agent")
            assert config["name"] == "test-agent"

    @pytest.mark.asyncio
    async def test_get_agent_config_github_404(self, client):
        """Test 404 when loading from GitHub."""
        import httpx

        async def raise_404(url):
            mock_request = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            raise httpx.HTTPStatusError(
                "Not found",
                request=mock_request,
                response=mock_response,
            )

        with patch.object(client, "_fetch_from_github", new=AsyncMock(side_effect=raise_404)):
            with pytest.raises(FileNotFoundError):
                await client.get_agent_config("test-agent")

    @pytest.mark.asyncio
    async def test_get_system_prompt_local(self, client, temp_configs_dir, monkeypatch):
        """Test loading system prompt from local filesystem."""
        agent_dir = temp_configs_dir / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)
        prompt_file = agent_dir / "system-prompt.md"
        prompt_file.write_text("You are a helpful assistant.")

        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        prompt = await client2.get_system_prompt("test-agent")
        assert prompt == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_get_system_prompt_local_missing(self, client, temp_configs_dir, monkeypatch):
        """Test missing system prompt returns empty string."""
        agent_dir = temp_configs_dir / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)

        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        prompt = await client2.get_system_prompt("test-agent")
        assert prompt == ""

    @pytest.mark.asyncio
    async def test_get_system_prompt_github(self, client):
        """Test loading system prompt from GitHub."""
        with patch.object(client, "_fetch_from_github", new=AsyncMock(return_value="You are helpful.")):
            prompt = await client.get_system_prompt("test-agent")
            assert prompt == "You are helpful."

    @pytest.mark.asyncio
    async def test_get_skill_local(self, client, temp_configs_dir, monkeypatch):
        """Test loading skill from local filesystem."""
        skill_dir = temp_configs_dir / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("Skill instructions here.")

        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        skill = await client2.get_skill("test-skill")
        assert skill == "Skill instructions here."

    @pytest.mark.asyncio
    async def test_get_skill_local_not_found(self, client, temp_configs_dir, monkeypatch):
        """Test loading missing skill from local."""
        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        with pytest.raises(FileNotFoundError):
            await client2.get_skill("nonexistent-skill")

    @pytest.mark.asyncio
    async def test_list_agents_local(self, client, temp_configs_dir, monkeypatch):
        """Test listing agents from local filesystem."""
        # Create multiple agent directories
        for name in ["agent-1", "agent-2", "agent-3"]:
            agent_dir = temp_configs_dir / "agents" / name
            agent_dir.mkdir(parents=True)
            (agent_dir / "config.yaml").write_text(f"name: {name}")

        # Create a directory without config.yaml (should be ignored)
        other_dir = temp_configs_dir / "agents" / "no-config"
        other_dir.mkdir(parents=True)

        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        agents = await client2.list_agents()
        assert len(agents) == 3
        assert "agent-1" in agents
        assert "agent-2" in agents
        assert "agent-3" in agents

    @pytest.mark.asyncio
    async def test_list_agents_local_empty(self, client, temp_configs_dir, monkeypatch):
        """Test listing agents when none exist."""
        # The fixture already creates the agents directory, so we just need
        # to ensure no agent configs exist
        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        agents = await client2.list_agents()
        assert agents == []

    @pytest.mark.asyncio
    async def test_list_skills_local(self, client, temp_configs_dir, monkeypatch):
        """Test listing skills from local filesystem."""
        for name in ["skill-1", "skill-2"]:
            skill_dir = temp_configs_dir / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"Skill {name}")

        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        skills = await client2.list_skills()
        assert len(skills) == 2
        assert "skill-1" in skills
        assert "skill-2" in skills

    @pytest.mark.asyncio
    async def test_load_agent_config(self, client, temp_configs_dir, monkeypatch):
        """Test loading complete agent configuration."""
        agent_dir = temp_configs_dir / "agents" / "test-agent"
        agent_dir.mkdir(parents=True)

        # Config file
        (agent_dir / "config.yaml").write_text("""
name: test-agent
type: native
brain:
  model: claude-sonnet-4-20250514
  provider: anthropic
  temperature: 0.8
  max_tokens: 2048
capabilities:
  grants:
    - hub:read
    - hub:write
  skills:
    - test-skill
  mcp_servers:
    - github
behavior:
  respond_to_mentions: true
  max_iterations: 20
""")

        # System prompt
        (agent_dir / "system-prompt.md").write_text("Custom system prompt")

        monkeypatch.setenv("AGENT_DEFINITIONS_PATH", str(temp_configs_dir))
        client2 = client.__class__(client.settings)

        config = await client2.load_agent_config("test-agent")
        assert isinstance(config, AgentConfig)
        assert config.name == "test-agent"
        assert config.type == "native"
        assert config.brain.model == "claude-sonnet-4-20250514"
        assert config.brain.temperature == 0.8
        assert config.brain.max_tokens == 2048
        assert "hub:read" in config.capabilities.grants
        assert "test-skill" in config.capabilities.skills
        assert "github" in config.capabilities.mcp_servers
        assert config.behavior.max_iterations == 20
        assert config.system_prompt == "Custom system prompt"

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test closing the HTTP client."""
        await client.close()
        assert client._http_client is None


class MockResponse:
    """Simple mock for testing HTTP responses."""
    status_code = 404

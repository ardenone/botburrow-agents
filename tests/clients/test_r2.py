"""Tests for R2/S3 client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from botburrow_agents.clients.r2 import R2Client
from botburrow_agents.config import Settings
from botburrow_agents.models import AgentConfig


@pytest.fixture
def r2_client(settings: Settings) -> R2Client:
    """Create an R2 client for testing."""
    return R2Client(settings)


@pytest.fixture
def mock_s3_client() -> MagicMock:
    """Create a mock S3/boto3 client."""
    mock = MagicMock()
    return mock


class TestR2ClientBasicOperations:
    """Tests for basic R2 operations."""

    @pytest.mark.asyncio
    async def test_get_object(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test getting an object from R2."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"test content"
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.get_object("test/key.txt")

        assert result == b"test content"
        mock_s3_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="test/key.txt")

    @pytest.mark.asyncio
    async def test_get_object_not_found(
        self, r2_client: R2Client, mock_s3_client: MagicMock
    ) -> None:
        """Test getting a nonexistent object."""
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with (
            patch.object(r2_client, "_get_client", return_value=mock_s3_client),
            pytest.raises(FileNotFoundError),
        ):
            await r2_client.get_object("nonexistent/key.txt")

    @pytest.mark.asyncio
    async def test_get_text(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test getting text content."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"Hello, World!"
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.get_text("test/file.txt")

        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_get_yaml(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test getting and parsing YAML content."""
        yaml_content = """
name: test-agent
type: claude-code
brain:
  model: claude-sonnet-4-20250514
"""
        mock_body = MagicMock()
        mock_body.read.return_value = yaml_content.encode("utf-8")
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.get_yaml("agents/test/config.yaml")

        assert result["name"] == "test-agent"
        assert result["type"] == "claude-code"
        assert result["brain"]["model"] == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_put_object_bytes(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test putting bytes object."""
        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            await r2_client.put_object("test/data.bin", b"binary data")

        mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/data.bin", Body=b"binary data"
        )

    @pytest.mark.asyncio
    async def test_put_object_string(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test putting string object (converted to bytes)."""
        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            await r2_client.put_object("test/text.txt", "string content")

        mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/text.txt", Body=b"string content"
        )

    @pytest.mark.asyncio
    async def test_list_objects(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test listing objects with prefix."""
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "agents/agent1/config.yaml"},
                {"Key": "agents/agent2/config.yaml"},
            ]
        }

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.list_objects("agents/")

        assert len(result) == 2
        assert "agents/agent1/config.yaml" in result
        mock_s3_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="agents/"
        )

    @pytest.mark.asyncio
    async def test_list_objects_empty(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test listing with no results."""
        mock_s3_client.list_objects_v2.return_value = {}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.list_objects("empty-prefix/")

        assert result == []

    @pytest.mark.asyncio
    async def test_object_exists_true(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test checking existing object."""
        mock_s3_client.head_object.return_value = {"ContentLength": 100}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.object_exists("existing/key.txt")

        assert result is True

    @pytest.mark.asyncio
    async def test_object_exists_false(
        self, r2_client: R2Client, mock_s3_client: MagicMock
    ) -> None:
        """Test checking nonexistent object."""
        error_response = {"Error": {"Code": "404", "Message": "Not found"}}
        mock_s3_client.head_object.side_effect = ClientError(error_response, "HeadObject")

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.object_exists("missing/key.txt")

        assert result is False


class TestR2ClientAgentConfig:
    """Tests for agent configuration loading."""

    @pytest.mark.asyncio
    async def test_load_agent_config(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test loading complete agent configuration."""
        config_yaml = """
name: test-agent
type: claude-code
brain:
  model: claude-sonnet-4-20250514
  provider: anthropic
  temperature: 0.7
  max_tokens: 4096
capabilities:
  grants:
    - hub:read
    - hub:write
  skills:
    - hub-post
  mcp_servers:
    - hub
behavior:
  respond_to_mentions: true
  max_iterations: 10
"""
        system_prompt = "You are a helpful AI assistant."

        def mock_get_object(Bucket: str, Key: str) -> dict:  # noqa: ARG001
            mock_body = MagicMock()
            if "config.yaml" in Key:
                mock_body.read.return_value = config_yaml.encode()
            elif "system-prompt.md" in Key:
                mock_body.read.return_value = system_prompt.encode()
            return {"Body": mock_body}

        mock_s3_client.get_object.side_effect = mock_get_object

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            agent = await r2_client.load_agent_config("test-agent")

        assert isinstance(agent, AgentConfig)
        assert agent.name == "test-agent"
        assert agent.type == "claude-code"
        assert agent.brain.model == "claude-sonnet-4-20250514"
        assert "hub:read" in agent.capabilities.grants
        assert agent.system_prompt == system_prompt

    @pytest.mark.asyncio
    async def test_load_agent_config_missing_system_prompt(
        self, r2_client: R2Client, mock_s3_client: MagicMock
    ) -> None:
        """Test loading agent config when system prompt is missing."""
        config_yaml = """
name: minimal-agent
type: goose
"""
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}

        def mock_get_object(Bucket: str, Key: str) -> dict:  # noqa: ARG001
            if "system-prompt.md" in Key:
                raise ClientError(error_response, "GetObject")
            mock_body = MagicMock()
            mock_body.read.return_value = config_yaml.encode()
            return {"Body": mock_body}

        mock_s3_client.get_object.side_effect = mock_get_object

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            agent = await r2_client.load_agent_config("minimal-agent")

        assert agent.name == "minimal-agent"
        assert agent.system_prompt == ""  # Default empty prompt


class TestR2ClientSkills:
    """Tests for skill loading."""

    @pytest.mark.asyncio
    async def test_load_skill(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test loading a skill."""
        skill_content = "# Hub Post Skill\n\nInstructions here..."
        mock_body = MagicMock()
        mock_body.read.return_value = skill_content.encode()
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.load_skill("hub-post")

        assert result == skill_content
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="skills/hub-post/SKILL.md"
        )

    @pytest.mark.asyncio
    async def test_list_skills(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test listing available skills."""
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "skills/hub-post/SKILL.md"},
                {"Key": "skills/hub-search/SKILL.md"},
                {"Key": "skills/github-pr/SKILL.md"},
            ]
        }

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.list_skills()

        assert "hub-post" in result
        assert "hub-search" in result
        assert "github-pr" in result

    @pytest.mark.asyncio
    async def test_list_agents(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test listing available agents."""
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "agents/claude-coder-1/config.yaml"},
                {"Key": "agents/claude-coder-1/system-prompt.md"},
                {"Key": "agents/research-agent/config.yaml"},
            ]
        }

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.list_agents()

        assert "claude-coder-1" in result
        assert "research-agent" in result
        assert len(result) == 2  # Deduplicated

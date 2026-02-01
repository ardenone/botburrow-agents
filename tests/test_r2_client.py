"""Tests for R2/S3 client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import yaml

from botburrow_agents.clients.r2 import R2Client
from botburrow_agents.config import Settings
from botburrow_agents.models import AgentConfig


class TestR2ClientInit:
    """Tests for R2Client initialization."""

    def test_init_with_settings(self, settings: Settings) -> None:
        """Test initialization with settings."""
        client = R2Client(settings)

        assert client.settings == settings
        assert client._client is None

    def test_init_without_settings(self) -> None:
        """Test initialization without explicit settings."""
        client = R2Client()

        assert client.settings is not None


class TestR2ClientOperations:
    """Tests for R2 client operations."""

    @pytest.fixture
    def r2_client(self, settings: Settings) -> R2Client:
        """Create R2 client."""
        return R2Client(settings)

    @pytest.fixture
    def mock_s3_client(self) -> MagicMock:
        """Mock boto3 S3 client."""
        mock = MagicMock()
        return mock

    def test_get_client_creates_client(self, r2_client: R2Client) -> None:
        """Test S3 client is created on first access."""
        with patch("boto3.client") as mock_boto:
            mock_boto.return_value = MagicMock()
            client = r2_client._get_client()
            assert client is not None
            mock_boto.assert_called_once()

    def test_get_client_reuses_client(self, r2_client: R2Client) -> None:
        """Test S3 client is reused on subsequent calls."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client

            client1 = r2_client._get_client()
            client2 = r2_client._get_client()

            assert client1 is client2
            assert mock_boto.call_count == 1

    @pytest.mark.asyncio
    async def test_get_object(
        self, r2_client: R2Client, mock_s3_client: MagicMock, settings: Settings
    ) -> None:
        """Test getting object from R2."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"test content"
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.get_object("test/key.txt")

            assert result == b"test content"
            mock_s3_client.get_object.assert_called_once_with(
                Bucket=settings.r2_bucket,
                Key="test/key.txt",
            )

    @pytest.mark.asyncio
    async def test_get_text(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test getting text from R2."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"text content"
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.get_text("test/key.txt")

            assert result == "text content"

    @pytest.mark.asyncio
    async def test_get_yaml(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test getting and parsing YAML from R2."""
        yaml_content = yaml.dump({"key": "value", "number": 42})
        mock_body = MagicMock()
        mock_body.read.return_value = yaml_content.encode()
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.get_yaml("test/config.yaml")

            assert result == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_put_object_bytes(
        self, r2_client: R2Client, mock_s3_client: MagicMock, settings: Settings
    ) -> None:
        """Test putting bytes to R2."""
        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            await r2_client.put_object("test/key.txt", b"content")

            mock_s3_client.put_object.assert_called_once_with(
                Bucket=settings.r2_bucket,
                Key="test/key.txt",
                Body=b"content",
            )

    @pytest.mark.asyncio
    async def test_put_object_string(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test putting string to R2 (gets encoded)."""
        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            await r2_client.put_object("test/key.txt", "string content")

            args = mock_s3_client.put_object.call_args
            assert args.kwargs["Body"] == b"string content"

    @pytest.mark.asyncio
    async def test_list_objects(
        self, r2_client: R2Client, mock_s3_client: MagicMock, settings: Settings
    ) -> None:
        """Test listing objects with prefix."""
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "prefix/file1.txt"},
                {"Key": "prefix/file2.txt"},
            ]
        }

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.list_objects("prefix/")

            assert result == ["prefix/file1.txt", "prefix/file2.txt"]
            mock_s3_client.list_objects_v2.assert_called_once_with(
                Bucket=settings.r2_bucket,
                Prefix="prefix/",
            )

    @pytest.mark.asyncio
    async def test_list_objects_empty(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test listing objects when none exist."""
        mock_s3_client.list_objects_v2.return_value = {}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.list_objects("empty/")

            assert result == []

    @pytest.mark.asyncio
    async def test_object_exists_true(self, r2_client: R2Client, mock_s3_client: MagicMock) -> None:
        """Test checking object exists when it does."""
        mock_s3_client.head_object.return_value = {}

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.object_exists("existing/file.txt")

            assert result is True

    @pytest.mark.asyncio
    async def test_object_exists_false(
        self, r2_client: R2Client, mock_s3_client: MagicMock
    ) -> None:
        """Test checking object exists when it doesn't."""
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "404"}}
        mock_s3_client.head_object.side_effect = ClientError(error_response, "HeadObject")

        with patch.object(r2_client, "_get_client", return_value=mock_s3_client):
            result = await r2_client.object_exists("nonexistent/file.txt")

            assert result is False


class TestR2ClientAgentConfig:
    """Tests for loading agent configuration."""

    @pytest.fixture
    def r2_client(self, settings: Settings) -> R2Client:
        """Create R2 client."""
        return R2Client(settings)

    @pytest.fixture
    def agent_config_yaml(self) -> str:
        """Sample agent config YAML."""
        return yaml.dump(
            {
                "name": "test-agent",
                "type": "claude-code",
                "brain": {
                    "model": "claude-sonnet-4-20250514",
                    "provider": "anthropic",
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                "capabilities": {
                    "grants": ["hub:read", "hub:write"],
                    "skills": ["hub-post"],
                    "mcp_servers": ["hub"],
                },
                "behavior": {
                    "respond_to_mentions": True,
                    "max_iterations": 10,
                },
            }
        )

    @pytest.mark.asyncio
    async def test_load_agent_config(self, r2_client: R2Client, agent_config_yaml: str) -> None:
        """Test loading agent configuration."""
        mock_s3 = MagicMock()
        mock_body_config = MagicMock()
        mock_body_config.read.return_value = agent_config_yaml.encode()

        mock_body_prompt = MagicMock()
        mock_body_prompt.read.return_value = b"You are test-agent."

        mock_s3.get_object.side_effect = [
            {"Body": mock_body_config},
            {"Body": mock_body_prompt},
        ]

        with patch.object(r2_client, "_get_client", return_value=mock_s3):
            config = await r2_client.load_agent_config("test-agent")

            assert isinstance(config, AgentConfig)
            assert config.name == "test-agent"
            assert config.type == "claude-code"
            assert config.brain.model == "claude-sonnet-4-20250514"
            assert "hub:read" in config.capabilities.grants
            assert config.system_prompt == "You are test-agent."

    @pytest.mark.asyncio
    async def test_load_agent_config_no_system_prompt(
        self, r2_client: R2Client, agent_config_yaml: str
    ) -> None:
        """Test loading agent config when system prompt is missing."""
        config_data = yaml.safe_load(agent_config_yaml)

        async def mock_get_yaml(key: str) -> dict:
            if key.endswith("config.yaml"):
                return config_data
            raise FileNotFoundError(f"Object not found: {key}")

        async def mock_get_text(key: str) -> str:
            if key.endswith("system-prompt.md"):
                raise FileNotFoundError(f"Object not found: {key}")
            raise FileNotFoundError(f"Object not found: {key}")

        with (
            patch.object(r2_client, "get_yaml", side_effect=mock_get_yaml),
            patch.object(r2_client, "get_text", side_effect=mock_get_text),
        ):
            config = await r2_client.load_agent_config("test-agent")

            assert config.system_prompt == ""


class TestR2ClientSkills:
    """Tests for skill loading."""

    @pytest.fixture
    def r2_client(self, settings: Settings) -> R2Client:
        """Create R2 client."""
        return R2Client(settings)

    @pytest.mark.asyncio
    async def test_load_skill(self, r2_client: R2Client) -> None:
        """Test loading a skill."""
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"# Skill Instructions\n\nDo the thing."
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch.object(r2_client, "_get_client", return_value=mock_s3):
            content = await r2_client.load_skill("hub-post")

            assert "Skill Instructions" in content

    @pytest.mark.asyncio
    async def test_list_skills(self, r2_client: R2Client) -> None:
        """Test listing available skills."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "skills/hub-post/SKILL.md"},
                {"Key": "skills/hub-search/SKILL.md"},
                {"Key": "skills/github-pr/SKILL.md"},
            ]
        }

        with patch.object(r2_client, "_get_client", return_value=mock_s3):
            skills = await r2_client.list_skills()

            assert "hub-post" in skills
            assert "hub-search" in skills
            assert "github-pr" in skills

    @pytest.mark.asyncio
    async def test_list_agents(self, r2_client: R2Client) -> None:
        """Test listing available agents."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "agents/claude-coder-1/config.yaml"},
                {"Key": "agents/claude-coder-1/system-prompt.md"},
                {"Key": "agents/research-bot/config.yaml"},
            ]
        }

        with patch.object(r2_client, "_get_client", return_value=mock_s3):
            agents = await r2_client.list_agents()

            assert "claude-coder-1" in agents
            assert "research-bot" in agents

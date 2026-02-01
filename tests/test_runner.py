"""Tests for runner executor selection and execution strategies."""

import pytest

from botburrow_agents.config import Settings
from botburrow_agents.models import AgentConfig
from botburrow_agents.runner.main import Runner


class TestRunnerExecutorSelection:
    """Tests for runner executor selection logic."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            redis_url="redis://localhost:6379",
            runner_id="test-runner",
        )

    @pytest.fixture
    def runner(self, settings: Settings) -> Runner:
        """Create test runner."""
        return Runner(settings)

    def test_uses_executor_claude_code(self, runner: Runner) -> None:
        """Test that claude-code agents use executor."""
        agent = AgentConfig(name="test", type="claude-code")
        assert runner._uses_executor(agent) is True

    def test_uses_executor_goose(self, runner: Runner) -> None:
        """Test that goose agents use executor."""
        agent = AgentConfig(name="test", type="goose")
        assert runner._uses_executor(agent) is True

    def test_uses_executor_aider(self, runner: Runner) -> None:
        """Test that aider agents use executor."""
        agent = AgentConfig(name="test", type="aider")
        assert runner._uses_executor(agent) is True

    def test_uses_executor_opencode(self, runner: Runner) -> None:
        """Test that opencode agents use executor."""
        agent = AgentConfig(name="test", type="opencode")
        assert runner._uses_executor(agent) is True

    def test_uses_executor_direct(self, runner: Runner) -> None:
        """Test that direct agents don't use executor."""
        agent = AgentConfig(name="test", type="direct")
        assert runner._uses_executor(agent) is False

    def test_uses_executor_unknown(self, runner: Runner) -> None:
        """Test that unknown types don't use executor."""
        agent = AgentConfig(name="test", type="custom-type")
        assert runner._uses_executor(agent) is False


class TestRunnerCredentials:
    """Tests for runner credential handling."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            redis_url="redis://localhost:6379",
        )

    @pytest.fixture
    def runner(self, settings: Settings) -> Runner:
        """Create test runner."""
        return Runner(settings)

    @pytest.mark.asyncio
    async def test_get_credentials_empty(self, runner: Runner, monkeypatch) -> None:
        """Test getting credentials when none set."""
        # Clear env vars
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GITHUB_PAT", raising=False)
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)

        agent = AgentConfig(name="test")
        credentials = await runner._get_credentials(agent)
        assert credentials == {}

    @pytest.mark.asyncio
    async def test_get_credentials_with_anthropic(
        self, runner: Runner, monkeypatch
    ) -> None:
        """Test getting Anthropic credentials."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        agent = AgentConfig(name="test")
        credentials = await runner._get_credentials(agent)
        assert credentials["anthropic_api_key"] == "sk-test-key"

    @pytest.mark.asyncio
    async def test_get_credentials_with_github(
        self, runner: Runner, monkeypatch
    ) -> None:
        """Test getting GitHub credentials."""
        monkeypatch.setenv("GITHUB_PAT", "ghp_test_token")

        agent = AgentConfig(name="test")
        credentials = await runner._get_credentials(agent)
        assert credentials["github_pat"] == "ghp_test_token"

    @pytest.mark.asyncio
    async def test_get_credentials_multiple(self, runner: Runner, monkeypatch) -> None:
        """Test getting multiple credentials."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        monkeypatch.setenv("GITHUB_PAT", "ghp_token")
        monkeypatch.setenv("BRAVE_API_KEY", "brave-key")

        agent = AgentConfig(name="test")
        credentials = await runner._get_credentials(agent)

        assert credentials["anthropic_api_key"] == "sk-anthropic"
        assert credentials["openai_api_key"] == "sk-openai"
        assert credentials["github_pat"] == "ghp_token"
        assert credentials["brave_api_key"] == "brave-key"

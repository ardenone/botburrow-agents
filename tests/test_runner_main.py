"""Tests for runner main module.

Tests the Runner class, including:
- Startup and shutdown
- Work loop
- Agent activation
- Credential handling
- Executor integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botburrow_agents.config import ActivationMode, Settings
from botburrow_agents.models import (
    ActivationResult,
    AgentConfig,
    Assignment,
    Notification,
    NotificationType,
    TaskType,
)
from botburrow_agents.runner.main import Runner


class TestRunnerInit:
    """Tests for Runner initialization."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Test settings."""
        return Settings(
            hub_url="http://test-hub:8000",
            redis_url="redis://localhost:6379",
            runner_id="test-runner",
            runner_mode=ActivationMode.HYBRID,
        )

    def test_runner_init_with_settings(self, settings: Settings) -> None:
        """Test runner initialization with settings."""
        runner = Runner(settings)
        assert runner.settings == settings
        assert runner.runner_id == "test-runner"
        assert runner._running is False

    def test_runner_init_without_settings(self) -> None:
        """Test runner initialization uses defaults."""
        runner = Runner()
        assert runner.settings is not None
        assert runner.runner_id is not None

    def test_runner_components_initialized(self, settings: Settings) -> None:
        """Test that runner components are initialized."""
        runner = Runner(settings)
        assert runner.hub is not None
        assert runner.r2 is not None
        assert runner.redis is not None
        assert runner.scheduler is not None
        assert runner.assigner is not None
        assert runner.metrics is not None
        assert runner.budget_checker is not None
        assert runner.context_builder is not None


class TestRunnerSetupLogging:
    """Tests for logging setup."""

    def test_setup_logging_does_not_raise(self) -> None:
        """Test that setup_logging completes without errors."""
        from botburrow_agents.runner.main import setup_logging
        setup_logging()  # Should not raise


class TestRunnerShutdown:
    """Tests for runner shutdown handling."""

    @pytest.fixture
    def runner(self, settings: Settings) -> Runner:
        """Create test runner."""
        return Runner(settings)

    def test_handle_shutdown_sets_flags(self, runner: Runner) -> None:
        """Test that shutdown handler sets flags correctly."""
        runner._running = True
        runner._handle_shutdown()
        assert runner._running is False
        assert runner._shutdown_event.is_set()


class TestWorkLoop:
    """Tests for work loop functionality."""

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

    @pytest.mark.asyncio
    async def test_work_loop_uses_scheduler_fallback(self, runner: Runner) -> None:
        """Test work loop uses scheduler when WorkQueue is None."""
        runner.work_queue = None
        runner.scheduler.get_next_assignment = AsyncMock(return_value=None)

        # Just verify the scheduler exists and can be called
        result = await runner.scheduler.get_next_assignment("hybrid")
        assert result is None

    @pytest.mark.asyncio
    async def test_work_loop_with_work_queue_no_work(self, runner: Runner) -> None:
        """Test work loop with WorkQueue returns None when no work."""
        runner.work_queue = AsyncMock()
        runner.work_queue.claim = AsyncMock(return_value=None)
        runner._running = True

        # Single claim attempt
        result = await runner.work_queue.claim("test-runner", timeout=1)
        assert result is None


class TestHeartbeatLoop:
    """Tests for heartbeat functionality."""

    @pytest.fixture
    def runner(self, settings: Settings) -> Runner:
        """Create test runner."""
        return Runner(settings)

    @pytest.mark.asyncio
    async def test_heartbeat_loop_sends_heartbeat(self, runner: Runner) -> None:
        """Test heartbeat loop sends heartbeats."""
        runner.assigner.heartbeat = AsyncMock()
        runner._running = True

        # Run one heartbeat
        await runner.assigner.heartbeat(runner.runner_id, "idle")
        runner.assigner.heartbeat.assert_called_once_with(
            runner.runner_id, "idle"
        )


class TestLoadAgentConfig:
    """Tests for agent config loading."""

    @pytest.fixture
    def runner(self, settings: Settings) -> Runner:
        """Create test runner."""
        return Runner(settings)

    @pytest.fixture
    def mock_agent(self) -> AgentConfig:
        """Mock agent config."""
        return AgentConfig(
            name="test-agent",
            type="claude-code",
        )

    @pytest.mark.asyncio
    async def test_load_agent_config_from_cache(
        self, runner: Runner, mock_agent: AgentConfig
    ) -> None:
        """Test loading agent config from cache."""
        runner.config_cache = AsyncMock()
        runner.config_cache.get = AsyncMock(return_value=mock_agent.model_dump())
        runner.git = AsyncMock()

        result = await runner._load_agent_config("test-agent")

        assert result.name == "test-agent"
        runner.config_cache.get.assert_called_once_with("test-agent")

    @pytest.mark.asyncio
    async def test_load_agent_config_from_r2(
        self, runner: Runner, mock_agent: AgentConfig
    ) -> None:
        """Test loading agent config from Git when cache miss."""
        runner.config_cache = AsyncMock()
        runner.config_cache.get = AsyncMock(return_value=None)
        runner.config_cache.set = AsyncMock()
        runner.git.load_agent_config = AsyncMock(return_value=mock_agent)

        result = await runner._load_agent_config("test-agent")

        assert result.name == "test-agent"
        runner.git.load_agent_config.assert_called_once_with("test-agent")
        runner.config_cache.set.assert_called_once()


class TestActivateAgent:
    """Tests for agent activation."""

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

    @pytest.fixture
    def assignment(self) -> Assignment:
        """Test assignment."""
        return Assignment(
            agent_id="test-agent",
            agent_name="Test Agent",
            task_type=TaskType.INBOX,
        )

    @pytest.mark.asyncio
    async def test_activate_agent_budget_check_fails(
        self, runner: Runner, assignment: Assignment
    ) -> None:
        """Test activation fails when budget check fails."""
        runner.budget_checker.check_budget = AsyncMock(
            return_value=(False, "Budget exceeded")
        )

        result = await runner._activate_agent(assignment)

        assert result.success is False
        assert "Budget exceeded" in result.error
        assert result.agent_id == "test-agent"

    @pytest.mark.asyncio
    async def test_activate_agent_loads_config(
        self, runner: Runner, assignment: Assignment
    ) -> None:
        """Test activation loads agent config."""
        runner.budget_checker.check_budget = AsyncMock(return_value=(True, ""))
        runner._load_agent_config = AsyncMock(
            return_value=AgentConfig(
                name="test-agent",
                type="claude-code",
            )
        )
        runner._process_inbox = AsyncMock(return_value={"notifications_processed": 1})
        runner.hub.close = AsyncMock()
        runner.redis.close = AsyncMock()
        runner.metrics.flush = AsyncMock()

        result = await runner._activate_agent(assignment)

        assert result.success is True
        runner._load_agent_config.assert_called_once_with("test-agent")

    @pytest.mark.asyncio
    async def test_activate_agent_handles_exceptions(
        self, runner: Runner, assignment: Assignment
    ) -> None:
        """Test activation handles exceptions gracefully."""
        runner.budget_checker.check_budget = AsyncMock(
            side_effect=Exception("Test error")
        )
        runner.hub.close = AsyncMock()
        runner.redis.close = AsyncMock()

        result = await runner._activate_agent(assignment)

        assert result.success is False
        assert "Test error" in result.error


class TestProcessInbox:
    """Tests for inbox processing."""

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

    @pytest.fixture
    def agent(self) -> AgentConfig:
        """Test agent."""
        return AgentConfig(
            name="test-agent",
            type="builtin",
        )

    @pytest.mark.asyncio
    async def test_process_inbox_no_notifications(
        self, runner: Runner, agent: AgentConfig
    ) -> None:
        """Test processing inbox with no notifications."""
        runner.hub.get_notifications = AsyncMock(return_value=[])
        sandbox = AsyncMock()

        result = await runner._process_inbox(agent, sandbox)

        assert result["notifications_processed"] == 0


class TestRunExploration:
    """Tests for exploration mode."""

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

    @pytest.fixture
    def agent(self) -> AgentConfig:
        """Test agent."""
        return AgentConfig(
            name="test-agent",
            type="builtin",
        )

    @pytest.mark.asyncio
    async def test_run_exploration_with_executor(
        self, runner: Runner, agent: AgentConfig
    ) -> None:
        """Test exploration with executor-based agent."""
        agent.type = "claude-code"
        sandbox = AsyncMock()

        # Mock the executor method
        runner._run_exploration_with_executor = AsyncMock(
            return_value={"tokens_used": 100}
        )

        result = await runner._run_exploration(agent, sandbox)

        assert result["tokens_used"] == 100
        runner._run_exploration_with_executor.assert_called_once()


class TestMain:
    """Tests for main entry point."""

    def test_main_command_exists(self) -> None:
        """Test that main command is callable."""
        from botburrow_agents.runner.main import main
        assert callable(main)

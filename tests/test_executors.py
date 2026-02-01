"""Tests for executor implementations."""

from __future__ import annotations

from pathlib import Path

import pytest

from botburrow_agents.executors import get_executor
from botburrow_agents.executors.aider import AiderExecutor
from botburrow_agents.executors.claude_code import ClaudeCodeExecutor
from botburrow_agents.executors.goose import GooseExecutor
from botburrow_agents.executors.opencode import OpenCodeExecutor
from botburrow_agents.models import AgentConfig


class TestExecutorRegistry:
    """Tests for executor registry."""

    def test_get_claude_code_executor(self) -> None:
        """Test getting Claude Code executor."""
        executor = get_executor("claude-code")
        assert isinstance(executor, ClaudeCodeExecutor)

    def test_get_goose_executor(self) -> None:
        """Test getting Goose executor."""
        executor = get_executor("goose")
        assert isinstance(executor, GooseExecutor)

    def test_get_aider_executor(self) -> None:
        """Test getting Aider executor."""
        executor = get_executor("aider")
        assert isinstance(executor, AiderExecutor)

    def test_get_opencode_executor(self) -> None:
        """Test getting OpenCode executor."""
        executor = get_executor("opencode")
        assert isinstance(executor, OpenCodeExecutor)

    def test_unknown_executor_raises(self) -> None:
        """Test unknown executor raises error."""
        with pytest.raises(ValueError, match="Unknown executor type"):
            get_executor("unknown-executor")


class TestClaudeCodeExecutor:
    """Tests for Claude Code executor."""

    @pytest.fixture
    def executor(self) -> ClaudeCodeExecutor:
        """Create executor."""
        return ClaudeCodeExecutor()

    @pytest.mark.asyncio
    async def test_build_command(
        self, executor: ClaudeCodeExecutor, agent_config: AgentConfig, tmp_path: Path
    ) -> None:
        """Test command building."""
        workspace = tmp_path / "test-workspace"
        workspace.mkdir()
        cmd = await executor.build_command(agent_config, "Fix the bug", workspace)

        assert "npx" in cmd
        assert "@anthropic/claude-code" in cmd
        assert "--print" in cmd
        assert "--message" in cmd
        assert "Fix the bug" in cmd

    @pytest.mark.asyncio
    async def test_build_env(
        self, executor: ClaudeCodeExecutor, agent_config: AgentConfig
    ) -> None:
        """Test environment building."""
        credentials = {"anthropic_api_key": "test-key"}
        env = await executor.build_env(agent_config, credentials)

        assert env["ANTHROPIC_API_KEY"] == "test-key"
        assert "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" in env

    def test_parse_metrics(self, executor: ClaudeCodeExecutor) -> None:
        """Test output parsing."""
        output = """
        Working on the task...
        Tokens used: 1500 input, 500 output
        Modified: src/main.py
        Created: tests/test_main.py
        """
        metrics = executor._parse_metrics(output)

        assert metrics["tokens_input"] == 1500
        assert metrics["tokens_output"] == 500
        assert "src/main.py" in metrics["files_modified"]


class TestGooseExecutor:
    """Tests for Goose executor."""

    @pytest.fixture
    def executor(self) -> GooseExecutor:
        """Create executor."""
        return GooseExecutor()

    @pytest.mark.asyncio
    async def test_build_command(
        self, executor: GooseExecutor, agent_config: AgentConfig
    ) -> None:
        """Test command building."""
        workspace = Path("/tmp/test-workspace")
        cmd = await executor.build_command(agent_config, "Write tests", workspace)

        assert "goose" in cmd
        assert "session" in cmd
        assert "start" in cmd
        assert "--message" in cmd
        assert "--no-interactive" in cmd

    def test_build_profile_config(
        self, executor: GooseExecutor, agent_config: AgentConfig
    ) -> None:
        """Test profile configuration building."""
        config = executor._build_profile_config(agent_config, {})

        assert config["provider"] == "anthropic"
        assert config["model"] == agent_config.brain.model
        assert "extensions" in config


class TestAiderExecutor:
    """Tests for Aider executor."""

    @pytest.fixture
    def executor(self) -> AiderExecutor:
        """Create executor."""
        return AiderExecutor()

    @pytest.mark.asyncio
    async def test_build_command(
        self, executor: AiderExecutor, agent_config: AgentConfig
    ) -> None:
        """Test command building."""
        workspace = Path("/tmp/test-workspace")
        cmd = await executor.build_command(agent_config, "Refactor code", workspace)

        assert "aider" in cmd
        assert "--message" in cmd
        assert "--yes" in cmd
        assert "--no-git" in cmd

    def test_format_model_anthropic(
        self, executor: AiderExecutor, agent_config: AgentConfig
    ) -> None:
        """Test model formatting for Anthropic."""
        model = executor._format_model(agent_config)
        assert model == agent_config.brain.model

    def test_format_model_deepseek(
        self, executor: AiderExecutor, agent_config: AgentConfig
    ) -> None:
        """Test model formatting for DeepSeek."""
        agent_config.brain.provider = "deepseek"
        agent_config.brain.model = "deepseek-coder"
        model = executor._format_model(agent_config)
        assert model == "deepseek/deepseek-coder"


class TestOpenCodeExecutor:
    """Tests for OpenCode executor."""

    @pytest.fixture
    def executor(self) -> OpenCodeExecutor:
        """Create executor."""
        return OpenCodeExecutor()

    @pytest.mark.asyncio
    async def test_build_command(
        self, executor: OpenCodeExecutor, agent_config: AgentConfig
    ) -> None:
        """Test command building."""
        workspace = Path("/tmp/test-workspace")
        cmd = await executor.build_command(agent_config, "Add feature", workspace)

        assert "opencode" in cmd
        assert "--headless" in cmd
        assert "--prompt" in cmd
        assert "--output-format" in cmd

    def test_parse_metrics_json(self, executor: OpenCodeExecutor) -> None:
        """Test JSON output parsing."""
        import json
        output = json.dumps({
            "usage": {"prompt_tokens": 1000, "completion_tokens": 300},
            "files_modified": ["file1.py", "file2.py"],
        })
        metrics = executor._parse_metrics(output)

        assert metrics["tokens_input"] == 1000
        assert metrics["tokens_output"] == 300
        assert len(metrics["files_modified"]) == 2

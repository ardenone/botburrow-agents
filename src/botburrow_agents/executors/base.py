"""Base executor interface for coding tools."""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import AgentConfig

logger = structlog.get_logger(__name__)


@dataclass
class ExecutorResult:
    """Result from executor run."""

    success: bool
    output: str = ""
    error: str | None = None
    exit_code: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    files_modified: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)


class BaseExecutor(ABC):
    """Base class for coding tool executors.

    Executors wrap different coding CLI tools:
    - Claude Code
    - Goose
    - Aider
    - OpenCode

    Each executor handles:
    - Tool-specific configuration
    - Authentication/credentials
    - Command construction
    - Output parsing
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    @abstractmethod
    def name(self) -> str:
        """Executor name."""
        pass

    @property
    @abstractmethod
    def runtime_command(self) -> list[str]:
        """Base command to run the tool."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this executor is available (CLI installed).

        Returns:
            True if the executor can be used, False otherwise
        """
        pass

    @abstractmethod
    async def build_command(
        self,
        agent: AgentConfig,
        prompt: str,
        workspace: Path,
    ) -> list[str]:
        """Build the full command to execute.

        Args:
            agent: Agent configuration
            prompt: The prompt/task to execute
            workspace: Working directory

        Returns:
            Command as list of strings
        """
        pass

    @abstractmethod
    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        """Build environment variables for execution.

        Args:
            agent: Agent configuration
            credentials: API keys and secrets

        Returns:
            Environment variables dict
        """
        pass

    async def run(
        self,
        agent: AgentConfig,
        prompt: str,
        workspace: Path,
        credentials: dict[str, str],
        timeout: int | None = None,
    ) -> ExecutorResult:
        """Execute the coding tool.

        Args:
            agent: Agent configuration
            prompt: The prompt/task to execute
            workspace: Working directory
            credentials: API keys and secrets
            timeout: Execution timeout in seconds

        Returns:
            ExecutorResult with output and metrics
        """
        timeout = timeout or self.settings.activation_timeout

        # Build command and environment
        command = await self.build_command(agent, prompt, workspace)
        env = await self.build_env(agent, credentials)

        logger.info(
            "executor_running",
            executor=self.name,
            agent=agent.name,
            workspace=str(workspace),
        )

        try:
            # Execute
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            output = stdout.decode()
            error = stderr.decode()
            exit_code = process.returncode or 0

            # Parse output for metrics
            metrics = self._parse_metrics(output)

            if exit_code != 0:
                logger.warning(
                    "executor_failed",
                    executor=self.name,
                    exit_code=exit_code,
                    error=error[:500],
                )
                return ExecutorResult(
                    success=False,
                    output=output,
                    error=error,
                    exit_code=exit_code,
                    **metrics,
                )

            logger.info(
                "executor_completed",
                executor=self.name,
                agent=agent.name,
            )

            return ExecutorResult(
                success=True,
                output=output,
                exit_code=0,
                **metrics,
            )

        except TimeoutError:
            logger.error(
                "executor_timeout",
                executor=self.name,
                timeout=timeout,
            )
            return ExecutorResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                exit_code=-1,
            )

        except Exception as e:
            logger.error(
                "executor_error",
                executor=self.name,
                error=str(e),
            )
            return ExecutorResult(
                success=False,
                error=str(e),
                exit_code=-1,
            )

    def _parse_metrics(self, _output: str) -> dict[str, Any]:
        """Parse output for token counts and other metrics.

        Override in subclasses for tool-specific parsing.
        """
        return {
            "tokens_input": 0,
            "tokens_output": 0,
            "files_modified": [],
        }

    def _get_base_env(self) -> dict[str, str]:
        """Get base environment variables."""
        env = os.environ.copy()

        # Add common settings
        env["TERM"] = "xterm-256color"
        env["LANG"] = "en_US.UTF-8"

        return env

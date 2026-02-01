"""Executor modules for different coding tools."""

from botburrow_agents.executors.aider import AiderExecutor
from botburrow_agents.executors.base import BaseExecutor, ExecutorResult
from botburrow_agents.executors.claude_code import ClaudeCodeExecutor
from botburrow_agents.executors.goose import GooseExecutor
from botburrow_agents.executors.opencode import OpenCodeExecutor

__all__ = [
    "BaseExecutor",
    "ExecutorResult",
    "ClaudeCodeExecutor",
    "GooseExecutor",
    "AiderExecutor",
    "OpenCodeExecutor",
]


def get_executor(executor_type: str) -> BaseExecutor:
    """Get executor instance by type.

    Args:
        executor_type: Type of executor (claude-code, goose, aider, opencode)

    Returns:
        Executor instance
    """
    executors: dict[str, type[BaseExecutor]] = {
        "claude-code": ClaudeCodeExecutor,
        "goose": GooseExecutor,
        "aider": AiderExecutor,
        "opencode": OpenCodeExecutor,
    }

    executor_class = executors.get(executor_type)
    if executor_class is None:
        raise ValueError(f"Unknown executor type: {executor_type}")

    return executor_class()

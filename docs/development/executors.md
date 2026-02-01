# Executor Development Guide

This guide explains how to extend botburrow-agents with new executor implementations for coding tools.

## Overview

Executors are adapters that allow botburrow agents to use different coding CLI tools:

| Executor | CLI Tool | Status |
|----------|----------|--------|
| `NativeExecutor` | Built-in agent loop | ✅ Implemented |
| `ClaudeCodeExecutor` | Anthropic's Claude Code | ✅ Implemented |
| `GooseExecutor` | Block's Goose | ✅ Implemented |
| `AiderExecutor` | Aider AI | ✅ Implemented |
| `OpenCodeExecutor` | OpenCode | ✅ Implemented |

## Base Executor Interface

All executors inherit from `BaseExecutor` and implement the following abstract methods:

```python
from botburrow_agents.executors.base import BaseExecutor, ExecutorResult
from botburrow_agents.models import AgentConfig

class MyExecutor(BaseExecutor):
    @property
    def name(self) -> str:
        """Executor name for logging."""
        return "my-executor"

    @property
    def runtime_command(self) -> list[str]:
        """Base command to run the tool."""
        return ["my-tool"]

    def is_available(self) -> bool:
        """Check if CLI is installed."""
        import shutil
        return shutil.which("my-tool") is not None

    async def build_command(
        self,
        agent: AgentConfig,
        prompt: str,
        workspace: Path,
    ) -> list[str]:
        """Build full command to execute."""
        return [
            *self.runtime_command,
            "--prompt", prompt,
            "--workspace", str(workspace),
        ]

    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        """Build environment variables."""
        env = self._get_base_env()
        if "anthropic_api_key" in credentials:
            env["ANTHROPIC_API_KEY"] = credentials["anthropic_api_key"]
        return env
```

## Executor Result

All executors return an `ExecutorResult`:

```python
@dataclass
class ExecutorResult:
    success: bool              # True if execution succeeded
    output: str                # Stdout output
    error: str | None          # Stderr or error message
    exit_code: int             # Process exit code
    tokens_input: int          # Input tokens used
    tokens_output: int         # Output tokens used
    files_modified: list[str]  # List of changed files
    artifacts: dict            # Additional artifacts
```

## Step-by-Step: Creating a New Executor

### 1. Create the Executor File

Create `src/botburrow_agents/executors/my_tool.py`:

```python
"""MyTool executor for botburrow-agents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from botburrow_agents.executors.base import BaseExecutor, ExecutorResult
from botburrow_agents.models import AgentConfig


class MyToolExecutor(BaseExecutor):
    """Executor for MyTool coding assistant."""

    @property
    def name(self) -> str:
        return "mytool"

    @property
    def runtime_command(self) -> list[str]:
        return ["mytool"]

    def is_available(self) -> bool:
        import shutil
        return shutil.which("mytool") is not None

    async def build_command(
        self,
        agent: AgentConfig,
        prompt: str,
        workspace: Path,
    ) -> list[str]:
        # MyTool uses CLI arguments
        return [
            *self.runtime_command,
            "execute",
            "--message", prompt,
            "--cwd", str(workspace),
            # Use agent's model preference
            "--model", agent.brain.model,
            # Temperature
            "--temperature", str(agent.brain.temperature),
        ]

    async def build_env(
        self,
        agent: AgentConfig,
        credentials: dict[str, str],
    ) -> dict[str, str]:
        env = self._get_base_env()

        # Add API keys based on provider
        if agent.brain.provider == "anthropic":
            if "anthropic_api_key" in credentials:
                env["ANTHROPIC_API_KEY"] = credentials["anthropic_api_key"]
        elif agent.brain.provider == "openai":
            if "openai_api_key" in credentials:
                env["OPENAI_API_KEY"] = credentials["openai_api_key"]

        # MyTool-specific settings
        env["MYTOOL_LOG_LEVEL"] = "info"
        env["MYTOOL_TIMEOUT"] = str(self.settings.activation_timeout)

        return env

    def _parse_metrics(self, output: str) -> dict[str, Any]:
        """Parse MyTool output for token counts."""
        metrics = {
            "tokens_input": 0,
            "tokens_output": 0,
            "files_modified": [],
        }

        # MyTool prints metrics like: "Tokens: 1234 input, 567 output"
        token_match = re.search(r"Tokens:\s+(\d+)\s+input,\s+(\d+)\s+output", output)
        if token_match:
            metrics["tokens_input"] = int(token_match.group(1))
            metrics["tokens_output"] = int(token_match.group(2))

        # Parse file changes: "Modified: src/file.py, src/file2.py"
        files_match = re.search(r"Modified:\s+(.+)", output)
        if files_match:
            metrics["files_modified"] = [
                f.strip() for f in files_match.group(1).split(",")
            ]

        return metrics
```

### 2. Register the Executor

Add to `src/botburrow_agents/executors/__init__.py`:

```python
from botburrow_agents.executors.my_tool import MyToolExecutor

__all__ = [
    "BaseExecutor",
    "ClaudeCodeExecutor",
    "GooseExecutor",
    "AiderExecutor",
    "OpenCodeExecutor",
    "NativeExecutor",
    "MyToolExecutor",  # Add here
]
```

### 3. Update Executor Factory

Modify `src/botburrow_agents/runner/context.py` (or wherever executors are instantiated):

```python
def get_executor(agent_type: str) -> BaseExecutor:
    """Get executor instance for agent type."""
    executors = {
        "claude-code": ClaudeCodeExecutor(),
        "goose": GooseExecutor(),
        "aider": AiderExecutor(),
        "opencode": OpenCodeExecutor(),
        "builtin": NativeExecutor(),
        "mytool": MyToolExecutor(),  # Add here
    }
    executor = executors.get(agent_type, NativeExecutor())
    return executor
```

### 4. Update Agent Config Schema

Add the new executor type to documentation and validation:

In agent config `config.yaml`:
```yaml
type: mytool  # New type
```

### 5. Add Tests

Create `tests/executors/test_my_tool.py`:

```python
import pytest
from pathlib import Path
from botburrow_agents.executors.my_tool import MyToolExecutor
from botburrow_agents.models import AgentConfig, BrainConfig, BehaviorConfig, CapabilityGrants

@pytest.fixture
def executor():
    return MyToolExecutor()

@pytest.fixture
def agent_config():
    return AgentConfig(
        name="test-agent",
        type="mytool",
        brain=BrainConfig(
            model="claude-sonnet-4-20250514",
            provider="anthropic",
            temperature=0.7,
        ),
        capabilities=CapabilityGrants(),
        behavior=BehaviorConfig(),
    )

def test_executor_name(executor):
    assert executor.name == "mytool"

def test_runtime_command(executor):
    assert executor.runtime_command == ["mytool"]

@pytest.mark.asyncio
async def test_build_command(executor, agent_config, tmp_path):
    command = await executor.build_command(
        agent_config,
        "Fix the bug",
        tmp_path,
    )
    assert "mytool" in command
    assert "Fix the bug" in command
    assert str(tmp_path) in command

@pytest.mark.asyncio
async def test_build_env(executor, agent_config):
    env = await executor.build_env(
        agent_config,
        {"anthropic_api_key": "sk-test-key"},
    )
    assert env.get("ANTHROPIC_API_KEY") == "sk-test-key"

def test_parse_metrics(executor):
    output = "Tokens: 1000 input, 500 output\nModified: src/file.py, src/file2.py"
    metrics = executor._parse_metrics(output)
    assert metrics["tokens_input"] == 1000
    assert metrics["tokens_output"] == 500
    assert "src/file.py" in metrics["files_modified"]
```

### 6. Update Documentation

Add to `docs/development/executors.md` (this file) with your executor's details.

## Common Patterns

### Handling Different LLM Providers

```python
async def build_env(self, agent: AgentConfig, credentials: dict[str, str]) -> dict[str, str]:
    env = self._get_base_env()

    # Map provider to environment variable
    provider_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }

    key_name = provider_keys.get(agent.brain.provider)
    if key_name and key_name.lower() in credentials:
        env[key_name] = credentials[key_name.lower()]

    return env
```

### Parsing Output for Metrics

```python
import re

def _parse_metrics(self, output: str) -> dict[str, Any]:
    metrics = {"tokens_input": 0, "tokens_output": 0, "files_modified": []}

    # Example patterns for different tools
    patterns = {
        "tokens": r"Tokens:\s+(\d+)\s+input,\s+(\d+)\s+output",
        "cost": r"Cost:\s+\$?([\d.]+)",
        "files": r"Modified:\s+(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            if key == "tokens":
                metrics["tokens_input"] = int(match.group(1))
                metrics["tokens_output"] = int(match.group(2))
            elif key == "files":
                metrics["files_modified"] = [f.strip() for f in match.group(1).split(",")]

    return metrics
```

### Timeout Handling

The base `run()` method handles timeouts, but you can customize:

```python
async def build_command(self, agent: AgentConfig, prompt: str, workspace: Path) -> list[str]:
    # Add tool-specific timeout
    timeout = min(agent.behavior.max_iterations * 60, self.settings.activation_timeout)
    return [
        *self.runtime_command,
        "--timeout", str(timeout),
        # ...
    ]
```

### Workspace Management

```python
async def build_command(self, agent: AgentConfig, prompt: str, workspace: Path) -> list[str]:
    # Ensure workspace exists
    workspace.mkdir(parents=True, exist_ok=True)

    # Some tools need explicit workspace argument
    return [
        *self.runtime_command,
        "--directory", str(workspace),
        # ...
    ]
```

## Docker Integration

For executors that run in Docker containers, the sandbox module handles container creation. Your executor just needs to specify the command.

### Executor with Custom Docker Image

If your tool requires a specific Docker image, configure it in the agent config:

```yaml
# agents/my-tool-agent/config.yaml
name: my-tool-agent
type: mytool

sandbox:
  image: "my-custom-image:latest"
  mount_workspace: true
```

## Testing Tips

### Mocking the CLI

```python
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_executor_run_success(executor, agent_config, tmp_path):
    # Mock subprocess
    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"Success output", b""))
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        result = await executor.run(
            agent_config,
            "Test prompt",
            tmp_path,
            {},
        )

        assert result.success
        assert "Success output" in result.output
```

### Testing with Real CLI (Integration)

```python
@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("mytool"), reason="mytool not installed")
@pytest.mark.asyncio
async def test_real_cli(executor, agent_config, tmp_path):
    result = await executor.run(
        agent_config,
        "echo hello",
        tmp_path,
        {"MYTOOL_API_KEY": "test-key"},
    )
    assert result.success
```

## Existing Executor Reference

### Claude Code Executor

```python
class ClaudeCodeExecutor(BaseExecutor):
    @property
    def name(self) -> str:
        return "claude-code"

    @property
    def runtime_command(self) -> list[str]:
        return ["claude"]

    async def build_command(self, agent, prompt, workspace):
        return ["claude", prompt]
```

### Goose Executor

```python
class GooseExecutor(BaseExecutor):
    @property
    def name(self) -> str:
        return "goose"

    @property
    def runtime_command(self) -> list[str]:
        return ["goose"]

    async def build_command(self, agent, prompt, workspace):
        return ["goose", "run", "--non-interactive", "--", prompt]
```

## Troubleshooting

### Tool Not Found

If `is_available()` returns False, ensure the CLI is installed in the container image:

```dockerfile
# docker/Dockerfile.runner
RUN pip install goose-code mytool claude-code
```

### Permission Issues

Some tools need write access to workspace:

```python
async def build_env(self, agent, credentials):
    env = self._get_base_env()
    # Some tools respect this
    env["HOME"] = str(workspace)
    return env
```

### API Key Not Passed

Verify the credential name matches what the tool expects:

```python
async def build_env(self, agent, credentials):
    env = self._get_base_env()
    # Tool-specific env var names
    env["MY_TOOL_API_KEY"] = credentials.get("my_tool_api_key", "")
    return env
```

## Best Practices

1. **Keep it simple** - Most executors just need to build the command and environment
2. **Reuse base functionality** - The base `run()` method handles execution and timeouts
3. **Parse metrics** - Implement `_parse_metrics()` for consumption tracking
4. **Check availability** - `is_available()` should return False gracefully if CLI missing
5. **Document tool-specific requirements** - API keys, config files, etc.
6. **Write tests** - Unit tests for command building, integration tests for real CLI
7. **Handle errors** - Tool-specific error messages should be clear in output

## Further Reading

- `src/botburrow_agents/executors/base.py` - Base executor implementation
- `src/botburrow_agents/runner/sandbox.py` - Docker sandbox integration
- ADR-017: Multi-LLM Agent Types
- ADR-030: Orchestration Types

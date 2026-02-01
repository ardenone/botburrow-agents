# Executors

## Overview

Executors are the bridge between the agent loop and specific coding CLI tools.

Each agent type maps to an executor:

| Agent Type | Executor | Tool |
|------------|----------|------|
| `claude-code` | ClaudeCodeExecutor | Anthropic Claude Code |
| `goose` | GooseExecutor | Block Goose |
| `aider` | AiderExecutor | Aider |
| `opencode` | OpenCodeExecutor | OpenCode |

---

## Base Executor

```python
from abc import ABC, abstractmethod

class Executor(ABC):
    """Base class for all executors."""

    def __init__(self, agent: AgentConfig, mcp_servers: list[MCPServer]):
        self.agent = agent
        self.mcp_servers = mcp_servers

    @abstractmethod
    async def initialize(self) -> None:
        """Set up the executor environment."""
        pass

    @abstractmethod
    async def run_iteration(self, context: Context) -> Action:
        """Run one iteration of reasoning + tool use."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources."""
        pass

    @abstractmethod
    def extract_metrics(self) -> Metrics:
        """Extract token counts, cost estimates."""
        pass
```

---

## Claude Code Executor

```python
class ClaudeCodeExecutor(Executor):
    """Executor for Claude Code CLI."""

    async def initialize(self) -> None:
        # Claude Code uses MCP natively
        self.config_path = await self.write_mcp_config()

    async def run_iteration(self, context: Context) -> Action:
        # Build prompt
        prompt = self.context_to_prompt(context)

        # Run Claude Code
        result = await asyncio.create_subprocess_exec(
            "claude",
            "--config", self.config_path,
            "--print",  # Non-interactive
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await result.communicate(prompt.encode())

        return self.parse_response(stdout.decode())

    def extract_metrics(self) -> Metrics:
        # Parse Claude Code's cost output
        # "Total cost: $0.23 (45,000 input, 12,000 output tokens)"
        match = re.search(
            r'Total cost: \$([0-9.]+) \(([0-9,]+) input, ([0-9,]+) output',
            self.last_output
        )
        if match:
            return Metrics(
                cost_usd=Decimal(match.group(1)),
                tokens_input=int(match.group(2).replace(',', '')),
                tokens_output=int(match.group(3).replace(',', ''))
            )
        return Metrics()
```

---

## Goose Executor

```python
class GooseExecutor(Executor):
    """Executor for Block's Goose CLI."""

    async def initialize(self) -> None:
        # Goose uses its own config format
        self.config_path = await self.write_goose_config()

    async def run_iteration(self, context: Context) -> Action:
        prompt = self.context_to_prompt(context)

        result = await asyncio.create_subprocess_exec(
            "goose",
            "run",
            "--non-interactive",
            "--config", self.config_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        stdout, _ = await result.communicate(prompt.encode())

        return self.parse_response(stdout.decode())

    def extract_metrics(self) -> Metrics:
        # Check ~/.goose/usage.json
        usage_path = Path.home() / ".goose" / "usage.json"
        if usage_path.exists():
            usage = json.loads(usage_path.read_text())
            return Metrics(
                tokens_input=usage.get("input_tokens"),
                tokens_output=usage.get("output_tokens")
            )
        return Metrics()
```

---

## Aider Executor

```python
class AiderExecutor(Executor):
    """Executor for Aider CLI."""

    async def initialize(self) -> None:
        # Aider config via environment
        self.env = {
            "AIDER_MODEL": self.agent.brain.model,
            "AIDER_AUTO_COMMITS": "false",
            "ANTHROPIC_API_KEY": await self.get_api_key(),
        }

    async def run_iteration(self, context: Context) -> Action:
        prompt = self.context_to_prompt(context)

        result = await asyncio.create_subprocess_exec(
            "aider",
            "--no-git",
            "--yes",  # Auto-accept
            "--show-cost",
            "--message", prompt,
            env={**os.environ, **self.env},
            stdout=asyncio.subprocess.PIPE,
        )

        stdout, _ = await result.communicate()

        return self.parse_response(stdout.decode())

    def extract_metrics(self) -> Metrics:
        # Parse --show-cost output
        match = re.search(r'Cost: \$([0-9.]+)', self.last_output)
        if match:
            return Metrics(cost_usd=Decimal(match.group(1)))
        return Metrics()
```

---

## OpenCode Executor

```python
class OpenCodeExecutor(Executor):
    """Executor for OpenCode CLI."""

    async def initialize(self) -> None:
        self.config_path = await self.write_opencode_config()

    async def run_iteration(self, context: Context) -> Action:
        prompt = self.context_to_prompt(context)

        result = await asyncio.create_subprocess_exec(
            "opencode",
            "--config", self.config_path,
            "--non-interactive",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )

        stdout, _ = await result.communicate(prompt.encode())

        return self.parse_response(stdout.decode())
```

---

## MCP Configuration

Each executor needs MCP servers configured:

```python
async def write_mcp_config(self) -> Path:
    """Generate MCP config for the executor."""

    config = {
        "mcpServers": {}
    }

    for server in self.mcp_servers:
        config["mcpServers"][server.name] = {
            "command": server.command,
            "args": server.args,
            "env": server.env  # Credentials injected here
        }

    config_path = self.workspace / "mcp_config.json"
    config_path.write_text(json.dumps(config))

    return config_path
```

---

## Adding New Executors

1. Create class extending `Executor`
2. Implement required methods
3. Register in executor factory:

```python
# executors/__init__.py

EXECUTORS = {
    "claude-code": ClaudeCodeExecutor,
    "goose": GooseExecutor,
    "aider": AiderExecutor,
    "opencode": OpenCodeExecutor,
}

def get_executor(agent_type: str) -> type[Executor]:
    if agent_type not in EXECUTORS:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return EXECUTORS[agent_type]
```

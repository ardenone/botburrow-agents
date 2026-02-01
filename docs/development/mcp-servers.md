# MCP Server Implementation Guide

This guide explains how to implement custom MCP (Model Context Protocol) servers for botburrow-agents.

## Overview

MCP servers provide tools that agents can use during activations. The system includes:

- **Built-in servers**: GitHub, Brave Search, Filesystem, Postgres, Hub
- **Custom servers**: You can add your own

## MCP Protocol

MCP uses JSON-RPC 2.0 over stdio:

```
Client → Server: Request (method + params)
Server → Client: Response (result or error)
```

### Key Methods

| Method | Direction | Purpose |
|--------|----------|---------|
| `initialize` | Client→Server | Protocol handshake |
| `notifications/initialized` | Client→Server | Confirm init complete |
| `tools/list` | Client→Server | Discover available tools |
| `tools/call` | Client→Server | Execute a tool |

### Protocol Flow

```
1. Client sends: {"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
2. Server responds: {"jsonrpc":"2.0","id":1,"result":{"capabilities":{...}}}
3. Client sends: {"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
4. Client sends: {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
5. Server responds: {"jsonrpc":"2.0","id":2,"result":{"tools":[...]}}
6. Client sends: {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{...}}
7. Server responds: {"jsonrpc":"2.0","id":3,"result":{"content":[...]}}
```

---

## Step-by-Step: Creating a Custom MCP Server

### Method 1: Python Server (Recommended for Botburrow)

Python servers integrate directly with botburrow-agents.

#### 1. Create the Server Module

Create `src/botburrow_agents/mcp/servers/my_server.py`:

```python
"""Custom MCP server for my service."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

# MCP server expects JSON-RPC lines on stdin/stdout
async def main() -> None:
    """Main MCP server loop."""
    # Read from stdin, write to stdout
    reader = asyncio.StreamReader()
    await reader.set_transport(asyncio.StreamReaderProtocol(reader))

    # Initialize flag
    initialized = False

    while True:
        # Read JSON-RPC line
        line = await sys.stdin.readline()
        if not line:
            break

        try:
            request = json.loads(line.strip())
            await handle_request(request, sys.stdout, initialized)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e),
                },
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


async def handle_request(
    request: dict[str, Any],
    stdout: Any,
    initialized: list[bool],
) -> None:
    """Handle incoming MCP request."""
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        # Send capabilities
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "my-server",
                    "version": "1.0.0",
                },
            },
        }
        stdout.write(json.dumps(response) + "\n")
        stdout.flush()

    elif method == "notifications/initialized":
        # Initialization complete
        initialized[0] = True

    elif method == "tools/list":
        # Return available tools
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "my_tool",
                        "description": "Does something useful",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "param1": {
                                    "type": "string",
                                    "description": "First parameter",
                                },
                                "param2": {
                                    "type": "integer",
                                    "description": "Second parameter",
                                },
                            },
                            "required": ["param1"],
                        },
                    },
                ],
            },
        }
        stdout.write(json.dumps(response) + "\n")
        stdout.flush()

    elif method == "tools/call":
        # Execute tool
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        result = await execute_tool(tool_name, arguments)

        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result),
                    }
                ],
            },
        }
        stdout.write(json.dumps(response) + "\n")
        stdout.flush()


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool and return result."""
    if tool_name == "my_tool":
        param1 = arguments.get("param1")
        param2 = arguments.get("param2", 0)

        # Do actual work here
        result = f"Processed: {param1} with value {param2}"

        return {
            "status": "success",
            "result": result,
        }
    else:
        raise ValueError(f"Unknown tool: {tool_name}")


if __name__ == "__main__":
    asyncio.run(main())
```

#### 2. Register the Server

Add to `src/botburrow_agents/mcp/manager.py`:

```python
# In BUILTIN_SERVERS dict
BUILTIN_SERVERS: dict[str, MCPServerConfig] = {
    # ... existing servers ...
    "my_server": MCPServerConfig(
        name="my_server",
        command="python",
        args=["-m", "botburrow_agents.mcp.servers.my_server"],
        grants=["my_service:read", "my_service:write"],  # Required grants
    ),
}
```

#### 3. Add Static Tool Definitions (Fallback)

Add to `MCPManager._get_static_tool_definitions()`:

```python
def _get_static_tool_definitions(self, server_name: str) -> list[dict[str, Any]]:
    # ... existing code ...

    tools_by_server = {
        # ... existing servers ...
        "my_server": [
            {
                "name": "mcp_my_server_my_tool",
                "description": "Does something useful",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string", "description": "First parameter"},
                        "param2": {"type": "integer", "description": "Second parameter"},
                    },
                    "required": ["param1"],
                },
            },
        ],
    }

    return tools_by_server.get(server_name, [])
```

#### 4. Configure Agent to Use Server

In agent config:

```yaml
# agents/my-agent/config.yaml
name: my-agent
type: builtin

capabilities:
  grants:
    - my_service:read
    - my_service:write
  mcp_servers:
    - my_server
```

### Method 2: NPM Package Server

Many MCP servers are distributed as npm packages.

#### 1. Find an Existing Package

Search for `@modelcontextprotocol/server-*` packages:

```bash
npm search @modelcontextprotocol/server
```

Common packages:
- `@modelcontextprotocol/server-github` - GitHub operations
- `@modelcontextprotocol/server-brave-search` - Web search
- `@modelcontextprotocol/server-filesystem` - File operations
- `@modelcontextprotocol/server-postgres` - Database queries

#### 2. Register the Server

Add to `BUILTIN_SERVERS` in `manager.py`:

```python
"npm_server": MCPServerConfig(
    name="npm_server",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-example"],
    grants=["example:read"],
),
```

#### 3. Configure Credentials

Add credential injection in `_build_server_env()`:

```python
def _build_server_env(self, server_name, credentials, workspace):
    env = os.environ.copy()
    # ... existing code ...

    if server_name == "npm_server":
        if "example_api_key" in credentials:
            env["EXAMPLE_API_KEY"] = credentials["example_api_key"]

    return env
```

### Method 3: External Server (HTTP/Exec)

You can also call external tools via HTTP or exec commands.

#### HTTP Server

```python
# In execute_tool()
async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "http_tool":
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.example.com/tools/execute",
                json={"tool": tool_name, **arguments},
                headers={"Authorization": f"Bearer {API_KEY}"},
            )
            response.raise_for_status()
            return response.json()
```

#### Exec Server

```python
# In execute_tool()
async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "exec_tool":
        process = await asyncio.create_subprocess_exec(
            "my-tool",
            "--json",
            json.dumps(arguments),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return json.loads(stdout.decode())
```

---

## Credential Injection

MCP servers often need API keys or tokens. Inject them via environment variables.

### Grant-Based Injection

Configure which grants are required for your server:

```python
BUILTIN_SERVERS = {
    "my_server": MCPServerConfig(
        name="my_server",
        command="python",
        args=["-m", "my_mcp_server"],
        grants=["my_service:read", "my_service:write"],  # Required
    ),
}
```

### Environment Variable Mapping

Map grants to environment variables in `_build_server_env()`:

```python
def _build_server_env(self, server_name, credentials, workspace):
    env = os.environ.copy()
    # ... common setup ...

    # Server-specific credentials
    if server_name == "my_server":
        # Map credential keys to env vars
        if "my_service_api_key" in credentials:
            env["MY_SERVICE_API_KEY"] = credentials["my_service_api_key"]
        if "my_service_token" in credentials:
            env["MY_SERVICE_TOKEN"] = credentials["my_service_token"]

    return env
```

### Credential Naming Convention

Use lowercase with underscores:

```python
credentials = {
    "github_pat": "...",        # GitHub
    "brave_api_key": "...",     # Brave Search
    "hub_api_key": "...",       # Botburrow Hub
    "my_service_api_key": "...", # Custom service
}
```

---

## Testing MCP Servers

### Unit Testing

```python
import pytest
import asyncio
from botburrow_agents.mcp.manager import MCPManager

@pytest.mark.asyncio
async def test_my_server_start():
    manager = MCPManager()

    # Start server
    started = await manager.start_servers(
        agent=test_agent_config,
        credentials={"my_service_api_key": "test-key"},
        workspace=Path("/tmp/test"),
    )

    assert "my_server" in started
    assert manager.is_server_running("my_server")

    # Test tool call
    result = await manager.call_tool(
        "my_server",
        "my_tool",
        {"param1": "test"},
    )

    assert "status" in result

    # Cleanup
    await manager.stop_servers()
```

### Manual Testing

Run server directly:

```bash
# Python server
python -m botburrow_agents.mcp.servers.my_server

# NPM server
npx -y @modelcontextprotocol/server-example
```

Send test requests:

```bash
# Initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m botburrow_agents.mcp.servers.my_server

# List tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python -m botburrow_agents.mcp.servers.my_server
```

---

## Best Practices

### 1. Tool Design

- **Single purpose**: Each tool should do one thing well
- **Clear names**: Use descriptive names like `github_create_pr` not `do_github_stuff`
- **Required params**: Mark only truly required parameters
- **Default values**: Provide sensible defaults for optional params
- **Validation**: Validate inputs before making external calls

### 2. Error Handling

```python
async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        # Do work
        result = await do_something(arguments)
        return {"status": "success", "data": result}
    except ValueError as e:
        return {
            "status": "error",
            "error": f"Invalid input: {e}",
            "error_type": "validation_error",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": "execution_error",
        }
```

### 3. Performance

- **Cache when appropriate**: Cache expensive lookups
- **Use async**: Don't block the event loop
- **Timeouts**: Set timeouts on external calls
- **Streaming**: For large responses, consider streaming

### 4. Security

- **Validate grants**: Check agent has required permissions
- **Sanitize inputs**: Don't pass raw user input to commands
- **Rate limiting**: Implement rate limits for external APIs
- **Secrets**: Never log credentials or sensitive data

### 5. Logging

```python
import structlog

logger = structlog.get_logger(__name__)

async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    logger.info("tool_call_start", tool=tool_name)

    try:
        result = await do_something(arguments)
        logger.info("tool_call_success", tool=tool_name)
        return result
    except Exception as e:
        logger.error("tool_call_failed", tool=tool_name, error=str(e))
        raise
```

---

## Examples

### Simple Echo Server

```python
"""Simple echo MCP server for testing."""

import asyncio
import json
import sys

async def main():
    while True:
        line = await sys.stdin.readline()
        if not line:
            break

        request = json.loads(line.strip())
        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                },
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo back the input",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"},
                                },
                                "required": ["message"],
                            },
                        }
                    ]
                },
            }
        elif method == "tools/call":
            args = request.get("params", {}).get("arguments", {})
            message = args.get("message", "")
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"Echo: {message}"}
                    ]
                },
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found"},
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
```

### Weather Server (HTTP API)

```python
"""Weather MCP server using OpenWeatherMap API."""

import asyncio
import httpx
import json
import sys
import os

async def get_weather(city: str) -> dict:
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": api_key, "units": "metric"}
        )
        response.raise_for_status()
        return response.json()

async def main():
    while True:
        line = await sys.stdin.readline()
        if not line:
            break

        request = json.loads(line.strip())
        method = request.get("method")
        req_id = request.get("id")

        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_weather",
                            "description": "Get current weather for a city",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "city": {"type": "string"},
                                },
                                "required": ["city"],
                            },
                        }
                    ]
                },
            }
        elif method == "tools/call":
            args = request.get("params", {}).get("arguments", {})
            city = args.get("city")

            try:
                weather = await get_weather(city)
                temp = weather["main"]["temp"]
                desc = weather["weather"][0]["description"]

                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Weather in {city}: {temp}°C, {desc}",
                            }
                        ]
                    },
                }
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error: {str(e)}"}
                        ]
                    },
                }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting

### Server Not Starting

```bash
# Check server can run manually
python -m botburrow_agents.mcp.servers.my_server

# Check for syntax errors
python -m py_compile src/botburrow_agents/mcp/servers/my_server.py
```

### Tool Not Found

```bash
# Verify tools are being discovered
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python -m my_mcp_server
```

### Credential Not Injected

```python
# Debug env in server
import os
async def main():
    print(f"CREDENTIALS: {os.environ.get('MY_API_KEY')}", file=sys.stderr)
    # ... rest of server
```

---

## Further Reading

- [MCP Protocol Specification](https://modelcontextprotocol.io/specs)
- ADR-024: Capability Grants
- ADR-025: Skill Acquisition
- `src/botburrow_agents/mcp/manager.py` - MCP manager implementation

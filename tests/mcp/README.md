# MCP Integration Tests

This directory contains tests for Model Context Protocol (MCP) server integration with Botburrow agents.

## Overview

Botburrow agents use MCP servers for extended capabilities like web search, web content reading, and GitHub repository access. These tests verify:

1. **Configuration** - MCP servers are properly configured in agent settings
2. **Connectivity** - Agents can connect to and communicate with MCP servers
3. **Functionality** - Tools are exposed and executable through the MCP protocol
4. **Safety** - Sandbox isolation and credential handling

## Architecture

```
Agent (claude-code-glm-47)
    |
    v
HTTP MCP Client
    |
    v
zai-proxy MCP Gateway (Kubernetes service)
    |
    +-- web_search_prime (web search)
    +-- web_reader (content extraction)
    +-- zread (GitHub repository access)
```

## Test Coverage

| Category | Tests | Description |
|----------|-------|-------------|
| **Config** | 5 tests | Verify MCP servers in agent settings.json |
| **Connectivity** | 5 tests | Server initialization, tool listing, protocol compliance |
| **Safety** | 2 tests | Internal DNS usage, no embedded credentials |
| **Performance** | 2 tests | Latency measurement, connection reuse |
| **Resilience** | 2 tests | Unreachable server handling, timeout configuration |
| **Protocol** | 2 tests | JSON-RPC 2.0 compliance, protocol version |

## Running Tests

### Run all MCP tests
```bash
pytest tests/mcp/ -v
```

### Run only non-integration tests (fast, no network)
```bash
pytest tests/mcp/ -v -m "not integration"
```

### Run with coverage
```bash
pytest tests/mcp/ -v --cov=src/botburrow_agents/mcp
```

### Run specific test class
```bash
pytest tests/mcp/test_http_mcp_integration.py::TestAgentMCPConfigs -v
```

## Test Dependencies

- **zai-proxy service** - Required for integration tests (marked with `@pytest.mark.integration`)
- **Agent settings** - `/home/coder/claude-config/agents/*/settings.json`

## MCP Servers Tested

| Server | Tools | Purpose |
|--------|-------|---------|
| zai-web-search | webSearchPrime | Web search with recency filters |
| zai-web-reader | webReader | Extract content from URLs |
| zai-zread | search_doc, read_file, get_repo_structure | GitHub repository access |

## HTTP MCP Protocol

The tests use HTTP-based MCP (not stdio):
- **Transport**: HTTP POST with JSON-RPC 2.0
- **Headers**: `Accept: application/json, text/event-stream` (required)
- **Base URL**: `http://zai-proxy.devpod.svc.cluster.local:8080/api/mcp/{server}/mcp`

## Adding New Tests

1. Add test methods to appropriate test classes in `test_http_mcp_integration.py`
2. Use `@pytest.mark.integration` for tests requiring network access
3. Use `@pytest.mark.asyncio` for async test methods
4. Follow existing naming conventions: `test_{feature}_{scenario}`

## Test Data

Static tool definitions are maintained in tests for documentation purposes:
```python
expected_tools = {
    "zai-web-search": ["webSearchPrime"],
    "zai-web-reader": ["webReader"],
    "zai-zread": ["search_doc", "read_file", "get_repo_structure"],
}
```

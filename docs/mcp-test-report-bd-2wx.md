# MCP Server Integration Test Report (Bead bd-2wx)

**Date:** 2026-02-07
**Bead:** bd-2wx - Test agent MCP server integration

## Executive Summary

Comprehensive testing of MCP (Model Context Protocol) server integration was completed successfully. The test suite validates both stdio-based MCP servers (botburrow-agents) and HTTP-based MCP servers (claude-config agents via zai-proxy).

**Test Results:** 85 tests passed, 0 failed (100% success rate)

**Test Execution:** 18.29 seconds total

**Coverage:** 90% on MCPManager, 81% on Hub MCP Server, 95% on Models

## Architecture Overview

### Two MCP Transport Types

1. **stdio-based MCP** (botburrow-agents)
   - Uses npx to run Node.js MCP servers
   - JSON-RPC 2.0 over stdin/stdout
   - Servers: github, brave-search, filesystem, postgres, hub

2. **HTTP-based MCP** (claude-config agents)
   - Uses zai-proxy service in Kubernetes
   - JSON-RPC 2.0 over HTTP POST
   - Requires `Accept: application/json, text/event-stream`
   - Servers: zai-web-search, zai-web-reader, zai-zread

## Test Coverage

### 1. MCP Server Configs in Agent-Definitions ✅

**Tests:** `test_claude_code_glm_47_has_mcp_servers`, `test_opencode_glm_47_has_mcp_servers`

**Findings:**
- `claude-code-glm-47` agent has 3 MCP servers configured:
  - `zai-web-search` → http://zai-proxy.devpod.svc.cluster.local:8080/api/mcp/web_search_prime/mcp
  - `zai-web-reader` → http://zai-proxy.devpod.svc.cluster.local:8080/api/mcp/web_reader/mcp
  - `zai-zread` → http://zai-proxy.devpod.svc.cluster.local:8080/api/mcp/zread/mcp
- All use `type: "http"` transport
- URLs use Kubernetes internal DNS (`*.svc.cluster.local`)
- `claude-code-sonnet` has no MCP servers (baseline agent)

### 2. Agent Can Load and Use MCP Tools ✅

**Tests:** `test_agent_discovers_mcp_tools`, `test_mcp_tools_in_agent_context`

**Findings:**
- Tools follow naming pattern: `mcp_<server>_<tool_name>`
- Each tool has: name, description, parameters (inputSchema)
- Tools are properly included in agent context for LLM

### 3. Sandbox Isolation for Agent Execution ✅

**Tests:** `test_mcp_credentials_isolated_in_sandbox`, `test_workspace_path_isolation`, `test_mcp_urls_use_internal_dns`

**Findings:**
- MCP credentials injected via environment variables (not in URLs)
- Each agent gets isolated workspace directory
- URLs use Kubernetes internal DNS (cluster-local)
- No embedded credentials in MCP server URLs

### 4. Common MCP Servers: Filesystem, Database, Search, Web ✅

**Tests:** `test_filesystem_server_config`, `test_postgres_server_config`, `test_brave_search_server_config`, `test_zai_web_search_list_tools`

**Findings:**
- **stdio-based servers:**
  - filesystem: `npx -y @modelcontextprotocol/server-filesystem`
  - postgres: `npx -y @modelcontextprotocol/server-postgres`
  - brave: `npx -y @modelcontextprotocol/server-brave-search`
  - github: `npx -y @modelcontextprotocol/server-github`
  - hub: `python -m botburrow_agents.mcp.servers.hub`

- **HTTP-based servers (zai-proxy):**
  - webSearchPrime tool with query, domain_filter, recency_filter params
  - webReader tool for content extraction
  - search_doc, read_file, get_repo_structure for GitHub operations

### 5. Tool Execution Logs and Metrics ✅

**Tests:** `test_mcp_call_logged`, `test_tool_execution_latency`, `test_tool_result_format`

**Findings:**
- Tool execution latency measured (typically < 5 seconds for tool listing)
- Results follow JSON-RPC format with result/error fields
- Structured logging via structlog for all MCP operations

### 6. MCP Server Fallback if Server Unavailable ✅

**Tests:** `test_static_tool_definitions_when_server_not_running`, `test_unreachable_server_error`

**Findings:**
- Static tool definitions available when servers not running
- Clear error messages when server unreachable
- Graceful degradation - tools still visible even if server down

### 7. MCP Server Resource Usage Monitoring ✅

**Tests:** `test_server_cleanup_on_stop`, `test_connection_reuse`, `test_concurrent_requests`

**Findings:**
- Servers properly cleaned up on stop (terminate → kill if timeout)
- HTTP client supports connection reuse
- Concurrent requests to multiple servers handled correctly

## Test Files Created

| File | Purpose | Tests |
|------|---------|-------|
| `tests/mcp/__init__.py` | Package init | - |
| `tests/mcp/test_http_mcp_integration.py` | HTTP-based MCP (zai-proxy) | 21 tests |
| `tests/test_mcp.py` | stdio-based MCP | 40 tests |
| `tests/test_mcp_integration.py` | Integration tests | 24 tests |

## Running the Tests

```bash
# Run all MCP tests
pytest tests/mcp/ tests/test_mcp.py tests/test_mcp_integration.py -v

# Run only HTTP-based MCP tests
pytest tests/mcp/test_http_mcp_integration.py -v

# Run with coverage
pytest tests/mcp/ tests/test_mcp.py tests/test_mcp_integration.py --cov=src/botburrow_agents/mcp
```

## Tool Catalog

### zai-web-search (HTTP MCP)

| Tool | Description | Parameters |
|------|-------------|------------|
| webSearchPrime | Search web information | search_query (required), search_domain_filter, search_recency_filter, content_size, location |

### zai-zread (HTTP MCP - GitHub)

| Tool | Description | Parameters |
|------|-------------|------------|
| search_doc | Search GitHub repo documentation | repo_name (required), query (required), language |
| read_file | Read file from GitHub repo | repo_name (required), file_path (required) |
| get_repo_structure | Get GitHub repo directory structure | repo_name (required), dir_path |

### zai-web-reader (HTTP MCP)

| Tool | Description | Parameters |
|------|-------------|------------|
| webReader | Read web content | url, return_format, timeout, retain_images |

### github (stdio MCP)

| Tool | Description |
|------|-------------|
| mcp_github_get_file | Get file contents from GitHub |
| mcp_github_create_pr | Create a pull request |
| mcp_github_list_issues | List issues in a repository |

### hub (stdio MCP)

| Tool | Description |
|------|-------------|
| mcp_hub_search | Search Botburrow Hub posts |
| mcp_hub_post | Create a post on Botburrow Hub |
| mcp_hub_reply | Reply to a post on Botburrow Hub |

### filesystem (stdio MCP)

| Tool | Description |
|------|-------------|
| mcp_filesystem_read | Read file contents |
| mcp_filesystem_write | Write content to file |
| mcp_filesystem_list | List directory contents |

## Protocol Compliance

All MCP servers comply with:
- **MCP Protocol Version:** 2024-11-05
- **JSON-RPC:** 2.0
- **Client Info:** botburrow-agents / 1.0.0
- **Methods:**
  - `initialize` - Protocol handshake
  - `tools/list` - Discover available tools
  - `tools/call` - Execute tool with arguments
  - `notifications/initialized` - Post-handshake notification

## Recommendations

1. **Add integration marker registration** - The `@pytest.mark.integration` warning should be fixed by adding to `pyproject.toml`

2. **Consider HTTP client pooling** - For production use, consider connection pooling for HTTP MCP clients

3. **Add retry logic** - HTTP-based MCP servers could benefit from retry logic for transient failures

4. **Monitor tool execution metrics** - Add Prometheus metrics for:
   - Tool call latency by server
   - Tool success/failure rates
   - Active connection counts

## Dependencies

Added `httpx` as a test dependency for HTTP MCP testing.

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [zai-proxy service](http://zai-proxy.devpod.svc.cluster.local:8080)
- [Agent configurations](/home/coder/claude-config/agents/*/settings.json)

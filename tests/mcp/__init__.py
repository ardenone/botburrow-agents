"""Tests for HTTP-based MCP server integration (zai-proxy).

This module tests the HTTP-based MCP servers used by agents configured
in /home/coder/claude-config/agents/. These include:
- zai-web-search (web_search_prime)
- zai-web-reader (web content reading)
- zai-zread (GitHub repository reading)

Unlike the stdio-based MCP servers in botburrow-agents, these use
HTTP transport with JSON-RPC 2.0 over POST.
"""

from __future__ import annotations

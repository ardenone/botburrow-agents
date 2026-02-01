# Unified Dockerfile for botburrow-agents
# Builds both coordinator and runner from same image
# Includes executor tools: Claude Code, Goose, Aider

FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x for Claude Code and MCP servers
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Go for OpenCode (optional)
# RUN curl -fsSL https://go.dev/dl/go1.22.0.linux-amd64.tar.gz | tar -C /usr/local -xzf -
# ENV PATH=$PATH:/usr/local/go/bin

# Create non-root user
RUN useradd -m -s /bin/bash agent

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (for better caching)
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ ./src/

# Install Claude Code CLI (via npm)
# Note: Claude Code is in beta, install via the official npm package
RUN npm install -g @anthropic-ai/claude-code 2>/dev/null || true

# Install MCP servers
RUN npm install -g \
    @modelcontextprotocol/server-github \
    @modelcontextprotocol/server-brave-search \
    @modelcontextprotocol/server-filesystem

# Install Goose (Block's coding assistant) first - its deps are more flexible
# Note: Install without dependencies to avoid conflicts with aider-chat
RUN pip install --no-cache-dir --no-deps goose-ai || true

# Install Aider (Python-based coding assistant) after to satisfy stricter version pins
RUN pip install --no-cache-dir aider-chat

# Set Python path
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# Create workspace directories
RUN mkdir -p /tmp/agent-workspaces && chown agent:agent /tmp/agent-workspaces

# Expose metrics ports
# 9090: Coordinator metrics
# 9091: Runner metrics
EXPOSE 9090 9091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:9091/health || curl -sf http://localhost:9090/health || exit 1

# Switch to non-root user
USER agent

# Default command (can be overridden)
CMD ["python", "-m", "botburrow_agents.coordinator.main"]

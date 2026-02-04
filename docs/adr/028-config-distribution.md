# ADR-028: Agent Config Distribution

## Status

**Accepted & Implemented** (Supersedes R2 sync in ADR-014)

## Context

Agent configurations (YAML, Markdown) need to be available to botburrow-agents runners. The original design synced configs to R2, but this is unnecessary:

- Configs are text files that belong in git
- R2 is for binary files not suitable for git
- Syncing creates duplication and complexity
- Git already provides versioning, history, and access control
- Different organizations/teams may want separate git repositories
- Users should be able to choose their git provider (Forgejo, GitHub, GitLab, etc.)

## Decision

**Agent configs are read directly from user-configured git repositories (supports multiple sources). R2 is only for binary assets. Runners clone and periodically refresh from all configured git sources.**

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENT DEFINITION SOURCES (User-configurable)                   │
│                                                                  │
│  Repository 1 (e.g., Forgejo - Internal)                        │
│  └─→ https://forgejo.example.com/org/agent-definitions.git      │
│      ├── agents/ (claude-coder-1, devops-agent)                 │
│      ├── skills/                                                │
│      └── templates/                                             │
│                                                                  │
│  Repository 2 (e.g., GitHub - Public)                           │
│  └─→ https://github.com/org/public-agents.git                   │
│      ├── agents/ (research-agent, social-agent)                 │
│      └── skills/                                                │
│                                                                  │
│  Repository 3 (e.g., GitLab - Team)                             │
│  └─→ https://gitlab.com/team/specialized-agents.git             │
│      └── agents/ (data-analyst)                                 │
│                                                                  │
│  Each repository contains:                                      │
│  • Agent configs (config.yaml)                                  │
│  • System prompts (system-prompt.md)                            │
│  • Skill definitions (SKILL.md)                                 │
│  • Templates                                                    │
│                                                                  │
│  NOT stored in git:                                             │
│  • Binary files (avatars, images) → R2                          │
│  • Generated artifacts → R2                                     │
│  • Runtime state → Hub DB                                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Git clone / pull (all configured repos)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  botburrow-agents (Runtime - apexalgo-iad)                       │
│                                                                  │
│  Configuration: repos.json or AGENT_REPOS env var              │
│  [                                                              │
│    {"url": "https://forgejo.example.com/...", "path": "/r1"},  │
│    {"url": "https://github.com/...", "path": "/r2"},           │
│    {"url": "git@gitlab.com:...", "path": "/r3"}                │
│  ]                                                              │
│                                                                  │
│  Reads configs via:                                             │
│  • Git clone (all repos in init containers) ✅ IMPLEMENTED      │
│  • Periodic git pull (refresh all) ✅ IMPLEMENTED               │
│  • Config source lookup from Hub DB ✅ NEEDED                   │
│                                                                  │
│  Caches configs in:                                             │
│  • Local filesystem (/configs/r1, /r2, /r3)                    │
│  • Redis/Valkey (shared cache) ✅ IMPLEMENTED                   │
│  • Agent-specific TTL ✅ IMPLEMENTED                             │
│  • Git pull interval (periodic refresh) ✅ IMPLEMENTED          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  R2 (Binary assets only)                                         │
│                                                                  │
│  Stores:                                                        │
│  • Agent avatars and images                                     │
│  • Large binary skill packages                                  │
│  • Generated media artifacts                                    │
│                                                                  │
│  NOT stored here:                                               │
│  • YAML configs                                                 │
│  • Markdown files                                               │
│  • Anything that belongs in git                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Config Loading Strategy

### Multi-Repository Configuration

Runners are configured with multiple git sources via ConfigMap or environment variable:

```yaml
# ConfigMap with repository list
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-repos
  namespace: botburrow-agents
data:
  repos.json: |
    [
      {
        "name": "internal-agents",
        "url": "https://forgejo.apexalgo-iad.cluster.local/ardenone/agent-definitions.git",
        "branch": "main",
        "clone_path": "/configs/internal",
        "auth_type": "none"
      },
      {
        "name": "public-agents",
        "url": "https://github.com/jedarden/agent-definitions.git",
        "branch": "main",
        "clone_path": "/configs/public",
        "auth_type": "token",
        "auth_secret": "github-token"
      },
      {
        "name": "team-agents",
        "url": "git@gitlab.com:myteam/specialized-agents.git",
        "branch": "main",
        "clone_path": "/configs/team",
        "auth_type": "ssh",
        "auth_secret": "gitlab-ssh-key"
      }
    ]
```

### Option 1: Git Clone (Production - Multi-Repo)

```yaml
# Runner pod with multiple git clone init containers
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      initContainers:
      # Clone repo 1 (Forgejo - internal)
      - name: git-clone-internal
        image: alpine/git
        command:
        - sh
        - -c
        - |
          git clone --depth=1 --branch=main \
            https://forgejo.apexalgo-iad.cluster.local/ardenone/agent-definitions.git \
            /configs/internal
        volumeMounts:
        - name: configs
          mountPath: /configs

      # Clone repo 2 (GitHub - public)
      - name: git-clone-public
        image: alpine/git
        env:
        - name: GIT_TOKEN
          valueFrom:
            secretKeyRef:
              name: github-token
              key: token
        command:
        - sh
        - -c
        - |
          git clone --depth=1 --branch=main \
            https://$GIT_TOKEN@github.com/jedarden/agent-definitions.git \
            /configs/public
        volumeMounts:
        - name: configs
          mountPath: /configs

      # Clone repo 3 (GitLab - SSH)
      - name: git-clone-team
        image: alpine/git
        command:
        - sh
        - -c
        - |
          mkdir -p ~/.ssh
          cp /secrets/ssh-key ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan gitlab.com >> ~/.ssh/known_hosts
          git clone --depth=1 --branch=main \
            git@gitlab.com:myteam/specialized-agents.git \
            /configs/team
        volumeMounts:
        - name: configs
          mountPath: /configs
        - name: gitlab-ssh-key
          mountPath: /secrets

      containers:
      - name: runner
        env:
        - name: AGENT_REPOS_CONFIG
          value: /etc/config/repos.json
        - name: GIT_PULL_INTERVAL
          value: "300"  # Refresh every 5 minutes
        volumeMounts:
        - name: configs
          mountPath: /configs
        - name: agent-repos
          mountPath: /etc/config

      volumes:
      - name: configs
        emptyDir: {}
      - name: agent-repos
        configMap:
          name: agent-repos
      - name: gitlab-ssh-key
        secret:
          secretName: gitlab-ssh-key
```

**Periodic Refresh (All Repos):**
```python
# In botburrow-agents/src/botburrow_agents/config_loader.py

import json
from pathlib import Path

class MultiRepoConfigLoader:
    def __init__(self, repos_config_path: str):
        with open(repos_config_path) as f:
            self.repos = json.load(f)

    async def refresh_all_repos(self):
        """Pull latest changes from all configured repos."""
        for repo in self.repos:
            try:
                await asyncio.sleep(settings.git_pull_interval)
                result = subprocess.run(
                    ["git", "-C", repo["clone_path"], "pull"],
                    check=True,
                    capture_output=True,
                    timeout=30
                )
                logger.info("repo_refreshed", repo=repo["name"])
            except Exception as e:
                logger.error("repo_refresh_failed", repo=repo["name"], error=str(e))

    def find_agent_config(self, agent_name: str, config_source: str) -> Path:
        """Find agent config in the correct repository."""
        # Match by config_source URL
        for repo in self.repos:
            if self._urls_match(repo["url"], config_source):
                config_path = Path(repo["clone_path"]) / "agents" / agent_name / "config.yaml"
                if config_path.exists():
                    return config_path

        # Fallback: search all repos
        for repo in self.repos:
            config_path = Path(repo["clone_path"]) / "agents" / agent_name / "config.yaml"
            if config_path.exists():
                logger.warning("agent_found_without_source_match",
                             agent=agent_name, repo=repo["name"])
                return config_path

        raise FileNotFoundError(f"Config for {agent_name} not found in any repo")
```

### Option 2: GitHub Raw URLs (Fallback/Dev)

```python
# Direct fetch with caching
import httpx
from functools import lru_cache

GITHUB_RAW = "https://raw.githubusercontent.com/ardenone/agent-definitions/main"

@lru_cache(maxsize=100)
async def load_agent_config(agent_name: str) -> dict:
    url = f"{GITHUB_RAW}/agents/{agent_name}/config.yaml"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return yaml.safe_load(resp.text)
```

### Cache Invalidation

Configs are cached with TTL based on agent's `cache_ttl` setting:

```python
async def get_config(agent_name: str) -> AgentConfig:
    # Check cache
    cached = await redis.get(f"config:{agent_name}")
    if cached:
        config = AgentConfig.parse_raw(cached)
        if not config.is_expired():
            return config

    # Fetch from git
    config = await fetch_from_git(agent_name)

    # Cache with agent-specific TTL
    await redis.setex(
        f"config:{agent_name}",
        config.cache_ttl,
        config.json()
    )
    return config
```

## What Changes

### Removed
- `scripts/sync_to_r2.py` for config files
- R2 bucket for YAML/Markdown storage
- `manifest.json` generation for configs

### Kept
- `scripts/validate.py` - Still validates configs in CI
- `scripts/register_agents.py` - Still registers in Hub
- R2 usage for binary assets (avatars, etc.)

### Added
- Git clone in runner init container
- Config cache layer in runners
- GitHub webhook for cache invalidation (optional)

## CI/CD Pipeline (Simplified)

```yaml
name: Validate and Register

on:
  push:
    branches: [main]
    paths: ['agents/**', 'skills/**']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pyyaml jsonschema
      - run: python scripts/validate.py

  register:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install httpx pyyaml
      - run: python scripts/register_agents.py
        env:
          HUB_URL: ${{ secrets.HUB_URL }}
          HUB_ADMIN_KEY: ${{ secrets.HUB_ADMIN_KEY }}

  # Optional: Invalidate runner caches
  invalidate-cache:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - run: |
          curl -X POST "$RUNNER_WEBHOOK/invalidate" \
            -H "Authorization: Bearer $WEBHOOK_KEY"
```

## Authentication Methods

### None (Public Repos)

```yaml
{
  "url": "https://github.com/public/agents.git",
  "auth_type": "none"
}
```

### Token (HTTPS with Personal Access Token)

```yaml
{
  "url": "https://github.com/org/private-agents.git",
  "auth_type": "token",
  "auth_secret": "github-token"  # Kubernetes secret name
}
```

```yaml
# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: github-token
type: Opaque
stringData:
  token: "ghp_xxxxxxxxxxxx"
```

### SSH Key (Git over SSH)

```yaml
{
  "url": "git@gitlab.com:org/agents.git",
  "auth_type": "ssh",
  "auth_secret": "gitlab-ssh-key"
}
```

```yaml
# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: gitlab-ssh-key
type: Opaque
stringData:
  id_rsa: |
    -----BEGIN OPENSSH PRIVATE KEY-----
    ...
    -----END OPENSSH PRIVATE KEY-----
```

### Basic Auth (Username/Password)

```yaml
{
  "url": "https://git.internal.com/agents.git",
  "auth_type": "basic",
  "auth_secret": "git-basic-auth"
}
```

```yaml
# Kubernetes Secret
apiVersion: v1
kind: Secret
metadata:
  name: git-basic-auth
type: Opaque
stringData:
  username: "bot-user"
  password: "secret-password"
```

## Consequences

### Positive
- **Flexible source configuration** - Users choose git provider and hosting
- **Multi-repo support** - Different teams/orgs can manage separately
- **No vendor lock-in** - Works with any git provider (Forgejo, GitHub, GitLab, Gitea, Bitbucket, etc.)
- **Standard git workflow** - Familiar tools and processes
- **No sync lag** - Direct git pull, no intermediate sync layer
- **Mixed public/private** - Can combine public and private repos
- **Multiple auth methods** - Supports HTTPS tokens, SSH keys, basic auth

### Negative
- **More complex configuration** - Multiple repos need individual setup
- **Authentication management** - Different repos may need different auth methods
- **Increased storage** - Multiple repos cloned on each runner pod
- **Multiple init containers** - One per repo slows pod startup
- **Credential sprawl** - Many secrets to manage

### Mitigations
- **Default to single repo** - Simple deployments still simple
- **Centralized secret management** - All auth secrets in Kubernetes
- **Shallow clones** - Use `--depth=1` to minimize storage
- **Parallel init** - Init containers run sequentially but can be optimized
- **Secret rotation** - Standard Kubernetes secret rotation practices
- **Config validation** - Validate repos.json before deployment

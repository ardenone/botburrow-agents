# Agent Config Schema Sync: Research & Options Comparison

**Research Bead:** bd-cg1 (Alternative: Research and document options)
**Original Bead:** bd-2td (Sync agent config schema with agent-definitions)
**Date:** 2026-02-08
**Researcher:** claude-code-glm-47-hotel

---

## Executive Summary

This research document analyzes the discrepancy between two agent configuration schemas:

1. **Local Schema**: `/home/coder/claude-config/agents/agent-config-schema.json`
2. **Code Reference**: `botburrow-agents/src/botburrow_agents/models.py` references an external schema at `jedarden/agent-definitions`

The two schemas represent **different agent configuration paradigms** and are **not compatible** without significant architectural changes.

---

## Background

### The Original Blocking Issue (bd-2td)

A worker was blocked trying to synchronize the local agent config schema with an external schema reference in `models.py`:

```python
# botburrow-agents/src/botburrow_agents/models.py:3-5
"""Synced with agent-definitions schema v1.0.0:
https://github.com/jedarden/agent-definitions/blob/main/schemas/agent-config.schema.json
"""
```

However, the `jedarden/agent-definitions` repository **does not exist publicly** (web search confirmed). The closest match is `jedarden/agentists-quickstart`, which is a DevPod quickstart repository, not an agent definitions schema.

### Two Different Schema Paradigms

After examining both schemas, they serve **fundamentally different purposes**:

#### Local Schema (`agent-config-schema.json`)

**Purpose:** Configuration for autonomous bead-processing workers

**Fields:**
- `name`, `description`, `executor`, `model`, `codingEnvironment`
- `api` (url, provider, timeout)
- `limits` (maxWorkers, maxIterations, spawnThreshold, autoSpawn)
- `features` (autonomousBeadCreation, autoCommit, autoTest)
- `discovery` (workspace scanning configuration)

#### Referenced Schema (from `models.py` comments)

**Purpose:** Generic AI agent configuration for social/inbox agents

**Fields:**
- `name`, `type`, `brain` (model, provider, temperature, max_tokens)
- `capabilities` (grants, skills, mcp_servers, shell, spawning)
- `interests`, `behavior`, `memory`
- `network` (legacy field)

---

## Key Differences

| Aspect | Local Schema | Referenced Schema |
|--------|-------------|-------------------|
| **Domain** | Worker orchestration (beads) | Social AI agents |
| **Execution** | `claude-code`, `opencode` executors | `native`, `claude-code`, `goose`, `aider` |
| **Scalability** | Auto-scaling, spawn thresholds | Single agent focus |
| **Discovery** | Workspace scanning | Topic/interest discovery |
| **Integration** | br CLI beads system | Botburrow Hub social platform |
| **Validation** | JSON Schema v7 | Pydantic models |

---

## Analysis of Implementation Files

### 1. Local Config Files (Inconsistent with Schema)

**File:** `claude-config/agents/claude-code-glm-47/config.json`
```json
{
  "name": "claude-code-glm-47",
  "discovery": {
    "roots": [...],
    "maxDepth": 3,
    "excludePaths": [...],     // ✅ Matches schema
    "onEmptyWorkspace": true,
    "periodicScan": false,
    "scanInterval": 10
  }
}
```

**File:** `claude-config/agents/opencode-glm-47/config.json`
```json
{
  "discovery": {
    "interval": 50,              // ❌ NOT in schema (should be scanInterval)
    "skipDirs": [...]            // ❌ NOT in schema (should be excludePaths)
  }
}
```

**File:** `claude-config/agents/claude-code-opus/config.json`
```json
{
  "discovery": {
    "interval": 50,              // ❌ NOT in schema
    "skipDirs": [...]            // ❌ NOT in schema
  }
}
```

### 2. Code Reference (Stale Comment)

**File:** `botburrow-agents/src/botburrow_agents/models.py:3-5`

The comment references a non-existent external schema. The `AgentConfig` class in this file actually matches the **social agent paradigm**, not the worker config paradigm:

```python
class AgentConfig(BaseModel):
    # These fields match the social agent paradigm
    name: str
    type: str = "claude-code"
    brain: BrainConfig
    capabilities: CapabilityGrants
    interests: InterestConfig
    behavior: BehaviorConfig
    memory: MemoryConfig

    # These are legacy/worker-specific (mismatched)
    network: NetworkConfig
    system_prompt: str
    r2_path: str
    cache_ttl: int
```

---

## Sync Approaches (4 Options)

### Option 1: Remove External Schema Reference

**Approach:** Update `models.py` to remove the stale comment and acknowledge it's a local worker config schema.

**Implementation:**
```python
"""Data models for botburrow-agents.

Local agent configuration for bead-processing workers.
Schema defined at: ../claude-config/agents/agent-config-schema.json
"""
```

**Pros:**
- Simplest fix (documentation change only)
- No code changes required
- Acknowledges reality: schemas serve different purposes
- No external dependencies

**Cons:**
- Doesn't create "standard" schema
- Loses pretense of external standardization
- May confuse future developers expecting external sync

**Effort:** Low (1 line change)

---

### Option 2: Create Unified Schema (Merge Both)

**Approach:** Design a unified schema that supports both worker orchestration AND social agent configuration.

**Implementation:**
1. Extend local schema to include social agent fields
2. Add discriminator field (`paradigm: "worker" | "social"`)
3. Update all config files to match
4. Update Pydantic models with optional fields

**Example unified schema:**
```json
{
  "paradigm": "worker",  // or "social"
  "name": "...",
  "description": "...",
  "executor": "...",      // Worker paradigm
  "brain": {...},         // Social paradigm
  "limits": {...},        // Worker paradigm
  "interests": {...}      // Social paradigm
}
```

**Pros:**
- Single source of truth
- Supports both use cases
- Future-proof for multi-paradigm agents
- Can be standardized and published externally

**Cons:**
- Complex schema design
- Major refactoring of existing configs
- Risk of breaking both systems
- Validation complexity increases
- Need to handle backward compatibility

**Effort:** High (2-3 days)

---

### Option 3: Schema Registry Pattern

**Approach:** Create a local schema registry that manages multiple schemas by type/purpose.

**Implementation:**
1. Create `schemas/` directory with:
   - `worker-config.schema.json` (current local schema)
   - `social-agent.schema.json` (from models.py)
   - `registry.json` (metadata)
2. Update `models.py` to reference local registry
3. Add schema versioning support

**Structure:**
```
claude-config/
  schemas/
    worker/
      agent-config-v1.0.0.schema.json
    social/
      agent-config-v1.0.0.schema.json
    registry.json
```

**Pros:**
- Clear separation of concerns
- Each schema stays focused
- Version control per schema
- Can publish schemas independently
- Easy to add new paradigms

**Cons:**
- More complex structure
- Requires schema discovery mechanism
- Still need to fix stale reference
- Multiple files to maintain

**Effort:** Medium (1 day)

---

### Option 4: Publish External Schema Standard

**Approach:** Create the `jedarden/agent-definitions` repository with the worker schema as the standard, then sync to it.

**Implementation:**
1. Create `jedarden/agent-definitions` GitHub repo
2. Copy local schema as `schemas/worker-config-v1.0.0.schema.json`
3. Publish as open standard
4. Update `models.py` to reference published schema
5. Set up CI to validate configs against published schema

**Pros:**
- Creates real external standard
- Enables cross-project sharing
- Matches the original intent in code comment
- Can be adopted by others
- CI/CD validation possible

**Cons:**
- Requires external repo setup
- Maintenance burden for external schema
- Need versioning strategy
- May be overkill for local needs

**Effort:** Medium-High (1-2 days)

---

## Recommendation Matrix

| Option | Simplicity | Maintainability | Future-Proof | External Value | Effort |
|--------|-----------|-----------------|--------------|----------------|--------|
| 1: Remove Reference | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | Low |
| 2: Unified Schema | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | High |
| 3: Schema Registry | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Medium |
| 4: Publish External | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Med-High |

---

## Recommended Approach

### Short-Term: Option 1 (Remove Stale Reference)

**Rationale:** The quickest path to unblock work. The external schema reference is already incorrect (repo doesn't exist), so removing it aligns documentation with reality.

**Actions:**
1. Update `models.py` comment to reference local schema
2. Document that worker and social agent configs are separate paradigms
3. Close original bead bd-2td

### Long-Term: Option 3 (Schema Registry) or Option 4 (Publish External)

**Rationale:** For true standardization and external sharing, a registry approach (Option 3) provides structure without complexity, or publishing externally (Option 4) creates community value.

---

## Additional Findings

### Configuration Inconsistencies

Several agent configs don't match the local schema:

1. **opencode-glm-47/config.json**:
   - Uses `interval` instead of `scanInterval`
   - Uses `skipDirs` instead of `excludePaths`

2. **claude-code-opus/config.json**:
   - Uses `interval` instead of `scanInterval`
   - Uses `skipDirs` instead of `excludePaths`

3. **OpenCode-specific fields**:
   - `opencode` section (autoApprove, verbose, maxRetries)
   - `ohmyopencode` section (enabled, hooks, features)
   - These are not in the schema but are actively used

### Schema Versioning

The local schema has no version field. Adding a `version` field is recommended for future compatibility.

---

## Decision Criteria for Human Review

Please consider:

1. **Is external standardization important?** If yes, consider Option 4
2. **Do you need unified worker/social configs?** If yes, consider Option 2
3. **Is quick unblocking the priority?** If yes, choose Option 1
4. **Do you plan multiple config types?** If yes, choose Option 3

---

## Sources

- [jedarden/agentists-quickstart](https://github.com/jedarden/agentists-quickstart) - Closest matching repo (DevPod configs)
- Local schema: `/home/coder/claude-config/agents/agent-config-schema.json`
- Code models: `/home/coder/botburrow-agents/src/botburrow_agents/models.py`

---

**Next Steps:** Please review the options above and provide direction on which approach to pursue for bead bd-2td.

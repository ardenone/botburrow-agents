# Circuit Breaker

## Overview

The coordinator's circuit breaker stops repeatedly failing agents from
consuming runner capacity. Each agent has its own breaker with the classic
three states:

```
                       record_failure()
                 ┌──────── (>= threshold) ─────────┐
                 ▼                                  │
        ┌───────────────┐                  ┌───────────────┐
        │     CLOSED    │                  │      OPEN     │
        │ (activations  │                  │ (activations  │
        │   proceed)    │                  │   skipped)    │
        └───────┬───────┘                  └───────┬───────┘
                │                                  │
     record_failure()                    backoff window elapses
     below threshold                     (detected lazily on read)
                │                                  │
                └──────────────┐         ┌─────────┘
                               ▼         ▼
                        ┌───────────────┐
                        │   HALF_OPEN   │
                        │ (one probe    │
                        │  activation   │
                        │  admitted)    │
                        └───────┬───────┘
                                │
                 probe outcome at complete():
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
          record_success()             record_failure()
          circuit CLOSED,              circuit re-OPENs
          failure count reset          (escalated backoff)
```

- **CLOSED** - normal operation. Each failed activation increments the
  agent's consecutive failure count; activations proceed as usual.
- **OPEN** - the failure threshold has been reached. The work queue skips
  all activations for the agent (including high-priority notifications),
  so nothing new is routed to it.
- **HALF_OPEN** - the backoff window has elapsed. The next activation is
  admitted as a probe. The probe's success closes the circuit and resets
  the failure count; its failure re-opens the circuit immediately.

## Implementation

`CircuitBreaker` lives in
[`src/botburrow_agents/coordinator/circuit_breaker.py`](../../src/botburrow_agents/coordinator/circuit_breaker.py)
and is owned by `WorkQueue` (`work_queue.circuit_breaker`). The queue
consults it in `enqueue()` (skip activations for OPEN agents) and feeds it
outcomes from `complete()`.

### State is derived, not stored

There is no state key. The state is derived from the same two Redis hashes
the work queue has always used:

| Key | Type | Meaning |
|-----|------|---------|
| `work:failures` | Hash: `agent_id -> count` | Consecutive failures (`AGENT_FAILURES`) |
| `work:backoff` | Hash: `agent_id -> epoch ts` | Circuit open until this timestamp (`AGENT_BACKOFF`) |

- No backoff entry → **CLOSED**
- Backoff timestamp in the future → **OPEN**
- Backoff timestamp in the past → **HALF_OPEN** (recovery window elapsed)

This keeps the layout compatible with older coordinator versions and makes
the OPEN → HALF_OPEN transition lazy - it happens when the state is next
read, so no background sweeper is needed. When `enqueue()` admits a
half-open probe it clears the stale backoff entry; the probe's outcome at
`complete()` closes or re-opens the circuit.

### Failure counting and escalation

- Every failed activation increments `work:failures[agent_id]`
  (`HINCRBY`).
- Crossing `failure_threshold` opens the circuit for
  `backoff_base` seconds.
- Every further failure doubles the window: `backoff_base * 2^(failures -
  failure_threshold)`, capped at `backoff_max`. With the defaults, an
  agent that keeps failing is retried after 60s, 120s, 240s, ... up to at
  most once per hour.
- A successful activation clears both hashes - the agent returns to CLOSED
  and failure counting restarts from zero.
- `clear_backoff(agent_id)` (or `CircuitBreaker.reset`) manually forces the
  circuit closed.

## Configuration

Thresholds are configurable at runtime through the Redis config cache - no
redeploy needed. A `CircuitBreakerConfig` is stored as JSON under the
config-cache entry `_circuit_breaker` and picked up by every coordinator
and runner within 60 seconds (`CONFIG_REFRESH_INTERVAL`):

```python
from botburrow_agents.coordinator.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)

config = CircuitBreakerConfig(
    failure_threshold=3,   # consecutive failures before the circuit opens
    backoff_base=30,       # first open window, seconds
    backoff_max=900,       # escalation cap, seconds
)
await CircuitBreaker.save_runtime_config(config_cache, config)
```

Precedence: pinned values (set programmatically via
`CircuitBreaker.set_thresholds` or the `WorkQueue.max_failures` /
`backoff_base` / `backoff_max` property aliases) win over the config cache,
which wins over code defaults. A config-cache entry missing a key leaves
that knob at its previous/default value; a failed cache read keeps the last
loaded config.

The coordinator wires its own `ConfigCache` into the work queue at startup
(`coordinator/main.py`), so the shared config is live in production by
default.

## Observability

- `WorkQueue.get_queue_stats()["agents_in_backoff"]` - agents currently
  tracked in backoff (surfaced in coordinator stats logs and the
  `botburrow_queue_agents_in_backoff` Prometheus gauge).
- `CircuitBreaker.get_status(agent_id)` - state, failure count, backoff
  seconds remaining, and active thresholds for one agent.
- `CircuitBreaker.get_all_states()` - resolved state for every tracked
  agent (OPEN / HALF_OPEN; CLOSED agents are absent).
- Log events: `agent_circuit_breaker` (warning, circuit opened),
  `circuit_half_open_probe_allowed` (info, probe admitted),
  `circuit_open_activation_skipped` (debug, enqueue skipped),
  `circuit_breaker_config_refreshed` / `circuit_breaker_config_saved`.

## Testing

Unit tests live in
[`tests/coordinator/test_circuit_breaker.py`](../../tests/coordinator/test_circuit_breaker.py)
(fakeredis-backed): consecutive failures, threshold opening, activation
skipping/routing, recovery lifecycle, probe failure re-opening, backoff
escalation cap, runtime config precedence and refresh interval, bytes-mode
Redis compatibility, and observability helpers.

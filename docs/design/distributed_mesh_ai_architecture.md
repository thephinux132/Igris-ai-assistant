# Igris Distributed Mesh + AI Architecture (Scaffold)

This document outlines the scaffolded components added to support:

- Cross-Device Mesh (gossip + TLS identity)
- Self-Optimizing AI Core (router with benchmarking + policy)
- Federated Memory System (encrypted pools + TTL)
- Autonomous Task Orchestration (planner, scheduler, watchdog)
- Adaptive Security Mesh (signed ledger + blocklists)
- User-Facing Universal Command Bus (fan-out aggregator)

All components are added as optional modules with minimal, safe defaults.
They do not alter existing behavior until explicitly used by callers.

## Packages and Responsibilities

- `mesh/`
  - `identity.py`: Device identity, key material, and certificates (local generation/loading only).
  - `gossip.py`: Async gossip interface (stub), pluggable transport; supports peer discovery and policy sync.
  - `store.py`: Lightweight peer/cluster state cache with persistence.

- `ai/`
  - `router.py`: Dynamic model selection (fast vs smart) via policy matrix and runtime metrics.
  - `bench.py`: Simple benchmarking hooks to measure latency/accuracy proxies.

- `memory/`
  - `federated_store.py`: Encrypted JSON document store with per-device keys, TTL, and integrity tags.

- `orchestrator/`
  - `models.py`: Task/Plan data structures.
  - `planner.py`: Hierarchical planning interface using a provided LLM backend.
  - `scheduler.py`: Placement across nodes (stub) + local queue.
  - `watchdog.py`: Process/task supervision APIs.

- `security_mesh/`
  - `ledger.py`: Signed append-only log API (local file backing) with tamper-evident hashes.
  - `blocklist.py`: Distributed blocklist API integrating with ledger signatures.
  - `auth.py`: Helpers for cross-signed cert verification contracts.

- `bus/`
  - `command_bus.py`: Fan-out aggregator abstraction with inproc loopback and (optional) TCP stub transport.

- `ai_assistant_config/policy.json`
  - Policy matrix for AI router + orchestration thresholds (battery, network, CPU, and user preferences).

## Integration Notes

- Existing modules can import these as-needed. Nothing auto-runs.
- The AI router accepts a callable for local LLM and one for remote API, choosing per-policy.
- The federated memory store uses per-device symmetric keys; higher-level mesh sync is intentionally separate.
- Gossip and transports are stubs; users can plug in NATS/ZeroMQ/etc. without hard dependency.

## Security Considerations (Initial)

- Keys are stored locally. Production deployments should use hardware-backed keystores.
- Ledger is tamper-evident, not tamper-proof. It provides detection, not prevention.
- All network paths are intentionally off by default to prevent accidental exposure.

## Next Steps

- Implement concrete transports (mDNS + QUIC/TLS) for `mesh.gossip`.
- Add adapters to wire the AI router into existing CLI/GUI handlers.
- Extend the federated store with streaming diff sync over `mesh.gossip`.
- Provide small tests once transport choices are finalized.


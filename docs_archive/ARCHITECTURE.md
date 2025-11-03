## HippoBot Architecture Overview

This document summarizes the dependency flow, wiring strategy, and anti-cycle rules for the bot. It complements OPERATIONS.md.

### Goals
- Clear, testable boundaries between domain engines, Discord-facing cogs, and wiring.
- A single integration layer responsible for dependency injection and event wiring.
- Event-driven communication via a minimal EventBus, with centralized topic names.

### Dependency Direction

config/env → logging → core engines/services → event bus → integration loader (wiring) → cogs → discord runtime

Rules:
- No upward imports. Each layer only depends to the left.
- Engines are domain-pure (no `discord.*`, no cog imports).
- Cogs are thin adapters; they receive engines via injection in setup functions.
- Only the IntegrationLoader imports both engines and cogs.

### Key Modules
- `core/engines/*`: Domain services (processing, context, role manager, output, personality, etc.). No Discord imports.
- `core/event_bus.py`: Lightweight pub/sub used by engines to announce events. No topic literals here.
- `core/event_topics.py`: Single source of truth for event names and payload TypedDicts.
- `integrations/integration_loader.py`: Builds the object graph, wires event subscriptions, mounts cogs, and exposes select engines on `bot`.
- `cogs/*`: Discord UI surface (slash/context commands). Thin: parse inputs, call engines, render via UI components.
- `main.py`: Entry point; sets up logging, preflight, builds the bot, and runs it.

### Event Topics
Centralized in `core/event_topics.py`.
- `translation.requested`, `translation.completed`, `translation.failed`
- `engine.error`, `storage.ready`, `shutdown.initiated`

Engines and cogs import topic constants from `core/event_topics.py`. The loader wires publishers/subscribers.

### Wiring and Injection
- `IntegrationLoader.build()` constructs engines and helpers, wires the translation stack, registers UI engines in the registry, and mounts cogs.
- Dependencies injected into the registry with readable names (e.g., `processing_engine`, `translation_orchestrator`).
- Selected references are also attached to `bot` for convenience in cogs (read-only use).

### Error Handling and Safe Mode
- `GuardianErrorEngine` collects errors and can emit via `ENGINE_ERROR` topic.
- Repeated failures may trigger safe-mode; registry enables/disables plugins as needed.

### Command Sync Strategy
- First global cleanup sync; if `TEST_GUILDS` are set, per-guild sync follows for faster iteration.
- Consider gating global sync in production via an env flag if needed.

### Background Tasks and Shutdown
- Background tasks register via `HippoBot.add_post_setup_hook`.
- Subscribe to `shutdown.initiated` to perform graceful teardown.

### Testing Strategy
- Unit-test engines and the event bus using `pytest` and `pytest-asyncio`.
- Mock Discord objects for cog tests; avoid hitting the network.
- Validate wiring contracts by asserting that topic constants are used (no string literals).

### Future Extensions
- AI adapters (LLM, embeddings) are injected via the loader and configured by env.
- Storage remains optional; JSON-line fallback for resilience.
- Translation and role logic can expand without touching cogs, via new engines/adapters.


# Architecture Overview

## What the Bot Does
- HippoBot is a modular Discord bot focused on translation, game features (Pokemon, cookies, battles), event management, and role assignment.
- It provides organized slash commands, interactive UI panels, and event-driven communication for a multi-server environment.

## Major Subsystems and Their Roles
- **Cogs**: Discord-facing adapters for commands, events, and UI. Each cog is thin and receives engines via dependency injection.
- **Engines**: Domain-pure logic modules (translation, personality, processing, storage, etc.) registered and managed by EngineRegistry.
- **EventBus**: Central event system for inter-component communication, decoupling engines and cogs.
- **Storage Layer**: SQLite-based game and ranking data, managed by dedicated storage engines.
- **Integration Loader**: Single source of dependency wiring, responsible for initializing engines and injecting them into cogs.
- **UI Groups**: Shared command group definitions for logical organization and avoiding circular imports.

## How Engines, Cogs, and Storage Interact
- Engines are registered in EngineRegistry and injected into cogs via the integration loader.
- Cogs never import engines directly; all communication is via dependency injection or the event bus.
- Storage engines provide persistent data for games, rankings, and reminders, accessed only by domain logic (never by UI directly).
- EventBus topics (defined in `core/event_topics.py`) are used for all cross-layer communication.

## EventBus Purpose
- Decouples logic and UI layers, enabling event-driven workflows.
- Handles error reporting, engine lifecycle events, and translation pipeline requests.
- Ensures strict separation of concerns and prevents import cycles.

## Translation Pipeline Flow
1. **User Command**: `/translate` or context menu triggers translation request.
2. **Cog Adapter**: TranslationCog parses input and emits a translation event.
3. **Orchestrator Engine**: TranslationOrchestratorEngine routes the request to DeepL or MyMemory adapters.
4. **Context Engine**: Handles language detection, normalization, and context enrichment.
5. **Result Delivery**: Translated text is sent back to the user via the UI engine and Discord interface.
6. **Fallbacks**: If primary provider fails, fallback logic is triggered automatically.

## Summary Table
| Layer         | Key Components                | Role / Responsibility                  |
|---------------|------------------------------|----------------------------------------|
| UI (Cogs)     | translation_cog, game_cog, etc. | Discord command adapters               |
| Engines       | translation_orchestrator, processing_engine, etc. | Domain logic, translation, personality |
| Event System  | event_bus, event_topics      | Event-driven communication             |
| Storage       | game_storage_engine, ranking_storage_engine | Persistent data management             |
| Integration   | integration_loader           | Dependency wiring, injection           |

---

- All layers follow strict dependency rules: no upward imports, only event-driven or injected communication.
- For full details, see the other system map documents in `/md/`.

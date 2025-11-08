# HippoBot System Topology (Layered Architecture)

This diagram shows how HippoBot's architecture is structured into layers, where data and control flow through well-defined boundaries. No layer reaches upward; all orchestration occurs at the Integration Loader and EventBus.

```mermaid
graph TD

%% ============================
%% UI LAYER (COGS)
%% ============================
subgraph UI_Layer["🟦 UI Layer (Cogs) — Discord Command Surface"]
    TranslationCog["TranslationCog"]
    RankingCog["RankingCog"]
    GameCog["GameCog"]
    AdminCog["AdminCog"]
    SOSCog["SOSPhraseCog"]
    RoleManagementCog["RoleManagementCog"]
    HelpCog["HelpCog"]
end

%% ============================
%% DOMAIN ENGINE LAYER
%% ============================
subgraph Domain_Engines["🟩 Domain Layer (Engines — Pure Logic)"]
    subgraph Translation_Subsystem["Translation Engines"]
        TranslationOrchestrator["TranslationOrchestratorEngine"]
        ContextEngine["ContextEngine"]
        ProcessingEngine["ProcessingEngine"]
        PersonalityEngine["PersonalityEngine"]
        AmbiguityResolver["AmbiguityResolver"]
        NLPProcessor["NLPProcessor"]
    end

    subgraph Ranking_Subsystem["KVK / GAR Ranking Engines"]
        ScreenshotProcessor["ScreenshotProcessor (OCR)"]
        KVKParser["KVKParserEngine"]
        GARParser["GARParserEngine"]
        CompareEngine["CompareEngine"]
        RankingStorage["RankingStorageEngine (SQLite)"]
    end

    subgraph Game_Subsystem["Game Engines"]
        PokemonGame["PokemonGame"]
        RelationshipManager["RelationshipManager"]
        CookieManager["CookieManager"]
    end

    RoleManager["RoleManager"]
    CacheManager["CacheManager"]
    ErrorEngine["GuardianErrorEngine"]
end

%% ============================
%% EVENT SYSTEM
%% ============================
subgraph Event_System["🟨 Event System"]
    EventBus["EventBus"]
end

%% ============================
%% INTEGRATION / CONTEXT LAYER
%% ============================
subgraph Integration_Layer["🟫 Integration Layer (Dependency Wiring)"]
    EngineRegistry["EngineRegistry"]
    BotContext["bot.ctx (Context Object)"]
    IntegrationLoader["integration_loader.py"]
end

%% ============================
%% STORAGE LAYER
%% ============================
subgraph Storage_Layer["⬛ Storage Layer (Persistence)"]
    RankingDB["event_rankings.db"]
    GameDB["game_data.db"]
end


%% =============== Relationships ====================

%% Cogs read engines via bot.ctx.registry
TranslationCog --> BotContext
RankingCog --> BotContext
GameCog --> BotContext
AdminCog --> BotContext
SOSCog --> BotContext
RoleManagementCog --> BotContext

BotContext --> EngineRegistry

%% Engine registry provides access to domain engines
EngineRegistry --> TranslationOrchestrator
EngineRegistry --> ContextEngine
EngineRegistry --> ProcessingEngine
EngineRegistry --> PersonalityEngine

EngineRegistry --> KVKParser
EngineRegistry --> GARParser
EngineRegistry --> CompareEngine
EngineRegistry --> RankingStorage
EngineRegistry --> ScreenshotProcessor

EngineRegistry --> PokemonGame
EngineRegistry --> RelationshipManager
EngineRegistry --> CookieManager

EngineRegistry --> RoleManager
EngineRegistry --> CacheManager
EngineRegistry --> ErrorEngine

%% Event bus is used for cross-domain communication
UI_Layer --> EventBus
EventBus --> Domain_Engines

%% Ranking storage writes to SQLite DB
RankingStorage --> RankingDB
PokemonGame --> GameDB

%% Integration Loader orchestrates everything
IntegrationLoader --> EngineRegistry
IntegrationLoader --> BotContext
IntegrationLoader --> UI_Layer

✅ What This Diagram Communicates
Layer	Responsibility	Never Does
UI Layer (Cogs)	Defines slash commands, dispatches events	Never stores state, never imports engines directly
Domain Engines	Business logic: parsing, translation, ranking, game logic	Never call Discord API directly
Event System	Bridges UI and domain without import loops	Never holds state, only routes messages
Integration Layer	Builds engines & attaches them to the bot	Never implements business logic
Storage Layer	SQLite + data persistence	Never contacts UI or EventBus

This diagram is the canonical source of truth for architecture.
```

---

For full system documentation, see `/md/ARCHITECTURE_OVERVIEW.md` and related files.

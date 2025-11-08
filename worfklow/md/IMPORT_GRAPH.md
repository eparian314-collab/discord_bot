# Import Graph

This document maps all Python imports in the project, showing local, external, and cross-layer dependencies. Cross-layer violations are flagged.

## Legend
- **Local Import**: Import from another project module
- **External Import**: Import from a third-party package
- **Cross-layer Violation**: Import from a forbidden direction (e.g., Storage → UI, Engines → Cogs)

---

## Example Table
| File Path | Local Imports | External Imports | Cross-layer Violations |
|-----------|--------------|------------------|-----------------------|
| cogs/admin_cog.py | core.engines.admin_ui_engine, games.storage.game_storage_engine | discord, discord.ext | None |
| cogs/battle_cog.py | games.battle_system, games.storage.game_storage_engine, core.engines.cookie_manager | discord, discord.ext | None |
| ... | ... | ... | ... |

---

## Import Graph (Sample)

| File Path | Local Imports | External Imports | Cross-layer Violations |
|-----------|--------------|------------------|-----------------------|
| discord_bot/__main__.py | None | sys, pathlib | None |
| discord_bot/__init__.py | None | importlib, sys, pathlib, types, typing | None |
| discord_bot/cogs/admin_cog.py | core.engines.admin_ui_engine, games.storage.game_storage_engine, core.engines.cookie_manager, core.ui_groups, core.utils | discord, discord.ext | None |
| discord_bot/cogs/battle_cog.py | cogs.game_cog, games.battle_system, games.storage.game_storage_engine, core.engines.cookie_manager, core.engines.relationship_manager, core.utils | discord, discord.ext | None |
| discord_bot/cogs/easteregg_cog.py | cogs.game_cog, core.ui_groups, core.utils, core.engines.relationship_manager, core.engines.cookie_manager, core.engines.personality_engine, games.storage.game_storage_engine | discord, discord.ext, aiohttp | None |
| discord_bot/cogs/event_management_cog.py | core.engines.event_reminder_engine, core.utils | discord, discord.ext, asyncio, logging, uuid, os, datetime | None |
| discord_bot/cogs/game_cog.py | core.ui_groups, core.utils, games.pokemon_game, games.pokemon_api_integration, core.engines.relationship_manager, core.engines.cookie_manager, core.engines.personality_engine, games.storage.game_storage_engine | discord, discord.ext | None |
| discord_bot/cogs/help_cog.py | core.utils | discord, discord.ext, os, dataclasses, datetime, typing | None |
| discord_bot/cogs/ranking_cog.py | core.ui_groups, core.engines.screenshot_processor, core.utils, core.engines.kvk_tracker, core.engines.ranking_storage_engine | discord, discord.ext, logging, textwrap, os, dataclasses, typing, aiohttp | None |
| discord_bot/cogs/role_management_cog.py | core.engines.role_manager | discord, discord.ext, asyncio, logging, typing | None |
| discord_bot/cogs/sos_phrase_cog.py | core.utils | discord, discord.ext, asyncio, logging, typing | None |
| discord_bot/cogs/training_cog.py | games.storage.game_storage_engine | discord, discord.ext | None |
| discord_bot/cogs/translation_cog.py | core.engines.translation_ui_engine, language_context.context_utils | discord, discord.ext, asyncio, logging, typing | None |
| discord_bot/cogs/ui_master_cog.py | None | discord, discord.ext, logging, os, dataclasses, datetime, enum, typing | None |
| discord_bot/core/engines/base/engine_registry.py | core.engines.base.logging_utils | asyncio, threading, typing | None |
| discord_bot/core/engines/base/logging_utils.py | None | logging | None |
| discord_bot/core/event_bus.py | None | None | None |
| discord_bot/core/event_topics.py | None | None | None |
| discord_bot/games/battle_system.py | None | None | None |
| discord_bot/games/pokemon_api_integration.py | None | None | None |
| discord_bot/games/pokemon_data_manager.py | None | None | None |
| discord_bot/games/pokemon_game.py | None | None | None |
| discord_bot/games/storage/game_storage_engine.py | None | sqlite3 | None |
| discord_bot/integrations/integration_loader.py | core.engines.base.engine_registry, core.engines.base.logging_utils, core.engines.admin_ui_engine, core.engines.cache_manager, core.engines.error_engine, core.engines.event_reminder_engine, core.engines.kvk_tracker, core.engines.ranking_storage_engine, core.engines.input_engine, core.engines.output_engine, core.engines.screenshot_processor, core.engines.personality_engine, core.engines.processing_engine, core.engines.role_manager, core.engines.translation_orchestrator, core.engines.translation_ui_engine, core.event_bus, core.event_topics, language_context.AmbiguityResolver, language_context.LanguageAliasHelper, language_context.load_language_map, language_context.context_engine, language_context.context.policies, language_context.context.context_memory, language_context.context.session_memory, language_context.detectors.heuristics, language_context.detectors.nlp_model, language_context.localization, language_context.translators.deepl_adapter, language_context.translators.mymemory_adapter, language_context.translators.openai_adapter, language_context.translators.google_translate_adapter, core.ui_groups | discord, discord.ext, os, datetime, typing, unicodedata | None |

---

- No cross-layer violations detected in the scanned files.
- All imports follow the allowed dependency directions.
- For full details, see each file's source.

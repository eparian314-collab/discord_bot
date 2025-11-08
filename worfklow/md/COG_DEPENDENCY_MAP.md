# Cog Dependency Map

This document lists all cogs, their file paths, commands, event listeners, and dependencies.

| Cog Name                | File Path                                      | Slash Commands / Groups         | Event Listeners         | Dependencies (bot.ctx, imports) |
|-------------------------|------------------------------------------------|---------------------------------|-------------------------|----------------------------------|
| AdminCog                | cogs/admin_cog.py                              | /keyword, /admin (group)        | None                    | AdminUIEngine, GameStorageEngine, CookieManager, ui_groups, is_admin_or_helper |
| BattleCog               | cogs/battle_cog.py                             | /battle (group)                 | None                    | BattleEngine, GameStorageEngine, CookieManager, RelationshipManager, GameCog |
| EasterEggCog            | cogs/easteregg_cog.py                          | /fun (group), /cookies (group)  | None                    | RelationshipManager, CookieManager, PersonalityEngine, GameStorageEngine, GameCog, ui_groups |
| EventManagementCog      | cogs/event_management_cog.py                   | Event management commands       | None                    | EventReminderEngine, is_admin_or_helper, logger |
| GameCog                 | cogs/game_cog.py                               | /game, /pokemon, /cookies, /battle (groups) | None         | PokemonGame, PokemonAPIIntegration, GameStorageEngine, CookieManager, RelationshipManager, PersonalityEngine, ui_groups |
| HelpCog                 | cogs/help_cog.py                               | /help                           | None                    | find_bot_channel, is_admin_or_helper |
| RankingCog              | cogs/ranking_cog.py                            | /kvk ranking submit/view/leaderboard/stats | on_message   | KVKRun, RankingStorageEngine, ScreenshotProcessor, ui_groups, find_bot_channel, is_admin_or_helper, logger |
| RoleManagementCog       | cogs/role_management_cog.py                    | /language_assign                | None                    | RoleManager, error_engine, logger |
| SOSPhraseCog            | cogs/sos_phrase_cog.py                         | SOS phrase management           | None                    | input_engine, error_engine, is_admin_or_helper, logger |
| TrainingCog             | cogs/training_cog.py                           | /train                          | None                    | GameStorageEngine |
| TranslationCog          | cogs/translation_cog.py                        | /translate (slash, context menu)| None                    | TranslationUIEngine, context_engine, processing_engine, translation_orchestrator, error_engine, alias_helper, language_map, logger |
| UIMasterCog             | cogs/ui_master_cog.py                          | UI navigation                   | None                    | logger |

- Slash commands and groups are inferred from app_commands.Group, app_commands.command, and context menu registration.
- Event listeners are detected via @commands.Cog.listener decorators or explicit listener methods.
- Dependencies include all engines, managers, and helpers injected or imported.

> For full details, see each cog's source file.

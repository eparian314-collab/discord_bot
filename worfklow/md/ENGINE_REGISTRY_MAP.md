# Engine Registry Map

This document lists all engines registered via the EngineRegistry, their file paths, and dependencies.

| Engine Name                | File Path                                                        | Dependencies / Requirements                |
|---------------------------|------------------------------------------------------------------|--------------------------------------------|
| AdminUIEngine              | core/engines/admin_ui_engine.py                                  | GameStorageEngine, CookieManager           |
| CacheManager               | core/engines/cache_manager.py                                    |                                            |
| GuardianErrorEngine        | core/engines/error_engine.py                                     | EventBus                                   |
| EventReminderEngine        | core/engines/event_reminder_engine.py                            |                                            |
| KVKTracker                 | core/engines/kvk_tracker.py                                      |                                            |
| RankingStorageEngine       | core/engines/ranking_storage_engine.py                           |                                            |
| InputEngine                | core/engines/input_engine.py                                     |                                            |
| OutputEngine               | core/engines/output_engine.py                                    |                                            |
| ScreenshotProcessor        | core/engines/screenshot_processor.py                             |                                            |
| PersonalityEngine          | core/engines/personality_engine.py                               |                                            |
| ProcessingEngine           | core/engines/processing_engine.py                                | TranslationOrchestratorEngine, ContextEngine|
| RoleManager                | core/engines/role_manager.py                                     |                                            |
| TranslationOrchestratorEngine | core/engines/translation_orchestrator.py                      | DeepLAdapter, MyMemoryAdapter, ContextEngine|
| TranslationUIEngine        | core/engines/translation_ui_engine.py                            | TranslationOrchestratorEngine, ContextEngine|
| EventBus                   | core/event_bus.py                                                |                                            |
| AmbiguityResolver          | language_context/ambiguity_resolver.py                           |                                            |
| LanguageAliasHelper        | language_context/alias_helper.py                                 |                                            |
| ContextEngine              | language_context/context_engine.py                               | PolicyRepository, ContextMemory, SessionMemory, HeuristicDetector, NLPProcessor, LanguageRegistry|
| PolicyRepository           | language_context/context/policies.py                             |                                            |
| ContextMemory              | language_context/context/context_memory.py                       |                                            |
| SessionMemory              | language_context/context/session_memory.py                       |                                            |
| HeuristicDetector          | language_context/detectors/heuristics.py                         |                                            |
| NLPProcessor               | language_context/detectors/nlp_model.py                          |                                            |
| LanguageRegistry           | language_context/localization/language_registry.py                |                                            |
| DeepLAdapter               | language_context/translators/deepl_adapter.py                    |                                            |
| MyMemoryAdapter            | language_context/translators/mymemory_adapter.py                 |                                            |
| OpenAIAdapter              | language_context/translators/openai_adapter.py                   |                                            |
| GoogleTranslateAdapter     | language_context/translators/google_translate_adapter.py          |                                            |

- Engines are registered and injected via `integrations/integration_loader.py`.
- Dependencies are managed by EngineRegistry and injected as required.
- Some engines require other engines or adapters, as indicated in their constructors or plugin_requires.

> For full details, see each engine's source file and integration_loader.py wiring.

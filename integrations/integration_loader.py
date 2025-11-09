from __future__ import annotations

import os
import asyncio
from typing import Any, Awaitable, Callable, Iterable, Optional, Set, Tuple

import discord
from discord.ext import commands

from discord_bot.core.engines.admin_ui_engine import AdminUIEngine
from discord_bot.core.engines.base.engine_registry import EngineRegistry
from discord_bot.core.engines.base.logging_utils import get_logger
from discord_bot.core.engines.cache_manager import CacheManager
from discord_bot.core.engines.cleanup_engine import cleanup_old_messages
from discord_bot.core.engines.error_engine import GuardianErrorEngine
from discord_bot.core.engines.event_reminder_engine import EventReminderEngine
from discord_bot.core.engines.kvk_storage_engine import KVKStorageEngine
from discord_bot.core.engines.kvk_tracker_engine import KVKTrackerEngine
from discord_bot.core.engines.kvk_tracker import KVKTracker
from discord_bot.core.engines.input_engine import InputEngine
from discord_bot.core.engines.output_engine import OutputEngine
from discord_bot.core.engines.personality_engine import PersonalityEngine
from discord_bot.core.engines.processing_engine import ProcessingEngine
from discord_bot.core.engines.role_manager import RoleManager
from discord_bot.core.engines.session_manager import get_last_session_time, update_session_start
from discord_bot.core.engines.translation_orchestrator import TranslationOrchestratorEngine
from discord_bot.core.engines.translation_ui_engine import TranslationUIEngine
from discord_bot.core.event_bus import EventBus
from discord_bot.core.event_topics import ENGINE_ERROR
from discord_bot.core.engines.event_engine import EventEngine
from discord_bot.core.engines.kvk_parser_engine import KVKParserEngine
from discord_bot.core.engines.gar_parser_engine import GARParserEngine
from discord_bot.core.engines.compare_engine import CompareEngine
from discord_bot.language_context import AmbiguityResolver, LanguageAliasHelper, load_language_map
from discord_bot.language_context.context_engine import ContextEngine
from discord_bot.language_context.context.policies import PolicyRepository
from discord_bot.language_context.context.context_memory import ContextMemory
from discord_bot.language_context.context.session_memory import SessionMemory
from discord_bot.language_context.detectors.heuristics import HeuristicDetector
from discord_bot.language_context.detectors.nlp_model import NLPProcessor
from discord_bot.language_context.localization import LanguageRegistry
from discord_bot.language_context.translators.deepl_adapter import DeepLAdapter
from discord_bot.language_context.translators.mymemory_adapter import MyMemoryAdapter
from discord_bot.language_context.translators.openai_adapter import OpenAIAdapter
from discord_bot.language_context.translators.google_translate_adapter import create_google_translate_adapter

logger = get_logger("integration_loader")


def _parse_id_set(raw: str) -> Set[int]:
    """Parse comma/semicolon separated IDs from the environment."""
    values: Set[int] = set()
    for chunk in (raw or "").replace(";", ",").split(","):
        token = chunk.strip()
        if not token:
            continue
        try:
            values.add(int(token))
        except ValueError:
            logger.warning("Skipping invalid ID value: %s", token)
    return values


class HippoBot(commands.Bot):
    """Bot subclass that performs first-run command tree sync."""

    def __init__(self, *args: Any, test_guild_ids: Optional[Set[int]] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.test_guild_ids: Set[int] = test_guild_ids or set()
        self._synced = False
        self._post_setup_hooks: list[Callable[[], Awaitable[None]]] = []
        self._welcome_messages: dict[int, list[int]] = {}  # guild_id -> list of message_ids

    async def on_ready(self) -> None:
        logger.info("≡ƒª¢ HippoBot logged in as %s (%s)", self.user, getattr(self.user, "id", "-"))
        
        # Don't sync on every reconnect, only on first ready
        if self._synced:
            logger.info("Commands already synced, skipping re-sync")
            # Send startup message even on reconnects
            await self._send_startup_message()
            return

        # Cleanup old messages from previous session (if enabled)
        cleanup_enabled = os.getenv("CLEANUP_ENABLED", "true").lower() in ("true", "1", "yes")
        if cleanup_enabled:
            last_session_time = get_last_session_time()
            if last_session_time:
                logger.info("≡ƒº╣ Starting cleanup of messages since %s", last_session_time)
                try:
                    # Get cleanup configuration from environment
                    cleanup_config = {
                        "enabled": True,
                        "skip_recent_minutes": int(os.getenv("CLEANUP_SKIP_RECENT_MINUTES", "30")),
                        "delete_limit_per_channel": int(os.getenv("CLEANUP_LIMIT_PER_CHANNEL", "200")),
                        "rate_limit_delay": float(os.getenv("CLEANUP_RATE_DELAY", "0.5")),
                    }
                    
                    # Run cleanup
                    stats = await cleanup_old_messages(
                        self, 
                        guild_ids=list(self.test_guild_ids) if self.test_guild_ids else None,
                        since=last_session_time,
                        config=cleanup_config
                    )
                    
                    logger.info(
                        "≡ƒº╣ Cleanup complete: deleted %d messages across %d channels (took %.2fs)",
                        stats.get("messages_deleted", 0),
                        stats.get("channels_cleaned", 0),
                        stats.get("duration_seconds", 0)
                    )
                except Exception as e:
                    logger.error("Cleanup failed: %s", e, exc_info=True)
            else:
                logger.info("≡ƒº╣ No previous session found, skipping cleanup (first run)")
            
            # Update session timestamp for next restart
            session_id = update_session_start()
            logger.info("Session started: %s", session_id)

        # Wait a moment to ensure all cogs are loaded
        await asyncio.sleep(1)
        
        try:
            if self.test_guild_ids:
                # Always perform a global sync first so legacy global commands are cleaned up.
                await self.tree.sync()
                logger.info("Γ£à Synced app commands globally (cleanup)")
                for guild_id in self.test_guild_ids:
                    guild = self.get_guild(guild_id)
                    if not guild:
                        logger.warning(
                            "Skipping command sync for guild %s: not a member of that guild.",
                            guild_id,
                        )
                        continue
                    try:
                        synced = await self.tree.sync(guild=guild)
                        logger.info("✅ Synced %d app commands for guild %s", len(synced), guild_id)
                    except discord.Forbidden:
                        logger.warning(
                            "Missing access syncing commands for guild %s; skipping.",
                            guild_id,
                        )
            else:
                synced = await self.tree.sync()
                logger.info("Γ£à Synced %d app commands globally", len(synced))
            self._synced = True
        except Exception:
            logger.exception("Failed to sync application commands on ready")

        # Send startup message to bot channels
        await self._send_startup_message()

    async def _send_startup_message(self) -> None:
        """Send a startup message to bot channels in all guilds."""
        preferred_names = ("bot", "bots", "bot-commands", "commands", "general")
        
        for guild in self.guilds:
            channel = None
            
            # Try to find a suitable channel
            for name in preferred_names:
                channel = discord.utils.get(guild.text_channels, name=name)
                if channel:
                    perms = channel.permissions_for(guild.me)
                    if perms.send_messages:
                        break
                    channel = None
            
            # Fallback to system channel
            if not channel and guild.system_channel:
                perms = guild.system_channel.permissions_for(guild.me)
                if perms.send_messages:
                    channel = guild.system_channel
            
            # Fallback to first available text channel
            if not channel:
                for text_channel in guild.text_channels:
                    perms = text_channel.permissions_for(guild.me)
                    if perms.send_messages:
                        channel = text_channel
                        break
            
            # Send the startup message
            if channel:
                try:
                    # Delete ALL previous welcome messages if they exist
                    if guild.id in self._welcome_messages:
                        deleted_count = 0
                        for old_message_id in self._welcome_messages[guild.id]:
                            try:
                                old_message = await channel.fetch_message(old_message_id)
                                await old_message.delete()
                                deleted_count += 1
                            except discord.NotFound:
                                pass  # Message already deleted
                            except discord.Forbidden:
                                logger.warning("No permission to delete welcome message %s in guild %s", old_message_id, guild.name)
                            except Exception as e:
                                logger.warning("Could not delete welcome message %s in guild %s: %s", old_message_id, guild.name, e)
                        
                        if deleted_count > 0:
                            logger.info("Deleted %d previous welcome message(s) in guild %s", deleted_count, guild.name)
                        
                        # Clear the list after attempting deletions
                        self._welcome_messages[guild.id] = []
                    
                    embed = discord.Embed(
                        title="≡ƒª¢ Baby Hippo is Online!",
                        description="Hello! I'm ready to help with translations, roles, and more. Use `/help` to see what I can do!",
                        color=discord.Color.green(),
                    )
                    new_message = await channel.send(embed=embed)
                    
                    # Store message ID for next restart
                    if guild.id not in self._welcome_messages:
                        self._welcome_messages[guild.id] = []
                    self._welcome_messages[guild.id].append(new_message.id)
                    
                    logger.info("Sent startup message to guild %s in channel %s", guild.name, channel.name)
                except Exception as e:
                    logger.warning("Failed to send startup message to guild %s: %s", guild.name, e)

    def add_post_setup_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        self._post_setup_hooks.append(hook)

    async def setup_hook(self) -> None:
        await super().setup_hook()
        for hook in self._post_setup_hooks:
            try:
                await hook()
            except Exception:
                logger.exception("Post-setup hook failed")


class IntegrationLoader:
    """
    Orchestrates engine wiring, dependency injection, and cog mounting.

    See `ARCHITECTURE.md` for dependency direction and anti-cycle rules. This
    loader is the only module that imports both engines and cogs and wires event
    topics defined in `core/event_topics.py`.
    """

    def __init__(self) -> None:
        # Core infrastructure
        self.event_bus = EventBus()
        self.registry = EngineRegistry(event_bus=self.event_bus)
        self.bot: Optional[HippoBot] = None
        
        # Guardian configuration
        self._guardian_auto_disable = os.getenv("GUARDIAN_SAFE_MODE", "0") == "1"

        # Guardian error engine
        self.error_engine = GuardianErrorEngine(event_bus=self.event_bus)
        self.error_engine.attach_registry(self.registry)

        # New KVK Tracking System
        self.kvk_storage_engine = KVKStorageEngine()
        self.kvk_tracker_engine = KVKTrackerEngine(storage_engine=self.kvk_storage_engine)

        # Language metadata helpers
        raw_language_map = load_language_map() if callable(load_language_map) else None
        self.language_map = raw_language_map or {}
        self.alias_helper = LanguageAliasHelper() if LanguageAliasHelper else None
        if self.alias_helper and self.language_map:
            try:
                self.alias_helper.load_from_language_map(self.language_map)
            except Exception:
                logger.debug("Failed to extend language alias helper from language_map.json", exc_info=True)

        # Core engines
        self.cache_manager = CacheManager()
        self.role_manager = RoleManager(
            cache_manager=self.cache_manager,
            error_engine=self.error_engine,
            alias_helper=self.alias_helper,
            language_map=self.language_map,
        )
        self.personality_engine = PersonalityEngine(cache_manager=self.cache_manager)
        self.processing_engine = ProcessingEngine(cache_manager=self.cache_manager, error_engine=self.error_engine)
        self.output_engine = OutputEngine(error_engine=self.error_engine)

        # Localization / NLP
        self.localization_registry = LanguageRegistry()
        self.detector = HeuristicDetector()
        self.nlp_processor = NLPProcessor()
        self.policy_repository = PolicyRepository()
        self.session_memory = SessionMemory()
        self.context_memory = ContextMemory()

        # Game system engines
        from discord_bot.games.storage.game_storage_engine import GameStorageEngine
        from discord_bot.core.engines.relationship_manager import RelationshipManager
        from discord_bot.core.engines.cookie_manager import CookieManager
        from discord_bot.games.pokemon_game import PokemonGame
        from discord_bot.games.pokemon_api_integration import PokemonAPIIntegration
        from discord_bot.games.pokemon_data_manager import PokemonDataManager
        
        self.game_storage = GameStorageEngine(db_path="data/game_data.db")
        self.kvk_tracker_engine.attach_tracker(KVKTracker(storage=self.game_storage))
        self.relationship_manager = RelationshipManager(storage=self.game_storage)
        self.cookie_manager = CookieManager(
            storage=self.game_storage,
            relationship_manager=self.relationship_manager
        )
        if hasattr(self.personality_engine, "set_relationship_manager"):
            self.personality_engine.set_relationship_manager(self.relationship_manager)
        # Initialize PokemonDataManager with configurable cache path
        self.pokemon_data_manager = PokemonDataManager(cache_file="pokemon_base_stats_cache.json")
        self.pokemon_game = PokemonGame(
            storage=self.game_storage,
            cookie_manager=self.cookie_manager,
            relationship_manager=self.relationship_manager,
            data_manager=self.pokemon_data_manager
        )
        self.pokemon_api = PokemonAPIIntegration()
        logger.debug("Game system engines initialized")
        
        # Event reminder engine for Top Heroes events
        self.event_reminder_engine = EventReminderEngine(storage_engine=self.game_storage)
        logger.debug("Event reminder engine initialized")
        self.kvk_tracker = self.kvk_tracker_engine
        logger.debug("KVK tracker initialized")
        self.event_reminder_engine.kvk_tracker = self.kvk_tracker
        
        # Rankings and modlog channel IDs for KVK visual system
        self.rankings_channel_id = int(os.getenv("RANKINGS_CHANNEL_ID", "0")) or None
        self.modlog_channel_id = int(os.getenv("MODLOG_CHANNEL_ID", "0")) or None
        logger.debug(f"Rankings channel: {self.rankings_channel_id}, Modlog channel: {self.modlog_channel_id}")
        
        # Rankings and modlog channel IDs for KVK visual system
        self.rankings_channel_id = int(os.getenv("RANKINGS_CHANNEL_ID", "0")) or None
        self.modlog_channel_id = int(os.getenv("MODLOG_CHANNEL_ID", "0")) or None
        logger.debug(f"Rankings channel: {self.rankings_channel_id}, Modlog channel: {self.modlog_channel_id}")

        self.ambiguity_resolver = (
            AmbiguityResolver(
                role_manager=self.role_manager,
                cache_manager=self.cache_manager,
                language_map=self.language_map,
            )
            if AmbiguityResolver
            else None
        )
        if self.ambiguity_resolver and hasattr(self.role_manager, "ambiguity_resolver"):
            self.role_manager.ambiguity_resolver = self.ambiguity_resolver

        self.context_engine = ContextEngine(
            role_manager=self.role_manager,
            cache_manager=self.cache_manager,
            error_engine=self.error_engine,
            alias_helper=self.alias_helper,
            ambiguity_resolver=self.ambiguity_resolver,
            localization_registry=self.localization_registry,
            detection_service=self.detector,
            policy_repository=self.policy_repository,
            context_memory=self.context_memory,
            session_memory=self.session_memory,
        )

        # Input engine is bot-bound and initialised in build()
        self.input_engine: Optional[InputEngine] = None

        # UI plugins
        self.translation_ui = TranslationUIEngine(event_bus=self.event_bus)
        self.admin_ui = AdminUIEngine(event_bus=self.event_bus)

        # Translators / orchestrator wiring
        self.deepl_adapter: Optional[DeepLAdapter] = None
        self.mymemory_adapter: Optional[MyMemoryAdapter] = None
        self.google_adapter = None  # GoogleTranslateAdapter (free tier fallback)
        self.openai_adapter: Optional[OpenAIAdapter] = None
        self.orchestrator: Optional[TranslationOrchestratorEngine] = None

    # ------------------------------------------------------------------
    # Adapter wiring
    # ------------------------------------------------------------------
    def _wire_translation_stack(self) -> None:
        """Initialise adapters and orchestrator, wiring them into the processing engine."""

        # DeepL
        try:
            deepl_key = os.getenv("DEEPL_API_KEY")
            if deepl_key:
                self.deepl_adapter = DeepLAdapter(api_key=deepl_key)
                logger.debug("DeepL adapter initialised")
            else:
                logger.debug("DEEPL_API_KEY not set; DeepL adapter disabled")
        except Exception:
            self.deepl_adapter = None
            logger.exception("Failed to initialise DeepLAdapter; continuing without it")

        # MyMemory
        try:
            mymemory_email = os.getenv("MYMEMORY_USER_EMAIL")
            mymemory_key = os.getenv("MYMEMORY_API_KEY")
            self.mymemory_adapter = MyMemoryAdapter(user_email=mymemory_email, api_key=mymemory_key)
            if mymemory_key:
                logger.debug("MyMemory adapter initialised with API key")
            elif mymemory_email:
                logger.debug("MyMemory adapter initialised with email identity")
            else:
                logger.debug("MyMemory adapter initialised without credentials (rate limits may apply)")
        except Exception:
            self.mymemory_adapter = None
            logger.exception("Failed to initialise MyMemoryAdapter; continuing without it")

        # Google Translate (free tier fallback for 100+ languages)
        try:
            self.google_adapter = create_google_translate_adapter()
            logger.debug("Google Translate adapter initialised (100+ languages)")
        except Exception:
            self.google_adapter = None
            logger.exception("Failed to initialise GoogleTranslateAdapter; continuing without it")

        # OpenAI (personality / LLM support)
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                self.openai_adapter = OpenAIAdapter(model=model)
                logger.debug("OpenAI adapter initialised for personality features (model=%s)", model)
            else:
                logger.debug("OPENAI_API_KEY not set; OpenAI adapter disabled")
        except Exception:
            self.openai_adapter = None
            logger.exception("Failed to initialise OpenAIAdapter; continuing without it")

        if self.personality_engine and hasattr(self.personality_engine, "set_ai_adapter"):
            try:
                self.personality_engine.set_ai_adapter(self.openai_adapter)
                if self.openai_adapter:
                    logger.debug("PersonalityEngine wired with OpenAI adapter")
                else:
                    logger.debug("PersonalityEngine operating without OpenAI adapter")
            except Exception:
                logger.exception("Failed to attach OpenAI adapter to PersonalityEngine")

        # Orchestrator
        try:
            self.orchestrator = TranslationOrchestratorEngine(
                deepl_adapter=self.deepl_adapter,
                mymemory_adapter=self.mymemory_adapter,
                google_adapter=self.google_adapter,
                detection_service=self.detector,
                nlp_processor=self.nlp_processor,
            )
            logger.info("TranslationOrchestratorEngine created (DeepL Γ₧£ MyMemory Γ₧£ Google Translate)")
        except Exception:
            self.orchestrator = None
            logger.exception("Failed to create TranslationOrchestratorEngine")

        # Attach orchestrator and adapters to processing engine and registry
        try:
            if self.orchestrator:
                if hasattr(self.processing_engine, "set_orchestrator"):
                    self.processing_engine.set_orchestrator(self.orchestrator)  # type: ignore[attr-defined]
                else:
                    setattr(self.processing_engine, "orchestrator", self.orchestrator)
                self.registry.inject("translation_orchestrator", self.orchestrator)

            if self.deepl_adapter and hasattr(self.processing_engine, "add_adapter"):
                self.processing_engine.add_adapter(self.deepl_adapter, provider_id="deepl", priority=10, timeout=6.0)  # type: ignore[attr-defined]
                self.registry.inject("deepl_adapter", self.deepl_adapter)
            if self.mymemory_adapter and hasattr(self.processing_engine, "add_adapter"):
                self.processing_engine.add_adapter(self.mymemory_adapter, provider_id="mymemory", priority=20, timeout=6.0)  # type: ignore[attr-defined]
                self.registry.inject("mymemory_adapter", self.mymemory_adapter)
            if self.google_adapter and hasattr(self.processing_engine, "add_adapter"):
                self.processing_engine.add_adapter(self.google_adapter, provider_id="google", priority=30, timeout=6.0)  # type: ignore[attr-defined]
                self.registry.inject("google_adapter", self.google_adapter)
            if self.openai_adapter:
                self.registry.inject("openai_adapter", self.openai_adapter)
        except Exception:
            logger.exception("Failed to wire translation adapters into ProcessingEngine")

    # ------------------------------------------------------------------
    # Bot build
    # ------------------------------------------------------------------
    def build_bot(self) -> HippoBot:
        """Constructs the bot instance with necessary intents and settings."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.messages = True
        intents.reactions = True

        owners = _parse_id_set(os.getenv("OWNER_IDS", ""))
        test_guilds = _parse_id_set(os.getenv("TEST_GUILDS", ""))

        self.bot = HippoBot(
            command_prefix=os.getenv("CMD_PREFIX", "!"),
            intents=intents,
            test_guild_ids=test_guilds,
            help_command=None,
        )
        self.event_reminder_engine.set_bot(self.bot)
        if hasattr(self.kvk_tracker_engine, "set_bot"):
            self.kvk_tracker_engine.set_bot(self.bot)

        logger.info("≡ƒ¢á∩╕Å Preparing engines and integrations")

        self.input_engine = InputEngine(
            bot=self.bot,
            context_engine=self.context_engine,
            processing_engine=self.processing_engine,
            output_engine=self.output_engine,
            cache_manager=self.cache_manager,
            role_manager=self.role_manager,
            alias_helper=getattr(self.context_engine, "alias_helper", None),
            ambiguity_resolver=getattr(self.context_engine, "ambiguity_resolver", None),
        )

        self.registry.register(self.translation_ui)
        self.registry.register(self.admin_ui)

        self._wire_translation_stack()

        # Inject dependencies
        self.registry.inject("engine_registry", self.registry)
        self.registry.inject("event_bus", self.event_bus)
        self.registry.inject("error_engine", self.error_engine)
        self.registry.inject("input_engine", self.input_engine)
        self.registry.inject("role_manager", self.role_manager)
        self.registry.inject("personality_engine", self.personality_engine)
        self.registry.inject("cache_manager", self.cache_manager)
        self.registry.inject("localization_registry", self.localization_registry)
        self.registry.inject("processing_engine", self.processing_engine)
        self.registry.inject("output_engine", self.output_engine)
        self.registry.inject("context_engine", self.context_engine)
        self.registry.inject("policy_repository", self.policy_repository)
        self.registry.inject("session_memory", self.session_memory)
        self.registry.inject("context_memory", self.context_memory)
        
        # Inject game system dependencies
        self.registry.inject("game_storage", self.game_storage)
        self.registry.inject("relationship_manager", self.relationship_manager)
        self.registry.inject("cookie_manager", self.cookie_manager)
        self.registry.inject("pokemon_data_manager", self.pokemon_data_manager)
        self.registry.inject("pokemon_game", self.pokemon_game)
        self.registry.inject("pokemon_api", self.pokemon_api)
        self.registry.inject("event_reminder_engine", self.event_reminder_engine)
        self.registry.inject("kvk_tracker", self.kvk_tracker)
        logger.debug("Game system engines registered")

        # Event Engines
        kvk_parser_engine = KVKParserEngine(event_bus=self.event_bus)
        gar_parser_engine = GARParserEngine(event_bus=self.event_bus)
        compare_engine = CompareEngine(event_bus=self.event_bus)
        event_engine = EventEngine(
            self.bot,  # Pass bot instance
            event_bus=self.event_bus,
            kvk_parser_engine=kvk_parser_engine,
            gar_parser_engine=gar_parser_engine,
            compare_engine=compare_engine,
        )
        self.registry.register(kvk_parser_engine)
        self.registry.register(gar_parser_engine)
        self.registry.register(compare_engine)
        self.registry.register(event_engine)
        self.event_engine = event_engine

        self._expose_bot_attributes()

        self.registry.enable("translation_ui_engine")
        self.registry.enable("admin_ui_engine")
        logger.debug("Enabled UI engines: translation_ui_engine, admin_ui_engine")
        self._log_registry_snapshot(context="post-enable")

        self._attach_core_listeners()
        
        # Register command groups needed by ranking cog (kvk parent group)
        # The kvk_ranking subgroup will be auto-registered when the cog is added
        from discord_bot.core import ui_groups
        self.bot.tree.add_command(ui_groups.kvk, override=True)
        logger.info("Γ£à Registered kvk command group for ranking cog")
        
        async def mount_cogs() -> None:
            await self._mount_cogs(owners)

        self.bot.add_post_setup_hook(mount_cogs)

        # Resume KVK runs on bot ready (if the method exists)
        async def resume_kvk_runs() -> None:
            if hasattr(self.kvk_tracker_engine, 'on_ready'):
                await self.kvk_tracker_engine.on_ready()

        self.bot.add_post_setup_hook(resume_kvk_runs)

        # self.bot.add_post_setup_hook(self.registry.on_bot_ready)  # Method doesn't exist
        self.bot.add_post_setup_hook(self.kvk_tracker_engine.on_startup)

        if self._guardian_auto_disable:
            logger.warning("Guardian SAFE MODE auto-disable is ENABLED (GUARDIAN_SAFE_MODE=1)")
        else:
            logger.debug("Guardian running in semi-automatic mode (no auto-disable)")

        self._log_registry_snapshot(context="ready")
        return self.bot

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _expose_bot_attributes(self) -> None:
        if not self.bot:
            return

        mapping = {
            "engine_registry": self.registry,
            "event_bus": self.event_bus,
            "error_engine": self.error_engine,
            "input_engine": self.input_engine,
            "processing_engine": self.processing_engine,
            "output_engine": self.output_engine,
            "context_engine": self.context_engine,
            "cache_manager": self.cache_manager,
            "role_manager": self.role_manager,
            "personality_engine": self.personality_engine,
            "localization_registry": self.localization_registry,
            "translation_ui": self.translation_ui,
            "admin_ui": self.admin_ui,
            "language_map": self.language_map,
            "alias_helper": self.alias_helper,
            "openai_adapter": self.openai_adapter,
            "policy_repository": self.policy_repository,
            "session_memory": self.session_memory,
            "context_memory": self.context_memory,
            # Game system
            "game_storage": self.game_storage,
            "relationship_manager": self.relationship_manager,
            "cookie_manager": self.cookie_manager,
            "pokemon_data_manager": self.pokemon_data_manager,
            "pokemon_game": self.pokemon_game,
            "pokemon_api": self.pokemon_api,
            "event_reminder_engine": self.event_reminder_engine,
            "kvk_tracker": self.kvk_tracker,
        }

        orchestrator = getattr(self.processing_engine, "orchestrator", None) or self.orchestrator
        if orchestrator:
            mapping["translation_orchestrator"] = orchestrator

        for name, value in mapping.items():
            if value is None:
                continue
            setattr(self.bot, name, value)

        if self.role_manager and hasattr(self.role_manager, "bot"):
            self.role_manager.bot = self.bot

    def _log_registry_snapshot(self, *, context: str) -> None:
        status = self.registry.status()
        ready = sorted(name for name, info in status.items() if info.get("ready"))
        waiting = {name: tuple(sorted(info.get("waiting_for", []))) for name, info in status.items() if not info.get("ready")}

        parts: list[str] = []
        if ready:
            parts.append(f"Γ£à ready: {', '.join(ready)}")
        if waiting:
            waiting_parts = []
            for name, deps in waiting.items():
                if deps:
                    waiting_parts.append(f"{name} (waiting: {', '.join(deps)})")
                else:
                    waiting_parts.append(name)
            parts.append(f"ΓÅ│ waiting: {', '.join(waiting_parts)}")
        summary = " | ".join(parts) if parts else "no registered engines"
        logger.info("≡ƒôª Engine registry snapshot (%s): %s", context, summary)

    async def _mount_cogs(self, owners: Iterable[int]) -> None:
        if not self.bot:
            return
        try:
            from discord_bot.cogs.translation_cog import setup_translation_cog
            from discord_bot.cogs.admin_cog import AdminCog
            from discord_bot.cogs.help_cog import setup as setup_help_cog
            from discord_bot.cogs.role_management_cog import setup as setup_language_cog
            from discord_bot.cogs.sos_phrase_cog import setup as setup_sos_cog
            from discord_bot.cogs.easteregg_cog import EasterEggCog
            from discord_bot.cogs.game_cog import GameCog
            from discord_bot.cogs.event_management_cog import setup as setup_event_cog
            from discord_bot.core.engines.screenshot_processor import ScreenshotProcessor
            from discord_bot.core.engines.ranking_storage_engine import RankingStorageEngine

            await setup_translation_cog(self.bot, ui_engine=self.translation_ui)
            await self.bot.add_cog(AdminCog(self.bot, ui_engine=self.admin_ui, owners=set(owners), storage=self.game_storage, cookie_manager=self.cookie_manager, event_engine=self.event_engine))
            await setup_help_cog(self.bot)
            await setup_language_cog(self.bot)
            await setup_sos_cog(self.bot)
            await setup_event_cog(self.bot, event_reminder_engine=self.event_reminder_engine)
            ranking_processor = ScreenshotProcessor()
            ranking_storage = RankingStorageEngine(storage=self.game_storage)
            ranking_cog_name = "UnifiedRankingCog"

            # Prefer EnhancedKVKRankingCog with Guardian wiring; fall back to unified ranking cog if needed.
            try:
                from discord_bot.cogs.kvk_visual_cog import EnhancedKVKRankingCog

                kvk_visual_cog = EnhancedKVKRankingCog(self.bot)
                await kvk_visual_cog.setup_dependencies(
                    kvk_tracker=self.kvk_tracker,
                    storage=ranking_storage,
                    guardian=self.error_engine,
                    rankings_channel_id=getattr(self, "rankings_channel_id", None),
                    modlog_channel_id=getattr(self, "modlog_channel_id", None),
                )
                await self.bot.add_cog(kvk_visual_cog, override=True)
                ranking_cog_name = "EnhancedKVKRankingCog"
                logger.info("? Mounted EnhancedKVKRankingCog with guardian integration")
            except Exception:
                logger.exception("Failed to mount EnhancedKVKRankingCog; falling back to UnifiedRankingCog")
                from discord_bot.cogs.unified_ranking_cog import setup as setup_unified_ranking_cog

                await setup_unified_ranking_cog(
                    self.bot,
                    processor=ranking_processor,
                    storage=ranking_storage,
                    guardian=self.error_engine,
                )
            
            # Mount game system cogs with dependency injection
            easter_egg_cog = EasterEggCog(
                bot=self.bot,
                relationship_manager=self.relationship_manager,
                cookie_manager=self.cookie_manager,
                personality_engine=self.personality_engine
            )
            await self.bot.add_cog(easter_egg_cog)
            
            game_cog = GameCog(
                bot=self.bot,
                pokemon_game=self.pokemon_game,
                pokemon_api=self.pokemon_api,
                storage=self.game_storage,
                cookie_manager=self.cookie_manager,
                relationship_manager=self.relationship_manager,
                personality_engine=self.personality_engine
            )
            await self.bot.add_cog(game_cog)
            
            setattr(self.bot, "ranking_processor", ranking_processor)
            setattr(self.bot, "ranking_storage", ranking_storage)
            logger.info(
                "?? Mounted cogs: translation, admin, help, language, sos, events, %s, easteregg, game",
                ranking_cog_name,
            )

            diagnostics_enabled = os.getenv("ENABLE_OCR_DIAGNOSTICS", "false").strip().lower() in {"1", "true", "yes", "on"}
            if diagnostics_enabled:
                try:
                    from discord_bot.cogs.image_diagnostic_cog import setup as setup_image_diagnostics_cog
                    from discord_bot.cogs.ocr_report_cog import setup as setup_ocr_report_cog

                    await setup_image_diagnostics_cog(self.bot)
                    await setup_ocr_report_cog(self.bot, ranking_storage)
                    logger.info("Mounted OCR diagnostic cogs (!testimg/!preprocess/!ocr and /ocr_report).")
                except Exception:
                    logger.exception("Failed to mount OCR diagnostic cogs")
        except Exception as exc:
            logger.exception("Failed to mount cogs")
            try:
                # Report cog mount errors through the standard error topic.
                await self.event_bus.emit(
                    ENGINE_ERROR,
                    name="integration_loader",
                    category="cog",
                    severity="error",
                    exc=exc,
                )
            except Exception:
                logger.exception("event_bus.emit failed while reporting cog mount error")

    def _attach_core_listeners(self) -> None:
        if not self.bot or not self.input_engine:
            return

        @self.bot.event
        async def on_message(message: discord.Message) -> None:
            try:
                await self.input_engine.handle_message(message)
            except Exception as exc:
                logger.exception("on_message handler failed")
                try:
                    await self.event_bus.emit(
                        ENGINE_ERROR,
                        name="input_engine",
                        category="event",
                        severity="error",
                        exc=exc,
                        context={"event": "on_message"},
                    )
                except Exception:
                    logger.exception("event_bus.emit failed while reporting on_message error")

        @self.bot.event
        async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
            try:
                if hasattr(self.input_engine, "handle_raw_reaction_add"):
                    await self.input_engine.handle_raw_reaction_add(payload)
                elif hasattr(self.input_engine, "handle_reaction_add"):
                    await self.input_engine.handle_reaction_add(payload)
            except Exception as exc:
                logger.exception("on_raw_reaction_add handler failed")
                try:
                    await self.event_bus.emit(
                        ENGINE_ERROR,
                        name="input_engine",
                        category="event",
                        severity="error",
                        exc=exc,
                        context={"event": "on_raw_reaction_add"},
                    )
                except Exception:
                    logger.exception("event_bus.emit failed while reporting reaction error")


def build_application() -> Tuple[HippoBot, EngineRegistry]:
    """Entry point used by main.py."""
    loader = IntegrationLoader()
    bot = loader.build_bot()
    return bot, loader.registry

from __future__ import annotations

import os
from typing import Any, Awaitable, Callable, Iterable, Optional, Set, Tuple

import discord
from discord.ext import commands

from discord_bot.core.engines.admin_ui_engine import AdminUIEngine
from discord_bot.core.engines.base.engine_registry import EngineRegistry
from discord_bot.core.engines.base.logging_utils import get_logger
from discord_bot.core.engines.cache_manager import CacheManager
from discord_bot.core.engines.error_engine import GuardianErrorEngine
from discord_bot.core.engines.event_reminder_engine import EventReminderEngine
from discord_bot.core.engines.input_engine import InputEngine
from discord_bot.core.engines.output_engine import OutputEngine
from discord_bot.core.engines.personality_engine import PersonalityEngine
from discord_bot.core.engines.processing_engine import ProcessingEngine
from discord_bot.core.engines.role_manager import RoleManager
from discord_bot.core.engines.translation_orchestrator import TranslationOrchestratorEngine
from discord_bot.core.engines.translation_ui_engine import TranslationUIEngine
from discord_bot.core.event_bus import EventBus
from discord_bot.core.event_topics import ENGINE_ERROR
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

    async def on_ready(self) -> None:
        logger.info("🦛 HippoBot logged in as %s (%s)", self.user, getattr(self.user, "id", "-"))
        if self._synced:
            return

        try:
            if self.test_guild_ids:
                # Always perform a global sync first so legacy global commands are cleaned up.
                await self.tree.sync()
                logger.debug("Synced app commands globally (cleanup)")
                for guild_id in self.test_guild_ids:
                    await self.tree.sync(guild=discord.Object(id=guild_id))
                    logger.debug("Synced app commands for guild %s", guild_id)
            else:
                await self.tree.sync()
                logger.debug("Synced app commands globally")
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
                    embed = discord.Embed(
                        title="🦛 Baby Hippo is Online!",
                        description="Hello! I'm ready to help with translations, roles, and more. Use `/help` to see what I can do!",
                        color=discord.Color.green(),
                    )
                    await channel.send(embed=embed)
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

        # Guardian error engine
        self.error_engine = GuardianErrorEngine(event_bus=self.event_bus)
        self.error_engine.attach_registry(self.registry)
        self._guardian_auto_disable = str(os.getenv("GUARDIAN_SAFE_MODE", "0")).lower() in {"1", "true", "yes"}

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
        
        self.game_storage = GameStorageEngine(db_path="game_data.db")
        self.relationship_manager = RelationshipManager(storage=self.game_storage)
        self.cookie_manager = CookieManager(
            storage=self.game_storage,
            relationship_manager=self.relationship_manager
        )
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
            logger.info("TranslationOrchestratorEngine created (DeepL ➜ MyMemory ➜ Google Translate)")
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
            if self.openai_adapter:
                self.registry.inject("openai_adapter", self.openai_adapter)
        except Exception:
            logger.exception("Failed to wire translation adapters into ProcessingEngine")

    # ------------------------------------------------------------------
    # Bot build
    # ------------------------------------------------------------------
    def build(self) -> Tuple[HippoBot, EngineRegistry]:
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

        logger.info("🛠️ Preparing engines and integrations")

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
        logger.debug("Game system engines registered")

        self._expose_bot_attributes()

        self.registry.enable("translation_ui_engine")
        self.registry.enable("admin_ui_engine")
        logger.debug("Enabled UI engines: translation_ui_engine, admin_ui_engine")
        self._log_registry_snapshot(context="post-enable")

        self._attach_core_listeners()
        async def mount_cogs() -> None:
            await self._mount_cogs(owners)

        self.bot.add_post_setup_hook(mount_cogs)

        if self._guardian_auto_disable:
            logger.warning("Guardian SAFE MODE auto-disable is ENABLED (GUARDIAN_SAFE_MODE=1)")
        else:
            logger.debug("Guardian running in semi-automatic mode (no auto-disable)")

        self._log_registry_snapshot(context="ready")
        return self.bot, self.registry

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
            parts.append(f"✅ ready: {', '.join(ready)}")
        if waiting:
            waiting_parts = []
            for name, deps in waiting.items():
                if deps:
                    waiting_parts.append(f"{name} (waiting: {', '.join(deps)})")
                else:
                    waiting_parts.append(name)
            parts.append(f"⏳ waiting: {', '.join(waiting_parts)}")
        summary = " | ".join(parts) if parts else "no registered engines"
        logger.info("📦 Engine registry snapshot (%s): %s", context, summary)

    async def _mount_cogs(self, owners: Iterable[int]) -> None:
        if not self.bot:
            return
        try:
            from discord_bot.cogs.translation_cog import setup_translation_cog
            from discord_bot.cogs.admin_cog import setup_admin_cog
            from discord_bot.cogs.help_cog import setup as setup_help_cog
            from discord_bot.cogs.role_management_cog import setup as setup_language_cog
            from discord_bot.cogs.sos_phrase_cog import setup as setup_sos_cog
            from discord_bot.cogs.easteregg_cog import EasterEggCog
            from discord_bot.cogs.game_cog import GameCog
            from discord_bot.cogs.event_management_cog import setup as setup_event_cog

            await setup_translation_cog(self.bot, ui_engine=self.translation_ui)
            await setup_admin_cog(self.bot, ui_engine=self.admin_ui, owners=set(owners), storage=self.game_storage, cookie_manager=self.cookie_manager)
            await setup_help_cog(self.bot)
            await setup_language_cog(self.bot)
            await setup_sos_cog(self.bot)
            await setup_event_cog(self.bot, event_reminder_engine=self.event_reminder_engine)
            
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
            
            logger.info("⚙️ Mounted cogs: translation, admin, help, language, sos, events, easteregg, game")
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
    return loader.build()

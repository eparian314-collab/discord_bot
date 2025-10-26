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
from discord_bot.core.engines.input_engine import InputEngine
from discord_bot.core.engines.output_engine import OutputEngine
from discord_bot.core.engines.personality_engine import PersonalityEngine
from discord_bot.core.engines.processing_engine import ProcessingEngine
from discord_bot.core.engines.role_manager import RoleManager
from discord_bot.core.engines.translation_orchestrator import TranslationOrchestratorEngine
from discord_bot.core.engines.translation_ui_engine import TranslationUIEngine
from discord_bot.core.event_bus import EventBus
from discord_bot.language_context.context_engine import ContextEngine
from discord_bot.language_context.detectors.heuristics import HeuristicDetector
from discord_bot.language_context.detectors.nlp_model import NLPProcessor
from discord_bot.language_context.localization import LanguageRegistry
from discord_bot.language_context.translators.deepl_adapter import DeepLAdapter
from discord_bot.language_context.translators.mymemory_adapter import MyMemoryAdapter
from discord_bot.language_context.translators.openai_adapter import OpenAIAdapter

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
        logger.info("Logged in as %s (%s)", self.user, getattr(self.user, "id", "-"))
        if self._synced:
            return

        try:
            if self.test_guild_ids:
                for guild_id in self.test_guild_ids:
                    await self.tree.sync(guild=discord.Object(id=guild_id))
                    logger.info("Synced app commands for guild %s", guild_id)
            else:
                await self.tree.sync()
                logger.info("Synced app commands globally")
            self._synced = True
        except Exception:
            logger.exception("Failed to sync application commands on ready")

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
    """Orchestrates engine wiring, dependency injection, and cog mounting."""

    def __init__(self) -> None:
        # Core infrastructure
        self.event_bus = EventBus()
        self.registry = EngineRegistry(event_bus=self.event_bus)
        self.bot: Optional[HippoBot] = None

        # Guardian error engine
        self.error_engine = GuardianErrorEngine(event_bus=self.event_bus)
        self.error_engine.attach_registry(self.registry)
        self._guardian_auto_disable = str(os.getenv("GUARDIAN_SAFE_MODE", "0")).lower() in {"1", "true", "yes"}

        # Core engines
        self.cache_manager = CacheManager()
        self.role_manager = RoleManager(cache_manager=self.cache_manager, error_engine=self.error_engine)
        self.personality_engine = PersonalityEngine(cache_manager=self.cache_manager)
        self.processing_engine = ProcessingEngine(cache_manager=self.cache_manager, error_engine=self.error_engine)
        self.output_engine = OutputEngine(error_engine=self.error_engine)
        self.context_engine = ContextEngine(
            role_manager=self.role_manager,
            cache_manager=self.cache_manager,
            error_engine=self.error_engine,
        )

        # Localization / NLP
        self.localization_registry = LanguageRegistry()
        self.detector = HeuristicDetector()
        self.nlp_processor = NLPProcessor()

        # Input engine is bot-bound and initialised in build()
        self.input_engine: Optional[InputEngine] = None

        # UI plugins
        self.translation_ui = TranslationUIEngine(event_bus=self.event_bus)
        self.admin_ui = AdminUIEngine(event_bus=self.event_bus)

        # Translators / orchestrator wiring
        self.deepl_adapter: Optional[DeepLAdapter] = None
        self.mymemory_adapter: Optional[MyMemoryAdapter] = None
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
                logger.info("DeepL adapter initialised")
            else:
                logger.info("DEEPL_API_KEY not set; DeepL adapter disabled")
        except Exception:
            self.deepl_adapter = None
            logger.exception("Failed to initialise DeepLAdapter; continuing without it")

        # MyMemory
        try:
            mymemory_email = os.getenv("MYMEMORY_USER_EMAIL")
            mymemory_key = os.getenv("MYMEMORY_API_KEY")
            self.mymemory_adapter = MyMemoryAdapter(user_email=mymemory_email, api_key=mymemory_key)
            if mymemory_key:
                logger.info("MyMemory adapter initialised with API key")
            elif mymemory_email:
                logger.info("MyMemory adapter initialised with email identity")
            else:
                logger.info("MyMemory adapter initialised without credentials (rate limits may apply)")
        except Exception:
            self.mymemory_adapter = None
            logger.exception("Failed to initialise MyMemoryAdapter; continuing without it")

        # OpenAI
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                self.openai_adapter = OpenAIAdapter(model=model)
                logger.info("OpenAI adapter initialised (model=%s)", model)
            else:
                logger.info("OPENAI_API_KEY not set; OpenAI adapter disabled")
        except Exception:
            self.openai_adapter = None
            logger.exception("Failed to initialise OpenAIAdapter; continuing without it")

        # Orchestrator
        try:
            self.orchestrator = TranslationOrchestratorEngine(
                deepl_adapter=self.deepl_adapter,
                mymemory_adapter=self.mymemory_adapter,
                openai_adapter=self.openai_adapter,
                detection_service=self.detector,
                nlp_processor=self.nlp_processor,
            )
            logger.info("TranslationOrchestratorEngine created")
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
            if self.openai_adapter and hasattr(self.processing_engine, "add_adapter"):
                self.processing_engine.add_adapter(self.openai_adapter, provider_id="openai", priority=30, timeout=10.0)  # type: ignore[attr-defined]
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

        logger.info("Bootstrapping engines and integrations")

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

        self._expose_bot_attributes()

        self.registry.enable("translation_ui_engine")
        self.registry.enable("admin_ui_engine")
        logger.info("Enabled UI engines: translation_ui_engine, admin_ui_engine")

        self._attach_core_listeners()
        async def mount_cogs() -> None:
            await self._mount_cogs(owners)

        self.bot.add_post_setup_hook(mount_cogs)

        if self._guardian_auto_disable:
            logger.warning("Guardian SAFE MODE auto-disable is ENABLED (GUARDIAN_SAFE_MODE=1)")
        else:
            logger.info("Guardian running in semi-automatic mode (no auto-disable)")

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
        }

        orchestrator = getattr(self.processing_engine, "orchestrator", None) or self.orchestrator
        if orchestrator:
            mapping["translation_orchestrator"] = orchestrator

        for name, value in mapping.items():
            if value is None:
                continue
            setattr(self.bot, name, value)

    async def _mount_cogs(self, owners: Iterable[int]) -> None:
        if not self.bot:
            return
        try:
            from discord_bot.cogs.translation_cog import setup_translation_cog
            from discord_bot.cogs.admin_cog import setup_admin_cog
            from discord_bot.cogs.help_cog import setup as setup_help_cog
            from discord_bot.cogs.role_management_cog import setup as setup_language_cog
            from discord_bot.cogs.sos_phrase_cog import setup as setup_sos_cog

            await setup_translation_cog(self.bot, ui_engine=self.translation_ui)
            await setup_admin_cog(self.bot, ui_engine=self.admin_ui, owners=set(owners))
            await setup_help_cog(self.bot)
            await setup_language_cog(self.bot)
            await setup_sos_cog(self.bot)
            logger.info("Mounted cogs: translation, admin, help, language, sos")
        except Exception as exc:
            logger.exception("Failed to mount cogs")
            try:
                await self.event_bus.emit(
                    "engine.error",
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
                        "engine.error",
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
                        "engine.error",
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

applyTo: "**"
description: "Authoritative build + debug instructions for HippoBot. All models and IDE copilots must follow this."

# 🦛 HippoBot — Master Architectural Instructions

HippoBot is a modular Discord bot built on strict layered architecture:

> Engines initialize first → registered into the EngineRegistry → attached to bot.ctx → cogs mount last.

This rule is absolute. **No cog or UI component may create its own engines.** No direct imports *upstream*.

---

## 🎯 Mission & Design Pillars
- Multilingual community support (auto translation + adaptive language UI)
- Top Heroes event + KVK + GAR ranking pipeline (OCR → validation → storage → reporting)
- Game & economy subsystems (cookies, relationship engine, Pokémon microgame)
- Strict modularity: **Input → Context → Processing → Output** with no cycles

The bot does **not** allow “helpful refactors" unless explicitly requested.
Stability > cleverness.

---

## 📁 Project Structure

discord_bot/
│ main.py → startup entrypoint
│ bot.py / hippo_bot.py → Bot class
│
├─ integrations/
│ integration_loader.py → Builds engines, attaches bot.ctx, mounts cogs, syncs slash cmds
│
├─ core/
│ engines/ → Business logic (no discord imports)
│ translation/
│ ranking/
│ kvk/
│ gar/
│ compare_engine.py
│ EventBus, EngineRegistry, CacheManager, GuardianErrorEngine, RoleManager (etc.)
│
├─ cogs/ → Discord-facing behavior
│ translation_cog.py
│ admin_cog.py
│ ranking_cog.py
│ game_cog.py
│ easteregg_cog.py
│ ...
│
├─ games/ → Pokémon + cookie systems
│
├─ data/ → SQLite runtime DBs
│
├─ scripts/ → operational tools & sync utilities
│
└─ docs/ → Markdown system documentation & SOPs

yaml
Copy code

---

## 🧠 Boot Order (Non-negotiable)

[1] Instantiate EventBus + EngineRegistry
[2] Initialize Core Engines (ErrorEngine, Cache, RoleManager, Translation)
[3] Initialize Game / Ranking / Parser / Comparison engines
[4] Register all engines in EngineRegistry
[5] Attach to bot:
bot.ctx = BotContext(event_bus, engine_registry)
[6] THEN mount cogs (bot.add_cog(...))
[7] THEN sync slash commands (prefer guild sync in development)

python
Copy code

**If you reverse this order, the bot will boot but ranking & translation will silently fail.**

---

## 🔌 Cog Dependency Pattern (Mandated)

Every cog receives services like this:

```python
class RankingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.registry = bot.ctx.registry
        self.events = bot.ctx.event_bus
        self.kvk = self.registry.get("kvk_parser_engine")
        self.gar = self.registry.get("gar_parser_engine")
        self.compare = self.registry.get("compare_engine")
No direct imports from engines inside cogs.
No global singletons.
Cogs do not construct engines.

🌍 Environment & Secrets
ini
Copy code
DISCORD_TOKEN=
DEEPL_API_KEY=
MY_MEMORY_API_KEY=
OPEN_AI_API_KEY=

RANKINGS_CHANNEL_ID=
MODLOG_CHANNEL_ID=
BOT_CHANNEL_ID=
ALLOWED_CHANNELS=comma,separated,ids
If RANKINGS_CHANNEL_ID is not in ALLOWED_CHANNELS, submissions will be rejected.

🔡 Translation System (Summary)
Priority fallback chain:
DeepL → MyMemory → Google Translate

Language detection + context memory lives in language_context/

UI layer is always server-language-aware

🏆 Ranking System (High Level)
pgsql
Copy code
User uploads screenshot → OCR (Tesseract) → Extracted features validated →
Saved to SQLite → Leaderboard + comparison engine → Visual UI feedback
Documentation lives in:
docs/RANKING_SYSTEM.md, docs/RANKING_ADMIN.md, docs/RANKING_WEEKLY_SYSTEM.md.

🧪 Testing Workflow
bash
Copy code
python scripts/preflight_check.py
pytest
python scripts/sync_commands.py --guild <id>
python main.py
OCR testing: place sample images in /test_data/screenshots/ and call parser directly.

⚠️ Safety Rules (Critical)
Do not auto-refactor imports.

Do not collapse directory trees.

Do not create new engines inside a cog.

Do not modify EngineRegistry signatures without explicit request.

Never remove or bypass bot.ctx — it is the spine of the architecture.
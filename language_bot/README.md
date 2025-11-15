
# LanguageBot

LanguageBot is a fully self-contained Discord bot project, located in the `language_bot` folder of the shared `discord_bot` monorepo. It is one of three independent bots (alongside FunBot and an upcoming third bot), each designed for separate deployment and operation.


## Project Philosophy

- **Self-contained:** LanguageBot does not rely on any code, configuration, or resources outside the `language_bot` directory. Treat this folder as the root and single source of truth for all LanguageBot logic, dependencies, and assets.
- **Monorepo Structure:** While LanguageBot shares the repository with other bots, it is architected for independent deployment and development. Similar principles apply to the other bot projects in this repo.
- **Focus:** LanguageBot specializes in language, translation, and communication features for Discord servers. It includes moderation support (admin/help) but is primarily designed for multilingual and language-related interactions.

## Features & Commands

LanguageBot offers a comprehensive set of features and commands, organized into modular cogs:

- **Translation & Language Utilities:**
	- `/translate` — Translate text to another language (context-aware, using non-OpenAI providers; replies ephemerally so you can experiment freely)
	- Right-click → **Apps → Translate message** — Translate any message in-place using your language roles (or the server default) and see one or more target languages in a compact embed
	- Automatic private translation of messages for mentioned users
	- Language detection and role-based translation targeting

- **Role Management:**
	- Auto-assign language roles when users send or react with flag emojis
	- `/language_sync` — Sync known language roles across the guild
	- Auto-create mentionable roles for new languages

- **SOS Phrase System:**
	- `/sos_add`, `/sos_remove`, `/sos_clear` — Manage emergency phrases for quick help
	- `/sos_phrase` — Send a pre-configured SOS message

- **Admin & Moderation:**
	- `/admin mute` / `/admin unmute` — Manage member timeouts
	- `/keyword set/list/remove/clear` — Manage keyword → phrase mappings

- **Help & Utility:**
	- `/help` — Interactive help and feature overview
	- Automated onboarding and welcome messages
	- Personality-driven responses and easter eggs

## Methods & Architecture

- Modular cog system for easy extension and maintenance
- Event-driven architecture using Discord.py's commands and app_commands
- Role-based permissions for admin and helper features
- Personality engine for dynamic, friendly bot responses
- Translation orchestrator and UI engine for context-aware, multi-provider translation
- Language directory and profile system for robust localization


## Running LanguageBot

Quickstart from the repo root:

```bash
cd language_bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DISCORD_TOKEN

# Recommended invocation (module mode ensures clean imports)
python -m language_bot.main

# Alternatively (script mode also works)
python ../language_bot/main.py
```

### Wiping stale slash commands from Discord

If Discord has stale or broken slash commands for LanguageBot and normal
syncing does not fix them, you can explicitly clear all registered
commands for this bot:

```bash
cd language_bot
export LANGUAGEBOT_WIPE_COMMANDS=1
python -m language_bot.main
```

On this special run LanguageBot will:

- Connect to Discord,
- Remove all existing global and test‑guild app commands owned by the bot,
- Log a completion message, and
- Skip re-registering commands.

After that, stop the bot, unset `LANGUAGEBOT_WIPE_COMMANDS`, and start it
normally again to resync a clean set of commands based on the current code.

Notes:
- LanguageBot loads environment variables from a `.env` file (via python-dotenv).
- Ensure `DISCORD_TOKEN` is set; otherwise startup raises a clear error.
- The entry sets `BOT_PROFILE=language` to enable the translation stack only.

---

For questions or contributions, treat the `language_bot` folder as the boundary for all LanguageBot-related work. Each bot in this repo is managed and deployed independently.


## Auto language roles & flag mapping

`LanguageRoleManager` ships with a curated `LanguageDirectory` that knows the common flag emojis, language aliases, and ISO codes. Users can earn the appropriate `LANGUAGE_ROLE_PREFIX` role (e.g., `lang-spanish`) by either:

- Sending a message that contains the target country's flag emoji (🇲🇽, 🇪🇸, 🇧🇷, 🇯🇵, etc.)
- Reacting to any message with that flag emoji

When no matching role exists, the bot will auto-create a mentionable role named with the configured prefix plus the map's slug (such as `lang-spanish`). The translation cog reads the same directory so every role slug resolves back to a concrete ISO code for provider calls. Update `language_bot/language_context/flag_map.py` if you need to add or override mappings for niche communities.



## One-touch bootstrap

`ready_set_go.sh` wraps the full lifecycle:

```bash
cd language_bot
./ready_set_go.sh          # compile + unit tests + bot runtime
./ready_set_go.sh --test-only   # smoke check without launching the bot
./ready_set_go.sh --skip-tests  # skip compile/tests when you just need the bot
```

By default the script creates/uses `../.venv`, installs `requirements.txt`, compiles the module tree, executes the lightweight unit tests in `language_bot/tests`, and only then starts `main.py`. Set `SKIP_PIP_INSTALL=1` when deploying on hosts where dependencies are baked into the image, and let systemd invoke the script directly for auto-restarts.

## Testing, coverage, and linting

Install the dev dependencies once:

```bash
pip install -r language_bot/requirements.txt
pip install -r language_bot/requirements-dev.txt
```

Run the full test suite (unit + integration + e2e simulators) with coverage:

```bash
pytest
```

Targeted suites are available via:

```bash
pytest language_bot/tests/integration
pytest language_bot/tests/e2e -k translation_end_to_end
```

Static analysis commands:

```bash
flake8 language_bot/
mypy language_bot/
pylint language_bot/
```

CI mirrors those commands via `.github/workflows/ci.yml`, so keeping them green locally guarantees green builds.

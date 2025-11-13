# LanguageBot
This bot focuses on language, translation, and interaction features from the HippoBot project.

## Running

```bash
python language_bot/main.py
```

This entry point forces the `BOT_PROFILE=language` mode, which limits the running cogs to the translation stack (translation, admin, help, role management, SOS phrases). You can override the selection via `BOT_COGS="translation,help"` if you need an ad-hoc combination while developing.

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

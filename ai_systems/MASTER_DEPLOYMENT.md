# Master Deployment & Operations Guide

This repo hosts multiple Discord bots in one codebase, but each bot is an independent project with its own runtime, dependencies, and config. You can run multiple bots on the same machine concurrently without coupling.

---

**Repo Rules**
- Independent projects: no cross-folder imports between bots.
- Separate env and deps: each bot uses its own `.venv`, requirements, and `.env`.
- Standalone entrypoints: start each bot via its own `main.py` (package module mode preferred).
- Shared host OK: multiple bots can run on the same instance under distinct services.

---

## Projects

- `fun_bot/` — Fun/game utilities and lightweight features
- `language_bot/` — Translation, language roles, and communication tools
- `ai_systems/` — Master docs (this file)

---

## Local Quickstart (Per Bot)

- Create venv and install deps
  - `cd fun_bot && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
  - `cd language_bot && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

- Configure env
  - Copy `.env.example` to `.env` inside each bot folder.
  - Set `DISCORD_TOKEN` (required). LanguageBot may also require provider keys per feature.

- Run the bot (recommended)
  - FunBot: `python -m fun_bot.main`
  - LanguageBot: `python -m language_bot.main`

Notes
- Both bots load `.env` with `python-dotenv` in their runners.
- `python -m package.main` ensures clean import paths and avoids self-import issues.

---

## Running Both Bots Concurrently

- Use two shells (or tmux panes), each with its bot’s venv activated.
- Start FunBot and LanguageBot as separate processes; they do not share state.
- Alternatively, install systemd units for auto-restart and boot-time start.

---

## Systemd Services

- Provided unit files:
  - `fun_bot/hippo_funbot.service:1`
  - `language_bot/hippo_langbot.service:1`

- Expected usage
  - Copy each file to `/etc/systemd/system/` (adjust `User` and paths).
  - Ensure `WorkingDirectory` points to each bot’s folder and `ExecStart` to the `ready_set_go.sh` script.
  - `sudo systemctl daemon-reload && sudo systemctl enable --now hippo_funbot.service hippo_langbot.service`

- Notes
  - The scripts will create/activate a venv, install deps (unless `SKIP_PIP_INSTALL=1`), and run the bot in a restart loop.
  - FunBot script: `fun_bot/ready_set_go.sh:1`
  - LanguageBot script: `language_bot/ready_set_go.sh:1`

---

## Logging

- Each bot writes errors to rotating files in `logs/`:
  - FunBot: `logs/funbot_errors.log`
  - LanguageBot: `logs/langbot_errors.log`
- Handlers are guarded to avoid duplicate attachment on restarts.

---

## Environment Variables

- Required (both bots)
  - `DISCORD_TOKEN` — bot token from the Discord Developer Portal

- Optional (examples)
  - `BOT_PREFIX`, `OWNER_IDS`, `TEST_GUILDS`
  - Language providers (LanguageBot): `OPENAI_API_KEY`, `DEEPL_API_KEY`, etc.

- Examples
  - FunBot: `fun_bot/.env.example:1`
  - LanguageBot: `language_bot/.env.example:1`

---

## Docker (Per Bot)

- Build per-bot images to preserve isolation. A shared root Dockerfile may not reflect per-bot deps.
- Example approach:
  - Create `Dockerfile` in `fun_bot/` and `language_bot/` installing only that bot’s `requirements.txt`.
  - Set `WORKDIR` to the bot folder and `CMD` to `python -m <package>.main`.

---

## Troubleshooting

- Module import errors: run with `python -m fun_bot.main` or `python -m language_bot.main` and ensure the bot venv is active.
- Missing token: set `DISCORD_TOKEN` in the bot’s `.env`.
- Slash commands not syncing: provide `TEST_GUILDS` for faster guild-only sync during development.
- Logs not writing: verify `logs/` exists and service has write permissions.

---

## Adding A New Bot

- Create a new top-level folder (e.g., `my_new_bot/`) with:
  - `__init__.py`, `main.py`, `runner.py`, `requirements.txt`, `.env.example`
  - Self-contained imports (no cross-folder imports)
- Follow the same venv, `.env`, and service pattern.
- Update this guide with run instructions and service file.

---

For details and commands, see each bot’s README:
- FunBot: `fun_bot/README.md:1`
- LanguageBot: `language_bot/README.md:1`

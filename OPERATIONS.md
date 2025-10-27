## HippoBot Startup Checklist

Quick sanity checks to run after deploying the latest translation stack changes.

1. **Boot log health**
   - Start the bot (`python -m discord_bot.main`) and confirm the log shows  
     `🧬 TranslationOrchestratorEngine created (DeepL ➜ MyMemory)`  
     and `⚙️ Mounted cogs: translation, admin, help, language, sos` without exceptions.
   - If `_mount_cogs` fails, slash/context commands won’t register. Fix the error and restart.

2. **Slash/context command sync**
   - In a test guild, run `/translate` and make sure it completes.
   - Right-click a message and verify the “Translate to My Language” context menu exists.
   - If either command is missing, keep the bot online for a few minutes and re-check logs for sync errors.

3. **Language coverage sanity**
   - Translate a phrase to a DeepL-supported target (e.g. `/translate text:"hello" target:fr`) and confirm the provider shows `deepl`.
   - Translate to a language DeepL does not cover (e.g. `/translate text:"hello" target:af`) and confirm the provider falls back to `mymemory`.

4. **Personality wiring**
   - If you want persona responses, set `OPENAI_API_KEY` before launch.
   - Watch for `🧠 PersonalityEngine wired with OpenAI adapter` in the startup logs. If you see `operating without`, the adapter is disabled.

5. **Secrets and environment**
   - The preflight block logs a sanitised snapshot. Ensure `DISCORD_TOKEN` is masked (not blank) and that any optional keys (DeepL/MyMemory/OpenAI) you expect are present.

Keep this checklist handy during smoke tests to catch regressions early. Feel free to expand it with guild-specific steps as your deployment process evolves.

## Event Topics Catalog and Wiring Rules

To avoid circular dependencies and keep wiring traceable, event topics are
centralized in `core/event_topics.py`. Engines and cogs import only topic name
constants and optional TypedDict payloads for clarity. The integration loader is
the single place that wires publishers to subscribers.

Key topics:
- `translation.requested` — input parsed and a translation job created
- `translation.completed` — processing finished with resolved text
- `translation.failed` — job failed or timed out
- `engine.error` — non-fatal errors from engines/adapters/cogs
- `storage.ready` — storage backend health check result
- `shutdown.initiated` — begin graceful shutdown

Rules to prevent cycles:
- Only the loader imports both cogs and engines.
- Engines do not import `discord.*` or cogs; they publish/subscribe via topics.
- Cogs are thin; they call engines via injected references and publish events via the bus.

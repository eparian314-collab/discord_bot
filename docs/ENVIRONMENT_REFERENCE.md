## Environment Variable Reference

This cheat sheet separates **required** keys from optional toggles so new machines
can come online without spelunking through multiple architecture docs.

### Required

| Key | Purpose | Notes |
| --- | --- | --- |
| `DISCORD_TOKEN` | Bot authentication token | Store in your secrets manager; never commit a real value. |
| `OWNER_IDS` | Comma/semicolon separated list of bot owners | Needed for elevated commands (test KVK windows, diagnostics). |
| `TEST_GUILDS` | Guild IDs where experimental commands may be synced | Keep this short to avoid slash command clutter. |
| `BOT_CHANNEL_ID` | Primary reminder/announcement channel(s) | Accepts comma/semicolon list. First value is used when reminders fall back to `find_bot_channel`. |
| `RANKINGS_CHANNEL_ID` | Channel that accepts `/kvk submit` and auto-prunes chatter | Required for automated ranking moderation and reminder-to-KVK flow. |

### Recommended / Optional

| Key | Purpose | Default |
| --- | --- | --- |
| `GENERAL_CHANNEL_ID`, `MEMBERSHIP_CHANNEL_ID` | Backwards compatible fallbacks for older cogs | `0` (disabled) |
| `DEEPL_API_KEY`, `MYMEMORY_*`, `OPENAI_API_KEY` | Translation + AI backends | Empty = feature disabled |
| `ENABLE_OCR_TRAINING` | Enables EasyOCR training flows during startup | `false` to avoid heavy GPU pulls on lightweight hosts |
| `ENABLE_OCR_DIAGNOSTICS` | Mounts the diagnostic cogs (`!testimg`, `!preprocess`, `!ocr`, `/ocr_report`) | `false` (only enable while debugging) |
| `EASYOCR_MODEL_DIR` | Explicit path to EasyOCR `.pth` weights | `cache/easyocr` |

### Handling Secrets

- Prefer OS or platform-level secret stores (e.g., GitHub Actions secrets, AWS Systems Manager Parameter Store).
- `.env.example` is intentionally sanitised—use it as a template only.
- Always grant the process **read-only** access to the token files; never log the values.

### Operational Tips

1. Run `python scripts/ci/check_env_example.py` during CI to ensure config drift is caught.
2. Before enabling `ENABLE_OCR_TRAINING`, run `python scripts/diagnostics/ocr_watchdog.py` so missing EasyOCR models do not break live events.
3. When adding new env vars, update both `.env.example` and this reference so migrations stay discoverable.

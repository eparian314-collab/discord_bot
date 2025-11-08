## HippoBot Runbook

This runbook summarises the most common production failures and how to triage them without SSH access to the host.

### KVK tracking failed to initialise

1. Run `python scripts/diagnostics/command_registry_diagnostic.py` to ensure slash commands are synced.
2. Execute `python scripts/diagnostics/find_duplicate_kvk.py` if duplicate runs are suspected.
3. Verify the rankings channel ID with `python scripts/ci/check_env_example.py`; missing `RANKINGS_CHANNEL_ID` will block `/kvk submit`.
4. If the issue is limited to a single guild, run `python scripts/diagnostics/verify_command_tree.py --guild <id>` then `/bot status` to view active runs.

### Reminders silently disappearing

1. Run `/bot status` (new admin command) to inspect pending reminders and channel routing.
2. If the status embed shows "0 pending" but events exist, inspect `logs/SYSTEM_TOPOLOGY.md` for stale scheduler errors.
3. Use `python scripts/diagnostics/command_sync_diagnostic.py` to re-sync slash commands, then `python scripts/diagnostics/fix_duplicate_commands.py` if there are collisions.
4. Re-run `python scripts/ci/check_env_example.py` to confirm `BOT_CHANNEL_ID` is set; otherwise the reminder engine will DM creators about missing permissions.

### OCR watchdog warnings / missing models

1. Run `python scripts/diagnostics/ocr_watchdog.py`.  
   - If it exits with code 1, drop the missing `.pth` files into `cache/easyocr` or set `EASYOCR_MODEL_DIR`.
2. Keep `ENABLE_OCR_TRAINING=false` until the watchdog succeeds; otherwise `/kvk submit` will queue jobs that fail mid-run.
3. After syncing models, restart the bot so EasyOCR caches load into memory.
4. When you need to inspect the Discord-side pipeline, temporarily set `ENABLE_OCR_DIAGNOSTICS=true`, reload the bot, and use `!testimg`, `!preprocess`, `!ocr`, and `/ocr_report` to walk through intake → preprocessing → OCR → reporting. Flip the flag back to `false` once finished so diagnostic commands are hidden again.

### Schema or short-ID migrations

1. Whenever `games/storage/game_storage_engine.py` gains new tables (e.g., `event_display_sequences`), run `python scripts/check_schema.py` to apply them.
2. For short-ID drift, `python scripts/diagnostics/command_tree_diagnostic.py --guild <id>` will list orphaned IDs.
3. If you backfill legacy events, call `EventManagementCog._allocate_display_id` (via `/event_refresh` once added) so new events keep sequential letters.

### Quick reference

- **Logs:** `logs/` for scheduler + OCR issues, `test_logs/` during CI runs.
- **Health:** `/bot status` includes active KVK runs, pending reminders, OCR training flags.
- **Deploy:** Run `scripts/deployment/deploy_update.sh` to push latest build, then `scripts/nuclear_sync.py` if slash commands get stuck.

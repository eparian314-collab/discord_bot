## HippoBot Runbook

This runbook summarises the most common production failures and how to triage them without SSH access to the host.

### `/event` command group missing

1. Run `python scripts/diagnostics/command_registry_diagnostic.py` to dump the tree and confirm `/event` and its subcommands exist.
2. If the tree is empty, execute `python scripts/diagnostics/fix_duplicate_commands.py` to clear remote state and let the bot resync on the next boot.
3. Verify guild-only sync variables via `python scripts/ci/check_env_example.py`; incorrect `TEST_GUILDS` entries often block `/event` propagation.
4. For guild-specific issues, run `python scripts/diagnostics/verify_command_tree.py --guild <id>` and inspect `logs/command_sync.log` for schema-hash mismatches.

### Reminders silently disappearing

1. Run `/bot status` followed by `/event status` to inspect pending reminders and channel routing.
2. If the status embed shows "0 pending" but events exist, inspect `logs/SYSTEM_TOPOLOGY.md` for stale scheduler errors.
3. Use `python scripts/diagnostics/command_sync_diagnostic.py` to re-sync slash commands, then `python scripts/diagnostics/fix_duplicate_commands.py` if there are collisions.
4. Re-run `python scripts/ci/check_env_example.py` to confirm `BOT_CHANNEL_ID` is set; otherwise the reminder engine will DM creators about missing permissions.

### Reminder scheduler behind / stuck

1. Run `python scripts/runtime_diagnostic.py --component event_reminder` to confirm the async tasks are scheduled.
2. If the scheduler shows stale timestamps, restart the bot after clearing `data/game_data.db-journal`.
3. Should reminders still skip, delete and recreate them with `/event cleanup` + `/event create` to ensure fresh cron anchors.

### Schema or short-ID migrations

1. Whenever `games/storage/game_storage_engine.py` gains new tables (e.g., `event_display_sequences`), run `python scripts/check_schema.py` to apply them.
2. For short-ID drift, `python scripts/diagnostics/command_tree_diagnostic.py --guild <id>` will list orphaned IDs.
3. If you backfill legacy events, call `EventManagementCog._allocate_display_id` (via `/event_refresh` once added) so new events keep sequential letters.

### Quick reference

- **Logs:** `logs/` for scheduler output, `test_logs/` during CI runs.
- **Health:** `/bot status` plus `/event status` include pending reminders and cleanup timers.
- **Deploy:** Run `scripts/deployment/deploy_update.sh` to push latest build, then `scripts/nuclear_sync.py` if slash commands get stuck.

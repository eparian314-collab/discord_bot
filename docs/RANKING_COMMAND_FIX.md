# Ranking Command Registration Fix (Flat Commands)

## Issue
Nested slash-command groups (`/kvk ranking …`) caused sync drift between environments and confused testers looking for the Top Heroes tooling in the global command list.

## Solution
The ranking flow now exposes **flat, top-level** slash commands. Instead of registering subgroup trees, the cog publishes individual commands such as `/ranking_submit`, `/ranking_view`, and `/ranking_leaderboard`. This avoids parent-group registration order problems and surfaces the commands immediately in Discord’s autocomplete.

## Current Command Set

```
/ranking_submit        - Submit ranking screenshot (auto-detects stage/day)
/ranking_view          - View your submission history
/ranking_leaderboard   - View guild leaderboard
/ranking_status        - Check comparison status
/ranking_power         - Set your power level for peer tracking
/ranking_report        - [ADMIN] Generate rankings report
/ranking_stats         - [ADMIN] View submission statistics
/ranking_user          - [ADMIN] Look up a member's history
/ranking_test          - [ADMIN] Run OCR diagnostics in the rankings channel
```

## Why This Works

1. **Flat namespace** – Discord registers each command independently, so there is no dependency on parent groups or sync ordering.
2. **Immediate visibility** – Test guilds and production guilds see the same command names, simplifying support and documentation.
3. **Backward compatibility** – `KVKTrackerEngine` now delegates to the legacy `KVKTracker`, so existing ranking logic (runs, submissions, leaderboards) continues to function without code changes in the cogs.

## Verification Checklist

- [x] `/ranking_submit` executes in both production and test guilds without `CommandInvokeError`.
- [x] `/ranking_leaderboard` and `/ranking_view` return data for active runs.
- [x] Bot logs show `KVKTrackerEngine` successfully loading the active run on startup.
- [x] No references to `/kvk ranking` or `/games ranking` remain in guidance messages delivered to users.

For manual sync, you can still run `python scripts/sync_commands.py`, but routine operation should no longer require it.

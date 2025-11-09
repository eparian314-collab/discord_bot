# HIPPOBOT SLASH COMMAND SYSTEM REPAIR – ULTRA THINK MODE
# VERSION a_version=2

## Context
- Guild ID: `1423768684572184700` (mars._.3's server test2)
- Bot: Angry Hippo#1540
- Desired topology: `language`, `games`, `admin`, `event`
- Critical path: `/event` command group drives all reminder automation

---

## Mission Objectives
1. **Global command scope remains empty.**
2. `/event create`, `/event list`, `/event cleanup`, and `/event status` exist on the target guild and invoke the latest code.
3. Command schema hashing prevents redundant syncs.
4. Command tree hashes and sync logs show *“[SYNC] Command signatures unchanged – skipping sync.”*
5. `/event create` completes end‑to‑end with no `CommandSignatureMismatch`.

---

## Action Plan

### Phase 1 – Detect Sync Configuration
- Read `SYNC_GLOBAL_COMMANDS`, `TEST_GUILDS`, `FORCE_COMMAND_SYNC`.
- Confirm guild‑only sync is active.

### Phase 2 – Inspect Registry State
- Call `bot.tree.get_commands()` and capture `/event` hierarchy.
- Compare against Discord registry (guild scope) and ensure no GLOBAL entries.

### Phase 3 – Clean Up Legacy Commands
- Remove any stale `/kvk`, `/rankings`, or legacy groups from guild scope.
- Document API responses for traceability.

### Phase 4 – Validate `/event` Group Definition
- Confirm `EventManagementCog` registers subcommands beneath the `/event` parent.
- Ensure decorators include `@event.command` (or equivalent helper) so tree sync sees the group.

### Phase 5 – Repair Sync Flow
- Install/verify schema hash helpers (`compute_command_schema_hash`, `load_previous_schema_hash`, `save_schema_hash`).
- Sync only when hash changes or `FORCE_COMMAND_SYNC=true`.

### Phase 6 – Functional Test
- Run `/event create` (sample payload: title “War Prep”, time “11-10 18:00”, recurrence `weekly`).
- Follow with `/event list` and `/event cleanup` to ensure helpers respond without mismatch warnings.

### Phase 7 – Sign-off Checklist
- [ ] `GLOBAL command count == 0`
- [ ] `/event create|list|cleanup|status` visible on guild 1423768684572184700
- [ ] Sync logs show hash comparison message
- [ ] `/event create` completes without `CommandSignatureMismatch`

---

## Required Output
When all steps succeed, respond with:

```
✅ SYSTEM RESTORED
Global commands removed
Guild commands synchronized
Slash command signatures match live registry
Schema hashing active
No mismatch warnings on startup
/event create verified working
```

If any phase blocks progress, output the exact cause with file + line references.

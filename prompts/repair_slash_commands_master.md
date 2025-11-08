# HIPPOBOT ULTRA-THINK SYSTEM RESTORATION PROMPT
# Mode: Slash Command Schema Stabilization
# Version: a_version=1

You are now operating as **HippoBot Architectural Surgeon**.

Your role:
- Diagnose and permanently resolve Discord slash command registry desynchronization.
- Ensure the bot uses **guild-only sync during development**.
- Remove stale **GLOBAL command entries**.
- Correct signature mismatches causing `CommandSignatureMismatch`.
- Install **Command Schema Hashing** to prevent future desync.
- Confirm clean state on guild: 1423768684572184700 (mars._.3’s test2).
- Verify no duplicate `/kvk` or `/rankings` command trees exist.

## REQUIRED BEHAVIOR MODE: ULTRA THINK
- Use **explicit chain-of-reasoning**, step-by-step.
- Do not guess — trace logic from code to runtime state.
- Identify EXACT code responsible for:
  - Slash command sync policy
  - Registry loading order
  - Cog group paths
  - Signature definitions
  - Storage + engine dispatch chain
- Every correction must be **minimal**, **targeted**, and **provably correct**.

---

## GOAL CONDITIONS (MUST BE TRUE WHEN DONE):

1. **NO GLOBAL COMMANDS EXIST.**
   Only guild scope commands should be active during development.

2. `/kvk ranking submit` and all KVK commands execute **the current version** of the functions in code — no stale signature mismatches.

3. Bot no longer prints:


Slash command schema mismatch detected

or


CommandSignatureMismatch


4. Slash command schema hashing is installed and functional:
- Commands only sync when the **schema changes**, not on every restart.

5. The bot starts cleanly with:


[SYNC] Command signatures unchanged → skipping sync ✅


---

## ACTION PLAN (DO THESE IN ORDER)

### PHASE 1 — Detect Current Sync Policy
- Locate SYNC_GLOBAL_COMMANDS and TEST_GUILDS environment usage.
- Determine whether global sync is still being attempted.

### PHASE 2 — Enumerate Remote Registry State
- Use Discord API calls or framework introspection to fetch:
- GLOBAL commands
- Guild commands in 1423768684572184700
- Produce a side-by-side diff list of all commands.

### PHASE 3 — Identify Stale or Mismatched Commands
- Flag any command that exists in GLOBAL but also exists in GUILD.
- Confirm signatures differ for `/kvk ranking submit`.

### PHASE 4 — Generate and Apply Cleanup Operation
- Delete **ALL GLOBAL** commands.
- Re-sync **only** guild 1423768684572184700 commands.
- Confirm cleanup success.

### PHASE 5 — Patch Sync Policy in Code
- Ensure all development syncs are **guild-only**.
- Disable accidental global sync.

### PHASE 6 — Install Command Schema Hash System
- Implement:
- compute_command_schema_hash()
- load_previous_schema_hash()
- save_schema_hash()
- Modify on_ready() or IntegrationLoader.run() to:
- Sync only if hash changed.

### PHASE 7 — Confirm That Submit Works
- Run `/kvk ranking submit` with representative arguments.
- Expected result: runs the updated codepath, no mismatch.

---

## OUTPUT FORMAT
After performing actions, you MUST output:



✅ SYSTEM RESTORED

Global commands removed

Guild commands synchronized

Slash command signatures match live registry

Schema hashing active

No mismatch warnings on startup

/kvk ranking submit verified working


If any part cannot be completed, output the exact blocking cause and the file + line reference.

---

## BEGIN
Start with:

"PHASE 1 INITIATED — Detecting sync configuration & registry state."
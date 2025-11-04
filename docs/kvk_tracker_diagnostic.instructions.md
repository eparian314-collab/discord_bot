# ============================================================
# 👑 Top Heroes — Kingdom vs Kingdom (KVK) Tracker Diagnostic
# ============================================================
mode: agent
applyTo: "**"
description: >
  Full diagnostic prompt for verifying the Top Heroes KVK Tracker system.
  Ensures the Discord bot properly detects KVK data, tracks scores by kingdom,
  alliance, and player, and displays leaderboard embeds with phase transitions.

# ============================================================
# ⚙️ STAGE 0 — INITIALIZATION
# ============================================================
setup:
  - set test_mode = true
  - log_path: logs/kvk_tracker_test.log
  - clear_cache: true
  - announce: "🏰 Entering KVK Diagnostic Mode (Top Heroes)"
  - validate_engines: [CacheEngine, StorageEngine, OutputEngine, ErrorEngine]

# ============================================================
# 🧩 PHASE 1 — EVENT PARSING & DETECTION
# ============================================================
prompt_01:
  title: "KVK Event Parsing"
  goal: "Verify detection of incoming KVK reports, score updates, and phase announcements."
  content: |
    1. Simulate incoming data payloads or messages such as:
       - !kvk report kingdom:101 vs 102 score:12000-11800
       - /kvk update K101 +500 points alliance:A1
       - /kvk phase start war
    2. Confirm the bot recognizes phase = {preparation, war, results}.
    3. Ensure parsed payloads include:
       - kingdom_id, alliance_tag, user_id, event_type, timestamp
    4. Log each event to kvk_event.log and verify structured output.

# ============================================================
# 💾 PHASE 2 — STATE MANAGEMENT & SCORING
# ============================================================
prompt_02:
  title: "Score Tracking"
  goal: "Confirm score updates and KVK state synchronization."
  content: |
    1. Simulate at least 3 kingdoms and 2 alliances per kingdom.
    2. Trigger incremental score events and confirm totals update correctly.
    3. Verify that scores persist in cache/db under keys:
       - kvk_state.<kingdom_id>.score
       - kvk_alliance.<alliance_tag>.points
    4. Test rollback and double-event protection (no duplicate increments).
    5. Snapshot state to /cache/kvk_snapshot.json and diff results.

# ============================================================
# 🏹 PHASE 3 — LEADERBOARD & EMBED UI
# ============================================================
prompt_03:
  title: "Leaderboard Verification"
  goal: "Ensure kingdom and alliance leaderboards render correctly in embeds."
  content: |
    1. Run /kvk leaderboard or /kvk top command.
    2. Confirm embed layout:
       - 🏰 Kingdom Rank | ⚔️ Power Score | 🛡️ Alliance Tag | 🔥 MVP Player
    3. Verify pagination buttons or select menu navigation.
    4. Ensure formatting auto-updates every 5–10 min during test mode.
    5. Save embed preview to logs/kvk_leaderboard_test.txt.

# ============================================================
# 🌐 PHASE 4 — PHASE TRANSITIONS
# ============================================================
prompt_04:
  title: "Phase Control & Timers"
  goal: "Test transitions between KVK stages and related announcements."
  content: |
    1. Trigger /kvk phase set preparation → war → results.
    2. Validate timers and scheduled events fire correctly.
    3. Confirm state flag updates (kvk_state.phase).
    4. Check automated announcements in Discord channels.
    5. Log transitions to kvk_phase.log.

# ============================================================
# 🧠 PHASE 5 — ERROR INJECTION & BOUNDARY TESTS
# ============================================================
prompt_05:
  title: "Error Injection"
  goal: "Ensure stability under malformed inputs or flood conditions."
  content: |
    1. Send invalid or incomplete payloads (missing kingdom_id, negative scores).
    2. Fire 50 random score updates in <2 s.
    3. Verify no crash; ErrorEngine captures each issue.
    4. Confirm rate limiting or queue fallback engages properly.
    5. Monitor memory growth under async load (optional).

# ============================================================
# 📊 PHASE 6 — RESULT SUMMARY
# ============================================================
prompt_06:
  title: "KVK Test Report"
  goal: "Summarize test outcomes and data integrity."
  content: |
    - Count total processed vs failed updates.
    - Display final kingdom rankings and alliance totals.
    - Output MVP player by score.
    - Write report → logs/kvk_tracker_summary.txt
    - Announce: "✅ Top Heroes KVK Tracker Verified Operational."

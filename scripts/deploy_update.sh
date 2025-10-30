#!/bin/bash
# ==========================================================
# 🦛 HippoBot Auto-Deploy + Rollback + Discord Login Verify
# Author: GeneDoesTech
# ==========================================================

set -e
cd "$(dirname "$0")/.." || exit 1
LOGFILE="./data/tmp_debug/deploy_$(date +"%Y%m%d_%H%M%S").log"

echo "🚀 Starting deployment at $(date)" | tee -a "$LOGFILE"
git remote set-url origin git@github.com:eparian314-collab/discord_bot.git

# ---------- 🧱 Create rollback snapshot ----------
BACKUP_DIR="../discord_bot_backup_$(date +"%Y%m%d_%H%M%S")"
mkdir -p "$BACKUP_DIR"
git rev-parse HEAD > "$BACKUP_DIR/commit_id.txt"
cp -r . "$BACKUP_DIR" >> "$LOGFILE" 2>&1
echo "🛡️  Backup created at: $BACKUP_DIR" | tee -a "$LOGFILE"

# ---------- 📦 Pull latest updates ----------
echo "📦 Fetching latest from GitHub..." | tee -a "$LOGFILE"
git fetch origin main >> "$LOGFILE" 2>&1
git pull origin main --no-rebase >> "$LOGFILE" 2>&1 || {
    echo "❌ Pull failed — keeping backup." | tee -a "$LOGFILE"
    exit 1
}

# ---------- 🛑 Stop running bot ----------
BOT_PROCESS=$(pgrep -f "python3 -m discord_bot.main" || true)
if [ -n "$BOT_PROCESS" ]; then
    echo "🛑 Stopping old bot (PID $BOT_PROCESS)..." | tee -a "$LOGFILE"
    kill "$BOT_PROCESS"
    sleep 3
fi

# ---------- 🧠 Activate venv ----------
if [ -f "./.venv/bin/activate" ]; then
    source ./.venv/bin/activate
    echo "✅ Virtual environment activated." | tee -a "$LOGFILE"
else
    echo "⚠️  No virtual environment found." | tee -a "$LOGFILE"
fi

# ---------- 📚 Dependencies ----------
if [ -f "requirements.txt" ]; then
    echo "📚 Updating dependencies..." | tee -a "$LOGFILE"
    pip install -r requirements.txt >> "$LOGFILE" 2>&1
fi

chmod -R 755 ./data ./cogs ./core ./language_context ./scripts >> "$LOGFILE" 2>&1

# ---------- 🧩 Schema validation ----------
if [ -f "./data/scripts/check_schema.py" ]; then
    echo "🧩 Validating schema..." | tee -a "$LOGFILE"
    python3 ./data/scripts/check_schema.py >> "$LOGFILE" 2>&1 || echo "⚠️  Schema warning." | tee -a "$LOGFILE"
fi

# ---------- 🦛 Restart bot ----------
echo "🦛 Launching new HippoBot..." | tee -a "$LOGFILE"
nohup python3 -m discord_bot.main >> "$LOGFILE" 2>&1 &
NEW_PID=$!
sleep 3

# ---------- 🧩 Verify Discord login ----------
echo "🔍 Waiting for Discord login confirmation..." | tee -a "$LOGFILE"
MAX_WAIT=45  # seconds
COUNTER=0
SUCCESS=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    if grep -q "🦛 HippoBot logged in as" "$LOGFILE"; then
        SUCCESS=1
        break
    fi
    sleep 3
    COUNTER=$((COUNTER+3))
done

# ---------- ✅ Success or 🔁 Rollback ----------
if [ $SUCCESS -eq 1 ]; then
    echo "💚 Login confirmed! Bot is online." | tee -a "$LOGFILE"
    echo "✅ Deployment successful at $(date)" | tee -a "$LOGFILE"
else
    echo "💥 Login not detected within $MAX_WAIT s — rolling back..." | tee -a "$LOGFILE"
    LAST_COMMIT=$(cat "$BACKUP_DIR/commit_id.txt")
    echo "🔙 Reverting to commit $LAST_COMMIT..." | tee -a "$LOGFILE"
    git reset --hard "$LAST_COMMIT" >> "$LOGFILE" 2>&1
    rsync -a --delete "$BACKUP_DIR/" . >> "$LOGFILE" 2>&1

    echo "🔁 Restarting previous version..." | tee -a "$LOGFILE"
    nohup python3 -m discord_bot.main >> "$LOGFILE" 2>&1 &
    echo "⚠️  Rolled back to stable build. Inspect $LOGFILE for details." | tee -a "$LOGFILE"
    exit 1
fi

echo "🕒 Deployment finished at $(date)" | tee -a "$LOGFILE"


#   executable --> chmod +x ~/discord_bot/scripts/deploy_update.sh
#  run --> bash ~/discord_bot/scripts/deploy_update.sh



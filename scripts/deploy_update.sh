#!/bin/bash
# ===========================================================
# HippoBot EC2 Deployment Script (Auto-Venv + Safe Restart)
# ===========================================================

set -e

PROJECT_DIR="$HOME/discord_bot"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_FILE="$PROJECT_DIR/bot.log"

echo ""
echo "🦛  HippoBot EC2 Deployment"
echo "-----------------------------------------------------------"
cd "$PROJECT_DIR"

# 1️⃣ Pull latest updates from GitHub
echo "📦  Fetching latest code from GitHub..."
git fetch origin main
git reset --hard origin/main

# 2️⃣ Auto-create virtual environment if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "⚙️  No virtual environment found — creating one..."
    python3 -m venv "$VENV_DIR"
fi

# 3️⃣ Auto-activate venv (even if user forgot)
echo "🐍  Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 4️⃣ Install dependencies safely
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "📚  Installing / upgrading dependencies..."
    pip install --upgrade pip
    pip install -r "$PROJECT_DIR/requirements.txt"
else
    echo "⚠️  Warning: requirements.txt not found, skipping dependency install."
fi

# 5️⃣ Stop any existing bot processes
echo "🛑  Stopping any running HippoBot processes..."
pkill -f "discord_bot.main" || true

# 6️⃣ Start the bot cleanly in the background
echo "🚀  Starting HippoBot..."
nohup python3 -m discord_bot.main > "$LOG_FILE" 2>&1 &

# 7️⃣ Wait a few seconds to confirm
sleep 3

# 8️⃣ Show summary + last log lines
echo ""
echo "✅  Deployment complete!"
echo "📜  Showing last 20 lines of bot.log:"
echo "-----------------------------------------------------------"
tail -n 20 "$LOG_FILE"
echo "-----------------------------------------------------------"
echo "✨  HippoBot successfully restarted!"


#   executable --> chmod +x ~/discord_bot/scripts/deploy_update.sh
#  run --> bash ~/discord_bot/scripts/deploy_update.sh



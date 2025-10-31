#!/bin/bash
# ===========================================================
# HippoBot EC2 Deployment Script
#  - Pulls latest code from GitHub
#  - Validates .env for required keys
#  - Ensures virtual environment & deps are up to date
#  - Restarts via systemd
#  - Verifies bot login success in logs
# ===========================================================

set -e

SERVICE_NAME="hippobot.service"
PROJECT_DIR="$HOME/discord_bot"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_FILE="$PROJECT_DIR/bot.log"
ENV_FILE="$PROJECT_DIR/.env"

echo ""
echo "🦛  HippoBot EC2 Deployment"
echo "=========================================================="

# 1️⃣  Pre-flight checks
echo "🔍  Running pre-flight health checks..."
if [ ! -f "$ENV_FILE" ]; then
    echo "❌  .env file missing at $ENV_FILE"
    exit 1
fi

REQUIRED_KEYS=("DISCORD_TOKEN" "OWNER_IDS" "DEEPL_API_KEY" "OPEN_AI_API_KEY")
MISSING_KEYS=()

for key in "${REQUIRED_KEYS[@]}"; do
    if ! grep -q "^$key=" "$ENV_FILE"; then
        MISSING_KEYS+=("$key")
    fi
done

if [ ${#MISSING_KEYS[@]} -ne 0 ]; then
    echo "❌  Missing required keys in .env: ${MISSING_KEYS[*]}"
    exit 1
else
    echo "✅  .env validated: all required keys present."
fi

# 2️⃣  Pull latest updates
echo ""
echo "📦  Fetching latest code from GitHub..."
cd "$PROJECT_DIR"
git fetch origin main
git reset --hard origin/main

# 3️⃣  Ensure virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "⚙️  Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 4️⃣  Activate and install dependencies
echo "🐍  Activating virtual environment..."
source "$VENV_DIR/bin/activate"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "📚  Installing / upgrading dependencies..."
    pip install --upgrade pip
    pip install -r "$PROJECT_DIR/requirements.txt"
else
    echo "⚠️  Warning: requirements.txt not found — skipping dependency install."
fi

# 5️⃣  Reload and restart systemd service
echo ""
echo "🔄  Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "🛑  Stopping $SERVICE_NAME if running..."
sudo systemctl stop "$SERVICE_NAME" || true

echo "🚀  Starting $SERVICE_NAME..."
sudo systemctl start "$SERVICE_NAME"

# 6️⃣  Post-startup verification
echo ""
echo "⏳  Waiting for service to initialize..."
sleep 8

if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "❌  Service failed to start. Check logs:"
    sudo journalctl -u "$SERVICE_NAME" -n 20 --no-pager
    exit 1
fi

echo "✅  Service is active."

# 7️⃣  Sanity check for bot login message in logs
echo ""
echo "🧠  Verifying bot startup logs..."
if grep -q "HippoBot logged in as" "$LOG_FILE"; then
    echo "✅  Bot successfully logged in and operational."
else
    echo "⚠️  Could not confirm login in logs — last 20 lines:"
    tail -n 20 "$LOG_FILE"
fi

echo ""
echo "✨  Deployment complete!"
echo "=========================================================="
# Usage:

#   executable --> chmod +x ~/discord_bot/scripts/deploy_update.sh
#  run --> bash ~/discord_bot/scripts/deploy_update.sh



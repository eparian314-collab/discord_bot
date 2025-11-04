#!/usr/bin/env bash
# ============================================
# Deploy and Restart Bot
# 1. Runs deployment (tests, updates)
# 2. Restarts the systemd service
# ============================================

set -euo pipefail

log() {
    printf '[%(%Y-%m-%dT%H:%M:%S%z)T] %s\n' -1 "$*"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

log "Running deployment script..."
if ! bash "${SCRIPT_DIR}/deploy_update.sh"; then
    log "❌ Deployment failed - NOT restarting bot"
    exit 1
fi

log "Deployment successful! Restarting bot..."

# Check if running as systemd service
if systemctl is-active --quiet discord_bot; then
    log "Restarting systemd service..."
    sudo systemctl restart discord_bot
    sleep 2
    if systemctl is-active --quiet discord_bot; then
        log "✅ Bot restarted successfully"
        sudo journalctl -u discord_bot -n 20 --no-pager
    else
        log "❌ Bot failed to start"
        sudo journalctl -u discord_bot -n 50 --no-pager
        exit 1
    fi
else
    log "Systemd service not running. Start manually with:"
    log "  ./scripts/run_bot.sh"
fi

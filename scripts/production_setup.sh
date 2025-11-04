#!/bin/bash
# Production deployment script with systemd service integration
# This ensures the bot runs as a service and restarts automatically

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

GREEN="\033[92m"
RED="\033[91m"
YELLOW="\033[93m"
BLUE="\033[94m"
RESET="\033[0m"

echo -e "${BLUE}========================================${RESET}"
echo -e "${BLUE}HippoBot Production Setup (EC2)${RESET}"
echo -e "${BLUE}========================================${RESET}"
echo ""

# Check if running as root (needed for systemd)
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please run as regular user (not root)${RESET}"
    echo -e "${YELLOW}This script will use sudo when needed${RESET}"
    exit 1
fi

# Step 1: Create systemd service file
echo -e "${BLUE}[1/6]${RESET} Creating systemd service file..."

cat > /tmp/discord_bot.service << EOF
[Unit]
Description=HippoBot Discord Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT
Environment="PATH=$PROJECT_ROOT/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_ROOT/.venv/bin/python $PROJECT_ROOT/main.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_ROOT/logs/systemd.log
StandardError=append:$PROJECT_ROOT/logs/systemd_error.log

# Monitoring with alive_monitor integrated
ExecStartPost=/bin/sleep 5
ExecStartPost=/bin/sh -c 'echo "Bot started at \$(date)" >> $PROJECT_ROOT/logs/service_status.log'

# Resource limits (optional - adjust as needed)
MemoryMax=1G
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOF

# Install service file
sudo cp /tmp/discord_bot.service /etc/systemd/system/discord_bot.service
sudo systemctl daemon-reload

echo -e "${GREEN}✓ Service file created${RESET}"

# Step 2: Create monitoring cron job
echo -e "${BLUE}[2/6]${RESET} Setting up health monitoring cron job..."

CRON_SCRIPT="$PROJECT_ROOT/scripts/health_check_cron.sh"
cat > "$CRON_SCRIPT" << 'EOF'
#!/bin/bash
# Health check script run by cron every 5 minutes

PROJECT_ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
LOG_FILE="$PROJECT_ROOT/logs/health_check.log"

cd "$PROJECT_ROOT"
source .venv/bin/activate

# Run health check via alive monitor
python3 -c "
import asyncio
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from scripts.alive_monitor import AliveMonitor
from datetime import datetime

async def check():
    monitor = AliveMonitor()
    metrics = await monitor.check_health()
    
    # Log results
    print(f\"[{datetime.now()}] Status: {metrics['status']}\")
    if metrics['warnings']:
        print(f\"  Warnings: {', '.join(metrics['warnings'])}\")
    
    # If critical, log to separate file
    if metrics['status'] == 'critical':
        with open('$PROJECT_ROOT/logs/critical_alerts.log', 'a') as f:
            f.write(f\"[{datetime.now()}] CRITICAL: {metrics['warnings']}\n\")
    
    return 0 if metrics['status'] == 'healthy' else 1

sys.exit(asyncio.run(check()))
" >> "$LOG_FILE" 2>&1

# Check if service is running, restart if not
if ! systemctl is-active --quiet discord_bot; then
    echo "[$(date)] Service not running, attempting restart..." >> "$LOG_FILE"
    sudo systemctl restart discord_bot
fi
EOF

chmod +x "$CRON_SCRIPT"

# Add to crontab if not already there
(crontab -l 2>/dev/null | grep -v "health_check_cron.sh"; echo "*/5 * * * * $CRON_SCRIPT") | crontab -

echo -e "${GREEN}✓ Health monitoring cron job configured${RESET}"

# Step 3: Create log rotation config
echo -e "${BLUE}[3/6]${RESET} Setting up log rotation..."

sudo tee /etc/logrotate.d/discord_bot > /dev/null << EOF
$PROJECT_ROOT/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 $USER $USER
    sharedscripts
    postrotate
        systemctl reload discord_bot > /dev/null 2>&1 || true
    endscript
}
EOF

echo -e "${GREEN}✓ Log rotation configured${RESET}"

# Step 4: Enable and start service
echo -e "${BLUE}[4/6]${RESET} Enabling systemd service..."

sudo systemctl enable discord_bot.service
echo -e "${GREEN}✓ Service enabled (will start on boot)${RESET}"

# Step 5: Run preflight checks
echo -e "${BLUE}[5/6]${RESET} Running preflight checks..."

source .venv/bin/activate

if ! python3 scripts/check_env.py; then
    echo -e "${RED}✗ Environment check failed${RESET}"
    exit 1
fi

if ! python3 scripts/test_module_integrity.py; then
    echo -e "${RED}✗ Module integrity check failed${RESET}"
    exit 1
fi

echo -e "${GREEN}✓ Preflight checks passed${RESET}"

# Step 6: Start the service
echo -e "${BLUE}[6/6]${RESET} Starting bot service..."

sudo systemctl start discord_bot.service

sleep 3

if systemctl is-active --quiet discord_bot; then
    echo -e "${GREEN}✓ Bot service started successfully${RESET}"
else
    echo -e "${RED}✗ Bot service failed to start${RESET}"
    echo -e "${YELLOW}Check logs: sudo journalctl -u discord_bot -n 50${RESET}"
    exit 1
fi

# Summary
echo ""
echo -e "${GREEN}========================================${RESET}"
echo -e "${GREEN}Production Setup Complete!${RESET}"
echo -e "${GREEN}========================================${RESET}"
echo ""
echo -e "${BLUE}Useful Commands:${RESET}"
echo ""
echo -e "  ${YELLOW}sudo systemctl status discord_bot${RESET}     - Check bot status"
echo -e "  ${YELLOW}sudo systemctl restart discord_bot${RESET}    - Restart bot"
echo -e "  ${YELLOW}sudo systemctl stop discord_bot${RESET}       - Stop bot"
echo -e "  ${YELLOW}sudo journalctl -u discord_bot -f${RESET}     - Follow service logs"
echo -e "  ${YELLOW}tail -f logs/systemd.log${RESET}              - Follow bot output"
echo -e "  ${YELLOW}tail -f logs/health_check.log${RESET}         - Follow health checks"
echo ""
echo -e "${BLUE}Monitoring:${RESET}"
echo -e "  • Health checks run every 5 minutes via cron"
echo -e "  • Auto-restart on failure (10s delay)"
echo -e "  • Logs rotate daily (7 day retention)"
echo -e "  • Critical alerts logged to logs/critical_alerts.log"
echo ""
echo -e "${GREEN}You can now close your terminal - bot will keep running!${RESET}"
echo ""
EOF
chmod +x "$PROJECT_ROOT/scripts/production_setup.sh"

echo "Created: $PROJECT_ROOT/scripts/production_setup.sh"

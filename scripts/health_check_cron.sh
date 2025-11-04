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

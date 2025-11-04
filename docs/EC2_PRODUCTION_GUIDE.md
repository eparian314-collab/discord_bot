# EC2 Production Deployment Guide

Complete guide for deploying HippoBot to EC2 with automatic monitoring and restart capabilities.

---

## 🚀 Quick Production Setup

**One-command setup** (recommended):

```bash
cd /home/mars/projects/discord_bot
chmod +x scripts/production_setup.sh
./scripts/production_setup.sh
```

This will:
- ✅ Create systemd service (runs on boot, auto-restarts)
- ✅ Set up health monitoring cron (checks every 5 minutes)
- ✅ Configure log rotation (daily, 7 day retention)
- ✅ Run preflight checks
- ✅ Start the bot

**After running, you can close your terminal - bot keeps running!**

---

## 📊 How It Works

### 1. **Systemd Service** (Primary Process Manager)

The bot runs as a **systemd service**, which means:

- ✅ **Starts automatically on EC2 boot/reboot**
- ✅ **Auto-restarts if bot crashes** (10 second delay)
- ✅ **Runs in background** (survives terminal close)
- ✅ **Standard logging** to `logs/systemd.log`
- ✅ **Resource limits** (1GB memory, 80% CPU max)

**Service file location**: `/etc/systemd/system/discord_bot.service`

### 2. **Health Monitoring Cron** (Watchdog)

A cron job runs **every 5 minutes** to:

- ✅ Check bot health (memory, latency, tasks)
- ✅ Log health status to `logs/health_check.log`
- ✅ Alert on critical issues to `logs/critical_alerts.log`
- ✅ Restart service if not running

**Cron script**: `scripts/health_check_cron.sh`

### 3. **Log Rotation** (Prevents Disk Fill)

Logs automatically rotate:

- ✅ **Daily** rotation
- ✅ **7 days** retention
- ✅ **Compressed** old logs
- ✅ Prevents disk space issues

**Config**: `/etc/logrotate.d/discord_bot`

---

## 🎛️ Managing the Bot

### Check Status

```bash
sudo systemctl status discord_bot
```

**Output**:
```
● discord_bot.service - HippoBot Discord Bot
   Active: active (running) since ...
   Main PID: 12345
```

### Start/Stop/Restart

```bash
sudo systemctl start discord_bot      # Start
sudo systemctl stop discord_bot       # Stop
sudo systemctl restart discord_bot    # Restart
```

### View Logs

```bash
# Real-time service logs
sudo journalctl -u discord_bot -f

# Real-time bot output
tail -f logs/systemd.log

# Real-time health checks
tail -f logs/health_check.log

# Critical alerts only
tail -f logs/critical_alerts.log

# Last 50 lines of service logs
sudo journalctl -u discord_bot -n 50
```

### Check Health Remotely

In Discord:
```
/admin selfcheck
```

This shows:
- ⚡ Latency and response time
- 💾 Memory usage and active tasks
- ⏱️ Uptime and session info
- 🔄 Event loop status
- 📊 Overall health

---

## 🔄 Auto-Restart Behavior

### When Bot Crashes

1. **Systemd** detects process exit
2. Waits 10 seconds
3. **Automatically restarts** bot
4. Logs restart to systemd journal

### When EC2 Reboots

1. EC2 starts up
2. **Systemd** starts `discord_bot.service` automatically
3. Bot comes online within ~30 seconds
4. New session created in `data/session_state.json`

### When Health Check Fails

1. **Cron job** (every 5 minutes) detects service down
2. Runs `sudo systemctl restart discord_bot`
3. Logs restart attempt to `logs/health_check.log`

---

## 📝 Log Files Reference

```
logs/
├── systemd.log              # Main bot output (stdout)
├── systemd_error.log        # Error output (stderr)
├── health_check.log         # Cron health check results
├── critical_alerts.log      # Critical issues only
├── service_status.log       # Service start/stop events
├── deployment.log           # Deployment script logs
└── nohup.out               # Legacy (if using nohup instead)
```

### Log Rotation Schedule

```
logs/systemd.log           → logs/systemd.log.1.gz (yesterday)
logs/systemd.log.1.gz      → logs/systemd.log.2.gz (2 days ago)
...
logs/systemd.log.6.gz      → deleted (7 days old)
```

---

## 🔍 Monitoring Dashboard (Optional)

### Set Up Alerts

Edit `scripts/health_check_cron.sh` to add email alerts:

```bash
# Add to health_check_cron.sh after critical check:
if [ "$metrics_status" == "critical" ]; then
    echo "HippoBot CRITICAL: $warnings" | mail -s "Bot Alert" your-email@example.com
fi
```

### View Health Trends

```bash
# Show all health checks from last hour
grep "$(date '+%Y-%m-%d %H')" logs/health_check.log

# Count critical alerts today
grep "$(date '+%Y-%m-%d')" logs/critical_alerts.log | wc -l

# Memory usage over time
grep "memory_mb" logs/health_check.log | tail -20
```

---

## 🛠️ Troubleshooting

### Bot Not Starting

```bash
# Check service status
sudo systemctl status discord_bot

# View detailed logs
sudo journalctl -u discord_bot -n 100 --no-pager

# Check environment
cd /home/mars/projects/discord_bot
source .venv/bin/activate
python3 scripts/check_env.py
```

### Service Keeps Restarting

```bash
# Check error logs
tail -50 logs/systemd_error.log

# Disable auto-restart temporarily
sudo systemctl edit discord_bot
# Add:
# [Service]
# Restart=no

sudo systemctl restart discord_bot
```

### Cron Not Running

```bash
# Verify cron job exists
crontab -l | grep health_check

# Check cron logs
grep CRON /var/log/syslog | tail -20

# Manually run health check
cd /home/mars/projects/discord_bot
./scripts/health_check_cron.sh
```

### High Memory/CPU

```bash
# Check in Discord
/admin selfcheck

# Or check directly
ps aux | grep discord_bot

# Restart to clear
sudo systemctl restart discord_bot
```

---

## 🔒 Security Notes

### Service Runs as Your User

- ✅ No root permissions required
- ✅ Files owned by your user account
- ✅ Uses your `.env` configuration

### Secrets Protection

```bash
# Ensure .env is not world-readable
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (only you can read)
```

### Firewall (Optional)

EC2 security groups handle firewall, but locally:

```bash
# Allow Discord API access (port 443)
# Already allowed by default in EC2
```

---

## 📦 Updates & Deployment

### Deploy Code Updates

```bash
cd /home/mars/projects/discord_bot

# Pull latest code
git pull origin hippo-v3

# Activate venv
source .venv/bin/activate

# Update dependencies
pip install -r requirements.txt

# Run tests
pytest -v

# Restart service
sudo systemctl restart discord_bot

# Monitor logs
sudo journalctl -u discord_bot -f
```

### Rollback if Issues

```bash
# Stop current version
sudo systemctl stop discord_bot

# Revert code
git checkout <previous-commit>

# Reinstall dependencies
pip install -r requirements.txt

# Restart
sudo systemctl start discord_bot
```

---

## 🧪 Testing Before Production

### Dry Run (Without Installing Service)

```bash
# Test manually first
cd /home/mars/projects/discord_bot
source .venv/bin/activate
python3 -m discord_bot.main

# Press Ctrl+C when verified working
```

### Test Service in Isolation

```bash
# Create service but don't enable auto-start
sudo systemctl start discord_bot

# Check it works
sudo systemctl status discord_bot

# If good, enable auto-start
sudo systemctl enable discord_bot
```

---

## 📋 Production Checklist

Before running `production_setup.sh`:

- [ ] `.env` file configured with all tokens
- [ ] Virtual environment created (`.venv/`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Tests passing (`pytest -v`)
- [ ] Environment check passing (`python3 scripts/check_env.py`)
- [ ] Module integrity passing (`python3 scripts/test_module_integrity.py`)

After setup:

- [ ] Service running (`sudo systemctl status discord_bot`)
- [ ] Bot online in Discord
- [ ] `/admin selfcheck` works
- [ ] Logs being written (`tail -f logs/systemd.log`)
- [ ] Cron job in crontab (`crontab -l`)

---

## 🚨 Emergency Procedures

### Complete Service Removal

```bash
# Stop and disable service
sudo systemctl stop discord_bot
sudo systemctl disable discord_bot

# Remove service file
sudo rm /etc/systemd/system/discord_bot.service
sudo systemctl daemon-reload

# Remove cron job
crontab -e
# Delete the health_check line

# Remove log rotation
sudo rm /etc/logrotate.d/discord_bot
```

### Manual Emergency Restart

```bash
# Kill all bot processes
pkill -f "discord_bot.main"

# Start fresh
cd /home/mars/projects/discord_bot
source .venv/bin/activate
nohup python3 -m discord_bot.main > logs/emergency.log 2>&1 &
```

---

## 📞 Support Commands

```bash
# Full system diagnostic
sudo systemctl status discord_bot
tail -50 logs/systemd.log
tail -20 logs/health_check.log
ps aux | grep discord_bot
df -h  # Check disk space
free -h  # Check memory
```

---

## ✅ Summary

After running `scripts/production_setup.sh`:

| Feature | Status |
|---------|--------|
| **Runs on boot** | ✅ Yes (systemd enabled) |
| **Survives terminal close** | ✅ Yes (background service) |
| **Auto-restart on crash** | ✅ Yes (10s delay) |
| **Health monitoring** | ✅ Yes (every 5 min) |
| **Auto-restart if down** | ✅ Yes (cron checks) |
| **Log rotation** | ✅ Yes (daily, 7 days) |
| **Remote health check** | ✅ Yes (`/admin selfcheck`) |
| **Resource limits** | ✅ Yes (1GB RAM, 80% CPU) |

**You can safely close your terminal - bot will keep running and monitoring itself!** 🎉

---

**Quick Reference**:
- Start: `sudo systemctl start discord_bot`
- Stop: `sudo systemctl stop discord_bot`
- Restart: `sudo systemctl restart discord_bot`
- Status: `sudo systemctl status discord_bot`
- Logs: `sudo journalctl -u discord_bot -f`

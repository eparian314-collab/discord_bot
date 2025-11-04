# 🎉 Production Setup Complete!

Your HippoBot is now running as a systemd service and will persist even after you close your terminal or disconnect from SSH!

## ✅ Current Status

- **Service Status**: Running as `discord_bot.service`
- **Auto-Start**: Enabled (will start on server reboot)
- **Auto-Restart**: Configured (restarts automatically if it crashes)
- **Health Monitoring**: Cron job runs every 5 minutes
- **Log Rotation**: Configured for 7-day retention

## 🎮 Managing Your Bot

### Check Bot Status
```bash
sudo systemctl status discord_bot
```

### View Live Logs
```bash
# Follow systemd logs
sudo journalctl -u discord_bot -f

# Follow bot output
tail -f logs/systemd.log

# Follow health checks
tail -f logs/health_check.log
```

### Control the Bot
```bash
# Restart the bot
sudo systemctl restart discord_bot

# Stop the bot
sudo systemctl stop discord_bot

# Start the bot
sudo systemctl start discord_bot

# Disable auto-start on boot
sudo systemctl disable discord_bot

# Re-enable auto-start
sudo systemctl enable discord_bot
```

### View Service Information
```bash
# Check bot status
systemctl is-active discord_bot

# View service configuration
cat /etc/systemd/system/discord_bot.service

# View recent service events
sudo journalctl -u discord_bot -n 100
```

## 📊 Monitoring

### Automated Health Checks
- Runs every 5 minutes via cron
- Checks process health, memory usage, and responsiveness
- Auto-restarts service if not running
- Critical alerts logged to `logs/critical_alerts.log`

### Manual Health Check
Use Discord commands:
```
/admin selfcheck
```

### View Health Logs
```bash
tail -f logs/health_check.log
```

## 🔄 Updating the Bot

When you push code changes:

```bash
# Pull latest changes
git pull

# Restart the service
sudo systemctl restart discord_bot

# Verify it restarted successfully
sudo systemctl status discord_bot
```

## 📝 Log Files

All logs are stored in the `logs/` directory:

- `logs/systemd.log` - Main bot output
- `logs/systemd_error.log` - Error messages
- `logs/health_check.log` - Health monitoring results
- `logs/critical_alerts.log` - Critical issues requiring attention
- `logs/service_status.log` - Service start/stop events

### View Log Files
```bash
# Main bot log
tail -100 logs/systemd.log

# Error log
tail -100 logs/systemd_error.log

# Health check results
tail -100 logs/health_check.log
```

## 🛠️ Troubleshooting

### Bot Won't Start
```bash
# Check error logs
sudo journalctl -u discord_bot -n 50

# Check environment variables
cat .env

# Run preflight checks
python3 scripts/check_env.py
python3 scripts/test_module_integrity.py
```

### Bot Keeps Restarting
```bash
# View the error log
tail -50 logs/systemd_error.log

# Check system resources
free -h
df -h
```

### Database Issues
```bash
# Check database files exist
ls -lh data/*.db

# Run schema validation
python3 scripts/check_schema.py
```

## 🚀 What Happens After You Close Your Terminal?

**You can safely close your SSH connection!** The bot will:

✅ Keep running in the background  
✅ Restart automatically if it crashes  
✅ Monitor its own health every 5 minutes  
✅ Start automatically when the server reboots  
✅ Rotate logs to prevent disk space issues  

## 📍 Important Files

- `/etc/systemd/system/discord_bot.service` - Service configuration
- `~/.env` - Environment variables and secrets
- `scripts/health_check_cron.sh` - Health monitoring script
- `/etc/logrotate.d/discord_bot` - Log rotation config

## 🔐 Security Notes

- Service runs as your user (`mars`), not root
- Environment variables loaded from `.env` file
- Logs are readable only by you
- Consider rotating Discord tokens periodically

## 📞 Need Help?

Check the comprehensive guides:
- `docs/EC2_PRODUCTION_GUIDE.md` - Full EC2 setup guide
- `docs/DEPLOYMENT_CHECKLIST.md` - Pre-deployment checklist
- `docs/QUICK_REFERENCE.md` - Common commands

---

**Congratulations!** Your bot is production-ready and will run reliably on your EC2 instance. 🦛

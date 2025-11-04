# HippoBot Quick Start & Reference

**One-page reference for common operations and troubleshooting.**

---

## 🚀 Quick Start

### Local Development
```bash
# 1. Clone and setup
git clone <repo>
cd discord_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your tokens

# 3. Validate
python3 scripts/check_env.py
python3 scripts/test_module_integrity.py

# 4. Launch
./scripts/deploy_loop.sh deploy
```

### EC2 Production Setup
```bash
# One-command production setup (with auto-restart & monitoring)
cd /home/mars/projects/discord_bot
chmod +x scripts/production_setup.sh
./scripts/production_setup.sh

# Bot will now:
# ✅ Run as systemd service (survives terminal close)
# ✅ Auto-restart on crash
# ✅ Start on EC2 boot
# ✅ Self-monitor every 5 minutes
```

**See [EC2_PRODUCTION_GUIDE.md](EC2_PRODUCTION_GUIDE.md) for full details**

---

## 📋 Common Commands

### Local Development
```bash
source .venv/bin/activate          # Activate venv
python3 main.py                    # Run bot directly
pytest -v                          # Run tests
python3 scripts/check_env.py       # Validate environment
```

### EC2 Production (Systemd Service)
```bash
sudo systemctl status discord_bot  # Check if running
sudo systemctl start discord_bot   # Start service
sudo systemctl stop discord_bot    # Stop service
sudo systemctl restart discord_bot # Restart service
sudo journalctl -u discord_bot -f  # Follow service logs
tail -f logs/systemd.log           # Follow bot output
tail -f logs/health_check.log      # Follow health checks
```

### Local Deployment (Manual)
```bash
./scripts/deploy_loop.sh deploy    # Auto-deploy with monitoring
./scripts/deploy_loop.sh start     # Start bot
./scripts/deploy_loop.sh stop      # Stop bot
./scripts/deploy_loop.sh restart   # Restart bot
./scripts/deploy_loop.sh status    # Check if running
./scripts/deploy_loop.sh logs      # Tail logs
```

### Monitoring
```bash
tail -f logs/nohup.out            # Watch bot output
tail -f logs/errors.log           # Watch errors only
python3 scripts/alive_monitor.py  # Run health monitor
```

---

## 🎮 Discord Commands

### Admin Commands
```
/admin selfcheck              # Health metrics
/admin cleanup [limit]        # Clean old messages
/admin mute <user> <duration> # Timeout user
/admin unmute <user>          # Remove timeout
/admin give <user>            # Share cookies
```

### Translation
```
/language translate <text>    # Translate message
/language roles               # Manage language roles
/language sos <text>          # Emergency translation
```

### Games & Events
```
/games ranking submit         # Submit ranking screenshot
/games ranking view           # View rankings
/games pokemon catch          # Catch Pokemon
/events schedule              # Schedule event
```

### Help
```
/help                         # Show all commands
```

---

## 🔍 Troubleshooting

### Bot Won't Start
```bash
# Check environment
python3 scripts/check_env.py

# Check modules
python3 scripts/test_module_integrity.py

# View logs
tail -50 logs/nohup.out

# Kill existing process
./scripts/deploy_loop.sh stop
```

### High Latency
```discord
/admin selfcheck              # Check metrics
/admin cleanup 200            # Free resources
```

Then restart:
```bash
./scripts/deploy_loop.sh restart
```

### Commands Not Syncing
```bash
python3 scripts/sync_commands.py
# Or nuclear option:
python3 scripts/nuclear_sync.py
```

### Memory Issues
```bash
# Check memory usage
ps aux | grep discord_bot

# Clean up
/admin cleanup

# Restart
./scripts/deploy_loop.sh restart
```

---

## 📊 Health Metrics

| Metric | Healthy | Monitor | Critical |
|--------|---------|---------|----------|
| Latency | < 500ms | 500-1000ms | > 1000ms |
| Memory | < 500MB | 500-800MB | > 800MB |
| Tasks | < 100 | 100-200 | > 200 |

---

## 📁 Key Files & Directories

```
discord_bot/
├── main.py                    # Entry point
├── .env                       # Configuration (DO NOT COMMIT)
├── requirements.txt           # Dependencies
├── cogs/                      # Discord commands
│   ├── admin_cog.py          # Admin commands
│   ├── translation_cog.py    # Translation
│   └── unified_ranking_cog.py # Rankings
├── core/engines/              # Business logic
│   ├── cleanup_engine.py     # Message cleanup
│   ├── session_manager.py    # Session tracking
│   └── translation_orchestrator.py
├── scripts/                   # Operational tools
│   ├── check_env.py          # Environment validation
│   ├── deploy_loop.sh        # Deployment automation
│   └── alive_monitor.py      # Health monitoring
├── data/                      # Runtime data
│   ├── session_state.json    # Session tracking
│   ├── event_rankings.db     # Rankings database
│   └── game_data.db          # Game data
└── logs/                      # Log files
    ├── nohup.out             # Main output
    └── errors.log            # Errors only
```

---

## ⚙️ Environment Variables

```bash
# Required
DISCORD_TOKEN=               # Bot token
DEEPL_API_KEY=              # DeepL translation
MY_MEMORY_API_KEY=          # MyMemory translation
OPEN_AI_API_KEY=            # OpenAI (optional)

# Optional
CLEANUP_ENABLED=true         # Auto-cleanup
CLEANUP_SKIP_RECENT_MINUTES=30
CLEANUP_LIMIT_PER_CHANNEL=200
CLEANUP_RATE_DELAY=0.5

# Channels
RANKINGS_CHANNEL_ID=         # Rankings submission
MODLOG_CHANNEL_ID=          # Moderation logs
BOT_CHANNEL_ID=             # Bot commands
```

---

## 🧪 Testing Quick Reference

```bash
# Run all tests
pytest -v

# Specific test file
pytest tests/test_cleanup_system.py -v

# With coverage
pytest --cov=discord_bot --cov-report=html

# Stop on first failure
pytest -x

# Run only failed tests
pytest --lf
```

---

## 🔗 Documentation Links

- [Full Deployment Guide](docs/DEPLOYMENT_CHECKLIST.md)
- [Message Cleanup System](docs/MESSAGE_CLEANUP_SYSTEM.md)
- [Ranking System](docs/RANKING_SYSTEM.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Master Bot Instructions](master_bot.instructions.md)

---

## 🆘 Emergency Procedures

### Bot Crashed
```bash
# Check what happened
tail -100 logs/nohup.out

# Restart with monitoring
./scripts/deploy_loop.sh deploy
```

### Database Corruption
```bash
# Backup first
cp data/event_rankings.db data/event_rankings.db.backup

# Check schema
python3 scripts/check_schema.py

# Restore if needed
mv data/event_rankings.db.backup data/event_rankings.db
```

### Complete Reset
```bash
# Stop bot
./scripts/deploy_loop.sh stop

# Clean project
./scripts/refactor_cleanup.sh

# Reinstall dependencies
source .venv/bin/activate
pip install -r requirements.txt --force-reinstall

# Deploy fresh
./scripts/deploy_loop.sh deploy
```

---

**Quick Help**: Run `./scripts/deploy_loop.sh` or `python3 scripts/check_env.py` for guided assistance.

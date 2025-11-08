## ✅ CORRECTED _mount_cogs() BLOCK

```python
async def _mount_cogs(self, owners: Iterable[int]) -> None:
    if not self.bot:
        return
    try:
        from discord_bot.cogs.translation_cog import setup_translation_cog
        from discord_bot.cogs.admin_cog import setup_admin_cog
        from discord_bot.cogs.help_cog import setup as setup_help_cog
        from discord_bot.cogs.role_management_cog import setup as setup_language_cog
        from discord_bot.cogs.sos_phrase_cog import setup as setup_sos_cog
        from discord_bot.cogs.easteregg_cog import EasterEggCog
        from discord_bot.cogs.game_cog import GameCog
        from discord_bot.cogs.event_management_cog import setup as setup_event_cog
        from discord_bot.cogs.ranking_cog import setup as setup_ranking_cog
        from discord_bot.cogs.battle_cog import setup as setup_battle_cog
        from discord_bot.cogs.training_cog import setup as setup_training_cog
        from discord_bot.cogs.ui_master_cog import setup as setup_ui_master_cog

        await setup_translation_cog(self.bot, ui_engine=self.translation_ui)
        await setup_admin_cog(self.bot, ui_engine=self.admin_ui, owners=set(owners), storage=self.game_storage, cookie_manager=self.cookie_manager)
        await setup_help_cog(self.bot)
        await setup_language_cog(self.bot)
        await setup_sos_cog(self.bot)
        await setup_event_cog(self.bot, event_reminder_engine=self.event_reminder_engine)
        await setup_ranking_cog(
            self.bot,
            processor=self.ranking_processor,
            storage=self.ranking_storage,
        )
        
        # Mount game system cogs with dependency injection
        easter_egg_cog = EasterEggCog(
            bot=self.bot,
            relationship_manager=self.relationship_manager,
            cookie_manager=self.cookie_manager,
            personality_engine=self.personality_engine
        )
        await self.bot.add_cog(easter_egg_cog, override=True)
        
        game_cog = GameCog(
            bot=self.bot,
            pokemon_game=self.pokemon_game,
            pokemon_api=self.pokemon_api,
            storage=self.game_storage,
            cookie_manager=self.cookie_manager,
            relationship_manager=self.relationship_manager,
            personality_engine=self.personality_engine
        )
        await self.bot.add_cog(game_cog, override=True)
        
        # Mount battle, training, and UI master cogs
        await setup_battle_cog(self.bot)
        await setup_training_cog(self.bot)
        await setup_ui_master_cog(self.bot)
        
        logger.info("⚙️ Mounted cogs: translation, admin, help, language, sos, events, ranking, easteregg, game, battle, training, ui_master")
    except Exception as exc:
        logger.exception("Failed to mount cogs")
        try:
            await self.event_bus.emit(
                ENGINE_ERROR,
                name="integration_loader",
                category="cog",
                severity="error",
                exc=exc,
            )
        except Exception:
            logger.exception("event_bus.emit failed while reporting cog mount error")
```

## 🔧 CHANGES MADE

### File: `discord_bot/integrations/integration_loader.py`

**Added Imports:**
- `from discord_bot.cogs.battle_cog import setup as setup_battle_cog`
- `from discord_bot.cogs.training_cog import setup as setup_training_cog`
- `from discord_bot.cogs.ui_master_cog import setup as setup_ui_master_cog`

**Added Mount Calls (after game_cog):**
```python
# Mount battle, training, and UI master cogs
await setup_battle_cog(self.bot)
await setup_training_cog(self.bot)
await setup_ui_master_cog(self.bot)
```

**Updated Log Message:**
```python
logger.info("⚙️ Mounted cogs: translation, admin, help, language, sos, events, ranking, easteregg, game, battle, training, ui_master")
```

## 📋 ALL 12 REQUIRED COGS NOW MOUNTED

✅ translation_cog
✅ admin_cog
✅ help_cog
✅ role_management_cog
✅ sos_phrase_cog
✅ event_management_cog
✅ ranking_cog
✅ game_cog
✅ easteregg_cog
✅ battle_cog (NEWLY ADDED)
✅ training_cog (NEWLY ADDED)
✅ ui_master_cog (NEWLY ADDED)

## 🚀 SLASH COMMAND SYNC SCRIPT

**File Created:** `sync_commands_ec2.py`

**Usage on EC2 Ubuntu:**
```bash
# Make executable
chmod +x sync_commands_ec2.py

# Run sync
python3 sync_commands_ec2.py
```

**Features:**
- Reads `.env` configuration automatically
- Syncs to PRIMARY_GUILD_NAME if configured (guild-only)
- Syncs to TEST_GUILDS if configured (multi-guild)
- Syncs globally if SYNC_GLOBAL_COMMANDS=1
- Provides detailed progress output
- Safe error handling

## 🎯 NEXT STEPS

### 1. Test Bot Startup
```bash
python3 main.py
```

**Expected Output:**
```
⚙️ Mounted cogs: translation, admin, help, language, sos, events, ranking, easteregg, game, battle, training, ui_master
```

### 2. Sync Commands (if needed)
```bash
python3 sync_commands_ec2.py
```

### 3. Verify in Discord
- Check that all slash command groups appear: `/language`, `/games`, `/kvk`, `/admin`
- Verify no duplicate commands
- Test ranking commands: `/kvk ranking submit`, `/kvk ranking view`, `/kvk ranking leaderboard`

---

## 🔍 READY FOR RANKING SYSTEM DIAGNOSTICS

All cogs are now mounted. The ranking system wiring is:

**RankingCog** → **ScreenshotProcessor** → **RankingStorageEngine** → **KVKTracker**

Awaiting next instruction for ranking system stability verification.

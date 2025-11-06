# SOS System Testing Guide

## ✅ Changes Made

### 1. **SOS Keyword Triggers** → Send to SOS Channel with @everyone
- When a user types an SOS keyword (like "help", "emergency"), the bot now:
  - ✅ Sends alert to **configured SOS channels** (not the original channel)
  - ✅ Includes **@everyone mention** to notify all server members
  - ✅ Shows who triggered it, which channel, and the message
  - ✅ Adds 🆘 reaction to the alert
  - ✅ Sends **translated DMs** to all users with language roles

### 2. **SOS Reaction (🆘)** → Send to SOS Channel with @everyone
- When someone reacts with 🆘 to a message, the bot now:
  - ✅ Sends alert to **configured SOS channels** (not the original channel)
  - ✅ Includes **@everyone mention**
  - ✅ Shows who reported it, message preview, and direct link
  - ✅ Allows moderators to jump directly to the problematic message

---

## 🔧 Configuration

### Your .env File
```bash
# SOS Channels - Where SOS alerts are sent (comma-separated, no spaces after commas)
SOS_CHANNEL_ID=11375159870759899368,1369093802639491075
```

**Note:** Remove trailing commas from channel IDs:
- ❌ `BOT_CHANNEL_ID=1370753888659181589,` (has comma)
- ✅ `BOT_CHANNEL_ID=1370753888659181589` (no comma)

---

## 🧪 Testing Steps

### Test 1: SOS Keyword Trigger

1. **Setup SOS Keyword:**
   ```
   /language sos add keyword:help phrase:User needs immediate assistance!
   ```

2. **Trigger SOS:**
   - In any channel, type: `help`
   - Bot should:
     - ✅ Send alert to SOS channels (not the channel you typed in)
     - ✅ Include @everyone mention
     - ✅ Show your username and the alert message
     - ✅ Add 🆘 reaction

3. **Check DMs:**
   - All users with language roles should receive DMs
   - Messages should be translated to their language role
   - DM format:
     ```
     🚨 SOS ALERT 🚨
     From: @YourName in ServerName
     Message: User needs immediate assistance!
     
     This is an emergency alert from your server.
     ```

---

### Test 2: SOS Reaction

1. **Create a test message** in any channel

2. **React with 🆘** to that message

3. **Check SOS channels:**
   - Should receive alert with @everyone
   - Should show:
     - Who reacted (your name)
     - Which channel
     - Message preview (first 100 chars)
     - Direct link to jump to the message
   
4. **Click the link** to verify it jumps to the original message

---

### Test 3: Multiple SOS Channels

Your config has 2 SOS channels:
- Channel 1: `11375159870759899368`
- Channel 2: `1369093802639491075`

**Test:** Both channels should receive the same SOS alerts

---

### Test 4: Language Role DMs

1. **Assign language roles** to test users:
   ```
   /language roles assign user:@TestUser language:Spanish
   /language roles assign user:@TestUser2 language:German
   ```

2. **Trigger SOS:**
   ```
   Type: help
   ```

3. **Check DMs:**
   - Spanish user should get DM in Spanish
   - German user should get DM in German
   - English users get DM in English

---

## 📋 Expected Alert Formats

### SOS Keyword Alert (in SOS channel)
```
@everyone 🚨 SOS ALERT 🚨

From: @Username
Channel: #general
Message: User needs immediate assistance!
```

### SOS Reaction Alert (in SOS channel)
```
@everyone 🚨 SOS REACTION DETECTED 🚨

Reported by: @Username
Channel: #general
Message: This is the message content that was flagged...
Link: https://discord.com/channels/...

Someone marked this message as requiring immediate attention.
```

### DM to Users with Language Roles
```
🚨 SOS ALERT 🚨
From: @Username in ServerName
Message: [Translated message in user's language]

This is an emergency alert from your server.
```

---

## 🚨 Important Notes

### Bot Permissions Required

The bot needs these permissions in **SOS channels**:
- ✅ View Channel
- ✅ Send Messages
- ✅ Mention @everyone
- ✅ Add Reactions
- ✅ Embed Links

### Why Users Might Not Get DMs

Users won't receive DMs if:
1. ❌ They don't have a language role assigned
2. ❌ They have DMs disabled for this server
3. ❌ They have blocked the bot
4. ❌ Their privacy settings block DMs from server members

Check logs for:
```
"Cannot DM user XYZ (DMs disabled or blocked)"
```

### Performance

- ✅ DMs are sent asynchronously (won't delay the main alert)
- ✅ Translation happens per-user (uses cached translations when possible)
- ✅ Failed DMs are logged but don't stop the process

---

## 🔍 Troubleshooting

### SOS not going to configured channels
1. Check SOS_CHANNEL_ID in .env
2. Verify channel IDs are correct (right-click → Copy Channel ID)
3. Remove trailing commas from channel IDs
4. Restart bot after changing .env

### @everyone not working
1. Verify bot has "Mention @everyone" permission in SOS channels
2. Check role hierarchy (bot role must be high enough)
3. Test with `/permissions` if available

### No DMs being sent
1. Check if users have language roles: `/language roles list`
2. Verify RoleManager is initialized (check bot logs)
3. Test with a user who definitely has DMs enabled

### Wrong channel receiving alerts
1. Double-check SOS_CHANNEL_ID values
2. Make sure you removed trailing commas
3. Restart bot after .env changes

---

## 📊 Monitoring

### Check Logs for:

**Successful SOS Alert:**
```
INFO: SOS alert sent to channel sos-alerts (1369093802639491075)
INFO: SOS DM broadcast complete: 12 sent, 3 failed
```

**DM Success:**
```
INFO: Sent SOS DM to user 123456789 (JohnDoe) in language: es
```

**DM Failures:**
```
DEBUG: Cannot DM user 987654321 (DMs disabled or blocked)
WARNING: Failed to send DM to user 555555555: Forbidden
```

---

## ✅ Success Criteria

Your SOS system is working correctly when:

1. ✅ SOS keywords trigger alerts in SOS channels (not original channel)
2. ✅ Alerts include @everyone mention
3. ✅ SOS reaction (🆘) sends alerts to SOS channels
4. ✅ Users with language roles receive DMs
5. ✅ DMs are translated to each user's language
6. ✅ All configured SOS channels receive alerts
7. ✅ Bot logs show successful sends and failures

---

## 🎯 Quick Test Commands

```bash
# 1. Add SOS keyword
/language sos add keyword:emergency phrase:Critical situation detected!

# 2. List SOS keywords
/language sos list

# 3. Trigger SOS (type in any channel)
emergency

# 4. Check SOS channels for alert with @everyone

# 5. Check your DMs if you have a language role

# 6. Remove SOS keyword when done testing
/language sos remove keyword:emergency
```

---

## 🔄 Restart Bot

After making .env changes:

```powershell
# Stop bot (Ctrl+C in terminal)

# Restart
python -m discord_bot.main
```

Wait for:
```
🦛 HippoBot logged in as YourBot#1234
```

Then test SOS system!

---

## 📞 Need Help?

If SOS still not working:

1. Share bot logs from `logs/` directory
2. Verify .env channel IDs are correct
3. Check bot permissions in SOS channels
4. Test with a simple SOS keyword first
5. Verify at least one user has a language role for DM testing

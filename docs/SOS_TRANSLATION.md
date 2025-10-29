# SOS Alert Translation System

## Overview

The SOS alert system now includes **automatic translation and direct messaging** to all server members with language roles. When an SOS keyword is detected, the bot will:

1. Post the alert in the channel where it was triggered
2. Send a **Direct Message (DM)** to every user with a language role
3. **Automatically translate** the message to each user's language

## How It Works

### 1. Channel Alert (Existing Behavior)
- SOS keyword detected in a message
- Bot posts alert in the same channel: `🚨 **SOS Triggered:** <message>`
- Alert message gets a 🆘 reaction

### 2. Direct Message Broadcast (NEW)
- Bot identifies all guild members with language roles
- For each member:
  - Skips bots and the person who triggered the SOS
  - Gets their primary language role
  - Translates the message to their language (if not English)
  - Sends a DM with the translated alert

### 3. Translation Logic
- **English speakers**: Receive message in English (no translation needed)
- **Non-English speakers**: Message is translated using:
  - DeepL API (preferred, high quality)
  - MyMemory API (fallback)
- **Translation failure**: User receives original English message
- **DMs disabled**: Failure is logged but doesn't stop other notifications

## Configuration

### Prerequisites
1. **Language Roles**: Users must have language roles assigned (e.g., "Spanish", "French", "日本語")
2. **Translation APIs**: At least one translation service configured:
   - `DEEPL_API_KEY` (recommended)
   - `MYMEMORY_API_KEY` + `MYMEMORY_USER_EMAIL`

### Setting Up SOS Keywords

```bash
# Add an SOS keyword
/sos add keyword:"fire" phrase:"Fire alarm activated! Evacuate immediately!"

# Add another keyword
/sos add keyword:"medical" phrase:"Medical emergency in progress. First aid responders needed."

# List configured keywords
/sos list

# Remove a keyword
/sos remove keyword:"fire"

# Clear all keywords
/sos clear
```

## Usage Example

### Scenario 1: International Server

**Server Members:**
- Alice (English role) 🇺🇸
- Juan (Spanish role) 🇪🇸
- Marie (French role) 🇫🇷
- Yuki (Japanese role) 🇯🇵

**Trigger:**
Someone types: "FIRE in the kitchen!"

**Results:**

**Channel (public):**
```
🚨 SOS Triggered: Fire alarm activated! Evacuate immediately!
```

**Alice's DM (English):**
```
🚨 SOS ALERT 🚨
From: @user in Test Server
Message: Fire alarm activated! Evacuate immediately!

This is an emergency alert from your server.
```

**Juan's DM (Spanish):**
```
🚨 SOS ALERT 🚨
From: @user in Test Server
Message: ¡Alarma de incendio activada! ¡Evacúen inmediatamente!

This is an emergency alert from your server.
```

**Marie's DM (French):**
```
🚨 SOS ALERT 🚨
From: @user in Test Server
Message: Alarme incendie activée ! Évacuez immédiatement !

This is an emergency alert from your server.
```

**Yuki's DM (Japanese):**
```
🚨 SOS ALERT 🚨
From: @user in Test Server
Message: 火災警報が作動しました！直ちに避難してください！

This is an emergency alert from your server.
```

### Scenario 2: Mixed Language User

If a user has multiple language roles (e.g., English + Spanish), the system uses their **first language role** for translation.

## DM Notification Details

### Who Gets Notified?
✅ Users with at least one language role  
❌ Bots  
❌ The person who triggered the SOS  
❌ Users without any language roles

### Message Format
```
🚨 SOS ALERT 🚨
From: @username in Server Name
Message: [Translated SOS message]

This is an emergency alert from your server.
```

### Privacy & Permissions
- DMs are sent directly to users (not visible to others)
- If a user has DMs disabled, the bot logs the failure but continues
- No personal information is shared beyond the sender's username and server name

## Technical Details

### Implementation
- **Module**: `core/engines/input_engine.py`
- **Method**: `_send_sos_dms(guild, sos_message, sender)`
- **Translation**: Uses `TranslationOrchestrator.translate_text_for_user()`
- **Language Detection**: Uses `RoleManager.get_user_languages()`

### Error Handling
- Translation failures → fallback to English
- DM failures (Forbidden) → logged, not raised
- Missing dependencies → graceful degradation
- No language roles → no DMs sent

### Logging
```python
# Success
"Sent SOS DM to user 12345 (User1) in language: es"

# Summary
"SOS DM broadcast complete: 15 sent, 2 failed"

# Failure (DMs disabled)
"Cannot DM user 67890 (DMs disabled or blocked)"

# Failure (translation)
"Translation failed for user 12345 (target: fr), using original message"
```

## Testing

### Unit Tests
Location: `tests/core/test_sos_translation.py`

**Test Coverage:**
- ✅ Channel alert is sent
- ✅ DMs sent to users with language roles
- ✅ Messages translated to target language
- ✅ English users receive English message (no translation)
- ✅ Translation failures use fallback message
- ✅ DM failures handled gracefully
- ✅ Users without language roles are skipped
- ✅ Bots and sender are excluded

### Manual Testing
1. Set up SOS keyword: `/sos add keyword:"test" phrase:"This is a test alert"`
2. Assign language roles to test users
3. Send message containing "test"
4. Verify:
   - Channel alert appears
   - Each user with language role receives DM
   - Messages are in correct language
   - Original sender doesn't get DM

## Performance Considerations

### Scalability
- **Small servers (<50 members)**: Instant delivery
- **Medium servers (50-200 members)**: 1-5 seconds
- **Large servers (>200 members)**: May take 10+ seconds

### Rate Limits
- Discord: 5 DMs per second per bot
- Translation APIs: Varies by provider
  - DeepL: 500,000 chars/month (free tier)
  - MyMemory: 1,000 requests/day (free tier)

### Optimization
- Only users with language roles receive DMs
- Translation requests are cached (via TranslationOrchestrator)
- Failed DMs don't block other notifications

## Best Practices

### For Server Administrators
1. **Keep SOS messages concise** - shorter messages translate better
2. **Use clear, simple language** - avoid idioms and slang
3. **Test before emergencies** - verify DMs work and translations are accurate
4. **Encourage language role assignment** - more coverage = better alerts
5. **Set up multiple keywords** - different emergency types

### For Bot Operators
1. **Monitor translation API quotas** - avoid hitting limits during emergencies
2. **Review logs regularly** - check for DM delivery issues
3. **Keep translation services configured** - fallback ensures delivery
4. **Test with multiple languages** - verify quality of translations

## Troubleshooting

### Users Not Receiving DMs

**Problem**: Some users don't get the alert

**Checklist:**
- ✅ Does user have a language role?
- ✅ Are user's DMs enabled for the server?
- ✅ Is the bot blocked by the user?
- ✅ Check bot logs for errors

### Translations Not Working

**Problem**: Messages sent in English to all users

**Checklist:**
- ✅ Are translation API keys configured?
- ✅ Check API quota/limits
- ✅ Review logs for translation errors
- ✅ Verify TranslationOrchestrator is loaded

### Channel Alert Not Posted

**Problem**: SOS keyword detected but no channel message

**Checklist:**
- ✅ Does bot have send message permission in channel?
- ✅ Is keyword configured correctly? (case-insensitive)
- ✅ Check InputEngine logs

## Future Enhancements (Optional)

- 🔮 **Multi-language support**: Send in ALL user's languages (not just first)
- 🔮 **Reaction-based acknowledgment**: Track who received/read the alert
- 🔮 **Priority levels**: Different alert types (low/medium/high/critical)
- 🔮 **Location tagging**: Include location information in alerts
- 🔮 **Audio alerts**: Text-to-speech notifications
- 🔮 **SMS integration**: Send critical alerts via SMS
- 🔮 **Alert history**: Log all SOS triggers with timestamps

## Related Documentation

- [Role Management](ARCHITECTURE.md#role-manager)
- [Translation System](ARCHITECTURE.md#translation-orchestrator)
- [Input Engine](ARCHITECTURE.md#input-engine)
- [SOS Phrase Configuration](OPERATIONS.md#sos-commands)

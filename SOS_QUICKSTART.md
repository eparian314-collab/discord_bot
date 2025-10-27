# 🚨 SOS Translation Feature - Quick Start

## What's New?

When an SOS keyword is detected, the bot now:
1. ✅ Posts alert in the channel (as before)
2. ✅ **NEW**: Sends DMs to ALL users with language roles
3. ✅ **NEW**: Automatically translates message to each user's language

## Setup (3 Steps)

### Step 1: Configure Translation APIs
```env
# In your .env file
DEEPL_API_KEY=your_deepl_key_here
MYMEMORY_API_KEY=your_mymemory_key
MYMEMORY_USER_EMAIL=your_email@example.com
```

### Step 2: Users Need Language Roles
Users must have at least one language role assigned:
- Use `/language add <language>` to assign roles
- Examples: English, Spanish, French, Japanese, etc.

### Step 3: Configure SOS Keywords
```bash
# Add emergency keywords
/sos add keyword:"fire" phrase:"Fire alarm! Evacuate now!"
/sos add keyword:"medical" phrase:"Medical emergency - first aid needed"
/sos add keyword:"intruder" phrase:"Security alert - intruder detected"
```

## How It Works

### Example: International Server

**Setup:**
- Alice has "English" role 🇺🇸
- Juan has "Spanish" role 🇪🇸  
- Marie has "French" role 🇫🇷

**Someone types:** "FIRE in the kitchen!"

**Results:**
```
Channel (public):
🚨 SOS Triggered: Fire alarm! Evacuate now!

Alice's DM (English):
🚨 SOS ALERT 🚨
From: @user in Server Name
Message: Fire alarm! Evacuate now!

Juan's DM (Spanish):
🚨 SOS ALERT 🚨
From: @user in Server Name
Message: ¡Alarma de incendio! ¡Evacuar ahora!

Marie's DM (French):
🚨 SOS ALERT 🚨
From: @user in Server Name
Message: Alarme incendie ! Évacuez maintenant !
```

## Key Features

✅ **Automatic Translation** - DeepL or MyMemory APIs  
✅ **Direct Messaging** - Private alerts to all language role users  
✅ **Fallback Support** - English message if translation fails  
✅ **Privacy Friendly** - Respects DM settings  
✅ **Bot Exclusion** - Bots don't receive alerts  
✅ **Sender Exclusion** - Person who triggered SOS doesn't get DM  

## Testing

### Quick Test
```bash
# 1. Add test keyword
/sos add keyword:"test123" phrase:"This is a test emergency alert"

# 2. Assign yourself a non-English language role
/language add Spanish

# 3. Trigger the SOS
Type in chat: "test123"

# 4. Check your DMs
You should receive a Spanish translation!
```

## Troubleshooting

### Not Getting DMs?
- ✅ Do you have a language role? Check with `/language list`
- ✅ Are your DMs enabled? Server Settings → Privacy Settings
- ✅ Did you trigger the alert yourself? (Senders don't get DMs)

### Messages in English Only?
- ✅ Check translation API keys are set
- ✅ Verify API quota hasn't been exceeded
- ✅ Check bot logs for translation errors

### Channel Alert Not Showing?
- ✅ Bot needs "Send Messages" permission
- ✅ Verify keyword is configured: `/sos list`
- ✅ Keywords are case-insensitive

## Commands Reference

```bash
# SOS Configuration
/sos add keyword:"word" phrase:"alert message"  # Add/update keyword
/sos remove keyword:"word"                      # Remove keyword
/sos list                                       # Show all keywords
/sos clear                                      # Remove all keywords

# Language Management
/language add <language>         # Add language role
/language remove <language>      # Remove language role
/language list                   # Show your language roles
```

## Performance

- **Small servers (<50 users)**: Instant
- **Medium servers (50-200 users)**: 1-5 seconds
- **Large servers (>200 users)**: 5-15 seconds

## Best Practices

### For Emergencies
1. Keep messages **short and clear**
2. Use **simple language** (translates better)
3. Avoid idioms, slang, and cultural references
4. Test keywords before actual emergencies

### For Server Admins
1. **Test regularly** - Verify translations are accurate
2. **Multiple keywords** - Different emergency types
3. **Encourage language roles** - Better coverage
4. **Monitor API limits** - Check DeepL/MyMemory quotas

## Full Documentation

For detailed information, see: [SOS_TRANSLATION.md](SOS_TRANSLATION.md)

---

**Questions?** Check the logs: `tmp_debug/error_logs.jsonl`

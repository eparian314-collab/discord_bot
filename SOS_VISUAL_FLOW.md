# 🚨 SOS Translation System - Visual Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Discord Server                              │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  User Types: "fire"                                           │ │
│  └────────────────────┬──────────────────────────────────────────┘ │
│                       │                                             │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    InputEngine.on_message()                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. Detect keyword "fire" in EMERGENCY_KEYWORDS              │  │
│  │  2. Get mapped message: "Fire alarm! Evacuate now!"          │  │
│  └────────────────────┬─────────────────────────────────────────┘  │
│                       │                                             │
│                       ▼                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  _trigger_sos(message, "Fire alarm! Evacuate now!")          │  │
│  └────────────────────┬─────────────────────────────────────────┘  │
└────────────────────────┼──────────────────────────────────────────┘
                        │
                        ├──────────────────┬───────────────────────┐
                        │                  │                       │
                        ▼                  ▼                       ▼
         ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
         │ Channel Alert    │  │  _send_sos_dms() │  │ Add 🆘 Reaction  │
         │ "🚨 SOS: Fire    │  │   (NEW SYSTEM)   │  │                  │
         │  alarm! Evacuate"│  │                  │  │                  │
         └──────────────────┘  └────────┬─────────┘  └──────────────────┘
                                        │
                        ┌───────────────┴────────────────┐
                        │  Iterate Guild Members         │
                        └───────────────┬────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
           ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
           │ Member 1       │  │ Member 2       │  │ Member 3       │
           │ (Bot - SKIP)   │  │ (Sender - SKIP)│  │ (Has Lang Role)│
           └────────────────┘  └────────────────┘  └────────┬───────┘
                                                             │
                                                             ▼
                                        ┌────────────────────────────────┐
                                        │ RoleManager.get_user_languages │
                                        │ Returns: ["es"] (Spanish)      │
                                        └────────────┬───────────────────┘
                                                     │
                                        ┌────────────▼───────────────────┐
                                        │ Target Language: "es"          │
                                        │ Is English? NO → Translate     │
                                        └────────────┬───────────────────┘
                                                     │
                                        ┌────────────▼────────────────────┐
                                        │ TranslationOrchestrator         │
                                        │ .translate_text_for_user()      │
                                        │                                 │
                                        │ Input: "Fire alarm! Evacuate!"  │
                                        │ Target: "es"                    │
                                        │                                 │
                                        │ Try DeepL API → Success! ✓      │
                                        │ Returns: "¡Alarma de incendio!" │
                                        └────────────┬────────────────────┘
                                                     │
                                        ┌────────────▼────────────────────┐
                                        │ Build DM Message:               │
                                        │ ┌─────────────────────────────┐ │
                                        │ │ 🚨 SOS ALERT 🚨             │ │
                                        │ │ From: @user in Test Server  │ │
                                        │ │ Message: ¡Alarma de         │ │
                                        │ │ incendio! ¡Evacuar ahora!   │ │
                                        │ │                             │ │
                                        │ │ This is an emergency alert. │ │
                                        │ └─────────────────────────────┘ │
                                        └────────────┬────────────────────┘
                                                     │
                                        ┌────────────▼────────────────────┐
                                        │ member.send(dm_alert)           │
                                        │ Status: SUCCESS ✓               │
                                        └─────────────────────────────────┘
```

## User Flow Comparison

### Before (Channel Only)
```
User Message → Keyword Detected → Channel Alert
                                        ↓
                    Users must actively monitor channel
                           (might miss alert)
```

### After (Channel + DMs)
```
User Message → Keyword Detected → Channel Alert
                                        ↓
                     ┌──────────────────┴──────────────────┐
                     │                                     │
              Channel Alert                         DM Broadcast
                     │                                     │
           All users in channel              All users with language roles
                     │                                     │
              See alert if online              Get DM notification
                     │                                     │
              English only                    Translated to user's language
```

## Language Detection & Translation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                       For Each User                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │ Get User's Language Roles      │
        │ (via RoleManager)              │
        └────────────┬───────────────────┘
                     │
        ┌────────────▼───────────────┐
        │ Has Language Role?         │
        └────────────┬───────────────┘
                     │
           ┌─────────┴─────────┐
           │                   │
          NO                  YES
           │                   │
           ▼                   ▼
    ┌──────────┐      ┌────────────────┐
    │   SKIP   │      │ Get Primary    │
    │   USER   │      │ Language Code  │
    └──────────┘      └────────┬───────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │ Is English "en"? │
                    └─────────┬────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
                   YES                  NO
                    │                    │
                    ▼                    ▼
         ┌─────────────────┐  ┌──────────────────┐
         │ Send Original   │  │ Translate via    │
         │ English Message │  │ Orchestrator     │
         └─────────┬───────┘  └────────┬─────────┘
                   │                    │
                   │          ┌─────────┴─────────┐
                   │          │                   │
                   │    Translation           Translation
                   │      Success              Failure
                   │          │                   │
                   │          ▼                   ▼
                   │  ┌──────────────┐  ┌─────────────────┐
                   │  │ Use          │  │ Use Original    │
                   │  │ Translated   │  │ English (FB)    │
                   │  │ Message      │  │                 │
                   │  └──────┬───────┘  └────────┬────────┘
                   │         │                    │
                   └─────────┴────────────────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │ Send DM to User  │
                   └────────┬─────────┘
                            │
                  ┌─────────┴──────────┐
                  │                    │
             DM Success           DM Failed
                  │                    │
                  ▼                    ▼
         ┌────────────────┐  ┌─────────────────┐
         │ Log Success    │  │ Log Warning     │
         │ Continue Next  │  │ Continue Next   │
         └────────────────┘  └─────────────────┘
```

## Translation Provider Selection

```
┌──────────────────────────────────────────────┐
│  TranslationOrchestrator.translate()         │
└────────────────┬─────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────┐
    │ Check DeepL Support    │
    │ for Target Language?   │
    └────────────┬───────────┘
                 │
       ┌─────────┴─────────┐
       │                   │
    YES ✓                 NO ✗
       │                   │
       ▼                   ▼
┌──────────────┐    ┌──────────────────┐
│ Try DeepL    │    │ Check MyMemory   │
│ API Call     │    │ Support?         │
└──────┬───────┘    └────────┬─────────┘
       │                     │
       │          ┌──────────┴──────────┐
       │          │                     │
       │        YES ✓                  NO ✗
       │          │                     │
       │          ▼                     ▼
       │   ┌──────────────┐    ┌────────────┐
       │   │ Try MyMemory │    │ Return     │
       │   │ API Call     │    │ NULL       │
       │   └──────┬───────┘    └────────────┘
       │          │
       └──────────┴─────────────┐
                                │
                                ▼
                    ┌───────────────────┐
                    │ Return Result     │
                    │ (text, src, prov) │
                    └───────────────────┘
```

## Error Handling Flow

```
┌────────────────────────────────────────┐
│  DM Sending Process                    │
└────────────────┬───────────────────────┘
                 │
                 ▼
    ┌────────────────────────┐
    │ Try: member.send(msg)  │
    └────────────┬───────────┘
                 │
       ┌─────────┴──────────┐
       │                    │
   Success ✓           Exception
       │                    │
       ▼                    ▼
┌──────────────┐    ┌────────────────┐
│ Log Success  │    │ What type?     │
│ Add to sent  │    └────────┬───────┘
│ Continue     │             │
└──────────────┘   ┌─────────┴─────────┐
                   │                   │
            discord.Forbidden    discord.HTTPException
                   │                   │
                   ▼                   ▼
         ┌──────────────────┐  ┌───────────────┐
         │ Log: "DMs        │  │ Log: "Failed  │
         │ disabled"        │  │ to send"      │
         │ Increment failed │  │ Increment     │
         │ Continue         │  │ failed        │
         └──────────────────┘  │ Continue      │
                               └───────────────┘
```

## Statistics & Logging

```
After Broadcasting to All Members:
┌──────────────────────────────────────────┐
│  Summary Statistics                      │
│  ┌────────────────────────────────────┐  │
│  │ Members Processed: 25              │  │
│  │ - Bots Skipped: 3                  │  │
│  │ - Sender Skipped: 1                │  │
│  │ - No Lang Role Skipped: 5          │  │
│  │ - DMs Sent: 14                     │  │
│  │ - DMs Failed: 2                    │  │
│  │                                    │  │
│  │ Translations:                      │  │
│  │ - Spanish: 6                       │  │
│  │ - French: 4                        │  │
│  │ - Japanese: 2                      │  │
│  │ - English (no translation): 2      │  │
│  │                                    │  │
│  │ API Calls:                         │  │
│  │ - DeepL: 12 (success)              │  │
│  │ - MyMemory: 0 (not needed)         │  │
│  │ - Fallbacks: 0                     │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘

Log Output:
INFO: Sent SOS DM to user 12345 (User1) in language: es
INFO: Sent SOS DM to user 67890 (User2) in language: fr
DEBUG: Cannot DM user 11111 (DMs disabled or blocked)
INFO: SOS DM broadcast complete: 14 sent, 2 failed
```

## Multi-Language Server Example

```
Server: "Global Gamers" (100 members)
SOS Trigger: "medical emergency"
Message: "Medical emergency in voice channel! First aid needed!"

Distribution:
┌─────────────────────────────────────────────────────────────┐
│                    Language Breakdown                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  English (en)    : 35 users → Original message         │ │
│  │  Spanish (es)    : 20 users → "¡Emergencia médica!"   │ │
│  │  French (fr)     : 15 users → "Urgence médicale!"     │ │
│  │  German (de)     : 10 users → "Medizinischer Notfall!"│ │
│  │  Japanese (ja)   :  5 users → "医療緊急事態！"         │ │
│  │  Portuguese (pt) :  5 users → "Emergência médica!"    │ │
│  │  No Role         : 10 users → SKIPPED                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Total DMs Sent: 90                                         │
│  Translation API Calls: 55 (DeepL)                          │
│  Processing Time: ~3 seconds                                │
└─────────────────────────────────────────────────────────────┘
```

---

**Legend:**
- → : Flow direction
- ✓ : Success
- ✗ : Failure/No
- FB : Fallback

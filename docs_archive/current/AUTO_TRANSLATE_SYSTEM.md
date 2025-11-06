# Auto-Translation System

## Overview
The bot now automatically detects and translates non-English messages to English when configured, making communication easier for English-speaking members.

## Configuration

### Environment Variables (`.env`)

```properties
# Server default language (ISO 639-1 code)
SERVER_DEFAULT_LANGUAGE=en

# Enable/disable auto-translation
AUTO_TRANSLATE_ENABLED=true

# Minimum confidence to trigger auto-translation (0.0-1.0)
# Higher = more confident detection required before translating
AUTO_TRANSLATE_CONFIDENCE_THRESHOLD=0.7

# Minimum message length to attempt auto-translation
# Prevents false positives on short phrases like "ya", "ok", etc.
AUTO_TRANSLATE_MIN_LENGTH=15
```

## How It Works

### Detection Flow

1. **Message received** → Check if auto-translate enabled
2. **Length check** → Skip if message < minimum length
3. **User language roles** → Skip if user has English role
4. **Language detection** → Detect language with confidence scoring
5. **Confidence check** → Only translate if confidence ≥ threshold
6. **Language check** → Skip if already in English
7. **Translate** → Send embedded translation to channel

### Confidence Levels

| Confidence | Meaning | Example |
|-----------|---------|---------|
| 1.00 | Definitive - Non-Latin script | Japanese, Russian, Arabic |
| 0.85-0.90 | Very high - Strong indicators | French with accents + keywords |
| 0.70-0.80 | High - Good indicators | Spanish with multiple keywords |
| 0.50-0.70 | Medium - Some indicators | Romance languages without accents |
| 0.30-0.50 | Low - Likely English | ASCII text with few clues |
| 0.00 | Unknown | Unable to determine |

## Edge Case Handling

### English Slang Detection
Common slang terms are recognized as English with high confidence:
- **Internet slang**: lol, lmao, bruh, fr, ngl, idk, tbh
- **Gaming**: gg, ez, pog, sus
- **Casual**: ya, yeah, yep, nah, ok, bet

### Short Phrases
Messages under 15 characters are **not** auto-translated to avoid false positives:
- "ya" → Treated as English slang, not Japanese
- "ok" → Treated as English
- "no" → Could be Spanish/English, too ambiguous

### Mixed Content
The system analyzes word patterns, not just characters:
- Detects Romance languages even without accents when multiple keywords present
- "Hola como estas" → Spanish (0.75 confidence)
- Prioritizes script-specific characters (Cyrillic, CJK) over word analysis

## Supported Languages

### Definitive Detection (1.0 confidence)
- **CJK**: Chinese (zh), Japanese (ja), Korean (ko)
- **Cyrillic**: Russian (ru)
- **Other scripts**: Greek (el), Arabic (ar), Hebrew (he), Thai (th)

### Pattern-Based Detection (0.6-0.9 confidence)
- **Romance**: Spanish (es), French (fr), Portuguese (pt)
- **Germanic**: German (de)
- **Default**: English (en)

## User Experience

### When Auto-Translation Occurs

**Original message** (from user):
```
Bonjour comment allez-vous aujourd'hui
```

**Bot response** (in channel):
```
💬 @User
🌐 Auto-Translation
Hello how are you today

Detected: French (75% confident) → English
```

### When Auto-Translation is Skipped

- User has English language role
- Message is too short (<15 chars)
- Confidence is below threshold
- Language is already English
- Detection fails or is ambiguous

## Testing

Run the test script to verify detection:

```bash
python test_auto_translate.py
```

### Example Test Cases

| Input | Detected | Confidence | Auto-Translate? |
|-------|----------|------------|-----------------|
| "ya" | en | 0.95 | ❌ Too short |
| "lol this is funny bruh" | en | 0.85 | ❌ English |
| "Hola como estas mi amigo" | es | 0.75 | ✅ Spanish |
| "Bonjour comment allez-vous" | fr | 0.75 | ✅ French |
| "こんにちは" | ja | 1.00 | ✅ Japanese |
| "Привет мир" | ru | 1.00 | ✅ Russian |

## Implementation Details

### Code Locations

- **Detection**: `language_context/normalizer.py` → `detect_language_with_confidence()`
- **Auto-translate logic**: `core/engines/input_engine.py` → `_try_auto_translate()`
- **Output**: `core/engines/output_engine.py` → `send_auto_translation()`
- **Configuration**: `.env` file

### Integration Points

1. **InputEngine.handle_message()** - Main entry point
2. **Checks user language roles** - Via RoleManager
3. **Detects language** - Via normalizer
4. **Translates** - Via TranslationOrchestrator (DeepL → MyMemory fallback)
5. **Outputs** - Via OutputEngine with embed formatting

### Performance Considerations

- **Lightweight detection**: Rule-based, no external API calls
- **Caching**: User language roles cached by Discord.py
- **Skip fast**: Early returns for common cases (English role, short messages)
- **Fallback**: Uses existing translation infrastructure (DeepL/MyMemory)

## Best Practices

### Recommended Settings

**For international servers**:
```properties
AUTO_TRANSLATE_ENABLED=true
AUTO_TRANSLATE_CONFIDENCE_THRESHOLD=0.7
AUTO_TRANSLATE_MIN_LENGTH=15
```

**For mostly-English servers**:
```properties
AUTO_TRANSLATE_ENABLED=false
# Or increase threshold:
AUTO_TRANSLATE_CONFIDENCE_THRESHOLD=0.85
```

### User Guidance

Encourage users to:
1. **Assign language roles** - Prevents unnecessary auto-translations
2. **Use English when possible** - For clarity in international channels
3. **Report issues** - If wrong language detected or poor translations

### Admin Guidance

- Monitor auto-translation frequency in logs
- Adjust `CONFIDENCE_THRESHOLD` if too many/few translations
- Adjust `MIN_LENGTH` if short phrases problematic
- Consider disabling for specific channels (future enhancement)

## Limitations

1. **ASCII-only Spanish/French**: Lower confidence without accents
2. **Very short messages**: May be ambiguous (intentionally skipped)
3. **Code/commands**: May trigger false positives (filtered by length)
4. **Mixed languages**: Detects dominant language only
5. **Slang evolution**: New slang may not be in dictionary

## Future Enhancements

- [ ] Per-channel enable/disable
- [ ] Whitelist/blacklist specific users
- [ ] ML-based detection (langdetect library)
- [ ] Confidence adjustment UI for admins
- [ ] Translation memory/cache
- [ ] Multi-language server defaults

---

**Status**: ✅ Implemented and tested
**Version**: 1.0
**Last Updated**: 2024-10-28

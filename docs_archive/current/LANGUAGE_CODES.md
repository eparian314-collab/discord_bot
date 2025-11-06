# Language Code Reference

## Supported Language Codes

This bot now supports **60+ languages** with proper code mapping. Users can use either:
- Language codes (e.g., `tl`, `es`, `fr`)
- Full language names (e.g., `Tagalog`, `Spanish`, `French`)

### Complete Language List

| Language | Code | Aliases |
|----------|------|---------|
| **Afrikaans** | `af` | afrikaans |
| **Albanian** | `sq` | albanian |
| **Arabic** | `ar` | arabic |
| **Bengali** | `bn` | bengali |
| **Bulgarian** | `bg` | bg, bulgarian |
| **Catalan** | `ca` | catalan |
| **Chinese** | `zh` | zh, chinese, mandarin, simplified, zh-cn, zh-hans, zh-hant |
| **Croatian** | `hr` | croatian |
| **Czech** | `cs` | cs, czech |
| **Danish** | `da` | da, danish |
| **Dutch** | `nl` | nl, dutch |
| **English** | `en` | en, english, en-gb, en-us, en-uk |
| **Estonian** | `et` | et, estonian |
| **Finnish** | `fi` | fi, finnish |
| **French** | `fr` | fr, french |
| **German** | `de` | de, german |
| **Greek** | `el` | el, greek |
| **Gujarati** | `gu` | gujarati |
| **Hebrew** | `he` | hebrew |
| **Hindi** | `hi` | hindi |
| **Hungarian** | `hu` | hu, hungarian |
| **Icelandic** | `is` | icelandic |
| **Indonesian** | `id` | id, indonesian |
| **Irish** | `ga` | irish |
| **Italian** | `it` | it, italian |
| **Japanese** | `ja` | ja, japanese |
| **Kannada** | `kn` | kannada |
| **Korean** | `ko` | ko, korean |
| **Latvian** | `lv` | lv, latvian |
| **Lithuanian** | `lt` | lt, lithuanian |
| **Malay** | `ms` | malay |
| **Malayalam** | `ml` | malayalam |
| **Maltese** | `mt` | maltese |
| **Marathi** | `mr` | marathi |
| **Norwegian** | `nb` | nb, no, norwegian |
| **Persian** | `fa` | persian |
| **Polish** | `pl` | pl, polish |
| **Portuguese** | `pt` | pt, portuguese, pt-br, pt-pt |
| **Punjabi** | `pa` | punjabi |
| **Romanian** | `ro` | ro, romanian |
| **Russian** | `ru` | ru, russian |
| **Serbian** | `sr` | serbian |
| **Slovak** | `sk` | sk, slovak |
| **Slovenian** | `sl` | sl, slovenian |
| **Spanish** | `es` | es, spanish |
| **Swahili** | `sw` | swahili |
| **Swedish** | `sv` | sv, swedish |
| **Tagalog** | `tl` | **tl**, tagalog, fil, filipino |
| **Tamil** | `ta` | tamil |
| **Telugu** | `te` | telugu |
| **Thai** | `th` | thai |
| **Turkish** | `tr` | tr, turkish |
| **Ukrainian** | `uk` | uk, ukrainian |
| **Urdu** | `ur` | urdu |
| **Vietnamese** | `vi` | vietnamese |
| **Welsh** | `cy` | welsh |

## Usage Examples

### Using Language Codes
```bash
/language add tl           # Tagalog (Filipino)
/language add es           # Spanish
/language add fr           # French
/language add ja           # Japanese
/language add hi           # Hindi
/language add ar           # Arabic
```

### Using Full Names
```bash
/language add Tagalog      # Same as 'tl'
/language add Spanish      # Same as 'es'
/language add French       # Same as 'fr'
/language add Japanese     # Same as 'ja'
```

### Using Flags
```bash
/language add 🇵🇭          # Philippines → Tagalog
/language add 🇪🇸          # Spain → Spanish
/language add 🇫🇷          # France → French
/language add 🇯🇵          # Japan → Japanese
```

## Flag to Language Mapping

| Flag | Language(s) |
|------|-------------|
| 🇺🇸 🇬🇧 | English |
| 🇪🇸 🇲🇽 | Spanish |
| 🇫🇷 | French |
| 🇩🇪 | German |
| 🇯🇵 | Japanese |
| 🇨🇳 | Chinese |
| 🇷🇺 | Russian |
| 🇮🇹 | Italian |
| 🇵🇹 🇧🇷 | Portuguese |
| 🇰🇷 | Korean |
| 🇳🇱 | Dutch |
| 🇵🇱 | Polish |
| 🇹🇷 | Turkish |
| 🇸🇪 | Swedish |
| 🇳🇴 | Norwegian |
| 🇩🇰 | Danish |
| 🇫🇮 | Finnish |
| 🇮🇩 | Indonesian |
| 🇺🇦 | Ukrainian |
| 🇷🇴 | Romanian |
| 🇭🇺 | Hungarian |
| 🇨🇿 | Czech |
| 🇬🇷 | Greek |
| 🇧🇬 | Bulgarian |
| 🇪🇪 | Estonian |
| 🇱🇹 | Lithuanian |
| 🇱🇻 | Latvian |
| 🇸🇰 | Slovak |
| 🇸🇮 | Slovenian |
| 🇵🇭 | **Tagalog**, English |
| 🇮🇳 | Hindi, English |
| 🇵🇰 | Urdu, English |
| 🇻🇳 | Vietnamese |
| 🇹🇭 | Thai |
| 🇮🇷 | Persian |
| 🇮🇱 | Hebrew |
| 🇦🇪 🇸🇦 🇪🇬 | Arabic |
| 🇮🇪 | Irish, English |
| 🇮🇸 | Icelandic |
| 🇲🇾 | Malay |
| 🇧🇩 | Bengali |
| 🇱🇰 | Tamil |
| 🇦🇱 | Albanian |
| 🇷🇸 | Serbian |
| 🇭🇷 | Croatian |
| 🇰🇪 | Swahili, English |

## Multi-Language Flags

Some flags map to multiple languages:
- 🇨🇭 Switzerland → German, French, Italian
- 🇧🇪 Belgium → Dutch, French, German
- 🇨🇦 Canada → English, French
- 🇵🇭 Philippines → Tagalog, English
- 🇮🇳 India → Hindi, English
- 🇵🇰 Pakistan → Urdu, English
- 🇮🇪 Ireland → Irish, English
- 🇰🇪 Kenya → Swahili, English

## Translation Support

### DeepL (High Quality)
DeepL supports 31 languages for premium translations.

### MyMemory (Fallback)
MyMemory supports 100+ languages as a fallback option.

## Notes

- Language codes are **case-insensitive** (e.g., ES, es, Es all work)
- Full names are also case-insensitive (e.g., Spanish, spanish, SPANISH)
- The bot will show the code in selection views but will properly map it to the language
- When using `/language add`, the bot will:
  1. Recognize the input code or name
  2. Create/assign the proper role with the full language name
  3. Use the normalized code for translation API calls

## Common Questions

**Q: Why does the autocomplete show codes instead of full names?**  
A: The bot internally maps codes to full language names. Roles will use full language names, not codes.

**Q: Can I use alternate names for languages?**  
A: Yes! Many languages have multiple aliases (e.g., "Mandarin" → "zh", "Filipino" → "tl").

**Q: What if I type a language code in all caps?**  
A: It works! Language codes are case-insensitive.

**Q: How do I see all my language roles?**  
A: Use `/language list` to see all assigned language roles.

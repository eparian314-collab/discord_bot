import json

# Load language map
with open('language_context/language_map.json', 'r') as f:
    data = json.load(f)

aliases = data['language_aliases']
unique_codes = set(aliases.values())

print("=" * 70)
print("🌍 LANGUAGE COVERAGE REPORT")
print("=" * 70)
print(f"\n📊 Statistics:")
print(f"  - Total alias entries: {len(aliases)}")
print(f"  - Unique language codes: {len(unique_codes)}")

print(f"\n🗣️  All {len(unique_codes)} Supported Languages:")
print("-" * 70)

# Create a reverse mapping: code -> list of aliases
code_to_aliases = {}
for alias, code in aliases.items():
    if code not in code_to_aliases:
        code_to_aliases[code] = []
    code_to_aliases[code].append(alias)

# Language names for display
lang_names = {
    'af': 'Afrikaans',
    'ar': 'Arabic',
    'bg': 'Bulgarian',
    'bn': 'Bengali',
    'ca': 'Catalan',
    'cy': 'Welsh',
    'cs': 'Czech',
    'da': 'Danish',
    'de': 'German',
    'el': 'Greek',
    'en': 'English',
    'es': 'Spanish',
    'et': 'Estonian',
    'fa': 'Persian',
    'fi': 'Finnish',
    'fr': 'French',
    'ga': 'Irish',
    'gu': 'Gujarati',
    'he': 'Hebrew',
    'hi': 'Hindi',
    'hr': 'Croatian',
    'hu': 'Hungarian',
    'id': 'Indonesian',
    'is': 'Icelandic',
    'it': 'Italian',
    'ja': 'Japanese',
    'kn': 'Kannada',
    'ko': 'Korean',
    'lt': 'Lithuanian',
    'lv': 'Latvian',
    'ml': 'Malayalam',
    'mr': 'Marathi',
    'ms': 'Malay',
    'mt': 'Maltese',
    'nb': 'Norwegian',
    'nl': 'Dutch',
    'pa': 'Punjabi',
    'pl': 'Polish',
    'pt': 'Portuguese',
    'ro': 'Romanian',
    'ru': 'Russian',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'sq': 'Albanian',
    'sr': 'Serbian',
    'sv': 'Swedish',
    'sw': 'Swahili',
    'ta': 'Tamil',
    'te': 'Telugu',
    'th': 'Thai',
    'tl': 'Tagalog',
    'tr': 'Turkish',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'vi': 'Vietnamese',
    'zh': 'Chinese'
}

count = 0
for code in sorted(unique_codes):
    count += 1
    name = lang_names.get(code, code.upper())
    alias_count = len(code_to_aliases[code])
    sample_aliases = ', '.join(sorted(code_to_aliases[code])[:4])
    if alias_count > 4:
        sample_aliases += f' (+{alias_count - 4} more)'
    print(f"{count:2d}. {name:15s} [{code:2s}] - {alias_count:2d} aliases: {sample_aliases}")

print("\n" + "=" * 70)
print("✅ Summary:")
print(f"   The bot covers {len(unique_codes)} languages with {len(aliases)} total aliases!")
print("=" * 70)

"""
Test language code normalization for all languages.
"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from language_context.context_utils import map_alias_to_code, load_language_map, normalize_lang_code

# Load language map
lang_map = load_language_map()

print("=" * 70)
print("🌍 LANGUAGE CODE NORMALIZATION TEST")
print("=" * 70)

# Test cases: (input, expected_output)
test_cases = [
    # Spanish
    ("es", "es"),
    ("ES", "es"),
    ("spanish", "es"),
    ("Spanish", "es"),
    ("SPANISH", "es"),
    
    # French
    ("fr", "fr"),
    ("FR", "fr"),
    ("french", "fr"),
    ("French", "fr"),
    
    # Tagalog/Filipino
    ("tl", "tl"),
    ("TL", "tl"),
    ("tagalog", "tl"),
    ("Tagalog", "tl"),
    ("TAGALOG", "tl"),
    ("filipino", "tl"),
    ("Filipino", "tl"),
    ("fil", "tl"),
    
    # Spanish
    ("es", "es"),
    ("ES", "es"),
    ("spanish", "es"),
    ("Spanish", "es"),
    
    # French
    ("fr", "fr"),
    ("FR", "fr"),
    ("french", "fr"),
    ("French", "fr"),
    
    # Japanese
    ("ja", "ja"),
    ("JA", "ja"),
    ("japanese", "ja"),
    ("Japanese", "ja"),
    
    # Chinese
    ("zh", "zh"),
    ("ZH", "zh"),
    ("chinese", "zh"),
    ("Chinese", "zh"),
    ("mandarin", "zh"),
    ("zh-CN", "zh"),
    ("zh-Hans", "zh"),
    
    # Hindi
    ("hi", "hi"),
    ("HI", "hi"),
    ("hindi", "hi"),
    ("Hindi", "hi"),
    
    # Arabic
    ("ar", "ar"),
    ("AR", "ar"),
    ("arabic", "ar"),
    ("Arabic", "ar"),
    
    # Vietnamese
    ("vi", "vi"),
    ("VI", "vi"),
    ("vietnamese", "vi"),
    ("Vietnamese", "vi"),
    
    # Thai
    ("th", "th"),
    ("TH", "th"),
    ("thai", "th"),
    ("Thai", "th"),
]

print(f"\n📋 Testing {len(test_cases)} language variations...\n")

passed = 0
failed = 0
errors = []

for input_token, expected in test_cases:
    result = map_alias_to_code(input_token, language_map=lang_map)
    
    if result == expected:
        print(f"✅ '{input_token}' → '{result}' (expected: '{expected}')")
        passed += 1
    else:
        print(f"❌ '{input_token}' → '{result}' (expected: '{expected}')")
        failed += 1
        errors.append((input_token, result, expected))

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print("=" * 70)

if errors:
    print("\n⚠️  FAILED TESTS:")
    for inp, got, exp in errors:
        print(f"  - '{inp}': got '{got}', expected '{exp}'")
else:
    print("\n🎉 ALL TESTS PASSED!")
    print("\n✨ The bot will correctly handle:")
    print("   - Language codes (es, fr, ja, etc.)")
    print("   - Full language names (Spanish, French, Japanese, etc.)")
    print("   - Case-insensitive input (ES, es, Es all work)")
    print("   - Alternate names (Mandarin → zh, Filipino → tl)")

print("\n💡 Usage in Discord:")
print("   /language add es        → Creates 'Spanish' role")
print("   /language add Spanish   → Creates 'Spanish' role")
print("   /language add fr        → Creates 'French' role")
print("   All will use normalized codes for translation API calls")

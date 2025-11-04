"""
Quick test script for auto-translation language detection
"""

from discord_bot.language_context.normalizer import detect_language_with_confidence

# Test cases: (text, expected_language, min_confidence)
test_cases = [
    # English slang - should be detected as English with high confidence
    ("ya", "en", 0.9),
    ("lol bruh fr", "en", 0.8),
    ("ok", "en", 0.2),
    ("yeah nah ya know", "en", 0.8),
    
    # Short English phrases - lower confidence
    ("hello world", "en", 0.2),
    ("how are you", "en", 0.2),
    
    # Longer English text - medium confidence
    ("I think this is a good idea for the project", "en", 0.3),
    
    # Spanish - should detect with good confidence
    ("Hola como estas amigo", "es", 0.6),
    ("Buenos días, cómo estás hoy?", "es", 0.6),
    
    # French
    ("Bonjour comment allez-vous", "fr", 0.6),
    
    # Non-Latin scripts - should be 100% confident
    ("こんにちは", "ja", 1.0),
    ("Привет мир", "ru", 1.0),
    ("你好世界", "zh", 1.0),
    ("안녕하세요", "ko", 1.0),
    
    # Mixed/ambiguous
    ("idk maybe", "en", 0.7),
]

print("=" * 80)
print("LANGUAGE DETECTION WITH CONFIDENCE TESTS")
print("=" * 80)

passed = 0
failed = 0

for text, expected_lang, min_confidence in test_cases:
    detected_lang, confidence = detect_language_with_confidence(text)
    
    # Check if detection matches
    lang_match = detected_lang == expected_lang
    conf_match = confidence >= min_confidence if detected_lang == expected_lang else True
    
    status = "✓" if (lang_match and conf_match) else "✗"
    
    if lang_match and conf_match:
        passed += 1
    else:
        failed += 1
    
    print(f"{status} \"{text[:40]:<40}\" -> {detected_lang or 'None':>4} ({confidence:.2f})")
    if not lang_match or not conf_match:
        print(f"   Expected: {expected_lang} with confidence >= {min_confidence:.2f}")

print("=" * 80)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 80)

# Test auto-translate threshold logic
print("\nAUTO-TRANSLATE DECISION TESTS (threshold=0.7, min_length=15)")
print("=" * 80)

threshold = 0.7
min_length = 15

auto_translate_tests = [
    ("ya", False, "Too short + English slang"),
    ("hello world", False, "Too short"),
    ("lol this is funny bruh", False, "English detected"),
    ("Hola como estas mi amigo como te va", True, "Spanish with good confidence"),
    ("Bonjour comment allez-vous aujourd'hui", True, "French with good confidence"),
    ("I think this is a great idea for our project", False, "English"),
]

for text, should_translate, reason in auto_translate_tests:
    detected_lang, confidence = detect_language_with_confidence(text)
    
    # Auto-translate logic
    will_translate = (
        len(text) >= min_length and
        detected_lang is not None and
        detected_lang != 'en' and
        confidence >= threshold
    )
    
    status = "✓" if will_translate == should_translate else "✗"
    action = "TRANSLATE" if will_translate else "SKIP"
    
    print(f"{status} [{action}] \"{text[:35]:<35}\" | {detected_lang or 'None'} ({confidence:.2f})")
    print(f"   Reason: {reason}")

print("=" * 80)

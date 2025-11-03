# Translation Logic Flow Fix - Layered Approach

## Problem Analysis

The bot was echoing back the original text instead of translating because:

1. **No target preference**: User didn't specify a target language and hasn't set `/language assign`
2. **Default fallback**: `_resolve_target_code` was defaulting to "en" 
3. **Source detection**: Text detected as "en" (English)
4. **Logic skip**: Since source == target ("en" == "en"), system skipped translation
5. **UI fallback bug**: UI engine's `_extract_text` had `result.get("text") or str(result)` which stringified the dict when text was None

## Root Cause

The translation flow had **no way to detect** that the user needed to specify a target. It assumed "en" was always an acceptable default, causing English text to be returned unchanged.

## Solution: Multi-Layered Defense

### Layer 1: Context Engine - Smart Target Resolution
**File:** `language_context/context_engine.py`

#### Changes to `_resolve_target_code`:
- Returns `"auto"` instead of `"en"` when no preference is found
- Checks user language roles before falling back
- Signals to upper layers that target needs to be specified

```python
# Before: Always returned "en" as fallback
return self._apply_policy_target("en", policy)

# After: Returns "auto" to signal no preference
return self._apply_policy_target("auto", policy)
```

#### Changes to `plan_for_author`:
- Detects `tgt == "auto"` case
- Returns special context with `needs_target: True`
- Prevents job creation when target is unknown

```python
# NEW: If target is "auto", it means no preference was found
if tgt == "auto":
    return {
        "job": None,
        "context": {
            "src": src,
            "tgt": "auto",
            "needs_target": True,
            "reason": "no_target_preference"
        }
    }
```

#### Changes to `translate_for_author_via_orchestrator`:
- Handles `needs_target` case with special metadata
- Differentiates between "no target" and "same language"

```python
if context.get("needs_target"):
    empty = TranslationResponse(
        text=None,
        src=context.get("src", "unknown"),
        tgt="auto",
        provider=None,
        confidence=0.0,
        meta={"reason": "no_target_preference", "needs_target": True}
    )
    return {"job": None, "context": context, "response": empty}
```

### Layer 2: Translation Cog - User-Friendly Messages
**File:** `cogs/translation_cog.py`

#### Changes to `_perform_translation`:
- Detects `needs_target` metadata
- Shows helpful error message with examples
- Differentiates between "need target" and "already in target language"

```python
# Check if user needs to specify a target (no preference set)
if not job and response:
    meta = getattr(response, "meta", {}) or {}
    if meta.get("needs_target"):
        src_lang = context.get("src", "unknown")
        await self.ui.show_error(
            interaction,
            f"🌍 **Please specify a target language!**\n\n"
            f"Your text appears to be in **{src_lang.upper()}**.\n\n"
            f"**Option 1:** Use the `target` parameter:\n"
            f"```/translate text:Hello target:es```\n\n"
            f"**Option 2:** Set your preferred language:\n"
            f"```/language assign <language>```\n\n"
            f"**Option 3:** Get a language role from staff",
            ephemeral=True
        )
        return
```

### Layer 3: UI Engine - Safe Text Extraction
**File:** `core/engines/translation_ui_engine.py`

#### Changes to `_extract_text`:
- Never falls back to `str(result)` when text is None
- Checks metadata for reasons why text is None
- Returns helpful messages instead of dict stringification

```python
# Before: Dangerous fallback
if isinstance(result, dict):
    return result.get("text") or str(result)  # BAD: stringifies dict!

# After: Safe handling
if isinstance(result, dict):
    text = result.get("text")
    if text is not None:
        return str(text)
    # Check metadata for why there's no text
    meta = result.get("meta", {})
    if meta.get("reason") == "no_translation_needed":
        ...
    return "No translation was produced."
```

## Cross-Compatibility Guarantees

### Backward Compatibility
1. **Existing behavior preserved**: Users with language preferences or explicit targets work exactly as before
2. **Role-based targeting**: New role check in `_resolve_target_code` doesn't break existing role systems
3. **Metadata non-breaking**: New metadata fields (`needs_target`, `reason`) are optional additions
4. **UI fallbacks**: UI engine still handles old response formats without metadata

### Forward Compatibility
1. **"auto" target**: New special value that won't conflict with ISO language codes
2. **Metadata extensibility**: `meta` dict can hold new fields without breaking existing code
3. **Context dictionary**: Additional context fields can be added without affecting existing consumers
4. **Response dataclass**: TranslationResponse is extensible via `meta` field

### Integration Points Protected
1. **Orchestrator interface**: No changes to orchestrator API
2. **Adapter interface**: No changes to translator adapter APIs
3. **Job structure**: TranslationJob format unchanged
4. **Cache interface**: No changes to cache manager APIs

## Testing Scenarios

### Scenario 1: User with NO preference, NO target
**Command:** `/translate text:Hello`
**Expected:** Error message asking user to specify target
**Result:** ✅ Layer 1 detects auto, Layer 2 shows helpful message

### Scenario 2: User with NO preference, WITH target
**Command:** `/translate text:Hello target:es`
**Expected:** Translation to Spanish
**Result:** ✅ Layer 1 uses force_tgt, normal flow continues

### Scenario 3: User with preference set
**Command:** `/language assign es` then `/translate text:Hello`
**Expected:** Translation to Spanish (from cache)
**Result:** ✅ Layer 1 reads cache, normal flow continues

### Scenario 4: User with language role
**Command:** User has "Spanish" role, `/translate text:Hello`
**Expected:** Translation to Spanish (from role)
**Result:** ✅ Layer 1 checks roles, normal flow continues

### Scenario 5: Same language translation
**Command:** `/translate text:Hello target:en`
**Expected:** Message saying "already in EN"
**Result:** ✅ Layer 2 detects same language case

### Scenario 6: Arabic to Spanish (existing working case)
**Command:** `/translate text:مرحبا target:es`
**Expected:** Translation "Hola"
**Result:** ✅ No changes to working translation flow

## Edge Cases Handled

1. **Empty text**: Handled at cog level before context engine
2. **Invalid language code**: Handled by `_normalize_target_code` 
3. **Orchestrator failure**: Existing fallback chains still work
4. **Cache errors**: Try-except blocks preserved
5. **Role manager unavailable**: Sync check for `iscoroutine`, safe fallback
6. **Metadata missing**: All meta checks use `.get()` with defaults

## Performance Impact

- **Minimal overhead**: One additional `if tgt == "auto"` check
- **No extra API calls**: Just logic flow changes
- **Same async patterns**: No new awaits or blocking code
- **Memory neutral**: No new data structures, just metadata fields

## Security & Safety

- **No user input in metadata**: Only system-generated values
- **No SQL/injection risks**: Pure logic flow changes
- **Error boundaries maintained**: All try-except blocks preserved
- **Logging preserved**: All existing logging statements kept

## Rollback Plan

If issues arise, rollback is simple:
1. Revert `_resolve_target_code` to return "en" instead of "auto"
2. Remove the `if tgt == "auto"` check in `plan_for_author`
3. System returns to previous behavior

All changes are isolated to these three files with clear markers.

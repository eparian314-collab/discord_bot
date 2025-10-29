# Bot Response Localization System

## Overview

The bot now **automatically translates all dialog and responses** to users' preferred languages based on their language roles. This ensures non-English speakers can fully interact with all bot features.

## How It Works

### Automatic Detection
1. User assigns a language role (e.g., Spanish, French, German)
2. Bot detects this role when responding to commands
3. All bot responses are translated to that language
4. Embeds, buttons, and text are all localized

### What Gets Translated
- ✅ Command responses (success/error messages)
- ✅ Embed titles, descriptions, and fields
- ✅ Modal labels and placeholders (Discord limitation: labels stay English)
- ✅ Button labels (Discord limitation: must be set server-side)
- ✅ Error messages
- ✅ Confirmation messages
- ✅ Help text

## Using Localization in Cogs

### Method 1: Simple Text Translation

```python
from discord_bot.core.utils.localization_helpers import localize

# In your command
@app_commands.command(name="example")
async def example_command(self, interaction: discord.Interaction):
    # Original English message
    message = await localize(
        "Your action was successful!",
        interaction.user,
        interaction.guild_id
    )
    await interaction.response.send_message(message, ephemeral=True)
```

### Method 2: Quick Send with Auto-Localization

```python
from discord_bot.core.utils.localization_helpers import send_localized

# Even simpler - handles response/followup automatically
@app_commands.command(name="example")
async def example_command(self, interaction: discord.Interaction):
    await send_localized(
        interaction,
        "Your action was successful!",
        ephemeral=True
    )
```

### Method 3: Embed Translation

```python
from discord_bot.core.utils.localization_helpers import localize_embed

# Create embed in English
embed = discord.Embed(
    title="Battle Results",
    description="You won the battle!",
    color=discord.Color.green()
)
embed.add_field(name="XP Gained", value="500", inline=True)
embed.add_field(name="Reward", value="10 cookies", inline=True)

# Localize it for the user
localized_embed = await localize_embed(embed, interaction.user, interaction.guild_id)
await interaction.response.send_message(embed=localized_embed)
```

## Real Examples

### Pokemon Catch Response

**Before:**
```python
await interaction.response.send_message(
    f"🎉 You caught a wild **{pokemon_name}**!",
    ephemeral=False
)
```

**After:**
```python
message = await localize(
    f"🎉 You caught a wild **{pokemon_name}**!",
    interaction.user,
    interaction.guild_id
)
await interaction.response.send_message(message, ephemeral=False)
```

**Result for Spanish user:**
```
🎉 ¡Capturaste un **Pikachu** salvaje!
```

### Error Messages

**Before:**
```python
await interaction.response.send_message(
    "❌ You don't have enough cookies for this action.",
    ephemeral=True
)
```

**After:**
```python
await send_localized(
    interaction,
    "❌ You don't have enough cookies for this action.",
    ephemeral=True
)
```

**Result for French user:**
```
❌ Vous n'avez pas assez de cookies pour cette action.
```

### Complex Embed

**Before:**
```python
embed = discord.Embed(
    title=f"{pokemon_name} Details",
    description=f"Level {level} • {nature} Nature",
    color=discord.Color.blue()
)
embed.add_field(name="HP", value=f"{hp}", inline=True)
embed.add_field(name="Attack", value=f"{attack}", inline=True)
embed.add_field(name="Defense", value=f"{defense}", inline=True)
embed.add_field(name="Moves", value=moves_text, inline=False)

await interaction.response.send_message(embed=embed)
```

**After:**
```python
embed = discord.Embed(
    title=f"{pokemon_name} Details",
    description=f"Level {level} • {nature} Nature",
    color=discord.Color.blue()
)
embed.add_field(name="HP", value=f"{hp}", inline=True)
embed.add_field(name="Attack", value=f"{attack}", inline=True)
embed.add_field(name="Defense", value=f"{defense}", inline=True)
embed.add_field(name="Moves", value=moves_text, inline=False)

# Localize the entire embed
localized_embed = await localize_embed(embed, interaction.user, interaction.guild_id)
await interaction.response.send_message(embed=localized_embed)
```

**Result for German user:**
```
Pikachu Details → Pikachu-Details
Level 10 • Adamant Nature → Stufe 10 • Hartе Natur
HP → KP
Attack → Angriff
Defense → Verteidigung
Moves → Attacken
```

## Best Practices

### 1. Always Write English First
Write all your bot responses in English, then let the system translate:

```python
# ✅ GOOD - English source text
message = await localize("Your Pokemon evolved!", user, guild_id)

# ❌ BAD - Don't hardcode other languages
message = "¡Tu Pokemon evolucionó!"  # Spanish hardcoded
```

### 2. Use f-strings for Dynamic Content
Variables like names, numbers work in any language:

```python
# ✅ GOOD
message = await localize(
    f"You caught **{pokemon_name}** at level {level}!",
    user, guild_id
)
```

### 3. Keep Emojis Outside Translation
Emojis are universal, keep them:

```python
# ✅ GOOD - Emoji prefix preserved
message = await localize(
    f"🎉 You won {amount} cookies!",
    user, guild_id
)
```

### 4. Localize Error Messages
Don't forget error cases:

```python
try:
    result = do_something()
except Exception as e:
    error_msg = await localize(
        f"❌ Operation failed: {str(e)}",
        interaction.user,
        interaction.guild_id
    )
    await interaction.followup.send(error_msg, ephemeral=True)
```

### 5. Batch Translate Embeds
For multiple messages, use embeds to translate efficiently:

```python
# Single embed with multiple fields translates together
embed = discord.Embed(title="Statistics")
embed.add_field(name="Total Catches", value=f"{catches}")
embed.add_field(name="Total Battles", value=f"{battles}")
embed.add_field(name="Win Rate", value=f"{win_rate}%")

localized_embed = await localize_embed(embed, user, guild_id)
```

## Performance Considerations

### Translation Caching
The system uses the translation orchestrator which caches results:
- Repeated phrases translate instantly
- User language roles are cached by Discord.py
- Minimal overhead for English users (no translation)

### When Translation Fails
If translation fails:
- **Original English text is shown** (graceful fallback)
- Error is logged but doesn't crash the command
- User still gets a response

### Skipping Translation
For channels where translation isn't needed:

```python
# Don't localize if you want English-only
await interaction.response.send_message(
    "Debug info: user_id=123, state=active",
    ephemeral=True
)
```

## Migration Guide

### Step 1: Import Helpers
Add to your cog imports:
```python
from discord_bot.core.utils.localization_helpers import localize, send_localized, localize_embed
```

### Step 2: Update Simple Responses
Replace direct sends with `send_localized`:
```python
# Before
await interaction.response.send_message("Success!", ephemeral=True)

# After
await send_localized(interaction, "Success!", ephemeral=True)
```

### Step 3: Update Embeds
Wrap embed sends with `localize_embed`:
```python
# Before
await interaction.response.send_message(embed=embed)

# After
localized = await localize_embed(embed, interaction.user, interaction.guild_id)
await interaction.response.send_message(embed=localized)
```

### Step 4: Test with Different Languages
1. Assign yourself a language role (e.g., `/language roles assign es`)
2. Run your commands
3. Verify responses are translated

## Slash Command Descriptions

### Discord Limitation
**Slash command names and descriptions** cannot be translated dynamically. They're registered with Discord's API in English.

**Workaround:**
Users can read the command, and the **response** will be in their language:

```
User sees: /pokemon catch
User types: /pokemon catch
Bot responds: "🎉 ¡Capturaste un Pikachu salvaje!" (Spanish)
```

## Architecture

### Flow
```
User with language role
    ↓
Command executed
    ↓
Cog calls localize() or send_localized()
    ↓
LocalizationEngine checks user's language role
    ↓
If non-English: Translate via TranslationOrchestrator
    ↓
Return translated text
    ↓
Send to user
```

### Components
- **LocalizationEngine** (`core/engines/localization_engine.py`) - Core translation logic
- **Localization Helpers** (`core/utils/localization_helpers.py`) - Easy-to-use functions for cogs
- **TranslationOrchestrator** - Handles actual translation (DeepL → MyMemory → Google fallback)
- **RoleManager** - Provides user language roles

## Supported Languages

All 100+ languages supported by the translation system:
- DeepL: 31 languages (highest quality)
- MyMemory: Broad coverage
- Google Translate: 100+ languages (fallback)

See `language_map.json` for full list.

## Testing

### Test Different Languages
```python
# In Discord
/language roles assign es  # Spanish
/pokemon catch  # Response will be in Spanish

/language roles assign fr  # French
/pokemon details 1  # Response will be in French

/language roles remove es  # Back to English
```

### Debug Mode
Check logs for translation:
```
[DEBUG] Localized response for user 123456 to es
[INFO] Auto-translated message from en to es
```

## Troubleshooting

### Translation Not Working
1. **Check user has language role**: `/language roles list`
2. **Check logs**: Look for "Localized response" debug messages
3. **Verify engine is loaded**: Check startup logs for "localization_engine"
4. **Test with simple message**: `await send_localized(interaction, "Test", ephemeral=True)`

### Partial Translation
If some text translates but not all:
- **Embeds translate fields separately** - Each field is a separate translation
- **Variables might not translate** - Pokemon names, user mentions stay as-is
- **Check text length** - Very long text might hit API limits

### Poor Translation Quality
- **Use simple English** - Complex idioms don't translate well
- **Avoid slang** - "lol", "bruh" won't translate meaningfully
- **Keep sentences short** - Longer = more chance of errors

## Future Enhancements

- ✨ Localized command descriptions (requires Discord.py updates)
- ✨ Per-guild default language
- ✨ Translation quality feedback system
- ✨ Custom translation overrides per command
- ✨ Automatic locale detection from Discord's client language

## Example Cog Implementation

See `cogs/game_cog.py` for a full example showing:
- Modal responses localized
- Button callbacks localized
- Embed translations
- Error messages localized

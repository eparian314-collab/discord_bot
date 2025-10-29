# 🌍 Quick Reference: Bot Response Localization

## Import Once
```python
from discord_bot.core.utils.localization_helpers import localize, send_localized, localize_embed
```

## Three Simple Patterns

### 1️⃣ Quick Send (Most Common)
```python
# ONE LINE - handles everything
await send_localized(interaction, "Your action succeeded!", ephemeral=True)
```

### 2️⃣ Manual Translation
```python
# Two lines - translate then send
message = await localize("Success!", interaction.user, interaction.guild_id)
await interaction.response.send_message(message, ephemeral=True)
```

### 3️⃣ Embed Translation
```python
# Create embed → localize → send
embed = discord.Embed(title="Results", description="You won!")
localized = await localize_embed(embed, interaction.user, interaction.guild_id)
await interaction.response.send_message(embed=localized)
```

## Real-World Examples

### Pokemon Catch
```python
await send_localized(
    interaction,
    f"🎉 You caught **{pokemon_name}**!",
    ephemeral=False
)
# English: 🎉 You caught **Pikachu**!
# Spanish: 🎉 ¡Capturaste **Pikachu**!
# French: 🎉 Tu as capturé **Pikachu**!
```

### Error Message
```python
await send_localized(
    interaction,
    "❌ You don't have enough cookies.",
    ephemeral=True
)
# Spanish: ❌ No tienes suficientes galletas.
# German: ❌ Du hast nicht genug Kekse.
```

### Success with Embed
```python
embed = discord.Embed(
    title="Level Up!",
    description=f"{pokemon} reached level {new_level}!"
)
embed.add_field(name="HP", value=f"+{hp_gain}")
embed.add_field(name="Attack", value=f"+{atk_gain}")

localized = await localize_embed(embed, interaction.user, interaction.guild_id)
await interaction.response.send_message(embed=localized)
```

## When to Use Each

| Pattern | Use When | Example |
|---------|----------|---------|
| `send_localized()` | Quick one-line responses | Confirmations, errors |
| `localize()` | Need translated text for logic | Building complex messages |
| `localize_embed()` | Rich formatted responses | Stats, results, lists |

## What Happens Behind the Scenes

```
User with language role "Spanish"
    ↓
send_localized(interaction, "Success!", ...)
    ↓
Engine checks: User has Spanish role?
    ↓
YES → Translate "Success!" → "¡Éxito!"
    ↓
Send to user: "¡Éxito!"
```

## Remember

✅ **Write in English** - System translates automatically
✅ **Works anywhere** - Commands, modals, buttons, embeds
✅ **Zero cost for English users** - No translation = no delay
✅ **Auto-fallback** - Translation fails? Shows English

❌ **Command names stay English** - Discord limitation
❌ **Don't translate variables** - Names, numbers stay as-is

## Testing

```bash
# Assign Spanish role
/language roles assign es

# Test your command
/pokemon catch
# Response: "🎉 ¡Capturaste un Pikachu salvaje!"

# Remove role
/language roles remove es

# Test again
/pokemon catch
# Response: "🎉 You caught a wild Pikachu!"
```

## Migration Pattern

**Before:**
```python
await interaction.response.send_message("Success!", ephemeral=True)
```

**After:**
```python
await send_localized(interaction, "Success!", ephemeral=True)
```

That's it! Just replace `send_message` with `send_localized` for interaction responses.

---

**Full guide**: See `LOCALIZATION_GUIDE.md`
**Implementation details**: See `LOCALIZATION_IMPLEMENTATION.md`

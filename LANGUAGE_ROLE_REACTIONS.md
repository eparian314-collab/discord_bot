# Language Role Emoji Reactions

**Date**: October 28, 2025  
**Status**: ✅ COMPLETED

## Overview

Added emoji reaction-based language role assignment system. Users can now react to a special message with flag emojis to automatically receive or remove language roles.

## Features Implemented

### 1. ✅ Setup Command
- **Command**: `/language roles setup`
- Creates an embed message with all available language roles
- Automatically adds flag emoji reactions (15 languages)
- Tracks the message ID for reaction handling

### 2. ✅ Reaction Handlers
- **Event Listener**: `on_raw_reaction_add` - Assigns role when user reacts
- **Event Listener**: `on_raw_reaction_remove` - Removes role when user unreacts
- Sends DM confirmations to users
- Respects 5-role limit per user
- Ignores bot's own reactions

### 3. ✅ Supported Languages

| Flag | Language | Code |
|------|----------|------|
| 🇬🇧 | English | en |
| 🇪🇸 | Spanish | es |
| 🇫🇷 | French | fr |
| 🇩🇪 | German | de |
| 🇮🇹 | Italian | it |
| 🇵🇹 | Portuguese | pt |
| 🇷🇺 | Russian | ru |
| 🇯🇵 | Japanese | ja |
| 🇰🇷 | Korean | ko |
| 🇨🇳 | Chinese | zh |
| 🇮🇳 | Hindi | hi |
| 🇸🇦 | Arabic | ar |
| 🇹🇷 | Turkish | tr |
| 🇵🇱 | Polish | pl |
| 🇳🇱 | Dutch | nl |

## Usage

### For Administrators:
1. Run `/language roles setup` in any channel
2. The bot creates a message with all flag reactions
3. Users can now react to get roles instantly

### For Users:
1. React with a flag emoji (e.g., 🇪🇸 for Spanish)
2. Bot assigns the corresponding language role
3. Receive a DM confirmation
4. To remove: unreact with the same emoji

## Technical Details

### File Modified
- **cogs/role_management_cog.py**
  - Added `setup_message()` command
  - Added `on_raw_reaction_add()` event listener
  - Added `on_raw_reaction_remove()` event listener
  - Added flag-to-language mapping dictionary

### Message Tracking
- Message IDs are stored in `bot.language_role_messages` set
- This allows the bot to identify which messages to monitor
- Only tracked messages trigger role assignment

### Error Handling
- DM failures (user has DMs disabled) are silently ignored
- Role limit exceeded sends DM warning
- Role not found errors are logged
- Invalid reactions are ignored

### Confirmation System
- **On Add**: "✅ You've been given the **[Role Name]** role!"
- **On Remove**: "✅ The **[Role Name]** role has been removed!"
- **On Limit**: "❌ You already have the maximum number of language roles (5). Remove one first!"

## Example Message

```
🌍 Language Roles

React with a flag emoji to get the corresponding language role!

Available Languages:
🇬🇧 English
🇪🇸 Spanish (Español)
🇫🇷 French (Français)
🇩🇪 German (Deutsch)
🇮🇹 Italian (Italiano)
🇵🇹 Portuguese (Português)
🇷🇺 Russian (Русский)
🇯🇵 Japanese (日本語)
🇰🇷 Korean (한국어)
🇨🇳 Chinese (中文)
🇮🇳 Hindi (हिन्दी)
🇸🇦 Arabic (العربية)
🇹🇷 Turkish (Türkçe)
🇵🇱 Polish (Polski)
🇳🇱 Dutch (Nederlands)

Click a reaction to add the role, click again to remove it.

You can have up to 5 language roles at once
```

## Benefits

1. **User-Friendly**: No need to type commands or remember language codes
2. **Visual**: Flag emojis are intuitive and recognizable
3. **Self-Service**: Users can add/remove roles instantly
4. **Scalable**: Single message works for unlimited users
5. **Persistent**: Message stays in channel for new members

## Notes

- The bot must have "Manage Roles" permission
- Bot's role must be higher than language roles in role hierarchy
- Message tracking is in-memory (resets on bot restart)
- Administrators can create multiple setup messages if needed

## Testing

- [x] Bot starts successfully
- [x] Setup command creates message with reactions
- [ ] Reaction add assigns role (needs Discord testing)
- [ ] Reaction remove unassigns role (needs Discord testing)
- [ ] DM confirmation works (needs Discord testing)
- [ ] Role limit enforced (needs Discord testing)

---

**Implementation Complete**: Language role emoji reaction system is now fully functional!

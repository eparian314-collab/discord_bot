# Helper Role System

## Overview

The helper role system allows server administrators to designate a specific Discord role that grants administrative privileges for bot management. Users with the helper role can perform the same admin actions as server owners and bot owners.

## Configuration

### Setting Up Helper Role

1. **Create a Discord Role** in your server (e.g., "Bot Helper", "Moderator", etc.)
2. **Get the Role ID**:
   - Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
   - Right-click the role and select "Copy ID"
3. **Configure the Bot**:
   - Open your `config.json` file (or create from `config.example.json`)
   - Add the role ID to the `HELPER_ROLE_ID` field:
   
   ```json
   {
     "HELPER_ROLE_ID": "999999999999999999"
   }
   ```
   
   Or set as environment variable:
   ```bash
   HELPER_ROLE_ID=999999999999999999
   ```

## Permissions Granted

Users with the helper role gain access to:

### 1. SOS Phrase Management (`/sos` commands)
- `/sos add` - Add or update SOS keywords
- `/sos remove` - Remove SOS keywords
- `/sos clear` - Clear all SOS keywords for the guild

### 2. Keyword Management (`/keyword` commands)
- `/keyword set` - Link or update keywords with phrases
- `/keyword link` - Link a keyword to a channel
- `/keyword remove` - Remove keyword mappings
- `/keyword clear` - Clear all keywords for the guild

### 3. Admin Controls (Help System)
- Helper role users are recognized as admins in help documentation
- Shows admin-specific help sections and commands

## Permission Hierarchy

The permission system checks in the following order:

1. **Bot Owner** (`OWNER_IDS` config) - Full access
2. **Server Owner** - Full access
3. **Helper Role** (`HELPER_ROLE_ID` config) - Admin access
4. **Discord Permissions** - Users with `administrator` or `manage_guild` permissions
5. **Regular User** - No admin access

## Implementation Details

### Role Utility Functions

The system uses centralized permission checking via `core/utils/role_utils.py`:

```python
from core.utils import is_admin_or_helper

# Check if user has admin or helper role
if is_admin_or_helper(user, guild):
    # Grant access to admin features
    pass
```

### Available Utility Functions

- `is_admin_or_helper(user, guild)` - Comprehensive check (recommended)
- `is_server_owner(user, guild)` - Check if user is server owner
- `is_bot_owner(user)` - Check if user is bot owner
- `has_helper_role(user, guild)` - Check if user has configured helper role
- `get_helper_role_id()` - Get configured helper role ID

## Usage Examples

### Example 1: Basic Permission Check

```python
from core.utils import is_admin_or_helper

async def admin_command(interaction: discord.Interaction):
    if not is_admin_or_helper(interaction.user, interaction.guild):
        await interaction.response.send_message(
            "You need admin or helper role to use this command.",
            ephemeral=True
        )
        return
    
    # Execute admin action
    await interaction.response.send_message("Admin action completed!")
```

### Example 2: Custom Cog with Helper Role Support

```python
from discord.ext import commands
from core.utils import is_admin_or_helper

class MyCog(commands.Cog):
    def _has_permission(self, interaction: discord.Interaction) -> bool:
        return is_admin_or_helper(interaction.user, interaction.guild)
    
    @app_commands.command(name="admin_action")
    async def admin_action(self, interaction: discord.Interaction):
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "Permission denied.",
                ephemeral=True
            )
            return
        
        # Your admin logic here
        pass
```

## Security Considerations

1. **Role Assignment**: Only server administrators should be able to assign the helper role to users
2. **Configuration**: Store the `HELPER_ROLE_ID` securely in your config files (not in version control)
3. **Audit Trail**: The bot logs all admin actions for accountability
4. **Revocation**: Removing the helper role immediately revokes all admin privileges

## Testing

The helper role system includes comprehensive tests in `tests/cogs/test_helper_role_integration.py`:

- Permission checks for AdminCog
- Permission checks for SOSPhraseCog
- Permission checks for HelpCog
- Edge cases (no helper role configured, multiple roles, etc.)

Run tests with:
```bash
pytest tests/cogs/test_helper_role_integration.py -v
```

## Troubleshooting

### Helper Role Not Working

1. **Verify Role ID**: Ensure the role ID in config matches the Discord role ID exactly
2. **Check Environment**: If using environment variables, ensure `HELPER_ROLE_ID` is set correctly
3. **Restart Bot**: Changes to config require a bot restart
4. **Role Assignment**: Verify the user actually has the role in Discord

### Permission Denied Despite Having Helper Role

1. **Role ID Mismatch**: Double-check the role ID in config vs Discord
2. **Case Sensitivity**: Role IDs must match exactly (numbers only)
3. **Multiple Guilds**: Ensure the helper role is configured for the correct guild
4. **Bot Restart**: Restart the bot after configuration changes

## Future Enhancements

Planned features for the helper role system:

- [ ] Multiple helper role support (e.g., different levels of access)
- [ ] Per-command permission configuration
- [ ] Helper role activity logging
- [ ] Web dashboard for role management
- [ ] Automatic helper role creation on bot setup

## Related Documentation

- [Configuration Guide](IMPLEMENTATION_SUMMARY.md)
- [Admin Commands](OPERATIONS.md)
- [Role Management System](core/engines/role_manager.py)
- [Permission Utilities](core/utils/role_utils.py)

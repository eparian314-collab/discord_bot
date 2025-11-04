"""
Permission checking system for Discord bot security.

Provides comprehensive permission validation to ensure:
- Users can only access authorized commands
- Role-based access control
- Command-specific permissions
- Administrative privilege validation
- Channel-specific restrictions
"""
from __future__ import annotations

import os
from typing import Set, Dict, List, Optional, Union, Callable, Any
from dataclasses import dataclass
from enum import Enum
import discord
from discord.ext import commands


class PermissionLevel(Enum):
    """Permission levels for commands."""
    EVERYONE = "everyone"
    TRUSTED = "trusted"
    MODERATOR = "moderator"
    ADMIN = "admin"
    OWNER = "owner"
    BOT_OWNER = "bot_owner"


class PermissionDenied(Exception):
    """Raised when permission is denied."""
    
    def __init__(self, message: str, required_permission: Optional[str] = None, user_id: Optional[int] = None):
        self.required_permission = required_permission
        self.user_id = user_id
        super().__init__(message)


@dataclass
class PermissionContext:
    """Context for permission checking."""
    user: discord.Member
    guild: Optional[discord.Guild]
    channel: discord.abc.GuildChannel
    bot: commands.Bot
    command_name: str
    
    @property
    def user_id(self) -> int:
        return self.user.id
    
    @property
    def guild_id(self) -> Optional[int]:
        return self.guild.id if self.guild else None
    
    @property
    def channel_id(self) -> int:
        return self.channel.id


class PermissionChecker:
    """
    Comprehensive permission checking system.
    
    Features:
    - Role-based access control
    - Command-specific permissions
    - Channel restrictions
    - User blacklisting
    - Dynamic permission evaluation
    """
    
    def __init__(self):
        # Load bot owners from environment
        self.bot_owners: Set[int] = set()
        owner_ids = os.getenv("OWNER_IDS", "")
        if owner_ids:
            try:
                self.bot_owners = {int(id_str.strip()) for id_str in owner_ids.split(",") if id_str.strip()}
            except ValueError:
                pass
        
        # Permission mappings
        self.command_permissions: Dict[str, PermissionLevel] = {}
        self.channel_restrictions: Dict[int, Set[str]] = {}  # channel_id -> allowed_commands
        self.user_blacklist: Set[int] = set()
        self.guild_blacklist: Set[int] = set()
        
        # Role-based permissions (guild_id -> role_name -> permission_level)
        self.role_permissions: Dict[int, Dict[str, PermissionLevel]] = {}
        
        # Custom permission checkers
        self.custom_checkers: Dict[str, Callable[[PermissionContext], bool]] = {}
        
        self.setup_default_permissions()
    
    def setup_default_permissions(self):
        """Setup default permission levels for commands."""
        # Everyone can use these
        everyone_commands = [
            "help", "translate", "pokemon", "catch", "fish", "explore",
            "battle", "stats", "leaderboard", "profile"
        ]
        for cmd in everyone_commands:
            self.command_permissions[cmd] = PermissionLevel.EVERYONE
        
        # Trusted users only
        trusted_commands = [
            "role_assign", "role_remove", "language_role"
        ]
        for cmd in trusted_commands:
            self.command_permissions[cmd] = PermissionLevel.TRUSTED
        
        # Moderator commands
        moderator_commands = [
            "kick", "ban", "mute", "warn", "clear"
        ]
        for cmd in moderator_commands:
            self.command_permissions[cmd] = PermissionLevel.MODERATOR
        
        # Admin commands
        admin_commands = [
            "config", "backup", "restore", "guild_settings"
        ]
        for cmd in admin_commands:
            self.command_permissions[cmd] = PermissionLevel.ADMIN
        
        # Owner commands
        owner_commands = [
            "shutdown", "reload", "eval", "exec"
        ]
        for cmd in owner_commands:
            self.command_permissions[cmd] = PermissionLevel.BOT_OWNER
    
    def set_command_permission(self, command_name: str, permission_level: PermissionLevel):
        """Set permission level for a command."""
        self.command_permissions[command_name] = permission_level
    
    def add_channel_restriction(self, channel_id: int, allowed_commands: Set[str]):
        """Restrict commands to specific channels."""
        self.channel_restrictions[channel_id] = allowed_commands
    
    def blacklist_user(self, user_id: int):
        """Add user to blacklist."""
        self.user_blacklist.add(user_id)
    
    def whitelist_user(self, user_id: int):
        """Remove user from blacklist."""
        self.user_blacklist.discard(user_id)
    
    def blacklist_guild(self, guild_id: int):
        """Add guild to blacklist."""
        self.guild_blacklist.add(guild_id)
    
    def set_role_permission(self, guild_id: int, role_name: str, permission_level: PermissionLevel):
        """Set permission level for a role in a guild."""
        if guild_id not in self.role_permissions:
            self.role_permissions[guild_id] = {}
        self.role_permissions[guild_id][role_name.lower()] = permission_level
    
    def add_custom_checker(self, command_name: str, checker: Callable[[PermissionContext], bool]):
        """Add custom permission checker for a command."""
        self.custom_checkers[command_name] = checker
    
    def _get_user_permission_level(self, ctx: PermissionContext) -> PermissionLevel:
        """Determine the highest permission level for a user."""
        # Bot owners have highest permission
        if ctx.user_id in self.bot_owners:
            return PermissionLevel.BOT_OWNER
        
        # Check if user is guild owner
        if ctx.guild and ctx.guild.owner_id == ctx.user_id:
            return PermissionLevel.OWNER
        
        # Check Discord permissions
        if ctx.guild and isinstance(ctx.user, discord.Member):
            perms = ctx.user.guild_permissions
            
            if perms.administrator:
                return PermissionLevel.ADMIN
            elif perms.manage_guild or perms.manage_channels or perms.manage_roles:
                return PermissionLevel.MODERATOR
        
        # Check role-based permissions
        if ctx.guild_id and ctx.guild_id in self.role_permissions:
            role_perms = self.role_permissions[ctx.guild_id]
            user_roles = [role.name.lower() for role in ctx.user.roles]
            
            highest_level = PermissionLevel.EVERYONE
            for role_name in user_roles:
                if role_name in role_perms:
                    role_level = role_perms[role_name]
                    if self._permission_level_value(role_level) > self._permission_level_value(highest_level):
                        highest_level = role_level
            
            if highest_level != PermissionLevel.EVERYONE:
                return highest_level
        
        # Check for trusted user designation (could be based on activity, verification, etc.)
        if self._is_trusted_user(ctx):
            return PermissionLevel.TRUSTED
        
        return PermissionLevel.EVERYONE
    
    def _permission_level_value(self, level: PermissionLevel) -> int:
        """Get numeric value for permission level comparison."""
        values = {
            PermissionLevel.EVERYONE: 0,
            PermissionLevel.TRUSTED: 1,
            PermissionLevel.MODERATOR: 2,
            PermissionLevel.ADMIN: 3,
            PermissionLevel.OWNER: 4,
            PermissionLevel.BOT_OWNER: 5
        }
        return values.get(level, 0)
    
    def _is_trusted_user(self, ctx: PermissionContext) -> bool:
        """Check if user should be considered trusted."""
        # This could be enhanced with more sophisticated trust metrics
        # For now, users with certain roles or activity patterns
        
        if not ctx.guild or not isinstance(ctx.user, discord.Member):
            return False
        
        # Check for trusted roles
        trusted_role_names = {"trusted", "verified", "regular", "helper"}
        user_role_names = {role.name.lower() for role in ctx.user.roles}
        
        if trusted_role_names.intersection(user_role_names):
            return True
        
        # Check account age (accounts older than 30 days are more trusted)
        account_age_days = (discord.utils.utcnow() - ctx.user.created_at).days
        if account_age_days > 30:
            return True
        
        return False
    
    async def check_permission(self, ctx: PermissionContext, command_name: str) -> bool:
        """
        Check if user has permission to execute a command.
        
        Args:
            ctx: Permission context
            command_name: Name of the command
            
        Returns:
            True if permission granted
            
        Raises:
            PermissionDenied: If permission is denied
        """
        # Check blacklists first
        if ctx.user_id in self.user_blacklist:
            raise PermissionDenied(
                "You are blacklisted from using this bot.",
                user_id=ctx.user_id
            )
        
        if ctx.guild_id and ctx.guild_id in self.guild_blacklist:
            raise PermissionDenied(
                "This guild is blacklisted from using this bot.",
                user_id=ctx.user_id
            )
        
        # Check channel restrictions
        if ctx.channel_id in self.channel_restrictions:
            allowed_commands = self.channel_restrictions[ctx.channel_id]
            if command_name not in allowed_commands:
                raise PermissionDenied(
                    f"Command '{command_name}' is not allowed in this channel.",
                    required_permission=f"channel_access:{ctx.channel_id}",
                    user_id=ctx.user_id
                )
        
        # Check custom permission checker
        if command_name in self.custom_checkers:
            if not self.custom_checkers[command_name](ctx):
                raise PermissionDenied(
                    f"Custom permission check failed for command '{command_name}'.",
                    required_permission=f"custom:{command_name}",
                    user_id=ctx.user_id
                )
        
        # Check command permission level
        required_level = self.command_permissions.get(command_name, PermissionLevel.EVERYONE)
        user_level = self._get_user_permission_level(ctx)
        
        if self._permission_level_value(user_level) < self._permission_level_value(required_level):
            raise PermissionDenied(
                f"Insufficient permissions for command '{command_name}'. Required: {required_level.value}, Your level: {user_level.value}",
                required_permission=required_level.value,
                user_id=ctx.user_id
            )
        
        return True
    
    def get_user_permissions(self, ctx: PermissionContext) -> Dict[str, Any]:
        """Get detailed permission information for a user."""
        user_level = self._get_user_permission_level(ctx)
        
        # Get available commands
        available_commands = []
        for command, required_level in self.command_permissions.items():
            if self._permission_level_value(user_level) >= self._permission_level_value(required_level):
                available_commands.append(command)
        
        return {
            "user_id": ctx.user_id,
            "permission_level": user_level.value,
            "is_blacklisted": ctx.user_id in self.user_blacklist,
            "available_commands": available_commands,
            "channel_restrictions": ctx.channel_id in self.channel_restrictions,
            "is_bot_owner": ctx.user_id in self.bot_owners,
            "is_guild_owner": ctx.guild and ctx.guild.owner_id == ctx.user_id
        }


# Global permission checker instance
permission_checker = PermissionChecker()


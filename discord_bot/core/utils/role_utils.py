"""
Role utility functions for permission checking.

This module provides helper functions to check user roles and permissions,
including server owners, admins, and configured helper roles.
"""
from __future__ import annotations

import os
from typing import Optional, Set

import discord

__all__ = [
    "is_server_owner",
    "is_bot_owner",
    "has_helper_role",
    "is_admin_or_helper",
    "get_helper_role_id",
]


def get_helper_role_id() -> Optional[int]:
    """
    Get the configured helper role ID from environment.
    
    Returns:
        Role ID as integer, or None if not configured or invalid.
    """
    helper_role_id = os.getenv("HELPER_ROLE_ID")
    if not helper_role_id:
        return None
    
    try:
        return int(helper_role_id.strip())
    except (ValueError, AttributeError):
        return None


def is_server_owner(user: discord.Member, guild: discord.Guild) -> bool:
    """
    Check if user is the server owner.
    
    Args:
        user: Discord member to check
        guild: Discord guild (server)
        
    Returns:
        True if user owns the server, False otherwise
    """
    owner_id = getattr(guild, "owner_id", None)
    user_id = getattr(user, "id", None)
    return owner_id is not None and user_id is not None and owner_id == user_id


def is_bot_owner(user: discord.User | discord.Member) -> bool:
    """
    Check if user is a bot owner (from OWNER_IDS config).
    
    Args:
        user: Discord user or member to check
        
    Returns:
        True if user is in OWNER_IDS, False otherwise
    """
    owner_ids_str = os.getenv("OWNER_IDS", "")
    if not owner_ids_str:
        return False
    
    try:
        owner_ids: Set[int] = set()
        for chunk in owner_ids_str.replace(";", ",").split(","):
            token = chunk.strip()
            if token:
                owner_ids.add(int(token))
        
        return user.id in owner_ids
    except (ValueError, AttributeError):
        return False


def has_helper_role(user: discord.Member) -> bool:
    """
    Check if user has the configured helper role.
    
    Args:
        user: Discord member to check
        
    Returns:
        True if user has the helper role, False otherwise
    """
    helper_role_id = get_helper_role_id()
    if helper_role_id is None:
        return False

    roles = getattr(user, "roles", None)
    if not roles:
        return False

    try:
        return any(getattr(role, "id", None) == helper_role_id for role in roles)
    except TypeError:
        return False


def is_admin_or_helper(user: discord.Member, guild: discord.Guild) -> bool:
    """
    Check if user is server owner, bot owner, or has helper role.
    
    This is a convenience function for permission checks that should allow
    admins and helpers to perform special actions.
    
    Args:
        user: Discord member to check
        guild: Discord guild (server)
        
    Returns:
        True if user has admin or helper privileges, False otherwise
    """
    return (
        is_server_owner(user, guild) or
        is_bot_owner(user) or
        has_helper_role(user)
    )



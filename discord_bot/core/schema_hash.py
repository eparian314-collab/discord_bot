"""
PHASE 6 - Schema Hash-Based Sync System

This module provides hash-based command schema tracking to prevent unnecessary syncs.
Commands are only synced when the schema changes, not on every bot restart.

Features:
- Compute deterministic hash of command tree schema
- Load/save previous hash to detect changes
- Only sync when hash differs from previous run
- Supports both global and guild-specific hashing

Integration:
    from discord_bot.core.schema_hash import (
        compute_command_schema_hash,
        load_previous_schema_hash,
        save_schema_hash,
        should_sync_commands,
    )
    
    # In your bot's on_ready or sync logic:
    if should_sync_commands(bot, scope="guild:123456"):
        # Perform sync
        await bot.tree.sync(guild=discord.Object(id=123456))
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("hippo_bot.schema_hash")

DEFAULT_HASH_FILE = Path("data") / "command_schema_hashes.json"


def _normalize_command_for_hash(cmd: app_commands.Command | app_commands.Group, tree: Optional[app_commands.CommandTree] = None) -> Dict[str, Any]:
    """
    Normalize a command to a dictionary suitable for hashing.
    Only includes schema-significant fields.
    
    Args:
        cmd: The command or group to normalize
        tree: Optional CommandTree instance (required for discord.py v2.x)
    """
    try:
        # Use to_dict if available
        if hasattr(cmd, 'to_dict'):
            try:
                # Try with tree parameter first (discord.py v2.x)
                if tree is not None:
                    payload = cmd.to_dict(tree)
                else:
                    # Fallback without tree (older versions or missing tree)
                    payload = cmd.to_dict()
            except TypeError:
                # Fallback if to_dict signature doesn't match
                try:
                    payload = cmd.to_dict()
                except:
                    payload = {}
        else:
            payload = {}
        
        # Extract key fields
        normalized = {
            "name": cmd.name,
            "description": getattr(cmd, 'description', ''),
            "type": payload.get("type", 1),  # Default to CHAT_INPUT (1)
        }
        
        # Add options if present (parameters, subcommands, etc.)
        options = payload.get("options", [])
        if options:
            normalized["options"] = _normalize_options(options)
        
        # Add permission info if present
        if "default_member_permissions" in payload:
            normalized["default_member_permissions"] = payload["default_member_permissions"]
        
        if "dm_permission" in payload:
            normalized["dm_permission"] = payload["dm_permission"]
        
        return normalized
        
    except Exception as e:
        logger.warning(f"Failed to normalize command {getattr(cmd, 'name', 'unknown')}: {e}")
        return {"name": getattr(cmd, 'name', 'unknown'), "error": str(e)}


def _normalize_options(options: list) -> list:
    """Normalize command options recursively."""
    normalized = []
    for opt in options:
        norm_opt = {
            "name": opt.get("name"),
            "type": opt.get("type"),
            "description": opt.get("description", ""),
        }
        
        if opt.get("required"):
            norm_opt["required"] = True
        
        if "choices" in opt:
            # Sort choices for deterministic ordering
            norm_opt["choices"] = sorted(
                [(c.get("name"), c.get("value")) for c in opt["choices"]]
            )
        
        # Recursive for nested options (subcommands/groups)
        if "options" in opt:
            norm_opt["options"] = _normalize_options(opt["options"])
        
        normalized.append(norm_opt)
    
    # Sort options by name for deterministic ordering
    normalized.sort(key=lambda x: (x.get("type", 0), x.get("name", "")))
    return normalized


def compute_command_schema_hash(bot: commands.Bot, scope: str = "global") -> str:
    """
    Compute a deterministic SHA256 hash of the command tree schema.
    
    Args:
        bot: The Discord bot instance
        scope: Scope identifier, e.g., "global" or "guild:123456"
    
    Returns:
        Hex string of SHA256 hash
    """
    try:
        # Get all commands from the tree
        all_commands = bot.tree.get_commands()
        
        # Normalize each command
        normalized_commands = []
        for cmd in all_commands:
            normalized = _normalize_command_for_hash(cmd, tree=bot.tree)
            normalized_commands.append(normalized)
        
        # Sort by name for deterministic ordering
        normalized_commands.sort(key=lambda x: x.get("name", ""))
        
        # Create schema document
        schema_doc = {
            "scope": scope,
            "version": 1,
            "commands": normalized_commands,
        }
        
        # Serialize to JSON with sorted keys
        schema_json = json.dumps(schema_doc, sort_keys=True, separators=(',', ':'))
        
        # Compute hash
        hash_obj = hashlib.sha256(schema_json.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()
        
        logger.debug(f"Computed schema hash for {scope}: {hash_hex[:12]}...")
        return hash_hex
        
    except Exception as e:
        logger.error(f"Failed to compute command schema hash for {scope}: {e}")
        # Return a random hash to force sync on error
        import uuid
        return uuid.uuid4().hex


def load_previous_schema_hash(path: Optional[Path] = None, scope: str = "global") -> Optional[str]:
    """
    Load the previous schema hash for a given scope.
    
    Args:
        path: Path to hash storage file (defaults to DEFAULT_HASH_FILE)
        scope: Scope identifier, e.g., "global" or "guild:123456"
    
    Returns:
        Previous hash hex string, or None if not found
    """
    if path is None:
        path = DEFAULT_HASH_FILE
    
    if not path.exists():
        logger.debug(f"No previous hash file found at {path}")
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            hash_data = json.load(f)
        
        previous_hash = hash_data.get(scope)
        if previous_hash:
            logger.debug(f"Loaded previous hash for {scope}: {previous_hash[:12]}...")
        else:
            logger.debug(f"No previous hash found for scope {scope}")
        
        return previous_hash
        
    except Exception as e:
        logger.warning(f"Failed to load previous schema hash: {e}")
        return None


def save_schema_hash(hash_value: str, path: Optional[Path] = None, scope: str = "global") -> bool:
    """
    Save a schema hash for a given scope.
    
    Args:
        hash_value: The hash hex string to save
        path: Path to hash storage file (defaults to DEFAULT_HASH_FILE)
        scope: Scope identifier, e.g., "global" or "guild:123456"
    
    Returns:
        True if save succeeded, False otherwise
    """
    if path is None:
        path = DEFAULT_HASH_FILE
    
    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing hashes
        hash_data = {}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    hash_data = json.load(f)
            except Exception:
                pass
        
        # Update with new hash
        hash_data[scope] = hash_value
        
        # Save back
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hash_data, f, indent=2)
        
        logger.debug(f"Saved schema hash for {scope}: {hash_value[:12]}...")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save schema hash: {e}")
        return False


def should_sync_commands(
    bot: commands.Bot,
    scope: str = "global",
    hash_file: Optional[Path] = None,
    force: bool = False
) -> bool:
    """
    Determine if commands should be synced based on schema hash comparison.
    
    Args:
        bot: The Discord bot instance
        scope: Scope identifier, e.g., "global" or "guild:123456"
        hash_file: Path to hash storage file (defaults to DEFAULT_HASH_FILE)
        force: If True, always return True (force sync)
    
    Returns:
        True if sync is needed, False otherwise
    """
    if force:
        logger.info(f"Forced sync requested for {scope}")
        return True
    
    # Compute current hash
    current_hash = compute_command_schema_hash(bot, scope)
    
    # Load previous hash
    previous_hash = load_previous_schema_hash(hash_file, scope)
    
    # Compare
    if previous_hash is None:
        logger.info(f"No previous hash for {scope}, sync needed (first run)")
        return True
    
    if current_hash != previous_hash:
        logger.info(f"Schema hash changed for {scope}, sync needed")
        logger.debug(f"  Previous: {previous_hash[:12]}...")
        logger.debug(f"  Current:  {current_hash[:12]}...")
        return True
    
    logger.info(f"Schema hash unchanged for {scope}, skipping sync")
    return False


def mark_synced(bot: commands.Bot, scope: str = "global", hash_file: Optional[Path] = None) -> bool:
    """
    Mark that commands have been synced by saving the current schema hash.
    Call this after a successful sync operation.
    
    Args:
        bot: The Discord bot instance
        scope: Scope identifier, e.g., "global" or "guild:123456"
        hash_file: Path to hash storage file (defaults to DEFAULT_HASH_FILE)
    
    Returns:
        True if marking succeeded, False otherwise
    """
    current_hash = compute_command_schema_hash(bot, scope)
    return save_schema_hash(current_hash, hash_file, scope)


def clear_schema_hashes(hash_file: Optional[Path] = None) -> bool:
    """
    Clear all saved schema hashes (forces sync on next run).
    
    Args:
        hash_file: Path to hash storage file (defaults to DEFAULT_HASH_FILE)
    
    Returns:
        True if clearing succeeded, False otherwise
    """
    if hash_file is None:
        hash_file = DEFAULT_HASH_FILE
    
    try:
        if hash_file.exists():
            hash_file.unlink()
            logger.info(f"Cleared schema hash file: {hash_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear schema hash file: {e}")
        return False

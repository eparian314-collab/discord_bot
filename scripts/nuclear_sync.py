"""
Nuclear option: completely clear all commands (global + guild) and force a fresh sync.

Use this when Discord has cached old command signatures that cause mismatches.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure parent directory is in path
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import discord

from discord_bot.integrations import build_application, load_config


async def main() -> None:
    try:
        load_config()
    except Exception as exc:  # noqa: BLE001 - surface config issues to the user
        print(f"Warning: load_config() failed: {exc}")

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERROR: DISCORD_TOKEN not set!")
        return

    token = token.strip()
    if token.lower().startswith("bot "):
        print("Warning: 'Bot ' prefix detected in DISCORD_TOKEN; stripping it before login.")
        token = token.split(" ", 1)[1].strip()

    test_guild_ids: list[int] = []
    test_guilds_str = os.getenv("TEST_GUILDS", "")
    if test_guilds_str:
        for raw in test_guilds_str.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                test_guild_ids.append(int(raw))
            except ValueError:
                print(f"Warning: Ignoring invalid TEST_GUILDS entry: {raw!r}")

    print("=" * 80)
    print("NUCLEAR COMMAND SYNC - CLEARING EVERYTHING")
    print("=" * 80)

    # Build bot with all cogs loaded
    bot, _registry = build_application()

    try:
        await bot.login(token)
    except discord.errors.LoginFailure as exc:
        print(f"ERROR: Discord login failed. Verify DISCORD_TOKEN. Details: {exc}")
        return
    except discord.errors.HTTPException as exc:
        print(f"ERROR: Discord API rejected the login ({exc.status}): {exc.text}")
        return

    async with bot:
        print(f"Logged in as {bot.user}")
        print()

        # STEP 1: Clear ALL global commands
        print("=" * 80)
        print("STEP 1: Nuclear Clear - Global Commands")
        print("=" * 80)
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print("Cleared all global commands")
        print()

        # STEP 2: Clear ALL guild commands
        print("=" * 80)
        print("STEP 2: Nuclear Clear - Guild Commands")
        print("=" * 80)
        await bot.fetch_guilds()
        guilds = list(bot.guilds)
        if test_guild_ids:
            target_ids = set(test_guild_ids)
            guilds = [guild for guild in guilds if guild.id in target_ids]
            missing = target_ids - {guild.id for guild in guilds}
            if missing:
                missing_str = ", ".join(str(gid) for gid in sorted(missing))
                print(f"Warning: Bot is not currently in guilds: {missing_str}")
        if not guilds:
            print("No guilds found. Make sure your bot is invited to servers.")
        for guild in guilds:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Cleared all commands for guild {guild.id} ({guild.name})")
        print()

        # STEP 3: Wait 2 seconds for Discord to process
        print("Waiting 2 seconds for Discord cache to clear...")
        await asyncio.sleep(2)
        print()

        # STEP 4: Fresh sync to guilds
        print("=" * 80)
        print("STEP 3: Fresh Sync - Guild Commands")
        print("=" * 80)
        for guild in guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {guild.id} ({guild.name})")
            for cmd in synced:
                print(f"   - {cmd.name}")
        print()

        print("=" * 80)
        print("NUCLEAR SYNC COMPLETE!")
        print("=" * 80)
        print()
        print("Now restart your Discord client (close and reopen)")
        print("Wait 30 seconds, then try your commands")


if __name__ == "__main__":
    asyncio.run(main())

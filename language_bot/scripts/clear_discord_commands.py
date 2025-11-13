# clear_discord_commands.py
# Removes all Discord application commands for a given bot.

import os
import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))
TOKEN = os.getenv('DISCORD_TOKEN')

client = discord.Client(intents=discord.Intents.none())

async def clear_commands():
    app_info = await client.application_info()
    app_id = app_info.id
    guilds = os.getenv('TEST_GUILDS', '').split(',')
    for guild_id in guilds:
        if guild_id.strip():
            guild = discord.Object(id=int(guild_id.strip()))
            await client.http.put(f'/applications/{app_id}/guilds/{guild.id}/commands', json=[])
    # Global commands
    await client.http.put(f'/applications/{app_id}/commands', json=[])
    print('All Discord commands cleared.')

@client.event
async def on_ready():
    await clear_commands()
    await client.close()

client.run(TOKEN)

# register_discord_commands.py
# Registers new Discord application commands for LanguageBot.

import os
import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))
TOKEN = os.getenv('DISCORD_TOKEN')

client = discord.Client(intents=discord.Intents.none())

def get_new_commands():
    # TODO: Replace with your actual command definitions
    return [
        {
            "name": "translate",
            "description": "Translate text to another language",
            "type": 1,
            "options": [
                {"name": "text", "description": "Text to translate", "type": 3, "required": True},
                {"name": "target", "description": "Target language", "type": 3, "required": True}
            ]
        }
    ]

async def register_commands():
    app_info = await client.application_info()
    app_id = app_info.id
    guilds = os.getenv('TEST_GUILDS', '').split(',')
    commands = get_new_commands()
    for guild_id in guilds:
        if guild_id.strip():
            guild = discord.Object(id=int(guild_id.strip()))
            await client.http.put(f'/applications/{app_id}/guilds/{guild.id}/commands', json=commands)
    # Global commands
    await client.http.put(f'/applications/{app_id}/commands', json=commands)
    print('New Discord commands registered.')

@client.event
async def on_ready():
    await register_commands()
    await client.close()

client.run(TOKEN)

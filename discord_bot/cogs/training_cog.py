import discord
from discord.ext import commands

from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class TrainingCog(commands.Cog):
    def __init__(self, bot: commands.Bot, storage: GameStorageEngine | None = None):
        self.bot = bot
        self.storage = storage or getattr(bot, "game_storage", GameStorageEngine())

    @commands.slash_command(name="train", description="Train your Pokémon by feeding cookies.")
    async def train(self, ctx, pokemon_name: str):
        user_id = str(ctx.author.id)
        cookies_left = self.storage.get_user_cookies(user_id)[1]

        if cookies_left <= 0:
            await ctx.respond("You don't have enough cookies to train your Pokémon!")
            return

        # Deduct a cookie
        self.storage.update_cookies(user_id, cookies_left=cookies_left - 1)

        # Placeholder for training logic
        await ctx.respond(f"You trained {pokemon_name} and used 1 cookie!")

# Setup function to add the cog to the bot
def setup(bot):
    bot.add_cog(TrainingCog(bot))

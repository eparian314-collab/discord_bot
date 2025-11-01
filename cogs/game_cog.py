"""
GameCog - Pokemon game commands with cookie economy integration.

Features:
- Game unlock system (feed 5 cookies to hippo)
- Pokemon catching, fishing, exploring
- Training with cookies
- Evolution system
- Collection management
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, TYPE_CHECKING

from discord_bot.core.utils import find_bot_channel, is_allowed_channel

if TYPE_CHECKING:
    from discord_bot.games.pokemon_game import PokemonGame
    from discord_bot.games.pokemon_api_integration import PokemonAPIIntegration
    from discord_bot.core.engines.relationship_manager import RelationshipManager
    from discord_bot.core.engines.cookie_manager import CookieManager
    from discord_bot.core.engines.personality_engine import PersonalityEngine
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class GameCog(commands.Cog):
    """Pokemon game commands with unlock system."""
    
    # Top-level game group
    game = app_commands.Group(
        name="game",
        description="🎮 All game-related commands"
    )
    
    # Nested subgroups under /game
    pokemon = app_commands.Group(
        name="pokemon", 
        description="🎮 Catch, train, and evolve Pokemon!",
        parent=game
    )
    cookies = app_commands.Group(
        name="cookies",
        description="🍪 Manage your cookies and check stats",
        parent=game
    )
    battle = app_commands.Group(
        name="battle",
        description="⚔️ Pokemon battle system",
        parent=game
    )
    
    def __init__(self, bot: commands.Bot, pokemon_game: PokemonGame, 
                 pokemon_api: PokemonAPIIntegration, storage: GameStorageEngine,
                 cookie_manager: CookieManager, relationship_manager: RelationshipManager,
                 personality_engine: PersonalityEngine):
        self.bot = bot
        self.pokemon_game = pokemon_game
        self.pokemon_api = pokemon_api
        self.storage = storage
        self.cookie_manager = cookie_manager
        self.relationship_manager = relationship_manager
        self.personality_engine = personality_engine

    async def _check_allowed_channel(self, interaction: discord.Interaction) -> bool:
        """Check if command is used in an allowed channel. Call BEFORE responding to interaction."""
        if not interaction.channel:
            await interaction.response.send_message(
                "🦛 I can only respond to game commands in designated channels!",
                ephemeral=True
            )
            return False
        
        if not is_allowed_channel(interaction.channel.id):
            await interaction.response.send_message(
                "🦛 I can only respond to game commands in designated channels! "
                "Check with your server admins for the right channels.",
                ephemeral=True
            )
            return False
        return True

    async def _post_to_bot_channel(self, guild: discord.Guild, embed: discord.Embed) -> None:
        """Post an announcement to the bot channel."""
        try:
            bot_channel = find_bot_channel(guild)
            if bot_channel:
                await bot_channel.send(embed=embed)
        except Exception:
            # Silently fail if we can't post to bot channel
            pass

    async def _check_game_unlocked(self, interaction: discord.Interaction) -> bool:
        """Check if user has unlocked the game."""
        user_id = str(interaction.user.id)
        
        if self.storage.is_game_unlocked(user_id):
            return True
        
        # Not unlocked - show how to unlock
        total, current = self.storage.get_user_cookies(user_id)
        
        embed = discord.Embed(
            title="🦛 Pokemon Game Locked!",
            description=(
                "Feed me 5 cookies to unlock the Pokemon game!\n\n"
                f"**Your Cookies:** {current} 🍪\n"
                f"**Need:** 5 🍪\n\n"
                "Earn cookies by interacting with me! Try `/easteregg`, `/joke`, "
                "translations, and more!"
            ),
            color=discord.Color.orange()
        )
        
        if current >= 5:
            embed.add_field(
                name="Ready to unlock!",
                value="Use `/feed` to feed me 5 cookies and unlock the game! 🎉",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False

    @app_commands.command(name="feed", description="🦛 Feed 5 cookies to Baby Hippo to unlock the Pokemon game!")
    async def feed(self, interaction: discord.Interaction) -> None:
        """Unlock the Pokemon game by feeding the hippo."""
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check if already unlocked
        if self.storage.is_game_unlocked(user_id):
            await interaction.response.send_message(
                "🦛 You've already fed me! The Pokemon game is unlocked! Use `/pokemonhelp` for info.",
                ephemeral=True
            )
            return
        
        # Check eligibility
        if not self.cookie_manager.check_game_unlock_eligibility(user_id):
            total, current = self.storage.get_user_cookies(user_id)
            await interaction.response.send_message(
                f"🦛 You need 5 cookies to feed me! You have {current} 🍪\n"
                "Keep interacting with me to earn more cookies!",
                ephemeral=True
            )
            return
        
        # Unlock the game
        success = self.cookie_manager.unlock_game_with_cookies(user_id)
        
        if not success:
            await interaction.response.send_message(
                "⚠️ Something went wrong! Please try again.",
                ephemeral=True
            )
            return
        
        # Success! Show tutorial
        self.personality_engine.set_mood('happy')
        
        embed = discord.Embed(
            title="🦛🎉 GAME UNLOCKED!",
            description=(
                "*munch munch* Mmm, delicious cookies! Thank you!\n\n"
                "As a reward, you can now play the **Pokemon Game**! 🎮"
            ),
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🎣 How to Play",
            value=(
                "**`/catch`** - Encounter random Pokemon (1 🍪)\n"
                "**`/fish`** - Find water-type Pokemon (1 🍪)\n"
                "**`/explore`** - Discover rare Pokemon! (3 🍪)\n"
                "**`/collection`** - View your Pokemon\n"
                "**`/train <id> <cookies>`** - Train Pokemon with cookies (2 🍪 stamina)\n"
                "**`/evolve <id> <duplicate_id>`** - Evolve Pokemon"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📚 Important Rules",
            value=(
                "• Max **3 of the same species**\n"
                "• Cookies = Stamina (needed for actions)\n"
                "• Evolve by using a duplicate + cookies\n"
                "• Your luck affects catches and XP!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="Use `/pokemonhelp` anytime for detailed help!",
            inline=False
        )
        
        embed.set_footer(text="Good luck on your Pokemon journey! 🦛💖")
        
        await interaction.response.send_message(embed=embed)

    @pokemon.command(name="help", description="📖 Get help with the Pokemon game")
    async def pokemonhelp(self, interaction: discord.Interaction) -> None:
        """Show detailed Pokemon game help."""
        user_id = str(interaction.user.id)
        is_unlocked = self.storage.is_game_unlocked(user_id)
        
        if not is_unlocked:
            await self._check_game_unlocked(interaction)
            return
        
        embed = discord.Embed(
            title="🦛 Pokemon Game Guide",
            description="Your complete guide to catching and training Pokemon!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎯 Catching Pokemon",
            value=(
                "**`/catch`** (1 🍪) - Common/Uncommon Pokemon\n"
                "**`/fish`** (1 🍪) - Water-types (chance for rare!)\n"
                "**`/explore`** (3 🍪) - Rare/Legendary Pokemon\n\n"
                "Your relationship level affects catch rates!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📦 Collection Limits",
            value=(
                "• Max **3 of each species**\n"
                "• Use duplicates to evolve Pokemon\n"
                "• View your collection with `/collection`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💪 Training",
            value=(
                "**`/train <pokemon_id> <cookies>`** (2 🍪 stamina)\n"
                "Spend cookies to gain XP for your Pokemon!\n"
                "XP amount is luck-based (relationship affects this)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔄 Evolution",
            value=(
                "**`/evolve <pokemon_id> <duplicate_id>`**\n"
                "Requirements:\n"
                "• 2+ of the same species\n"
                "• Evolution cookies (varies by species)\n"
                "• The duplicate will be consumed"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚔️ Battles",
            value=(
                "**`/battle @user`** (2 🍪) - Challenge players!\n"
                "Turn-based combat with type effectiveness\n"
                "Winner earns XP and cookies!\n"
                "• `/battle_move <1-4>` - Use a move\n"
                "• `/battle_status` - Check battle\n"
                "• `/battle_forfeit` - Give up"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🍪 Cookie Management",
            value=(
                "Check your cookies: `/check_cookies`\n"
                "Earn more by interacting with me!\n"
                "Use `/help` for all bot features"
            ),
            inline=False
        )
        
        embed.set_footer(text="Have fun catching them all! 🦛")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @cookies.command(name="balance", description="💰 Check your cookie balance and stats")
    async def check_cookies(self, interaction: discord.Interaction) -> None:
        """Check cookie balance and stats."""
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        cookie_stats = self.cookie_manager.get_cookie_balance(user_id)
        relationship = self.relationship_manager.get_relationship_index(user_id)
        tier = self.relationship_manager.get_relationship_tier(user_id)
        luck = self.relationship_manager.get_luck_modifier(user_id)
        user_data = self.storage.get_user_data(user_id)
        
        streak = user_data.get('daily_streak', 0) if user_data else 0
        
        embed = discord.Embed(
            title=f"🍪 {interaction.user.display_name}'s Stats",
            color=discord.Color.gold()
        )
        
        # Check if owner has unlimited cookies
        is_owner = self.cookie_manager._is_owner(user_id)
        cookie_balance_text = (
            f"**Current:** {cookie_stats['current_balance']} 🍪\n"
            f"**Total Earned:** {cookie_stats['total_earned']} 🍪\n"
            f"**Spent:** {cookie_stats['spent']} 🍪"
        )
        if is_owner:
            cookie_balance_text += "\n✨ **UNLIMITED COOKIES** ✨ (Owner Mode)"
        
        embed.add_field(
            name="Cookie Balance",
            value=cookie_balance_text,
            inline=False
        )
        
        embed.add_field(
            name="Relationship",
            value=(
                f"**Level:** {relationship}/100\n"
                f"**Tier:** {tier}\n"
                f"**Daily Streak:** {streak} days 🔥"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Luck & Bonuses",
            value=(
                f"**Luck Multiplier:** {luck:.2f}x\n"
                f"**Drop Rate Bonus:** +{self.relationship_manager.get_cookie_drop_bonus(user_id)*100:.1f}%"
            ),
            inline=False
        )
        
        # Game status
        game_status = "🎮 Unlocked" if self.storage.is_game_unlocked(user_id) else "🔒 Locked (need 5 🍪)"
        embed.add_field(
            name="Pokemon Game",
            value=game_status,
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @cookies.command(name="leaderboard", description="🏆 View the top cookie earners!")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        """Display cookie leaderboard."""
        # Defer response since we might need to fetch usernames
        await interaction.response.defer()
        
        # Get top 10 users
        leaderboard_data = self.storage.get_cookie_leaderboard(limit=10)
        
        if not leaderboard_data:
            await interaction.followup.send("No one has earned cookies yet! 🍪", ephemeral=True)
            return
        
        # Build the leaderboard embed
        embed = discord.Embed(
            title="🏆 Cookie Leaderboard 🍪",
            description="Top cookie earners in the server!",
            color=discord.Color.gold()
        )
        
        leaderboard_text = []
        for idx, user_data in enumerate(leaderboard_data, start=1):
            user_id = user_data['user_id']
            total = user_data['total_cookies']
            current = user_data['cookies_left']
            
            # Try to get username
            try:
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name if hasattr(user, 'display_name') else user.name
            except:
                username = f"User {user_id}"
            
            # Medal for top 3
            medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"**{idx}.**"
            leaderboard_text.append(
                f"{medal} **{username}** - {total:,} 🍪 total ({current:,} current)"
            )
        
        embed.description = "\n".join(leaderboard_text)
        embed.set_footer(text="Keep earning cookies by interacting with Baby Hippo!")
        
        # Post to followup (already deferred)
        await interaction.followup.send(embed=embed)

    @pokemon.command(name="catch", description="🎯 Attempt to catch a random Pokemon! (Costs 1 cookie)")
    async def catch(self, interaction: discord.Interaction) -> None:
        """Catch a random Pokemon."""
        if not await self._check_allowed_channel(interaction):
            return
        if not await self._check_game_unlocked(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check stamina
        if not self.cookie_manager.can_afford(user_id, 'catch'):
            await interaction.response.send_message(
                "🦛 You don't have enough cookies! Use `/check_cookies` to see your balance.",
                ephemeral=True
            )
            return
        
        # Spend cookies
        success, cost = self.cookie_manager.spend_stamina(user_id, 'catch')
        if not success:
            await interaction.response.send_message("⚠️ Failed to spend cookies. Try again!", ephemeral=True)
            return
        
        # Generate encounter
        encounter = self.pokemon_game.generate_encounter('catch')
        pokemon_name = encounter.species.capitalize()
        user_name = interaction.user.display_name
        
        # Record interaction
        self.relationship_manager.record_interaction(user_id, 'game_action')
        
        # Attempt catch
        caught, pokemon = self.pokemon_game.attempt_catch(user_id, encounter)
        
        if pokemon:
            # Success!
            embed = discord.Embed(
                title="\U0001f389 Pokemon Caught!",
                description=(
                    f"{self.personality_engine.get_pokemon_catch_success(user_name, pokemon_name)}\n\n"
                    f"You caught a **{pokemon_name}**!"
                ),
                color=discord.Color.green()
            )
            embed.add_field(name="Level", value=str(encounter.level), inline=True)
            embed.add_field(name="Rarity", value=encounter.rarity.capitalize(), inline=True)
            embed.add_field(name="ID", value=str(pokemon.pokemon_id), inline=True)
            
            # Try cookie reward
            cookies = self.cookie_manager.try_award_cookies(user_id, 'game_action', self.personality_engine.get_mood())
            if cookies:
                embed.set_footer(text=f"Bonus: +{cookies} 🍪")
            
            await interaction.response.send_message(embed=embed)
        else:
            # Failed
            if not caught:
                # Check if it was limit or catch failure
                count = self.storage.get_pokemon_count_by_species(user_id, encounter.species)
                if count >= 3:
                    result_info = f"\U0001f99b A **{pokemon_name}** appeared, but you already have 3! Consider evolving one."
                else:
                    result_info = f"\U0001f99b A **{pokemon_name}** (Lv.{encounter.level}) appeared... but it got away! \U0001f614"

                miss_msg = self.personality_engine.get_pokemon_catch_fail(user_name, pokemon_name)
                await interaction.response.send_message(f"{miss_msg}\n{result_info}")

    @pokemon.command(name="fish", description="🎣 Fish for water-type Pokemon! (Costs 1 cookie)")
    async def fish(self, interaction: discord.Interaction) -> None:
        """Fish for water-type Pokemon."""
        if not await self._check_allowed_channel(interaction):
            return
        if not await self._check_game_unlocked(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check stamina
        if not self.cookie_manager.can_afford(user_id, 'fish'):
            await interaction.response.send_message(
                "🦛 You don't have enough cookies! Use `/check_cookies` to see your balance.",
                ephemeral=True
            )
            return
        
        # Spend cookies
        success, cost = self.cookie_manager.spend_stamina(user_id, 'fish')
        if not success:
            await interaction.response.send_message("⚠️ Failed to spend cookies. Try again!", ephemeral=True)
            return
        
        # Generate encounter
        encounter = self.pokemon_game.generate_encounter('fish')
        pokemon_name = encounter.species.capitalize()
        user_name = interaction.user.display_name
        
        # Record interaction
        self.relationship_manager.record_interaction(user_id, 'game_action')
        
        # Attempt catch
        caught, pokemon = self.pokemon_game.attempt_catch(user_id, encounter)
        
        if pokemon:
            # Success!
            embed = discord.Embed(
                title="🎣 Pokemon Fished!",
                description=(
                    f"{self.personality_engine.get_pokemon_catch_success(user_name, pokemon_name)}\n\n"
                    f"You fished up a **{pokemon_name}**!"
                ),
                color=discord.Color.blue()
            )
            embed.add_field(name="Level", value=str(encounter.level), inline=True)
            embed.add_field(name="Rarity", value=encounter.rarity.capitalize(), inline=True)
            embed.add_field(name="ID", value=str(pokemon.pokemon_id), inline=True)
            
            # Try cookie reward
            cookies = self.cookie_manager.try_award_cookies(user_id, 'game_action', self.personality_engine.get_mood())
            if cookies:
                embed.set_footer(text=f"Bonus: +{cookies} 🍪")
            
            await interaction.response.send_message(embed=embed)
        else:
            count = self.storage.get_pokemon_count_by_species(user_id, encounter.species)
            if count >= 3:
                result_info = f"🎣 A **{pokemon_name}** bit the line, but you already have 3!"
            else:
                result_info = f"🎣 A **{pokemon_name}** (Lv.{encounter.level}) got away... 😔"

            miss_msg = self.personality_engine.get_pokemon_catch_fail(user_name, pokemon_name)
            await interaction.response.send_message(f"{miss_msg}
{result_info}")

    @pokemon.command(name="explore", description="🔍 Explore for rare Pokemon! (Costs 3 cookies)")
    async def explore(self, interaction: discord.Interaction) -> None:
        """Explore for rare Pokemon."""
        if not await self._check_allowed_channel(interaction):
            return
        if not await self._check_game_unlocked(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check stamina
        if not self.cookie_manager.can_afford(user_id, 'explore'):
            await interaction.response.send_message(
                "🦛 You don't have enough cookies! Need 3 🍪 to explore.",
                ephemeral=True
            )
            return
        
        # Spend stamina
        success, cost = self.cookie_manager.spend_stamina(user_id, 'explore')
        if not success:
            await interaction.response.send_message("⚠️ Failed to spend cookies. Try again!", ephemeral=True)
            return
        
        # Generate encounter
        encounter = self.pokemon_game.generate_encounter('explore')
        pokemon_name = encounter.species.capitalize()
        user_name = interaction.user.display_name
        
        # Record interaction
        self.relationship_manager.record_interaction(user_id, 'game_action')
        
        # Attempt catch
        caught, pokemon = self.pokemon_game.attempt_catch(user_id, encounter)
        
        if pokemon:
            # Success!
            embed = discord.Embed(
                title="🌟 Rare Discovery!",
                description=(
                    f"{self.personality_engine.get_pokemon_catch_success(user_name, pokemon_name)}\n\n"
                    f"You discovered a **{pokemon_name}**!"
                ),
                color=discord.Color.purple()
            )
            embed.add_field(name="Level", value=str(encounter.level), inline=True)
            embed.add_field(name="Rarity", value=encounter.rarity.capitalize(), inline=True)
            embed.add_field(name="ID", value=str(pokemon.pokemon_id), inline=True)
            
            # Try cookie reward
            cookies = self.cookie_manager.try_award_cookies(user_id, 'game_action', self.personality_engine.get_mood())
            if cookies:
                embed.set_footer(text=f"Bonus: +{cookies} 🍪")
            
            await interaction.response.send_message(embed=embed)
        else:
            count = self.storage.get_pokemon_count_by_species(user_id, encounter.species)
            if count >= 3:
                result_info = f"🌟 A **{pokemon_name}** appeared, but you already have 3!"
            else:
                result_info = f"🌟 A **{pokemon_name}** (Lv.{encounter.level}) fled... 😔"

            miss_msg = self.personality_engine.get_pokemon_catch_fail(user_name, pokemon_name)
            await interaction.response.send_message(f"{miss_msg}
{result_info}")

    @pokemon.command(name="collection", description="📋 View your Pokemon collection")
    async def collection(self, interaction: discord.Interaction) -> None:
        """View Pokemon collection."""
        if not await self._check_allowed_channel(interaction):
            return
        if not await self._check_game_unlocked(interaction):
            return
        
        user_id = str(interaction.user.id)
        collection = self.pokemon_game.get_user_collection(user_id)
        
        if not collection:
            await interaction.response.send_message(
                "🦛 Your collection is empty! Use `/catch`, `/fish`, or `/explore` to find Pokemon!",
                ephemeral=True
            )
            return
        
        # Group by species
        species_groups = {}
        for pokemon in collection:
            species = pokemon['species']
            if species not in species_groups:
                species_groups[species] = []
            species_groups[species].append(pokemon)
        
        embed = discord.Embed(
            title=f"🦛 {interaction.user.display_name}'s Pokemon Collection",
            description=f"Total Pokemon: {len(collection)}",
            color=discord.Color.green()
        )
        
        for species, pokemon_list in list(species_groups.items())[:10]:  # Limit to 10 species per page
            pokemon_info = []
            for poke in pokemon_list[:3]:  # Show up to 3 of each species
                pokemon_info.append(
                    f"ID:{poke['pokemon_id']} | Lv.{poke['level']} | XP:{poke['experience']}"
                )
            
            count_text = f"({len(pokemon_list)}/3)" if len(pokemon_list) < 3 else "(MAX 3/3)"
            embed.add_field(
                name=f"{species.capitalize()} {count_text}",
                value="\n".join(pokemon_info),
                inline=False
            )
        
        if len(species_groups) > 10:
            embed.set_footer(text=f"Showing 10/{len(species_groups)} species...")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @pokemon.command(name="train", description="💪 Train a Pokemon with cookies to level it up")
    @app_commands.describe(pokemon_id="The ID of the Pokemon to train", cookies="Number of cookies to spend (2 stamina + cookies for XP)")
    async def train(self, interaction: discord.Interaction, pokemon_id: int, cookies: int) -> None:
        """Train a Pokemon."""
        if not await self._check_allowed_channel(interaction):
            return
        if not await self._check_game_unlocked(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        if cookies < 1:
            await interaction.response.send_message("🦛 You need to spend at least 1 cookie for training!", ephemeral=True)
            return
        
        # Check if user has enough cookies (2 for stamina + cookies for training)
        total_cost = 2 + cookies
        _, current = self.storage.get_user_cookies(user_id)
        if current < total_cost:
            await interaction.response.send_message(
                f"🦛 Not enough cookies! Need {total_cost} 🍪 (2 stamina + {cookies} for training)\nYou have: {current} 🍪",
                ephemeral=True
            )
            return
        
        # Train Pokemon
        success, updated_pokemon = self.pokemon_game.train_pokemon(user_id, pokemon_id, cookies)
        
        if not success or not updated_pokemon:
            await interaction.response.send_message("⚠️ Training failed! Check that the Pokemon ID is correct.", ephemeral=True)
            return
        
        # Calculate XP gain (difference from before)
        xp_gain = self.cookie_manager.calculate_training_xp(user_id, cookies)
        
        embed = discord.Embed(
            title="💪 Training Complete!",
            description=f"**{updated_pokemon['species'].capitalize()}** gained experience!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Level", value=str(updated_pokemon['level']), inline=True)
        embed.add_field(name="XP Gained", value=f"+{xp_gain}", inline=True)
        embed.add_field(name="Total XP", value=str(updated_pokemon['experience']), inline=True)
        embed.set_footer(text=f"Spent: {total_cost} 🍪 (1 stamina + {cookies} training)")
        
        await interaction.response.send_message(embed=embed)

    @pokemon.command(name="evolve", description="✨ Evolve a Pokemon using your duplicates")
    @app_commands.describe(
        pokemon_id="ID of the Pokemon to evolve (oldest capture stays as main)",
        duplicate_id="Optional duplicate ID to consume (auto-selects newest if omitted)"
    )
    async def evolve(
        self,
        interaction: discord.Interaction,
        pokemon_id: int,
        duplicate_id: Optional[int] = None
    ) -> None:
        """Evolve a Pokemon."""
        if not await self._check_allowed_channel(interaction):
            return
        if not await self._check_game_unlocked(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Check if can evolve
        can_evolve_result = self.pokemon_game.can_evolve(user_id, pokemon_id)
        can_evolve, evolved_form, cookie_cost, reason = can_evolve_result
        
        if not can_evolve:
            if reason:
                await interaction.response.send_message(f"🦛 {reason}", ephemeral=True)
            elif not evolved_form:
                await interaction.response.send_message("🦛 This Pokemon can't evolve!", ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"🦛 Can't evolve yet! Requirements:\n"
                    f"• 2+ of the same species\n"
                    f"• {cookie_cost} 🍪 for evolution",
                    ephemeral=True
                )
            return
        
        # Evolve
        success, evolved_pokemon, error_msg = self.pokemon_game.evolve_pokemon(
            user_id, pokemon_id, duplicate_id
        )
        
        if not success or not evolved_pokemon:
            error_text = error_msg or "Check your Pokemon IDs and cookies."
            await interaction.response.send_message(f"⚠️ Evolution failed! {error_text}", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="✨ Evolution Success!",
            description=f"Your Pokemon evolved into **{evolved_pokemon['species'].capitalize()}**!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Level", value=str(evolved_pokemon['level']), inline=True)
        embed.add_field(name="New ID", value=str(evolved_pokemon['pokemon_id']), inline=True)
        
        # Show evolution stage info
        if evolved_pokemon['species'].lower() in self.pokemon_game.EVOLUTIONS:
            next_form, next_level, _, _ = self.pokemon_game.EVOLUTIONS[evolved_pokemon['species'].lower()]
            embed.add_field(
                name="Next Evolution",
                value=f"{next_form.capitalize()} at Lv.{next_level}",
                inline=False
            )
        else:
            embed.add_field(name="Evolution", value="✨ Final Form!", inline=False)
        
        consumed_id = evolved_pokemon.get('consumed_duplicate_id')
        consumed_name = evolved_pokemon.get('consumed_duplicate_nickname') or "duplicate"
        if consumed_id:
            footer = f"Evolution cost: {cookie_cost} 🍪 + {consumed_name} (ID:{consumed_id}) consumed"
        else:
            footer = f"Evolution cost: {cookie_cost} 🍪"
        embed.set_footer(text=footer)
        
        await interaction.response.send_message(embed=embed)

    @pokemon.command(name="evolve_list", description="📜 View your evolution-ready Pokemon IDs")
    async def evolve_list(self, interaction: discord.Interaction) -> None:
        """List Pokemon eligible for evolution with their IDs."""
        if not await self._check_allowed_channel(interaction):
            return
        if not await self._check_game_unlocked(interaction):
            return

        user_id = str(interaction.user.id)
        candidates = self.pokemon_game.get_evolution_candidates(user_id)

        if not candidates:
            await interaction.response.send_message(
                "🦛 You don't have any evolution-ready Pokemon yet.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📜 Evolution Candidates",
            description="Oldest capture is treated as your main Pokemon for evolution.",
            color=discord.Color.gold()
        )

        for candidate in candidates[:10]:
            duplicates = ", ".join(str(d) for d in candidate["duplicate_ids"]) or "None"
            next_form = candidate["next_form"].capitalize() if candidate["next_form"] else "Unknown"
            if candidate["ready"]:
                status = "✅ Ready"
            else:
                reason = candidate["reason"] or "Not ready"
                status = f"❌ {reason}"
            embed.add_field(
                name=f"{candidate['species'].capitalize()} ➜ {next_form}",
                value=(
                    f"Main ID: {candidate['main_id']} (Lv.{candidate['main_level']})\n"
                    f"Duplicates: {duplicates}\n"
                    f"Cost: {candidate['cookie_cost']} 🍪\n"
                    f"Status: {status}"
                ),
                inline=False,
            )

        if len(candidates) > 10:
            embed.set_footer(text=f"Showing first 10 of {len(candidates)} options.")
        else:
            embed.set_footer(text="Oldest capture remains your main partner today.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @pokemon.command(name="info", description="ℹ️ Get detailed information about any Pokemon")
    @app_commands.describe(pokemon_name="Name of the Pokemon")
    async def pokemon_info(self, interaction: discord.Interaction, pokemon_name: str) -> None:
        """Fetch Pokemon information using PokeAPI."""
        user_id = str(interaction.user.id)
        self.relationship_manager.record_interaction(user_id, 'help_command')
        
        data = self.pokemon_api.get_pokemon_data(pokemon_name)
        if data:
            embed = discord.Embed(
                title=f"{pokemon_name.capitalize()}",
                description=f"Species: {data['species']['name']}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Base Experience", value=str(data['base_experience']), inline=True)
            embed.add_field(name="Height", value=str(data['height']), inline=True)
            embed.add_field(name="Weight", value=str(data['weight']), inline=True)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"⚠️ Could not find data for Pokemon: {pokemon_name}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Setup function - dependencies injected by IntegrationLoader."""
    pass

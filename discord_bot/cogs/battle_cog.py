"""
Battle Cog - Discord commands for Pokemon battles.

Commands:
- /battle @user - Challenge another user to a Pokemon battle
- /battle_move <move_number> - Use a move during your turn
- /battle_forfeit - Forfeit the current battle
- /battle_status - Check current battle status
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from discord_bot.core.utils import find_bot_channel, is_allowed_channel
from discord_bot.cogs.game_cog import GameCog

try:
    from discord_bot.games.battle_system import (
        BattleEngine, BattlePokemon, create_battle, get_active_battle, 
        end_battle, BattleState
    )
    from discord_bot.games.storage.game_storage_engine import GameStorageEngine
    from discord_bot.core.engines.cookie_manager import CookieManager
    from discord_bot.core.engines.relationship_manager import RelationshipManager
except ImportError:
    from games.battle_system import (
        BattleEngine, BattlePokemon, create_battle, get_active_battle,
        end_battle, BattleState
    )
    from games.storage.game_storage_engine import GameStorageEngine
    from core.engines.cookie_manager import CookieManager
    from core.engines.relationship_manager import RelationshipManager


class BattleCog(commands.Cog):
    """Pokemon battle commands."""
    
    # Use the battle group from GameCog (shared nested group)
    battle = GameCog.battle
    
    def __init__(self, bot: commands.Bot, storage: GameStorageEngine,
                 cookie_manager: CookieManager, relationship_manager: RelationshipManager):
        self.bot = bot
        self.storage = storage
        self.cookie_manager = cookie_manager
        self.relationship_manager = relationship_manager
    
    async def _check_allowed_channel(self, interaction: discord.Interaction) -> bool:
        """Check if command is used in an allowed channel."""
        if not interaction.channel:
            return False
        
        if not is_allowed_channel(interaction.channel.id):
            await interaction.response.send_message(
                "🦛 I can only respond to battle commands in designated channels! "
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
    
    def _create_battle_pokemon(self, pokemon_data: dict) -> BattlePokemon:
        """Convert database Pokemon to BattlePokemon for battle."""
        moves = BattleEngine.assign_moves_to_pokemon(pokemon_data, pokemon_data['level'])
        
        types = pokemon_data.get('types', [])
        if isinstance(types, str):
            # Parse if stored as string
            types = [t.strip() for t in types.split(',') if t.strip()]
        
        return BattlePokemon(
            pokemon_id=pokemon_data['pokemon_id'],
            user_id=pokemon_data['user_id'],
            species=pokemon_data['species'],
            nickname=pokemon_data.get('nickname'),
            level=pokemon_data['level'],
            max_hp=pokemon_data['hp'],
            current_hp=pokemon_data['hp'],
            attack=pokemon_data['attack'],
            defense=pokemon_data['defense'],
            special_attack=pokemon_data['special_attack'],
            special_defense=pokemon_data['special_defense'],
            speed=pokemon_data['speed'],
            types=types if types else ['normal'],
            moves=moves
        )
    
    def _create_battle_embed(self, battle: BattleState, title: str = "Pokemon Battle") -> discord.Embed:
        """Create an embed showing current battle status."""
        embed = discord.Embed(
            title=title,
            color=discord.Color.red()
        )
        
        # Challenger Pokemon
        c_poke = battle.challenger_pokemon
        embed.add_field(
            name=f"🔴 {c_poke.display_name} (Lv.{c_poke.level})",
            value=f"HP: {c_poke.current_hp}/{c_poke.max_hp} ({c_poke.hp_percentage:.1f}%)\n{'❤️' * int(c_poke.hp_percentage // 10)}",
            inline=False
        )
        
        # Opponent Pokemon
        o_poke = battle.opponent_pokemon
        embed.add_field(
            name=f"🔵 {o_poke.display_name} (Lv.{o_poke.level})",
            value=f"HP: {o_poke.current_hp}/{o_poke.max_hp} ({o_poke.hp_percentage:.1f}%)\n{'💙' * int(o_poke.hp_percentage // 10)}",
            inline=False
        )
        
        # Turn info
        current_user = battle.current_turn_user_id
        if current_user == battle.challenger_id:
            current_name = c_poke.display_name
        else:
            current_name = o_poke.display_name
        
        embed.add_field(
            name="⚔️ Current Turn",
            value=f"**{current_name}**'s turn! (Turn {battle.turn_number + 1})",
            inline=False
        )
        
        return embed
    
    def _create_moves_embed(self, pokemon: BattlePokemon) -> discord.Embed:
        """Create an embed showing available moves."""
        embed = discord.Embed(
            title=f"{pokemon.display_name}'s Moves",
            description="Use `/battle_move <number>` to attack!",
            color=discord.Color.blue()
        )
        
        for i, move in enumerate(pokemon.moves, 1):
            embed.add_field(
                name=f"{i}. {move.name}",
                value=f"Type: {move.type.title()} | Power: {move.power} | Accuracy: {move.accuracy}%",
                inline=False
            )
        
        return embed
    
    @battle.command(name="start", description="⚔️ Challenge someone to a Pokemon battle! (Costs 2 cookies)")
    @app_commands.describe(opponent="The user to challenge")
    async def battle_start(self, interaction: discord.Interaction, opponent: discord.User) -> None:
        """Challenge another user to a Pokemon battle."""
        if not await self._check_allowed_channel(interaction):
            return
        
        challenger_id = str(interaction.user.id)
        opponent_id = str(opponent.id)
        
        # Check if game is unlocked
        if not self.storage.is_game_unlocked(challenger_id):
            await interaction.response.send_message(
                "🦛 You need to unlock the Pokemon game first! Use `/feed` to unlock it.",
                ephemeral=True
            )
            return
        
        if not self.storage.is_game_unlocked(opponent_id):
            await interaction.response.send_message(
                f"🦛 {opponent.display_name} hasn't unlocked the Pokemon game yet!",
                ephemeral=True
            )
            return
        
        # Check if challenging self
        if challenger_id == opponent_id:
            await interaction.response.send_message(
                "🦛 You can't battle yourself! Challenge another player or the bot!",
                ephemeral=True
            )
            return
        
        # Check if already in battle
        if get_active_battle(challenger_id):
            await interaction.response.send_message(
                "⚠️ You're already in a battle! Finish it first with `/battle_move` or `/battle_forfeit`",
                ephemeral=True
            )
            return
        
        if get_active_battle(opponent_id):
            await interaction.response.send_message(
                f"⚠️ {opponent.display_name} is already in a battle!",
                ephemeral=True
            )
            return
        
        # Check cookies
        if not self.cookie_manager.can_afford(challenger_id, 'battle'):
            await interaction.response.send_message(
                "🦛 You don't have enough cookies! Battles cost 2 🍪",
                ephemeral=True
            )
            return
        
        # Get Pokemon for both players
        challenger_pokemon_list = self.storage.get_user_pokemon(challenger_id)
        opponent_pokemon_list = self.storage.get_user_pokemon(opponent_id)
        
        if not challenger_pokemon_list:
            await interaction.response.send_message(
                "🦛 You don't have any Pokemon! Catch some first with `/catch`",
                ephemeral=True
            )
            return
        
        if not opponent_pokemon_list:
            await interaction.response.send_message(
                f"🦛 {opponent.display_name} doesn't have any Pokemon yet!",
                ephemeral=True
            )
            return
        
        # Use highest level Pokemon for each player
        challenger_poke_data = max(challenger_pokemon_list, key=lambda p: p['level'])
        opponent_poke_data = max(opponent_pokemon_list, key=lambda p: p['level'])
        
        # Create battle Pokemon
        challenger_battle_poke = self._create_battle_pokemon(challenger_poke_data)
        opponent_battle_poke = self._create_battle_pokemon(opponent_poke_data)
        
        # Spend cookies
        success, cost = self.cookie_manager.spend_stamina(challenger_id, 'battle')
        if not success:
            await interaction.response.send_message(
                "⚠️ Failed to spend cookies. Please try again.",
                ephemeral=True
            )
            return
        
        # Create battle
        battle = create_battle(
            challenger_id, opponent_id,
            challenger_battle_poke, opponent_battle_poke
        )
        
        # Record interaction
        self.relationship_manager.record_interaction(challenger_id, 'game_action')
        
        # Create battle start embed
        embed = self._create_battle_embed(battle, "⚔️ Battle Started!")
        embed.set_footer(text=f"Battle cost: {cost} 🍪 | Use /battle_move to attack!")
        
        # Send to channel
        await interaction.response.send_message(
            content=f"⚔️ **{interaction.user.display_name}** challenges **{opponent.display_name}** to a Pokemon battle!",
            embed=embed
        )
        
        # Send move list to current turn player
        current_pokemon = battle.challenger_pokemon if battle.current_turn_user_id == challenger_id else battle.opponent_pokemon
        moves_embed = self._create_moves_embed(current_pokemon)
        
        # Try to DM the current player (or send ephemeral)
        current_user = interaction.user if battle.current_turn_user_id == challenger_id else opponent
        try:
            await current_user.send(embed=moves_embed)
        except:
            # If DM fails, they can use /battle_status
            pass
    
    @battle.command(name="move", description="⚡ Use a move in your current battle")
    @app_commands.describe(move_number="Which move to use (1-4)")
    async def battle_move(self, interaction: discord.Interaction, move_number: int) -> None:
        """Execute a move in the current battle."""
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        # Get active battle
        battle = get_active_battle(user_id)
        if not battle:
            await interaction.response.send_message(
                "🦛 You're not in a battle! Use `/battle @user` to start one.",
                ephemeral=True
            )
            return
        
        # Check if it's user's turn
        if battle.current_turn_user_id != user_id:
            await interaction.response.send_message(
                "⚠️ It's not your turn! Wait for your opponent to move.",
                ephemeral=True
            )
            return
        
        # Validate move number
        if move_number < 1 or move_number > 4:
            await interaction.response.send_message(
                "⚠️ Invalid move number! Choose a move from 1-4.",
                ephemeral=True
            )
            return
        
        # Get attacker and defender
        attacker = battle.get_pokemon_by_user(user_id)
        defender = battle.get_opponent_pokemon(user_id)
        
        # Check if move exists
        move_index = move_number - 1
        if move_index >= len(attacker.moves):
            await interaction.response.send_message(
                f"⚠️ You only have {len(attacker.moves)} moves available!",
                ephemeral=True
            )
            return
        
        # Execute turn
        turn_result = BattleEngine.execute_turn(attacker, defender, move_index)
        battle.battle_log.append(turn_result)
        
        # Create result embed
        embed = discord.Embed(
            title="💥 Battle Action!",
            description=turn_result.message,
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Damage Dealt",
            value=f"{turn_result.damage_dealt} HP",
            inline=True
        )
        
        # Check if battle is over
        if turn_result.defender_fainted:
            battle.winner_id = user_id
            battle.is_finished = True
            
            winner_pokemon = attacker
            loser_pokemon = defender
            loser_id = battle.get_opponent_id(user_id)
            
            # Calculate rewards
            xp_reward = BattleEngine.calculate_xp_reward(winner_pokemon.level, loser_pokemon.level)
            cookie_reward = BattleEngine.calculate_cookie_reward(winner_pokemon.level, loser_pokemon.level)
            
            # Award XP to winner's Pokemon
            self.storage.update_pokemon_xp(winner_pokemon.pokemon_id, xp_reward)
            
            # Award cookies to winner
            self.storage.add_cookies(user_id, cookie_reward)
            
            # Victory embed
            victory_embed = discord.Embed(
                title="🎉 Battle Complete!",
                description=f"**{attacker.display_name}** defeated **{defender.display_name}**!",
                color=discord.Color.gold()
            )
            
            victory_embed.add_field(
                name="Winner",
                value=f"<@{user_id}>",
                inline=True
            )
            
            victory_embed.add_field(
                name="Rewards",
                value=f"+{xp_reward} XP\n+{cookie_reward} 🍪",
                inline=True
            )
            
            victory_embed.set_footer(text="Good battle! Train your Pokemon to become even stronger!")
            
            await interaction.response.send_message(embed=victory_embed)
            
            # Post public announcement to bot channel
            if interaction.guild:
                announcement_embed = discord.Embed(
                    title="⚔️ Battle Victory!",
                    description=f"<@{user_id}>'s **{attacker.display_name}** defeated <@{loser_id}>'s **{defender.display_name}**!",
                    color=discord.Color.gold()
                )
                announcement_embed.add_field(
                    name="Rewards",
                    value=f"+{xp_reward} XP, +{cookie_reward} 🍪",
                    inline=False
                )
                await self._post_to_bot_channel(interaction.guild, announcement_embed)
            
            # End battle
            end_battle(battle)
            
        else:
            # Battle continues
            battle.switch_turn()
            
            # Show updated battle status
            status_embed = self._create_battle_embed(battle, "⚔️ Battle Continues!")
            
            await interaction.response.send_message(embed=status_embed)
            
            # Send move options to next player
            next_pokemon = battle.get_pokemon_by_user(battle.current_turn_user_id)
            moves_embed = self._create_moves_embed(next_pokemon)
            
            # Get next player user object
            next_user_id = battle.current_turn_user_id
            if next_user_id == str(interaction.user.id):
                next_user = interaction.user
            else:
                # Try to get from guild
                try:
                    next_user = await interaction.guild.fetch_member(int(next_user_id))
                except:
                    next_user = None
            
            if next_user:
                try:
                    await next_user.send(embed=moves_embed)
                except:
                    pass
    
    @battle.command(name="forfeit", description="🏳️ Forfeit your current battle")
    async def battle_forfeit(self, interaction: discord.Interaction) -> None:
        """Forfeit the current battle."""
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        battle = get_active_battle(user_id)
        if not battle:
            await interaction.response.send_message(
                "🦛 You're not in a battle!",
                ephemeral=True
            )
            return
        
        # Determine winner
        opponent_id = battle.get_opponent_id(user_id)
        battle.winner_id = opponent_id
        battle.is_finished = True
        
        # Create forfeit embed
        embed = discord.Embed(
            title="🏳️ Battle Forfeited",
            description=f"<@{user_id}> has forfeited the battle!\n<@{opponent_id}> wins!",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed)
        
        # End battle
        end_battle(battle)
    
    @battle.command(name="status", description="📊 Check your current battle status")
    async def battle_status(self, interaction: discord.Interaction) -> None:
        """Show current battle status."""
        if not await self._check_allowed_channel(interaction):
            return
        
        user_id = str(interaction.user.id)
        
        battle = get_active_battle(user_id)
        if not battle:
            await interaction.response.send_message(
                "🦛 You're not in a battle! Use `/battle @user` to start one.",
                ephemeral=True
            )
            return
        
        # Show battle status
        embed = self._create_battle_embed(battle)
        
        # Show moves if it's user's turn
        if battle.current_turn_user_id == user_id:
            pokemon = battle.get_pokemon_by_user(user_id)
            moves_embed = self._create_moves_embed(pokemon)
            await interaction.response.send_message(embeds=[embed, moves_embed], ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot, storage: GameStorageEngine,
                cookie_manager: CookieManager, relationship_manager: RelationshipManager):
    """Setup function for the cog with proper dependency injection."""
    await bot.add_cog(BattleCog(bot, storage, cookie_manager, relationship_manager))
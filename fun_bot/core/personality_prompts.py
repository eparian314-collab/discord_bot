from __future__ import annotations

from typing import Dict, List


"""Static personality prompt data for FunBot.

This file purposefully keeps things simple and deterministic. Each
persona maps to a set of message keys, each of which contains one or
more text templates. The :class:`PersonalityEngine` chooses an
appropriate template and formats it with keyword arguments.

No external models or APIs are used; this is entirely local.
"""


PERSONALITY_PROMPTS: Dict[str, Dict[str, List[str]]] = {
    "classic": {
        "pokemon_catch": [
            "You caught **{name}**! You now have **{total}** Pokémon in your collection.",
            "Nice catch! **{name}** joins your team (total: **{total}**).",
        ],
        "pokemon_stats_header": [
            "Here are your Pokémon stats, {user_name}:",
        ],
        "cookies_balance": [
            "You have **{amount}** cookies.",
        ],
        "cookies_give_success": [
            "Gave {amount} cookies to {target}. They now have **{new_amount}** cookies.",
        ],
        "cookies_invalid_amount": [
            "Amount must be a positive integer.",
        ],
        "cookies_no_permission": [
            "Only server admins and the bot owner can give cookies.",
        ],
        "wrong_channel": [
            "Please use this command in the designated bot channel.",
        ],
        "help_intro": [
            "Hi, I'm FunBot! I run games and cookie rewards in the bot channel.",
        ],
        "help_pokemon": [
            "Use /pokemon catch to collect Pokémon and /pokemon stats to see your collection.",
        ],
        "help_cookies": [
            "Use /cookies balance to see your cookies. Admins can use /cookies give to reward members.",
        ],
        "easter_ping": [
            "Pong! I'm awake and watching the chat.",
        ],
        "easter_vibe": [
            "The vibes are **{vibe}** today.",
        ],
        "battle_start": [
            "Battle started between {p1} and {p2}! {first_turn} goes first.",
        ],
        "battle_moves_list": [
            "Available moves: {moves}",
        ],
        "battle_not_in_battle": [
            "You are not currently in a battle in this channel.",
        ],
        "battle_not_your_turn": [
            "It's not your turn yet. Please wait for your opponent.",
        ],
        "battle_invalid_move": [
            "Unknown move '{move_name}'. Use /battle moves to see your options.",
        ],
        "battle_turn_result": [
            "{actor} used **{move_name}**! {effect} {status}",
        ],
        "battle_victory": [
            "{winner} wins the battle! GG.",
        ],
        "battle_forfeit": [
            "{loser} forfeited the battle. {winner} takes the win.",
        ],
    },
    "gamer": {
        "pokemon_catch": [
            "GG! You caught **{name}**. Collection now at **{total}**.",
        ],
        "cookies_balance": [
            "Inventory check: you have **{amount}** cookies in your bag.",
        ],
    },
    "meme": {
        "pokemon_catch": [
            "**{name}** joined your squad. Much wow. Total: **{total}**.",
        ],
        "easter_ping": [
            "Ping? More like P O N G. 🎯",  # visual flair even without emojis rendered
        ],
    },
}


__all__ = ["PERSONALITY_PROMPTS"]

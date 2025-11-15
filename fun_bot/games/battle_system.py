from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import random


MAX_HP = 100


@dataclass(slots=True)
class Move:
    name: str
    description: str
    power: int = 0
    heal: int = 0
    accuracy: float = 1.0


@dataclass(slots=True)
class BattleParticipant:
    user_id: int
    display_name: str
    hp: int = MAX_HP


@dataclass(slots=True)
class BattleState:
    """In-memory representation of a two-player battle."""

    channel_id: int
    p1: BattleParticipant
    p2: BattleParticipant
    current_turn: int
    winner_id: Optional[int] = None

    @property
    def is_finished(self) -> bool:
        return self.winner_id is not None

    def other_player(self, user_id: int) -> BattleParticipant:
        if self.p1.user_id == user_id:
            return self.p2
        if self.p2.user_id == user_id:
            return self.p1
        raise ValueError("User is not part of this battle")

    def get_player(self, user_id: int) -> BattleParticipant:
        if self.p1.user_id == user_id:
            return self.p1
        if self.p2.user_id == user_id:
            return self.p2
        raise ValueError("User is not part of this battle")


MOVES: Dict[str, Move] = {
    "strike": Move(
        name="strike",
        description="Reliable attack dealing moderate damage.",
        power=20,
        accuracy=0.95,
    ),
    "heavy_strike": Move(
        name="heavy_strike",
        description="Big hit with a chance to miss.",
        power=30,
        accuracy=0.75,
    ),
    "heal": Move(
        name="heal",
        description="Recover a chunk of your HP.",
        heal=18,
        accuracy=1.0,
    ),
}


def list_moves() -> List[Move]:
    return list(MOVES.values())


def create_battle(
    channel_id: int,
    p1_id: int,
    p1_name: str,
    p2_id: int,
    p2_name: str,
    *,
    starting_hp: int = MAX_HP,
) -> BattleState:
    """Create a new battle state with fresh HP for both players."""

    p1 = BattleParticipant(user_id=p1_id, display_name=p1_name, hp=starting_hp)
    p2 = BattleParticipant(user_id=p2_id, display_name=p2_name, hp=starting_hp)
    return BattleState(channel_id=channel_id, p1=p1, p2=p2, current_turn=p1_id)


def perform_move(
    state: BattleState,
    actor_id: int,
    move_name: str,
    *,
    rng: Optional[random.Random] = None,
) -> Tuple[BattleState, str, str]:
    """Apply a move for the acting user.

    Returns ``(state, effect_text, status_text)`` where ``effect_text``
    describes the immediate outcome (hit, heal, miss) and
    ``status_text`` summarises HP and winner state after the move.
    """

    if state.is_finished:
        return state, "The battle is already over.", ""

    if actor_id != state.current_turn:
        raise PermissionError("Not this player's turn")

    move_key = move_name.lower().strip()
    if move_key not in MOVES:
        raise KeyError(move_key)

    if rng is None:
        rng = random.Random()

    actor = state.get_player(actor_id)
    target = state.other_player(actor_id)
    move = MOVES[move_key]

    # Determine whether the move hits (for damage or heal).
    hit_roll = rng.random()
    if hit_roll > move.accuracy:
        effect = f"{actor.display_name}'s {move.name} missed!"
    else:
        effect_parts: List[str] = []
        if move.power > 0:
            damage = move.power
            target.hp = max(0, target.hp - damage)
            effect_parts.append(
                f"{actor.display_name} dealt {damage} damage to {target.display_name}."
            )
        if move.heal > 0:
            heal_amount = move.heal
            old_hp = actor.hp
            actor.hp = min(MAX_HP, actor.hp + heal_amount)
            actual_heal = actor.hp - old_hp
            if actual_heal > 0:
                effect_parts.append(
                    f"{actor.display_name} healed {actual_heal} HP."
                )
        effect = " ".join(effect_parts) if effect_parts else "Nothing happened."

    # Check for winner.
    winner_text = ""
    if target.hp <= 0 and actor.hp <= 0:
        # Extremely unlikely with this move set; treat as a draw.
        state.winner_id = None
        winner_text = "It's a draw! Both battlers are down."
    elif target.hp <= 0:
        state.winner_id = actor.user_id
        winner_text = f"{actor.display_name} wins!"
    elif actor.hp <= 0:
        state.winner_id = target.user_id
        winner_text = f"{target.display_name} wins!"

    # Advance turn if the battle continues.
    if not state.is_finished:
        state.current_turn = target.user_id

    status = (
        f"{state.p1.display_name}: {state.p1.hp} HP | "
        f"{state.p2.display_name}: {state.p2.hp} HP"
    )
    if winner_text:
        status = f"{status} — {winner_text}"

    return state, effect, status


def forfeit(state: BattleState, actor_id: int) -> Tuple[BattleState, int]:
    """Mark the battle as forfeited by ``actor_id``.

    Returns ``(state, winner_id)``.
    """

    if state.is_finished:
        if state.winner_id is None:
            raise RuntimeError("Battle already finished in a draw")
        return state, state.winner_id

    loser = state.get_player(actor_id)
    winner = state.other_player(actor_id)
    state.winner_id = winner.user_id
    loser.hp = max(0, loser.hp)
    return state, winner.user_id


__all__ = [
    "Move",
    "BattleParticipant",
    "BattleState",
    "MOVES",
    "list_moves",
    "create_battle",
    "perform_move",
    "forfeit",
]

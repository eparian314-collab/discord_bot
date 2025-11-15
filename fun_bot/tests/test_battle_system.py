from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fun_bot.games.battle_system import (  # noqa: E402
    BattleState,
    create_battle,
    list_moves,
    perform_move,
    forfeit,
    MAX_HP,
)


def test_create_battle_initial_state() -> None:
    state = create_battle(channel_id=1, p1_id=10, p1_name="A", p2_id=20, p2_name="B")
    assert isinstance(state, BattleState)
    assert state.p1.user_id == 10
    assert state.p2.user_id == 20
    assert state.p1.hp == MAX_HP
    assert state.p2.hp == MAX_HP
    assert state.current_turn == 10
    assert not state.is_finished


def test_list_moves_non_empty() -> None:
    moves = list_moves()
    assert moves
    names = {m.name for m in moves}
    assert {"strike", "heavy_strike", "heal"}.issubset(names)


def test_perform_move_switches_turn_and_damages() -> None:
    rng = __import__("random").Random(0)
    state = create_battle(channel_id=1, p1_id=1, p1_name="P1", p2_id=2, p2_name="P2")
    # P1 uses strike on P2
    state, effect, status = perform_move(state, actor_id=1, move_name="strike", rng=rng)
    assert "P1" in effect
    assert state.current_turn == 2
    assert state.p2.hp < MAX_HP
    assert not state.is_finished


def test_perform_move_invalid_turn_raises() -> None:
    state = create_battle(channel_id=1, p1_id=1, p1_name="P1", p2_id=2, p2_name="P2")
    with pytest.raises(PermissionError):
        perform_move(state, actor_id=2, move_name="strike")


def test_perform_move_invalid_move_raises_keyerror() -> None:
    state = create_battle(channel_id=1, p1_id=1, p1_name="P1", p2_id=2, p2_name="P2")
    with pytest.raises(KeyError):
        perform_move(state, actor_id=1, move_name="unknown_move")


def test_forfeit_marks_winner() -> None:
    state = create_battle(channel_id=1, p1_id=1, p1_name="P1", p2_id=2, p2_name="P2")
    state, winner_id = forfeit(state, actor_id=1)
    assert winner_id == 2
    assert state.winner_id == 2
    assert state.is_finished



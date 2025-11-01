import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from discord_bot.core.engines.kvk_tracker import KVKTracker
from discord_bot.core.engines.screenshot_processor import RankingData, StageType, RankingCategory
from discord_bot.games.storage.game_storage_engine import GameStorageEngine


@pytest.fixture()
def storage(tmp_path):
    db_path = tmp_path / "kvk_test.db"
    return GameStorageEngine(db_path=str(db_path))


@pytest.fixture()
def tracker(storage):
    # Use a small reminder window so tests complete quickly.
    return KVKTracker(storage=storage, reminder_days=14)


def _make_ranking(user_id: str, guild_id: str, *, day: int, run_id: int) -> RankingData:
    now = datetime.now(timezone.utc)
    return RankingData(
        user_id=user_id,
        username="Tester",
        guild_tag="TAG",
        event_week="TEST-WEEK",
        stage_type=StageType.PREP,
        day_number=day,
        category=RankingCategory.CONSTRUCTION,
        rank=10,
        score=123_456,
        player_name="Tester",
        submitted_at=now,
        screenshot_url="https://example.com/shot.png",
        guild_id=guild_id,
        kvk_run_id=run_id,
        is_test_run=False,
    )


def test_ensure_run_creates_and_reuses(storage, tracker):
    run, created = asyncio.run(tracker.ensure_run(
        guild_id=123,
        title="KVK Alpha",
        initiated_by=42,
        channel_id=999,
        is_test=False,
        event_id="evt-1",
    ))

    assert created is True
    assert run.run_number == 1
    assert run.is_test is False
    assert run.is_active
    assert abs((run.ends_at - datetime.now(timezone.utc)) - timedelta(days=14)) < timedelta(minutes=1)

    reused, created_second = asyncio.run(tracker.ensure_run(
        guild_id=123,
        title="KVK Alpha",
        initiated_by=42,
        channel_id=999,
        is_test=False,
        event_id="evt-1",
    ))

    assert created_second is False
    assert reused.id == run.id
    assert reused.run_number == 1

    test_run, test_created = asyncio.run(tracker.ensure_run(
        guild_id=123,
        title="TEST KVK",
        initiated_by=42,
        channel_id=999,
        is_test=True,
        event_id="test-evt",
    ))
    assert test_created is True
    assert test_run.is_test is True
    assert test_run.run_number is None


def test_record_submission_and_queries(storage, tracker):
    run, _ = asyncio.run(tracker.ensure_run(
        guild_id=555,
        title="KVK Beta",
        initiated_by=None,
        channel_id=111,
        is_test=False,
        event_id="evt-2",
    ))

    ranking = _make_ranking("1001", "555", day=1, run_id=run.id)
    ranking_id = storage.save_event_ranking(ranking)

    tracker.record_submission(
        kvk_run_id=run.id,
        ranking_id=ranking_id,
        user_id=1001,
        day_number=1,
        stage_type=ranking.stage_type.value,
        is_test=False,
    )

    submission = tracker.get_submission(
        kvk_run_id=run.id,
        user_id=1001,
        day_number=1,
        stage_type=ranking.stage_type.value,
    )
    assert submission is not None
    assert submission["ranking_id"] == ranking_id

    entries = tracker.fetch_user_entries(run_id=run.id, user_id=1001)
    assert len(entries) == 1
    assert entries[0]["kvk_day"] == 1
    assert entries[0]["score"] == ranking.score

    leaderboard = tracker.fetch_leaderboard(run_id=run.id, day_number=1)
    assert len(leaderboard) == 1

    asyncio.run(tracker.close_run(run.id, reason="test"))
    closed = tracker.get_active_run(guild_id=555)
    assert closed is None


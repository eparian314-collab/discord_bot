from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cogs import ranking_cog
from cogs.ranking_cog import RankingCog
from discord_bot.core.engines.screenshot_processor import RankingData, StageType, RankingCategory
from discord_bot.games.storage.game_storage_engine import GameStorageEngine


class FakeProcessor:
    def __init__(self, ranking: RankingData):
        self._ranking = ranking

    async def validate_screenshot(self, image_data: bytes):
        return True, ""

    async def process_screenshot(self, image_data: bytes, user_id: str, username: str, guild_id: str | None = None):
        return self._ranking


class FakeAttachment:
    def __init__(self, url="https://cdn.example.com/screen.png"):
        self.content_type = "image/png"
        self.size = 1024
        self.url = url

    async def read(self):
        return b"fake-image-bytes"


class FakeKvkRun:
    def __init__(self, *, run_number=2, active=True, is_test=False):
        self.id = 77
        self.run_number = run_number
        self.is_test = is_test
        self.is_active = active
        self.started_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.ends_at = datetime(2025, 1, 15, tzinfo=timezone.utc)


class FakeKvkTracker:
    def __init__(self, run: FakeKvkRun | None):
        self._run = run
        self.record_calls = []

    def get_active_run(self, guild_id: int, *, include_tests: bool = True):
        if self._run and self._run.is_active:
            return self._run
        return None

    def list_runs(self, guild_id: int, *, include_tests: bool = True):
        return [self._run] if self._run else []

    def record_submission(self, **kwargs):
        self.record_calls.append(kwargs)


def make_interaction(channel_id: int, user_id: int, *, is_admin=False):
    response = AsyncMock()
    response.defer = AsyncMock()
    response.send_message = AsyncMock()
    response.is_done = lambda: False

    followup = AsyncMock()
    followup.send = AsyncMock()

    interaction = SimpleNamespace(
        guild=SimpleNamespace(id=999),
        guild_id=999,
        channel=SimpleNamespace(id=channel_id),
        channel_id=channel_id,
        user=SimpleNamespace(id=user_id, name="Tester", display_name="Tester"),
        response=response,
        followup=followup,
    )
    return interaction


@pytest.fixture()
def storage(tmp_path):
    db_path = tmp_path / "rankings.db"
    return GameStorageEngine(db_path=str(db_path))


def _build_ranking_data(day: int) -> RankingData:
    now = datetime.now(timezone.utc)
    return RankingData(
        user_id="100",
        username="Tester",
        guild_tag="TAG",
        event_week="placeholder",
        stage_type=StageType.PREP,
        day_number=day,
        category=RankingCategory.CONSTRUCTION,
        rank=12,
        score=222_000,
        player_name="Tester",
        submitted_at=now,
        screenshot_url=None,
        guild_id="999",
        kvk_run_id=None,
        is_test_run=False,
    )


@pytest.mark.asyncio
async def test_submit_ranking_requires_active_run(monkeypatch, storage):
    monkeypatch.setenv("RANKINGS_CHANNEL_ID", "555")
    monkeypatch.setenv("OWNER_IDS", "")
    monkeypatch.setattr(ranking_cog, "is_admin_or_helper", lambda *_: False)

    run = FakeKvkRun(active=True)
    tracker = FakeKvkTracker(run)
    ranking = _build_ranking_data(day=1)
    processor = FakeProcessor(ranking)

    bot = SimpleNamespace()
    cog = RankingCog(bot, processor, storage, kvk_tracker=tracker)

    interaction = make_interaction(channel_id=555, user_id=100)
    attachment = FakeAttachment()

    await cog.submit_ranking(
        interaction=interaction,
        screenshot=attachment,
        day=1,
        stage="prep",
    )

    # ensure tracker recorded submission with run id and normalized day
    assert tracker.record_calls
    record = tracker.record_calls[0]
    assert record["kvk_run_id"] == run.id
    assert record["day_number"] == 1

    rows = storage.get_user_event_rankings(user_id="100", guild_id="999", limit=5)
    assert rows[0]["kvk_run_id"] == run.id


@pytest.mark.asyncio
async def test_submit_ranking_blocks_when_window_closed(monkeypatch, storage):
    monkeypatch.setenv("RANKINGS_CHANNEL_ID", "555")
    monkeypatch.setattr(ranking_cog, "is_admin_or_helper", lambda *args, **kwargs: False)

    closed_run = FakeKvkRun(active=False)
    tracker = FakeKvkTracker(closed_run)
    ranking = _build_ranking_data(day=1)
    processor = FakeProcessor(ranking)

    bot = SimpleNamespace()
    cog = RankingCog(bot, processor, storage, kvk_tracker=tracker)

    interaction = make_interaction(channel_id=555, user_id=100)
    attachment = FakeAttachment()

    await cog.submit_ranking(
        interaction=interaction,
        screenshot=attachment,
        day=1,
        stage="prep",
    )

    assert not tracker.record_calls
    interaction.response.send_message.assert_awaited()
    storage_rows = storage.get_user_event_rankings(user_id="100", guild_id="999")
    assert storage_rows == []


@pytest.mark.asyncio
async def test_submit_ranking_allows_admin_when_closed(monkeypatch, storage):
    monkeypatch.setenv("RANKINGS_CHANNEL_ID", "555")
    monkeypatch.setattr(ranking_cog, "is_admin_or_helper", lambda *args, **kwargs: True)

    closed_run = FakeKvkRun(active=False)
    tracker = FakeKvkTracker(closed_run)
    ranking = _build_ranking_data(day=1)
    processor = FakeProcessor(ranking)

    bot = SimpleNamespace()
    cog = RankingCog(bot, processor, storage, kvk_tracker=tracker)

    interaction = make_interaction(channel_id=555, user_id=100, is_admin=True)
    attachment = FakeAttachment()

    await cog.submit_ranking(
        interaction=interaction,
        screenshot=attachment,
        day=1,
        stage="prep",
    )

    assert tracker.record_calls  # admin override allowed



from __future__ import annotations

import os
from asyncio import create_task, sleep
from typing import Optional

from core.engines.performance_analyzer import PerformanceAnalyzer
from core.engines.trajectory_model import compute_trajectory
from core.engines.war_report import WarReportGenerator, war_report_generator
from core.engines.war_stage_detector import war_stage_detector
from core.event_bus import EventBus
from core.supervisor.scheduler import DailyScheduler


class FusionEngine:
    """Coordinates analyzer insights, war reports, and guardian safeguards."""

    def __init__(
        self,
        analyzer: PerformanceAnalyzer,
        war_report: WarReportGenerator,
        sentinel: Optional[object] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.analyzer = analyzer
        self.war_report = war_report
        self.last_stage: dict[str, str] = {}
        self._sentinel = sentinel
        self._event_bus = event_bus

    async def run(self, guild_id, bot=None):
        sentinel = self._sentinel
        if sentinel is None and bot:
            ctx = getattr(bot, "ctx", None)
            sentinel = getattr(ctx, "sentinel", None)
            self._sentinel = sentinel

        bus = self._event_bus
        if bus is None and bot:
            bus = getattr(bot, "event_bus", None)
            self._event_bus = bus

        async def send_daily_report():
            history = self.analyzer.load_history(guild_id)
            if not history:
                return
            report = war_report_generator.generate_daily_report(guild_id, mode="leadership")
            channel_id = int(os.getenv("LEADERSHIP_CHANNEL_ID", "0"))
            if not (bot and channel_id):
                return
            channel = bot.get_channel(channel_id)
            if not channel:
                return
            render_embed = getattr(report, "render_as_embed", None)
            if callable(render_embed):
                await channel.send(embed=render_embed())
            else:
                await channel.send(str(report))

        create_task(DailyScheduler(send_daily_report).start())

        stage_detector = war_stage_detector(self.analyzer, None)

        while True:
            history = self.analyzer.load_history(guild_id)

            stage = stage_detector.detect(guild_id)
            if stage != self.last_stage.get(guild_id):
                if bus:
                    await bus.publish(
                        "war_stage_changed",
                        guild_id=guild_id,
                        old_stage=self.last_stage.get(guild_id),
                        new_stage=stage,
                    )
                self.last_stage[guild_id] = stage

            compute_trajectory(history, war_stage=stage)

            await sleep(300)


fusion_engine = FusionEngine

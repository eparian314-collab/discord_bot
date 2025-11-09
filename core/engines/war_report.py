from __future__ import annotations

import statistics
from typing import Dict, Iterable, List, Tuple

from core.engines.performance_analyzer import performance_analyzer
from core.engines.trajectory_model import compute_trajectory
from core.engines.war_stage_detector import war_stage_detector
from core.utils.humanize import humanize_score, percent, trend_arrow


class WarReportGenerator:
    """Produce guild-level summaries for war performance dashboards."""

    def __init__(self, performance_source):
        self.performance_analyzer = performance_source

    def _summarize_history(
        self, guild_id: str
    ) -> Tuple[Dict[str, List[float]], Dict[str, float], Dict[str, float], Dict[str, float], float]:
        history = self.performance_analyzer.load_history(guild_id)
        if not history:
            return {}, {}, {}, {}, 0.0

        latest_scores = {name: scores[-1] for name, scores in history.items() if scores}
        deltas = {
            name: ((scores[-1] - scores[-2]) / scores[-2] * 100)
            if len(scores) > 1 and scores[-2]
            else 0.0
            for name, scores in history.items()
            if len(scores) > 1
        }
        variances = {
            name: statistics.stdev(scores) if len(scores) > 1 else 0.0
            for name, scores in history.items()
            if scores
        }
        guild_average = statistics.mean(list(latest_scores.values())) if latest_scores else 0.0
        return history, latest_scores, deltas, variances, guild_average

    def generate_daily_report(self, guild_id: str, mode: str = "standard") -> Dict[str, Iterable]:
        history, latest_scores, deltas, variances, guild_average = self._summarize_history(guild_id)
        if not history:
            return {
                "key_drivers": [],
                "strong_momentum": [],
                "needs_support": [],
                "consistency_high": [],
                "consistency_low": [],
                "guild_average": 0.0,
            }

        stage_detector = war_stage_detector(self.performance_analyzer, None)
        stage = stage_detector.detect(guild_id)

        sorted_scores = sorted(latest_scores.items(), key=lambda item: item[1], reverse=True)
        top_n = max(1, int(len(sorted_scores) * 0.1))
        key_drivers = sorted_scores[:top_n]

        strong_momentum = sorted(
            ((name, delta) for name, delta in deltas.items() if delta > 0),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        needs_support = sorted(
            ((name, delta) for name, delta in deltas.items() if delta < 0),
            key=lambda item: item[1],
        )[:3]

        consistency_high = [name for name, _ in sorted(variances.items(), key=lambda item: item[1])[:3]]
        consistency_low = [name for name, _ in sorted(variances.items(), key=lambda item: item[1], reverse=True)[:3]]

        if mode == "leadership":
            sentinel = getattr(self.performance_analyzer, "sentinel", None)
            soften = sentinel.safe_mode if sentinel else False
            trajectory_scores = compute_trajectory(history, soften=soften, war_stage=stage)
            projected_impact = [(name, f"{score:.2f}") for name, score in list(trajectory_scores.items())[:10]]

            sections = {
                "war_stage": stage,
                "key_drivers": [(name, humanize_score(score)) for name, score in key_drivers],
                "strong_momentum": [(name, percent(delta)) for name, delta in strong_momentum],
                "needs_support": [(name, percent(delta)) for name, delta in needs_support],
                "guild_average": humanize_score(guild_average),
                "guild_trend": trend_arrow("forward momentum" if strong_momentum else "steady"),
                "projected_impact": projected_impact,
            }
            focus_map = {
                "early_surge": "momentum",
                "mid_stabilization": "consistency",
                "end_push": "rally",
                "recovery": "support",
            }
            if stage in focus_map:
                sections["focus"] = focus_map[stage]
            return sections

        return {
            "key_drivers": [(name, humanize_score(score)) for name, score in key_drivers],
            "strong_momentum": [(name, percent(delta)) for name, delta in strong_momentum],
            "needs_support": [(name, percent(delta)) for name, delta in needs_support],
            "consistency_high": consistency_high,
            "consistency_low": consistency_low,
            "guild_average": humanize_score(guild_average),
        }


war_report_generator = WarReportGenerator(performance_analyzer)

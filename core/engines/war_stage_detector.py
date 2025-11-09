from __future__ import annotations

from core.engines.trajectory_model import compute_trajectory

__all__ = ["WarStageDetector", "war_stage_detector", "get_stage_weights"]

_STAGE_WEIGHTS = {
    None: {"momentum": 0.6, "stability": 0.3, "output": 0.1},
    "early_surge": {"momentum": 0.7, "stability": 0.2, "output": 0.1},
    "mid_stabilization": {"momentum": 0.4, "stability": 0.4, "output": 0.2},
    "end_push": {"momentum": 0.5, "stability": 0.1, "output": 0.4},
    "recovery": {"momentum": 0.3, "stability": 0.5, "output": 0.2},
}


class WarStageDetector:
    """Lightweight heuristic detector for war stages."""

    def __init__(self, analyzer, trajectory_model=None):
        self.analyzer = analyzer
        self.trajectory_model = trajectory_model

    def detect(self, guild_id: str) -> str:
        """
        Possible return values:
        'prep', 'early_surge', 'mid_stabilization', 'end_push', 'recovery'
        """
        history = self.analyzer.load_history(guild_id)
        if not history:
            return "prep"

        trajectories = compute_trajectory(history)
        g_momentum = sum(trajectories.values()) / max(len(trajectories), 1)
        scores = [series[-1] for series in history.values() if series]
        if not scores:
            return "prep"
        variance = (max(scores) - min(scores)) / max(sum(scores) / len(scores), 1)

        sample_series = next(iter(history.values()), [])
        if len(sample_series) < 3:
            return "prep"
        if g_momentum > 0.10 and variance > 0.20:
            return "early_surge"
        if -0.05 < g_momentum < 0.05:
            return "mid_stabilization"
        if g_momentum > 0.15 and variance < 0.10:
            return "end_push"
        if g_momentum < -0.10:
            return "recovery"
        return "mid_stabilization"

    @staticmethod
    def get_stage_weights(stage: str | None) -> dict[str, float]:
        return get_stage_weights(stage)


def get_stage_weights(stage: str | None) -> dict[str, float]:
    """Return weighting heuristics for the provided war stage."""
    return _STAGE_WEIGHTS.get(stage, _STAGE_WEIGHTS[None]).copy()


def war_stage_detector(analyzer, trajectory_model=None) -> WarStageDetector:
    """Compatibility helper returning a configured detector instance."""
    detector = WarStageDetector(analyzer, trajectory_model)
    return detector


# Backwards compatibility: allow war_stage_detector.get_stage_weights(...)
war_stage_detector.get_stage_weights = get_stage_weights  # type: ignore[attr-defined]

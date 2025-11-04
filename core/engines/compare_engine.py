from .base.engine_plugin import EnginePlugin
from .base.logging_utils import get_logger

class CompareEngine(EnginePlugin):
    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.logger = get_logger("CompareEngine")

    def plugin_name(self) -> str:
        return "compare_engine"

    async def on_engine_ready(self):
        self.logger.info("Compare Engine is ready.")

    def compare_scores(self, user_score, all_scores):
        # Placeholder for comparison logic
        self.logger.info(f"Comparing score {user_score} against {len(all_scores)} other scores.")
        
        # Find peers within ±10% power
        power_range = 0.10
        peers = [
            score for score in all_scores 
            if abs(score['score'] - user_score['score']) / user_score['score'] <= power_range
        ]
        
        # Compute percentile
        rank = user_score['rank']
        total_users = len(all_scores)
        percentile = 100 * (1 - rank / total_users) if total_users > 0 else 0

        return {
            "peers": peers,
            "percentile": percentile
        }

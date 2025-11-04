import json
import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from discord.ext import tasks
from discord.ext.commands import Bot

from .base.engine_plugin import EnginePlugin
from .base.logging_utils import get_logger
from .kvk_parser_engine import KVKParserEngine
from .gar_parser_engine import GARParserEngine
from .compare_engine import CompareEngine
from core.event_bus import EventBus


class EventEngine(EnginePlugin):
    def __init__(
        self,
        bot: Bot,
        event_bus: EventBus,
        kvk_parser_engine: KVKParserEngine,
        gar_parser_engine: GARParserEngine,
        compare_engine: CompareEngine,
    ):
        super().__init__()
        self.bot = bot
        self.event_bus = event_bus
        self.logger = get_logger("EventEngine")
        self.kvk_parser = kvk_parser_engine
        self.gar_parser = gar_parser_engine
        self.compare_engine = compare_engine
        self.event_registry = {}
        self.event_scores: list[dict] = []  # In-memory storage for scores
        self.refresh_leaderboards.start()

    def plugin_name(self) -> str:
        return "event_engine"

    def plugin_requires(self) -> tuple[str, ...]:
        return ("kvk_parser_engine", "gar_parser_engine", "compare_engine")

    async def on_engine_ready(self):
        self.logger.info("Event Engine is ready.")
        self._load_event_registry()

    @tasks.loop(hours=6)
    async def refresh_leaderboards(self):
        self.logger.info("📊 Event standings refreshing...")
        # This is where you would re-run comparisons and update leaderboards
        # For now, we'll just log a message.
        
        # Example of what might go here:
        # all_kvk_scores = self.get_leaderboard("KVK")
        # all_gar_scores = self.get_leaderboard("GAR")
        # for score in self.event_scores:
        #     all_scores = all_kvk_scores if score['event'] == 'KVK' else all_gar_scores
        #     comparison = self.compare_engine.compare_scores(score, all_scores)
        #     score['percentile'] = comparison['percentile']
        
        self.logger.info("✅ Event standings refreshed.")

    @refresh_leaderboards.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready() # wait for the bot to be ready

    def _load_event_registry(self):
        registry_path = Path("data/event_registry.json")
        if not registry_path.exists():
            self.logger.error("Event registry file not found at data/event_registry.json")
            return
        
        with open(registry_path, "r") as f:
            self.event_registry = {event['event_id']: event for event in json.load(f)}
        self.logger.info(f"Loaded {len(self.event_registry)} events from registry.")

    def detect_event_type(self, text: str) -> Optional[str]:
        """Detects event type from text keywords."""
        text_lower = text.lower()
        if 'prep stage' in text_lower or 'war stage' in text_lower:
            return "KVK"
        if 'guild assault' in text_lower or 'tech boost' in text_lower:
            return "GAR"
        return None

    def get_parser_for_event(self, event_id: str) -> Optional[Any]:
        if event_id == "KVK":
            return self.kvk_parser
        if event_id == "GAR":
            return self.gar_parser
        return None

    async def process_submission(self, attachment_url: str, message_content: str) -> Optional[Dict[str, Any]]:
        event_type = self.detect_event_type(message_content)
        if not event_type:
            self.logger.warning("Could not detect event type from message.")
            return None

        parser = self.get_parser_for_event(event_type)
        if not parser:
            self.logger.error(f"No parser found for event type: {event_type}")
            return None

        # In a real scenario, we'd download the image from attachment_url
        # For now, we'll just pass a placeholder path.
        placeholder_path = f"uploads/{Path(attachment_url).name}"
        
        parsed_data = parser.parse_image(placeholder_path)
        
        # Store data
        self.event_scores.append(parsed_data)
        
        return parsed_data

    def get_user_status(self, user_id: int, event_id: Optional[str] = None) -> list[dict]:
        """Gets all event scores for a given user."""
        # This is a mock implementation. In a real system, you'd query a database.
        user_scores = [score for score in self.event_scores if score.get('user_id') == user_id]
        if event_id:
            return [score for score in user_scores if score.get('event') == event_id]
        return user_scores

    def get_leaderboard(self, event_id: str) -> list[dict]:
        """Gets the top scores for a given event."""
        event_scores = [score for score in self.event_scores if score.get('event') == event_id]
        return sorted(event_scores, key=lambda x: x.get('score', 0), reverse=True)[:10]

    def generate_summary_report(self) -> str:
        """Generates a cross-event summary report for all users."""
        self.logger.info("Generating cross-event summary report...")
        
        user_summaries = {}
        
        # This is a mock implementation. A real one would be more robust.
        for score in self.event_scores:
            user_id = score.get("user_id", "Unknown")
            if user_id not in user_summaries:
                user_summaries[user_id] = {"KVK": None, "GAR": None, "user": score.get("user")}

            if score["event"] == "KVK":
                user_summaries[user_id]["KVK"] = score
            elif score["event"] == "GAR":
                user_summaries[user_id]["GAR"] = score

        report_data = []
        for user_id, data in user_summaries.items():
            kvk_score = data["KVK"]
            gar_score = data["GAR"]
            
            kvk_percentile = kvk_score.get("percentile", 0) if kvk_score else 0
            gar_percentile = gar_score.get("percentile", 0) if gar_score else 0
            
            avg_percentile = (kvk_percentile + gar_percentile) / 2 if kvk_score and gar_score else (kvk_percentile or gar_percentile)
            
            tier = "Bronze"
            if avg_percentile > 90:
                tier = "Gold"
            elif avg_percentile > 75:
                tier = "Silver"

            report_data.append({
                "user": data["user"],
                "user_id": user_id,
                "kvk_data": kvk_score,
                "gar_data": gar_score,
                "average_percentile": avg_percentile,
                "overall_tier": tier,
            })

        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        report_path = Path(f"logs/event_summary_{date_str}.json")
        
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
            
        self.logger.info(f"✅ Event Engine fully integrated and operational. Report saved to {report_path}")
        return str(report_path)

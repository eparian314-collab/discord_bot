import json
import os
import threading
from statistics import mean

PERF_PATH = os.path.join(os.path.dirname(__file__), '../../storage/performance_history.json')
PERF_PATH = os.path.abspath(PERF_PATH)

class PerformanceAnalyzer:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(PERF_PATH):
            with open(PERF_PATH, 'r', encoding='utf-8') as f:
                try:
                    self.data = json.load(f)
                except Exception:
                    self.data = {}
        else:
            self.data = {}

    def save(self):
        with self.lock:
            with open(PERF_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)

    def record(self, guild_id, player_name, score):
        with self.lock:
            gid = str(guild_id)
            if gid not in self.data:
                self.data[gid] = {}
            if player_name not in self.data[gid]:
                self.data[gid][player_name] = []
            self.data[gid][player_name].append(int(score))
            self.data[gid][player_name] = self.data[gid][player_name][-50:]
            self.save()

    def load_history(self, guild_id):
        gid = str(guild_id)
        return self.data.get(gid, {})

    def save_history(self, guild_id, history):
        with self.lock:
            self.data[str(guild_id)] = history
            self.save()

    def analyze(self, guild_id, player_name, latest_score):
        history = self.load_history(guild_id).get(player_name, [])
        if not history:
            print("Compiling momentum profile…")
            return {
                "change_from_last": 0.0,
                "change_from_average": 0.0,
                "trend": "steady",
                "rank_shift_estimate": 0,
                "narrative": "Performance baseline established."
            }
        last_score = history[-2] if len(history) > 1 else history[-1]
        avg_score = mean(history) if history else latest_score
        change_from_last = ((latest_score - last_score) / last_score * 100) if last_score else 0.0
        change_from_average = ((latest_score - avg_score) / avg_score * 100) if avg_score else 0.0
        # Strategic, supportive trend detection
        if len(history) > 2:
            if latest_score > history[-2] > history[-3]:
                trend = "forward momentum"
                narrative = "Noted upward performance trend."
            elif latest_score < history[-2] < history[-3]:
                trend = "needs support"
                narrative = "Performance variance trending downward - monitor next cycle."
            else:
                trend = "steady"
                narrative = "Consistent output detected."
        else:
            trend = "steady"
            narrative = "Consistent output detected."
        rank_shift_estimate = int(change_from_last // 10)
        from core.utils.humanize import percent, trend_arrow
        return {
            "change_from_last": percent(change_from_last),
            "change_from_average": percent(change_from_average),
            "trend": trend,
            "trend_arrow": trend_arrow(trend),
            "rank_shift_estimate": rank_shift_estimate,
            "narrative": narrative
        }

performance_analyzer = PerformanceAnalyzer()

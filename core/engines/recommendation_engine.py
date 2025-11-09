from statistics import mean
from typing import Dict, List
from core.engines.trajectory_model import compute_trajectory
from core.engines.war_stage_detector import WarStageDetector
from core.utils.humanize import trend_arrow

class RecommendationEngine:
    def __init__(self, analyzer, trajectory_model, stage_detector):
        self.analyzer = analyzer
        self.trajectory_model = trajectory_model
        self.stage_detector = stage_detector

    def recommend(self, guild_id) -> Dict[str, List[str]]:
        """Generate strategic recommendations based on trajectory analysis and war stage."""
        history = self.analyzer.load_history(guild_id)
        stage = self.stage_detector.detect(guild_id)
        trajectories = compute_trajectory(history, war_stage=stage)

        # Sort by trajectory score
        sorted_players = sorted(trajectories.items(), key=lambda x: x[1], reverse=True)

        top = sorted_players[:5]
        bottom = sorted_players[-5:] if len(sorted_players) > 5 else sorted_players[-3:]

        stage_context = {
            'early_surge': {
                'push_label': 'Primary Momentum Drivers',
                'support_label': 'Ramp-Up Support Targets'
            },
            'mid_stabilization': {
                'push_label': 'Reliable Anchors',
                'support_label': 'Stabilization Focus'
            },
            'end_push': {
                'push_label': 'Final Rally Leaders',
                'support_label': 'Resource Reallocation'
            },
            'recovery': {
                'push_label': 'Sustained Performance',
                'support_label': 'Recovery Priority'
            },
            'prep': {
                'push_label': 'Early Indicators',
                'support_label': 'Setup Assistance'
            }
        }.get(stage, {
            'push_label': 'Strategic Focus',
            'support_label': 'Support Focus'
        })

        recommendations = {
            'stage': stage,
            'push': [(p, score) for p, score in top],
            'support': [(p, score) for p, score in bottom],
            'context': stage_context
        }

        return recommendations

    def render_recommendations(self, guild_name: str, recommendations: Dict, safe_mode: bool = False) -> dict:
        """Format recommendations for Discord embed display."""
        stage = recommendations['stage']
        context = recommendations['context']
        
        description = []
        if safe_mode:
            description.append("⚠️ System Stability Reduced - Recommendations Conservative")
        
        description.append(f"**Current War Stage:** {stage.replace('_', ' ').title()}")
        
        # Add stage-specific sections with neutral tone
        fields = [
            {
                "name": context['push_label'],
                "value": "\n".join(f"• {name} {trend_arrow('rising')} - {score:.2f}" 
                                 for name, score in recommendations['push']),
                "inline": False
            },
            {
                "name": context['support_label'],
                "value": "\n".join(f"• {name} {trend_arrow('steady')} - {score:.2f}"
                                 for name, score in recommendations['support']),
                "inline": False
            }
        ]

        return {
            "title": f"🎯 Strategic Recommendations - {guild_name}",
            "description": "\n".join(description),
            "fields": fields,
            "color": 0x3498db  # Professional blue
        }

# Global instance
recommendation_engine = RecommendationEngine
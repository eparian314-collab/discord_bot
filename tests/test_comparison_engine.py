"""
Tests for the Comparison Engine.
"""
import pytest
from unittest.mock import MagicMock

# Assume this engine will be created
# from discord_bot.core.engines.comparison_engine import ComparisonEngine

pytestmark = pytest.mark.asyncio

# --- Mock Engine ---

class ComparisonEngine:
    def __init__(self, storage_engine):
        self.storage = storage_engine

    def compute_percentile(self, target_power: int, target_score: int, cohort: list) -> float:
        """
        Computes the percentile of a player's score within a cohort of similar power.
        """
        if not cohort:
            return 0.0

        # Filter cohort to find players with higher scores
        players_with_better_scores = [
            p for p in cohort if p['score'] > target_score
        ]

        num_better = len(players_with_better_scores)
        total_in_cohort = len(cohort)

        # Percentile formula: (Number of people you are better than / Total people) * 100
        percentile = ((total_in_cohort - num_better) / total_in_cohort) * 100
        return percentile

    def get_badge(self, percentile: float) -> str:
        if percentile >= 95:
            return "Top 5%"
        elif percentile >= 90:
            return "Top 10%"
        elif percentile >= 75:
            return "Top 25%"
        else:
            return "Participant"

# --- Fixtures ---

@pytest.fixture
def mock_storage():
    return MagicMock()

@pytest.fixture
def comparison_engine(mock_storage):
    return ComparisonEngine(storage_engine=mock_storage)

# --- Test Cases ---

async def test_percentile_computation(comparison_engine: ComparisonEngine):
    """
    STAGE 6/test_06: Ensure accurate percentile calculation.
    """
    # 1. Insert 10 mock players
    mock_cohort = [
        {'power': 25_000_000, 'score': 1_000_000},
        {'power': 26_000_000, 'score': 2_000_000},
        {'power': 27_000_000, 'score': 3_000_000},
        {'power': 28_000_000, 'score': 4_000_000},
        {'power': 29_000_000, 'score': 5_000_000},
        {'power': 30_000_000, 'score': 6_000_000},
        {'power': 31_000_000, 'score': 7_000_000}, # Our target player
        {'power': 32_000_000, 'score': 8_000_000},
        {'power': 33_000_000, 'score': 9_000_000},
        {'power': 34_000_000, 'score': 10_000_000},
    ]

    target_power = 31_000_000
    target_score = 7_000_000

    # 2. Run compute_percentile
    # In this cohort of 10, our player is better than 6 others.
    # (10 - 3) / 10 = 0.7 or 70th percentile.
    percentile = comparison_engine.compute_percentile(target_power, target_score, mock_cohort)

    # 3. Confirm percentile
    assert 69.9 < percentile < 70.1
    print(f"\nPlayer with score {target_score:,} is at the {percentile:.1f}th percentile.")

async def test_badge_assignment(comparison_engine: ComparisonEngine):
    """
    STAGE 6/test_06: Verify badge assignment based on percentile.
    """
    assert comparison_engine.get_badge(96.0) == "Top 5%"
    assert comparison_engine.get_badge(92.0) == "Top 10%"
    assert comparison_engine.get_badge(80.0) == "Top 25%"
    assert comparison_engine.get_badge(74.9) == "Participant"

async def test_edge_case_few_players(comparison_engine: ComparisonEngine):
    """
    STAGE 6/test_06: Test with a small cohort.
    """
    # 4. Edge case: few players
    small_cohort = [
        {'power': 30_000_000, 'score': 6_000_000},
        {'power': 32_000_000, 'score': 8_000_000},
    ]
    
    target_power = 31_000_000
    target_score = 7_000_000

    # The logic for expanding the cohort would be in a higher-level function
    # that calls the storage engine. Here we just test the calculation.
    # Our player is better than 1 of the 2. (2 - 1) / 2 = 50th percentile.
    percentile = comparison_engine.compute_percentile(target_power, target_score, small_cohort + [{'power': target_power, 'score': target_score}])
    
    # The cohort is now 3 people. Our player is better than 1. (3-1)/3 = 66.6th percentile
    assert 66.5 < percentile < 66.7
    print(f"\nIn a small cohort, percentile is {percentile:.1f}th.")

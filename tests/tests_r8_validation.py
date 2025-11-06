"""
Tests for R8 Validation Layer
"""

import pytest
from datetime import datetime, timezone, timedelta
from discord_bot.core.engines.validators import (
    score_confidence,
    phase_confidence,
    day_confidence,
    server_confidence,
    guild_confidence,
    name_confidence,
    overall_confidence,
    sanitize_and_validate
)
from discord_bot.core.engines.profile_cache import (
    get_player,
    upsert_player,
    prefer_cached_when_low_confidence,
    is_name_lock_active
)
from discord_bot.core.engines.confirm_flow import (
    build_soft_confirm_payload,
    build_disambiguation_payload,
    apply_user_corrections
)


class TestValidators:
    """Test confidence scoring functions."""
    
    def test_score_confidence_high(self):
        """Test high confidence score extraction."""
        raw_text = "Points: 1,250,000"
        parsed = 1250000
        conf = score_confidence(raw_text, parsed)
        assert conf >= 0.9, f"Expected high confidence, got {conf}"
    
    def test_score_confidence_low_out_of_bounds(self):
        """Test out of bounds score gets 0 confidence."""
        raw_text = "Points: 3000000000"
        parsed = 3000000000
        conf = score_confidence(raw_text, parsed, bounds=(1, 2_000_000_000))
        assert conf == 0.0
    
    def test_phase_confidence_prep_highlighted(self):
        """Test prep phase with highlight marker."""
        ui_flags = {
            'prep_highlighted': True,
            'war_highlighted': False,
            'has_day_selector': True
        }
        conf = phase_confidence(ui_flags)
        assert conf >= 0.9
    
    def test_phase_confidence_conflicting(self):
        """Test conflicting phase signals."""
        ui_flags = {
            'prep_highlighted': True,
            'war_highlighted': True,
            'has_day_selector': False
        }
        conf = phase_confidence(ui_flags)
        assert conf < 0.5
    
    def test_day_confidence_single_highlight(self):
        """Test single day highlighted."""
        ui_flags = {
            'day_1_highlighted': False,
            'day_2_highlighted': False,
            'day_3_highlighted': True,
            'day_4_highlighted': False,
            'day_5_highlighted': False,
            'overall_highlighted': False
        }
        conf = day_confidence(ui_flags)
        assert conf >= 0.9
    
    def test_day_confidence_multiple_highlights(self):
        """Test ambiguous multiple highlights."""
        ui_flags = {
            'day_1_highlighted': True,
            'day_2_highlighted': True,
            'day_3_highlighted': False
        }
        conf = day_confidence(ui_flags)
        assert conf < 0.5
    
    def test_server_confidence_valid(self):
        """Test valid server ID extraction."""
        text = "#10435 [TAO] Mars"
        server_id, conf = server_confidence(text)
        assert server_id == 10435
        assert conf >= 0.7
    
    def test_server_confidence_no_match(self):
        """Test no server ID found."""
        text = "No server ID here"
        server_id, conf = server_confidence(text)
        assert server_id == 0
        assert conf == 0.0
    
    def test_guild_confidence_clear_match(self):
        """Test clear guild tag extraction."""
        text = "#10435 [TAO] Mars"
        guild, conf = guild_confidence(text, cached_guild=None)
        assert guild == "TAO"
        assert conf >= 0.7
    
    def test_guild_confidence_cached_match(self):
        """Test cached guild boosts confidence."""
        text = "#10435 [TAO] Mars"
        guild, conf = guild_confidence(text, cached_guild="TAO")
        assert guild == "TAO"
        assert conf >= 0.9
    
    def test_guild_confidence_no_match_use_cache(self):
        """Test fallback to cached guild."""
        text = "No guild tag here"
        guild, conf = guild_confidence(text, cached_guild="TAO")
        assert guild == "TAO"
        assert conf == 0.7
    
    def test_name_confidence_valid(self):
        """Test valid name extraction."""
        text = "#10435 [TAO] MarsWarrior"
        name, conf = name_confidence(text, cached_name=None)
        assert name == "MarsWarrior"
        assert conf >= 0.6
    
    def test_name_confidence_cached_match(self):
        """Test cached name match boosts confidence."""
        text = "#10435 [TAO] MarsWarrior"
        name, conf = name_confidence(text, cached_name="MarsWarrior")
        assert name == "MarsWarrior"
        assert conf >= 0.9
    
    def test_overall_confidence_calculation(self):
        """Test weighted overall confidence."""
        field_confs = {
            'score': 0.95,
            'phase': 0.90,
            'day': 0.85,
            'server_id': 0.80,
            'guild': 0.75,
            'player_name': 0.70
        }
        overall = overall_confidence(field_confs)
        # Should be weighted average, score has highest weight
        assert 0.8 <= overall <= 0.9
    
    def test_sanitize_valid_data(self):
        """Test validation of good data."""
        parsed = {
            'score': 1250000,
            'server_id': 10435,
            'guild': 'TAO',
            'player_name': 'Mars',
            'phase': 'prep',
            'day': 3
        }
        is_valid, errors = sanitize_and_validate(parsed)
        assert is_valid
        assert len(errors) == 0
    
    def test_sanitize_invalid_score(self):
        """Test validation catches invalid score."""
        parsed = {
            'score': -100,
            'server_id': 10435,
            'guild': 'TAO',
            'player_name': 'Mars',
            'phase': 'prep',
            'day': 3
        }
        is_valid, errors = sanitize_and_validate(parsed)
        assert not is_valid
        assert any('score' in err.lower() for err in errors)
    
    def test_sanitize_invalid_phase(self):
        """Test validation catches invalid phase."""
        parsed = {
            'score': 1250000,
            'server_id': 10435,
            'guild': 'TAO',
            'player_name': 'Mars',
            'phase': 'invalid',
            'day': 3
        }
        is_valid, errors = sanitize_and_validate(parsed)
        assert not is_valid
        assert any('phase' in err.lower() for err in errors)
    
    def test_sanitize_war_with_day(self):
        """Test validation catches war phase with day value."""
        parsed = {
            'score': 1250000,
            'server_id': 10435,
            'guild': 'TAO',
            'player_name': 'Mars',
            'phase': 'war',
            'day': 3
        }
        is_valid, errors = sanitize_and_validate(parsed)
        assert not is_valid
        assert any('war' in err.lower() and 'day' in err.lower() for err in errors)


class TestProfileCache:
    """Test player profile caching."""
    
    @pytest.fixture
    def db_conn(self, tmp_path):
        """Create temporary database connection."""
        import sqlite3
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()
    
    def test_upsert_new_player(self, db_conn):
        """Test creating new player profile."""
        upsert_player(db_conn, "user123", 10435, "TAO", "Mars")
        
        player = get_player(db_conn, "user123")
        assert player is not None
        assert player['guild'] == "TAO"
        assert player['player_name'] == "Mars"
        assert player['server_id'] == 10435
    
    def test_upsert_update_player(self, db_conn):
        """Test updating existing player profile."""
        upsert_player(db_conn, "user123", 10435, "TAO", "Mars")
        upsert_player(db_conn, "user123", 10435, "GOD", "MarsWarrior")
        
        player = get_player(db_conn, "user123")
        assert player['guild'] == "GOD"
        assert player['player_name'] == "MarsWarrior"
    
    def test_get_nonexistent_player(self, db_conn):
        """Test getting player that doesn't exist."""
        player = get_player(db_conn, "nonexistent")
        assert player is None
    
    def test_prefer_cached_guild_low_confidence(self, db_conn):
        """Test using cached guild when confidence low."""
        upsert_player(db_conn, "user123", 10435, "TAO", "Mars")
        cached = get_player(db_conn, "user123")
        
        parsed = {
            'guild': 'T4O',  # OCR error
            'player_name': 'Mars',
            'score': 1250000
        }
        confidence_map = {
            'guild': 0.60  # Low confidence
        }
        
        result = prefer_cached_when_low_confidence(parsed, cached, confidence_map)
        assert result['guild'] == "TAO"  # Used cached
        assert result['_guild_from_cache'] is True
    
    def test_prefer_cached_name_differs(self, db_conn):
        """Test handling when name differs from cache."""
        upsert_player(db_conn, "user123", 10435, "TAO", "Mars")
        cached = get_player(db_conn, "user123")
        
        parsed = {
            'guild': 'TAO',
            'player_name': 'MarsWarrior',  # Different name
            'score': 1250000
        }
        confidence_map = {
            'player_name': 0.85  # Medium confidence
        }
        
        result = prefer_cached_when_low_confidence(parsed, cached, confidence_map)
        assert result['_name_differs'] is True
        assert result['_cached_name'] == "Mars"
    
    def test_name_lock_active(self, db_conn):
        """Test name lock prevents override."""
        # Lock name for 24 hours
        locked_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        upsert_player(
            db_conn, "user123", 10435, "TAO", "Mars",
            lock_updates={'name_locked': True, 'name_locked_until': locked_until}
        )
        
        cached = get_player(db_conn, "user123")
        assert is_name_lock_active(cached)
        
        # Attempt to change name with low confidence
        parsed = {
            'guild': 'TAO',
            'player_name': 'NewName',
            'score': 1250000
        }
        confidence_map = {
            'player_name': 0.90
        }
        
        result = prefer_cached_when_low_confidence(parsed, cached, confidence_map)
        assert result['player_name'] == "Mars"  # Kept locked name
        assert result['_name_locked'] is True


class TestConfirmFlow:
    """Test confirmation UI payloads."""
    
    def test_soft_confirm_payload(self):
        """Test soft confirm payload structure."""
        parsed = {
            'phase': 'prep',
            'day': 3,
            'score': 1250000,
            'guild': 'TAO',
            'player_name': 'Mars',
            'server_id': 10435
        }
        confidences = {
            'overall': 0.97,
            'score': 0.95,
            'phase': 0.98
        }
        
        payload = build_soft_confirm_payload(parsed, confidences)
        
        assert payload['type'] == 'soft_confirm'
        assert 'embed' in payload
        assert 'components' in payload
        assert payload['timeout'] == 120
        assert len(payload['components']) == 3  # Confirm, Edit, Cancel
    
    def test_disambiguation_payload(self):
        """Test disambiguation payload structure."""
        parsed = {
            'phase': 'prep',
            'day': 3,
            'score': 1250000,
            'guild': 'T4O',  # Uncertain
            'player_name': 'Mars',
            'server_id': 10435
        }
        confidences = {
            'overall': 0.85,
            'guild': 0.60  # Low
        }
        candidates = {
            'guild': ['TAO', 'T4O', 'TAO']
        }
        
        payload = build_disambiguation_payload(parsed, candidates, confidences)
        
        assert payload['type'] == 'disambiguation'
        assert 'embed' in payload
        assert 'components' in payload
        assert 'modal_hint' in payload
        assert 'prefill' in payload['modal_hint']
    
    def test_apply_corrections(self):
        """Test applying user corrections."""
        parsed = {
            'score': 1000000,
            'guild': 'T4O',
            'player_name': 'Mar5',
            'server_id': 10435
        }
        user_input = {
            'score': '1,250,000',
            'guild': 'tao',
            'player_name': 'Mars'
        }
        
        result = apply_user_corrections(parsed, user_input)
        
        assert result['score'] == 1250000  # Comma removed, converted to int
        assert result['guild'] == 'TAO'  # Uppercased
        assert result['player_name'] == 'Mars'  # Corrected
        assert result['_manually_verified'] is True


class TestIntegration:
    """Integration tests for complete validation flow."""
    
    def test_high_confidence_auto_accept(self):
        """Test high confidence data auto-accepts."""
        parsed = {
            'score': 1250000,
            'server_id': 10435,
            'guild': 'TAO',
            'player_name': 'Mars',
            'phase': 'prep',
            'day': 3
        }
        
        # High confidence scores
        confidence_map = {
            'score': 0.98,
            'phase': 0.99,
            'day': 0.98,
            'server_id': 0.95,
            'guild': 0.96,
            'player_name': 0.97
        }
        
        overall = overall_confidence(confidence_map)
        assert overall >= 0.99, "Should auto-accept with high confidence"
        
        is_valid, errors = sanitize_and_validate(parsed)
        assert is_valid, f"Valid data should pass: {errors}"
    
    def test_low_confidence_requires_disambiguation(self):
        """Test low confidence triggers disambiguation."""
        parsed = {
            'score': 1250000,
            'server_id': 10435,
            'guild': 'T4O',  # OCR error
            'player_name': 'Mar5',  # OCR error
            'phase': 'prep',
            'day': 3
        }
        
        confidence_map = {
            'score': 0.95,
            'phase': 0.90,
            'day': 0.85,
            'server_id': 0.80,
            'guild': 0.60,  # Low
            'player_name': 0.65  # Low
        }
        
        overall = overall_confidence(confidence_map)
        assert overall < 0.95, "Should trigger disambiguation"
        
        # Payload should be built
        payload = build_disambiguation_payload(parsed, {}, confidence_map)
        assert 'modal_hint' in payload
    
    def test_overwrite_behavior_unchanged(self):
        """Test that validation doesn't break overwrite logic."""
        # Same (phase, day) key should overwrite
        submission1 = {
            'user_id': 'user123',
            'phase': 'prep',
            'day': 3,
            'score': 1000000
        }
        submission2 = {
            'user_id': 'user123',
            'phase': 'prep',
            'day': 3,
            'score': 1250000  # Higher score
        }
        
        # Both should pass validation
        for sub in [submission1, submission2]:
            sub.update({
                'server_id': 10435,
                'guild': 'TAO',
                'player_name': 'Mars'
            })
            is_valid, errors = sanitize_and_validate(sub)
            assert is_valid
        
        # Key is (user_id, phase, day) - same key should overwrite
        assert submission1['user_id'] == submission2['user_id']
        assert submission1['phase'] == submission2['phase']
        assert submission1['day'] == submission2['day']

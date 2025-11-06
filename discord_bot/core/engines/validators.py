"""
KVK Ranking Validation Layer
Confidence scoring and sanity checks for OCR-parsed ranking data.
"""

import re
from typing import Dict, Any, Optional, Tuple, List


def score_confidence(
    raw_text: str,
    parsed_int: int,
    bounds: Tuple[int, int] = (1, 2_000_000_000)
) -> float:
    """
    Calculate confidence for score extraction.
    
    Args:
        raw_text: Raw OCR text containing score
        parsed_int: Extracted score value
        bounds: (min, max) valid score range
    
    Returns:
        Confidence (0.0-1.0)
    """
    confidence = 0.0
    
    # Bounds check
    if not (bounds[0] <= parsed_int <= bounds[1]):
        return 0.0
    
    # Start with base confidence
    confidence = 0.5
    
    # Pattern match for "Points:" or "Score:" prefix
    score_pattern = r'(?:points?|score)\s*:?\s*([\d,]+)'
    match = re.search(score_pattern, raw_text, re.IGNORECASE)
    if match:
        confidence += 0.3
        
        # Check if extracted digits match pattern
        digits_in_text = match.group(1).replace(',', '')
        if digits_in_text == str(parsed_int):
            confidence += 0.2
    
    # Reasonable digit count (5-10 digits typical)
    digit_count = len(str(parsed_int))
    if 5 <= digit_count <= 10:
        confidence += 0.1
    elif digit_count < 5:
        confidence -= 0.1
    
    return min(1.0, max(0.0, confidence))


def phase_confidence(ui_flags: Dict[str, Any]) -> float:
    """
    Calculate confidence for phase detection.
    
    Args:
        ui_flags: Dict with keys like 'prep_highlighted', 'war_highlighted', 'has_day_selector'
    
    Returns:
        Confidence (0.0-1.0)
    """
    confidence = 0.5
    
    prep_highlighted = ui_flags.get('prep_highlighted', False)
    war_highlighted = ui_flags.get('war_highlighted', False)
    has_day_selector = ui_flags.get('has_day_selector', False)
    
    # Explicit highlight markers
    if prep_highlighted and not war_highlighted:
        confidence = 0.95
    elif war_highlighted and not prep_highlighted:
        confidence = 0.95
    elif prep_highlighted and war_highlighted:
        # Conflicting signals
        confidence = 0.4
    
    # Day selector presence (strong prep indicator)
    if has_day_selector:
        confidence = max(confidence, 0.85)
    
    # If no clear signals, low confidence
    if not any([prep_highlighted, war_highlighted, has_day_selector]):
        confidence = 0.3
    
    return min(1.0, max(0.0, confidence))


def day_confidence(ui_flags: Dict[str, Any]) -> float:
    """
    Calculate confidence for day detection (prep only).
    
    Args:
        ui_flags: Dict with keys like 'day_1_highlighted', 'day_2_highlighted', etc., 'overall_highlighted'
    
    Returns:
        Confidence (0.0-1.0)
    """
    confidence = 0.5
    
    # Count highlighted days
    highlighted_days = sum(1 for k, v in ui_flags.items() 
                          if k.startswith('day_') and k.endswith('_highlighted') and v)
    
    overall_highlighted = ui_flags.get('overall_highlighted', False)
    
    # Single day highlighted = high confidence
    if highlighted_days == 1:
        confidence = 0.95
    elif overall_highlighted and highlighted_days == 0:
        confidence = 0.95
    elif highlighted_days > 1:
        # Multiple days highlighted = ambiguous
        confidence = 0.4
    elif highlighted_days == 0 and not overall_highlighted:
        # No day indicators
        confidence = 0.3
    
    return min(1.0, max(0.0, confidence))


def server_confidence(text: str) -> Tuple[int, float]:
    """
    Extract and validate server_id from text.
    
    Args:
        text: Raw text containing "#12345" format
    
    Returns:
        (server_id, confidence)
    """
    # Pattern: #<digits>
    pattern = r'#(\d{3,6})\b'
    matches = re.findall(pattern, text)
    
    if not matches:
        return 0, 0.0
    
    # Take first match
    server_id = int(matches[0])
    confidence = 0.5
    
    # 4-5 digit server IDs are most common
    digit_count = len(matches[0])
    if 4 <= digit_count <= 5:
        confidence += 0.3
    elif digit_count == 3 or digit_count == 6:
        confidence += 0.1
    
    # Only one match = more confident
    if len(matches) == 1:
        confidence += 0.2
    else:
        confidence -= 0.1
    
    return server_id, min(1.0, max(0.0, confidence))


def guild_confidence(
    text: str,
    cached_guild: Optional[str] = None
) -> Tuple[str, float]:
    """
    Extract and validate guild tag from text.
    
    Args:
        text: Raw text containing "[TAG]" format
        cached_guild: Previously known guild for this user
    
    Returns:
        (guild_tag, confidence)
    """
    # Pattern: [LETTERS]
    pattern = r'\[([A-Z]{2,6})\]'
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    if not matches:
        # No match, use cached if available
        if cached_guild:
            return cached_guild, 0.7  # Medium confidence from cache
        return "", 0.0
    
    # Take first match, uppercase
    guild_tag = matches[0].upper()
    confidence = 0.6
    
    # 3-letter tags are most common
    if len(guild_tag) == 3:
        confidence += 0.2
    elif len(guild_tag) in [2, 4]:
        confidence += 0.1
    
    # Only one match = more confident
    if len(matches) == 1:
        confidence += 0.2
    else:
        confidence -= 0.1
    
    # Matches cached guild = high confidence
    if cached_guild and guild_tag == cached_guild:
        confidence = min(0.98, confidence + 0.2)
    
    return guild_tag, min(1.0, max(0.0, confidence))


def name_confidence(
    text: str,
    cached_name: Optional[str] = None
) -> Tuple[str, float]:
    """
    Extract and validate player name from text.
    
    Args:
        text: Raw text after guild tag
        cached_name: Previously known name for this user
    
    Returns:
        (player_name, confidence)
    """
    # Pattern: After [GUILD] comes the name
    pattern = r'\[[A-Z]{2,6}\]\s+([^\n]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    
    if not match:
        if cached_name:
            return cached_name, 0.75
        return "", 0.0
    
    player_name = match.group(1).strip()
    confidence = 0.6
    
    # Reasonable length (3-20 chars)
    if 3 <= len(player_name) <= 20:
        confidence += 0.2
    elif len(player_name) < 3:
        confidence -= 0.2
    
    # No special OCR artifacts
    if not re.search(r'[|\\/_@#$%^&*()]', player_name):
        confidence += 0.1
    else:
        confidence -= 0.2
    
    # Matches cached name = high confidence
    if cached_name and player_name.lower() == cached_name.lower():
        confidence = min(0.98, confidence + 0.2)
    elif cached_name and player_name.lower() != cached_name.lower():
        # Name differs from cache = lower confidence
        confidence = min(0.75, confidence)
    
    return player_name, min(1.0, max(0.0, confidence))


def overall_confidence(
    field_confidences: Dict[str, float],
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Calculate weighted overall confidence.
    
    Args:
        field_confidences: Dict mapping field name to confidence (0.0-1.0)
        weights: Optional custom weights (defaults to CONFIDENCE_WEIGHTS)
    
    Returns:
        Overall confidence (0.0-1.0)
    """
    if weights is None:
        weights = {
            'score': 0.35,
            'phase': 0.20,
            'day': 0.15,
            'server_id': 0.10,
            'guild': 0.10,
            'player_name': 0.10
        }
    
    total = 0.0
    weight_sum = 0.0
    
    for field, weight in weights.items():
        if field in field_confidences:
            total += field_confidences[field] * weight
            weight_sum += weight
    
    if weight_sum == 0:
        return 0.0
    
    return total / weight_sum


def sanitize_and_validate(parsed: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Perform sanity checks on parsed data.
    
    Args:
        parsed: Parsed ranking data dict
    
    Returns:
        (is_valid, error_reasons)
    """
    errors = []
    
    # Score validation
    score = parsed.get('score', 0)
    if not isinstance(score, int) or score <= 0:
        errors.append("Score must be a positive integer")
    elif score > 2_000_000_000:
        errors.append("Score exceeds maximum (2B)")
    
    # Server ID validation
    server_id = parsed.get('server_id', 0)
    if not isinstance(server_id, int):
        errors.append("Server ID must be an integer")
    elif not (100 <= server_id <= 999999):
        errors.append("Server ID must be 3-6 digits")
    
    # Guild validation
    guild = parsed.get('guild', '')
    if guild and not re.match(r'^[A-Z]{2,6}$', guild):
        errors.append("Guild tag must be 2-6 uppercase letters")
    
    # Player name validation
    player_name = parsed.get('player_name', '')
    if not player_name or len(player_name) < 2:
        errors.append("Player name must be at least 2 characters")
    elif len(player_name) > 30:
        errors.append("Player name too long (max 30 chars)")
    
    # Phase validation
    phase = parsed.get('phase')
    if phase not in ['prep', 'war']:
        errors.append(f"Invalid phase: {phase}")
    
    # Day validation
    day = parsed.get('day')
    if phase == 'prep':
        if day is None:
            errors.append("Prep phase requires a day value")
        elif day != 'overall' and not isinstance(day, int):
            errors.append("Day must be integer (1-5) or 'overall'")
        elif isinstance(day, int) and not (1 <= day <= 5):
            errors.append("Day must be 1-5 or 'overall'")
    elif phase == 'war':
        if day is not None:
            errors.append("War phase must have day=None")
    
    return len(errors) == 0, errors

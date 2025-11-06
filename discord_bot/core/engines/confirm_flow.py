"""
KVK Ranking Confirmation Flow
Discord-agnostic payload builders for soft confirm and disambiguation UI.
"""

from typing import Dict, Any, List, Optional


def build_soft_confirm_payload(
    parsed: Dict[str, Any],
    confidences: Dict[str, float]
) -> Dict[str, Any]:
    """
    Build payload for soft confirmation (95-98.99% confidence).
    
    Shows parsed values and asks for one-click confirmation.
    
    Args:
        parsed: Parsed ranking data
        confidences: Field confidence scores
    
    Returns:
        Dict with embed and component structure
    """
    phase_label = "Prep" if parsed['phase'] == 'prep' else "War"
    day_label = ""
    if parsed['phase'] == 'prep':
        if parsed['day'] == 'overall':
            day_label = " • Overall"
        else:
            day_label = f" • Day {parsed['day']}"
    
    # Build confidence indicators
    overall_conf = confidences.get('overall', 0.95)
    conf_pct = int(overall_conf * 100)
    
    fields = [
        {
            'name': '🏷️ Phase & Day',
            'value': f"{phase_label}{day_label}",
            'inline': True
        },
        {
            'name': '⭐ Score',
            'value': f"{parsed['score']:,} points",
            'inline': True
        },
        {
            'name': '🏰 Guild',
            'value': f"[{parsed['guild']}]" if parsed.get('guild') else '*Unknown*',
            'inline': True
        },
        {
            'name': '👤 Player',
            'value': parsed.get('player_name', '*Unknown*'),
            'inline': True
        },
        {
            'name': '🖥️ Server',
            'value': f"#{parsed.get('server_id', '???')}",
            'inline': True
        },
        {
            'name': '🎯 Confidence',
            'value': f"{conf_pct}%",
            'inline': True
        }
    ]
    
    # Add warnings for cached values
    warnings = []
    if parsed.get('_guild_from_cache'):
        warnings.append("🔄 Guild auto-filled from profile")
    if parsed.get('_name_from_cache'):
        warnings.append("🔄 Name auto-filled from profile")
    
    if warnings:
        fields.append({
            'name': '⚠️ Note',
            'value': '\n'.join(warnings),
            'inline': False
        })
    
    return {
        'type': 'soft_confirm',
        'embed': {
            'title': '✅ Confirm Ranking Submission',
            'description': 'Please verify the extracted data below is correct.',
            'color': 0xf39c12,  # Orange
            'fields': fields
        },
        'components': [
            {
                'type': 'button',
                'label': 'Confirm',
                'style': 'success',
                'custom_id': 'confirm_ranking'
            },
            {
                'type': 'button',
                'label': 'Edit',
                'style': 'secondary',
                'custom_id': 'edit_ranking'
            },
            {
                'type': 'button',
                'label': 'Cancel',
                'style': 'danger',
                'custom_id': 'cancel_ranking'
            }
        ],
        'timeout': 120
    }


def build_disambiguation_payload(
    parsed: Dict[str, Any],
    candidates: Dict[str, List[Any]],
    confidences: Dict[str, float]
) -> Dict[str, Any]:
    """
    Build payload for disambiguation UI (<95% confidence).
    
    Shows multiple candidates for uncertain fields.
    
    Args:
        parsed: Parsed ranking data
        candidates: Dict mapping field name to list of candidate values
        confidences: Field confidence scores
    
    Returns:
        Dict with embed and component structure
    """
    overall_conf = confidences.get('overall', 0.5)
    conf_pct = int(overall_conf * 100)
    
    # Identify uncertain fields
    uncertain_fields = []
    for field, conf in confidences.items():
        if field != 'overall' and conf < 0.95:
            uncertain_fields.append(field)
    
    fields = [
        {
            'name': '⚠️ Low Confidence Detected',
            'value': f"Overall confidence: {conf_pct}%\nPlease review and correct the fields below.",
            'inline': False
        }
    ]
    
    # Show current values with confidence
    for field in ['score', 'guild', 'player_name', 'server_id']:
        if field in parsed:
            conf = confidences.get(field, 0.0)
            icon = '❌' if conf < 0.5 else '⚠️' if conf < 0.95 else '✅'
            
            if field == 'score':
                value_str = f"{parsed[field]:,} points ({icon} {int(conf*100)}%)"
            elif field == 'guild':
                value_str = f"[{parsed[field]}] ({icon} {int(conf*100)}%)" if parsed[field] else f"*Unknown* ({icon} {int(conf*100)}%)"
            elif field == 'server_id':
                value_str = f"#{parsed[field]} ({icon} {int(conf*100)}%)"
            else:
                value_str = f"{parsed[field]} ({icon} {int(conf*100)}%)"
            
            fields.append({
                'name': field.replace('_', ' ').title(),
                'value': value_str,
                'inline': True
            })
    
    # Show candidates if available
    if candidates:
        candidate_text = []
        for field, options in candidates.items():
            if options and len(options) > 1:
                candidate_text.append(f"**{field}**: {', '.join(str(o) for o in options[:3])}")
        
        if candidate_text:
            fields.append({
                'name': '💡 Detected Alternatives',
                'value': '\n'.join(candidate_text),
                'inline': False
            })
    
    return {
        'type': 'disambiguation',
        'embed': {
            'title': '🔍 Review Required',
            'description': 'OCR had difficulty reading some values. Please verify or correct them.',
            'color': 0xe67e22,  # Orange-red
            'fields': fields
        },
        'components': [
            {
                'type': 'button',
                'label': 'Edit Values',
                'style': 'primary',
                'custom_id': 'open_correction_modal'
            },
            {
                'type': 'button',
                'label': 'Use As-Is',
                'style': 'secondary',
                'custom_id': 'accept_uncertain'
            },
            {
                'type': 'button',
                'label': 'Cancel',
                'style': 'danger',
                'custom_id': 'cancel_ranking'
            }
        ],
        'modal_hint': {
            'prefill': {
                'guild': parsed.get('guild', ''),
                'player_name': parsed.get('player_name', ''),
                'score': str(parsed.get('score', '')),
                'server_id': str(parsed.get('server_id', ''))
            }
        },
        'timeout': 120
    }


def apply_user_corrections(
    parsed: Dict[str, Any],
    user_input: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply user-provided corrections to parsed data.
    
    Args:
        parsed: Original parsed ranking data
        user_input: User corrections from modal
    
    Returns:
        Updated parsed dict with corrections applied
    """
    result = parsed.copy()
    
    # Apply guild correction
    if 'guild' in user_input and user_input['guild']:
        result['guild'] = user_input['guild'].strip().upper()
        result['_user_corrected_guild'] = True
    
    # Apply player name correction
    if 'player_name' in user_input and user_input['player_name']:
        result['player_name'] = user_input['player_name'].strip()
        result['_user_corrected_name'] = True
    
    # Apply score correction
    if 'score' in user_input:
        try:
            # Remove commas and convert to int
            score_str = str(user_input['score']).replace(',', '').strip()
            result['score'] = int(score_str)
            result['_user_corrected_score'] = True
        except (ValueError, TypeError):
            pass  # Keep original if conversion fails
    
    # Apply server_id correction
    if 'server_id' in user_input:
        try:
            server_str = str(user_input['server_id']).replace('#', '').strip()
            result['server_id'] = int(server_str)
            result['_user_corrected_server'] = True
        except (ValueError, TypeError):
            pass
    
    # Mark as manually verified
    result['_manually_verified'] = True
    
    return result


def build_name_change_prompt(
    parsed_name: str,
    cached_name: str
) -> Dict[str, Any]:
    """
    Build prompt asking user if they changed their in-game name.
    
    Args:
        parsed_name: Name detected in current screenshot
        cached_name: Name from player profile
    
    Returns:
        Dict with embed and component structure
    """
    return {
        'type': 'name_change_prompt',
        'embed': {
            'title': '🔄 Name Change Detected',
            'description': f"Your in-game name appears to have changed.\n\n**Previous**: {cached_name}\n**Current**: {parsed_name}\n\nDid you change your name?",
            'color': 0x3498db,  # Blue
            'fields': []
        },
        'components': [
            {
                'type': 'button',
                'label': 'Yes, Update Name',
                'style': 'success',
                'custom_id': 'confirm_name_change'
            },
            {
                'type': 'button',
                'label': 'No, Keep Old Name',
                'style': 'secondary',
                'custom_id': 'keep_old_name'
            }
        ],
        'timeout': 60
    }

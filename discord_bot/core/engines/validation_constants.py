"""
KVK Ranking Validation Constants
Tunable parameters for confidence thresholds and validation rules.
"""

# ═══════════════════════════════════════════════════════════════════════
# CONFIDENCE SCORING WEIGHTS
# ═══════════════════════════════════════════════════════════════════════

CONFIDENCE_WEIGHTS = {
    'score': 0.35,        # Highest weight - most critical field
    'phase': 0.20,        # Phase detection is important
    'day': 0.15,          # Day detection for prep phase
    'server_id': 0.10,    # Server ID for kingdom filtering
    'guild': 0.10,        # Guild tag
    'player_name': 0.10   # Player name (can be cached/corrected)
}

# ═══════════════════════════════════════════════════════════════════════
# CONFIDENCE THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════

# Auto-accept threshold: >= 0.99 proceeds directly to save
AUTO_ACCEPT_THRESHOLD = 0.99

# Soft confirm range: 0.95-0.989 shows one-click confirmation
SOFT_CONFIRM_MIN = 0.95
SOFT_CONFIRM_MAX = 0.989

# Disambiguation threshold: < 0.95 shows correction modal
DISAMBIGUATION_THRESHOLD = 0.95

# Individual field thresholds for fallback to cache
GUILD_CACHE_THRESHOLD = 0.95      # Use cached guild if confidence < this
NAME_CACHE_THRESHOLD = 0.98       # Use cached name if confidence < this

# ═══════════════════════════════════════════════════════════════════════
# SCORE VALIDATION BOUNDS
# ═══════════════════════════════════════════════════════════════════════

SCORE_MIN = 1                     # Minimum valid score
SCORE_MAX = 2_000_000_000         # Maximum valid score (2 billion)

# Daily score typical ranges (for anomaly detection)
PREP_DAY_TYPICAL_MIN = 100_000
PREP_DAY_TYPICAL_MAX = 50_000_000

PREP_OVERALL_TYPICAL_MIN = 500_000
PREP_OVERALL_TYPICAL_MAX = 200_000_000

WAR_TYPICAL_MIN = 1_000_000
WAR_TYPICAL_MAX = 500_000_000

# ═══════════════════════════════════════════════════════════════════════
# SERVER ID VALIDATION
# ═══════════════════════════════════════════════════════════════════════

SERVER_ID_MIN_DIGITS = 3
SERVER_ID_MAX_DIGITS = 6
SERVER_ID_TYPICAL_DIGITS = 5      # Most common

# ═══════════════════════════════════════════════════════════════════════
# GUILD TAG VALIDATION
# ═══════════════════════════════════════════════════════════════════════

GUILD_MIN_LENGTH = 2
GUILD_MAX_LENGTH = 6
GUILD_TYPICAL_LENGTH = 3          # Most common

# ═══════════════════════════════════════════════════════════════════════
# PLAYER NAME VALIDATION
# ═══════════════════════════════════════════════════════════════════════

PLAYER_NAME_MIN_LENGTH = 2
PLAYER_NAME_MAX_LENGTH = 30

# Characters that suggest OCR errors
OCR_ERROR_CHARS = r'[|\\/_@#$%^&*()]'

# ═══════════════════════════════════════════════════════════════════════
# INTERACTION TIMEOUTS
# ═══════════════════════════════════════════════════════════════════════

SOFT_CONFIRM_TIMEOUT_SECONDS = 120      # 2 minutes to confirm
DISAMBIGUATION_TIMEOUT_SECONDS = 120    # 2 minutes to correct
NAME_CHANGE_PROMPT_TIMEOUT_SECONDS = 60 # 1 minute to answer name change

# ═══════════════════════════════════════════════════════════════════════
# NAME LOCKING
# ═══════════════════════════════════════════════════════════════════════

NAME_LOCK_COOLDOWN_HOURS = 24    # Hours to lock name after manual change

# ═══════════════════════════════════════════════════════════════════════
# OCR PATTERN CONFIDENCE BOOSTS
# ═══════════════════════════════════════════════════════════════════════

# Confidence boost when patterns match expected format
PATTERN_MATCH_BOOST = 0.2
CACHE_MATCH_BOOST = 0.2
SINGLE_CANDIDATE_BOOST = 0.2

# Confidence penalty for ambiguous/multiple candidates
MULTIPLE_CANDIDATES_PENALTY = 0.1
OCR_ERROR_PENALTY = 0.2

# ═══════════════════════════════════════════════════════════════════════
# UI/UX CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

# Embed colors (decimal)
COLOR_AUTO_ACCEPT = 0x2ecc71      # Green
COLOR_SOFT_CONFIRM = 0xf39c12     # Orange
COLOR_DISAMBIGUATION = 0xe67e22   # Orange-red
COLOR_ERROR = 0xe74c3c            # Red
COLOR_NAME_CHANGE = 0x3498db      # Blue

# Emoji indicators
EMOJI_HIGH_CONFIDENCE = '✅'
EMOJI_MEDIUM_CONFIDENCE = '⚠️'
EMOJI_LOW_CONFIDENCE = '❌'
EMOJI_CACHED = '🔄'
EMOJI_LOCKED = '🔒'

# ═══════════════════════════════════════════════════════════════════════
# VALIDATION MESSAGES
# ═══════════════════════════════════════════════════════════════════════

MSG_AUTO_ACCEPT = "High confidence detected - submission accepted automatically."
MSG_SOFT_CONFIRM = "Please confirm the detected values are correct."
MSG_DISAMBIGUATION = "OCR had difficulty reading some values. Please verify or correct them."
MSG_TIMEOUT = "⏱️ Confirmation timed out. Please submit again."
MSG_CANCELLED = "❌ Submission cancelled."
MSG_VALIDATION_FAILED = "❌ Validation failed. Please check your screenshot and try again."

# ═══════════════════════════════════════════════════════════════════════
# FEATURE FLAGS
# ═══════════════════════════════════════════════════════════════════════

ENABLE_AUTO_ACCEPT = True         # Allow auto-accept for high confidence
ENABLE_GUILD_CACHE = True         # Use cached guild for low confidence
ENABLE_NAME_LOCK = True           # Lock name after manual confirmation
ENABLE_DISAMBIGUATION = True      # Show correction modal for low confidence

# Debug mode - log all confidence scores
DEBUG_LOG_CONFIDENCE = False

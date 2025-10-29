
"""
READING GUIDE
-------------
Purpose:
- This module provides comprehensive, platform-specific normalization rules for Discord text cleanup.
- It is the lowest layer in the language context stack: only pure functions, dataclasses, and rule definitions.
- All logic is AI-optional and deterministic; no external dependencies or downstream imports.
- Upstream modules (tokenizers, pipelines, engines) should inject or compose these rules as needed.

Usage:
- Import and use the provided rule packs and normalization helpers in higher-level modules.
- Extend or override rules by injecting additional functions or patterns upstream.

STRICT MODULARITY:
- Do NOT import managers, pipelines, or services.
- Only use standard library, typing, and dataclasses.
- Keep all functions minimal, composable, and testable.
"""

import re
import unicodedata
from typing import Callable, List, Pattern, Dict

# Type alias for a normalization rule: a pure function that takes and returns a string
NormalizationRule = Callable[[str], str]

# --- Discord-specific normalization rules ---

def remove_discord_markdown(text: str) -> str:
	"""
	Removes common Discord markdown (bold, italics, underline, strikethrough, code blocks).
	Pure function, no side effects.
	"""
	# Remove **bold**, __underline__, *italics*, ~~strikethrough~~, `inline`, ```code blocks```
	text = re.sub(r"(\*\*|__|\*|~~|`{1,3})(.*?)\1", r"\2", text)
	return text

def remove_discord_mentions(text: str) -> str:
	"""
	Removes Discord user, channel, and role mentions.
	"""
	text = re.sub(r"<@[!&]?[0-9]+>", "", text)  # User/role mentions
	text = re.sub(r"<#[0-9]+>", "", text)       # Channel mentions
	text = re.sub(r"<@everyone>", "", text)
	text = re.sub(r"<@here>", "", text)
	return text

def remove_custom_emojis(text: str) -> str:
	"""
	Removes Discord custom emoji tags.
	"""
	text = re.sub(r"<a?:\w+:\d+>", "", text)
	return text

def protect_mass_mentions(text: str) -> str:
	"""
	Inserts zero-width space after @everyone and @here to prevent accidental pings.
	"""
	text = re.sub(r"@(everyone|here)", r"@\u200b\1", text, flags=re.IGNORECASE)
	return text

def protect_generic_at(text: str) -> str:
	"""
	Inserts zero-width space after any remaining '@' to reduce chance of mention.
	"""
	# This will also affect email addresses; keep it because translations shouldn't trigger pings.
	text = re.sub(r"@", "@\u200b", text)
	return text

def collapse_backticks(text: str) -> str:
	"""
	Collapse long sequences of backticks to exactly three (for code blocks).
	"""
	text = re.sub(r"`{3,}", "```", text)
	return text

def remove_zero_width(text: str) -> str:
	"""
	Remove zero-width spaces and similar Unicode chars.
	"""
	return re.sub(r"[\u200B-\u200F\uFEFF]", "", text)

def replace_smart_quotes(text: str) -> str:
	"""
	Replace common smart quotes and dashes with ASCII equivalents.
	"""
	replacements = {
		"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
		"\u2013": "-", "\u2014": "-", "\u2026": "...",
		""": '"', """: '"', "'": "'", "'": "'"
	}
	return text.translate(str.maketrans(replacements))

def strip_control_chars(text: str) -> str:
	"""
	Remove control characters except common whitespace (tab/newline).
	"""
	return "".join(ch for ch in text if ch == "\t" or ch == "\n" or unicodedata.category(ch)[0] != "C")

def collapse_whitespace(text: str) -> str:
	"""
	Collapses multiple spaces/tabs/newlines into a single space.
	"""
	return re.sub(r"\s+", " ", text).strip()

def unicode_normalize(text: str) -> str:
	"""
	Unicode normalization (NFKC).
	"""
	return unicodedata.normalize("NFKC", text)

def normalize_ellipses(text: str) -> str:
	"""
	Normalize ellipses to three dots.
	"""
	return re.sub(r"\.{2,}", "...", text)

def normalize_punctuation_spacing(text: str) -> str:
	"""
	Normalize space before punctuation (e.g., "hello  ," -> "hello,").
	"""
	return re.sub(r"\s+([,;:.!?])", r"\1", text)

def trim_leading_trailing_whitespace(text: str) -> str:
	"""
	Trim leading and trailing whitespace.
	"""
	return text.strip()

# --- General normalization rule pack (ordered) ---

GENERAL_RULES: List[NormalizationRule] = [
	unicode_normalize,
	replace_smart_quotes,
	normalize_ellipses,
	remove_zero_width,
	strip_control_chars,
	remove_discord_markdown,
	remove_discord_mentions,
	remove_custom_emojis,
	protect_mass_mentions,
	protect_generic_at,
	collapse_backticks,
	normalize_punctuation_spacing,
	collapse_whitespace,
	trim_leading_trailing_whitespace,
]

def apply_general_rules(text: str, rules: List[NormalizationRule] = None) -> str:
	"""
	Applies all general normalization rules in order.
	"""
	rules = rules or GENERAL_RULES
	for rule in rules:
		text = rule(text)
	return text

# --- Example: context-specific rule packs (for future extension) ---

DISCORD_MESSAGE_RULES: List[NormalizationRule] = [
	unicode_normalize,
	replace_smart_quotes,
	normalize_ellipses,
	remove_zero_width,
	strip_control_chars,
	remove_discord_markdown,
	remove_discord_mentions,
	remove_custom_emojis,
	protect_mass_mentions,
	protect_generic_at,
	collapse_backticks,
	normalize_punctuation_spacing,
	collapse_whitespace,
	trim_leading_trailing_whitespace,
]

# --- Example usage (for maintainers): ---
# cleaned = apply_general_rules("Hello **world**! <@123456789> <:smile:987654321> @everyone @here")

# TODO: Add more platform-specific rules as Discord evolves.
# TODO: Upstream modules should inject additional rules for context-specific normalization.
# TODO: Add unit tests for edge cases (emoji-only, code blocks, mass-mention protection).

# End of file.
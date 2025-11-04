from __future__ import annotations
from typing import Dict

EN_US_DEFAULTS: Dict[str, str] = {
    "greeting": "Hello {user}!",
    "farewell": "Goodbye!",
    "error_general": "Something went wrong.",
    "error_translate_failed": "Could not translate that.",
    "loading": "Please wait…",
    "ok": "OK",
    "nr4_choose_language_title": "Choose your language",
    "nr4_assign_role_confirm": "Set {locale} as your language role for future translations?",
    "nr4_role_assigned": "Language preference saved as {locale}.",
    "nr4_role_skipped": "Okay, not assigning {locale}.",
    "ui_select_language": "Select a language…",
    "ui_search_languages": "Search languages",
    "ui_translate_to_my_language": "Translate to My Language",
    "ui_translate_specific": "Translate to Specific Language…",
    "help_translate_tip": "Use /translate <code> to translate a message or text publicly.",
    "admin_loading": "Admin engine is loading or not ready yet.",
    "plugins_title": "Plugins",
    "diagnostics_title": "Diagnostics",
}

ES_ES_SEEDS: Dict[str, str] = {
    "greeting": "¡Hola {user}!",
    "farewell": "¡Adiós!",
    "error_general": "Algo salió mal.",
    "nr4_choose_language_title": "Elige tu idioma",
    "ui_select_language": "Selecciona un idioma…",
}

JA_JP_SEEDS: Dict[str, str] = {
    "greeting": "こんにちは {user}！",
    "farewell": "さようなら！",
    "error_general": "問題が発生しました。",
    "nr4_choose_language_title": "言語を選択",
    "ui_select_language": "言語を選択…",
}

BUILTIN_LOCALE_SEEDS = {
    "en-US": EN_US_DEFAULTS,
    "es-ES": ES_ES_SEEDS,
    "ja-JP": JA_JP_SEEDS,
}



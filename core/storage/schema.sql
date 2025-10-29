﻿-- schema.sql
-- ------------------------------
-- Core Database Schema
-- Used by storage_engine.py to initialize structured storage
-- ------------------------------
-- Each CREATE TABLE IF NOT EXISTS statement is modular:
-- add, remove, or migrate tables without breaking old data
-- ------------------------------

-- 1️⃣ General key-value storage (system-level data)
CREATE TABLE IF NOT EXISTS storage (
    key TEXT PRIMARY KEY,
    value TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2️⃣ User profiles and preferences
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    preferred_language TEXT DEFAULT 'en',
    timezone TEXT DEFAULT 'UTC',
    last_seen DATETIME,
    metadata TEXT
);

-- 3️⃣ Guild / Server configuration
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    prefix TEXT DEFAULT '/',
    default_language TEXT DEFAULT 'en',
    system_channel TEXT,
    auto_translate BOOLEAN DEFAULT 0
);

-- 4️⃣ Translation history (for caching and analytics)
CREATE TABLE IF NOT EXISTS translation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    source_lang TEXT,
    target_lang TEXT,
    input_text TEXT,
    translated_text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5️⃣ Error logs (used by error_engine)
CREATE TABLE IF NOT EXISTS error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_type TEXT,
    message TEXT,
    traceback TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    context TEXT
);

-- 6️⃣ Caching metadata (optional for cache manager)
CREATE TABLE IF NOT EXISTS cache_records (
    key TEXT PRIMARY KEY,
    value TEXT,
    expires_at DATETIME,
    last_access DATETIME
);

-- 7️⃣ System diagnostics or heartbeats (future observability)
CREATE TABLE IF NOT EXISTS system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT,
    status TEXT,
    last_checked DATETIME DEFAULT CURRENT_TIMESTAMP,
    details TEXT
);

-- 8️⃣ Language role mapping (used by context/translation engines)
CREATE TABLE IF NOT EXISTS language_roles (
    guild_id TEXT,
    role_id TEXT,
    language_code TEXT,
    PRIMARY KEY (guild_id, role_id)
);
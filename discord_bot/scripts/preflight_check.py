#!/usr/bin/env python3
"""
Preflight checks before launching HippoBot.
This script performs comprehensive validation to ensure the bot can start safely.
"""
import os
import sys
import sqlite3
import json
import logging
from typing import Dict, Optional
from pathlib import Path

# Setup logging
LOG_FILE = 'logs/preflight.log'
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

class PreflightChecker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self._env_cache: Optional[Dict[str, str]] = None

    def log_error(self, message):
        logging.error(message)
        self.errors.append(message)
        
    def log_warning(self, message):
        logging.warning(message)
        self.warnings.append(message)
        
    def log_info(self, message):
        logging.info(message)
        
    def _load_env(self) -> Dict[str, str]:
        """Parse the .env file into a dictionary."""
        if self._env_cache is not None:
            return self._env_cache

        env_path = Path('.env')
        data: Dict[str, str] = {}
        if not env_path.exists():
            self._env_cache = data
            return data

        for raw_line in env_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip()

        self._env_cache = data
        return data

    def check_environment_file(self):
        """Check if .env file exists and has required variables."""
        self.log_info("Checking environment file...")
        if not os.path.exists('.env'):
            self.log_error(".env file not found")
            return False
            
        required_vars = ['DISCORD_TOKEN']
        missing_vars = []
        
        with open('.env', 'r') as f:
            env_content = f.read()
            for var in required_vars:
                if var not in env_content:
                    missing_vars.append(var)
                    
        if missing_vars:
            self.log_error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
            
        self.log_info("Environment file check passed")
        # Reset cache so downstream checks read the latest file
        self._env_cache = None
        return True

    def check_channel_configuration(self):
        """Ensure channel-related environment configuration is consistent."""
        self.log_info("Checking channel configuration...")
        env = self._load_env()

        rankings_channel = env.get('RANKINGS_CHANNEL_ID', '').strip()
        if not rankings_channel:
            self.log_error("RANKINGS_CHANNEL_ID is not configured in .env")
            return False

        try:
            int(rankings_channel)
        except ValueError:
            self.log_error("RANKINGS_CHANNEL_ID must be a numeric Discord channel ID")
            return False

        allowed_channels_raw = env.get('ALLOWED_CHANNELS', '')
        allowed_channels = {
            token.strip()
            for token in allowed_channels_raw.replace(';', ',').split(',')
            if token.strip()
        }

        if allowed_channels and rankings_channel not in allowed_channels:
            self.log_error(
                "RANKINGS_CHANNEL_ID must be included in ALLOWED_CHANNELS to permit submissions"
            )
            return False

        bot_channels_raw = env.get('BOT_CHANNEL_ID', '')
        bot_channels = [
            token.strip()
            for token in bot_channels_raw.replace(';', ',').split(',')
            if token.strip()
        ]
        invalid_bot_channels = [
            token for token in bot_channels
            if not token.isdigit()
        ]
        if invalid_bot_channels:
            self.log_error(
                f"BOT_CHANNEL_ID contains non-numeric values: {', '.join(invalid_bot_channels)}"
            )
            return False

        if not allowed_channels:
            self.log_warning(
                "ALLOWED_CHANNELS is empty; bot commands will be accepted in any channel"
            )

        self.log_info("Channel configuration check passed")
        return True
        
    def check_databases(self):
        """Check if databases exist and are accessible."""
        self.log_info("Checking databases...")
        databases = [
            'data/game_data.db',
            'data/event_rankings.db'
        ]
        
        all_ok = True
        for db_path in databases:
            if not os.path.exists(db_path):
                self.log_warning(f"Database {db_path} does not exist (will be auto-created)")
                continue
                
            try:
                conn = sqlite3.connect(db_path)
                conn.execute('SELECT 1')
                conn.close()
                self.log_info(f"Database {db_path} is accessible")
            except Exception as e:
                self.log_error(f"Database {db_path} check failed: {e}")
                all_ok = False
                
        return all_ok
        
    def check_required_directories(self):
        """Check and create required directories."""
        self.log_info("Checking required directories...")
        required_dirs = [
            'data',
            'logs',
            'core',
            'cogs',
            'games',
            'integrations',
            'language_context'
        ]
        
        for dir_name in required_dirs:
            if not os.path.exists(dir_name):
                self.log_error(f"Required directory missing: {dir_name}")
                return False
            self.log_info(f"Directory {dir_name} exists")
            
        return True
        
    def check_language_map(self):
        """Check if language map exists and is valid JSON."""
        self.log_info("Checking language map...")
        lang_map_path = 'language_context/language_map.json'
        
        if not os.path.exists(lang_map_path):
            self.log_error(f"Language map not found at {lang_map_path}")
            return False
            
        try:
            with open(lang_map_path, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    self.log_error("Language map is not a valid dictionary")
                    return False
            self.log_info("Language map is valid")
            return True
        except json.JSONDecodeError as e:
            self.log_error(f"Language map JSON is invalid: {e}")
            return False
            
    def check_python_version(self):
        """Check if Python version is compatible."""
        self.log_info("Checking Python version...")
        min_version = (3, 8)
        current_version = sys.version_info[:2]
        
        if current_version < min_version:
            self.log_error(f"Python {min_version[0]}.{min_version[1]}+ required, found {current_version[0]}.{current_version[1]}")
            return False
            
        self.log_info(f"Python version {current_version[0]}.{current_version[1]} is compatible")
        return True
        
    def check_import_sanity(self):
        """Test critical imports to catch dependency issues."""
        self.log_info("Checking critical imports...")
        critical_imports = [
            ('discord', 'discord.py'),
            ('aiohttp', 'aiohttp'),
            ('sqlite3', 'sqlite3 (built-in)'),
        ]
        
        all_ok = True
        for module_name, package_name in critical_imports:
            try:
                __import__(module_name)
                self.log_info(f"Import check passed: {package_name}")
            except ImportError as e:
                self.log_error(f"Failed to import {package_name}: {e}")
                all_ok = False
                
        return all_ok
        
    def check_disk_space(self):
        """Check if sufficient disk space is available."""
        self.log_info("Checking disk space...")
        try:
            import shutil
            stat = shutil.disk_usage('.')
            free_gb = stat.free / (1024**3)
            
            if free_gb < 1.0:
                self.log_error(f"Low disk space: {free_gb:.2f} GB free")
                return False
            elif free_gb < 5.0:
                self.log_warning(f"Disk space is low: {free_gb:.2f} GB free")
                
            self.log_info(f"Disk space check passed: {free_gb:.2f} GB free")
            return True
        except Exception as e:
            self.log_warning(f"Could not check disk space: {e}")
            return True  # Don't fail on this check
            
    def run_all_checks(self):
        """Run all preflight checks."""
        self.log_info("=" * 60)
        self.log_info("Starting preflight checks...")
        self.log_info("=" * 60)
        
        checks = [
            ("Python Version", self.check_python_version),
            ("Environment File", self.check_environment_file),
            ("Channel Configuration", self.check_channel_configuration),
            ("Required Directories", self.check_required_directories),
            ("Databases", self.check_databases),
            ("Language Map", self.check_language_map),
            ("Critical Imports", self.check_import_sanity),
            ("Disk Space", self.check_disk_space),
        ]
        
        for check_name, check_func in checks:
            self.log_info(f"Running check: {check_name}")
            try:
                result = check_func()
                if not result:
                    self.log_error(f"Check failed: {check_name}")
            except Exception as e:
                self.log_error(f"Check crashed: {check_name} - {e}")
                self.errors.append(f"{check_name}: {e}")
                
        self.log_info("=" * 60)
        self.log_info("Preflight checks complete")
        self.log_info(f"Errors: {len(self.errors)}, Warnings: {len(self.warnings)}")
        self.log_info("=" * 60)
        
        return len(self.errors) == 0

def main():
    """Main entry point."""
    checker = PreflightChecker()
    
    # Change to script's directory
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    
    success = checker.run_all_checks()
    
    # Print summary to stdout
    print("=" * 60)
    print("PREFLIGHT CHECK SUMMARY")
    print("=" * 60)
    
    if checker.errors:
        print(f"\n❌ ERRORS ({len(checker.errors)}):")
        for error in checker.errors:
            print(f"  - {error}")
            
    if checker.warnings:
        print(f"\n⚠️  WARNINGS ({len(checker.warnings)}):")
        for warning in checker.warnings:
            print(f"  - {warning}")
            
    if success:
        print("\n✅ All preflight checks passed!")
        print(f"Detailed log: {LOG_FILE}")
        sys.exit(0)
    else:
        print("\n❌ Preflight checks failed!")
        print(f"Detailed log: {LOG_FILE}")
        sys.exit(1)

if __name__ == '__main__':
    main()

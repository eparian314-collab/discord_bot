"""
Secure configuration management for Discord bot.

Provides secure handling of:
- Environment variables
- API keys and secrets
- Configuration validation
- Secret masking and auditing
"""
from __future__ import annotations

import os
import re
from typing import Dict, Any, Optional, Set, List, Union
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConfigSecret:
    """Represents a secret configuration value."""
    name: str
    value: str
    masked_value: str
    is_required: bool = True
    validation_pattern: Optional[str] = None
    
    def __post_init__(self):
        if not self.masked_value:
            self.masked_value = self._mask_secret(self.value)
    
    @staticmethod
    def _mask_secret(value: str) -> str:
        """Mask a secret value for logging."""
        if not value:
            return "***EMPTY***"
        if len(value) <= 8:
            return "***"
        return f"{value[:3]}***{value[-3:]}"


class SecureConfigManager:
    """
    Secure configuration management system.
    
    Features:
    - Secret masking for logs
    - Environment variable validation
    - Required configuration checking
    - Configuration change auditing
    - Default value management
    """
    
    def __init__(self):
        self.secrets: Dict[str, ConfigSecret] = {}
        self.config_values: Dict[str, Any] = {}
        self.required_keys: Set[str] = set()
        self.validation_patterns: Dict[str, str] = {}
        self.default_values: Dict[str, Any] = {}
        
        self.setup_default_config()
    
    def setup_default_config(self):
        """Setup default configuration schema."""
        # Required secrets
        self.add_secret_config("DISCORD_TOKEN", required=True, 
                             validation_pattern=r'^[A-Za-z0-9\-_.]+$')
        
        # Optional but recommended secrets
        self.add_secret_config("DEEPL_API_KEY", required=False,
                             validation_pattern=r'^[a-f0-9\-]+$')
        self.add_secret_config("MY_MEMORY_API_KEY", required=False,
                             validation_pattern=r'^[a-f0-9]+$')
        self.add_secret_config("OPENAI_API_KEY", required=False,
                             validation_pattern=r'^sk-[A-Za-z0-9]+$')
        
        # Configuration values with defaults
        self.add_config("OWNER_IDS", default="", validation_pattern=r'^[\d,\s]*$')
        self.add_config("TEST_GUILDS", default="", validation_pattern=r'^[\d,\s]*$')
        self.add_config("BOT_CHANNEL_ID", default="", validation_pattern=r'^\d*$')
        self.add_config("ALLOWED_CHANNELS", default="", validation_pattern=r'^[\d,\s]*$')
        self.add_config("HELPER_ROLE_ID", default="", validation_pattern=r'^\d*$')
        
        # Security settings
        self.add_config("ENABLE_RATE_LIMITING", default="true", validation_pattern=r'^(true|false)$')
        self.add_config("ENABLE_INPUT_VALIDATION", default="true", validation_pattern=r'^(true|false)$')
        self.add_config("ENABLE_SECURITY_LOGGING", default="true", validation_pattern=r'^(true|false)$')
        self.add_config("ENABLE_SANDBOXING", default="true", validation_pattern=r'^(true|false)$')
        
        # Performance settings
        self.add_config("MAX_MEMORY_MB", default="256", validation_pattern=r'^\d+$')
        self.add_config("MAX_EXECUTION_TIME", default="30", validation_pattern=r'^\d+$')
        self.add_config("LOG_LEVEL", default="INFO", validation_pattern=r'^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$')
    
    def add_secret_config(self, name: str, required: bool = False, validation_pattern: Optional[str] = None):
        """Add a secret configuration item."""
        self.required_keys.add(name) if required else None
        if validation_pattern:
            self.validation_patterns[name] = validation_pattern
    
    def add_config(self, name: str, default: Any = None, validation_pattern: Optional[str] = None):
        """Add a regular configuration item."""
        if default is not None:
            self.default_values[name] = default
        if validation_pattern:
            self.validation_patterns[name] = validation_pattern
    
    def load_configuration(self) -> Dict[str, Any]:
        """Load and validate all configuration."""
        config = {}
        errors = []
        
        # Load all environment variables
        for key in os.environ:
            config[key] = os.environ[key]
        
        # Add default values for missing keys
        for key, default_value in self.default_values.items():
            if key not in config:
                config[key] = default_value
        
        # Validate required keys
        missing_required = self.required_keys - set(config.keys())
        if missing_required:
            errors.append(f"Missing required configuration: {', '.join(missing_required)}")
        
        # Validate patterns
        for key, pattern in self.validation_patterns.items():
            if key in config:
                value = str(config[key])
                if not re.match(pattern, value):
                    errors.append(f"Invalid format for {key}: {self._mask_value(key, value)}")
        
        # Process secrets
        secret_keys = {
            "DISCORD_TOKEN", "DEEPL_API_KEY", "MY_MEMORY_API_KEY", 
            "OPENAI_API_KEY", "DATABASE_PASSWORD", "WEBHOOK_SECRET"
        }
        
        for key in secret_keys:
            if key in config:
                self.secrets[key] = ConfigSecret(
                    name=key,
                    value=config[key],
                    masked_value=self._mask_value(key, config[key]),
                    is_required=key in self.required_keys,
                    validation_pattern=self.validation_patterns.get(key)
                )
        
        # Store non-secret config
        for key, value in config.items():
            if key not in secret_keys:
                self.config_values[key] = value
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        return config
    
    def get_secret(self, name: str) -> Optional[str]:
        """Get a secret value."""
        if name in self.secrets:
            return self.secrets[name].value
        return os.getenv(name)
    
    def get_config(self, name: str, default: Any = None) -> Any:
        """Get a configuration value."""
        if name in self.config_values:
            return self.config_values[name]
        return os.getenv(name, default)
    
    def get_bool_config(self, name: str, default: bool = False) -> bool:
        """Get a boolean configuration value."""
        value = self.get_config(name, str(default).lower())
        return str(value).lower() in ('true', '1', 'yes', 'on')
    
    def get_int_config(self, name: str, default: int = 0) -> int:
        """Get an integer configuration value."""
        value = self.get_config(name, str(default))
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_list_config(self, name: str, default: Optional[List[str]] = None) -> List[str]:
        """Get a list configuration value (comma-separated)."""
        value = self.get_config(name, "")
        if not value:
            return default or []
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def _mask_value(self, key: str, value: str) -> str:
        """Mask sensitive values for logging."""
        sensitive_patterns = [
            'token', 'key', 'secret', 'password', 'auth', 'credential'
        ]
        
        if any(pattern in key.lower() for pattern in sensitive_patterns):
            return ConfigSecret._mask_secret(value)
        
        return value
    
    def get_masked_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary with sensitive values masked."""
        summary = {}
        
        # Add secrets (masked)
        for name, secret in self.secrets.items():
            summary[name] = secret.masked_value
        
        # Add regular config
        for name, value in self.config_values.items():
            summary[name] = self._mask_value(name, str(value))
        
        return summary
    
    def validate_api_key(self, key_name: str, key_value: str) -> bool:
        """Validate an API key format."""
        patterns = {
            "DISCORD_TOKEN": r'^[A-Za-z0-9\-_.]+$',
            "DEEPL_API_KEY": r'^[a-f0-9\-]+$',
            "MY_MEMORY_API_KEY": r'^[a-f0-9]+$',
            "OPENAI_API_KEY": r'^sk-[A-Za-z0-9]+$'
        }
        
        pattern = patterns.get(key_name)
        if pattern:
            return bool(re.match(pattern, key_value))
        
        return True  # Allow unknown keys
    
    def check_security_configuration(self) -> Dict[str, Any]:
        """Check security-related configuration."""
        security_status = {
            "rate_limiting_enabled": self.get_bool_config("ENABLE_RATE_LIMITING", True),
            "input_validation_enabled": self.get_bool_config("ENABLE_INPUT_VALIDATION", True),
            "security_logging_enabled": self.get_bool_config("ENABLE_SECURITY_LOGGING", True),
            "sandboxing_enabled": self.get_bool_config("ENABLE_SANDBOXING", True),
            "memory_limit_mb": self.get_int_config("MAX_MEMORY_MB", 256),
            "execution_time_limit": self.get_int_config("MAX_EXECUTION_TIME", 30),
            "log_level": self.get_config("LOG_LEVEL", "INFO")
        }
        
        # Check for security issues
        issues = []
        
        if not security_status["rate_limiting_enabled"]:
            issues.append("Rate limiting is disabled - bot may be vulnerable to spam")
        
        if not security_status["input_validation_enabled"]:
            issues.append("Input validation is disabled - bot may be vulnerable to injection attacks")
        
        if not security_status["security_logging_enabled"]:
            issues.append("Security logging is disabled - security events won't be tracked")
        
        if security_status["memory_limit_mb"] > 512:
            issues.append("Memory limit is very high - may allow DoS attacks")
        
        if security_status["execution_time_limit"] > 60:
            issues.append("Execution time limit is very high - may allow DoS attacks")
        
        security_status["issues"] = issues
        security_status["security_score"] = self._calculate_security_score(security_status)
        
        return security_status
    
    def _calculate_security_score(self, security_status: Dict[str, Any]) -> int:
        """Calculate a security score (0-100)."""
        score = 100
        
        # Deduct points for disabled security features
        if not security_status["rate_limiting_enabled"]:
            score -= 25
        if not security_status["input_validation_enabled"]:
            score -= 25
        if not security_status["security_logging_enabled"]:
            score -= 20
        if not security_status["sandboxing_enabled"]:
            score -= 20
        
        # Deduct points for high limits
        if security_status["memory_limit_mb"] > 512:
            score -= 10
        if security_status["execution_time_limit"] > 60:
            score -= 10
        
        return max(0, score)
    
    def export_secure_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Export configuration (optionally including secrets)."""
        config = {}
        
        if include_secrets:
            for name, secret in self.secrets.items():
                config[name] = secret.value
        else:
            for name, secret in self.secrets.items():
                config[name] = secret.masked_value
        
        config.update(self.config_values)
        
        return config


# Global secure config manager instance
secure_config = SecureConfigManager()


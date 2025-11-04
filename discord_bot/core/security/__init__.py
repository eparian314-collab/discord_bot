"""
Security framework for Discord bot protection.

This module provides comprehensive security measures including:
- Input validation and sanitization
- Rate limiting and abuse prevention
- Permission validation
- Secure configuration management
- Security logging and monitoring
- Sandboxing for dangerous operations
- Automated threat detection and response
"""

from .input_validator import InputValidator, ValidationError
from .rate_limiter import RateLimiter, RateLimitExceeded, rate_limiter
from .permission_checker import PermissionChecker, PermissionDenied, permission_checker, PermissionLevel
from .security_logger import SecurityLogger, SecurityEvent, SecurityEventType, SecurityLevel, security_logger
from .sandbox import SandboxManager, SandboxViolation, sandbox_manager
from .secure_config import SecureConfigManager, secure_config
from .security_engine import SecurityEngine, security_engine
from .decorators import (
    secure_command, rate_limit, validate_input, require_permission,
    audit_log, sandboxed, admin_only, moderator_only, trusted_only, owner_only
)

__all__ = [
    # Core validators and checkers
    'InputValidator',
    'ValidationError', 
    'RateLimiter',
    'RateLimitExceeded',
    'PermissionChecker',
    'PermissionDenied',
    'PermissionLevel',
    
    # Logging and monitoring
    'SecurityLogger',
    'SecurityEvent',
    'SecurityEventType',
    'SecurityLevel',
    
    # Sandboxing
    'SandboxManager',
    'SandboxViolation',
    
    # Configuration
    'SecureConfigManager',
    
    # Main security engine
    'SecurityEngine',
    
    # Global instances
    'rate_limiter',
    'permission_checker',
    'security_logger',
    'sandbox_manager',
    'secure_config',
    'security_engine',
    
    # Decorators for easy security integration
    'secure_command',
    'rate_limit',
    'validate_input',
    'require_permission',
    'audit_log',
    'sandboxed',
    'admin_only',
    'moderator_only',
    'trusted_only',
    'owner_only'
]


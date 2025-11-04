"""
Security Engine - Comprehensive security system integration.

Centralizes all security components and provides a unified interface for:
- Security monitoring and reporting
- Incident response
- Security policy enforcement
- Threat detection and analysis
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

from .input_validator import InputValidator, ValidationError
from .rate_limiter import rate_limiter, RateLimitExceeded
from .permission_checker import permission_checker, PermissionDenied
from .security_logger import security_logger, SecurityEventType, SecurityLevel
from .sandbox import sandbox_manager, SandboxViolation
from .secure_config import secure_config


@dataclass
class SecurityThreat:
    """Represents a detected security threat."""
    threat_id: str
    threat_type: str
    severity: SecurityLevel
    description: str
    user_id: Optional[int]
    guild_id: Optional[int]
    first_seen: float
    last_seen: float
    occurrence_count: int
    is_active: bool = True
    mitigation_actions: List[str] = None
    
    def __post_init__(self):
        if self.mitigation_actions is None:
            self.mitigation_actions = []


class SecurityEngine:
    """
    Comprehensive security management engine.
    
    Features:
    - Real-time threat detection
    - Automated incident response
    - Security policy enforcement
    - Performance monitoring
    - Compliance reporting
    """
    
    def __init__(self):
        self.active_threats: Dict[str, SecurityThreat] = {}
        self.blocked_users: Set[int] = set()
        self.blocked_guilds: Set[int] = set()
        self.suspicious_ips: Set[str] = set()
        
        # Security policies
        self.security_policies = {
            "max_failed_commands_per_minute": 10,
            "max_rate_limit_violations_per_hour": 20,
            "max_permission_denials_per_hour": 15,
            "suspicious_activity_threshold": 5,
            "auto_block_threshold": 50,  # Security score threshold for auto-blocking
            "quarantine_duration_hours": 24
        }
        
        # Performance metrics
        self.metrics = {
            "total_threats_detected": 0,
            "total_blocks_issued": 0,
            "total_validations_performed": 0,
            "total_rate_limits_enforced": 0,
            "total_permissions_checked": 0,
            "average_response_time": 0.0
        }
        
        # Initialize security components
        self.initialize_security_systems()
    
    def initialize_security_systems(self):
        """Initialize all security subsystems."""
        try:
            # Try to load secure configuration (but don't fail if env vars missing during import)
            try:
                config = secure_config.load_configuration()
            except ValueError as e:
                # During import, it's okay if configuration isn't complete yet
                # Log the warning but don't fail
                import sys
                if 'pytest' not in sys.modules and '__main__' in sys.modules:
                    # Only warn if we're actually running the bot
                    security_logger.security_logger.warning(f"Security configuration incomplete: {e}")
                config = {}
            
            # Initialize components based on configuration
            if secure_config.get_bool_config("ENABLE_RATE_LIMITING", True):
                rate_limiter.setup_default_limits()
            
            if secure_config.get_bool_config("ENABLE_SECURITY_LOGGING", True):
                security_logger.security_logger.info("Security engine initialized")
            
            # Setup sandbox with configured limits
            memory_limit = secure_config.get_int_config("MAX_MEMORY_MB", 256)
            time_limit = secure_config.get_int_config("MAX_EXECUTION_TIME", 30)
            
            sandbox_manager.limits.max_memory_mb = memory_limit
            sandbox_manager.limits.max_execution_time = time_limit
            
        except Exception as e:
            security_logger.security_logger.error(f"Failed to initialize security systems: {e}")
            # Don't raise - allow bot to continue with default security settings
    
    async def validate_user_action(
        self, 
        user_id: int, 
        action_type: str, 
        context: Dict[str, Any]
    ) -> bool:
        """
        Comprehensive validation of user actions.
        
        Args:
            user_id: ID of the user performing the action
            action_type: Type of action being performed
            context: Additional context for validation
            
        Returns:
            True if action is allowed, False otherwise
        """
        start_time = time.time()
        
        try:
            # Check if user is blocked
            if user_id in self.blocked_users:
                self._log_security_event(
                    "blocked_user_attempt",
                    f"Blocked user {user_id} attempted {action_type}",
                    SecurityLevel.WARNING,
                    user_id=user_id,
                    additional_data=context
                )
                return False
            
            # Check guild blocks
            guild_id = context.get("guild_id")
            if guild_id and guild_id in self.blocked_guilds:
                self._log_security_event(
                    "blocked_guild_attempt",
                    f"Action {action_type} attempted in blocked guild {guild_id}",
                    SecurityLevel.WARNING,
                    user_id=user_id,
                    additional_data=context
                )
                return False
            
            # Validate input if provided
            if "input_data" in context:
                try:
                    InputValidator.validate_text_input(
                        str(context["input_data"]), 
                        action_type
                    )
                    self.metrics["total_validations_performed"] += 1
                except ValidationError as e:
                    self._handle_validation_failure(user_id, action_type, e, context)
                    return False
            
            # Check rate limits
            if secure_config.get_bool_config("ENABLE_RATE_LIMITING", True):
                try:
                    await rate_limiter.check_user_command_limit(user_id, action_type)
                    self.metrics["total_rate_limits_enforced"] += 1
                except RateLimitExceeded as e:
                    self._handle_rate_limit_violation(user_id, action_type, e, context)
                    return False
            
            # Check permissions
            if "permission_context" in context:
                try:
                    await permission_checker.check_permission(
                        context["permission_context"], 
                        action_type
                    )
                    self.metrics["total_permissions_checked"] += 1
                except PermissionDenied as e:
                    self._handle_permission_denial(user_id, action_type, e, context)
                    return False
            
            # Update performance metrics
            response_time = time.time() - start_time
            self._update_performance_metrics(response_time)
            
            return True
            
        except Exception as e:
            self._log_security_event(
                "validation_error",
                f"Security validation failed for {action_type}: {e}",
                SecurityLevel.ERROR,
                user_id=user_id,
                additional_data={"error": str(e), **context}
            )
            return False
    
    def _handle_validation_failure(
        self, 
        user_id: int, 
        action_type: str, 
        error: ValidationError, 
        context: Dict[str, Any]
    ):
        """Handle input validation failures."""
        security_logger.log_invalid_input(
            user_id, error.field or "unknown", error.value,
            action_type, context.get("guild_id")
        )
        
        # Check for potential attack patterns
        self._analyze_threat_pattern(user_id, "invalid_input", context)
    
    def _handle_rate_limit_violation(
        self, 
        user_id: int, 
        action_type: str, 
        error: RateLimitExceeded, 
        context: Dict[str, Any]
    ):
        """Handle rate limit violations."""
        security_logger.log_rate_limit_exceeded(
            user_id, action_type, error.retry_after, context.get("guild_id")
        )
        
        # Check for potential abuse
        self._analyze_threat_pattern(user_id, "rate_limit_abuse", context)
    
    def _handle_permission_denial(
        self, 
        user_id: int, 
        action_type: str, 
        error: PermissionDenied, 
        context: Dict[str, Any]
    ):
        """Handle permission denials."""
        security_logger.log_permission_denied(
            user_id, action_type, error.required_permission or "unknown",
            context.get("guild_id"), context.get("channel_id")
        )
        
        # Check for privilege escalation attempts
        self._analyze_threat_pattern(user_id, "privilege_escalation", context)
    
    def _analyze_threat_pattern(self, user_id: int, threat_type: str, context: Dict[str, Any]):
        """Analyze patterns to detect potential threats."""
        threat_id = f"{threat_type}_{user_id}"
        current_time = time.time()
        
        if threat_id in self.active_threats:
            threat = self.active_threats[threat_id]
            threat.last_seen = current_time
            threat.occurrence_count += 1
        else:
            threat = SecurityThreat(
                threat_id=threat_id,
                threat_type=threat_type,
                severity=SecurityLevel.WARNING,
                description=f"Potential {threat_type} from user {user_id}",
                user_id=user_id,
                guild_id=context.get("guild_id"),
                first_seen=current_time,
                last_seen=current_time,
                occurrence_count=1
            )
            self.active_threats[threat_id] = threat
            self.metrics["total_threats_detected"] += 1
        
        # Escalate threat severity based on frequency
        if threat.occurrence_count >= 10:
            threat.severity = SecurityLevel.CRITICAL
            self._trigger_automatic_response(threat)
        elif threat.occurrence_count >= 5:
            threat.severity = SecurityLevel.ERROR
    
    def _trigger_automatic_response(self, threat: SecurityThreat):
        """Trigger automatic response to high-severity threats."""
        if threat.user_id and threat.occurrence_count >= self.security_policies["auto_block_threshold"]:
            self.block_user(threat.user_id, f"Automatic block due to {threat.threat_type}")
            threat.mitigation_actions.append("user_blocked")
        
        # Log critical incident
        self._log_security_event(
            "critical_threat_detected",
            f"Critical threat: {threat.description} (occurrences: {threat.occurrence_count})",
            SecurityLevel.CRITICAL,
            user_id=threat.user_id,
            additional_data={
                "threat_type": threat.threat_type,
                "occurrence_count": threat.occurrence_count,
                "mitigation_actions": threat.mitigation_actions
            }
        )
    
    def block_user(self, user_id: int, reason: str, duration_hours: Optional[float] = None):
        """Block a user from using the bot."""
        self.blocked_users.add(user_id)
        self.metrics["total_blocks_issued"] += 1
        
        # Schedule unblock if duration specified
        if duration_hours:
            asyncio.create_task(self._schedule_unblock(user_id, duration_hours * 3600))
        
        self._log_security_event(
            "user_blocked",
            f"User {user_id} blocked: {reason}",
            SecurityLevel.ERROR,
            user_id=user_id,
            additional_data={"reason": reason, "duration_hours": duration_hours}
        )
    
    def unblock_user(self, user_id: int, reason: str = "Manual unblock"):
        """Unblock a user."""
        self.blocked_users.discard(user_id)
        
        self._log_security_event(
            "user_unblocked",
            f"User {user_id} unblocked: {reason}",
            SecurityLevel.INFO,
            user_id=user_id,
            additional_data={"reason": reason}
        )
    
    async def _schedule_unblock(self, user_id: int, delay_seconds: float):
        """Schedule automatic unblocking of a user."""
        await asyncio.sleep(delay_seconds)
        self.unblock_user(user_id, "Automatic unblock after timeout")
    
    def block_guild(self, guild_id: int, reason: str):
        """Block a guild from using the bot."""
        self.blocked_guilds.add(guild_id)
        
        self._log_security_event(
            "guild_blocked",
            f"Guild {guild_id} blocked: {reason}",
            SecurityLevel.ERROR,
            guild_id=guild_id,
            additional_data={"reason": reason}
        )
    
    def unblock_guild(self, guild_id: int, reason: str = "Manual unblock"):
        """Unblock a guild."""
        self.blocked_guilds.discard(guild_id)
        
        self._log_security_event(
            "guild_unblocked",
            f"Guild {guild_id} unblocked: {reason}",
            SecurityLevel.INFO,
            guild_id=guild_id,
            additional_data={"reason": reason}
        )
    
    def _log_security_event(
        self, 
        event_type: str, 
        message: str, 
        level: SecurityLevel,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log a security event."""
        from .security_logger import SecurityEvent
        
        event = SecurityEvent(
            event_type=SecurityEventType.SECURITY_VIOLATION,
            level=level,
            message=message,
            user_id=user_id,
            guild_id=guild_id,
            additional_data=additional_data or {}
        )
        
        security_logger.log_event(event)
    
    def _update_performance_metrics(self, response_time: float):
        """Update performance metrics."""
        # Simple moving average for response time
        if self.metrics["average_response_time"] == 0:
            self.metrics["average_response_time"] = response_time
        else:
            self.metrics["average_response_time"] = (
                self.metrics["average_response_time"] * 0.9 + response_time * 0.1
            )
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status report."""
        current_time = time.time()
        
        # Count active threats by severity
        threat_counts = {level.value: 0 for level in SecurityLevel}
        for threat in self.active_threats.values():
            if threat.is_active:
                threat_counts[threat.severity.value] += 1
        
        # Get recent threat activity
        recent_threats = [
            threat for threat in self.active_threats.values()
            if current_time - threat.last_seen < 3600  # Last hour
        ]
        
        # Security configuration status
        security_config_status = secure_config.check_security_configuration()
        
        return {
            "timestamp": current_time,
            "system_status": {
                "rate_limiting_enabled": secure_config.get_bool_config("ENABLE_RATE_LIMITING", True),
                "input_validation_enabled": secure_config.get_bool_config("ENABLE_INPUT_VALIDATION", True),
                "security_logging_enabled": secure_config.get_bool_config("ENABLE_SECURITY_LOGGING", True),
                "sandboxing_enabled": secure_config.get_bool_config("ENABLE_SANDBOXING", True)
            },
            "threat_summary": {
                "total_active_threats": len([t for t in self.active_threats.values() if t.is_active]),
                "recent_threats": len(recent_threats),
                "threats_by_severity": threat_counts
            },
            "blocking_status": {
                "blocked_users": len(self.blocked_users),
                "blocked_guilds": len(self.blocked_guilds),
                "suspicious_ips": len(self.suspicious_ips)
            },
            "performance_metrics": self.metrics,
            "security_score": security_config_status["security_score"],
            "configuration_issues": security_config_status.get("issues", [])
        }
    
    def cleanup_old_threats(self, max_age_hours: int = 24):
        """Clean up old inactive threats."""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        threats_to_remove = []
        for threat_id, threat in self.active_threats.items():
            if threat.last_seen < cutoff_time:
                threats_to_remove.append(threat_id)
        
        for threat_id in threats_to_remove:
            del self.active_threats[threat_id]
    
    async def perform_security_audit(self) -> Dict[str, Any]:
        """Perform comprehensive security audit."""
        audit_results = {
            "audit_timestamp": time.time(),
            "security_status": self.get_security_status(),
            "configuration_audit": secure_config.get_masked_config_summary(),
            "component_health": {
                "rate_limiter": rate_limiter.get_remaining_requests("global:commands", "global") or 0,
                "sandbox_manager": sandbox_manager.get_stats(),
                "security_logger": security_logger.get_security_summary()
            }
        }
        
        return audit_results


# Global security engine instance
security_engine = SecurityEngine()


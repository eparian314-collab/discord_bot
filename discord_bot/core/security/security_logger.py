"""
Security logging and monitoring system for Discord bot.

Provides comprehensive security event tracking:
- Failed authentication attempts
- Permission violations  
- Rate limit violations
- Suspicious activity detection
- Security audit trails
- Incident response logging
"""
from __future__ import annotations

import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import discord


class SecurityEventType(Enum):
    """Types of security events."""
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_INPUT = "invalid_input"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    AUTHENTICATION_FAILURE = "authentication_failure"
    COMMAND_EXECUTION = "command_execution"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"
    ERROR_OCCURRED = "error_occurred"
    SECURITY_VIOLATION = "security_violation"


class SecurityLevel(Enum):
    """Security event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Represents a security event."""
    event_type: SecurityEventType
    level: SecurityLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    user_id: Optional[int] = None
    guild_id: Optional[int] = None
    channel_id: Optional[int] = None
    command_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default="")
    
    def __post_init__(self):
        if not self.event_id:
            # Generate unique event ID
            data = f"{self.timestamp}_{self.event_type.value}_{self.user_id}_{self.message}"
            self.event_id = hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['level'] = self.level.value
        return data
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class SecurityLogger:
    """
    Comprehensive security logging system.
    
    Features:
    - Structured logging with JSON format
    - Multiple output destinations
    - Event correlation and analysis
    - Automatic incident detection
    - Performance monitoring
    """
    
    def __init__(self, log_directory: str = "logs/security"):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Setup loggers
        self.setup_loggers()
        
        # Event storage for analysis
        self.recent_events: List[SecurityEvent] = []
        self.max_recent_events = 1000
        
        # Incident detection thresholds
        self.incident_thresholds = {
            "failed_commands_per_minute": 10,
            "rate_limit_violations_per_hour": 50,
            "permission_denials_per_hour": 20,
            "suspicious_patterns_per_hour": 5
        }
        
        # Suspicious activity patterns
        self.suspicious_patterns = [
            "rapid_command_execution",
            "permission_escalation_attempt",
            "unusual_access_pattern",
            "potential_bot_behavior",
            "data_harvesting_attempt"
        ]
    
    def setup_loggers(self):
        """Setup different loggers for different security aspects."""
        # Main security logger
        self.security_logger = logging.getLogger("security")
        self.security_logger.setLevel(logging.INFO)
        
        # Security events file
        security_handler = RotatingFileHandler(
            self.log_directory / "security_events.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        security_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        security_handler.setFormatter(security_formatter)
        self.security_logger.addHandler(security_handler)
        
        # Audit logger (for compliance)
        self.audit_logger = logging.getLogger("audit")
        self.audit_logger.setLevel(logging.INFO)
        
        audit_handler = RotatingFileHandler(
            self.log_directory / "audit.log",
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=20
        )
        audit_formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(message)s'
        )
        audit_handler.setFormatter(audit_formatter)
        self.audit_logger.addHandler(audit_handler)
        
        # Incident logger (for critical events)
        self.incident_logger = logging.getLogger("incidents")
        self.incident_logger.setLevel(logging.WARNING)
        
        incident_handler = RotatingFileHandler(
            self.log_directory / "incidents.log",
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=50
        )
        incident_formatter = logging.Formatter(
            '%(asctime)s - INCIDENT - %(levelname)s - %(message)s'
        )
        incident_handler.setFormatter(incident_formatter)
        self.incident_logger.addHandler(incident_handler)
    
    def log_event(self, event: SecurityEvent):
        """Log a security event."""
        # Add to recent events for analysis
        self.recent_events.append(event)
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events.pop(0)
        
        # Log to appropriate logger
        log_message = f"[{event.event_id}] {event.message}"
        if event.user_id:
            log_message += f" | User: {event.user_id}"
        if event.guild_id:
            log_message += f" | Guild: {event.guild_id}"
        if event.command_name:
            log_message += f" | Command: {event.command_name}"
        
        # Add structured data
        structured_data = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "level": event.level.value,
            "timestamp": event.timestamp,
            "user_id": event.user_id,
            "guild_id": event.guild_id,
            "channel_id": event.channel_id,
            "command_name": event.command_name,
            "additional_data": event.additional_data
        }
        
        log_message += f" | Data: {json.dumps(structured_data)}"
        
        # Log based on severity
        if event.level == SecurityLevel.INFO:
            self.security_logger.info(log_message)
        elif event.level == SecurityLevel.WARNING:
            self.security_logger.warning(log_message)
            self.incident_logger.warning(log_message)
        elif event.level == SecurityLevel.ERROR:
            self.security_logger.error(log_message)
            self.incident_logger.error(log_message)
        elif event.level == SecurityLevel.CRITICAL:
            self.security_logger.critical(log_message)
            self.incident_logger.critical(log_message)
        
        # Always log to audit trail
        self.audit_logger.info(event.to_json())
        
        # Check for incidents
        self._check_for_incidents()
    
    def log_permission_denied(
        self, 
        user_id: int, 
        command_name: str, 
        required_permission: str,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None
    ):
        """Log permission denied event."""
        event = SecurityEvent(
            event_type=SecurityEventType.PERMISSION_DENIED,
            level=SecurityLevel.WARNING,
            message=f"Permission denied for command '{command_name}': requires {required_permission}",
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            command_name=command_name,
            additional_data={"required_permission": required_permission}
        )
        self.log_event(event)
    
    def log_rate_limit_exceeded(
        self, 
        user_id: int, 
        limit_type: str, 
        retry_after: float,
        guild_id: Optional[int] = None
    ):
        """Log rate limit exceeded event."""
        event = SecurityEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            level=SecurityLevel.WARNING,
            message=f"Rate limit exceeded for {limit_type}. Retry after {retry_after:.1f}s",
            user_id=user_id,
            guild_id=guild_id,
            additional_data={
                "limit_type": limit_type,
                "retry_after": retry_after
            }
        )
        self.log_event(event)
    
    def log_invalid_input(
        self, 
        user_id: int, 
        field_name: str, 
        value: Any,
        command_name: Optional[str] = None,
        guild_id: Optional[int] = None
    ):
        """Log invalid input event."""
        # Sanitize value for logging (don't log actual malicious content)
        sanitized_value = str(value)[:100] if value else None
        
        event = SecurityEvent(
            event_type=SecurityEventType.INVALID_INPUT,
            level=SecurityLevel.WARNING,
            message=f"Invalid input detected in field '{field_name}'",
            user_id=user_id,
            guild_id=guild_id,
            command_name=command_name,
            additional_data={
                "field_name": field_name,
                "sanitized_value": sanitized_value
            }
        )
        self.log_event(event)
    
    def log_command_execution(
        self, 
        user_id: int, 
        command_name: str, 
        success: bool,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        execution_time: Optional[float] = None
    ):
        """Log command execution event."""
        level = SecurityLevel.INFO if success else SecurityLevel.WARNING
        status = "successful" if success else "failed"
        
        additional_data = {"success": success}
        if execution_time is not None:
            additional_data["execution_time"] = execution_time
        
        event = SecurityEvent(
            event_type=SecurityEventType.COMMAND_EXECUTION,
            level=level,
            message=f"Command '{command_name}' execution {status}",
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            command_name=command_name,
            additional_data=additional_data
        )
        self.log_event(event)
    
    def log_suspicious_activity(
        self, 
        user_id: int, 
        activity_type: str, 
        description: str,
        guild_id: Optional[int] = None,
        severity: SecurityLevel = SecurityLevel.WARNING
    ):
        """Log suspicious activity event."""
        event = SecurityEvent(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            level=severity,
            message=f"Suspicious activity detected: {activity_type} - {description}",
            user_id=user_id,
            guild_id=guild_id,
            additional_data={"activity_type": activity_type}
        )
        self.log_event(event)
    
    def log_security_violation(
        self, 
        user_id: int, 
        violation_type: str, 
        description: str,
        guild_id: Optional[int] = None
    ):
        """Log security violation event."""
        event = SecurityEvent(
            event_type=SecurityEventType.SECURITY_VIOLATION,
            level=SecurityLevel.ERROR,
            message=f"Security violation: {violation_type} - {description}",
            user_id=user_id,
            guild_id=guild_id,
            additional_data={"violation_type": violation_type}
        )
        self.log_event(event)
    
    def log_configuration_change(
        self, 
        user_id: int, 
        setting_name: str, 
        old_value: Any, 
        new_value: Any,
        guild_id: Optional[int] = None
    ):
        """Log configuration change event."""
        # Don't log sensitive values
        safe_old = "***" if "password" in setting_name.lower() or "token" in setting_name.lower() else str(old_value)
        safe_new = "***" if "password" in setting_name.lower() or "token" in setting_name.lower() else str(new_value)
        
        event = SecurityEvent(
            event_type=SecurityEventType.CONFIGURATION_CHANGE,
            level=SecurityLevel.INFO,
            message=f"Configuration changed: {setting_name} = {safe_new} (was: {safe_old})",
            user_id=user_id,
            guild_id=guild_id,
            additional_data={
                "setting_name": setting_name,
                "old_value": safe_old,
                "new_value": safe_new
            }
        )
        self.log_event(event)
    
    def _check_for_incidents(self):
        """Check recent events for incident patterns."""
        current_time = time.time()
        
        # Check for rapid permission denials
        recent_denials = [
            e for e in self.recent_events
            if e.event_type == SecurityEventType.PERMISSION_DENIED
            and current_time - e.timestamp < 3600  # Last hour
        ]
        
        if len(recent_denials) > self.incident_thresholds["permission_denials_per_hour"]:
            self._trigger_incident("High number of permission denials detected", SecurityLevel.ERROR)
        
        # Check for rate limit abuse
        recent_rate_limits = [
            e for e in self.recent_events
            if e.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED
            and current_time - e.timestamp < 3600
        ]
        
        if len(recent_rate_limits) > self.incident_thresholds["rate_limit_violations_per_hour"]:
            self._trigger_incident("High number of rate limit violations detected", SecurityLevel.ERROR)
        
        # Check for suspicious activity patterns
        recent_suspicious = [
            e for e in self.recent_events
            if e.event_type == SecurityEventType.SUSPICIOUS_ACTIVITY
            and current_time - e.timestamp < 3600
        ]
        
        if len(recent_suspicious) > self.incident_thresholds["suspicious_patterns_per_hour"]:
            self._trigger_incident("High number of suspicious activities detected", SecurityLevel.CRITICAL)
    
    def _trigger_incident(self, description: str, level: SecurityLevel):
        """Trigger a security incident."""
        incident_event = SecurityEvent(
            event_type=SecurityEventType.SECURITY_VIOLATION,
            level=level,
            message=f"SECURITY INCIDENT: {description}",
            additional_data={"incident_type": "automated_detection"}
        )
        
        self.log_event(incident_event)
        
        # TODO: Add incident response actions like:
        # - Notify administrators
        # - Temporarily increase security measures
        # - Send alerts to monitoring systems
    
    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get security summary for the last N hours."""
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        recent_events = [e for e in self.recent_events if e.timestamp > cutoff_time]
        
        # Count events by type
        event_counts = {}
        for event in recent_events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Count events by severity
        severity_counts = {}
        for event in recent_events:
            severity = event.level.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Top users by event count
        user_counts = {}
        for event in recent_events:
            if event.user_id:
                user_counts[event.user_id] = user_counts.get(event.user_id, 0) + 1
        
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "period_hours": hours,
            "total_events": len(recent_events),
            "event_counts": event_counts,
            "severity_counts": severity_counts,
            "top_users": top_users,
            "incidents_detected": len([e for e in recent_events if "INCIDENT" in e.message])
        }


# Global security logger instance
security_logger = SecurityLogger()


"""
Input validation and sanitization for Discord bot security.

Provides comprehensive input validation to prevent:
- Code injection attacks
- XSS attacks
- SQL injection
- Path traversal
- Command injection
- Malicious file uploads
- Unicode exploitation
"""
from __future__ import annotations

import re
import html
import urllib.parse
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


class ValidationError(Exception):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        self.field = field
        self.value = value
        super().__init__(message)


class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    # Dangerous patterns that should be blocked
    DANGEROUS_PATTERNS = [
        # Code injection patterns
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'vbscript:',
        r'data:.*base64',
        r'eval\s*\(',
        r'exec\s*\(',
        r'system\s*\(',
        r'subprocess\s*\.',
        r'os\s*\.',
        r'__import__\s*\(',
        
        # SQL injection patterns  
        r'union\s+select',
        r'drop\s+table',
        r'delete\s+from',
        r'insert\s+into',
        r'update\s+.*\s+set',
        r'alter\s+table',
        r'create\s+table',
        
        # Path traversal
        r'\.\./+',
        r'\.\.\\+',
        r'/etc/passwd',
        r'/etc/shadow',
        r'\\windows\\system32',
        
        # Command injection
        r';\s*rm\s+',
        r';\s*del\s+',
        r';\s*format\s+',
        r'\|\s*nc\s+',
        r'\|\s*netcat\s+',
        r'`.*`',
        r'\$\(.*\)',
    ]
    
    # Compiled regex patterns for better performance
    DANGEROUS_REGEX = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in DANGEROUS_PATTERNS]
    
    # Safe characters for different contexts
    SAFE_FILENAME_CHARS = re.compile(r'^[a-zA-Z0-9._-]+$')
    SAFE_USERNAME_CHARS = re.compile(r'^[a-zA-Z0-9._-]{1,32}$')
    SAFE_CHANNEL_NAME_CHARS = re.compile(r'^[a-z0-9_-]{1,100}$')
    
    # Maximum lengths to prevent DoS
    MAX_MESSAGE_LENGTH = 2000
    MAX_EMBED_TITLE_LENGTH = 256
    MAX_EMBED_DESCRIPTION_LENGTH = 4096
    MAX_EMBED_FIELD_LENGTH = 1024
    MAX_FILENAME_LENGTH = 255
    MAX_URL_LENGTH = 2048
    
    @classmethod
    def validate_text_input(cls, text: str, field_name: str = "input", max_length: Optional[int] = None) -> str:
        """
        Validate and sanitize text input.
        
        Args:
            text: The text to validate
            field_name: Name of the field for error reporting
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
            
        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(text, str):
            raise ValidationError(f"{field_name} must be a string", field_name, text)
        
        # Check length
        if max_length and len(text) > max_length:
            raise ValidationError(f"{field_name} exceeds maximum length of {max_length}", field_name, text)
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_REGEX:
            if pattern.search(text):
                raise ValidationError(f"{field_name} contains potentially dangerous content", field_name, text)
        
        # Sanitize HTML entities
        sanitized = html.escape(text, quote=False)
        
        # Normalize Unicode to prevent Unicode-based attacks
        sanitized = sanitized.encode('ascii', 'ignore').decode('ascii')
        
        return sanitized.strip()
    
    @classmethod
    def validate_discord_message(cls, content: str) -> str:
        """Validate Discord message content."""
        return cls.validate_text_input(content, "message", cls.MAX_MESSAGE_LENGTH)
    
    @classmethod
    def validate_embed_title(cls, title: str) -> str:
        """Validate Discord embed title."""
        return cls.validate_text_input(title, "embed_title", cls.MAX_EMBED_TITLE_LENGTH)
    
    @classmethod
    def validate_embed_description(cls, description: str) -> str:
        """Validate Discord embed description."""
        return cls.validate_text_input(description, "embed_description", cls.MAX_EMBED_DESCRIPTION_LENGTH)
    
    @classmethod
    def validate_filename(cls, filename: str) -> str:
        """
        Validate filename for security.
        
        Args:
            filename: The filename to validate
            
        Returns:
            Sanitized filename
            
        Raises:
            ValidationError: If filename is invalid
        """
        if not isinstance(filename, str):
            raise ValidationError("Filename must be a string", "filename", filename)
        
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            raise ValidationError(f"Filename exceeds maximum length of {cls.MAX_FILENAME_LENGTH}", "filename", filename)
        
        # Remove any path components
        filename = Path(filename).name
        
        # Check for safe characters
        if not cls.SAFE_FILENAME_CHARS.match(filename):
            raise ValidationError("Filename contains invalid characters", "filename", filename)
        
        # Block dangerous filenames
        dangerous_names = {
            'con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 'com5',
            'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3', 'lpt4',
            'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
        }
        
        if filename.lower() in dangerous_names:
            raise ValidationError("Filename is a reserved system name", "filename", filename)
        
        return filename
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """
        Validate URL for security.
        
        Args:
            url: The URL to validate
            
        Returns:
            Sanitized URL
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not isinstance(url, str):
            raise ValidationError("URL must be a string", "url", url)
        
        if len(url) > cls.MAX_URL_LENGTH:
            raise ValidationError(f"URL exceeds maximum length of {cls.MAX_URL_LENGTH}", "url", url)
        
        # Parse URL to validate structure
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            raise ValidationError("Invalid URL format", "url", url)
        
        # Only allow safe schemes
        safe_schemes = {'http', 'https', 'ftp', 'ftps'}
        if parsed.scheme.lower() not in safe_schemes:
            raise ValidationError(f"URL scheme '{parsed.scheme}' not allowed", "url", url)
        
        # Block dangerous hostnames
        dangerous_hosts = {
            'localhost', '127.0.0.1', '0.0.0.0', '::1',
            '10.', '172.', '192.168.',  # Private IP ranges
        }
        
        hostname = parsed.hostname or ''
        for dangerous in dangerous_hosts:
            if hostname.startswith(dangerous):
                raise ValidationError("URL points to dangerous or private network", "url", url)
        
        return url
    
    @classmethod
    def validate_user_id(cls, user_id: Union[str, int]) -> int:
        """
        Validate Discord user ID.
        
        Args:
            user_id: The user ID to validate
            
        Returns:
            Validated user ID as integer
            
        Raises:
            ValidationError: If user ID is invalid
        """
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            raise ValidationError("User ID must be a valid integer", "user_id", user_id)
        
        # Discord snowflake IDs are 64-bit unsigned integers
        if user_id_int < 0 or user_id_int > 2**63 - 1:
            raise ValidationError("User ID out of valid range", "user_id", user_id)
        
        return user_id_int
    
    @classmethod
    def validate_channel_id(cls, channel_id: Union[str, int]) -> int:
        """Validate Discord channel ID."""
        return cls.validate_user_id(channel_id)  # Same validation logic
    
    @classmethod
    def validate_guild_id(cls, guild_id: Union[str, int]) -> int:
        """Validate Discord guild ID."""
        return cls.validate_user_id(guild_id)  # Same validation logic
    
    @classmethod
    def sanitize_command_parameter(cls, param: Any, param_name: str) -> Any:
        """
        Sanitize command parameters based on type.
        
        Args:
            param: The parameter to sanitize
            param_name: Name of the parameter
            
        Returns:
            Sanitized parameter
        """
        if isinstance(param, str):
            return cls.validate_text_input(param, param_name)
        elif isinstance(param, (int, float)):
            # Validate numeric ranges
            if isinstance(param, int) and (param < -2**31 or param > 2**31 - 1):
                raise ValidationError(f"{param_name} integer out of safe range", param_name, param)
            if isinstance(param, float) and (abs(param) > 1e100):
                raise ValidationError(f"{param_name} float too large", param_name, param)
            return param
        elif isinstance(param, bool):
            return param
        elif param is None:
            return param
        else:
            # Convert unknown types to string and validate
            return cls.validate_text_input(str(param), param_name)
    
    @classmethod
    def validate_json_data(cls, data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """
        Validate JSON data to prevent billion laughs and other attacks.
        
        Args:
            data: Dictionary to validate
            max_depth: Maximum nesting depth allowed
            
        Returns:
            Validated data
            
        Raises:
            ValidationError: If data is invalid
        """
        def _validate_recursive(obj: Any, depth: int = 0) -> Any:
            if depth > max_depth:
                raise ValidationError(f"JSON data exceeds maximum nesting depth of {max_depth}")
            
            if isinstance(obj, dict):
                if len(obj) > 1000:  # Prevent massive objects
                    raise ValidationError("JSON object has too many keys")
                return {
                    cls.validate_text_input(str(k), "json_key"): _validate_recursive(v, depth + 1)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                if len(obj) > 10000:  # Prevent massive arrays
                    raise ValidationError("JSON array is too large")
                return [_validate_recursive(item, depth + 1) for item in obj]
            elif isinstance(obj, str):
                return cls.validate_text_input(obj, "json_value")
            elif isinstance(obj, (int, float, bool)) or obj is None:
                return obj
            else:
                raise ValidationError(f"Unsupported JSON data type: {type(obj)}")
        
        return _validate_recursive(data)


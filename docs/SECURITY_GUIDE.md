# Discord Bot Security Framework

## Overview

This comprehensive security framework protects your Discord bot against common vulnerabilities and attacks through multiple layers of defense:

- **Input Validation**: Prevents injection attacks and malicious input
- **Rate Limiting**: Protects against spam and DoS attacks
- **Permission System**: Enforces role-based access control
- **Audit Logging**: Comprehensive security event tracking
- **Sandboxing**: Isolates dangerous operations
- **Threat Detection**: Automated security monitoring

## Quick Start

### 1. Basic Security Integration

Apply security to any command using decorators:

```python
from core.security import secure_command, admin_only, rate_limit

class YourCog(commands.Cog):
    
    @secure_command(permission_level="trusted", rate_limit_type="pokemon_catch")
    async def catch_pokemon(self, ctx, pokemon_name: str):
        # Command automatically gets:
        # - Input validation for pokemon_name
        # - Rate limiting for pokemon catches
        # - Permission checking for trusted users
        # - Audit logging
        pass
    
    @admin_only
    async def admin_command(self, ctx):
        # Only admins can use this
        pass
    
    @rate_limit("special_command", requests=5, period=300)  # 5 uses per 5 minutes
    async def special_command(self, ctx):
        pass
```

### 2. Manual Security Checks

For advanced use cases, use security components directly:

```python
from core.security import (
    InputValidator, rate_limiter, permission_checker, 
    security_logger, sandbox_manager
)

async def my_function(ctx, user_input: str):
    # Validate input
    try:
        clean_input = InputValidator.validate_text_input(user_input, "user_message")
    except ValidationError as e:
        await ctx.send(f"Invalid input: {e}")
        return
    
    # Check rate limits
    try:
        await rate_limiter.check_user_command_limit(ctx.author.id, "my_function")
    except RateLimitExceeded as e:
        await ctx.send(f"Rate limited. Try again in {e.retry_after:.1f} seconds.")
        return
    
    # Log security event
    security_logger.log_command_execution(
        ctx.author.id, "my_function", True, ctx.guild.id, ctx.channel.id
    )
```

### 3. Sandboxed Operations

For potentially dangerous operations like file I/O or network requests:

```python
from core.security import sandbox_manager

async def download_file(url: str):
    async with sandbox_manager.sandbox_operation("download"):
        # This will validate the URL and apply resource limits
        response = await sandbox_manager.safe_http_request("GET", url)
        return await response.text()

async def process_file(file_path: str):
    async with sandbox_manager.temp_directory() as temp_dir:
        # Work with files in a temporary, sandboxed directory
        safe_path = temp_dir / "processed_file.txt"
        content = await sandbox_manager.safe_file_read(file_path)
        await sandbox_manager.safe_file_write(safe_path, content.upper())
```

## Security Configuration

Set these environment variables to configure security:

```env
# Security Controls
ENABLE_RATE_LIMITING=true
ENABLE_INPUT_VALIDATION=true
ENABLE_SECURITY_LOGGING=true
ENABLE_SANDBOXING=true

# Resource Limits
MAX_MEMORY_MB=256
MAX_EXECUTION_TIME=30

# Required for permission system
OWNER_IDS=123456789,987654321
```

## Security Levels and Permissions

The system supports hierarchical permission levels:

- **everyone**: Default level, basic commands
- **trusted**: Users with verified roles or account age > 30 days
- **moderator**: Users with Discord moderation permissions
- **admin**: Users with Discord administrator permissions
- **owner**: Guild owners
- **bot_owner**: Bot owners (defined in OWNER_IDS)

## Rate Limiting

Default rate limits are automatically applied:

- **Global**: 100 commands/minute, 1000 messages/minute
- **Per-user**: 30 commands/minute, 50 messages/minute
- **Per-guild**: 200 commands/minute, 500 messages/minute
- **Special operations**: Pokemon catches (10/minute), battles (3/5 minutes)

## Input Validation

All user inputs are automatically validated against:

- **Dangerous patterns**: Code injection, SQL injection, XSS
- **Length limits**: Prevents buffer overflow attacks
- **Character validation**: Only safe Unicode characters
- **File validation**: Safe extensions and paths only

## Security Monitoring

The system automatically detects and responds to:

- **Repeated permission violations**: Auto-blocks after threshold
- **Rate limit abuse**: Temporary restrictions
- **Suspicious patterns**: Unusual access patterns
- **Input attacks**: Malicious content attempts

## Getting Security Reports

```python
from core.security import security_engine

# Get current security status
status = security_engine.get_security_status()
print(f"Security Score: {status['security_score']}/100")
print(f"Active Threats: {status['threat_summary']['total_active_threats']}")

# Perform security audit
audit = await security_engine.perform_security_audit()
```

## Emergency Response

If you detect an attack:

```python
from core.security import security_engine

# Block a malicious user
security_engine.block_user(user_id, "Detected attack pattern", duration_hours=24)

# Block an entire guild
security_engine.block_guild(guild_id, "Coordinated abuse")

# Check if user is blocked
if user_id in security_engine.blocked_users:
    # User is blocked
    pass
```

## Best Practices

1. **Always use security decorators** on public commands
2. **Validate all user inputs** before processing
3. **Use sandboxing** for file operations and external API calls
4. **Monitor security logs** regularly
5. **Keep rate limits reasonable** but protective
6. **Use least privilege principle** for permissions
7. **Regularly audit security configuration**

## Troubleshooting

### High Security Score Issues

If security score is low, check:
- Are security features enabled in configuration?
- Are resource limits too high?
- Check for configuration issues in the security status

### Rate Limiting Issues

If users report rate limiting problems:
```python
# Check remaining requests for a user
remaining = rate_limiter.get_remaining_requests("user:commands", user_id)

# Reset limits for a user (admin only)
rate_limiter.reset_limits(user_id)
```

### False Positive Blocks

If legitimate users are blocked:
```python
# Unblock a user
security_engine.unblock_user(user_id, "False positive - legitimate user")

# Check threat details
threats = security_engine.active_threats
for threat_id, threat in threats.items():
    if threat.user_id == user_id:
        print(f"Threat: {threat.threat_type}, Count: {threat.occurrence_count}")
```

## Logging and Compliance

Security logs are automatically written to:
- `logs/security/security_events.log` - All security events
- `logs/security/audit.log` - Compliance audit trail
- `logs/security/incidents.log` - Critical security incidents

Log format is JSON for easy parsing and analysis.

## Integration with Existing Code

The security framework is designed to integrate seamlessly:

1. **Minimal changes required**: Just add decorators to existing commands
2. **Backwards compatible**: Existing commands work without modification
3. **Gradual adoption**: Can be applied incrementally
4. **Performance optimized**: Minimal overhead on normal operations

This security framework provides enterprise-grade protection while maintaining ease of use and performance.
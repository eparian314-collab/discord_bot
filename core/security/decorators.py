"""
Security decorators for Discord bot commands.

Provides easy-to-use decorators for applying security measures:
- Input validation
- Rate limiting
- Permission checking
- Audit logging
- Sandboxing
"""
from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Callable, Any, Optional, Union, List
import discord
from discord.ext import commands

from .input_validator import InputValidator, ValidationError
from .rate_limiter import rate_limiter, RateLimitExceeded
from .permission_checker import permission_checker, PermissionChecker, PermissionContext, PermissionDenied
from .security_logger import security_logger, SecurityEventType, SecurityLevel
from .sandbox import sandbox_manager, SandboxViolation


def secure_command(
    permission_level: str = "everyone",
    rate_limit_type: Optional[str] = None,
    validate_inputs: bool = True,
    log_execution: bool = True,
    sandbox: bool = False
):
    """
    Comprehensive security decorator for Discord commands.
    
    Args:
        permission_level: Required permission level
        rate_limit_type: Rate limit type to apply
        validate_inputs: Whether to validate command inputs
        log_execution: Whether to log command execution
        sandbox: Whether to run command in sandbox
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            start_time = time.time()
            command_name = func.__name__
            user_id = ctx.author.id
            guild_id = ctx.guild.id if ctx.guild else None
            channel_id = ctx.channel.id
            
            try:
                # Create permission context
                perm_ctx = PermissionContext(
                    user=ctx.author,
                    guild=ctx.guild,
                    channel=ctx.channel,
                    bot=ctx.bot,
                    command_name=command_name
                )
                
                # 1. Permission checking
                try:
                    await permission_checker.check_permission(perm_ctx, command_name)
                except PermissionDenied as e:
                    security_logger.log_permission_denied(
                        user_id, command_name, e.required_permission or "unknown",
                        guild_id, channel_id
                    )
                    await ctx.send("❌ You don't have permission to use this command.")
                    return
                
                # 2. Rate limiting
                if rate_limit_type:
                    try:
                        await rate_limiter.check_user_command_limit(user_id, rate_limit_type)
                    except RateLimitExceeded as e:
                        security_logger.log_rate_limit_exceeded(
                            user_id, rate_limit_type, e.retry_after, guild_id
                        )
                        await ctx.send(f"⏰ Rate limit exceeded. Try again in {e.retry_after:.1f} seconds.")
                        return
                
                # 3. Input validation
                if validate_inputs:
                    try:
                        # Validate all string arguments
                        validated_args = []
                        for arg in args:
                            if isinstance(arg, str):
                                validated_args.append(InputValidator.validate_text_input(arg, "argument"))
                            else:
                                validated_args.append(arg)
                        
                        validated_kwargs = {}
                        for key, value in kwargs.items():
                            if isinstance(value, str):
                                validated_kwargs[key] = InputValidator.validate_text_input(value, key)
                            else:
                                validated_kwargs[key] = value
                        
                        args = tuple(validated_args)
                        kwargs = validated_kwargs
                        
                    except ValidationError as e:
                        security_logger.log_invalid_input(
                            user_id, e.field or "unknown", e.value, command_name, guild_id
                        )
                        await ctx.send(f"❌ Invalid input: {e}")
                        return
                
                # 4. Execute command (with or without sandbox)
                if sandbox:
                    async with sandbox_manager.sandbox_operation(command_name):
                        result = await func(self, ctx, *args, **kwargs)
                else:
                    result = await func(self, ctx, *args, **kwargs)
                
                # 5. Log successful execution
                if log_execution:
                    execution_time = time.time() - start_time
                    security_logger.log_command_execution(
                        user_id, command_name, True, guild_id, channel_id, execution_time
                    )
                
                return result
                
            except SandboxViolation as e:
                security_logger.log_security_violation(
                    user_id, "sandbox_violation", str(e), guild_id
                )
                await ctx.send("❌ Command blocked for security reasons.")
                
            except Exception as e:
                # Log failed execution
                if log_execution:
                    execution_time = time.time() - start_time
                    security_logger.log_command_execution(
                        user_id, command_name, False, guild_id, channel_id, execution_time
                    )
                
                # Don't leak error details to users
                await ctx.send("❌ An error occurred while processing your command.")
                raise  # Re-raise for proper error handling
        
        return wrapper
    return decorator


def rate_limit(limit_type: str, requests: int = 10, period: float = 60.0):
    """
    Rate limiting decorator.
    
    Args:
        limit_type: Type of rate limit
        requests: Number of requests allowed
        period: Time period in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            user_id = ctx.author.id
            
            try:
                await rate_limiter.check_rate_limit(f"user:{limit_type}", user_id)
                return await func(self, ctx, *args, **kwargs)
            except RateLimitExceeded as e:
                security_logger.log_rate_limit_exceeded(
                    user_id, limit_type, e.retry_after, 
                    ctx.guild.id if ctx.guild else None
                )
                await ctx.send(f"⏰ Rate limit exceeded. Try again in {e.retry_after:.1f} seconds.")
        
        return wrapper
    return decorator


def validate_input(max_length: Optional[int] = None, field_name: str = "input"):
    """
    Input validation decorator.
    
    Args:
        max_length: Maximum length for string inputs
        field_name: Name of the field for error messages
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, input_value: str, *args, **kwargs):
            try:
                validated_input = InputValidator.validate_text_input(
                    input_value, field_name, max_length
                )
                return await func(self, ctx, validated_input, *args, **kwargs)
            except ValidationError as e:
                security_logger.log_invalid_input(
                    ctx.author.id, e.field or field_name, e.value,
                    func.__name__, ctx.guild.id if ctx.guild else None
                )
                await ctx.send(f"❌ Invalid input: {e}")
        
        return wrapper
    return decorator


def require_permission(permission_level: str):
    """
    Permission checking decorator.
    
    Args:
        permission_level: Required permission level
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            perm_ctx = PermissionContext(
                user=ctx.author,
                guild=ctx.guild,
                channel=ctx.channel,
                bot=ctx.bot,
                command_name=func.__name__
            )
            
            try:
                await permission_checker.check_permission(perm_ctx, func.__name__)
                return await func(self, ctx, *args, **kwargs)
            except PermissionDenied as e:
                security_logger.log_permission_denied(
                    ctx.author.id, func.__name__, e.required_permission or "unknown",
                    ctx.guild.id if ctx.guild else None, ctx.channel.id
                )
                await ctx.send("❌ You don't have permission to use this command.")
        
        return wrapper
    return decorator


def audit_log(event_type: str = "command_execution"):
    """
    Audit logging decorator.
    
    Args:
        event_type: Type of event to log
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(self, ctx, *args, **kwargs)
                
                execution_time = time.time() - start_time
                security_logger.log_command_execution(
                    ctx.author.id, func.__name__, True,
                    ctx.guild.id if ctx.guild else None,
                    ctx.channel.id, execution_time
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                security_logger.log_command_execution(
                    ctx.author.id, func.__name__, False,
                    ctx.guild.id if ctx.guild else None,
                    ctx.channel.id, execution_time
                )
                raise
        
        return wrapper
    return decorator


def sandboxed():
    """Sandbox execution decorator."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            try:
                async with sandbox_manager.sandbox_operation(func.__name__):
                    return await func(self, ctx, *args, **kwargs)
            except SandboxViolation as e:
                security_logger.log_security_violation(
                    ctx.author.id, "sandbox_violation", str(e),
                    ctx.guild.id if ctx.guild else None
                )
                await ctx.send("❌ Command blocked for security reasons.")
        
        return wrapper
    return decorator


# Convenience decorators for common security levels
def admin_only(func: Callable) -> Callable:
    """Decorator for admin-only commands."""
    return require_permission("admin")(audit_log()(func))


def moderator_only(func: Callable) -> Callable:
    """Decorator for moderator-only commands."""
    return require_permission("moderator")(audit_log()(func))


def trusted_only(func: Callable) -> Callable:
    """Decorator for trusted user commands."""
    return require_permission("trusted")(rate_limit("trusted_command")(func))


def owner_only(func: Callable) -> Callable:
    """Decorator for owner-only commands."""
    return require_permission("bot_owner")(audit_log()(func))
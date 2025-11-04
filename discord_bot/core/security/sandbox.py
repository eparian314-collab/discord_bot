"""
Sandboxing system for Discord bot security.

Provides sandboxing for potentially dangerous operations:
- External API calls
- File operations
- Code execution
- Database operations
- Network requests
"""
from __future__ import annotations

import os
import time
import tempfile
import subprocess
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable, Set
from dataclasses import dataclass
from pathlib import Path
from contextlib import asynccontextmanager

# Import optional dependencies
try:
    import aiohttp
    HAS_AIOHTTP = True
# except ImportError:
    HAS_AIOHTTP = False

try:
    import aiofiles
    HAS_AIOFILES = True
# except ImportError:
    HAS_AIOFILES = False

# Import resource module only on Unix-like systems
try:
    import resource
    HAS_RESOURCE = True
# except ImportError:
    HAS_RESOURCE = False


class SandboxViolation(Exception):
    """Raised when sandbox security is violated."""
    
    def __init__(self, message: str, violation_type: str, details: Optional[Dict] = None):
        self.violation_type = violation_type
        self.details = details or {}
        super().__init__(message)


@dataclass
class SandboxLimits:
    """Sandbox resource limits."""
    max_execution_time: float = 30.0  # seconds
    max_memory_mb: int = 128
    max_file_size_mb: int = 10
    max_network_requests: int = 10
    max_file_operations: int = 100
    allowed_domains: Set[str] = None
    blocked_domains: Set[str] = None
    allowed_file_extensions: Set[str] = None
    blocked_file_extensions: Set[str] = None
    
    def __post_init__(self):
        if self.allowed_domains is None:
            # Default allowed domains for bot operations
            self.allowed_domains = {
                "api.deepl.com",
                "api.mymemory.translated.net", 
                "pokeapi.co",
                "api.openai.com",
                "discord.com",
                "discordapp.com"
            }
        
        if self.blocked_domains is None:
            # Dangerous domains to block
            self.blocked_domains = {
                "localhost",
                "127.0.0.1",
                "0.0.0.0",
                "::1",
                "metadata.google.internal",  # Cloud metadata
                "169.254.169.254"  # AWS metadata
            }
        
        if self.allowed_file_extensions is None:
            self.allowed_file_extensions = {
                ".txt", ".json", ".csv", ".log", ".md",
                ".png", ".jpg", ".jpeg", ".gif", ".webp"
            }
        
        if self.blocked_file_extensions is None:
            self.blocked_file_extensions = {
                ".exe", ".bat", ".cmd", ".ps1", ".sh",
                ".py", ".js", ".php", ".rb", ".pl",
                ".dll", ".so", ".dylib"
            }


class SandboxManager:
    """
    Comprehensive sandboxing system for bot operations.
    
    Features:
    - Resource limiting
    - Network request filtering
    - File operation restrictions
    - Execution time limits
    - Memory usage monitoring
    """
    
    def __init__(self, limits: Optional[SandboxLimits] = None):
        self.limits = limits or SandboxLimits()
        self.active_operations: Dict[str, float] = {}  # operation_id -> start_time
        self.temp_directories: Set[Path] = set()
        
        # Statistics tracking
        self.stats = {
            "operations_started": 0,
            "operations_completed": 0,
            "operations_failed": 0,
            "violations_detected": 0,
            "bytes_transferred": 0,
            "files_created": 0,
            "network_requests_made": 0
        }
    
    def _generate_operation_id(self) -> str:
        """Generate unique operation ID."""
        return f"op_{int(time.time() * 1000000)}_{id(self)}"
    
    def _validate_url(self, url: str) -> None:
        """Validate URL against sandbox restrictions."""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            raise SandboxViolation(
                "Invalid URL: no hostname",
                "invalid_url",
                {"url": url}
            )
        
        # Check blocked domains
        for blocked in self.limits.blocked_domains:
            if blocked in hostname or hostname.startswith(blocked):
                raise SandboxViolation(
                    f"Blocked domain: {hostname}",
                    "blocked_domain",
                    {"hostname": hostname, "url": url}
                )
        
        # Check if domain is in allowed list (if specified)
        if self.limits.allowed_domains:
            allowed = False
            for allowed_domain in self.limits.allowed_domains:
                if hostname == allowed_domain or hostname.endswith(f".{allowed_domain}"):
                    allowed = True
                    break
            
            if not allowed:
                raise SandboxViolation(
                    f"Domain not in allowed list: {hostname}",
                    "domain_not_allowed",
                    {"hostname": hostname, "url": url}
                )
    
    def _validate_file_path(self, file_path: Union[str, Path]) -> Path:
        """Validate file path against sandbox restrictions."""
        path = Path(file_path).resolve()
        
        # Check file extension
        extension = path.suffix.lower()
        
        if extension in self.limits.blocked_file_extensions:
            raise SandboxViolation(
                f"Blocked file extension: {extension}",
                "blocked_extension",
                {"path": str(path), "extension": extension}
            )
        
        if self.limits.allowed_file_extensions and extension not in self.limits.allowed_file_extensions:
            raise SandboxViolation(
                f"File extension not allowed: {extension}",
                "extension_not_allowed",
                {"path": str(path), "extension": extension}
            )
        
        # Prevent path traversal
        try:
            # Ensure path is within current working directory or temp directories
            cwd = Path.cwd().resolve()
            temp_dirs = [Path(tempfile.gettempdir()).resolve()]
            temp_dirs.extend(self.temp_directories)
            
            allowed = False
            for allowed_dir in [cwd] + temp_dirs:
                try:
                    path.relative_to(allowed_dir)
                    allowed = True
                    break
                except ValueError:
                    continue
            
            if not allowed:
                raise SandboxViolation(
                    f"Path outside allowed directories: {path}",
                    "path_traversal",
                    {"path": str(path)}
                )
        
        except Exception as e:
            raise SandboxViolation(
                f"Path validation error: {e}",
                "path_validation_error",
                {"path": str(path)}
            )
        
        return path
    
    @asynccontextmanager
    async def sandbox_operation(self, operation_name: str):
        """Context manager for sandboxed operations."""
        operation_id = self._generate_operation_id()
        start_time = time.time()
        
        self.active_operations[operation_id] = start_time
        self.stats["operations_started"] += 1
        
        try:
            # Set resource limits (if on Unix-like system)
            if HAS_RESOURCE:
                # Memory limit
                memory_limit = self.limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
                
                # CPU time limit
                cpu_limit = int(self.limits.max_execution_time)
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
            
            # Yield control to the operation
            yield operation_id
            
            self.stats["operations_completed"] += 1
            
        except Exception as e:
            self.stats["operations_failed"] += 1
            if isinstance(e, SandboxViolation):
                self.stats["violations_detected"] += 1
            raise
        finally:
            # Clean up
            if operation_id in self.active_operations:
                del self.active_operations[operation_id]
            
            # Check execution time
            execution_time = time.time() - start_time
            if execution_time > self.limits.max_execution_time:
                raise SandboxViolation(
                    f"Operation exceeded time limit: {execution_time:.2f}s > {self.limits.max_execution_time}s",
                    "time_limit_exceeded",
                    {"execution_time": execution_time, "limit": self.limits.max_execution_time}
                )
    
    async def safe_http_request(
        self, 
        method: str, 
        url: str, 
        **kwargs
    ) -> Any:
        """Make a sandboxed HTTP request."""
        if not HAS_AIOHTTP:
            raise SandboxViolation(
                "HTTP requests not available - aiohttp not installed",
                "missing_dependency"
            )
        
        async with self.sandbox_operation("http_request"):
            # Validate URL
            self._validate_url(url)
            
            # Set timeout
            timeout = aiohttp.ClientTimeout(total=self.limits.max_execution_time)
            kwargs.setdefault('timeout', timeout)
            
            # Track request
            self.stats["network_requests_made"] += 1
            
            async with aiohttp.ClientSession() as session:
                response = await session.request(method, url, **kwargs)
                
                # Check response size
                content_length = response.headers.get('content-length')
                if content_length:
                    size_mb = int(content_length) / (1024 * 1024)
                    if size_mb > self.limits.max_file_size_mb:
                        await response.close()
                        raise SandboxViolation(
                            f"Response too large: {size_mb:.2f}MB > {self.limits.max_file_size_mb}MB",
                            "response_too_large",
                            {"size_mb": size_mb, "limit_mb": self.limits.max_file_size_mb}
                        )
                
                self.stats["bytes_transferred"] += len(await response.read())
                return response
    
    async def safe_file_read(self, file_path: Union[str, Path], max_size: Optional[int] = None) -> str:
        """Safely read a file with size limits."""
        async with self.sandbox_operation("file_read"):
            validated_path = self._validate_file_path(file_path)
            
            # Check file size
            if validated_path.exists():
                file_size = validated_path.stat().st_size
                max_bytes = max_size or (self.limits.max_file_size_mb * 1024 * 1024)
                
                if file_size > max_bytes:
                    raise SandboxViolation(
                        f"File too large: {file_size} bytes > {max_bytes} bytes",
                        "file_too_large",
                        {"file_size": file_size, "max_size": max_bytes, "path": str(validated_path)}
                    )
            
            if HAS_AIOFILES:
                async with aiofiles.open(validated_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
            else:
                # Fallback to synchronous file operations
                with open(validated_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
            return content
    
    async def safe_file_write(
        self, 
        file_path: Union[str, Path], 
        content: str, 
        max_size: Optional[int] = None
    ) -> None:
        """Safely write to a file with size limits."""
        async with self.sandbox_operation("file_write"):
            validated_path = self._validate_file_path(file_path)
            
            # Check content size
            content_bytes = content.encode('utf-8')
            max_bytes = max_size or (self.limits.max_file_size_mb * 1024 * 1024)
            
            if len(content_bytes) > max_bytes:
                raise SandboxViolation(
                    f"Content too large: {len(content_bytes)} bytes > {max_bytes} bytes",
                    "content_too_large",
                    {"content_size": len(content_bytes), "max_size": max_bytes}
                )
            
            # Ensure directory exists
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            
            if HAS_AIOFILES:
                async with aiofiles.open(validated_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
            else:
                # Fallback to synchronous file operations
                with open(validated_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            self.stats["files_created"] += 1
    
    @asynccontextmanager
    async def temp_directory(self):
        """Create a temporary directory for sandboxed operations."""
        temp_dir = Path(tempfile.mkdtemp(prefix="bot_sandbox_"))
        self.temp_directories.add(temp_dir)
        
        try:
            yield temp_dir
        finally:
            # Clean up
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            
            self.temp_directories.discard(temp_dir)
    
    async def safe_subprocess(
        self, 
        command: List[str], 
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None
    ) -> subprocess.CompletedProcess:
        """Execute a subprocess in sandbox."""
        async with self.sandbox_operation("subprocess"):
            # Validate command
            if not command or not command[0]:
                raise SandboxViolation(
                    "Invalid command",
                    "invalid_command",
                    {"command": command}
                )
            
            # Block dangerous commands
            dangerous_commands = {
                'rm', 'del', 'format', 'fdisk', 'dd', 'mkfs',
                'wget', 'curl', 'nc', 'netcat', 'telnet',
                'ssh', 'scp', 'rsync', 'sudo', 'su'
            }
            
            command_name = Path(command[0]).name.lower()
            if command_name in dangerous_commands:
                raise SandboxViolation(
                    f"Dangerous command blocked: {command_name}",
                    "dangerous_command",
                    {"command": command}
                )
            
            # Set safe environment
            safe_env = {
                'PATH': os.environ.get('PATH', ''),
                'HOME': os.environ.get('HOME', ''),
                'USER': os.environ.get('USER', ''),
                'LANG': os.environ.get('LANG', 'en_US.UTF-8')
            }
            
            if env:
                # Only allow specific environment variables
                allowed_env_vars = {'PYTHONPATH', 'TEMP', 'TMP'}
                for key, value in env.items():
                    if key in allowed_env_vars:
                        safe_env[key] = value
            
            # Execute with timeout
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=cwd,
                    env=safe_env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.limits.max_execution_time
                )
                
                return subprocess.CompletedProcess(
                    command, process.returncode, stdout, stderr
                )
                
            except asyncio.TimeoutError:
                if process:
                    process.kill()
                    await process.wait()
                
                raise SandboxViolation(
                    f"Subprocess timed out after {self.limits.max_execution_time}s",
                    "subprocess_timeout",
                    {"command": command, "timeout": self.limits.max_execution_time}
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sandbox usage statistics."""
        return {
            **self.stats,
            "active_operations": len(self.active_operations),
            "temp_directories": len(self.temp_directories),
            "uptime": time.time() - (min(self.active_operations.values()) if self.active_operations else time.time())
        }
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            "operations_started": 0,
            "operations_completed": 0,
            "operations_failed": 0,
            "violations_detected": 0,
            "bytes_transferred": 0,
            "files_created": 0,
            "network_requests_made": 0
        }


# Global sandbox manager instance
sandbox_manager = SandboxManager()


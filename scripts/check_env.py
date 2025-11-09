#!/usr/bin/env python3
"""
Environment Validation Script for HippoBot.

Validates runtime environment before launch:
- Python version
- Required dependencies
- Environment configuration
- File system structure
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def check_python_version() -> Tuple[bool, str]:
    """Check if Python version is >= 3.10."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        return True, f"{version.major}.{version.minor}.{version.micro}"
    return False, f"{version.major}.{version.minor}.{version.micro} (requires >= 3.10)"


def check_dependencies() -> Dict[str, Tuple[bool, str]]:
    """Check if all required dependencies are installed."""
    dependencies = {
        "discord.py": "discord",
        "Pillow": "PIL",
        "aiohttp": "aiohttp",
        "python-dotenv": "dotenv",
        "pytest": "pytest",
        "pytest-asyncio": "pytest_asyncio",
    }
    
    results = {}
    for name, module_name in dependencies.items():
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "unknown")
            results[name] = (True, version)
        except ImportError:
            results[name] = (False, "not installed")
    
    return results


def check_env_file() -> Tuple[bool, List[str]]:
    """Check if .env file exists and contains required keys."""
    env_file = Path(__file__).parent.parent / ".env"
    
    if not env_file.exists():
        return False, [".env file not found"]
    
    required_keys = [
        "DISCORD_TOKEN",
        "DEEPL_API_KEY",
        "MY_MEMORY_API_KEY",
    ]
    
    missing = []
    with open(env_file, "r", encoding="utf-8") as f:
        content = f.read()
        for key in required_keys:
            if key not in content or f"{key}=" not in content:
                missing.append(key)
    
    return len(missing) == 0, missing


def check_directory_structure() -> Dict[str, bool]:
    """Check if required directories exist."""
    base = Path(__file__).parent.parent
    
    required_dirs = {
        "cogs": base / "cogs",
        "core": base / "core",
        "core/engines": base / "core" / "engines",
        "games": base / "games",
        "integrations": base / "integrations",
        "language_context": base / "language_context",
        "data": base / "data",
        "logs": base / "logs",
        "tests": base / "tests",
        "scripts": base / "scripts",
    }
    
    return {name: path.exists() for name, path in required_dirs.items()}


def check_critical_files() -> Dict[str, bool]:
    """Check if critical files exist."""
    base = Path(__file__).parent.parent
    
    critical_files = {
        "main.py": base / "main.py",
        "__main__.py": base / "__main__.py",
        "integration_loader.py": base / "integrations" / "integration_loader.py",
        "requirements.txt": base / "requirements.txt",
        "pytest.ini": base / "pytest.ini",
    }
    
    return {name: path.exists() for name, path in critical_files.items()}


def print_check(name: str, passed: bool, details: str = "") -> None:
    """Print a formatted check result."""
    symbol = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    detail_str = f" ({details})" if details else ""
    print(f"  {symbol} {name}{detail_str}")


def main() -> int:
    """Run all environment checks."""
    print("=" * 60)
    print("HippoBot Environment Validation")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # Check Python version
    print("📌 Python Version:")
    passed, version = check_python_version()
    print_check(f"Python {version}", passed)
    all_passed = all_passed and passed
    print()
    
    # Check dependencies
    print("📦 Dependencies:")
    deps = check_dependencies()
    for name, (passed, version) in deps.items():
        print_check(name, passed, version)
        all_passed = all_passed and passed
    print()
    
    # Check .env file
    print("🔐 Environment Configuration:")
    env_passed, missing = check_env_file()
    if env_passed:
        print_check(".env file", True, "all required keys present")
    else:
        print_check(".env file", False, f"missing: {', '.join(missing)}")
        all_passed = False
    print()
    
    # Check directory structure
    print("📁 Directory Structure:")
    dirs = check_directory_structure()
    for name, exists in dirs.items():
        print_check(name, exists)
        all_passed = all_passed and exists
    print()
    
    # Check critical files
    print("📄 Critical Files:")
    files = check_critical_files()
    for name, exists in files.items():
        print_check(name, exists)
        all_passed = all_passed and exists
    print()
    
    # Summary
    print("=" * 60)
    if all_passed:
        print(f"{GREEN}✅ All checks passed! Ready to launch.{RESET}")
        return 0
    else:
        print(f"{RED}❌ Some checks failed. Please fix issues before launching.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

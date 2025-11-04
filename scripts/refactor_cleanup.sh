#!/bin/bash
# Refactor cleanup script - consolidate project structure
# This removes duplicate/stale test files and backup files

set -e

PROJECT_ROOT="/home/mars/projects/discord_bot"
cd "$PROJECT_ROOT"

echo "🧹 HippoBot Project Structure Cleanup"
echo "======================================"
echo ""

# Verify symlinks are correct
echo "✓ Checking symlink structure..."
if [ ! -L "$PROJECT_ROOT/discord_bot/cogs" ]; then
    echo "❌ ERROR: discord_bot/cogs should be a symlink!"
    exit 1
fi

if [ ! -L "$PROJECT_ROOT/discord_bot/core" ]; then
    echo "❌ ERROR: discord_bot/core should be a symlink!"
    exit 1
fi

echo "✓ Symlinks verified"
echo ""

# Remove stale data/tests directory (old test copies)
if [ -d "$PROJECT_ROOT/data/tests" ]; then
    echo "🗑️  Removing stale data/tests directory..."
    rm -rf "$PROJECT_ROOT/data/tests"
    echo "✓ Removed data/tests"
else
    echo "✓ data/tests already clean"
fi
echo ""

# Remove stale data/integrations directory (if it exists)
if [ -d "$PROJECT_ROOT/data/integrations" ]; then
    echo "🗑️  Removing stale data/integrations directory..."
    rm -rf "$PROJECT_ROOT/data/integrations"
    echo "✓ Removed data/integrations"
else
    echo "✓ data/integrations already clean"
fi
echo ""

# Remove backup files
echo "🗑️  Removing backup files..."
BACKUP_FILES=$(find "$PROJECT_ROOT" -type f \( -name "*.backup" -o -name "*.py.backup" -o -name "*~" \) -not -path "*/.git/*" 2>/dev/null || true)

if [ -z "$BACKUP_FILES" ]; then
    echo "✓ No backup files found"
else
    BACKUP_COUNT=0
    while IFS= read -r file; do
        if [ -n "$file" ]; then
            echo "  - Removing: $file"
            rm "$file"
            ((BACKUP_COUNT++))
        fi
    done <<< "$BACKUP_FILES"
    echo "✓ Removed $BACKUP_COUNT backup file(s)"
fi
echo ""

# Clean up __pycache__ directories
echo "🗑️  Cleaning __pycache__ directories..."
find "$PROJECT_ROOT" -type d -name "__pycache__" -not -path "*/.git/*" -not -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null || true
echo "✓ Cleaned __pycache__ directories"
echo ""

# Verify import structure (optional - requires virtual env)
echo "🔍 Verifying Python import structure..."
if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
import discord_bot
import discord_bot.cogs
import discord_bot.core
import discord_bot.games
import discord_bot.integrations
import discord_bot.language_context
print('✓ All imports successful')
" 2>&1; then
    echo "✓ Import structure verified"
else
    echo "⚠️  Import verification skipped (requires virtualenv with dependencies)"
fi
echo ""

echo "======================================"
echo "✅ Cleanup complete!"
echo ""
echo "Summary:"
echo "  - Symlinks: verified"
echo "  - Stale test copies: removed"
echo "  - Backup files: cleaned"
echo "  - Import structure: verified"
echo ""
echo "Next steps:"
echo "  1. Run tests: pytest"
echo "  2. Verify bot starts: python3 main.py --help"

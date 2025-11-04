# ========================================
# Git Auto Commit & Push Script
# Location: your project root (discord_bot)
# Usage: run this inside PowerShell while venv is active
# ========================================

# Activate virtual environment (optional but nice to include)
$venvPath = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    Write-Host "✅ Virtual environment activated."
} else {
    Write-Host "⚠️  No virtual environment found at $venvPath"
}

# Stage all changes                      RUN WITH ---> .\data\scripts\push_update.ps1

git add .

# Create timestamped commit message
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$commitMessage = "🧠 Auto update ($timestamp): Sync latest engine/data/test changes"
git commit -m "$commitMessage"

# Sync with remote main before push
git pull origin main --no-rebase

# Push changes to GitHub
git push origin main

Write-Host "🚀 Successfully pushed updates to GitHub at $timestamp"

# Quick Start Script for HippoBot
# Run this with: .\start_bot.ps1

Write-Host "🦛 Starting HippoBot..." -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Check if activation was successful
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "   Make sure .venv exists: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Starting bot..." -ForegroundColor Yellow
Write-Host ""

# Run the bot
python -m discord_bot.main

# Keep window open on error
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Red
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

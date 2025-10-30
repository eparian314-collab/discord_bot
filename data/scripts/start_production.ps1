# Production Bot Startup Script
# Handles restarts and keeps bot running

Write-Host "🦛 Starting HippoBot in production mode..." -ForegroundColor Cyan

# Activate virtual environment
& ".\discord_bot\.venv\Scripts\Activate.ps1"

# Infinite restart loop
$restartCount = 0
while ($true) {
    $restartCount++
    
    if ($restartCount -gt 1) {
        Write-Host "`n⚠️  Bot crashed! Restarting (attempt $restartCount)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
    
    Write-Host "`n🚀 Starting bot..." -ForegroundColor Green
    
    # Run the bot
    cd discord_bot
    python -m discord_bot.main
    
    $exitCode = $LASTEXITCODE
    
    # If clean shutdown (Ctrl+C), exit
    if ($exitCode -eq 0) {
        Write-Host "`n✅ Bot shut down cleanly." -ForegroundColor Green
        break
    }
    
    # If too many restarts, pause
    if ($restartCount -gt 10) {
        Write-Host "`n❌ Too many crashes! Pausing for 5 minutes..." -ForegroundColor Red
        Start-Sleep -Seconds 300
        $restartCount = 0
    }
}

Write-Host "`n👋 Bot stopped." -ForegroundColor Cyan

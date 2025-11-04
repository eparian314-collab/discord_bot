<#
.SYNOPSIS
    Quick EC2 bot status checker

.DESCRIPTION
    Check if your bot is running on EC2 without deploying

.EXAMPLE
    .\check_ec2_status.ps1
#>

param(
    [string]$EC2Host = "",
    [string]$EC2User = "ubuntu",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\hippobot-ec2.pem"
)

# Get EC2 host from .env if not provided
if (-not $EC2Host -and (Test-Path ".env")) {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match 'EC2_HOST=(.+)') {
        $EC2Host = $Matches[1].Trim()
    }
}

if (-not $EC2Host) {
    Write-Host "❌ EC2_HOST not found. Set it in .env or use -EC2Host parameter" -ForegroundColor Red
    exit 1
}

Write-Host "`n🔍 Checking HippoBot status on $EC2Host...`n" -ForegroundColor Cyan

$checkCommands = @"
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo '🦛 HIPPOBOT EC2 STATUS REPORT'
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
echo ''

echo '📊 Bot Process Status:'
if ps aux | grep -v grep | grep 'python.*main.py' > /dev/null; then
    echo '✅ Bot is RUNNING'
    ps aux | grep -v grep | grep 'python.*main.py' | awk '{print \"   PID: \" \$2 \" | CPU: \" \$3\"% | MEM: \" \$4\"%\"}'
else
    echo '❌ Bot is NOT running'
fi

echo ''
echo '📂 Disk Usage:'
df -h ~/discord_bot | tail -1 | awk '{print \"   \" \$5 \" used of \" \$2}'

echo ''
echo '🔄 Current Branch:'
cd ~/discord_bot && git branch --show-current

echo ''
echo '📝 Last Commit:'
cd ~/discord_bot && git log -1 --pretty=format:'   %h - %s (%cr)'

echo ''
echo '📊 Recent Log Entries (last 10 lines):'
if [ -f ~/discord_bot/logs/bot.log ]; then
    tail -10 ~/discord_bot/logs/bot.log | sed 's/^/   /'
else
    echo '   ⚠️  No log file found'
fi

echo ''
echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
"@

ssh -i $KeyPath -o StrictHostKeyChecking=no "$EC2User@$EC2Host" $checkCommands

Write-Host "`n💡 Quick Commands:" -ForegroundColor Cyan
Write-Host "   View live logs:  ssh -i $KeyPath $EC2User@$EC2Host 'tail -f ~/discord_bot/logs/bot.log'"
Write-Host "   Restart bot:     .\deploy_to_ec2.ps1"
Write-Host "   Stop bot:        ssh -i $KeyPath $EC2User@$EC2Host 'pkill -f python.*main.py'"
Write-Host ""

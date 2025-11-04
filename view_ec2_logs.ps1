<#
.SYNOPSIS
    View HippoBot logs from EC2 in real-time

.DESCRIPTION
    Opens a live tail of your bot logs on EC2

.PARAMETER Lines
    Number of lines to show initially (default: 50)

.EXAMPLE
    .\view_ec2_logs.ps1
    
.EXAMPLE
    .\view_ec2_logs.ps1 -Lines 100
#>

param(
    [int]$Lines = 50,
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

Write-Host @"

╔════════════════════════════════════════════════════════════╗
║          🦛 HIPPOBOT EC2 LIVE LOGS VIEWER 🦛              ║
╚════════════════════════════════════════════════════════════╝

Connecting to: $EC2Host
Showing last $Lines lines, then live updates...
Press Ctrl+C to exit

"@ -ForegroundColor Cyan

ssh -i $KeyPath -o StrictHostKeyChecking=no "$EC2User@$EC2Host" "tail -n $Lines -f ~/discord_bot/logs/bot.log"

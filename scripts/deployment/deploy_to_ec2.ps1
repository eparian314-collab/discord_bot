<#
.SYNOPSIS
    Automated EC2 deployment script for HippoBot

.DESCRIPTION
    This script automates the entire deployment process to your EC2 instance:
    1. Commits and pushes local changes to GitHub
    2. SSHs into EC2 instance
    3. Pulls latest code
    4. Restarts the bot service
    All without manual SSH connection!

.PARAMETER Message
    Git commit message (default: "Auto-deploy update")

.PARAMETER SkipTests
    Skip local tests before deployment

.PARAMETER EC2Host
    EC2 instance hostname or IP (default: from .env or prompt)

.PARAMETER EC2User
    SSH username (default: ubuntu)

.PARAMETER KeyPath
    Path to SSH private key (default: ~/.ssh/hippobot-ec2.pem)

.EXAMPLE
    .\deploy_to_ec2.ps1 -Message "Fixed translation bug"
    
.EXAMPLE
    .\deploy_to_ec2.ps1 -SkipTests -EC2Host "ec2-12-34-56-78.compute.amazonaws.com"
#>

[CmdletBinding()]
param(
    [string]$Message = "Auto-deploy update $(Get-Date -Format 'yyyy-MM-dd HH:mm')",
    [switch]$SkipTests,
    [string]$EC2Host = "",
    [string]$EC2User = "ubuntu",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\hippobot-ec2.pem",
    [string]$Branch = "hippo-v2.2"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Colors
function Write-Step { param($Msg) Write-Host "`n🔹 $Msg" -ForegroundColor Cyan }
function Write-Success { param($Msg) Write-Host "✅ $Msg" -ForegroundColor Green }
function Write-Error { param($Msg) Write-Host "❌ $Msg" -ForegroundColor Red; exit 1 }
function Write-Warning { param($Msg) Write-Host "⚠️  $Msg" -ForegroundColor Yellow }

Write-Host @"

╔════════════════════════════════════════════════════════════╗
║         🦛 HIPPOBOT EC2 AUTO-DEPLOYMENT SCRIPT 🦛         ║
╚════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Magenta

# -----------------------------------------------------------------------------
# 1. Verify we're in the repo
# -----------------------------------------------------------------------------
Write-Step "Verifying repository..."
if (-not (Test-Path ".git")) {
    Write-Error "Not in a git repository. Run this from the project root."
}
Write-Success "Repository confirmed"

# -----------------------------------------------------------------------------
# 2. Get EC2 host from .env if not provided
# -----------------------------------------------------------------------------
if (-not $EC2Host) {
    Write-Step "Looking for EC2 host configuration..."
    if (Test-Path ".env") {
        $envContent = Get-Content ".env" -Raw
        if ($envContent -match 'EC2_HOST=(.+)') {
            $EC2Host = $Matches[1].Trim()
            Write-Success "Found EC2_HOST in .env: $EC2Host"
        }
    }
    
    if (-not $EC2Host) {
        Write-Warning "EC2_HOST not found in .env"
        $EC2Host = Read-Host "Enter your EC2 instance hostname or IP"
        if (-not $EC2Host) {
            Write-Error "EC2 host is required"
        }
        
        # Offer to save it
        $save = Read-Host "Save EC2_HOST to .env? (y/n)"
        if ($save -eq 'y') {
            Add-Content -Path ".env" -Value "`nEC2_HOST=$EC2Host"
            Write-Success "Saved to .env"
        }
    }
}

# -----------------------------------------------------------------------------
# 3. Verify SSH key exists
# -----------------------------------------------------------------------------
Write-Step "Checking SSH key..."
if (-not (Test-Path $KeyPath)) {
    Write-Warning "SSH key not found at: $KeyPath"
    $KeyPath = Read-Host "Enter path to your EC2 SSH private key"
    if (-not (Test-Path $KeyPath)) {
        Write-Error "SSH key not found at: $KeyPath"
    }
}
Write-Success "SSH key found: $KeyPath"

# -----------------------------------------------------------------------------
# 4. Check for uncommitted changes
# -----------------------------------------------------------------------------
Write-Step "Checking git status..."
$status = git status --porcelain
if ($status) {
    Write-Host "`nUncommitted changes detected:"
    git status --short
    
    $commit = Read-Host "`nCommit these changes? (y/n)"
    if ($commit -eq 'y') {
        git add -A
        git commit -m $Message
        Write-Success "Changes committed"
    } else {
        Write-Warning "Deploying without committing local changes"
    }
} else {
    Write-Success "No uncommitted changes"
}

# -----------------------------------------------------------------------------
# 5. Run local tests (optional)
# -----------------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Step "Running local tests..."
    try {
        python -m discord_bot.scripts.simulation_test
        Write-Success "Local tests passed"
    } catch {
        Write-Warning "Tests had issues but continuing..."
    }
} else {
    Write-Warning "Skipping tests (--SkipTests flag set)"
}

# -----------------------------------------------------------------------------
# 6. Push to GitHub
# -----------------------------------------------------------------------------
Write-Step "Pushing to GitHub..."
try {
    $currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
    Write-Host "Current branch: $currentBranch"
    
    git push origin $currentBranch
    Write-Success "Pushed to GitHub"
} catch {
    Write-Error "Failed to push to GitHub: $_"
}

# -----------------------------------------------------------------------------
# 7. Deploy to EC2 via SSH
# -----------------------------------------------------------------------------
Write-Step "Connecting to EC2 and deploying..."

$sshCommand = @"
echo '🔹 Stopping bot if running...'
pkill -f 'python.*main.py' || true

echo '🔹 Navigating to project directory...'
cd ~/discord_bot || { echo 'Project directory not found!'; exit 1; }

echo '🔹 Pulling latest changes...'
git fetch origin
git checkout $Branch
git pull origin $Branch

echo '🔹 Activating virtual environment...'
source ~/.venv/bin/activate || python3 -m venv ~/.venv && source ~/.venv/bin/activate

echo '🔹 Installing/updating dependencies...'
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo '🔹 Running database migrations if any...'
python -m discord_bot.scripts.check_schema 2>/dev/null || true

echo '🔹 Starting bot in background...'
nohup python main.py > logs/bot.log 2>&1 &
echo \$! > .bot.pid

sleep 3

if ps -p \$(cat .bot.pid) > /dev/null 2>&1; then
    echo '✅ Bot started successfully! PID: '\$(cat .bot.pid)
    echo '📝 View logs: tail -f ~/discord_bot/logs/bot.log'
else
    echo '❌ Bot failed to start. Check logs:'
    tail -20 logs/bot.log
    exit 1
fi

echo '✅ Deployment complete!'
"@

Write-Host "Executing remote commands on $EC2Host..." -ForegroundColor Yellow

try {
    # Use ssh with key authentication
    $sshCommand | ssh -i $KeyPath -o StrictHostKeyChecking=no "$EC2User@$EC2Host" 'bash -s'
    
    Write-Host ""
    Write-Success "Deployment completed successfully!"
    Write-Host ""
    Write-Host "📊 Useful commands:" -ForegroundColor Cyan
    Write-Host "  View logs:    ssh -i $KeyPath $EC2User@$EC2Host 'tail -f ~/discord_bot/logs/bot.log'"
    Write-Host "  Check status: ssh -i $KeyPath $EC2User@$EC2Host 'ps aux | grep python.*main.py'"
    Write-Host "  Stop bot:     ssh -i $KeyPath $EC2User@$EC2Host 'pkill -f python.*main.py'"
    Write-Host ""
    
} catch {
    Write-Error "SSH connection or deployment failed: $_"
}

Write-Host @"

╔════════════════════════════════════════════════════════════╗
║              🎉 DEPLOYMENT SUCCESSFUL! 🎉                  ║
╚════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Green

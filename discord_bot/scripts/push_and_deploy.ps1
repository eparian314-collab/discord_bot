<#
.SYNOPSIS
    Push current changes, run validation layers, and trigger deploy.sh.

.DESCRIPTION
    Mirrors the behaviour of push_and_deploy.sh but in native PowerShell.
    - Verifies git workspace cleanliness
    - Pushes the current branch to origin
    - Runs preflight checks and pytest (when available)
    - Invokes scripts/deploy.sh for downstream validation/deployment

.PARAMETER SkipCooldown
    If set, DEPLOY_SKIP_COOLDOWN=1 will be exported while invoking deploy.sh.
#>

[CmdletBinding()]
param(
    [switch]$SkipCooldown
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
function Write-Info  { param($Message) Write-Host "[INFO]  $Message" -ForegroundColor Green }
function Write-Warn  { param($Message) Write-Host "[WARN]  $Message" -ForegroundColor Yellow }
function Write-ErrorAndExit {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------------------------
# Resolve paths
# -----------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir   = if ($env:REPO_DIR_OVERRIDE) { $env:REPO_DIR_OVERRIDE } else { Split-Path -Parent $ScriptDir }

if (-not (Test-Path $RepoDir)) {
    Write-ErrorAndExit "Repository directory '$RepoDir' does not exist."
}

Set-Location $RepoDir

if (-not (Test-Path ".git")) {
    Write-ErrorAndExit "This script must be executed inside a Git repository."
}

# -----------------------------------------------------------------------------
# Determine Python interpreter
# -----------------------------------------------------------------------------
$venvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $Python = $venvPython
    Write-Info "Using virtual environment Python at $Python"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = (Get-Command python).Path
    Write-Warn "Virtual environment not found. Falling back to '$Python'."
} else {
    Write-ErrorAndExit "Python interpreter not found. Create .venv or install python in PATH."
}

# -----------------------------------------------------------------------------
# Git checks
# -----------------------------------------------------------------------------
try {
    $currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
} catch {
    Write-ErrorAndExit "Unable to determine current Git branch."
}

if ($currentBranch -eq 'HEAD') {
    Write-ErrorAndExit "Detached HEAD state detected. Checkout a branch before deploying."
}

$status = git status --porcelain --untracked-files=normal
if ($status) {
    Write-Host $status
    Write-ErrorAndExit "Working tree is not clean. Commit or stash changes before deploying."
}

# -----------------------------------------------------------------------------
# Push to remote
# -----------------------------------------------------------------------------
Write-Info "Pushing branch '$currentBranch' to origin..."
try {
    git push origin $currentBranch
} catch {
    Write-ErrorAndExit "Git push failed: $_"
}

# -----------------------------------------------------------------------------
# Run preflight checks
# -----------------------------------------------------------------------------
Write-Info "Running preflight checks..."
try {
    & $Python "scripts/preflight_check.py"
} catch {
    Write-ErrorAndExit "Preflight checks failed."
}

# -----------------------------------------------------------------------------
# Run pytest (if available)
# -----------------------------------------------------------------------------
$pytestAvailable = $false
try {
    & $Python -m pytest --version *> $null
    $pytestAvailable = $true
} catch {
    Write-Warn "pytest not available - skipping test suite."
}

if ($pytestAvailable) {
    Write-Info "Running pytest suite..."
    try {
        & $Python -m pytest "tests/" -v --tb=short
    } catch {
        Write-ErrorAndExit "Pytest suite failed."
    }
}

# -----------------------------------------------------------------------------
# Trigger deploy.sh (via bash)
# -----------------------------------------------------------------------------
$deployScript = Join-Path $ScriptDir "deploy.sh"
if (-not (Test-Path $deployScript)) {
    Write-ErrorAndExit "Deployment script '$deployScript' not found."
}

if (-not (Get-Command bash -ErrorAction SilentlyContinue)) {
    Write-ErrorAndExit "Bash executable not found. Install Git Bash or WSL to run deploy.sh."
}

Write-Info "Invoking deploy.sh for additional validation..."
$originalCooldown = $env:DEPLOY_SKIP_COOLDOWN
if ($SkipCooldown) {
    $env:DEPLOY_SKIP_COOLDOWN = "1"
}

try {
    & bash "$deployScript"
} catch {
    Write-ErrorAndExit "deploy.sh reported a failure."
} finally {
    if ($SkipCooldown) {
        if ($null -ne $originalCooldown) {
            $env:DEPLOY_SKIP_COOLDOWN = $originalCooldown
        } else {
            Remove-Item Env:DEPLOY_SKIP_COOLDOWN -ErrorAction SilentlyContinue
        }
    }
}

Write-Info "Push and deployment pipeline completed successfully."

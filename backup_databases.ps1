# Database Backup Script
# Run this daily or before major updates

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupDir = ".\backups\$timestamp"

Write-Host "Creating backup directory: $backupDir"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

# Backup all .db files
Get-ChildItem -Filter "*.db" | ForEach-Object {
    $destFile = Join-Path $backupDir $_.Name
    Write-Host "Backing up $($_.Name)..."
    Copy-Item $_.FullName -Destination $destFile
}

Write-Host "✅ Backup complete!"
Write-Host "Location: $backupDir"

# Keep only last 7 days of backups
Get-ChildItem -Path ".\backups" -Directory | 
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-7) } | 
    Remove-Item -Recurse -Force

Write-Host "✅ Cleaned up old backups (kept last 7 days)"

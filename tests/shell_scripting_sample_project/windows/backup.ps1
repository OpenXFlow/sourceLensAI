# backup.ps1 - Creates a backup archive on Windows.

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupDestination,
    
    [Parameter(Mandatory=$true)]
    [string]$AppSource
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFileName = "app_backup_$timestamp.zip"
$backupFilePath = Join-Path -Path $BackupDestination -ChildPath $backupFileName

Write-Host "--- Creating backup archive ---"

# Using .NET for compression as it's built-in
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path $backupFilePath) { Remove-Item $backupFilePath }
[System.IO.Compression.ZipFile]::CreateFromDirectory($AppSource, $backupFilePath)

Write-Host "Backup created successfully at $backupFilePath"
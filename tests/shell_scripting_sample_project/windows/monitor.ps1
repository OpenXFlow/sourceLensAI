# monitor.ps1 - Checks the status of Windows services.

$services = @("W3SVC", "MSSQLSERVER") # IIS and SQL Server example names
$allRunning = $true

Write-Host "--- Monitoring Windows Services ---"

foreach ($serviceName in $services) {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq "Running") {
        Write-Host "✅ STATUS: $serviceName is Running."
    } else {
        Write-Host "🔴 STATUS: $serviceName is NOT running or does not exist." -ForegroundColor Red
        $allRunning = $false
    }
}

if (-not $allRunning) {
    Write-Error "One or more critical services are stopped."
    exit 1
}

Write-Host "All critical services are running."
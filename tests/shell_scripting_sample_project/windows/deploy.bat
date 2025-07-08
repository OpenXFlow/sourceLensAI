@echo off
REM deploy.bat - Simple deployment script for Windows.

set APP_DIR="C:\inetpub\wwwroot\my_app"

echo --- Deploying to %APP_DIR% ---

if not exist %APP_DIR% (
    echo Creating directory %APP_DIR%
    mkdir %APP_DIR%
)

echo Simulating file copy...
REM xcopy /E /I /Y "path\to\source" %APP_DIR%

echo Simulating application pool restart...
REM C:\Windows\System32\inetsrv\appcmd.exe recycle apppool /apppool.name:"MyAppPool"

echo Deployment finished.
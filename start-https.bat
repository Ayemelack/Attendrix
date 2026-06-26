@echo off
title Attendrix HTTPS Server
cd /d "%~dp0"

REM Auto-elevate to Admin if not already (needed for CA install + firewall rule)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs -Wait"
    exit /b %errorlevel%
)

echo ============================================
echo  Attendrix - HTTPS Development Server
echo ============================================
echo.
echo This starts Attendrix with HTTPS enabled for
echo mobile camera (getUserMedia) access over LAN.
echo.

REM Run HTTPS cert setup (idempotent)
powershell -ExecutionPolicy Bypass -File "%~dp0tools\setup-https.ps1" -InstallCA >nul 2>&1

REM Ensure firewall allows inbound TCP 5443
netsh advfirewall firewall add rule name="Attendrix HTTPS 5443" dir=in action=allow protocol=TCP localport=5443 >nul 2>&1

set HTTPS_PORT=5443

py app.py

pause

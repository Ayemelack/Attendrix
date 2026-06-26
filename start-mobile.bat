@echo off
setlocal enabledelayedexpansion
title Attendrix Mobile Server
cd /d "%~dp0"

REM Auto-elevate to Admin if not already (needed for CA install + firewall rule)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs -Wait"
    exit /b %errorlevel%
)

echo ============================================
echo  Attendrix - Mobile LAN Access (HTTPS)
echo ============================================
echo.
echo This starts Attendrix with HTTPS for mobile testing.
echo Camera access on mobile browsers requires HTTPS.
echo.

REM [1/3] HTTPS certificate setup (idempotent)
echo [1/3] Setting up trusted HTTPS certificates...
powershell -ExecutionPolicy Bypass -File "%~dp0tools\setup-https.ps1" -InstallCA
if %errorlevel% neq 0 (
    echo [WARNING] Certificate setup had issues. Continuing anyway...
)
echo.

REM [2/3] Windows Firewall — ensure inbound TCP 5443 is open for LAN access
echo [2/3] Configuring Windows Firewall for port 5443...
netsh advfirewall firewall add rule name="Attendrix HTTPS 5443" dir=in action=allow protocol=TCP localport=5443 >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Firewall rule added/confirmed for TCP port 5443
) else (
    echo   [WARNING] Could not configure firewall. Try running as Administrator.
)
echo.

REM [3/3] Start HTTPS server — app.py will detect LAN IPs and print the URL
echo [3/3] Starting Attendrix HTTPS server...
echo.
set HTTPS_PORT=5443

py app.py

pause

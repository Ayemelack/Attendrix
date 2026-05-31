@echo off
setlocal enabledelayedexpansion
title Attendrix Mobile Server
echo ============================================
echo  Attendrix - Mobile LAN Access (HTTPS)
echo ============================================
echo.
echo This starts Attendrix with HTTPS for mobile testing.
echo Camera access on mobile browsers requires HTTPS.
echo.

REM Run HTTPS cert setup first (idempotent — safe to run every time)
echo [1/3] Setting up trusted HTTPS certificates...
powershell -ExecutionPolicy Bypass -File "%~dp0tools\setup-https.ps1" -InstallCA
if %errorlevel% neq 0 (
    echo [WARNING] Certificate setup had issues. Continuing anyway...
)
echo.

REM Detect and display all LAN IPs
echo [2/3] Detecting network addresses...
echo.
echo Mobile access URLs:
set COUNT=0
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set "IP=%%a"
    set "IP=!IP: =!"
    set /a COUNT+=1
    echo   !COUNT!. https://!IP!:5443
)
echo.
echo NOTE: On first visit, your browser may show a warning.
echo       This is normal for development certificates.
echo.
echo       Android Chrome: tap "Proceed to site" (unsafe)
echo       iOS Safari:     tap "Show Details" ^> "Visit Website"
echo       After first visit, the cert is cached and trusted.
echo.

REM Start HTTPS server
echo [3/3] Starting Attendrix HTTPS server...
echo.
set HTTPS_PORT=5443

py app.py

pause

@echo off
title Attendrix HTTPS Server
echo ============================================
echo  Attendrix - HTTPS Development Server
echo ============================================
echo.
echo This starts Attendrix with HTTPS enabled for
echo mobile camera (getUserMedia) access over LAN.
echo.
echo 1. Find your LAN IP from the startup message
echo 2. On your phone, open:
echo    https://YOUR_LAN_IP:5443
echo 3. Accept the self-signed cert warning in
echo    your mobile browser (tap "Advanced" then
echo    "Proceed to site").
echo 4. Camera will work on mobile.
echo.
echo NOTE: Self-signed certs show a warning the
echo first time. This is normal for development.
echo For trusted certs, use mkcert instead.
echo.
echo ============================================
echo.

set HTTPS_PORT=5443

py app.py

pause

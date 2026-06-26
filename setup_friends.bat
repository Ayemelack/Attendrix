@echo off
title Attendrix — Friends Testing Setup
echo ============================================
echo   Attendrix — Setup for Friends Testing
echo ============================================
echo.

:: Check Python
py -3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3 not found. Install from https://python.org
    pause
    exit /b 1
)
py -3 --version

:: Install dependencies
echo.
echo [1/4] Installing Python packages...
py -3 -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [WARN] pip install had issues. Check requirements.txt
)

:: Generate random secrets
echo [2/4] Generating secrets...
setlocal enabledelayedexpansion
:: Generate random hex for SECRET_KEY
set "RAND1="
for /l %%i in (1,1,32) do (
    set /a "n=!random! %% 16"
    if !n! lss 10 (set "RAND1=!RAND1!!n!") else (
        set /a "n=!n! - 10"
        for %%c in (a b c d e f) do if !n!==0 set "RAND1=!RAND1!%%c"
    )
)
:: Do the same for JWT_SECRET_KEY
set "RAND2="
for /l %%i in (1,1,32) do (
    set /a "n=!random! %% 16"
    if !n! lss 10 (set "RAND2=!RAND2!!n!") else (
        set /a "n=!n! - 10"
        for %%c in (a b c d e f) do if !n!==0 set "RAND2=!RAND2!%%c"
    )
)

:: Write .env file
(
echo # ── ATTENDRIX PRODUCTION CONFIG ──
echo ENVIRONMENT=production
echo FLASK_DEBUG=False
echo LOG_LEVEL=INFO
echo USE_MOCK_FIREBASE=false
echo FIREBASE_CREDENTIALS_PATH=firebase-dev.json
echo FIREBASE_PROJECT_ID=attendrix-dev
echo FIREBASE_DATABASE_URL=https://attendrix-dev.firebaseio.com
echo DATABASE_URL=sqlite:///attendrix_prod.db
echo REDIS_URL=
echo SECRET_KEY=attendrix-%RAND1%
echo JWT_SECRET_KEY=attendrix-jwt-%RAND2%
echo JWT_ACCESS_TOKEN_EXPIRES=86400
echo JWT_REFRESH_TOKEN_EXPIRES=2592000
echo MAIL_SERVER=
echo MAIL_PORT=587
echo MAIL_USE_TLS=False
echo MAIL_USERNAME=
echo MAIL_PASSWORD=
echo CACHE_TYPE=simple
echo CACHE_REDIS_URL=
echo CELERY_BROKER_URL=
echo CELERY_RESULT_BACKEND=
echo RATELIMIT_STORAGE_URL=
echo RATELIMIT_DEFAULT=200 per day, 50 per hour
echo MAX_CONTENT_LENGTH=16777216
echo UPLOAD_FOLDER=uploads
echo ALLOWED_EXTENSIONS=png,jpg,jpeg,gif,pdf,doc,docx
echo GOOGLE_GEOCODING_API_KEY=
echo DEFAULT_GEOLOCATION_RADIUS=100
echo DEFAULT_ATTENDANCE_THRESHOLD=75
echo SESSION_TIMEOUT_MINUTES=15
echo MAX_LATE_MINUTES=10
) > .env
echo   Secrets generated and saved to .env

:: Create uploads directory
echo [3/4] Creating directories...
if not exist uploads mkdir uploads
if not exist logs mkdir logs

:: Seed demo data (creates test accounts)
echo [4/4] Starting app to seed demo data...
echo.
echo   First launch will auto-create demo accounts:
echo     admin@attendrix.demo / password123
echo     lecturer1@attendrix.demo / password123
echo     student1@attendrix.demo / password123
echo.
echo   Starting server...
echo   Your friends connect to: http://YOUR_IP_ADDRESS:5000
echo   Find YOUR_IP_ADDRESS with: ipconfig
echo.
echo ============================================
echo   Press CTRL+C to stop the server
echo ============================================
echo.

:: Start Flask in production mode
set FLASK_APP=app.py
set FLASK_ENV=production
py -3 -m flask run --host=0.0.0.0 --port=5000

pause

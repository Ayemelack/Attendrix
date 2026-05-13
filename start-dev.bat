@echo off
echo Starting Attendrix Development Server...
echo.

REM Check if Python is available
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python 3.11+ and add to PATH.
    pause
    exit /b 1
)

REM Check if required packages are installed
echo Checking dependencies...
py -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Flask...
    py -m pip install flask flask-cors
)

py -c "import firebase_admin" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Firebase Admin...
    py -m pip install firebase-admin
)

py -c "import jwt" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyJWT...
    py -m pip install pyjwt
)

py -c "import bcrypt" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing bcrypt...
    py -m pip install bcrypt
)

py -c "import decouple" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing python-decouple...
    py -m pip install python-decouple
)

echo.
echo Dependencies check complete!
echo.

REM Start the server
echo Starting Attendrix development server...
echo Server will be available at: http://localhost:5000
echo Health check: http://localhost:5000/health
echo API test: http://localhost:5000/api/test
echo System info: http://localhost:5000/api/info
echo.
echo Press Ctrl+C to stop the server
echo.

py app.py

pause

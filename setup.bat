@echo off
cd /d "%~dp0"
call :main
echo.
echo ==========================================
echo   Setup finished. Window will stay open.
echo ==========================================
echo.
pause
exit /b

:main
echo [SETUP] Starting Tenant-VLite Environment Setup
echo.

REM 1. Check if the venv directory exists
if not exist "venv" (
    echo [SETUP] Creating new Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :eof
    )
) else (
    echo [SETUP] Virtual environment already exists.
)

REM 2. Activate the virtual environment
echo [SETUP] Activating virtual environment...
call venv\Scripts\activate.bat

REM 3. Upgrade pip
echo [SETUP] Upgrading pip...
pip install --upgrade pip

REM 4. Install the requirements
echo [SETUP] Installing project dependencies...
pip install -r requirements.txt

REM 5. Set up WebUI dependencies
echo [SETUP] Installing WebUI dependencies...
pushd webui
call npm install
popd

REM 6. Run the tenant.py main boot script
echo [SETUP] Starting the Tenant-VLite server...
python tenant.py

goto :eof

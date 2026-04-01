@echo off
cd /d "%~dp0"

set "SETUP_MARKER=%~dp0.tenant_vlite_setup_complete"

if not exist "%SETUP_MARKER%" (
    echo [STARTUP] Setup has not been completed yet. Run setup.bat once to create the environment, then use startup.bat.
    pause
    exit /b 1
)

if not exist "venv" (
    echo [STARTUP] Virtual environment is missing. Run setup.bat to repair your installation.
    pause
    exit /b 1
)

echo [STARTUP] Starting Tenant-VLite...
call venv\Scripts\activate.bat
python tenant.py

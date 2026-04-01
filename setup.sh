#!/bin/bash

# Exit on error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SETUP_MARKER="$SCRIPT_DIR/.tenant_vlite_setup_complete"

echo "[SETUP] Starting Tenant-VLite Environment Setup"

# 1. Check if the venv directory exists
if [ ! -d "venv" ]; then
    echo "[SETUP] Creating new Python virtual environment..."
    python3 -m venv venv
else
    echo "[SETUP] Virtual environment already exists."
fi

# 2. Activate the virtual environment
echo "[SETUP] Activating virtual environment..."
source venv/bin/activate

# 3. Upgrade pip to the latest version to avoid warnings
echo "[SETUP] Upgrading pip..."
pip install --upgrade pip

# 4. Install the requirements
echo "[SETUP] Installing project dependencies..."
pip install -r requirements.txt

# 5. Set up WebUI dependencies
echo "[SETUP] Installing WebUI dependencies..."
cd webui
npm install
cd ..

touch "$SETUP_MARKER"
echo "[SETUP] Environment setup finished."

echo "[SETUP] Launching Tenant-VLite via startup.sh..."
exec "$SCRIPT_DIR/startup.sh"

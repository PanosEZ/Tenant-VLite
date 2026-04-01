#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SETUP_MARKER="$SCRIPT_DIR/.tenant_vlite_setup_complete"

if [ ! -f "$SETUP_MARKER" ]; then
    echo "[STARTUP] Setup has not been completed yet. Run ./setup.sh once to create the environment, then use ./startup.sh."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[STARTUP] Virtual environment is missing. Run ./setup.sh to repair your installation."
    exit 1
fi

echo "[STARTUP] Starting Tenant-VLite..."
source venv/bin/activate
exec python3 tenant.py

#!/usr/bin/env bash
set -euo pipefail

# Simple bootstrap script to get the bot running quickly.
# Usage: ./setup.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
CONFIG_FILE="${CONFIG_FILE:-config.yml}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python interpreter not found (looked for '$PYTHON_BIN')." >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "Upgrading pip and installing requirements ..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Ensuring configuration file exists ..."
if [ ! -f "$CONFIG_FILE" ]; then
    cp config.example.yml "$CONFIG_FILE"
    echo "Created $CONFIG_FILE from config.example.yml. Fill in your tokens and channel IDs before running the bot."
else
    echo "Found existing $CONFIG_FILE."
fi

echo "Setup complete. Activate the environment with 'source $VENV_DIR/bin/activate' and run the bot with 'python bot.py'."

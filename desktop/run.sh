#!/usr/bin/env bash
# OmniVault Desktop Launcher Script
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export DISPLAY="${DISPLAY:-:0.0}"

# Prefer system python3 or pyenv python
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif [ -f "/home/k/.pyenv/shims/python" ]; then
    PYTHON_BIN="/home/k/.pyenv/shims/python"
else
    PYTHON_BIN="python"
fi

exec "$PYTHON_BIN" main.py "$@"

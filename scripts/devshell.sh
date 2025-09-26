#!/usr/bin/env bash
# Helper to run commands inside the project's virtual environment.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/venv"

PYTHON_BIN="${PYTHON:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python interpreter '$PYTHON_BIN' not found" >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

REQ_FILE="$ROOT_DIR/requirements.txt"
STAMP_FILE="$VENV_DIR/.requirements-stamp"

if [ -f "$REQ_FILE" ]; then
    if [ ! -f "$STAMP_FILE" ] || [ "$REQ_FILE" -nt "$STAMP_FILE" ]; then
        if python -m pip install -r "$REQ_FILE"; then
            touch "$STAMP_FILE"
        else
            echo "Warning: dependency installation failed; using existing environment" >&2
        fi
    fi
fi

if [ "$#" -eq 0 ]; then
    exec "$SHELL"
else
    exec "$@"
fi

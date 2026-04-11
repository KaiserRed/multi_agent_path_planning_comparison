#!/usr/bin/env bash
# Build a single-file Linux executable with PyInstaller.
#
# Usage:
#   ./build.sh            # build in release mode
#   ./build.sh --debug    # keep console window + debug output
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON=".venv/bin/python"
PYINSTALLER=".venv/bin/pyinstaller"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: virtual environment not found at .venv/"
    echo "  Run:  uv sync"
    exit 1
fi

if [[ ! -x "$PYINSTALLER" ]]; then
    echo "ERROR: pyinstaller not found in .venv/"
    echo "  Run:  uv add --dev pyinstaller"
    exit 1
fi

DEBUG_FLAG=""
if [[ "${1:-}" == "--debug" ]]; then
    DEBUG_FLAG="--debug=all"
    echo "Building in DEBUG mode …"
else
    echo "Building release binary …"
fi

"$PYINSTALLER" mrse.spec \
    --distpath dist/linux \
    --workpath build/linux \
    --noconfirm \
    $DEBUG_FLAG

echo ""
echo "Done!  Executable: dist/linux/mrse"

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VIEWER_DIR="$ROOT_DIR/viewer"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
elif [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
  PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON="$(command -v python)"
else
  echo "Python is required to build artifacts for the local viewer." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to run the local viewer." >&2
  exit 1
fi

if [[ ! -f "$VIEWER_DIR/package.json" ]]; then
  echo "Viewer package not found at $VIEWER_DIR." >&2
  exit 1
fi

"$PYTHON" "$ROOT_DIR/build.py"

cd "$VIEWER_DIR"

if [[ ! -d node_modules ]]; then
  npm ci
fi

npm run prepare-model
exec npm run dev -- "$@"

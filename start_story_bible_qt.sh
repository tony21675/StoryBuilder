#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  echo "ERROR: StoryBuilder's .venv was not found."
  echo "Create it with: python3 -m venv .venv"
  echo "Then install: .venv/bin/python -m pip install -r requirements.txt -r requirements-ui.txt"
  exit 1
fi

if ! "$SCRIPT_DIR/.venv/bin/python" -c "import PySide6" >/dev/null 2>&1; then
  echo "ERROR: PySide6 is not installed in StoryBuilder's virtual environment."
  echo "Run: .venv/bin/python -m pip install -r requirements-ui.txt"
  exit 1
fi

SKIP_SYNC="$(printenv STORYBUILDER_SKIP_SYNC 2>/dev/null || printf '0')"
if [[ "$SKIP_SYNC" != "1" ]]; then
  echo "Synchronizing StoryBuilder on main..."
  bash "$SCRIPT_DIR/sync.sh" start
  if ! "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/backup_handoffs.py"; then
    echo "WARNING: Could not refresh the local handoff backup. Story Bible will still start."
  fi
fi

echo "Starting PySide6 Story Bible..."
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/story_bible_qt.py"

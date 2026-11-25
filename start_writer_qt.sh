#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${STORYBUILDER_SKIP_SYNC:-0}" != "1" ]]; then
  echo "Synchronizing StoryBuilder with GitHub..."
  bash "$SCRIPT_DIR/sync.sh" start
  if ! python3 "$SCRIPT_DIR/backup_handoffs.py"; then
    echo "WARNING: Could not refresh the local handoff backup. The Qt Writer will still start."
  fi
fi

PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi
if ! "$PYTHON" -c "import PySide6" >/dev/null 2>&1; then
  echo "PySide6 is not installed in $PYTHON."
  echo "Install it with: $PYTHON -m pip install -r requirements-ui.txt"
  exit 1
fi

export STORYBUILDER_THEME="${STORYBUILDER_THEME:-dark}"
export STORY_WRITER_CONTEXT="${STORY_WRITER_CONTEXT:-16384}"
export STORY_WRITER_MAX_TOKENS="${STORY_WRITER_MAX_TOKENS:-4000}"
exec "$PYTHON" "$SCRIPT_DIR/writer_qt.py"

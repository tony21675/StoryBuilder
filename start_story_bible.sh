#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Synchronizing StoryBuilder with GitHub..."
bash "$SCRIPT_DIR/sync.sh" start
if ! python3 "$SCRIPT_DIR/backup_handoffs.py"; then
  echo "WARNING: Could not refresh the local handoff backup. Story Bible will still start."
fi

echo "Starting Story Bible..."
export STORYBUILDER_THEME="${STORYBUILDER_THEME:-dark}"
exec python3 "$SCRIPT_DIR/story_bible_app.py"

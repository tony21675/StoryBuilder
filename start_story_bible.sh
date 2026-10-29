#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Synchronizing StoryBuilder with GitHub..."
bash "$SCRIPT_DIR/sync.sh" start

echo "Starting Story Bible..."
exec python3 "$SCRIPT_DIR/story_bible_app.py"

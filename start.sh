#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Synchronizing StoryBuilder with GitHub..."
# Run the Bash sync helper explicitly and stop here if synchronization is unsafe.
bash "$SCRIPT_DIR/sync.sh" start

echo "Starting StoryBuilder..."
# Larger defaults prevent longer scenes from being cut off too early.
# Environment variables can still override these values for a particular launch.
# Keep StoryBuilder dark by default for readability; allow an explicit light-mode override.
export STORYBUILDER_THEME="${STORYBUILDER_THEME:-dark}"
export STORY_WRITER_CONTEXT="${STORY_WRITER_CONTEXT:-16384}"
export STORY_WRITER_MAX_TOKENS="${STORY_WRITER_MAX_TOKENS:-4000}"
exec python3 "$SCRIPT_DIR/storybuilder.py"

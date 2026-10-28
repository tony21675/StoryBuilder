#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Synchronizing StoryBuilder with GitHub..."
bash "$SCRIPT_DIR/sync.sh" start

echo "Starting Minimal Writer..."
export STORYBUILDER_THEME="${STORYBUILDER_THEME:-dark}"
export STORY_WRITER_CONTEXT="${STORY_WRITER_CONTEXT:-16384}"
export STORY_WRITER_MAX_TOKENS="${STORY_WRITER_MAX_TOKENS:-4000}"
exec python3 "$SCRIPT_DIR/minimal_writer.py"

#!/bin/sh
set -e

cd "$(dirname "$0")"

echo "Synchronizing StoryBuilder with GitHub..."
./sync.sh start

echo "Starting StoryBuilder..."
# Larger defaults prevent longer scenes from being cut off too early.
# Environment variables can still override these values for a particular launch.
export STORY_WRITER_CONTEXT="${STORY_WRITER_CONTEXT:-16384}"
export STORY_WRITER_MAX_TOKENS="${STORY_WRITER_MAX_TOKENS:-4000}"
exec python3 storybuilder.py

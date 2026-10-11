#!/bin/sh
set -e

cd "$(dirname "$0")"

echo "Synchronizing StoryBuilder with GitHub..."
./sync.sh start

echo "Starting StoryBuilder..."
export STORY_WRITER_CONTEXT="${STORY_WRITER_CONTEXT:-8192}"
export STORY_WRITER_MAX_TOKENS="${STORY_WRITER_MAX_TOKENS:-2000}"
exec python3 storybuilder.py

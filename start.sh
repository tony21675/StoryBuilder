#!/bin/sh
set -e

cd "$(dirname "$0")"

echo "Synchronizing StoryBuilder with GitHub..."
./sync.sh start

echo "Starting StoryBuilder..."
exec python3 storybuilder.py

#!/usr/bin/env bash
set -euo pipefail

REMOTE="origin"

usage() {
  echo "Usage: $0 start|finish"
  echo
  echo "  start   Pull the latest GitHub changes before you begin working."
  echo "  finish  Commit and push your changes after you finish working."
  exit 1
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: This script must be run inside a Git repository."
  exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then
  echo "ERROR: Repository is in detached HEAD state."
  exit 1
fi

case "${1:-}" in
  start)
    if [[ -n "$(git status --porcelain)" ]]; then
      echo "ERROR: Local changes are present."
      echo "Finish or deliberately handle those changes before syncing."
      git status --short
      exit 1
    fi

    echo "Fetching latest changes from GitHub..."
    git fetch --prune "$REMOTE"

    echo "Updating $BRANCH..."
    git pull --rebase "$REMOTE" "$BRANCH"

    echo
    echo "READY: local files are synchronized with GitHub."
    git status -sb
    ;;

  finish)
    echo "Staging local changes..."
    git add -A

    if git diff --cached --quiet; then
      echo "No file changes to commit."
      git status -sb
      exit 0
    fi

    git diff --cached --stat

    COMMIT_MESSAGE="Sync changes $(date '+%Y-%m-%d %H:%M:%S')"
    git commit -m "$COMMIT_MESSAGE"

    echo "Checking GitHub for changes made elsewhere..."
    git pull --rebase "$REMOTE" "$BRANCH"

    echo "Pushing to GitHub..."
    git push "$REMOTE" "$BRANCH"

    echo
    echo "DONE: GitHub now contains the latest committed local files."
    git status -sb
    ;;

  *)
    usage
    ;;
esac

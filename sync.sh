#!/usr/bin/env bash
set -euo pipefail

REMOTE="origin"

usage() {
  echo "Usage: $0 start|finish"
  echo
  echo "  start   Sync StoryBuilder code before you begin working."
  echo "          Local app changes are stashed and restored automatically."
  echo "  finish  Commit and push StoryBuilder code changes."
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

restore_stash() {
  if [[ "${STASHED:-0}" != "1" ]]; then
    return 0
  fi

  echo "Restoring your local StoryBuilder changes..."
  if ! git stash pop; then
    echo
    echo "WARNING: Git could not automatically restore the local changes."
    echo "Your stash is still preserved in Git."
    echo "Resolve the conflict before continuing."
    git status --short
    return 1
  fi
  STASHED=0
  return 0
}

case "${1:-}" in
  start)
    if [[ -n "$(git diff --name-only --diff-filter=U)" ]]; then
      echo "ERROR: Unresolved Git conflicts are already present."
      echo "Resolve them before starting StoryBuilder."
      git status --short
      exit 1
    fi

    STASHED=0
    if [[ -n "$(git status --porcelain)" ]]; then
      echo "Local StoryBuilder changes found."
      echo "Temporarily stashing them so GitHub can be synchronized safely..."
      if ! git stash push -u -m "StoryBuilder automatic start sync $(date '+%Y-%m-%d %H:%M:%S')"; then
        echo "ERROR: Could not stash local StoryBuilder changes."
        exit 1
      fi
      STASHED=1
    fi

    echo "Fetching latest StoryBuilder changes from GitHub..."
    if ! git fetch --prune "$REMOTE"; then
      restore_stash || true
      exit 1
    fi

    echo "Updating $BRANCH..."
    if ! git pull --rebase "$REMOTE" "$BRANCH"; then
      echo
      echo "ERROR: StoryBuilder itself could not be updated cleanly."
      git status --short
      restore_stash || true
      exit 1
    fi

    if ! restore_stash; then
      exit 1
    fi

    echo
    echo "READY: StoryBuilder is synchronized with GitHub."
    git status -sb
    ;;

  finish)
    if [[ -n "$(git diff --name-only --diff-filter=U)" ]]; then
      echo "ERROR: Unresolved Git conflicts are present."
      git status --short
      exit 1
    fi

    echo "Staging local StoryBuilder changes..."
    git add -A

    if git diff --cached --quiet; then
      echo "No StoryBuilder file changes to commit."
      git fetch --prune "$REMOTE"
      git pull --rebase "$REMOTE" "$BRANCH"
      git status -sb
      exit 0
    fi

    git diff --cached --stat

    COMMIT_MESSAGE="Sync StoryBuilder changes $(date '+%Y-%m-%d %H:%M:%S')"
    git commit -m "$COMMIT_MESSAGE"

    echo "Checking GitHub for changes made elsewhere..."
    if ! git pull --rebase "$REMOTE" "$BRANCH"; then
      echo
      echo "ERROR: StoryBuilder changes conflict with GitHub."
      echo "Your local commit is preserved. Resolve the rebase before pushing."
      git status --short
      exit 1
    fi

    echo "Pushing StoryBuilder changes to GitHub..."
    git push "$REMOTE" "$BRANCH"

    echo
    echo "DONE: StoryBuilder is synchronized with GitHub."
    git status -sb
    ;;

  *)
    usage
    ;;
esac

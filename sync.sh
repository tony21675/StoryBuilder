#!/usr/bin/env bash
set -euo pipefail

REMOTE="origin"

usage() {
  echo "Usage: $0 start|finish"
  echo
  echo "  start   Safely update the current StoryBuilder development branch before launch."
  echo "          Uncommitted local changes are stashed and restored automatically."
  echo "  finish  Commit and push StoryBuilder code changes on the current development branch."
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

# Keep the shell helper aligned with the app's Close & Sync App safeguards.
# Work only on the existing development branch; never sync or push from main.
if [[ "$BRANCH" == "main" ]]; then
  echo "ERROR: StoryBuilder app sync is blocked on main."
  echo "Use the existing development branch. No branch switch or deletion was attempted."
  exit 1
fi

UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
if [[ "$UPSTREAM" != "$REMOTE/$BRANCH" ]]; then
  echo "ERROR: Current branch '$BRANCH' must track '$REMOTE/$BRANCH' before syncing."
  echo "No files were committed, pushed, or switched."
  exit 1
fi

if git status 2>&1 | grep -Eiq \
  'rebase in progress|you are currently rebasing|merge in progress|you are currently merging|cherry-pick currently in progress|you are currently cherry-picking'; then
  echo "ERROR: An unfinished Git merge, rebase, or cherry-pick is in progress."
  echo "Resolve it before syncing. No files were committed or pushed."
  git status --short
  exit 1
fi

if [[ -n "$(git diff --name-only --diff-filter=U)" ]]; then
  echo "ERROR: Unresolved Git conflicts are already present."
  echo "Resolve them before syncing."
  git status --short
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

    echo "Fast-forwarding $BRANCH..."
    if ! git pull --ff-only "$REMOTE" "$BRANCH"; then
      echo
      echo "ERROR: StoryBuilder could not be fast-forwarded safely."
      echo "No rebase or reset was attempted."
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
    echo "Staging local StoryBuilder changes..."
    git add -A

    if git diff --cached --quiet; then
      echo "No StoryBuilder file changes to commit."
    else
      git diff --cached --stat
      COMMIT_MESSAGE="Sync StoryBuilder changes $(date '+%Y-%m-%d %H:%M:%S')"
      git commit -m "$COMMIT_MESSAGE"
    fi

    echo "Checking GitHub for changes made elsewhere..."
    if ! git fetch --prune "$REMOTE"; then
      echo "ERROR: Could not fetch GitHub. Any local commit is preserved."
      exit 1
    fi

    if ! git pull --ff-only "$REMOTE" "$BRANCH"; then
      echo
      echo "ERROR: StoryBuilder could not be fast-forwarded safely."
      echo "Any local commit is preserved. No push was attempted."
      git status --short
      exit 1
    fi

    echo "Pushing StoryBuilder changes to GitHub..."
    if ! git push "$REMOTE" "$BRANCH"; then
      echo "ERROR: Push failed. Local changes and commits are preserved."
      exit 1
    fi

    echo
    echo "DONE: StoryBuilder is synchronized with GitHub."
    git status -sb
    ;;

  *)
    usage
    ;;
esac

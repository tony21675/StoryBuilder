from __future__ import annotations

import subprocess
from pathlib import Path


class NovelSyncError(RuntimeError):
    """Raised when a novel repository cannot be synchronized safely."""


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _git_root(novel_path: Path) -> Path:
    novel_path = Path(novel_path).expanduser().resolve()
    if not novel_path.is_dir():
        raise NovelSyncError(f"Novel folder does not exist: {novel_path}")

    result = _run_git(novel_path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise NovelSyncError(
            "The selected novel is not a Git repository. "
            "Use the regular Close button or initialize/clone the novel repository first."
        )
    return Path(result.stdout.strip()).resolve()


def _branch(root: Path) -> str:
    result = _run_git(root, "branch", "--show-current")
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        raise NovelSyncError("The novel repository is not on a normal branch.")
    return branch


def sync_novel_repository(novel_path: Path) -> str:
    """Save the current novel repo to GitHub without touching StoryBuilder itself.

    The novel repo is committed first, then rebased onto the remote branch, then
    pushed. A rebase conflict is reported without silently choosing either side.
    """
    root = _git_root(novel_path)
    branch = _branch(root)

    status = _run_git(root, "status", "--porcelain")
    if status.returncode != 0:
        raise NovelSyncError(status.stderr.strip() or "Could not inspect the novel repository.")

    has_changes = bool(status.stdout.strip())
    if has_changes:
        staged = _run_git(root, "add", "-A")
        if staged.returncode != 0:
            raise NovelSyncError(staged.stderr.strip() or "Could not stage novel changes.")

        staged_check = _run_git(root, "diff", "--cached", "--quiet")
        if staged_check.returncode not in (0, 1):
            raise NovelSyncError(
                staged_check.stderr.strip() or "Could not inspect staged novel changes."
            )

        if staged_check.returncode == 1:
            commit = _run_git(
                root,
                "commit",
                "-m",
                "Sync novel changes " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            if commit.returncode != 0:
                raise NovelSyncError(
                    commit.stderr.strip() or commit.stdout.strip() or "Could not commit novel changes."
                )

    fetch = _run_git(root, "fetch", "--prune", "origin")
    if fetch.returncode != 0:
        raise NovelSyncError(
            fetch.stderr.strip() or fetch.stdout.strip() or "Could not fetch the novel remote."
        )

    pull = _run_git(root, "pull", "--rebase", "origin", branch)
    if pull.returncode != 0:
        details = pull.stderr.strip() or pull.stdout.strip()
        if "CONFLICT" in details or "conflict" in details or "could not apply" in details:
            raise NovelSyncError(
                "GitHub and this laptop changed the same novel content. "
                "The repository was left in the rebase state so nothing was overwritten.\n\n"
                + details
            )
        raise NovelSyncError(details or "Could not rebase the novel repository.")

    push = _run_git(root, "push", "origin", branch)
    if push.returncode != 0:
        raise NovelSyncError(
            push.stderr.strip() or push.stdout.strip() or "Could not push the novel repository."
        )

    final = _run_git(root, "status", "-sb")
    status_line = final.stdout.strip()
    return f"Novel synchronized successfully.\n{status_line}" if status_line else "Novel synchronized successfully."


def novel_repo_root(novel_path: Path) -> Path | None:
    """Return the novel's Git root, or None when the folder is not a Git repo."""
    try:
        return _git_root(novel_path)
    except NovelSyncError:
        return None

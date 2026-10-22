from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


class StoryBuilderSyncError(RuntimeError):
    """Raised when the StoryBuilder application repository cannot sync safely."""


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StoryBuilderSyncError(
            f"Could not run git {' '.join(args)}: {exc}"
        ) from exc


def _failure(result: subprocess.CompletedProcess[str], fallback: str) -> StoryBuilderSyncError:
    details = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
    )
    return StoryBuilderSyncError(details or fallback)


def sync_storybuilder_repository(app_path: str | Path) -> str:
    """Sync only the StoryBuilder application repository on its current development branch.

    This intentionally refuses to switch branches, merge into main, or rebase local
    commits. Local application changes are committed on the active branch, then the
    remote is fetched and fast-forwarded if possible before pushing. Any divergence
    or conflict stops safely without pushing.
    """
    app_root = Path(app_path).expanduser().resolve()
    if not app_root.is_dir():
        raise StoryBuilderSyncError(f"StoryBuilder application folder does not exist: {app_root}")
    if not (app_root / "storybuilder.py").is_file() or not (app_root / "builder").is_dir():
        raise StoryBuilderSyncError(
            "Safety check failed: the selected folder does not look like the StoryBuilder application root."
        )

    root_result = _run_git(app_root, "rev-parse", "--show-toplevel")
    if root_result.returncode != 0:
        raise _failure(
            root_result,
            "StoryBuilder application folder is not a Git repository. No sync was attempted.",
        )
    git_root = Path(root_result.stdout.strip()).expanduser().resolve()
    if git_root != app_root:
        raise StoryBuilderSyncError(
            "Safety check failed: the StoryBuilder source folder is inside a different Git repository. "
            "No files were committed or pushed."
        )

    status_result = _run_git(git_root, "status")
    if status_result.returncode != 0:
        raise _failure(status_result, "Could not inspect the StoryBuilder repository.")
    status_text = (status_result.stdout + "\n" + status_result.stderr).casefold()
    in_progress = (
        "rebase in progress",
        "you are currently rebasing",
        "merge in progress",
        "you are currently merging",
        "cherry-pick currently in progress",
        "you are currently cherry-picking",
    )
    if any(marker in status_text for marker in in_progress):
        raise StoryBuilderSyncError(
            "StoryBuilder has an unfinished Git merge, rebase, or cherry-pick. "
            "No files were committed or pushed. Resolve that Git operation before syncing."
        )

    branch_result = _run_git(git_root, "branch", "--show-current")
    branch = branch_result.stdout.strip()
    if branch_result.returncode != 0 or not branch:
        raise StoryBuilderSyncError(
            "StoryBuilder is not on a normal branch. No files were committed or pushed."
        )
    if branch == "main":
        raise StoryBuilderSyncError(
            "Safety check blocked syncing StoryBuilder from main. Keep working on the existing "
            "StoryBuilder development branch; no files were committed or pushed."
        )

    upstream_result = _run_git(
        git_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
    )
    upstream = upstream_result.stdout.strip()
    if upstream_result.returncode != 0 or upstream != f"origin/{branch}":
        raise StoryBuilderSyncError(
            f"StoryBuilder branch '{branch}' must track 'origin/{branch}' before app sync. "
            "No files were committed or pushed."
        )

    unmerged = _run_git(git_root, "diff", "--name-only", "--diff-filter=U")
    if unmerged.returncode != 0:
        raise _failure(unmerged, "Could not check for unresolved StoryBuilder conflicts.")
    if unmerged.stdout.strip():
        raise StoryBuilderSyncError(
            "StoryBuilder has unresolved conflict files. No files were committed or pushed:\n"
            + unmerged.stdout.strip()
        )

    working_status = _run_git(git_root, "status", "--porcelain")
    if working_status.returncode != 0:
        raise _failure(working_status, "Could not inspect StoryBuilder file changes.")

    if working_status.stdout.strip():
        staged = _run_git(git_root, "add", "-A")
        if staged.returncode != 0:
            raise _failure(staged, "Could not stage StoryBuilder application changes.")

        staged_check = _run_git(git_root, "diff", "--cached", "--quiet")
        if staged_check.returncode not in (0, 1):
            raise _failure(staged_check, "Could not inspect staged StoryBuilder changes.")

        if staged_check.returncode == 1:
            commit = _run_git(
                git_root,
                "commit",
                "-m",
                "Sync StoryBuilder application files "
                + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            if commit.returncode != 0:
                raise _failure(
                    commit,
                    "Could not commit StoryBuilder application changes. No push was attempted.",
                )

    fetch = _run_git(git_root, "fetch", "--prune", "origin")
    if fetch.returncode != 0:
        raise _failure(fetch, "Could not fetch the StoryBuilder application remote.")

    pull = _run_git(git_root, "pull", "--ff-only", "origin", branch)
    if pull.returncode != 0:
        raise StoryBuilderSyncError(
            "The StoryBuilder branch could not be fast-forwarded safely. No push was attempted; "
            "any local commit remains on the current branch. Do not reset or switch branches.\n\n"
            + "\n".join(
                part.strip() for part in (pull.stdout, pull.stderr) if part and part.strip()
            )
        )

    push = _run_git(git_root, "push", "origin", branch)
    if push.returncode != 0:
        raise _failure(
            push,
            "Could not push StoryBuilder application changes. The novel repository was not touched.",
        )

    final = _run_git(git_root, "status", "-sb")
    if final.returncode != 0:
        raise _failure(final, "StoryBuilder synced, but the final repository status could not be read.")
    status_line = final.stdout.strip()
    return (
        "StoryBuilder application synchronized successfully. The novel was not saved or synced.\n"
        + (status_line if status_line else f"Branch: {branch}")
    )

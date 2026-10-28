from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class NovelGitSyncError(RuntimeError):
    """A safe novel-to-GitHub sync could not be completed."""


@dataclass(frozen=True)
class NovelSyncPreview:
    repository: Path
    branch: str
    upstream: str
    remote_url: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class NovelSyncResult:
    repository: Path
    branch: str
    remote_url: str
    committed: bool
    changed_files: tuple[str, ...]
    message: str


def _run_git(
    repository: Path,
    *arguments: str,
    check: bool = True,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run Git only inside the selected novel repository, never through a shell."""
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(repository),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise NovelGitSyncError(
            "Git could not be found. Install Git and try again."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise NovelGitSyncError(
            f"Git timed out while running '{' '.join(arguments)}'. "
            "No push was attempted; check the repository before trying again."
        ) from exc

    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if len(detail) > 1400:
            detail = detail[-1400:]
        command = " ".join(arguments)
        suffix = f"\n\nGit said:\n{detail}" if detail else ""
        raise NovelGitSyncError(f"Git command failed: {command}.{suffix}")
    return result


def _safe_remote_url(remote_url: str) -> str:
    """Remove embedded HTTP credentials before showing a remote in the UI."""
    parsed = urlsplit(remote_url)
    if parsed.scheme and parsed.netloc and parsed.hostname:
        host = parsed.hostname
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit(
            (parsed.scheme, host, parsed.path, parsed.query, parsed.fragment)
        )
    # SCP-style URLs (git@github.com:owner/repo.git) contain no URL password
    # field, and are useful for identifying the configured repository.
    return remote_url


def _git_path(repository: Path, git_path_name: str) -> Path | None:
    result = _run_git(repository, "rev-parse", "--git-path", git_path_name, check=False)
    if result.returncode != 0:
        return None
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (repository / path)


def _check_no_operation_in_progress(repository: Path) -> None:
    active = (
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-merge",
        "rebase-apply",
    )
    for name in active:
        path = _git_path(repository, name)
        if path is not None and path.exists():
            raise NovelGitSyncError(
                f"This novel has an unfinished Git operation ({name}). "
                "Resolve it before syncing. No commit or push was attempted."
            )


def _status_lines(repository: Path) -> list[str]:
    output = _run_git(
        repository, "status", "--porcelain=v1", "--untracked-files=all"
    ).stdout
    lines = [line for line in output.splitlines() if line]
    unmerged_codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    if any(line[:2] in unmerged_codes or "U" in line[:2] for line in lines):
        raise NovelGitSyncError(
            "This novel has unresolved Git conflicts. Resolve them before syncing. "
            "No commit or push was attempted."
        )
    return lines


def _paths_from_status(lines: list[str]) -> tuple[str, ...]:
    paths: list[str] = []
    for line in lines:
        path_text = line[3:] if len(line) > 3 else line
        # Porcelain status uses 'old -> new' for renames and copies.
        candidates = path_text.split(" -> ")
        paths.extend(candidate.strip().strip('"') for candidate in candidates)
    return tuple(paths)


def _is_protected_local_path(path_text: str) -> bool:
    normalised = path_text.strip().strip('"').replace("\\", "/").casefold()
    parts = [part for part in normalised.split("/") if part]
    if any(part in {"secret", "secrets"} for part in parts):
        return True
    filename = parts[-1] if parts else normalised
    return (
        filename in {"private_key", "private-key", "id_rsa", "id_ed25519"}
        or "private_key" in filename
        or filename.endswith((".enc", ".enc.b64", ".enc.json", ".key", ".pem"))
    )


def _block_protected_changes(paths: tuple[str, ...]) -> None:
    if any(_is_protected_local_path(path) for path in paths):
        raise NovelGitSyncError(
            "Local-only secret or encrypted assets appear in this novel's Git change "
            "list. Sync was blocked before committing or pushing. Check the novel's "
            ".gitignore and keep those assets out of GitHub."
        )


def inspect_novel_repository(novel_path: str | Path) -> NovelSyncPreview:
    """Validate the selected novel repository and return a confirmation preview."""
    repository = Path(novel_path).expanduser().resolve()
    if not repository.is_dir():
        raise NovelGitSyncError(f"The selected novel folder does not exist:\n{repository}")
    if not (repository / "story_bible.json").is_file():
        raise NovelGitSyncError(
            "The selected folder does not contain story_bible.json, so it will not "
            "be treated as a novel package."
        )

    root_output = _run_git(repository, "rev-parse", "--show-toplevel").stdout.strip()
    repository_root = Path(root_output).resolve()
    if repository_root != repository:
        raise NovelGitSyncError(
            "The selected novel folder is not the root of its own Git repository. "
            "Sync is blocked so Writer cannot accidentally push another repository."
        )

    branch = _run_git(repository, "branch", "--show-current").stdout.strip()
    if not branch:
        raise NovelGitSyncError(
            "This novel repository is in detached-HEAD state. Select its existing "
            "branch in Git before syncing."
        )

    remote_result = _run_git(
        repository, "remote", "get-url", "origin", check=False
    )
    if remote_result.returncode != 0 or not remote_result.stdout.strip():
        raise NovelGitSyncError(
            "This novel has no 'origin' Git remote configured. Configure the correct "
            "GitHub remote manually before syncing."
        )
    remote_url = _safe_remote_url(remote_result.stdout.strip())

    upstream_result = _run_git(
        repository,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        check=False,
    )
    if upstream_result.returncode != 0:
        raise NovelGitSyncError(
            f"Branch '{branch}' has no upstream configured. Sync will not create "
            "branches or guess a destination; configure origin/{branch} first."
        )
    upstream = upstream_result.stdout.strip()
    if upstream != f"origin/{branch}":
        raise NovelGitSyncError(
            f"Branch '{branch}' tracks '{upstream}', not 'origin/{branch}'. "
            "Sync is blocked rather than pushing to an unexpected branch."
        )

    _check_no_operation_in_progress(repository)
    lines = _status_lines(repository)
    changed_files = _paths_from_status(lines)
    _block_protected_changes(changed_files)

    return NovelSyncPreview(
        repository=repository,
        branch=branch,
        upstream=upstream,
        remote_url=remote_url,
        changed_files=changed_files,
    )


def sync_novel_repository(novel_path: str | Path) -> NovelSyncResult:
    """Safely fast-forward, commit selected-novel changes, and push its branch.

    The caller must obtain explicit user confirmation from the preview before
    calling this function. Local changes are temporarily stashed while GitHub is
    fetched and fast-forwarded, then restored before any commit is made.
    """
    preview = inspect_novel_repository(novel_path)
    repository = preview.repository
    stashed = False

    if preview.changed_files:
        before_result = _run_git(
            repository, "rev-parse", "--verify", "refs/stash", check=False
        )
        before_stash = before_result.stdout.strip() if before_result.returncode == 0 else ""
        _run_git(
            repository,
            "stash",
            "push",
            "--include-untracked",
            "-m",
            f"StoryBuilder novel sync safety stash {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            timeout=60,
        )
        after_result = _run_git(
            repository, "rev-parse", "--verify", "refs/stash", check=False
        )
        after_stash = after_result.stdout.strip() if after_result.returncode == 0 else ""
        stashed = bool(after_stash and after_stash != before_stash)
        if not stashed and _run_git(
            repository, "status", "--porcelain=v1", "--untracked-files=all"
        ).stdout.strip():
            raise NovelGitSyncError(
                "Git could not safely set aside the local novel changes. "
                "No commit or push was attempted."
            )

    sync_error: NovelGitSyncError | None = None
    try:
        _run_git(repository, "fetch", "origin", timeout=90)
        _run_git(
            repository, "pull", "--ff-only", "origin", preview.branch, timeout=90
        )
    except NovelGitSyncError as exc:
        sync_error = exc

    if stashed:
        try:
            _run_git(repository, "stash", "pop", timeout=60)
        except NovelGitSyncError as exc:
            raise NovelGitSyncError(
                "Git could not automatically restore your local changes after the "
                "fetch/fast-forward step. Your safety stash is preserved in Git; "
                "do not run another sync until the working tree is checked. "
                "No commit or push was attempted.\n\n"
                f"Git said:\n{exc}"
            ) from exc

    if sync_error is not None:
        raise NovelGitSyncError(
            f"{sync_error}\n\nLocal changes were restored. No commit or push was attempted."
        ) from sync_error

    # Revalidate after the remote update and stash restoration, including the
    # protected-path rule and any conflict state created by a stash pop.
    refreshed = inspect_novel_repository(repository)
    committed = False
    changed_files = refreshed.changed_files

    if changed_files:
        _run_git(repository, "add", "--all", timeout=60)
        staged_result = _run_git(
            repository, "diff", "--cached", "--name-only", "-z"
        )
        staged_paths = tuple(path for path in staged_result.stdout.split("\0") if path)
        protected_staged = tuple(
            path for path in staged_paths if _is_protected_local_path(path)
        )
        if protected_staged:
            # This is a second guard against a protected file appearing between
            # preflight and staging. Only those protected paths are unstaged.
            _run_git(repository, "reset", "--", *protected_staged, check=False)
            raise NovelGitSyncError(
                "A local-only secret or encrypted asset appeared during staging. "
                "Those paths were unstaged; no commit or push was attempted."
            )

        if staged_paths:
            message = (
                "Update novel via StoryBuilder Writer "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            _run_git(repository, "commit", "-m", message, timeout=60)
            committed = True

    _run_git(repository, "push", "origin", preview.branch, timeout=90)
    if committed:
        message = (
            f"Synced '{repository.name}' to GitHub on branch '{preview.branch}'. "
            "Local changes were committed and pushed."
        )
    else:
        message = (
            f"Synced '{repository.name}' to GitHub on branch '{preview.branch}'. "
            "No local file commit was needed."
        )

    return NovelSyncResult(
        repository=repository,
        branch=preview.branch,
        remote_url=preview.remote_url,
        committed=committed,
        changed_files=changed_files,
        message=message,
    )

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_TRACE_REPOSITORY_NAME = "StoryBuilder-Traces"
TRACE_FILENAME = "prompt_trace.json"
API_ROOT = "https://api.github.com"


class TraceSyncError(RuntimeError):
    """A trace could not be uploaded safely to its private GitHub repository."""


def _github_token() -> str:
    """Use an explicitly configured token or GitHub CLI auth; never persist it."""
    for name in (
        "STORYBUILDER_TRACE_GITHUB_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
    ):
        value = os.environ.get(name, "").strip()
        if value:
            return value

    gh = shutil.which("gh")
    if not gh:
        raise TraceSyncError(
            "GitHub trace sync needs the GitHub CLI. Install gh and sign in with "
            "gh auth login, or configure STORYBUILDER_TRACE_GITHUB_TOKEN."
        )

    try:
        result = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TraceSyncError(
            "Could not read GitHub CLI authentication. Check gh auth status."
        ) from exc

    token = (result.stdout or "").strip()
    if result.returncode != 0 or not token:
        raise TraceSyncError(
            "GitHub CLI is not authenticated. Run gh auth login and ensure the "
            "account can write to the private trace repository."
        )
    return token


def _api_request(
    token: str,
    method: str,
    endpoint: str,
    payload: dict | None = None,
    *,
    allow_404: bool = False,
) -> dict | None:
    url = f"{API_ROOT}{endpoint}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "StoryBuilder-private-prompt-trace",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read()
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        if allow_404 and exc.code in (404, 409):
            # Git database endpoints may report 409 for a repository with no refs.
            return None
        try:
            message = str(json.loads(error_body).get("message", "")).strip()
        except (ValueError, AttributeError):
            message = ""
        detail = f": {message[:300]}" if message else ""
        if exc.code in (401, 403, 404):
            detail += (
                " Check that the GitHub account/token can access this private "
                "repository and has Contents write permission."
            )
        raise TraceSyncError(f"GitHub API returned HTTP {exc.code}{detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TraceSyncError(
            f"Could not contact GitHub to sync the trace: {exc}"
        ) from exc

    if not raw:
        return {}
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TraceSyncError("GitHub returned an unreadable API response.") from exc
    if not isinstance(decoded, dict):
        raise TraceSyncError("GitHub returned an unexpected API response.")
    return decoded


def upload_prompt_trace(
    trace_path: str | os.PathLike[str],
    *,
    repository: str | None = None,
) -> dict[str, str | bool]:
    """Upload the latest trace to a private repo without retaining branch history.

    The destination branch is rewritten to a new root commit each time so its
    reachable history contains only the latest trace. The destination must be a
    dedicated single-file repository; any unrelated existing files block upload.
    This is overwrite behavior, not a secure-erasure guarantee for Git object storage.
    """
    try:
        configured_repo = (
            repository or os.environ.get("STORYBUILDER_TRACE_GITHUB_REPO", "")
        ).strip()
        if configured_repo and not re.fullmatch(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", configured_repo
        ):
            raise TraceSyncError(
                "Configure STORYBUILDER_TRACE_GITHUB_REPO as owner/repository."
            )

        path = os.fspath(trace_path)
        with open(path, "rb") as stream:
            trace_bytes = stream.read()
        if not trace_bytes:
            raise TraceSyncError("The local prompt trace is empty.")

        # Verify that the file is valid JSON before sending private story material.
        try:
            json.loads(trace_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise TraceSyncError(
                "The local prompt trace is not valid UTF-8 JSON; nothing was uploaded."
            ) from exc

        token = _github_token()
        repo = configured_repo
        if not repo:
            user_info = _api_request(token, "GET", "/user")
            login = str((user_info or {}).get("login") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9-]+", login):
                raise TraceSyncError(
                    "Could not determine the authenticated GitHub username. "
                    "Set STORYBUILDER_TRACE_GITHUB_REPO to owner/repository."
                )
            # Never default to another developer's private repository.
            repo = f"{login}/{DEFAULT_TRACE_REPOSITORY_NAME}"

        root = f"/repos/{repo}"
        repo_info = _api_request(token, "GET", root)
        if not repo_info or repo_info.get("private") is not True:
            raise TraceSyncError(
                f"Trace upload was blocked because {repo} is not confirmed private."
            )

        default_branch = str(repo_info.get("default_branch") or "main")
        branch_override = os.environ.get("STORYBUILDER_TRACE_GITHUB_BRANCH", "").strip()
        branch = branch_override or default_branch
        branch_path = quote(branch, safe="")
        # GitHub uses /git/ref/{ref} for reads but /git/refs/{ref}
        # for updates. Keep the two endpoints separate; using the singular
        # read endpoint for PATCH returns HTTP 404 on an existing branch.
        ref_endpoint = f"{root}/git/ref/heads/{branch_path}"
        update_ref_endpoint = f"{root}/git/refs/heads/{branch_path}"

        current_ref = _api_request(
            token, "GET", ref_endpoint, allow_404=True
        )
        if current_ref is None:
            if branch != default_branch:
                raise TraceSyncError(
                    "The configured trace branch does not exist. For an empty trace "
                    "repository, remove STORYBUILDER_TRACE_GITHUB_BRANCH or set it to "
                    "the repository's default branch."
                )
            # GitHub's Git Database API cannot create refs in an empty repository.
            # Contents API initializes the first branch and first root commit.
            initial = _api_request(
                token,
                "PUT",
                f"{root}/contents/{quote(TRACE_FILENAME, safe='')}",
                {
                    "message": "Initialize latest StoryBuilder prompt trace",
                    "content": base64.b64encode(trace_bytes).decode("ascii"),
                },
            )
            file_info = (initial or {}).get("content") or {}
            commit_info = (initial or {}).get("commit") or {}
            return {
                "ok": True,
                "repository": repo,
                "branch": branch,
                "url": str(file_info.get("html_url") or (
                    f"https://github.com/{repo}/blob/{quote(branch, safe='/')}/{TRACE_FILENAME}"
                )),
                "commit_url": str(commit_info.get("html_url") or ""),
            }

        if current_ref is not None:
            old_commit_sha = str(
                ((current_ref.get("object") or {}).get("sha") or "")
            ).strip()
            if not old_commit_sha:
                raise TraceSyncError(
                    "The destination branch exists but has no readable commit SHA."
                )
            old_commit = _api_request(
                token, "GET", f"{root}/git/commits/{quote(old_commit_sha, safe='')}"
            )
            old_tree_sha = str(((old_commit or {}).get("tree") or {}).get("sha") or "")
            if not old_tree_sha:
                raise TraceSyncError("Could not inspect the existing trace repository tree.")
            old_tree = _api_request(
                token,
                "GET",
                f"{root}/git/trees/{quote(old_tree_sha, safe='')}?{urlencode({'recursive': 1})}",
            )
            if old_tree and old_tree.get("truncated"):
                raise TraceSyncError(
                    "The trace repository tree is unexpectedly large; upload was stopped."
                )
            existing_paths = {
                str(item.get("path", ""))
                for item in (old_tree or {}).get("tree", [])
                if isinstance(item, dict) and item.get("type") != "tree"
            }
            if existing_paths - {TRACE_FILENAME}:
                raise TraceSyncError(
                    "The trace repository contains files other than prompt_trace.json. "
                    "No upload was made to avoid deleting unrelated content."
                )

        blob = _api_request(
            token,
            "POST",
            f"{root}/git/blobs",
            {
                "content": base64.b64encode(trace_bytes).decode("ascii"),
                "encoding": "base64",
            },
        )
        blob_sha = str((blob or {}).get("sha") or "")
        if not blob_sha:
            raise TraceSyncError("GitHub did not create a trace blob.")

        # No base_tree means this root tree intentionally contains just the trace.
        tree = _api_request(
            token,
            "POST",
            f"{root}/git/trees",
            {
                "tree": [
                    {
                        "path": TRACE_FILENAME,
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_sha,
                    }
                ]
            },
        )
        tree_sha = str((tree or {}).get("sha") or "")
        if not tree_sha:
            raise TraceSyncError("GitHub did not create a trace tree.")

        # A root commit keeps old runs out of the branch's visible commit history.
        commit = _api_request(
            token,
            "POST",
            f"{root}/git/commits",
            {
                "message": "Update latest StoryBuilder prompt trace",
                "tree": tree_sha,
                "parents": [],
            },
        )
        commit_sha = str((commit or {}).get("sha") or "")
        if not commit_sha:
            raise TraceSyncError("GitHub did not create the latest-trace commit.")

        _api_request(
            token,
            "PATCH",
            update_ref_endpoint,
            {"sha": commit_sha, "force": True},
        )

        return {
            "ok": True,
            "repository": repo,
            "branch": branch,
            "url": f"https://github.com/{repo}/blob/{quote(branch, safe='/')}/{TRACE_FILENAME}",
            "commit_url": str((commit or {}).get("html_url") or ""),
        }
    except Exception as exc:
        # Trace synchronization is diagnostic convenience only; it must never
        # turn a saved scene into a failed writing operation or expose credentials.
        message = str(exc).strip() or exc.__class__.__name__
        return {"ok": False, "error": message[:700]}

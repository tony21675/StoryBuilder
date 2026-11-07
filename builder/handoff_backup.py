from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


README_TEXT = """# Local project handoff backups

These are automatic local mirrors of the current project handoffs and story-direction notes.

- Source files remain authoritative in their own project repositories.
- This folder is an independent local safety copy, not a place to edit primary project records.
- The mirrors refresh when StoryBuilder starts and after a successful app or selected-novel GitHub sync.
- You can refresh them manually with: `bash ~/Documents/StoryBuilder/backup_handoffs.py`
- Only handoff and planning documents are copied. Manuscripts, model files, credentials, encrypted files, secret-letter assets, and other project data are not copied.
- Missing source files are skipped and are never used as a reason to delete an existing backup.

Default location: `~/Documents/Project_Handoff_Backups`
"""


class HandoffBackupError(RuntimeError):
    """Raised when the local handoff mirror cannot be refreshed safely."""


def _atomic_copy(source: Path, destination: Path) -> bool:
    """Copy one file atomically; return True only when the mirror changed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and source.read_bytes() == destination.read_bytes():
        return False

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return True


def refresh_handoff_backups(
    *,
    storybuilder_root: str | Path | None = None,
    novel_root: str | Path | None = None,
    backup_root: str | Path | None = None,
) -> list[str]:
    """Refresh a small local mirror of current project handoffs.

    Only named Markdown handoff/planning files are copied. This never runs Git,
    changes a source repository, deletes old backups, or copies manuscript/secret
    assets. Missing source files are skipped.
    """
    home = Path.home()
    app_root = (
        Path(storybuilder_root).expanduser().resolve()
        if storybuilder_root is not None
        else Path(__file__).resolve().parents[1]
    )
    novels = (
        Path(novel_root).expanduser().resolve()
        if novel_root is not None
        else Path(os.environ.get("STORY_NOVEL_ROOT", home / "Documents" / "MyNovel"))
        .expanduser()
        .resolve()
    )
    destination_root = (
        Path(backup_root).expanduser().resolve()
        if backup_root is not None
        else Path(
            os.environ.get(
                "STORY_HANDOFF_BACKUP_DIR",
                home / "Documents" / "Project_Handoff_Backups",
            )
        ).expanduser().resolve()
    )

    sources = [
        (app_root / "CHAT_HANDOFF_LATEST.md", "StoryBuilder/CHAT_HANDOFF_LATEST.md"),
        (app_root / "WRITER_APP_HANDOFF.md", "StoryBuilder/WRITER_APP_HANDOFF.md"),
        (app_root / "STORY_BIBLE_APP_HANDOFF.md", "StoryBuilder/STORY_BIBLE_APP_HANDOFF.md"),
        (
            novels / "The-Long-Way-Home" / "CHAT_HANDOFF_LATEST.md",
            "The-Long-Way-Home/CHAT_HANDOFF_LATEST.md",
        ),
        (
            novels / "The-Long-Way-Home" / "STORY_DIRECTION.md",
            "The-Long-Way-Home/STORY_DIRECTION.md",
        ),
        (
            novels / "Taken_at_Dusk" / "HANDOFF_LATEST.md",
            "Taken-at-Dusk/HANDOFF_LATEST.md",
        ),
        (
            novels / "Taken_at_Dusk" / "STORY_PLAN.md",
            "Taken-at-Dusk/STORY_PLAN.md",
        ),
        (
            novels / "Taken_at_Dusk" / "SECRET_LETTERS_STORAGE.md",
            "Taken-at-Dusk/SECRET_LETTERS_STORAGE.md",
        ),
    ]

    messages: list[str] = []
    copied = 0
    present = 0
    for source, relative_destination in sources:
        if not source.is_file():
            messages.append(f"SKIP (not found): {source}")
            continue
        present += 1
        destination = destination_root / relative_destination
        try:
            changed = _atomic_copy(source, destination)
        except OSError as exc:
            raise HandoffBackupError(
                f"Could not copy handoff '{source}' to '{destination}': {exc}"
            ) from exc
        if changed:
            copied += 1
            messages.append(f"UPDATED: {destination}")
        else:
            messages.append(f"CURRENT: {destination}")

    if present == 0:
        raise HandoffBackupError(
            "No known handoff source files were found. Check the StoryBuilder and novel paths."
        )

    readme = destination_root / "README.md"
    try:
        if not readme.is_file() or readme.read_text(encoding="utf-8") != README_TEXT:
            readme.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(
                prefix=".README.", suffix=".tmp", dir=readme.parent
            )
            os.close(fd)
            temporary = Path(temporary_name)
            try:
                temporary.write_text(README_TEXT, encoding="utf-8")
                os.replace(temporary, readme)
            except OSError:
                temporary.unlink(missing_ok=True)
                raise
    except OSError as exc:
        raise HandoffBackupError(f"Could not write local handoff backup README: {exc}") from exc

    messages.insert(0, f"Local handoff mirror: {destination_root} ({copied} updated, {present} found)")
    return messages

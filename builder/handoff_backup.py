from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


README_TEXT = """# Local project handoff backups

These are local mirrors of the current app and novel handoffs plus the separate story-direction/plan references.

- Each application and novel has one authoritative handoff in its own GitHub repository.
- Source files remain authoritative in their own project repositories.
- This folder is an independent local safety copy, not a place to edit primary project records.
- The mirrors refresh when StoryBuilder starts and after a successful app or selected-novel GitHub sync.
- You can refresh them manually with: `python3 ~/Documents/StoryBuilder/backup_handoffs.py`
- Manuscripts, model files, credentials, encrypted files, secret-letter files/references, and other project data are not mirrored by this utility.
- Refresh removes only two explicitly retired duplicate handoff copies: the old StoryBuilder handoff index and The Long Way Home's former CHAT_HANDOFF filename. It does not prune other project files or folders.

Default location: `~/Documents/Project_Handoff_Backups`
"""


# These are the only obsolete handoff copies this utility is allowed to remove.
# Secret-letter paths, novel content, and all other files are deliberately excluded.
_RETIRED_HANDOFF_COPIES = (
    Path("StoryBuilder/CHAT_HANDOFF_LATEST.md"),
    Path("The-Long-Way-Home/CHAT_HANDOFF_LATEST.md"),
)


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


def _remove_retired_handoff_copies(destination_root: Path) -> list[str]:
    """Remove only the two explicitly retired duplicate handoff paths."""
    messages: list[str] = []
    for relative_path in _RETIRED_HANDOFF_COPIES:
        target = destination_root / relative_path
        try:
            # unlink removes a symlink itself rather than following its target.
            if target.is_file() or target.is_symlink():
                target.unlink()
                messages.append(f"REMOVED RETIRED HANDOFF: {target}")
        except OSError as exc:
            raise HandoffBackupError(
                f"Could not remove retired handoff copy '{target}': {exc}"
            ) from exc
    return messages


def refresh_handoff_backups(
    *,
    storybuilder_root: str | Path | None = None,
    novel_root: str | Path | None = None,
    backup_root: str | Path | None = None,
) -> list[str]:
    """Refresh the current handoff mirror and prune only named retired copies.

    Only the listed Markdown handoffs and story-direction/plan references are copied.
    This never runs Git or edits source repositories. It removes only the two exact
    retired duplicate handoff paths above. Secret-letter paths and all other local
    backup contents are left untouched. Missing source files are skipped.
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
        (app_root / "WRITER_APP_HANDOFF.md", "StoryBuilder/WRITER_APP_HANDOFF.md"),
        (
            app_root / "STORY_BIBLE_APP_HANDOFF.md",
            "StoryBuilder/STORY_BIBLE_APP_HANDOFF.md",
        ),
        (
            novels / "The-Long-Way-Home" / "HANDOFF_LATEST.md",
            "The-Long-Way-Home/HANDOFF_LATEST.md",
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
            novels / "Summer-at-Willow-Bay" / "HANDOFF_LATEST.md",
            "Summer-at-Willow-Bay/HANDOFF_LATEST.md",
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

    messages.extend(_remove_retired_handoff_copies(destination_root))

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

    messages.insert(
        0,
        f"Local handoff mirror: {destination_root} ({copied} updated, {present} found)",
    )
    return messages

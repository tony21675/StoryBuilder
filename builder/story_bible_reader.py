from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


_TEXT_FIELDS = {"premise", "setting"}


def _parse_story_bible(content: bytes, bible_path: Path) -> dict[str, Any]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Story Bible is not valid UTF-8 text.") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Story Bible is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Story Bible must contain a JSON object at its top level.")

    return data


def load_story_bible(novel_path: str | Path) -> dict[str, Any]:
    """Read and validate one package's story_bible.json without modifying it."""
    bible_path = Path(novel_path).expanduser() / "story_bible.json"
    if not bible_path.is_file():
        raise FileNotFoundError(f"No story_bible.json was found at:\n{bible_path}")

    return _parse_story_bible(bible_path.read_bytes(), bible_path)


def save_story_bible_text_field(
    novel_path: str | Path, field_name: str, value: str
) -> Path:
    """Update one approved text field, preserving all other data atomically."""
    if field_name not in _TEXT_FIELDS:
        allowed = ", ".join(sorted(_TEXT_FIELDS))
        raise ValueError(f"Only these Story Bible text fields can be edited: {allowed}.")
    if not isinstance(value, str):
        raise ValueError(f"{field_name.title()} must be text.")

    bible_path = Path(novel_path).expanduser() / "story_bible.json"
    if not bible_path.is_file():
        raise FileNotFoundError(f"No story_bible.json was found at:\n{bible_path}")

    original_bytes = bible_path.read_bytes()
    data = _parse_story_bible(original_bytes, bible_path)
    data[field_name] = value
    output = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    original_mode = stat.S_IMODE(bible_path.stat().st_mode)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{bible_path.name}.",
            suffix=".tmp",
            dir=bible_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(output)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.chmod(temporary_path, original_mode)

        # Never replace a file that changed while this edit was being prepared.
        if not bible_path.is_file() or bible_path.read_bytes() != original_bytes:
            raise RuntimeError(
                "The Story Bible changed on disk while this edit was being saved. "
                "Cancel this edit, reload the Story Bible, and try again."
            )

        os.replace(temporary_path, bible_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return bible_path


def save_story_bible_premise(novel_path: str | Path, premise: str) -> Path:
    """Compatibility wrapper for the premise-only editing workflow."""
    return save_story_bible_text_field(novel_path, "premise", premise)

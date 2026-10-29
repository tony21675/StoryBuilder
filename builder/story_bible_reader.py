from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_story_bible(novel_path: str | Path) -> dict[str, Any]:
    """Read and validate one package's story_bible.json without modifying it."""
    bible_path = Path(novel_path).expanduser() / "story_bible.json"
    if not bible_path.is_file():
        raise FileNotFoundError(f"No story_bible.json was found at:\n{bible_path}")

    try:
        content = bible_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Story Bible is not valid UTF-8 text.") from exc

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Story Bible is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Story Bible must contain a JSON object at its top level.")

    return data

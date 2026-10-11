from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(
    os.environ.get("STORY_WORKSPACE_ROOT", str(REPO_ROOT.parent))
).expanduser().resolve()

MODELS_DIR = Path(
    os.environ.get("STORY_MODELS_DIR", str(WORKSPACE_ROOT / "Models"))
).expanduser().resolve()

LLAMA = Path(
    os.environ.get(
        "STORY_LLAMA_PATH",
        str(WORKSPACE_ROOT / "llama.cpp" / "build" / "bin" / "llama-cli"),
    )
).expanduser().resolve()

NOVEL_ROOT = Path(
    os.environ.get("STORY_NOVEL_ROOT", str(WORKSPACE_ROOT / "MyNovel"))
).expanduser().resolve()



def find_novel_packages(novel_root: Path | None = None) -> list[Path]:
    """Find novel packages in the one-level-deep novel library.

    A legacy package stored directly at the library path remains supported.
    Otherwise, only immediate child folders containing story_bible.json count
    as novels. Arbitrary descendant folders are intentionally not searched.
    """
    root = Path(novel_root or NOVEL_ROOT).expanduser()
    if (root / "story_bible.json").is_file():
        return [root]

    if not root.is_dir():
        return []

    try:
        candidates = [
            child
            for child in root.iterdir()
            if child.is_dir() and (child / "story_bible.json").is_file()
        ]
    except OSError:
        return []

    return sorted(candidates, key=lambda path: path.name.casefold())

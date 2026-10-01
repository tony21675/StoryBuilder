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
    os.environ.get("STORY_NOVEL_ROOT", str(REPO_ROOT / "MyNovel"))
).expanduser().resolve()

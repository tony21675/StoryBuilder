from __future__ import annotations

import re
from pathlib import Path


class ManuscriptManager:
    """Read and write accepted/draft scene text inside a novel package."""

    def __init__(self, novel_path: Path) -> None:
        self.novel_path = Path(novel_path)

    @property
    def chapters_dir(self) -> Path:
        return self.novel_path / "Manuscript" / "Chapters"

    @staticmethod
    def _safe_part(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip())
        return cleaned.strip("_") or fallback

    def scene_path(self, chapter: int, scene: int) -> Path:
        chapter_dir = self.chapters_dir / f"Chapter_{int(chapter):02d}"
        return chapter_dir / f"Scene_{int(scene):02d}.txt"

    def save_scene(self, chapter: int, scene: int, text: str) -> Path:
        target = self.scene_path(chapter, scene)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (text or "").strip() + "\n",
            encoding="utf-8",
        )
        return target

    def save_draft(self, chapter: int, scene: int, text: str) -> Path:
        target = self.scene_path(chapter, scene)
        draft = target.with_name(target.stem + "_draft.txt")
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(
            (text or "").strip() + "\n",
            encoding="utf-8",
        )
        return draft

    def list_scenes(self) -> list[Path]:
        if not self.chapters_dir.exists():
            return []
        return sorted(self.chapters_dir.rglob("Scene_*.txt"))

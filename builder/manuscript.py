from __future__ import annotations

from pathlib import Path


class ManuscriptManager:
    """Read and write scene/section text inside a novel package."""

    def __init__(self, novel_path: Path) -> None:
        self.novel_path = Path(novel_path)

    @property
    def chapters_dir(self) -> Path:
        return self.novel_path / "Manuscript" / "Chapters"

    def scene_path(self, chapter: int, scene: int) -> Path:
        chapter_dir = self.chapters_dir / f"Chapter_{int(chapter):02d}"
        chapter_dir.mkdir(parents=True, exist_ok=True)

        section = chapter_dir / (
            f"Chapter_{int(chapter):02d}_Section_{int(scene):02d}.txt"
        )
        legacy = chapter_dir / f"Scene_{int(scene):02d}.txt"

        if section.exists():
            return section
        if legacy.exists():
            return legacy
        return section

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

        return sorted(
            (
                path
                for path in self.chapters_dir.rglob("*.txt")
                if not path.name.endswith("_draft.txt")
            ),
            key=lambda path: (
                str(path.parent).casefold(),
                path.name.casefold(),
            ),
        )

    def recent_text(self, limit_chars: int = 16000) -> str:
        parts = []
        total = 0

        for path in reversed(self.list_scenes()):
            try:
                text = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue

            if not text:
                continue

            chunk = (
                f"\n[Manuscript File: {path.relative_to(self.novel_path)}]\n"
                + text
                + "\n"
            )

            remaining = limit_chars - total
            if remaining <= 0:
                break

            if len(chunk) > remaining:
                chunk = chunk[-remaining:]

            parts.append(chunk)
            total += len(chunk)

            if total >= limit_chars:
                break

        return "\n".join(reversed(parts)).strip()

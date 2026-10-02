from __future__ import annotations

import json
import re
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

    def state_before_path(self, chapter: int, scene: int) -> Path:
        target = self.scene_path(chapter, scene)
        return target.with_name(target.stem + "_before_state.json")

    def state_after_path(self, chapter: int, scene: int) -> Path:
        target = self.scene_path(chapter, scene)
        return target.with_name(target.stem + "_after_state.json")

    def save_state_before(self, chapter: int, scene: int, state: dict) -> Path:
        path = self.state_before_path(chapter, scene)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def save_state_after_candidate(self, chapter: int, scene: int, state: dict) -> Path:
        path = self.state_after_path(chapter, scene)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def load_state_before(self, chapter: int, scene: int) -> dict | None:
        path = self.state_before_path(chapter, scene)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def scene_numbers(path: Path) -> tuple[int, int] | None:
        match = re.search(
            r"Chapter_(\d+).*?(?:Section_(\d+)|Scene_(\d+))",
            path.name,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        scene = match.group(2) or match.group(3)
        if scene is None:
            return None
        return int(match.group(1)), int(scene)

    def save_draft(self, chapter: int, scene: int, text: str) -> Path:
        target = self.scene_path(chapter, scene)
        draft = target.with_name(target.stem + "_draft.txt")
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(
            (text or "").strip() + "\n",
            encoding="utf-8",
        )
        return draft

    @property
    def compiled_dir(self) -> Path:
        return self.novel_path / "Manuscript" / "Compiled"

    def chapter_scene_paths(self, chapter: int) -> list[Path]:
        chapter_dir = self.chapters_dir / f"Chapter_{int(chapter):02d}"
        if not chapter_dir.exists():
            return []

        paths = []
        for path in chapter_dir.glob("*.txt"):
            if path.name.endswith("_draft.txt"):
                continue
            if self.scene_numbers(path) is None:
                continue
            paths.append(path)

        return sorted(
            paths,
            key=lambda path: (
                self.scene_numbers(path)[1] if self.scene_numbers(path) else 999999,
                path.name.casefold(),
            ),
        )

    @staticmethod
    def _output_filename(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", str(name or "")).strip()
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned or "Complete_Novel"

    def _chapter_text(self, chapter: int) -> str:
        paths = self.chapter_scene_paths(chapter)
        if not paths:
            raise ValueError(f"No accepted manuscript sections were found for Chapter {int(chapter)}.")

        chunks = [f"CHAPTER {int(chapter)}"]
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise OSError(f"Could not read {path.name}: {exc}") from exc
            if text:
                chunks.append(text)

        if len(chunks) == 1:
            raise ValueError(f"Chapter {int(chapter)} has no manuscript prose to assemble.")

        return "\n\n".join(chunks).rstrip() + "\n"

    def compile_chapter(self, chapter: int) -> Path:
        self.compiled_dir.mkdir(parents=True, exist_ok=True)
        target = self.compiled_dir / f"Chapter_{int(chapter):02d}.txt"
        target.write_text(
            self._chapter_text(chapter),
            encoding="utf-8",
        )
        return target

    def compile_novel(self, title: str = "Complete_Novel") -> Path:
        chapter_numbers = sorted({
            self.scene_numbers(path)[0]
            for path in self.list_scenes()
            if self.scene_numbers(path) is not None
        })
        if not chapter_numbers:
            raise ValueError("No accepted manuscript sections were found to assemble.")

        self.compiled_dir.mkdir(parents=True, exist_ok=True)
        chapter_texts = []
        for chapter in chapter_numbers:
            chapter_texts.append(self._chapter_text(chapter))

        target = self.compiled_dir / f"{self._output_filename(title)}_Complete_Novel.txt"
        target.write_text(
            "\n\n".join(text.rstrip() for text in chapter_texts).rstrip() + "\n",
            encoding="utf-8",
        )
        return target

    def list_scenes(self) -> list[Path]:
        if not self.chapters_dir.exists():
            return []

        paths = []
        for path in self.chapters_dir.rglob("*.txt"):
            if path.name.endswith("_draft.txt"):
                continue
            relative_parts = path.relative_to(self.chapters_dir).parts
            if "Compiled" in relative_parts:
                continue
            if self.scene_numbers(path) is None:
                continue
            paths.append(path)

        return sorted(
            paths,
            key=lambda path: (
                self.scene_numbers(path)[0] if self.scene_numbers(path) else 999999,
                self.scene_numbers(path)[1] if self.scene_numbers(path) else 999999,
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

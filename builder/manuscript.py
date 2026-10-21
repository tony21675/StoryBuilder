from __future__ import annotations

import json
import re
from pathlib import Path

from builder.continuity_context import (
    estimate_tokens_from_chars,
    historical_relevance_tokens,
)


_HISTORICAL_CORRECTION_CUE = re.compile(
    r"\b(?:isn't|aren't|wasn't|weren't|doesn't|don't|didn't|hasn't|haven't|hadn't|"
    r"can't|cannot|ruled out|rather than|instead of|not\s+(?:caused by|due to|a|an|the|from|in|at|part of|because of|proof of))\b",
    re.IGNORECASE,
)


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

    def load_state_after(self, chapter: int, scene: int) -> dict | None:
        """Load the saved ending-state snapshot for an accepted scene."""
        path = self.state_after_path(chapter, scene)
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
        if match:
            scene = match.group(2) or match.group(3)
            if scene is not None:
                return int(match.group(1)), int(scene)

        # Older packages may retain Scene_XX.txt names within Chapter_XX
        # folders. Their chapter is encoded by the parent directory.
        chapter_match = re.search(r"Chapter_(\d+)", str(path.parent), flags=re.IGNORECASE)
        scene_match = re.search(r"(?:Section|Scene)_(\d+)", path.name, flags=re.IGNORECASE)
        if chapter_match and scene_match:
            return int(chapter_match.group(1)), int(scene_match.group(1))
        return None

    def save_draft(self, chapter: int, scene: int, text: str) -> Path:
        target = self.scene_path(chapter, scene)
        draft = target.with_name(target.stem + "_draft.txt")
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(
            (text or "").strip() + "\n",
            encoding="utf-8",
        )
        return draft

    def load_scene_for_state_review(
        self,
        chapter: int,
        scene: int,
        current_state: dict,
    ) -> dict | None:
        """Load the accepted scene matching the live pointer, if its baseline is safe.

        Returns the saved path, prose, and the scene's starting state. A mismatch
        between the saved before-state and the live state is rejected so Writer
        cannot analyze old prose against a different continuity baseline.
        """
        target = self.scene_path(chapter, scene)
        if not target.is_file():
            return None

        try:
            prose = target.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise OSError(f"Could not read saved scene {target.name}: {exc}") from exc
        if not prose:
            return None

        before_state = self.load_state_before(chapter, scene)
        if before_state is not None and before_state != current_state:
            raise ValueError(
                f"The saved starting state for {target.name} does not match the current story state. "
                "Use Manuscript → Analyze Saved Section to review this section safely; "
                "Writer has not loaded it."
            )

        baseline = before_state if before_state is not None else json.loads(
            json.dumps(current_state, ensure_ascii=False)
        )
        return {
            "path": target,
            "text": prose,
            "start_state": baseline,
        }


    def search_historical_context(
        self,
        query: str,
        *,
        before_chapter: int,
        before_scene: int,
        character_names: list[str] | None = None,
        limit: int = 4,
        max_chars: int = 2400,
        max_snippet_chars: int = 650,
    ) -> dict:
        """Retrieve small, source-labelled excerpts from accepted earlier scenes.

        This is a read-only search over the existing manuscript archive, not a
        second continuity database. Only scenes strictly before the target scene
        are eligible, preventing future/current manuscript text from leaking into
        generation. Excerpts are historical evidence and never override current
        state.
        """
        query_terms = historical_relevance_tokens(query)
        character_terms = set()
        for name in character_names or []:
            character_terms.update(historical_relevance_tokens(str(name)))
        query_terms.difference_update(character_terms)
        if not query_terms or int(limit) <= 0 or int(max_chars) <= 0:
            return {
                "snippets": [],
                "text": "",
                "characters": 0,
                "estimated_tokens": 0,
            }

        target = (int(before_chapter), int(before_scene))
        candidates = []
        scene_recency = 0
        for path in self.list_scenes():
            scene_numbers = self.scene_numbers(path)
            if scene_numbers is None or scene_numbers >= target:
                continue
            try:
                source_text = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if not source_text:
                continue

            # Paragraph chunks retain surrounding local context better than
            # isolated keyword fragments. Very long paragraphs are split into
            # sentences so one old scene cannot consume the retrieval budget.
            chunks = []
            for paragraph in re.split(r"\n\s*\n", source_text):
                paragraph = re.sub(r"\s+", " ", paragraph).strip()
                if not paragraph:
                    continue
                if len(paragraph) <= max_snippet_chars:
                    chunks.append(paragraph)
                else:
                    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if not sentence:
                            continue
                        if len(sentence) > max_snippet_chars:
                            sentence = sentence[:max_snippet_chars - 1].rstrip() + "…"
                        chunks.append(sentence)

            # Prefer higher lexical relevance. Recency breaks ties only; it does
            # not outrank a genuinely stronger match in an older scene.
            for chunk_index, chunk in enumerate(chunks):
                matched = sorted(historical_relevance_tokens(chunk) & query_terms)
                correction_cue = bool(_HISTORICAL_CORRECTION_CUE.search(chunk))
                # A single generic overlap is still insufficient. However, an
                # explicit correction/rejection relevant to the query may be
                # crucial continuity evidence even when it shares only one noun.
                if len(matched) < 2 and not (matched and correction_cue):
                    continue
                score = len(matched) * 10 + min(5, len(matched) // 2)
                if correction_cue:
                    score += 15
                candidates.append({
                    "source": str(path.relative_to(self.novel_path)),
                    "chapter": scene_numbers[0],
                    "scene": scene_numbers[1],
                    "text": chunk,
                    "matched_terms": matched,
                    "is_correction": correction_cue,
                    "score": score,
                    "recency": scene_recency,
                    "chunk_index": chunk_index,
                })
            scene_recency += 1

        # Prefer one excerpt per source scene, but permit one additional
        # explicitly corrective excerpt so a high-scoring passage does not hide
        # a rejected hypothesis from the same accepted scene.
        candidates.sort(
            key=lambda item: (item["score"], item["chapter"], item["scene"], -item["chunk_index"]),
            reverse=True,
        )
        chosen = []
        source_counts = {}
        total_chars = 0
        for item in candidates:
            source_key = (item["chapter"], item["scene"])
            count_for_source = source_counts.get(source_key, 0)
            if count_for_source >= 2 or (count_for_source == 1 and not item.get("is_correction")):
                continue
            formatted = (
                f"[Historical source: {item['source']} | "
                f"matched: {', '.join(item['matched_terms'])}]\n"
                f"{item['text']}"
            )
            added_chars = len(formatted) + (2 if chosen else 0)
            if total_chars + added_chars > int(max_chars):
                separator_chars = 2 if chosen else 0
                header = (
                    f"[Historical source: {item['source']} | "
                    f"matched: {', '.join(item['matched_terms'])}]\n"
                )
                remaining_text_chars = int(max_chars) - total_chars - separator_chars - len(header)
                if remaining_text_chars < 80:
                    continue
                item = dict(item)
                item["text"] = item["text"][:remaining_text_chars].rstrip()
                formatted = header + item["text"]
                added_chars = len(formatted) + separator_chars
            chosen.append(item)
            source_counts[source_key] = count_for_source + 1
            total_chars += added_chars
            if len(chosen) >= int(limit) or total_chars >= int(max_chars):
                break

        rendered = "\n\n".join(
            f"[Historical source: {item['source']} | matched: {', '.join(item['matched_terms'])}]\n"
            f"{item['text']}"
            for item in chosen
        )
        return {
            "snippets": chosen,
            "text": rendered,
            "characters": len(rendered),
            "estimated_tokens": estimate_tokens_from_chars(len(rendered)),
        }

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

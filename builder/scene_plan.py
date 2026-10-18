from __future__ import annotations

import re
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*#*[ \t]*$")
_CHAPTER_RE = re.compile(r"\bchapter\s+(\d+)\b", re.IGNORECASE)
_EXPLICIT_SCENE_RE = re.compile(
    r"^(?:(?:confirmed|proposed|open|planned)\s*:\s*)?"
    r"chapter\s+(\d+)\b.*?\bscene\s+(\d+)\b",
    re.IGNORECASE,
)
_SCENE_RE = re.compile(r"^scene\s+(\d+)\b", re.IGNORECASE)
_NUMBERED_SCENE_RE = re.compile(r"^(\d+)\s*[./]\s*(\d+)\b")


def _scene_heading(title: str, current_chapter: int | None) -> tuple[int | None, int, str] | None:
    """Return (chapter, scene, display title) for a recognized scene heading."""
    text = title.strip()

    match = _EXPLICIT_SCENE_RE.match(text)
    if match:
        chapter, scene = int(match.group(1)), int(match.group(2))
        display = re.sub(
            r"^(?:(?:confirmed|proposed|open|planned)\s*:\s*)?"
            r"chapter\s+\d+\b\s*[,;:/\-–— ]*\s*scene\s+\d+\s*[:.\-–—]?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" \t:.-–—")
        return chapter, scene, display or text

    match = _NUMBERED_SCENE_RE.match(text)
    if match:
        chapter, scene = int(match.group(1)), int(match.group(2))
        display = re.sub(
            r"^\d+\s*[./]\s*\d+\s*[:.\-–—]?\s*", "", text
        ).strip(" \t:.-–—")
        return chapter, scene, display or text

    match = _SCENE_RE.match(text)
    if match:
        scene = int(match.group(1))
        display = re.sub(
            r"^scene\s+\d+\s*[:.\-–—]?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" \t:.-–—")
        return current_chapter, scene, display or text

    return None


def find_scene_idea(markdown: str, chapter: int, scene: int) -> str | None:
    """Extract one planned scene title and its body from a Markdown story plan.

    A scene without its own chapter number inherits the latest enclosing/preceding
    heading that names a chapter. The returned body ends at the next heading of
    the same or higher level, so neighboring scene plans are not pulled in.
    """
    lines = str(markdown or "").splitlines()
    current_chapter: int | None = None

    for index, line in enumerate(lines):
        heading_match = _HEADING_RE.match(line)
        if not heading_match:
            continue

        level = len(heading_match.group(1))
        heading_title = heading_match.group(2).strip()
        # A scene title may mention another chapter in its prose. Only update
        # inherited chapter context from non-scene headings or explicit
        # "Chapter N, Scene M" headings.
        is_scene_label = (
            _SCENE_RE.match(heading_title) is not None
            or _NUMBERED_SCENE_RE.match(heading_title) is not None
        )
        chapter_match = _CHAPTER_RE.search(heading_title)
        if chapter_match and not is_scene_label:
            current_chapter = int(chapter_match.group(1))

        scene_info = _scene_heading(heading_title, current_chapter)
        if scene_info is None:
            continue
        heading_chapter, heading_scene, display_title = scene_info
        if heading_chapter != int(chapter) or heading_scene != int(scene):
            continue

        end_index = len(lines)
        for later_index in range(index + 1, len(lines)):
            later_heading = _HEADING_RE.match(lines[later_index])
            if later_heading and len(later_heading.group(1)) <= level:
                end_index = later_index
                break

        body = "\n".join(lines[index + 1 : end_index]).strip()
        if display_title and body:
            return f"{display_title}\n\n{body}".strip()
        if body:
            return body
        if display_title:
            return display_title
        return None

    return None


def load_scene_idea_from_plan(
    package_path: str | Path | None,
    chapter: int,
    scene: int,
) -> str | None:
    """Read a scene from STORY_PLAN.md in the active novel package, if present."""
    if package_path is None:
        return None

    package_dir = Path(package_path)
    if not package_dir.is_dir():
        return None

    plan_path = next(
        (
            path
            for path in package_dir.iterdir()
            if path.is_file() and path.name.casefold() == "story_plan.md"
        ),
        None,
    )
    if plan_path is None:
        return None

    return find_scene_idea(
        plan_path.read_text(encoding="utf-8"),
        int(chapter),
        int(scene),
    )

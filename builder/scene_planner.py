from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from builder.scene_plan import (
    _CHAPTER_RE, _EXPLICIT_SCENE_RE, _HEADING_RE, _NUMBERED_SCENE_RE,
    _SCENE_RE, _scene_heading,
)
from builder.workspace import LLAMA as DEFAULT_LLAMA

PLAN_FILENAME = "STORY_PLAN.md"
MAX_PLAN_CONTEXT_CHARS = 8500
MAX_CONVERSATION_MESSAGES = 8
MAX_MESSAGE_CHARS = 950


def find_story_plan_file(package_path: str | Path) -> Path:
    """Return the existing STORY_PLAN.md path, or its canonical path if new."""
    package_dir = Path(package_path).expanduser()
    if not package_dir.is_dir():
        raise FileNotFoundError(f"The active novel folder does not exist: {package_dir}")
    matches = [
        path for path in package_dir.iterdir()
        if path.is_file() and path.name.casefold() == PLAN_FILENAME.casefold()
    ]
    if len(matches) > 1:
        raise ValueError(
            "More than one file matches STORY_PLAN.md by name, including capitalization. "
            "Resolve the duplicate filenames before planning."
        )
    return matches[0] if matches else package_dir / PLAN_FILENAME


def read_story_plan_file(package_path: str | Path) -> tuple[Path, str | None]:
    """Read the plan without changing it; missing plan files are allowed."""
    path = find_story_plan_file(package_path)
    try:
        return path, path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return path, None


def _clean_model_output(output: str, prompt: str) -> str:
    """Return generated text only, omitting echoed prompt and llama.cpp footer noise."""
    cleaned = str(output or "")
    cleaned = re.sub(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", cleaned)

    # Some llama.cpp builds still echo --prompt even with --no-display-prompt.
    # Prefer the exact full prompt, then fall back to its distinctive final line
    # in case the CLI alters leading characters or spacing while echoing it.
    prompt_index = cleaned.find(prompt) if prompt else -1
    if prompt_index >= 0:
        cleaned = cleaned[prompt_index + len(prompt):]
    elif prompt:
        prompt_tail = prompt.rstrip().rsplit("\n", 1)[-1]
        tail_index = cleaned.rfind(prompt_tail) if prompt_tail else -1
        if tail_index >= 0:
            cleaned = cleaned[tail_index + len(prompt_tail):]

    # These are CLI timing/exit lines, not part of the model's answer.
    cleaned = re.sub(r"(?m)^[ \t]*\[[ \t]*Prompt:.*\][ \t]*$", "", cleaned)
    cleaned = re.sub(r"(?m)^[ \t]*Exiting\.\.\.[ \t]*$", "", cleaned)
    return cleaned.strip()


def _extract_object(
    raw: str, *, required_string_fields: Sequence[str] = ()
) -> dict[str, Any]:
    """Extract the last JSON object matching the requested fields.

    The generated text may be preceded by echoed context containing other JSON
    objects. Choosing the first dictionary can accidentally select that context
    instead of the model's actual response.
    """
    cleaned = (raw or "").strip()
    decoder = json.JSONDecoder()
    matching: list[dict[str, Any]] = []
    found_dict = False
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        found_dict = True
        if all(isinstance(value.get(key), str) for key in required_string_fields):
            matching.append(value)

    if matching:
        return matching[-1]
    if found_dict and required_string_fields:
        fields = " and ".join(required_string_fields)
        raise ValueError(
            f"The local model's proposal must contain string fields {fields}. No file was changed."
        )
    raise ValueError(
        "The local model did not return a readable scene-plan proposal. "
        "Your conversation and existing plan were left unchanged. Try preparing the proposal again."
    )


def _chapter_heading_match(title: str):
    return re.match(
        r"^(?:(?:confirmed|proposed|open|planned)\s*:\s*)?chapter\s+(\d+)\b",
        title.strip(), re.IGNORECASE,
    )


def _scan_plan(markdown: str):
    lines = str(markdown or "").splitlines()
    current_chapter: int | None = None
    chapter_headings, scenes = [], []
    for index, line in enumerate(lines):
        heading = _HEADING_RE.match(line)
        if not heading:
            continue
        level = len(heading.group(1))
        title = heading.group(2).strip()
        short_scene_label = bool(_SCENE_RE.match(title) or _NUMBERED_SCENE_RE.match(title))
        chapter_match = _CHAPTER_RE.search(title)
        if chapter_match and not short_scene_label:
            current_chapter = int(chapter_match.group(1))
        scene_info = _scene_heading(title, current_chapter)
        if scene_info is not None:
            chapter, scene, display_title = scene_info
            if chapter is not None:
                scenes.append({
                    "chapter": chapter, "scene": scene, "index": index,
                    "level": level, "heading_title": title, "display_title": display_title,
                })
            continue
        chapter_heading = _chapter_heading_match(title)
        if chapter_heading:
            chapter_headings.append({
                "chapter": int(chapter_heading.group(1)), "index": index,
                "level": level, "heading_title": title,
            })
    return lines, chapter_headings, scenes


def _section_end(lines: list[str], start: int, level: int) -> int:
    for index in range(start + 1, len(lines)):
        heading = _HEADING_RE.match(lines[index])
        if heading and len(heading.group(1)) <= level:
            return index
    return len(lines)


def _plan_excerpt(markdown: str | None, chapter: int) -> str:
    text = str(markdown or "").strip()
    if not text:
        return "(No STORY_PLAN.md exists yet. No scene plan has been saved.)"
    if len(text) <= MAX_PLAN_CONTEXT_CHARS:
        return text
    lines, chapter_headings, _scenes = _scan_plan(text)
    matching = [item for item in chapter_headings if item["chapter"] == chapter]
    chapter_excerpt = ""
    if len(matching) == 1:
        item = matching[0]
        chapter_excerpt = "\n".join(
            lines[item["index"]:_section_end(lines, item["index"], item["level"])]
        ).strip()
    prefix, tail = text[:2200].rstrip(), text[-900:].lstrip()
    budget = max(800, MAX_PLAN_CONTEXT_CHARS - len(prefix) - len(tail) - 120)
    chapter_excerpt = chapter_excerpt[:budget].rstrip()
    if chapter_excerpt:
        parts = [
            "GLOBAL PLAN CONTEXT (opening portion):", prefix,
            "[Other material omitted to fit the local model context.]",
            f"CHAPTER {chapter} CONTEXT:", chapter_excerpt,
            "PLAN CONTEXT (ending portion, may contain global constraints):", tail,
        ]
        return "\n\n".join(parts)[:MAX_PLAN_CONTEXT_CHARS]
    return (prefix + "\n\n[Middle of the plan omitted.]\n\n" + tail)[:MAX_PLAN_CONTEXT_CHARS]


def _compact_canon(story_bible: dict[str, Any], characters: dict[str, Any]) -> str:
    rules = story_bible.get("canon_rules", [])
    if isinstance(rules, str):
        rules = [item.strip() for item in rules.splitlines() if item.strip()]
    if not isinstance(rules, list):
        rules = []
    planning = story_bible.get("story_planning", {})
    relationships = story_bible.get("relationships", {})
    locations = story_bible.get("locations", {})
    if not isinstance(planning, dict):
        planning = {}
    if not isinstance(relationships, dict):
        relationships = {}
    if not isinstance(locations, dict):
        locations = {}
    character_rows = []
    if isinstance(characters, dict):
        for filename, item in list(characters.items())[:10]:
            if not isinstance(item, dict):
                continue
            row = {"name": str(item.get("name") or Path(str(filename)).stem)}
            for key in ("role", "occupation", "description", "personality", "background",
                        "relationships", "knowledge_rule"):
                value = item.get(key)
                if isinstance(value, (str, int, float)) and str(value).strip():
                    row[key] = str(value).strip()[:220]
            character_rows.append(row)
    compact = {
        "title": story_bible.get("title", ""),
        "premise": str(story_bible.get("premise", "") or "")[:1000],
        "canon_rules": [str(item)[:400] for item in rules[:12]],
        "story_planning": {str(key): value for key, value in list(planning.items())[:8]},
        "relationships": {str(key): str(value)[:250] for key, value in list(relationships.items())[:10]},
        "locations": {str(key): str(value)[:250] for key, value in list(locations.items())[:6]},
        "characters": character_rows,
    }
    return json.dumps(compact, indent=2, ensure_ascii=False)[:4000]


def _render_history(messages: Sequence[dict[str, str]]) -> str:
    rendered = []
    for message in list(messages or [])[-MAX_CONVERSATION_MESSAGES:]:
        role = str(message.get("role", "")).casefold()
        if role not in {"user", "assistant"}:
            continue
        content = str(message.get("content", "") or "").strip()
        if not content:
            continue
        if len(content) > MAX_MESSAGE_CHARS:
            content = content[:MAX_MESSAGE_CHARS].rstrip() + "\n[This message was shortened for context.]"
        rendered.append(f"{'AUTHOR' if role == 'user' else 'PLANNER'}:\n{content}")
    return "\n\n".join(rendered) or "(The author has not sent a message yet.)"


def _build_context(*, chapter: int, scene: int, plan_text: str | None,
                   story_context: dict[str, Any]) -> str:
    state = story_context.get("current_state", {})
    canon = story_context.get("story_bible", {})
    characters = story_context.get("characters", {})
    if not isinstance(state, dict):
        state = {}
    if not isinstance(canon, dict):
        canon = {}
    if not isinstance(characters, dict):
        characters = {}
    state_excerpt = {
        "chapter": chapter, "scene": scene,
        "location": state.get("location", ""),
        "time": state.get("time", state.get("time_of_day", "")),
        "scene_cast": state.get("scene_cast", []),
        "current_situation": str(state.get("current_situation", "") or "")[:1800],
    }
    sections = [
        "TARGET SCENE:\n" + json.dumps({"chapter": chapter, "scene": scene}, indent=2),
        "CURRENT STARTING STATE (reference, not a scene requirement list):\n"
        + json.dumps(state_excerpt, indent=2, ensure_ascii=False),
        "ESTABLISHED STORY CANON (reference only):\n" + _compact_canon(canon, characters),
        "EXISTING STORY_PLAN.md (read-only reference; the app changes nothing during conversation):\n"
        + _plan_excerpt(plan_text, chapter),
    ]
    saved_idea = str(story_context.get("saved_scene_idea", "") or "").strip()
    if saved_idea:
        sections.append(
            "EXISTING SAVED SCENE IDEA (may be older than the current plan; treat it as context, not as permission to change canon):\n"
            + saved_idea[:1800]
        )
    return "\n\n".join(sections)


def _run_model(model_path: str | Path, *, system_prompt: str, prompt: str,
               max_predict: int, temperature: str) -> str:
    model = Path(os.path.expanduser(str(model_path))).resolve()
    if model.suffix.casefold() != ".gguf" or not model.is_file():
        raise ValueError("The selected model is not a valid GGUF file.")
    if not DEFAULT_LLAMA.is_file():
        raise FileNotFoundError(f"llama-cli not found: {DEFAULT_LLAMA}")
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(DEFAULT_LLAMA.parent) + (
        ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
    )
    device = os.environ.get("STORY_LLM_DEVICE", "").strip()
    args = [
        str(DEFAULT_LLAMA), "-m", str(model),
        "-ngl", "all" if device else "0", "--device", device or "none",
        "-c", "8192", "--reasoning", "off", "--temp", temperature,
        "--top-k", "20", "--top-p", "0.80", "--repeat-last-n", "256",
        "--repeat-penalty", "1.08", "--n-predict", str(max_predict),
        "--system-prompt", system_prompt, "--prompt", prompt, "--color", "off",
        "--no-display-prompt", "--simple-io", "--single-turn",
    ]
    proc = None
    try:
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            text=True, encoding="utf-8", errors="replace",
        )
        output, diagnostics = proc.communicate(timeout=600)
    except subprocess.TimeoutExpired as exc:
        if proc is not None:
            proc.kill()
            proc.communicate()
        raise TimeoutError("The local model timed out while planning. No plan file was changed.") from exc
    if proc.returncode not in (0, None):
        details = (diagnostics or output or "").strip()
        raise RuntimeError("The local model failed while planning.\n" + details[-3000:])
    response = _clean_model_output(output or "", prompt)
    if not response:
        details = (diagnostics or "").strip()
        suffix = f" Diagnostics: {details[-1200:]}" if details else ""
        raise ValueError("The local model returned an empty response. No plan file was changed." + suffix)
    return response


def generate_scene_planner_reply(model_path: str | Path, *, chapter: int, scene: int,
                                 plan_text: str | None, story_context: dict[str, Any],
                                 messages: Sequence[dict[str, str]]) -> str:
    """Generate one conversational planning turn without changing any file."""
    system_prompt = (
        "You are StoryBuilder's Scene Planner, a collaborative planning partner for a novelist. "
        "Help the author decide what a scene should accomplish and how its events should unfold. "
        "The author is the source of story canon and has the final decision. Do not write finished scene prose. "
        "Do not invent consequential facts, clues, motives, identities, relationships, future events, or outcomes. "
        "Distinguish established facts from suggestions and unresolved questions. Do not treat your own suggestions as "
        "confirmed. Ask one focused follow-up question at a time when an important decision is genuinely unresolved; "
        "otherwise offer a concise useful plan discussion and let the author choose. Keep the plan from advancing past "
        "the scene's intended endpoint. Never claim that you saved or changed any file. The application does not write "
        "anything during this conversation."
    )
    prompt = (
        _build_context(chapter=chapter, scene=scene, plan_text=plan_text, story_context=story_context)
        + "\n\nPLANNING CONVERSATION SO FAR:\n" + _render_history(messages)
        + "\n\nReply to the author's latest message as a thoughtful planning partner. Be clear and fairly concise. "
        "If a detail can safely remain open, do not force the author to decide it now."
    )
    return _run_model(
        model_path, system_prompt=system_prompt, prompt=prompt,
        max_predict=900, temperature="0.20",
    )


def validate_scene_plan_fields(title: str, plan_body: str, *, chapter: int, scene: int) -> dict[str, str]:
    """Validate editable proposal fields before a targeted Markdown update."""
    normalized_title = str(title or "").strip()
    body = str(plan_body or "").strip()
    normalized_title = re.sub(
        rf"^(?:chapter\s+{int(chapter)}\s*[,;:/-]?\s*)?scene\s+{int(scene)}\s*[:.\-–—]?\s*",
        "", normalized_title, flags=re.IGNORECASE,
    ).strip(" \t:.-–—")
    normalized_title = re.sub(
        rf"^{int(chapter)}\s*[./]\s*{int(scene)}\s*[:.\-–—]?\s*",
        "", normalized_title,
    ).strip(" \t:.-–—")
    if not normalized_title:
        raise ValueError("Give the scene a title before approving the plan.")
    if len(normalized_title) > 140 or "\n" in normalized_title or "\r" in normalized_title:
        raise ValueError("The scene title must fit on one line and be no longer than 140 characters.")
    if any(ord(char) < 32 for char in normalized_title):
        raise ValueError("The scene title contains a control character.")
    if not body:
        raise ValueError("The scene plan body is empty. Nothing was saved.")
    if len(body) > 25000:
        raise ValueError("The scene plan is too long. Keep it under 25,000 characters.")
    if re.search(r"(?m)^\s{0,3}#{1,6}\s+", body):
        raise ValueError(
            "The plan body contains a Markdown heading. The Scene Planner manages the scene heading "
            "itself, so replace internal headings with bold labels before saving."
        )
    return {"title": normalized_title, "plan_body": body}


def prepare_scene_plan_proposal(model_path: str | Path, *, chapter: int, scene: int,
                                plan_text: str | None, story_context: dict[str, Any],
                                messages: Sequence[dict[str, str]]) -> dict[str, str]:
    """Ask the model for a reviewable scene section; this does not write it."""
    system_prompt = (
        "You prepare an editable scene-plan proposal for StoryBuilder. The author alone decides what becomes canon. "
        "Use the supplied story plan, current state, and conversation as reference. Do not invent facts, clues, motives, "
        "identities, relationships, or later outcomes. Preserve the requested scene endpoint and hard stops. Do not turn "
        "suggestions from the planner into confirmed facts unless the author explicitly accepted them. Keep unresolved "
        "choices explicitly open or mark them as proposed. The result is only a proposal for review, never a saved change. "
        "Return one valid JSON object with string fields title and plan_body. Return JSON only."
    )
    context = _build_context(chapter=chapter, scene=scene, plan_text=plan_text, story_context=story_context)
    prompt = (
        context + "\n\nPLANNING CONVERSATION:\n" + _render_history(messages)
        + "\n\nCreate a concise plan body for Chapter " + str(chapter) + ", Scene " + str(scene) + ". "
        "Use the conversation as the author's most recent intent while preserving established canon and prior-scene "
        "continuity. Include the scene's purpose, starting point or handoff, meaningful beats in order, and a clear "
        "hard stop/end. Add boundaries only where useful. Leave ordinary dialogue, gestures, and connective prose flexible. "
        "Do not write the finished scene. Do not repeat the chapter/scene heading inside plan_body. Use bold labels and "
        "bullets, not Markdown heading lines beginning with #. Mark unresolved information OPEN or PROPOSED.\n\n"
        "Return only this JSON shape, with the plan_body value containing Markdown:\n"
        + json.dumps({"title": "Short scene title", "plan_body": "Purpose and planned beats..."},
                     ensure_ascii=False)
    )
    raw = _run_model(
        model_path, system_prompt=system_prompt, prompt=prompt,
        max_predict=1900, temperature="0.10",
    )
    proposal = _extract_object(raw, required_string_fields=("title", "plan_body"))
    return validate_scene_plan_fields(
        proposal["title"], proposal["plan_body"], chapter=chapter, scene=scene,
    )


def _format_replacement_heading(existing_title: str, *, level: int, chapter: int,
                                scene: int, title: str) -> str:
    status_match = re.match(r"^((?:confirmed|proposed|open|planned)\s*:\s*)",
                            existing_title, re.IGNORECASE)
    status = status_match.group(1) if status_match else ""
    if _EXPLICIT_SCENE_RE.match(existing_title):
        new_title = f"Chapter {chapter}, Scene {scene}: {title}"
    elif _NUMBERED_SCENE_RE.match(existing_title):
        new_title = f"{chapter}.{scene}: {title}"
    else:
        new_title = f"Scene {scene}: {title}"
    return ("#" * level) + " " + status + new_title


def _join_replaced_section(lines: list[str], start: int, end: int,
                           new_heading: str, body: str) -> list[str]:
    prefix, suffix = list(lines[:start]), list(lines[end:])
    while prefix and not prefix[-1].strip():
        prefix.pop()
    while suffix and not suffix[0].strip():
        suffix.pop()
    return prefix + [new_heading, "", *body.strip().splitlines(), ""] + suffix


def update_scene_plan_markdown(markdown: str, chapter: int, scene: int,
                               title: str, plan_body: str) -> str:
    """Insert or replace exactly one scene section, preserving other sections."""
    fields = validate_scene_plan_fields(title, plan_body, chapter=chapter, scene=scene)
    title, body = fields["title"], fields["plan_body"]
    source = str(markdown or "")
    lines, chapter_headings, scenes = _scan_plan(source)
    matching_scenes = [item for item in scenes
                       if item["chapter"] == int(chapter) and item["scene"] == int(scene)]
    if len(matching_scenes) > 1:
        raise ValueError(
            f"STORY_PLAN.md contains more than one heading for Chapter {chapter}, Scene {scene}. "
            "Resolve the duplicate headings before replacing this scene."
        )
    if matching_scenes:
        item = matching_scenes[0]
        end = _section_end(lines, item["index"], item["level"])
        heading = _format_replacement_heading(
            item["heading_title"], level=item["level"], chapter=int(chapter),
            scene=int(scene), title=title,
        )
        return "\n".join(_join_replaced_section(lines, item["index"], end, heading, body)).rstrip("\n") + "\n"

    if not source.strip():
        return (
            "# Story Plan\n\n## Chapter " + str(int(chapter)) + "\n\n"
            + "### Scene " + str(int(scene)) + ": " + title + "\n\n" + body + "\n"
        )

    matching_chapters = [item for item in chapter_headings if item["chapter"] == int(chapter)]
    if len(matching_chapters) > 1:
        raise ValueError(
            f"STORY_PLAN.md has multiple possible Chapter {chapter} sections. The scene was not inserted."
        )
    if len(matching_chapters) == 1:
        chapter_heading = matching_chapters[0]
        chapter_end = _section_end(lines, chapter_heading["index"], chapter_heading["level"])
        chapter_scenes = [
            item for item in scenes
            if item["chapter"] == int(chapter)
            and chapter_heading["index"] < item["index"] < chapter_end
        ]
        if chapter_scenes:
            later = [item for item in chapter_scenes if item["scene"] > int(scene)]
            if later:
                insertion = min(later, key=lambda item: item["index"])["index"]
            else:
                last_scene = max(chapter_scenes, key=lambda item: item["index"])
                insertion = _section_end(lines, last_scene["index"], last_scene["level"])
            level = chapter_scenes[0]["level"]
        else:
            insertion = chapter_heading["index"] + 1
            level = min(6, chapter_heading["level"] + 1)
        heading = ("#" * level) + f" Scene {int(scene)}: {title}"
        return "\n".join(_join_replaced_section(lines, insertion, insertion, heading, body)).rstrip("\n") + "\n"

    if any(_EXPLICIT_SCENE_RE.match(item["heading_title"]) for item in scenes):
        level = min(6, max(item["level"] for item in scenes))
        heading = ("#" * level) + f" Chapter {int(chapter)}, Scene {int(scene)}: {title}"
        return "\n".join(_join_replaced_section(lines, len(lines), len(lines), heading, body)).rstrip("\n") + "\n"

    raise ValueError(
        f"Could not find a clear Chapter {chapter} section in STORY_PLAN.md. No scene was inserted. "
        "Add or correct the chapter heading, then prepare the proposal again."
    )


def save_scene_plan_file(path: str | Path, content: str) -> Path | None:
    """Write atomically and keep a prior file in StoryBuilder's private local backups."""
    target = Path(path).expanduser()
    if not target.parent.is_dir():
        raise FileNotFoundError(f"The novel folder does not exist: {target.parent}")
    backup_path = None
    existing_mode = None
    if target.exists():
        existing_mode = stat.S_IMODE(target.stat().st_mode)
        backup_dir = Path.home() / ".local" / "share" / "storybuilder" / "scene_plan_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        safe_novel = re.sub(r"[^A-Za-z0-9._-]+", "_", target.parent.name).strip("._") or "novel"
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time_ns() % 1_000_000_000):09d}"
        backup_path = backup_dir / f"{safe_novel}-{stamp}-{PLAN_FILENAME}"
        shutil.copy2(target, backup_path)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            prefix=f".{target.name}.", suffix=".tmp",
            dir=str(target.parent), delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(str(content))
            handle.flush()
            os.fsync(handle.fileno())
        if existing_mode is not None:
            os.chmod(temp_path, existing_mode)
        os.replace(temp_path, target)
    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return backup_path

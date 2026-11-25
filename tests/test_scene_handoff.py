from __future__ import annotations

import json

from builder.scene_handoff import (
    build_handoff_extraction_prompt,
    format_scene_handoff,
    handoff_path,
    load_scene_handoff,
    parse_handoff_response,
    save_scene_handoff,
)


def sample_handoff():
    return {
        "ending": "Wednesday, 9:20 PM, in the theatre near the side entrance. The handle moves.",
        "events": ["Mara discovers the brass key missing.", "They find a note reading SIDE DOOR - 9:15."],
        "character_knowledge": {
            "Mara": "She remembers placing the key on the office hook.",
            "Eli": "He borrowed and returned the clipboard.",
            "June": "She saw the office door ajar around 8:20 and says she did not enter.",
        },
        "physical_continuity": ["The red lanyard remains on the hook without the key.", "The clipboard is on the prop table."],
        "unresolved": ["Who wrote the note?", "Who is outside the side door?"],
    }


def test_handoff_saved_and_loaded_only_for_matching_source(tmp_path):
    scene_path = tmp_path / "Chapter_01_Section_01.odt"
    scene = "Accepted manuscript scene text."
    scene_path.write_text("placeholder", encoding="utf-8")
    save_scene_handoff(scene_path, scene, sample_handoff())

    loaded = load_scene_handoff(scene_path, scene)
    assert loaded == sample_handoff()
    assert load_scene_handoff(scene_path, scene + " edited") is None
    assert handoff_path(scene_path).exists()


def test_handoff_format_contains_key_sections():
    formatted = format_scene_handoff(sample_handoff(), 1, 2)
    assert "Chapter 01, Scene 02" in formatted
    assert "CHARACTER KNOWLEDGE" in formatted
    assert "PHYSICAL CONTINUITY" in formatted
    assert "Who is outside the side door?" in formatted


def test_parse_handoff_response_accepts_fenced_json():
    response = "Here is the handoff:\n```json\n" + json.dumps(sample_handoff()) + "\n```"
    parsed = parse_handoff_response(response)
    assert parsed == sample_handoff()


def test_parse_handoff_response_rejects_missing_ending():
    assert parse_handoff_response('{"events":["something"]}') is None


def test_extraction_prompt_uses_accepted_scene_as_evidence():
    prompt = build_handoff_extraction_prompt(2, 3, "The accepted scene ends at the side door.")
    assert "ACCEPTED SCENE" in prompt
    assert "Chapter 02, Scene 03" in prompt
    assert "ends at the side door" in prompt

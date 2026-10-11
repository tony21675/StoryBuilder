from __future__ import annotations

from builder.scene_contract import SceneContract


def validate_package(package) -> list[str]:
    errors: list[str] = []
    bible = package.story_bible
    state = package.current_state

    if not bible.get("story_format_version"):
        errors.append("story_bible.json is missing story_format_version.")
    if not bible.get("title"):
        errors.append("Story title is empty.")

    cards = bible.get("character_cards")
    if not isinstance(cards, list):
        errors.append("character_cards must be a list.")
    else:
        for filename in cards:
            if filename not in package.characters:
                errors.append(f"Character card is listed but missing: {filename}")

    if not isinstance(state.get("chapter"), int) or state["chapter"] < 1:
        errors.append("Current State chapter must be an integer greater than 0.")
    if not isinstance(state.get("scene"), int) or state["scene"] < 1:
        errors.append("Current State scene must be an integer greater than 0.")
    if not isinstance(state.get("scene_cast", []), list):
        errors.append("scene_cast must be a list.")
    if not isinstance(state.get("events", []), list):
        errors.append("events must be a list.")

    guidance = package.extra_json.get("writing_guidance.json", {})
    if guidance and not isinstance(guidance, dict):
        errors.append("writing_guidance.json must contain an object.")
    elif isinstance(guidance, dict):
        scene_entries: list[tuple[str, dict]] = []

        chapter_plans = guidance.get("chapter_plans")
        if isinstance(chapter_plans, dict):
            for chapter_key, chapter_entry in chapter_plans.items():
                if not isinstance(chapter_entry, dict):
                    errors.append(
                        f"writing_guidance chapter {chapter_key!r} must be an object."
                    )
                    continue
                scene_plan = chapter_entry.get("scene_plan", {})
                if not isinstance(scene_plan, dict):
                    errors.append(
                        f"writing_guidance chapter {chapter_key!r} scene_plan must be an object."
                    )
                    continue
                for scene_key, entry in scene_plan.items():
                    if isinstance(entry, dict):
                        scene_entries.append(
                            (f"Chapter {chapter_key}, Scene {scene_key}", entry)
                        )
                    else:
                        errors.append(
                            f"writing_guidance Chapter {chapter_key}, Scene {scene_key} must be an object."
                        )

        legacy_scene_plan = guidance.get("scene_plan")
        if isinstance(legacy_scene_plan, dict):
            for scene_key, entry in legacy_scene_plan.items():
                if isinstance(entry, dict):
                    scene_entries.append((f"Chapter 1, Scene {scene_key}", entry))
                else:
                    errors.append(
                        f"writing_guidance Chapter 1, Scene {scene_key} must be an object."
                    )

        for label, entry in scene_entries:
            try:
                contract = SceneContract.from_guidance(entry, [])
                lint_errors = SceneContract.lint(contract) if contract else []
                for detail in lint_errors:
                    errors.append(f"{label}: {detail}")
            except (TypeError, ValueError) as exc:
                errors.append(f"{label}: {exc}")

    return errors

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import builder.state_manager as state_manager_module
from builder.state_manager import (
    StateManager,
    remove_prior_chapter_opening_markers,
)


class StateUpdateValidationTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "chapter": 2,
            "scene": 1,
            "location": {
                "primary": "Tony's bedroom",
                "Tony": "Holding Maya close",
                "Maya": "Curled against Tony's chest",
            },
            "character_knowledge": {
                "Tony": ["Tony knows Maya is Tiffany's best friend."],
                "Maya": [],
            },
            "physical_state": {
                "Tony": {"position": "sitting"},
                "Maya": {"position": "curled against Tony"},
            },
        }

    def test_rejects_character_knowledge_lists_inside_location(self):
        patch = {
            "location": {
                "Tony": ["Tony now knows Tiffany is gone."],
                "Maya": ["Maya told Tony the man hit her."],
            }
        }

        with self.assertRaisesRegex(ValueError, "Character knowledge belongs"):
            StateManager.validate_patch(self.state, patch)

    def test_rejects_non_object_location(self):
        with self.assertRaisesRegex(ValueError, "'location' must be an object"):
            StateManager.validate_patch(self.state, {"location": ["wrong shape"]})

    def test_rejects_app_managed_scene_control_fields(self):
        for field, value in (
            ("chapter", 3),
            ("scene", 2),
            ("status", "story_start"),
            ("scene_completed", True),
            ("chapter_completed", True),
            ("scene_cast", ["Tiffany"]),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "controlled by StoryBuilder"):
                    StateManager.validate_patch(self.state, {field: value})

    def test_accepts_location_text_and_character_knowledge_in_correct_fields(self):
        patch = {
            "location": {"Maya": "Sitting beside Tony"},
            "character_knowledge": {
                "Tony": [
                    "Tony knows Maya witnessed the abduction.",
                    "Tony knows the man hit Maya.",
                ]
            },
        }

        self.assertIs(StateManager.validate_patch(self.state, patch), patch)

    def test_rejects_non_text_character_knowledge_items(self):
        patch = {"character_knowledge": {"Maya": ["Valid fact", {"fact": "bad shape"}]}}

        with self.assertRaisesRegex(ValueError, "list of text facts"):
            StateManager.validate_patch(self.state, patch)

    def test_removes_prior_chapter_opening_marker_but_preserves_shared_notes(self):
        state = {
            "continuity_notes": [
                "Chapter 1 begins here.",
                "Tony is protective of the girls.",
                "Tiffany's dog tags contain a hidden tracker.",
            ]
        }

        restored = remove_prior_chapter_opening_markers(state, 1, 2)

        self.assertEqual(
            restored["continuity_notes"],
            [
                "Tony is protective of the girls.",
                "Tiffany's dog tags contain a hidden tracker.",
            ],
        )
        self.assertEqual(len(state["continuity_notes"]), 3)

    def test_removes_opening_marker_from_continuity_requirements_too(self):
        state = {
            "continuity_requirements": [
                "Chapter 1 begins here.",
                "Tony and Tiffany live together.",
            ],
            "continuity_notes": [
                "Chapter 1 starts here.",
                "Keep this shared note.",
            ],
        }

        restored = remove_prior_chapter_opening_markers(state, 1, 2)

        self.assertEqual(
            restored["continuity_requirements"],
            ["Tony and Tiffany live together."],
        )
        self.assertEqual(restored["continuity_notes"], ["Keep this shared note."])

    def test_does_not_remove_opening_marker_within_same_chapter(self):
        state = {
            "continuity_notes": ["Chapter 1 begins here.", "Keep this shared note."],
            "continuity_requirements": ["Chapter 1 begins here."],
        }

        restored = remove_prior_chapter_opening_markers(state, 1, 1)

        self.assertEqual(restored, state)

    def test_planned_end_state_hint_does_not_override_state_from_completed_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "writer.gguf"
            llama = root / "llama-cli"
            model.touch()
            llama.touch()

            current_state = {
                "chapter": 2,
                "scene": 1,
                "current_situation": "Before the accepted scene.",
                "scene_cast": [],
                "character_knowledge": {},
            }
            prose_derived_patch = {
                "current_situation": (
                    "Maya has told Tony that Tiffany is gone, but has not explained the abduction."
                )
            }
            planned_hint = {
                "current_situation": (
                    "Tony knows that the kidnapper hit Maya and asks for details."
                )
            }

            class FakeProcess:
                returncode = 0

                def communicate(self, timeout=None):
                    return json.dumps(prose_derived_patch), None

            with (
                patch.object(state_manager_module, "DEFAULT_LLAMA", llama),
                patch.object(state_manager_module.subprocess, "Popen", return_value=FakeProcess()),
                patch.object(StateManager, "_detect_accelerator", return_value=None),
                patch.object(StateManager, "_propose_knowledge_delta", return_value={}),
            ):
                result = StateManager.propose(
                    model,
                    current_state,
                    "Maya tells Tony that Tiffany is gone, then remains too shaken to explain more.",
                    scene_end_guidance=(
                        "EXPECTED END STATE HINT:\n"
                        + json.dumps(planned_hint)
                    ),
                )

            self.assertEqual(result, prose_derived_patch)

if __name__ == "__main__":
    unittest.main()

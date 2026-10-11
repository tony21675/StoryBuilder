import unittest

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

    def test_does_not_remove_opening_marker_within_same_chapter(self):
        state = {"continuity_notes": ["Chapter 1 begins here.", "Keep this shared note."]}

        restored = remove_prior_chapter_opening_markers(state, 1, 1)

        self.assertEqual(restored, state)


if __name__ == "__main__":
    unittest.main()

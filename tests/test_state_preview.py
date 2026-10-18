import copy
import unittest

from builder.state_manager import (
    StateManager,
    merge_patch,
    reviewed_state_preview_to_patch,
)


class ReviewedStatePreviewTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "chapter": 3,
            "scene": 1,
            "status": "in_progress",
            "scene_completed": False,
            "chapter_completed": False,
            "scene_cast": ["Tony", "Maya"],
            "time": {
                "period": "the middle of the night",
                "exact_time": "not established",
            },
            "current_situation": "Tony and Maya are together late at night.",
            "location": {"Tony": "kitchen", "Maya": "bedroom"},
            "physical_state": {
                "Tony": {"location": "kitchen"},
                "Maya": {"location": "bedroom"},
            },
        }
        self.proposal = {
            "current_situation": "Tony has begun the morning with Maya.",
        }
        self.expected_preview = StateManager.merge_patch(self.before, self.proposal)

    def test_applies_a_manual_time_correction_from_the_visible_preview(self):
        reviewed = copy.deepcopy(self.expected_preview)
        reviewed["time"]["period"] = "daybreak / early morning"

        preview_edits = reviewed_state_preview_to_patch(self.expected_preview, reviewed)
        combined_patch = merge_patch(self.proposal, preview_edits)
        result = StateManager.merge_patch(self.before, combined_patch)

        self.assertEqual(result["time"]["period"], "daybreak / early morning")
        self.assertEqual(result["time"]["exact_time"], "not established")
        self.assertEqual(result["chapter"], 3)
        self.assertEqual(result["scene"], 1)

    def test_rejects_changes_to_storybuilder_managed_navigation_fields(self):
        reviewed = copy.deepcopy(self.expected_preview)
        reviewed["scene"] = 99

        with self.assertRaisesRegex(ValueError, "managed by StoryBuilder"):
            reviewed_state_preview_to_patch(self.expected_preview, reviewed)

    def test_rejects_removing_existing_fields_from_the_full_preview(self):
        reviewed = copy.deepcopy(self.expected_preview)
        del reviewed["time"]["exact_time"]

        with self.assertRaisesRegex(ValueError, "removed the existing field 'time.exact_time'"):
            reviewed_state_preview_to_patch(self.expected_preview, reviewed)

    def test_unchanged_preview_produces_no_manual_override(self):
        reviewed = copy.deepcopy(self.expected_preview)

        self.assertEqual(
            reviewed_state_preview_to_patch(self.expected_preview, reviewed),
            {},
        )


if __name__ == "__main__":
    unittest.main()

import json
import unittest

from builder.focused_revision import (
    apply_focused_replacement,
    build_focused_revision_prompt,
)


class FocusedRevisionTests(unittest.TestCase):
    def test_replaces_only_the_requested_unique_passage(self):
        original = (
            "Tony turned on the bath and checked that the water was warm.\n\n"
            "He left Maya in peace and went downstairs."
        )
        response = json.dumps({
            "target_text": "turned on the bath",
            "replacement_text": "turned on the bath, adding unscented bubbles",
        })

        revised = apply_focused_replacement(original, response)

        self.assertEqual(
            revised,
            "Tony turned on the bath, adding unscented bubbles and checked that the water was warm.\n\n"
            "He left Maya in peace and went downstairs.",
        )
        self.assertTrue(revised.endswith("He left Maya in peace and went downstairs."))

    def test_accepts_json_fences_but_only_applies_the_patch(self):
        original = "First paragraph.\n\nSecond paragraph."
        response = ' ```json\n{"target_text":"Second paragraph.",'
        response += '"replacement_text":"Second paragraph, revised."}\n``` '

        self.assertEqual(
            apply_focused_replacement(original, response),
            "First paragraph.\n\nSecond paragraph, revised.",
        )

    def test_matches_whitespace_variations_without_modifying_surrounding_text(self):
        original = "Before.\n\nHe filled the tub.\nThen he left."
        response = json.dumps({
            "target_text": "He filled the tub. Then he left.",
            "replacement_text": "He filled the tub with unscented bubbles. Then he left.",
        })

        revised = apply_focused_replacement(original, response)

        self.assertEqual(revised, "Before.\n\nHe filled the tub with unscented bubbles. Then he left.")
        self.assertTrue(revised.startswith("Before.\n\n"))

    def test_rejects_target_not_found(self):
        original = "The bath was quiet."
        response = json.dumps({
            "target_text": "The shower was quiet.",
            "replacement_text": "The bubble bath was quiet.",
        })

        with self.assertRaisesRegex(ValueError, "does not appear"):
            apply_focused_replacement(original, response)
        self.assertEqual(original, "The bath was quiet.")

    def test_rejects_ambiguous_target(self):
        original = "He checked the water. Later, he checked the water again."
        response = json.dumps({
            "target_text": "checked the water",
            "replacement_text": "checked the bubble bath",
        })

        with self.assertRaisesRegex(ValueError, "more than once"):
            apply_focused_replacement(original, response)

    def test_rejects_scene_sized_replacement_for_a_small_target(self):
        original = ("The bath was plain. " + "The rest of the scene stays unchanged. " * 8).strip()
        response = json.dumps({
            "target_text": "The bath was plain.",
            "replacement_text": original + " rewritten in full",
        })

        with self.assertRaisesRegex(ValueError, "too broad"):
            apply_focused_replacement(original, response)

    def test_rejects_whole_scene_rewrites(self):
        original = "A short complete scene."
        response = json.dumps({
            "target_text": original,
            "replacement_text": "A different complete scene.",
        })

        with self.assertRaisesRegex(ValueError, "entire scene"):
            apply_focused_replacement(original, response)

    def test_rejects_malformed_output(self):
        with self.assertRaisesRegex(ValueError, "JSON"):
            apply_focused_replacement("A scene.", "I changed the bath.")

    def test_prompt_keeps_the_author_request_and_draft_available(self):
        prompt = build_focused_revision_prompt(
            "He ran the bath.", "Add unscented bubbles."
        )
        self.assertIn("Add unscented bubbles.", prompt)
        self.assertIn("He ran the bath.", prompt)
        self.assertIn('"target_text"', prompt)
        self.assertIn("Do not return the whole scene.", prompt)

    def test_prompt_requires_a_request(self):
        with self.assertRaisesRegex(ValueError, "specific change"):
            build_focused_revision_prompt("A scene.", " ")


if __name__ == "__main__":
    unittest.main()

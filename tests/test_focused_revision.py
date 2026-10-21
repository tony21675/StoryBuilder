import json
import unittest

from builder.focused_revision import (
    apply_focused_replacement,
    apply_selected_replacement,
    build_focused_revision_prompt,
    build_selected_revision_prompt,
    revise_selected_passage,
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


class SelectedPassageRevisionTests(unittest.TestCase):
    def test_prompt_requests_replacement_only_and_includes_read_only_context(self):
        prompt = build_selected_revision_prompt(
            "Tony swallowed hard.\n\nChloe held him.",
            "Make Chloe steady Tony.",
            before_context="He was close to losing control.",
            after_context="The room fell quiet.",
        )
        self.assertIn('"replacement_text"', prompt)
        self.assertIn("Tony swallowed hard.\n\nChloe held him.", prompt)
        self.assertIn("The room fell quiet.", prompt)
        self.assertNotIn('"target_text"', prompt)

    def test_selected_multiline_edit_preserves_long_scene_outside_span(self):
        prefix = ("An earlier paragraph with unchanged wording. " * 35) + "\n\n"
        selected = '“You have no idea how much I needed that from you,” Tony said.\nChloe held him close.'
        suffix = "\n\n" + ("A later paragraph must stay byte-for-byte unchanged. " * 35)
        original = prefix + selected + suffix
        start = len(prefix)
        end = start + len(selected)
        replacement = '“You have no idea how much I needed that,” Tony whispered, tears in his eyes.\nChloe kept her arms around him.'
        response = json.dumps({"replacement_text": replacement})

        revised = apply_selected_replacement(original, start, end, selected, response)

        self.assertEqual(revised[:start], prefix)
        self.assertEqual(revised[-len(suffix):], suffix)
        self.assertIn("tears in his eyes", revised)
        self.assertEqual(revised[start:start + len(replacement)], replacement)

    def test_rejects_if_captured_selection_no_longer_matches_source_offsets(self):
        original = "Before. selected phrase. After."
        response = json.dumps({"replacement_text": "revised phrase"})
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            apply_selected_replacement(original, 8, 23, "selected phrase.", response)

    def test_rejects_whole_scene_selection(self):
        original = "Whole scene text."
        response = json.dumps({"replacement_text": "Different whole scene."})
        with self.assertRaisesRegex(ValueError, "entire scene"):
            apply_selected_replacement(original, 0, len(original), original, response)

    def test_rejects_a_model_that_returns_target_text_again(self):
        original = "Before. Selected phrase. After."
        response = json.dumps({"target_text": "Selected phrase.", "replacement_text": "Revised phrase."})
        with self.assertRaisesRegex(ValueError, "Only replacement_text"):
            apply_selected_replacement(original, 8, 24, "Selected phrase.", response)

    def test_accepts_fenced_json_but_only_replaces_selected_span(self):
        original = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        selected = "Second paragraph."
        start = original.index(selected)
        fence = chr(96) * 3
        response = fence + 'json\n{"replacement_text":"The revised middle paragraph."}\n' + fence
        revised = apply_selected_replacement(original, start, start + len(selected), selected, response)
        self.assertEqual(revised, "First paragraph.\n\nThe revised middle paragraph.\n\nThird paragraph.")

    def test_each_retry_gets_a_fresh_context_without_prior_model_response(self):
        class FakeEngine:
            def __init__(self):
                self.responses = [
                    json.dumps({"target_text": "misguided quoted target", "replacement_text": "Bad revision"}),
                    json.dumps({"replacement_text": "Better revision"}),
                ]
                self.prompts = []
                self.reset_calls = []

            def reset_context(self, model_path, system_prompt):
                self.reset_calls.append((model_path, system_prompt))

            def generate(self, prompt):
                self.prompts.append(prompt)
                return self.responses.pop(0)

        engine = FakeEngine()
        original = "Before. Selected passage. After."
        selected = "Selected passage."
        start = original.index(selected)
        revised, error, restore_error = revise_selected_passage(
            engine=engine,
            model_path="/models/test.gguf",
            original_system_prompt="normal writer prompt",
            original=original,
            start=start,
            end=start + len(selected),
            selected_text=selected,
            request="Revise the selected passage.",
        )

        self.assertEqual(revised, "Before. Better revision After.")
        self.assertIsNone(error)
        self.assertIsNone(restore_error)
        self.assertEqual(len(engine.reset_calls), 3)
        self.assertEqual(engine.reset_calls[-1], ("/models/test.gguf", "normal writer prompt"))
        self.assertNotIn("misguided quoted target", engine.prompts[1])
        self.assertIn("Only replacement_text is permitted", engine.prompts[1])

    def test_failed_attempts_return_error_without_mutating_original(self):
        class FakeEngine:
            def __init__(self):
                self.responses = ["not JSON", "still not JSON"]
                self.reset_calls = []

            def reset_context(self, model_path, system_prompt):
                self.reset_calls.append(system_prompt)

            def generate(self, prompt):
                return self.responses.pop(0)

        engine = FakeEngine()
        original = "Before. Selected passage. After."
        selected = "Selected passage."
        start = original.index(selected)
        revised, error, restore_error = revise_selected_passage(
            engine=engine,
            model_path="/models/test.gguf",
            original_system_prompt="normal writer prompt",
            original=original,
            start=start,
            end=start + len(selected),
            selected_text=selected,
            request="Revise the selected passage.",
        )
        self.assertIsNone(revised)
        self.assertIn("after 2 attempts", error)
        self.assertIsNone(restore_error)
        self.assertEqual(original, "Before. Selected passage. After.")

if __name__ == "__main__":
    unittest.main()

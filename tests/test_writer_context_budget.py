import json
import unittest

from builder.writer_context_budget import (
    WriterContextBudgetError,
    conservative_token_estimate,
    fit_writer_context_files,
)


class WriterContextBudgetTests(unittest.TestCase):
    @staticmethod
    def _render(files):
        return "BASE SYSTEM PROMPT " + "".join(
            f"\n[{name}]\n{content}\n" for name, content in files
        )

    def test_prunes_optional_context_and_preserves_scene_requirements(self):
        files = [
            ("scene_state.json", '{"current_situation":"The scene starts here."}'),
            ("scene_physical_state.json", '{"Tony":{"position":"standing"}}'),
            ("working_writer_notes.json", '{"notes":"' + ("craft-note " * 300) + '"}'),
            ("supporting_people_context.json", '{"people":"' + ("support " * 180) + '"}'),
            ("author_defined_canon_rules.txt", "Author canon must be preserved."),
            ("author_writing_guidance.txt", "Stable author guidance must be preserved."),
        ]
        fitted, metrics = fit_writer_context_files(
            files,
            prompt_builder=self._render,
            base_prompt="CURRENT SCENE CONTRACT " + ("important scene direction " * 20),
            context_window_tokens=1800,
            reserved_output_tokens=400,
            safety_margin_tokens=300,
        )
        names = [name for name, _content in fitted]
        self.assertIn("scene_state.json", names)
        self.assertIn("scene_physical_state.json", names)
        self.assertIn("author_defined_canon_rules.txt", names)
        self.assertIn("author_writing_guidance.txt", names)
        self.assertNotIn("working_writer_notes.json", names)
        self.assertLessEqual(metrics["final_conservative_tokens"], metrics["input_token_budget"])
        self.assertEqual(metrics["reserved_output_tokens"], 400)
        self.assertEqual(metrics["safety_margin_tokens"], 300)
        self.assertIn("working_writer_notes.json", metrics["pruned_reference_files"])

    def test_compacts_character_cards_before_dropping_them(self):
        card = {
            "Tony": {
                "name": "Tony",
                "appearance": "Broad shoulders and tired eyes.",
                "personality": "Protective and controlled.",
                "voice": "Low and dry.",
                "unrelated_long_biography": "x" * 8000,
            }
        }
        files = [
            ("scene_state.json", '{"current_situation":"Current."}'),
            ("scene_characters.json", json.dumps(card)),
            ("author_writing_guidance.txt", "Keep tone stable."),
        ]
        fitted, metrics = fit_writer_context_files(
            files,
            prompt_builder=self._render,
            base_prompt="Write this scene.",
            context_window_tokens=2400,
            reserved_output_tokens=500,
            safety_margin_tokens=300,
        )
        self.assertIn("scene_characters.json", dict(fitted))
        self.assertIn("appearance", dict(fitted)["scene_characters.json"])
        self.assertNotIn("unrelated_long_biography", dict(fitted)["scene_characters.json"])
        self.assertIn("scene_characters.json", metrics["compacted_reference_files"])

    def test_fails_clearly_if_mandatory_context_cannot_fit(self):
        files = [("scene_state.json", "x" * 4000)]
        with self.assertRaisesRegex(WriterContextBudgetError, "Required Writer context still exceeds"):
            fit_writer_context_files(
                files,
                prompt_builder=self._render,
                base_prompt="",
                context_window_tokens=700,
                reserved_output_tokens=200,
                safety_margin_tokens=100,
            )

    def test_estimate_is_conservative_and_repeatable(self):
        self.assertEqual(conservative_token_estimate("x" * 300), 100)


if __name__ == "__main__":
    unittest.main()

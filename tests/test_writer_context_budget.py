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

    def test_keeps_compacted_character_cards_and_knowledge_before_dropping_history(self):
        card = {
            "Tony": {
                "name": "Tony",
                "appearance": "Broad shoulders and tired eyes.",
                "personality": "Protective and controlled.",
                "unrelated_long_biography": "x" * 3600,
            }
        }
        knowledge = {
            "Tony": [
                "Tony knows Tiffany is his daughter.",
                "Tony knows the kidnapper's identity is unknown.",
            ]
        }
        files = [
            ("scene_state.json", '{"current_situation":"The group begins a search for Tiffany."}'),
            ("scene_physical_state.json", '{"Tony":{"position":"standing"}}'),
            ("scene_characters.json", json.dumps(card)),
            ("scene_character_knowledge.json", json.dumps(knowledge)),
            ("author_writing_guidance.txt", "Preserve the author's stable style guidance. " * 10),
            ("historical_continuity_archive.txt", "Old historical passage text. " * 120),
        ]
        fitted, metrics = fit_writer_context_files(
            files,
            prompt_builder=self._render,
            base_prompt="CURRENT SCENE CONTRACT " + ("Specific scene direction. " * 45),
            context_window_tokens=2000,
            reserved_output_tokens=400,
            safety_margin_tokens=300,
        )
        fitted_map = dict(fitted)
        self.assertIn("scene_characters.json", fitted_map)
        self.assertIn("scene_character_knowledge.json", fitted_map)
        self.assertIn("appearance", fitted_map["scene_characters.json"])
        self.assertNotIn("unrelated_long_biography", fitted_map["scene_characters.json"])
        self.assertIn("Tony knows Tiffany is his daughter.", fitted_map["scene_character_knowledge.json"])
        self.assertNotIn("historical_continuity_archive.txt", fitted_map)
        self.assertIn("historical_continuity_archive.txt", metrics["pruned_reference_files"])
        self.assertLessEqual(metrics["final_conservative_tokens"], metrics["input_token_budget"])

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

    def test_diagnostic_mode_reports_over_budget_without_weakening_default_guard(self):
        files = [
            ("scene_state.json", "x" * 4000),
            ("author_writing_guidance.txt", "preserve stable guidance " * 200),
        ]
        fitted, metrics = fit_writer_context_files(
            files,
            prompt_builder=self._render,
            base_prompt="Current scene direction.",
            context_window_tokens=700,
            reserved_output_tokens=200,
            safety_margin_tokens=100,
            raise_on_overflow=False,
        )
        self.assertGreater(metrics["final_conservative_tokens"], metrics["input_token_budget"])
        self.assertTrue(metrics["required_context_over_budget"])
        self.assertGreater(metrics["estimated_overage_tokens"], 0)
        self.assertIn("scene_state.json", dict(fitted))
        self.assertIn("author_writing_guidance.txt", dict(fitted))
        with self.assertRaisesRegex(WriterContextBudgetError, "Required Writer context still exceeds"):
            fit_writer_context_files(
                files,
                prompt_builder=self._render,
                base_prompt="Current scene direction.",
                context_window_tokens=700,
                reserved_output_tokens=200,
                safety_margin_tokens=100,
            )

    def test_estimate_is_conservative_and_repeatable(self):
        self.assertEqual(conservative_token_estimate("x" * 300), 100)


if __name__ == "__main__":
    unittest.main()

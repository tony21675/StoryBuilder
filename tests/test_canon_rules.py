import unittest

from builder.canon_rules import build_canon_rules_prompt


class CanonRulesPromptTests(unittest.TestCase):
    def test_renders_nonblank_rules_as_a_compact_bulleted_section(self):
        prompt = build_canon_rules_prompt(
            [
                "  Keep the crew together.\nAvoid forced foreshadowing.  ",
                "",
                None,
                7,
                "Let relationships develop naturally.",
            ]
        )

        self.assertIn("CANON RULES", prompt)
        self.assertIn("- Keep the crew together. Avoid forced foreshadowing.", prompt)
        self.assertIn("- Let relationships develop naturally.", prompt)
        self.assertNotIn("None", prompt)
        self.assertNotIn("7", prompt)

    def test_empty_or_unsupported_values_add_no_prompt_text(self):
        self.assertEqual(build_canon_rules_prompt([]), "")
        self.assertEqual(build_canon_rules_prompt(None), "")
        self.assertEqual(build_canon_rules_prompt("not a list"), "")


if __name__ == "__main__":
    unittest.main()

import unittest

from builder.scene_idea_suggestion import (
    SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT,
    build_scene_idea_suggestion_prompt,
    normalize_scene_idea_suggestion,
)


class SceneIdeaSuggestionTests(unittest.TestCase):
    def test_prompt_uses_context_and_keeps_suggestion_editable(self):
        context = {
            "current_state": {
                "chapter": 1,
                "scene": 3,
                "current_situation": "The crew has identified silicate contamination.",
                "unresolved_questions": ["Where are the particulates entering?"],
            }
        }
        prompt = build_scene_idea_suggestion_prompt(context)
        self.assertIn("READ-ONLY STORY CONTEXT", prompt)
        self.assertIn("Where are the particulates entering?", prompt)
        self.assertIn("author will edit or replace", SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT)
        self.assertIn('"scene_idea"', SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT)

    def test_suggestion_prompt_treats_saved_state_as_fallible(self):
        prompt = SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT.casefold()
        self.assertIn("not as sole proof", prompt)
        self.assertIn("unsupported by accepted prose or canon", prompt)
        self.assertIn("explicit author corrections take precedence", prompt)
        self.assertNotIn("as the truth of what has already happened", prompt)
        self.assertNotIn("villain, sabotage, conspiracy", prompt)

    def test_normalizes_valid_idea(self):
        self.assertEqual(
            normalize_scene_idea_suggestion(
                {"scene_idea": "  Daniel checks the filtration logs while Zoe compares sensor readings.  "}
            ),
            "Daniel checks the filtration logs while Zoe compares sensor readings.",
        )

    def test_rejects_missing_or_empty_idea(self):
        with self.assertRaises(ValueError):
            normalize_scene_idea_suggestion({})
        with self.assertRaises(ValueError):
            normalize_scene_idea_suggestion({"scene_idea": "   "})

    def test_rejects_oversized_idea(self):
        with self.assertRaises(ValueError):
            normalize_scene_idea_suggestion({"scene_idea": "x" * 2401})


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from builder.scene_completion import generate_scene_with_completion_check


class FakeEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.reset_calls = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise RuntimeError("no fake response remains")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def reset_context(self, model_path, system_prompt):
        self.reset_calls.append((model_path, system_prompt))


class SceneCompletionTests(unittest.TestCase):
    def setUp(self):
        self.engine = FakeEngine(["Tony tells the group Tiffany is gone."])
        self.contract = {
            "author_idea": "Tell the group what happened; let them react and begin forming a private effort.",
            "hard_stop": "Stop once broad roles begin to emerge.",
            "max_attempts": 3,
        }
        self.state = {"chapter": 3, "scene": 2}
        self.model = "/models/test.gguf"
        self.system_prompt = "writer system prompt"
        self.scene_context = "Author's idea and supporting direction."

    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_passing_completion_review_preserves_draft_and_restores_writer(self, validate):
        validate.return_value = {"pass": True, "missed_beats": [], "violations": []}

        draft, notice = generate_scene_with_completion_check(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            initial_prompt="write",
            scene_context=self.scene_context,
            contract=self.contract,
            current_state=self.state,
        )

        self.assertEqual(draft, "Tony tells the group Tiffany is gone.")
        self.assertEqual(notice, "")
        self.assertEqual(len(self.engine.prompts), 1)
        self.assertEqual(self.engine.reset_calls, [(self.model, self.system_prompt)])

    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_missing_planned_events_get_one_append_only_continuation(self, validate):
        validate.return_value = {
            "pass": False,
            "missed_beats": ["The group reacts and begins discussing broad roles."],
            "violations": [],
        }
        self.engine.responses.append("Beth's face drained of color as Chloe pushed her chair back.")

        draft, notice = generate_scene_with_completion_check(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            initial_prompt="write",
            scene_context=self.scene_context,
            contract=self.contract,
            current_state=self.state,
        )

        self.assertIn("Tony tells the group Tiffany is gone.", draft)
        self.assertIn("Beth's face drained of color", draft)
        self.assertIn("automatically continued", notice)
        self.assertEqual(len(self.engine.prompts), 2)
        self.assertIn("do not repeat", self.engine.prompts[1].casefold())
        self.assertIn("broad roles", self.engine.prompts[1].casefold())

    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_continuity_violation_does_not_trigger_unsafe_append(self, validate):
        validate.return_value = {
            "pass": False,
            "missed_beats": ["The group begins discussing broad roles."],
            "violations": ["The opening contradicts established time."],
        }

        draft, notice = generate_scene_with_completion_check(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            initial_prompt="write",
            scene_context=self.scene_context,
            contract=self.contract,
            current_state=self.state,
        )

        self.assertEqual(draft, "Tony tells the group Tiffany is gone.")
        self.assertIn("continuity concern", notice)
        self.assertEqual(len(self.engine.prompts), 1)
        self.assertEqual(len(self.engine.reset_calls), 1)

    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_validator_failure_preserves_original_draft(self, validate):
        validate.side_effect = RuntimeError("validator unavailable")

        draft, notice = generate_scene_with_completion_check(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            initial_prompt="write",
            scene_context=self.scene_context,
            contract=self.contract,
            current_state=self.state,
        )

        self.assertEqual(draft, "Tony tells the group Tiffany is gone.")
        self.assertIn("completion check could not finish", notice)
        self.assertEqual(self.engine.reset_calls, [(self.model, self.system_prompt)])

    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_scene_without_saved_author_idea_skips_completion_review(self, validate):
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            initial_prompt="write",
            scene_context=self.scene_context,
            contract={},
            current_state=self.state,
        )

        self.assertEqual(draft, "Tony tells the group Tiffany is gone.")
        self.assertEqual(notice, "")
        validate.assert_not_called()
        self.assertEqual(self.engine.reset_calls, [])

    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_retry_limit_one_disables_automatic_continuation(self, validate):
        validate.return_value = {
            "pass": False,
            "missed_beats": ["The group begins forming a private effort."],
            "violations": [],
        }
        self.contract["max_attempts"] = 1

        draft, notice = generate_scene_with_completion_check(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            initial_prompt="write",
            scene_context=self.scene_context,
            contract=self.contract,
            current_state=self.state,
        )

        self.assertEqual(draft, "Tony tells the group Tiffany is gone.")
        self.assertIn("automatic continuation is disabled", notice)
        self.assertEqual(len(self.engine.prompts), 1)
        self.assertEqual(len(self.engine.reset_calls), 1)


if __name__ == "__main__":
    unittest.main()

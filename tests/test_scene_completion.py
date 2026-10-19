import unittest
from unittest.mock import patch

from builder.scene_completion import generate_scene_with_completion_check


PASS_AUDIT = {"pass": True, "issues": []}


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
        self.engine = FakeEngine(["Draft scene."])
        self.contract = {
            "author_idea": "Tell the group what happened; let them react and begin forming a private effort.",
            "hard_stop": "Stop once broad roles begin to emerge.",
            "max_attempts": 3,
        }
        self.state = {"chapter": 3, "scene": 2}
        self.model = "/models/test.gguf"
        self.system_prompt = "writer system prompt"
        self.scene_context = "Author's idea and supporting direction."

    @patch("builder.scene_completion._run_scene_integrity_audit", return_value=PASS_AUDIT)
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_passing_completion_review_preserves_draft_and_restores_writer(self, validate, _audit):
        validate.return_value = {"pass": True, "missed_beats": [], "violations": []}
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Draft scene.")
        self.assertEqual(notice, "")
        self.assertEqual(len(self.engine.prompts), 1)
        self.assertEqual(self.engine.reset_calls, [(self.model, self.system_prompt)])

    @patch("builder.scene_completion._run_scene_integrity_audit", side_effect=[PASS_AUDIT, PASS_AUDIT])
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_missing_planned_events_get_one_append_only_continuation(self, validate, _audit):
        validate.return_value = {"pass": False, "missed_beats": ["Group begins discussing broad roles."], "violations": []}
        self.engine.responses = ["Opening and disclosure.", "The group reacts and begins sketching roles."]
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Opening and disclosure.\n\nThe group reacts and begins sketching roles.")
        self.assertIn("one continuation", notice)
        self.assertEqual(len(self.engine.prompts), 2)
        self.assertIn("do not rewrite", self.engine.prompts[1].casefold())

    @patch("builder.scene_completion._run_scene_integrity_audit", return_value=PASS_AUDIT)
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_semantic_violation_triggers_one_full_retry(self, validate, _audit):
        validate.side_effect = [
            {"pass": False, "missed_beats": [], "violations": ["Timeline conflict."]},
            {"pass": True, "missed_beats": [], "violations": []},
        ]
        self.engine.responses = ["Bad draft with wrong time.", "Corrected complete scene."]
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Corrected complete scene.")
        self.assertIn("regenerated the whole scene once", notice)
        self.assertEqual(len(self.engine.prompts), 2)
        self.assertIn("Timeline conflict", self.engine.prompts[1])

    @patch("builder.scene_completion._run_scene_integrity_audit", side_effect=[
        {"pass": False, "issues": ["A character claims to witness an event despite being absent."]}, PASS_AUDIT
    ])
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_independent_integrity_issue_triggers_full_retry_and_recheck(self, validate, _audit):
        validate.return_value = {"pass": True, "missed_beats": [], "violations": []}
        self.engine.responses = ["Unsupported eyewitness claim.", "Corrected complete scene."]
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Corrected complete scene.")
        self.assertIn("passed follow-up checks", notice)
        self.assertEqual(len(self.engine.prompts), 2)
        self.assertIn("witness", self.engine.prompts[1].casefold())

    @patch("builder.scene_completion._run_scene_integrity_audit", side_effect=RuntimeError("auditor unavailable"))
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_integrity_audit_failure_preserves_original_draft(self, validate, _audit):
        validate.return_value = {"pass": True, "missed_beats": [], "violations": []}
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Draft scene.")
        self.assertIn("audit failed", notice)
        self.assertEqual(len(self.engine.prompts), 1)

    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_validator_failure_preserves_original_draft(self, validate):
        validate.side_effect = RuntimeError("validator unavailable")
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Draft scene.")
        self.assertIn("completion check failed", notice)
        self.assertEqual(self.engine.reset_calls, [(self.model, self.system_prompt)])

    @patch("builder.scene_completion._run_scene_integrity_audit", return_value=PASS_AUDIT)
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_scene_without_saved_author_idea_skips_completion_review(self, validate, _audit):
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract={},
            current_state=self.state,
        )
        self.assertEqual(draft, "Draft scene.")
        self.assertEqual(notice, "")
        validate.assert_not_called()
        _audit.assert_not_called()

    @patch("builder.scene_completion._run_scene_integrity_audit", return_value=PASS_AUDIT)
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_retry_limit_one_disables_automatic_continuation(self, validate, _audit):
        validate.return_value = {"pass": False, "missed_beats": ["Private effort forms."], "violations": []}
        self.contract["max_attempts"] = 1
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Draft scene.")
        self.assertIn("retry limit disables continuation", notice)
        self.assertEqual(len(self.engine.prompts), 1)

    @patch("builder.scene_completion._run_scene_integrity_audit", side_effect=[
        PASS_AUDIT, {"pass": False, "issues": ["The continuation invents a consequential event."]}
    ])
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_unverified_continuation_is_not_appended(self, validate, _audit):
        validate.return_value = {"pass": False, "missed_beats": ["Private effort forms."], "violations": []}
        self.engine.responses = ["Safe but incomplete draft.", "Continuation with a new clue."]
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Safe but incomplete draft.")
        self.assertIn("original draft preserved", notice)
        self.assertEqual(len(self.engine.prompts), 2)


if __name__ == "__main__":
    unittest.main()

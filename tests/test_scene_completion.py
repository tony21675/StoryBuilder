import json
import unittest
from unittest.mock import patch

from builder.scene_completion import (
    AUDIT_CATEGORIES,
    _run_scene_integrity_audit,
    generate_scene_with_completion_check,
)


PASS_AUDIT = {"pass": True, "status": "clear", "issues": [], "details": []}
CONFLICT_AUDIT = {"pass": False, "status": "conflict", "issues": ["Timeline conflict."], "details": []}
UNCERTAIN_AUDIT = {"pass": False, "status": "uncertain", "issues": [], "details": ["The timeline check is uncertain."]}


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

    def _audit_checks(self):
        return {
            category: {
                "status": "clear",
                "reason": "Reviewed the supplied source evidence; no material conflict appears in this category.",
                "draft_evidence": "",
                "source_evidence": "",
            }
            for category in AUDIT_CATEGORIES
        }

    def _run_audit(self, prose, scene_context, state, guidance, checks):
        self.engine.responses = [json.dumps({"checks": checks})]
        return _run_scene_integrity_audit(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            scene_context=scene_context,
            current_state=state,
            author_guidance=guidance,
            prose=prose,
        )

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

    @patch("builder.scene_completion._run_scene_integrity_audit", side_effect=[CONFLICT_AUDIT, PASS_AUDIT])
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

    @patch("builder.scene_completion._run_scene_integrity_audit", side_effect=[CONFLICT_AUDIT, PASS_AUDIT])
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
        self.assertIn("eyewitness", self.engine.prompts[1].casefold())

    @patch("builder.scene_completion._run_scene_integrity_audit", return_value=UNCERTAIN_AUDIT)
    @patch("builder.scene_completion.SceneContract.validate_with_engine")
    def test_uncertain_audit_preserves_original_even_when_validator_flags_violation(self, validate, _audit):
        validate.return_value = {"pass": False, "missed_beats": [], "violations": ["Possible timeline conflict."]}
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model, writer_system_prompt=self.system_prompt,
            initial_prompt="write", scene_context=self.scene_context, contract=self.contract,
            current_state=self.state,
        )
        self.assertEqual(draft, "Draft scene.")
        self.assertIn("could not verify every required category", notice)
        self.assertEqual(len(self.engine.prompts), 1)

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
        PASS_AUDIT, CONFLICT_AUDIT
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
        self.assertIn("Original draft preserved", notice)
        self.assertEqual(len(self.engine.prompts), 2)

    def test_audit_requires_verbatim_evidence_for_viewpoint_timeline_privacy_and_scope(self):
        prose = (
            "Last night, Chloe saw Tiffany taken. Maya changed in the kitchen. "
            "Jessica began reviewing traffic cameras."
        )
        context = (
            "The abduction happened Friday afternoon. "
            "The hard stop is before search tasks."
        )
        state = {"location": {"Chloe": "At home sick."}}
        guidance = "Maya must change clothes privately."
        checks = self._audit_checks()
        examples = {
            "timeline_and_event_order": (
                "Last night", "Friday afternoon", "The draft's timing conflicts with the established day."
            ),
            "presence_and_character_knowledge": (
                "Chloe saw Tiffany taken", "At home sick.", "The absent character is written as a firsthand witness."
            ),
            "physical_and_location_continuity": (
                "Maya changed in the kitchen", "Maya must change clothes privately.",
                "The draft contradicts the explicit privacy instruction."
            ),
            "scene_scope_and_hard_stop": (
                "Jessica began reviewing traffic cameras", "The hard stop is before search tasks.",
                "The draft begins a later investigative step."
            ),
        }
        for category, (draft_quote, source_quote, reason) in examples.items():
            checks[category] = {
                "status": "conflict",
                "reason": reason,
                "draft_evidence": draft_quote,
                "source_evidence": source_quote,
            }
        result = self._run_audit(prose, context, state, guidance, checks)
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(len(result["issues"]), 4)
        joined = "\n".join(result["issues"])
        for source_quote, *_ in examples.values():
            self.assertIn(source_quote, joined)
        self.assertIn("unsupported_consequential_details", result["details"][3])

    def test_audit_marks_conflict_uncertain_when_quotes_are_not_verifiable(self):
        prose = "Chloe saw Tiffany taken."
        context = "The abduction happened Friday afternoon."
        state = {"location": {"Chloe": "At home sick."}}
        checks = self._audit_checks()
        checks["presence_and_character_knowledge"] = {
            "status": "conflict",
            "reason": "The draft claims firsthand knowledge from an absent character.",
            "draft_evidence": "Chloe saw Tiffany taken.",
            "source_evidence": "Chloe was present at the roadside.",
        }
        result = self._run_audit(prose, context, state, "", checks)
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(result["issues"], [])
        self.assertTrue(any("verifiable, exact excerpts" in detail for detail in result["details"]))

    def test_audit_marks_missing_category_uncertain(self):
        checks = {"timeline_and_event_order": {
            "status": "clear",
            "reason": "No material timeline conflict found.",
            "draft_evidence": "",
            "source_evidence": "",
        }}
        result = self._run_audit(
            "An ordinary scene.",
            "Original Scene Idea.",
            {"current_situation": "Daybreak."},
            "",
            checks,
        )
        self.assertEqual(result["status"], "uncertain")
        self.assertEqual(result["issues"], [])
        self.assertTrue(any("Missing audit categories" in detail for detail in result["details"]))

    def test_audit_prompt_requires_category_by_category_evidence(self):
        checks = self._audit_checks()
        self.engine.responses = [json.dumps({"checks": checks})]
        result = _run_scene_integrity_audit(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            scene_context="Scene Idea: end before investigation.",
            current_state={"scene_cast": ["Tony"]},
            author_guidance="No investigation in this scene.",
            prose="Tony listened.",
        )
        prompt = self.engine.prompts[0]
        for category in AUDIT_CATEGORIES:
            self.assertIn(category, prompt)
        self.assertIn("exact quote", prompt)
        self.assertEqual(result["status"], "clear")


if __name__ == "__main__":
    unittest.main()

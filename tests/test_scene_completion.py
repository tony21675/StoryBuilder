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
EYEWITNESS_CONFLICT_AUDIT = {"pass": False, "status": "conflict", "issues": ["presence_and_character_knowledge: draft evidence \"Unsupported eyewitness claim.\"; source evidence \"At home sick.\"; unsupported firsthand knowledge."], "details": []}
UNCERTAIN_AUDIT = {"pass": False, "status": "uncertain", "issues": [], "details": ["The timeline check is uncertain."]}


class FakeEngine:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.reset_calls = []

    def generate(self, prompt, on_delta=None):
        self.prompts.append(prompt)
        if not self.responses:
            raise RuntimeError("no fake response remains")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(on_delta):
            midpoint = max(1, len(response) // 2)
            on_delta(response[:midpoint])
            on_delta(response[midpoint:])
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
                "basis": "no_material_claim",
                "reason": "No material claim in this category.",
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

    def test_initial_scene_generation_forwards_streamed_text_callback(self):
        self.engine.responses = ["A scene arriving in pieces."]
        pieces = []
        draft, notice = generate_scene_with_completion_check(
            engine=self.engine, model_path=self.model,
            writer_system_prompt=self.system_prompt, initial_prompt="write",
            scene_context=self.scene_context, contract={},
            current_state=self.state, on_draft_delta=pieces.append,
        )
        self.assertEqual(draft, "A scene arriving in pieces.")
        self.assertEqual("".join(pieces), draft)
        self.assertIn("AUTOMATED REVIEW SKIPPED", notice)

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
        self.assertIn("AUTOMATED REVIEW:", notice)
        self.assertIn("reported no issues", notice)
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

    @patch("builder.scene_completion._run_scene_integrity_audit", side_effect=[EYEWITNESS_CONFLICT_AUDIT, PASS_AUDIT])
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
        self.assertIn("AUTOMATED REVIEW SKIPPED", notice)
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
            "Maya said Tiffany had told her about an abandoned warehouse on Route 9. "
            "Jessica began reviewing traffic cameras."
        )
        context = (
            "The abduction happened Friday afternoon. "
            "Boundaries: Do not introduce new clues. "
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
            "unsupported_consequential_details": (
                "Tiffany had told her about an abandoned warehouse on Route 9",
                "Boundaries: Do not introduce new clues.",
                "The draft invents a specific actionable destination despite the explicit boundary."
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
        self.assertEqual(len(result["issues"]), 5)
        joined = "\n".join(result["issues"])
        for source_quote, *_ in examples.values():
            self.assertIn(source_quote, joined)
        self.assertIn("unsupported_consequential_details", result["details"][3])

    def test_general_friend_based_habit_suggestion_is_not_itself_a_new_clue(self):
        prose = "Maya suggested Tiffany might have a familiar place she liked to go when overwhelmed."
        scene_context = (
            "Scene Idea: Form the beginning of a private effort. "
            "Boundaries: Do not introduce new clues. "
            "Maya and Chloe are lifelong friends of Tiffany."
        )
        checks = self._audit_checks()
        checks["unsupported_consequential_details"] = {
            "status": "clear",
            "basis": "new_present_scene_development",
            "reason": (
                "This is a tentative suggestion spoken during the current scene, not a claim "
                "that a location or prior event is established."
            ),
            "draft_evidence": prose,
            "source_evidence": "",
        }
        self.engine.responses = [json.dumps({"checks": checks})]
        result = _run_scene_integrity_audit(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            scene_context=scene_context,
            current_state={"scene_cast": ["Tony", "Maya"]},
            author_guidance="Maya and Chloe have known Tiffany for years.",
            prose=prose,
        )
        self.assertEqual(result["status"], "clear")
        self.assertEqual(result["issues"], [])
        prompt = self.engine.prompts[0]
        self.assertIn("Distinguish reasonable character-based speculation from established fact", prompt)
        self.assertIn("Maya and Chloe are lifelong friends of Tiffany.", prompt)

    def test_integrity_audit_can_quote_accepted_historical_corrections(self):
        prose = "The pressure leak was feeding the scrubber."
        accepted_history = "It's not a pressure bleed causing the spike."
        checks = self._audit_checks()
        checks["unsupported_consequential_details"] = {
            "status": "conflict",
            "reason": "The draft revives an explanation explicitly rejected in accepted prose.",
            "draft_evidence": prose,
            "source_evidence": accepted_history,
        }
        self.engine.responses = [json.dumps({"checks": checks})]

        result = _run_scene_integrity_audit(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            scene_context="The crew identifies the contamination path.",
            current_state={"current_situation": "The cause remains unresolved."},
            author_guidance="The failure is accidental, not sabotage.",
            historical_context=accepted_history,
            prose=prose,
        )

        self.assertEqual(result["status"], "conflict")
        self.assertIn(accepted_history, self.engine.prompts[0])
        self.assertIn(accepted_history, result["issues"][0])

    def test_integrity_audit_flags_unsupported_retroactive_history(self):
        prose = "Morgan said technician Kai had prepared the panel yesterday."
        policy_quote = (
            "Do not present a past action, encounter, maintenance event, log result, named off-scene person, "
            "diagnosis, motive, or other consequential historical detail as fact unless supported by author "
            "canon, accepted manuscript, or the original Scene Idea."
        )
        checks = self._audit_checks()
        checks["unsupported_consequential_details"] = {
            "status": "conflict",
            "reason": "The draft invents an unsupported past encounter and named off-scene person.",
            "draft_evidence": prose,
            "source_evidence": policy_quote,
        }
        self.engine.responses = [json.dumps({"checks": checks})]

        result = _run_scene_integrity_audit(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            scene_context="Elena gathers the crew to isolate the contamination source.",
            current_state={
                "unresolved_questions": [
                    "Where in the processing line are silicates entering the air scrubbers?"
                ]
            },
            author_guidance="The failure is accidental, not sabotage.",
            historical_context="The accepted prose establishes no technician visit.",
            prose=prose,
        )

        self.assertEqual(result["status"], "conflict")
        self.assertIn("SHARED CONTINUITY RULES (source block E)", self.engine.prompts[0])
        self.assertIn(policy_quote, result["issues"][0])

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

    def test_clear_audit_requires_exact_evidence_for_material_claims(self):
        prose = "Morgan says the seal felt sticky during the current inspection."
        checks = self._audit_checks()
        checks["unsupported_consequential_details"] = {
            "status": "clear",
            "basis": "new_present_scene_development",
            "reason": "This is a new on-page discovery, not a claim about an earlier inspection.",
            "draft_evidence": "",
            "source_evidence": "",
        }
        result = self._run_audit(
            prose,
            "Scene Idea: Elena gathers the crew to investigate contamination.",
            {"unresolved_questions": ["Where are silicates entering the system?"]},
            "The failure is accidental.",
            checks,
        )
        self.assertEqual(result["status"], "uncertain")
        self.assertTrue(any(
            "lacked verifiable exact draft evidence" in detail
            for detail in result["details"]
        ))

    def test_clear_on_page_discovery_can_pass_with_exact_draft_evidence(self):
        prose = "Morgan tests the seal during the scene and feels resistance."
        checks = self._audit_checks()
        checks["unsupported_consequential_details"] = {
            "status": "clear",
            "basis": "new_present_scene_development",
            "reason": "This is a new on-page discovery, not a claim about an earlier inspection.",
            "draft_evidence": prose,
            "source_evidence": "",
        }
        result = self._run_audit(
            prose,
            "Scene Idea: Elena gathers the crew to investigate contamination.",
            {"unresolved_questions": ["Where are silicates entering the system?"]},
            "The failure is accidental.",
            checks,
        )
        self.assertEqual(result["status"], "clear")

    def test_clear_established_fact_requires_verifiable_source_evidence(self):
        prose = "Daniel's scan matched the silicate signature."
        checks = self._audit_checks()
        checks["timeline_and_event_order"] = {
            "status": "clear",
            "basis": "established_fact",
            "reason": "The draft repeats an established diagnostic result.",
            "draft_evidence": prose,
            "source_evidence": "The ingress point is already confirmed.",
        }
        result = self._run_audit(
            prose,
            "Scene Idea: Elena consolidates the crew's findings.",
            {"unresolved_questions": ["Where are silicates entering the system?"]},
            "The failure is accidental.",
            checks,
        )
        self.assertEqual(result["status"], "uncertain")
        self.assertTrue(any(
            "lacked verifiable exact draft and supporting source excerpts" in detail
            for detail in result["details"]
        ))

    def test_audit_prompt_requires_category_by_category_evidence(self):
        checks = self._audit_checks()
        self.engine.responses = [json.dumps({"checks": checks})]
        result = _run_scene_integrity_audit(
            engine=self.engine,
            model_path=self.model,
            writer_system_prompt=self.system_prompt,
            scene_context="Scene Idea: end before investigation. Boundaries: Do not introduce new clues.",
            current_state={"scene_cast": ["Tony"]},
            author_guidance="No investigation in this scene.",
            prose="Tony listened.",
        )
        prompt = self.engine.prompts[0]
        for category in AUDIT_CATEGORIES:
            self.assertIn(category, prompt)
        self.assertIn("exact quote", prompt)
        self.assertIn("basis", prompt)
        self.assertIn("most consequential continuity-relevant claim", prompt)
        self.assertIn("No material claim in this category.", prompt)
        self.assertIn("new on-page action, observation, dialogue, or hypothesis", prompt)
        self.assertIn("unsupported consequential fact", prompt)
        self.assertIn("Do not treat ordinary brainstorming as a continuity conflict unless the draft presents or relies on it as fact", prompt)
        self.assertIn("Check for unsupported consequential facts", prompt)
        self.assertIn("direct correction or rejection in accepted manuscript evidence", prompt)
        self.assertIn("SHARED CONTINUITY RULES (source block E)", prompt)
        self.assertIn("current_state[unresolved_questions]", prompt)
        self.assertIn("New observations and discoveries made on-page now are welcome", prompt)
        self.assertIn(
            "as unresolved unless the scene establishes an answer through on-page evidence",
            prompt,
        )
        self.assertIn("the Scene Idea permits that progress", prompt)
        self.assertIn("indirect framing as well as explicit claims", prompt)
        self.assertIn("Distinguish reasonable character-based speculation from established fact", prompt)
        self.assertIn("Boundaries: Do not introduce new clues.", prompt)
        self.assertNotIn("abduction", prompt.casefold())
        self.assertNotIn("tiffany", prompt.casefold())
        self.assertEqual(result["status"], "clear")


if __name__ == "__main__":
    unittest.main()

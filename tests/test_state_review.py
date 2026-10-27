import json
import unittest

from builder.state_manager import MAIN_PLOT_SYSTEM_PROMPT
from builder.state_review import (
    STATE_PROPOSAL_REVIEW_SYSTEM_PROMPT,
    build_state_proposal_review_prompt,
    get_state_patch_value,
    iter_state_patch_text_fields,
    parse_state_proposal_review,
    review_state_proposal,
    set_state_patch_value,
)


class StateProposalReviewTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "chapter": 1,
            "scene": 4,
            "current_situation": "The scrubber temperature is rising; the cause is unknown.",
            "unresolved_questions": ["What is causing the temperature rise?"],
            "active_clues": ["A silicate-like trace remains unverified."],
        }
        self.patch = {
            "current_situation": (
                "The scrubber has failed because silicate contamination entered the housing."
            )
        }
        self.scene = (
            "The temperature remains elevated. The silicate-like trace is preliminary, "
            "and the team has not confirmed a cause."
        )

    def test_prompt_preserves_uncertainty_and_compares_proposed_fields(self):
        prompt = build_state_proposal_review_prompt(
            self.before, self.patch, self.scene,
            author_guidance="Keep hypotheses unconfirmed until evidence supports them.",
            scene_idea="Continue the investigation without resolving the cause.",
        )
        self.assertIn("ACCEPTED SCENE", prompt)
        self.assertIn("PROPOSED STATE CHANGES", prompt)
        self.assertIn("must be one of these paths: current_situation", prompt)
        self.assertIn("uncertainty", prompt.lower())
        self.assertIn("What is causing the temperature rise?", prompt)


    def test_main_plot_summary_keeps_material_unresolved_evidence(self):
        prompt = MAIN_PLOT_SYSTEM_PROMPT
        self.assertIn("exhaustive clue lists", prompt)
        self.assertIn("do not omit a concise reference to an unresolved physical anomaly", prompt)
        self.assertIn("when it materially changes the main crisis", prompt)
        self.assertIn("briefly identify who is pursuing an active diagnostic avenue", prompt)
        self.assertIn("a hypothesis is not a diagnosis", prompt)

    def test_state_reviewer_checks_full_scene_before_claiming_omission(self):
        prompt = STATE_PROPOSAL_REVIEW_SYSTEM_PROMPT
        self.assertIn("the entire accepted scene from beginning to end", prompt)
        self.assertIn("including dialogue and actions in the middle", prompt)
        self.assertIn(
            "Never claim that the scene does not mention something when the scene explicitly describes or discusses it.",
            prompt,
        )
        self.assertIn("genuinely missing or materially underrepresented", prompt)
        self.assertIn("possible timing match", prompt)

    def test_state_reviewer_does_not_treat_prior_state_as_a_checklist(self):
        prompt = STATE_PROPOSAL_REVIEW_SYSTEM_PROMPT
        self.assertIn("before-state is a fallible baseline, not a checklist", prompt)
        self.assertIn("A newer decision or plan in the accepted scene may replace or supersede", prompt)
        self.assertIn("Do not resurrect an earlier plan when a newer decision is now controlling.", prompt)
        self.assertIn("Prefer no finding over a weak or merely debatable finding.", prompt)
        self.assertIn("would likely cause the next scene to repeat events", prompt)
        self.assertIn("scene_evidence", prompt)
        self.assertIn("summary_evidence", prompt)

    def test_parser_keeps_only_findings_targeting_existing_text_with_verbatim_evidence(self):
        scene_evidence = "The silicate-like trace is preliminary, and the team has not confirmed a cause."
        summary_evidence = "The scrubber has failed because silicate contamination entered the housing."
        response = (
            '{"findings":['
            '{"field":"current_situation","title":"Unsupported cause",'
            '"message":"The scene leaves the cause unknown.",'
            '"edit_request":"Remove the confirmed cause and preserve uncertainty.",'
            '"scene_evidence":' + json.dumps(scene_evidence) + ','
            '"summary_evidence":' + __import__("json").dumps(summary_evidence) + '},'
            '{"field":"active_clues","title":"Bad target","message":"Do not target a list field.",'
            '"scene_evidence":' + __import__("json").dumps(scene_evidence) + '},'
            '{"field":"location.Ryan","title":"Not in patch","message":"This field was not proposed.",'
            '"scene_evidence":' + __import__("json").dumps(scene_evidence) + '}'
            ']}'
        )
        findings = parse_state_proposal_review(
            response, self.patch, accepted_scene=self.scene
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["field"], "current_situation")
        self.assertEqual(findings[0]["kind"], "state")
        self.assertTrue(findings[0]["can_suggest"])
        self.assertEqual(findings[0]["scene_evidence"], scene_evidence)
        self.assertEqual(findings[0]["summary_evidence"], summary_evidence)

    def test_parser_discards_findings_with_invented_scene_quotes(self):
        response = (
            '{"findings":[{"field":"current_situation","title":"Missing discovery",'
            '"message":"The accepted scene only covers the initial alarm.",'
            '"edit_request":"Repeat the full investigation.",'
            '"scene_evidence":"The accepted scene only covers the initial alarm.",'
            '"summary_evidence":""}]}'
        )
        findings = parse_state_proposal_review(
            response,
            {"current_situation": "The crew decides to prepare a Delta-9 bypass."},
            accepted_scene=(
                "Morgan reports intermittent vibration at the sealed housing. "
                "Ryan finds the Cycle 42 record. Zoe confirms a temporal match. "
                "Elena decides to prepare a bypass."
            ),
        )
        self.assertEqual(findings, [])

    def test_parser_discards_findings_with_nonverbatim_summary_quotes(self):
        response = (
            '{"findings":[{"field":"current_situation","title":"Missing decision",'
            '"message":"The current decision is not preserved.",'
            '"edit_request":"Change the summary.",'
            '"scene_evidence":"Elena decides to prepare a partial bypass.",'
            '"summary_evidence":"The crew agrees to prep the Delta-9 bypass."}]}'
        )
        findings = parse_state_proposal_review(
            response,
            {"current_situation": "The crew agrees to prepare the Delta-9 bypass."},
            accepted_scene="Elena decides to prepare a partial bypass after weighing the risk.",
        )
        self.assertEqual(findings, [])

    def test_review_warns_when_all_model_findings_fail_evidence_validation(self):
        response = (
            '{"findings":[{"field":"current_situation","title":"Unsupported finding",'
            '"message":"The scene omits an action that is actually present.",'
            '"edit_request":"Change the summary.",'
            '"scene_evidence":"The accepted scene only covers the initial alarm.",'
            '"summary_evidence":""}]}'
        )

        class StubEngine:
            def reset_context(self, model_path, system_prompt):
                pass

            def generate(self, prompt, timeout):
                return response

        findings, warning = review_state_proposal(
            engine=StubEngine(),
            model_path="test-model.gguf",
            original_system_prompt="writer prompt",
            current_state=self.before,
            proposed_patch=self.patch,
            accepted_scene=self.scene,
        )
        self.assertEqual(findings, [])
        self.assertIsNotNone(warning)
        self.assertIn("returned findings", warning)
        self.assertIn("evidence validation", warning)
        self.assertIn("No review popup was shown", warning)

    def test_empty_findings_means_no_semantic_concerns(self):
        self.assertEqual(
            parse_state_proposal_review('{"findings":[]}', self.patch, accepted_scene=self.scene),
            [],
        )

    def test_text_path_accessors_change_only_the_proposed_patch(self):
        patch = {"current_situation": "First. Second.", "location": {"Elena": "At the hub."}}
        self.assertEqual(get_state_patch_value(patch, "location.Elena"), "At the hub.")
        set_state_patch_value(patch, "location.Elena", "Near the closed hatch.")
        self.assertEqual(patch["location"]["Elena"], "Near the closed hatch.")
        self.assertEqual(iter_state_patch_text_fields(patch), {
            "current_situation": "First. Second.",
            "location.Elena": "Near the closed hatch.",
        })

    def test_state_text_replacement_can_correct_an_entire_single_field(self):
        from builder.state_review import apply_state_text_replacement

        corrected = apply_state_text_replacement(
            "The scrubber has failed because contamination is confirmed.",
            "The scrubber has failed because contamination is confirmed.",
            "The scrubber temperature remains elevated, but the cause is still unknown.",
        )
        self.assertEqual(
            corrected,
            "The scrubber temperature remains elevated, but the cause is still unknown.",
        )

    def test_state_text_replacement_rejects_ambiguous_targets(self):
        from builder.state_review import apply_state_text_replacement

        with self.assertRaisesRegex(ValueError, "appears more than once"):
            apply_state_text_replacement("Unknown. Unknown.", "Unknown", "uncertain")

    def test_path_accessor_rejects_overwriting_non_text_state_structures(self):
        with self.assertRaisesRegex(ValueError, "existing text field"):
            set_state_patch_value({"active_clues": ["one"]}, "active_clues", "replacement")


if __name__ == "__main__":
    unittest.main()

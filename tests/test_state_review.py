import unittest

from builder.state_review import (
    build_state_proposal_review_prompt,
    get_state_patch_value,
    iter_state_patch_text_fields,
    parse_state_proposal_review,
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

    def test_parser_keeps_only_findings_targeting_existing_text_in_the_patch(self):
        response = (
            '{"findings":['
            '{"field":"current_situation","title":"Unsupported cause",'
            '"message":"The scene leaves the cause unknown.",'
            '"edit_request":"Remove the confirmed cause and preserve uncertainty."},'
            '{"field":"active_clues","title":"Bad target","message":"Do not target a list field."},'
            '{"field":"location.Ryan","title":"Not in patch","message":"This field was not proposed."}'
            ']}'
        )
        findings = parse_state_proposal_review(response, self.patch)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["field"], "current_situation")
        self.assertEqual(findings[0]["kind"], "state")
        self.assertTrue(findings[0]["can_suggest"])

    def test_empty_findings_means_no_semantic_concerns(self):
        self.assertEqual(parse_state_proposal_review('{"findings":[]}', self.patch), [])

    def test_text_path_accessors_change_only_the_proposed_patch(self):
        patch = {"current_situation": "First. Second.", "location": {"Elena": "At the hub."}}
        self.assertEqual(get_state_patch_value(patch, "location.Elena"), "At the hub.")
        set_state_patch_value(patch, "location.Elena", "Near the closed hatch.")
        self.assertEqual(patch["location"]["Elena"], "Near the closed hatch.")
        self.assertEqual(iter_state_patch_text_fields(patch), {
            "current_situation": "First. Second.",
            "location.Elena": "Near the closed hatch.",
        })

    def test_path_accessor_rejects_overwriting_non_text_state_structures(self):
        with self.assertRaisesRegex(ValueError, "existing text field"):
            set_state_patch_value({"active_clues": ["one"]}, "active_clues", "replacement")


if __name__ == "__main__":
    unittest.main()

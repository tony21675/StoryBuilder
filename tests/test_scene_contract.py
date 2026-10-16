import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from builder import scene_contract
from builder.scene_contract import (
    SceneContract,
    SceneContractResponseError,
    SceneContractValidationUnavailable,
)


class FakeEngine:
    def __init__(self):
        self.model_path = Path("/tmp/Llama-3.1-8B-instruct-Q4_K_M.gguf")

    def generate(self, _prompt):
        raise AssertionError("Semantic validation must not reuse the prose writer session")


class SceneContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "required_beats": [
                "Tony notices Maya's temporary red cheek mark and asks what happened.",
                "Maya explains that the unfamiliar man struck her across the cheek during the struggle with Tiffany.",
                "Tony asks Maya what happened to Tiffany.",
            ],
            "required_facts": [
                "Maya's cheek injury was caused by the unfamiliar man striking her.",
            ],
            "required_sequence": [
                "Notice and question the cheek mark.",
                "Maya explains the cause.",
                "Tony asks about Tiffany.",
            ],
            "forbidden": [
                "Do not repeat 'Tiffany is gone' as new information.",
            ],
            "forbidden_details": [
                "Do not introduce bleeding or a lasting cheek injury.",
            ],
            "hard_stop": "End after Tony asks what happened to Tiffany and Maya is ready to answer.",
            "local_hard_checks": {
                "forbidden_terms": ["blood", "bleeding", "bruise", "scrape", "cut"],
                "forbidden_patterns": [
                    r"\bTony\b[^\n\"“”]{0,220}\b(?:stranger|unfamiliar man|kidnapper)\b[^\n\"“”]{0,180}\b(?:took|taken|kidnapped|abducted)\b[^\n\"“”]{0,100}\bTiffany\b"
                ],
                # These used to be hard requirements. They are intentionally
                # left here to prove that wording regexes no longer gate prose.
                "required_patterns": [
                    {
                        "label": "Old wording gate",
                        "pattern": r"\b(?:Tony|he)\b[^\n]{0,20}\bred mark\b"
                    }
                ],
            },
        }

    def test_has_saved_contract_detects_fields_that_a_rebuild_would_replace(self):
        entries = [
            {"direction": "Existing direction"},
            {"end_condition": "Existing ending"},
            {"scene_contract": {"hard_stop": "Existing hard stop"}},
            {"scene_contract": {"required_beats": ["Required action"]}},
            {"scene_contract": {"required_facts": ["Legacy content to preserve"]}},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertTrue(SceneContract.has_saved_contract(entry))

    def test_has_saved_contract_ignores_scene_idea_and_empty_shell(self):
        entries = [
            {},
            None,
            {"scene_idea": "Tony cares for Maya and they drink tea."},
            {"scene_idea": "An idea.", "scene_contract": {"required_beats": [], "max_attempts": 3}},
            {"scene_contract": {}},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertFalse(SceneContract.has_saved_contract(entry))

    def test_creative_paraphrase_is_not_rejected_by_wording_regex(self):
        prose = (
            "Tony noticed a flush of color on Maya's cheek. "
            "\"What happened?\" he asked. "
            "\"The unfamiliar man backhanded me during the struggle with Tiffany,\" Maya said. "
            "Tony's expression tightened. "
            "\"Tell me what happened to Tiffany.\" "
            "Maya drew a breath and prepared herself to explain."
        )

        result = scene_contract.SceneContract._local_hard_checks(self.contract, prose)

        self.assertTrue(result["pass"], result)

    def test_paragraph_breaks_do_not_break_forbidden_pattern_detection(self):
        prose = (
            "Tony stared at Maya.\n\n"
            "He kept thinking about the unfamiliar man who had taken Tiffany."
        )

        result = scene_contract.SceneContract._local_hard_checks(self.contract, prose)

        self.assertFalse(result["pass"])
        self.assertTrue(result["violations"])

    def test_forbidden_terms_still_fail(self):
        prose = "Tony noticed a bruise on Maya's cheek."

        result = scene_contract.SceneContract._local_hard_checks(self.contract, prose)

        self.assertFalse(result["pass"])
        self.assertIn("bruise", result["violations"][0])

    def test_semantic_validator_uses_separate_process_and_omits_regex_hints(self):
        prose = "Tony comforts Maya, and they finish at the kitchen table."
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
        }
        raw_validator_result = dict(validator_result, checks=[
            {
                "requirement": "Tony comforts Maya.",
                "status": "met",
                "evidence": "Tony comforts Maya",
            },
            {
                "requirement": "They end at the kitchen table.",
                "status": "met",
                "evidence": "they finish at the kitchen table",
            },
        ])
        captured = {}

        def fake_validator(model, prompt):
            captured["model"] = model
            captured["prompt"] = prompt
            return raw_validator_result

        engine = FakeEngine()
        idea = "The original plain-English idea says Tony comforts Maya and they end at the kitchen table."

        with patch.object(scene_contract, "_run_validator", side_effect=fake_validator):
            result = SceneContract.validate_with_engine(
                engine,
                dict(self.contract, author_idea=idea),
                {
                    "chapter": 2,
                    "scene": 1,
                    "current_situation": "Tony and Maya are together.",
                    "physical_state": {"Tony": {"position": "sitting on the bed"}},
                    "unrelated_archive_blob": "This old material must not enter validation.",
                },
                prose,
            )

        self.assertEqual(result, validator_result)
        self.assertEqual(captured["model"], engine.model_path)
        self.assertIn("required_beats", captured["prompt"])
        self.assertIn("hard_stop", captured["prompt"])
        self.assertIn(idea, captured["prompt"])
        self.assertIn("physical_state", captured["prompt"])
        self.assertIn("sitting on the bed", captured["prompt"])
        self.assertIn(prose, captured["prompt"])
        self.assertNotIn("unrelated_archive_blob", captured["prompt"])
        self.assertNotIn("This old material must not enter validation.", captured["prompt"])
        self.assertNotIn('"state_after"', captured["prompt"])
        self.assertNotIn('"local_hard_checks"', captured["prompt"])
        self.assertNotIn('"required_facts"', captured["prompt"])
        self.assertNotIn('"required_sequence"', captured["prompt"])
        self.assertNotIn('"forbidden"', captured["prompt"])
        self.assertNotIn('"forbidden_details"', captured["prompt"])
        self.assertNotIn("Old wording gate", captured["prompt"])
        self.assertLess(len(captured["prompt"]), 3200)
        self.assertLess(len(scene_contract.VALIDATOR_SYSTEM_PROMPT), 1500)


    def test_validator_string_false_is_treated_as_false(self):
        prose = "A valid creative scene."
        validator_result = {
            "pass": "false",
            "missed_beats": ["The required ending is missing."],
            "violations": [],
            "notes": "",
        }

        with patch.object(scene_contract, "_run_validator", return_value=validator_result):
            result = scene_contract.SceneContract.validate_with_engine(
                FakeEngine(),
                self.contract,
                {"chapter": 2, "scene": 1},
                prose,
            )

        self.assertFalse(result["pass"])

    def test_validator_retries_once_with_a_corrected_json_prompt(self):
        valid_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
        }
        with patch.object(
            scene_contract,
            "_run_validator",
            side_effect=[
                SceneContractResponseError("invalid JSON"),
                valid_result,
            ],
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                self.contract,
                {"chapter": 2, "scene": 1},
                "A complete, natural scene.",
            )

        self.assertTrue(result["pass"])
        self.assertEqual(run_validator.call_count, 2)
        first_prompt = run_validator.call_args_list[0].args[1]
        retry_prompt = run_validator.call_args_list[1].args[1]
        self.assertNotEqual(first_prompt, retry_prompt)
        self.assertIn("CORRECTION REQUIRED", retry_prompt)
        self.assertIn('"pass": true, "missed_beats": [], "violations": [], "checks": [{"requirement": "", "status": "met", "evidence": ""}], "notes": ""', retry_prompt)

    def test_validator_unavailable_after_retry_is_distinguished_from_scene_failure(self):
        with patch.object(
            scene_contract,
            "_run_validator",
            side_effect=[
                SceneContractResponseError("invalid JSON"),
                SceneContractResponseError("still invalid JSON"),
            ],
        ) as run_validator:
            with self.assertRaises(SceneContractValidationUnavailable) as raised:
                SceneContract.validate_with_engine(
                    FakeEngine(),
                    self.contract,
                    {"chapter": 2, "scene": 1},
                    "A complete, natural scene.",
                )

        self.assertEqual(run_validator.call_count, 2)
        self.assertIn("not been semantically validated", str(raised.exception))
        self.assertIn("before deciding whether to accept it", str(raised.exception))

    def test_validator_cannot_pass_with_reported_omissions_or_violations(self):
        cases = [
            {
                "pass": True,
                "missed_beats": ["The required phone calls are missing."],
                "violations": [],
                "notes": "",
            },
            {
                "pass": True,
                "missed_beats": [],
                "violations": ["The scene contradicts established character knowledge."],
                "notes": "",
            },
        ]

        for raw_result in cases:
            with self.subTest(raw_result=raw_result):
                with patch.object(
                    scene_contract, "_run_validator", return_value=raw_result
                ):
                    result = SceneContract.validate_with_engine(
                        FakeEngine(),
                        self.contract,
                        {"chapter": 2, "scene": 1},
                        "A scene draft with prose.",
                    )

                self.assertFalse(result["pass"])
                self.assertIn(
                    "cannot pass yet",
                    result["notes"],
                )

    def test_scene_revision_prompt_keeps_previous_draft_and_limits_changes(self):
        draft = "The dialogue and the quiet ending already work."
        feedback = "Barnaby is Tiffany's stuffed rabbit, not a dog."
        prompt = SceneContract.revision_prompt("BASE IDEA", draft, feedback)

        self.assertIn(draft, prompt)
        self.assertIn(feedback, prompt)
        self.assertIn("Use the previous draft below as your starting point", prompt)
        self.assertIn("Do not rewrite unaffected passages", prompt)
        self.assertIn("missing explicit", prompt)
        self.assertIn("natural prose rather than", prompt)
        self.assertIn("restore the intended choice rather than a near-equivalent", prompt)
        self.assertIn("defining details and meaningful", prompt)
        self.assertNotIn("Rewrite the scene from the beginning", prompt)

    def test_validator_treats_required_beats_as_narrative_goals(self):
        prompt = scene_contract.VALIDATOR_SYSTEM_PROMPT
        self.assertIn("Required Beats are goals, not a wording checklist", prompt)
        self.assertIn("Fail for absent/materially wrong core actions/outcomes", prompt)
        self.assertIn("a bubble bath is not a shower", prompt)
        self.assertIn("a warm bubble bath includes bubbles", prompt)
        self.assertIn('"checks": [{"requirement": "", "status": "met", "evidence": ""}]', prompt)
        self.assertIn("verbatim quote directly proving it", prompt)
        self.assertIn("COMPLETED SCENE only", prompt)
        self.assertIn("never from the author idea, instructions", prompt)
        self.assertIn("keep stated object backstory", prompt)
        self.assertIn("Omitting/substituting one is material", prompt)
        self.assertIn("Ignore incidental description unless a specified action/object, core outcome, knowledge, or endpoint changes", prompt)
        self.assertLess(len(prompt), 1500)

    def test_validator_checks_whole_scene_before_calling_a_beat_missing(self):
        prose = (
            "Tony offers Maya a warm bath, makes sure she has privacy, and leaves her "
            "to bathe. While she is in the bathroom, he calls Beth about breakfast, "
            "then calls Jessica, who confirms that she, Chloe, and Rick will attend "
            "breakfast tomorrow. Later, Tony retrieves clean clothes, hugs Barnaby "
            "in Tiffany's room and vows to bring her home, then drinks chamomile tea "
            "with Maya at the kitchen table."
        )
        captured = {}
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
        }

        def fake_validator(model, prompt):
            captured["prompt"] = prompt
            return validator_result

        with patch.object(
            scene_contract, "_run_validator", side_effect=fake_validator
        ):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                self.contract,
                {"chapter": 2, "scene": 4, "current_situation": "Tony is holding Maya."},
                prose,
            )

        self.assertTrue(result["pass"], result)
        self.assertIn(
            "Treat Required Beats as narrative-level goals, not a word-for-word checklist",
            captured["prompt"],
        )
        self.assertIn(
            "If the main action occurs but only a purely incidental detail is missing, do not fail for that alone",
            captured["prompt"],
        )
        self.assertIn(
            "A specified bubble bath replaced with a shower is a material substitution",
            captured["prompt"],
        )
        self.assertIn(
            "Search the entire scene for equivalent actions, including paraphrases or later paragraphs",
            captured["prompt"],
        )
        self.assertIn(
            "Do not fail for a minor descriptive or phrasing omission when the intended event, character knowledge, and endpoint remain intact",
            captured["prompt"],
        )
        self.assertIn(prose, captured["prompt"])
        self.assertLess(len(captured["prompt"]), 3200)


    def test_reported_missing_author_detail_blocks_a_false_pass(self):
        idea = "Tony offers Maya a warm bubble bath with unscented bubbles and gives her privacy."
        prose = "Tony offered Maya a warm bath, then left the room to give her privacy."
        raw_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {
                    "requirement": "Tony offers a warm bubble bath with unscented bubbles.",
                    "status": "missing",
                    "evidence": "",
                },
                {
                    "requirement": "Tony gives Maya privacy.",
                    "status": "met",
                    "evidence": "left the room to give her privacy.",
                },
            ],
            "notes": "",
        }

        with patch.object(scene_contract, "_run_validator", return_value=raw_result):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 2, "scene": 4},
                prose,
            )

        self.assertFalse(result["pass"])
        self.assertTrue(any("warm bubble bath with unscented bubbles" in item for item in result["missed_beats"]))

    def test_copied_instruction_evidence_is_retried_and_corrected_scene_quote_can_pass(self):
        idea = "Tony offers Maya a warm bubble bath with unscented bubbles and gives her privacy."
        prose = (
            "Tony offered Maya a warm bubble bath with unscented bubbles, "
            "then left the room to give her privacy."
        )
        ungrounded_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {
                    "requirement": "Tony offers a warm bubble bath with unscented bubbles.",
                    "status": "met",
                    "evidence": "If the main action occurs but only a purely incidental detail is missing, do not fail for that alone.",
                },
                {
                    "requirement": "Tony gives Maya privacy.",
                    "status": "met",
                    "evidence": "left the room to give her privacy.",
                },
            ],
            "notes": "",
        }
        corrected_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {
                    "requirement": "Tony offers a warm bubble bath with unscented bubbles.",
                    "status": "met",
                    "evidence": "Tony offered Maya a warm bubble bath with unscented bubbles",
                },
                {
                    "requirement": "Tony gives Maya privacy.",
                    "status": "met",
                    "evidence": "left the room to give her privacy.",
                },
            ],
            "notes": "",
        }

        with patch.object(
            scene_contract,
            "_run_validator",
            side_effect=[ungrounded_result, corrected_result],
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 2, "scene": 4},
                prose,
            )

        self.assertTrue(result["pass"], result)
        self.assertEqual(run_validator.call_count, 2)
        retry_prompt = run_validator.call_args_list[1].args[1]
        self.assertIn("TARGETED EVIDENCE CORRECTION REQUIRED", retry_prompt)
        self.assertIn("author's idea", retry_prompt)
        self.assertIn("starting state", retry_prompt)
        self.assertIn("EVIDENCE SOURCE (only this passage may be quoted):", retry_prompt)
        self.assertTrue(retry_prompt.rstrip().endswith(prose))

    def test_repeated_invalid_evidence_returns_validation_unavailable(self):
        idea = "Tony offers Maya a warm bubble bath with unscented bubbles and gives her privacy."
        prose = "Tony offered Maya a warm bath, then left the room to give her privacy."
        copied_idea_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {
                    "requirement": "Tony offers a warm bubble bath with unscented bubbles.",
                    "status": "met",
                    "evidence": idea,
                },
            ],
            "notes": "",
        }

        with patch.object(
            scene_contract,
            "_run_validator",
            side_effect=[copied_idea_result, copied_idea_result],
        ) as run_validator:
            with self.assertRaises(SceneContractValidationUnavailable) as raised:
                SceneContract.validate_with_engine(
                    FakeEngine(),
                    {"author_idea": idea, "required_beats": []},
                    {"chapter": 2, "scene": 4},
                    prose,
                )

        self.assertEqual(run_validator.call_count, 2)
        self.assertIn("not been semantically validated", str(raised.exception))
        self.assertIn("evidence", str(raised.exception).lower())
        self.assertIn(
            "EVIDENCE SOURCE (only this passage may be quoted):",
            run_validator.call_args_list[1].args[1],
        )

    def test_plain_english_idea_cannot_pass_without_coverage_report(self):
        idea = "Tony offers Maya a warm bubble bath and leaves her private."
        old_schema = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
        }

        with patch.object(
            scene_contract, "_run_validator", side_effect=[old_schema, old_schema]
        ) as run_validator:
            with self.assertRaises(SceneContractValidationUnavailable):
                SceneContract.validate_with_engine(
                    FakeEngine(),
                    {"author_idea": idea, "required_beats": []},
                    {"chapter": 2, "scene": 4},
                    "Tony offers Maya a warm bath and leaves the room.",
                )

        self.assertEqual(run_validator.call_count, 2)
        self.assertIn('"checks": [{"requirement": "", "status": "met", "evidence": ""}]', run_validator.call_args_list[0].args[1])



    def test_validator_prompt_puts_author_idea_first_and_compacts_guidance_and_state(self):
        idea = (
            "Tony offers Maya a warm bubble bath while she has privacy, calls Beth "
            "and Jessica about breakfast, then hugs Barnaby in Tiffany's room."
        )
        guidance = "\n".join([
            "- Generic unrelated guidance about distant plot arcs.",
            "- Maya's personal belongings may carry Tiffany's familiar scent.",
            "- Do not introduce floral scents in bath products.",
            "- Only characters explicitly listed in the scene cast participate.",
            "- Do not import details from discarded drafts.",
        ] + [
            "- Generic unrelated guidance about distant plot arcs and background lore."
            for _ in range(20)
        ])
        compact_guidance = scene_contract._compact_validator_guidance(
            guidance, idea, ["Tony", "Maya"]
        )
        self.assertLessEqual(len(compact_guidance), 1600)
        self.assertIn("floral scents", compact_guidance)
        self.assertIn("Only characters explicitly listed", compact_guidance)
        self.assertNotIn("distant plot arcs", compact_guidance)

        state = {
            "chapter": 2,
            "scene": 4,
            "scene_cast": ["Tony", "Maya"],
            "current_situation": "Maya is recounting Tiffany's abduction.",
            "location": {
                "primary": "Tony and Tiffany's home",
                "Tony": "In the bedroom",
                "Maya": "Against Tony",
                "Tiffany": "Inside the van",
            },
            "physical_state": {
                "Tony": {"position": "sitting"},
                "Maya": {"position": "lying against Tony"},
                "Tiffany": {"position": "inside the van"},
            },
            "character_knowledge": {
                "Tony": ["Knows Maya was struck."],
                "Maya": ["Witnessed the abduction."],
                "Tiffany": ["Knows Tony is her father."],
            },
            "active_objectives": {
                "Tony": "Protect Maya",
                "Tiffany": "Stay safe",
            },
            "unrelated_history": "Do not send this to the validator.",
        }
        compact_state = scene_contract._compact_validation_state(
            state, ["Tony", "Maya"], idea
        )
        self.assertIn("Tony", compact_state["character_knowledge"])
        self.assertIn("Maya", compact_state["character_knowledge"])
        self.assertNotIn("Tiffany", compact_state["character_knowledge"])
        self.assertNotIn("unrelated_history", compact_state)
        self.assertIn("Tiffany", compact_state["location"])
        self.assertIn("Tiffany", compact_state["physical_state"])

        captured = {}
        prose = "Tony offers Maya a warm bubble bath. He calls Beth and Jessica, then hugs Barnaby."
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
            "checks": [
                {
                    "requirement": "Tony offers Maya a bath.",
                    "status": "met",
                    "evidence": "Tony offers Maya a warm bubble bath.",
                }
            ],
        }

        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return validator_result

        with patch.object(scene_contract, "_run_validator", side_effect=fake_validator):
            SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "direction": "A concise supporting direction."},
                state,
                prose,
                author_guidance=guidance,
            )

        prompt = captured["prompt"]
        self.assertLess(
            prompt.index("AUTHOR'S ORIGINAL SCENE IDEA (PRIMARY VALIDATION SOURCE)"),
            prompt.index("VALIDATOR TASK:"),
        )
        self.assertLess(prompt.index(idea), prompt.index("SUPPORTING SCENE DIRECTION AND CONTRACT"))
        self.assertLess(prompt.index("STARTING STATE (relevant fields only)"), prompt.index("COMPLETED SCENE:"))
        self.assertNotIn('"author_idea"', prompt)
        self.assertNotIn("Do not send this to the validator.", prompt)
        self.assertNotIn("unrelated_history", prompt)
        self.assertLess(len(prompt), 11000)

    def test_retry_explains_missing_coverage_instead_of_claiming_json_is_unreadable(self):
        idea = "Tony offers Maya a warm bubble bath and leaves her in private."
        old_schema = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
        }
        valid = {
            "pass": False,
            "missed_beats": ["The bubble bath is not explicit."],
            "violations": [],
            "notes": "",
            "checks": [
                {
                    "requirement": "Tony offers a warm bubble bath.",
                    "status": "missing",
                    "evidence": "",
                }
            ],
        }
        with patch.object(
            scene_contract, "_run_validator", side_effect=[old_schema, valid]
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea},
                {"chapter": 2, "scene": 4},
                "Tony offers Maya a warm bath and leaves her in private.",
            )

        self.assertFalse(result["pass"])
        retry_prompt = run_validator.call_args_list[1].args[1]
        self.assertIn("checks", retry_prompt)
        self.assertIn("itemized author-intent checks", retry_prompt)
        self.assertIn("do not claim they are absent", retry_prompt)
        self.assertNotIn("previous response was not a readable", retry_prompt)



    def test_minor_secondary_detail_can_be_reported_without_failing_scene(self):
        idea = (
            "Tony helps Maya bathe privately, makes ordinary breakfast calls while "
            "she bathes, gets her clean clothes and hugs Barnaby, then ends with "
            "chamomile tea at the kitchen table."
        )
        contract = {
            "author_idea": idea,
            "required_beats": [
                "Tony gives Maya a private opportunity to bathe.",
                "Tony handles breakfast arrangements with Beth and Jessica for tomorrow.",
                "Tony retrieves clean clothes, hugs Barnaby, and privately vows to bring Tiffany home.",
                "The scene ends with quiet tea with Maya at the kitchen table.",
            ],
            "hard_stop": "Tony and Maya begin to settle over tea at the kitchen table.",
        }
        prose = (
            "Tony offers Maya a warm bath and leaves her in private. While she bathes, "
            "he calls Beth about breakfast, then calls Jessica, who confirms that she, "
            "Chloe, and Rick will join tomorrow. He fetches clean clothes, hugs Barnaby "
            "in Tiffany's room and silently vows to bring his daughter home. He then "
            "makes chamomile tea and sits with Maya at the kitchen table."
        )
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "The reassurance to Beth could be a little more explicit.",
            "checks": [
                {
                    "requirement": "Tony offers Maya a bath and leaves her in private.",
                    "status": "met",
                    "evidence": "Tony offers Maya a warm bath and leaves her in private.",
                },
                {
                    "requirement": "Tony calls Beth and Jessica to arrange breakfast, with Jessica confirming everyone.",
                    "status": "met",
                    "evidence": "he calls Beth about breakfast, then calls Jessica, who confirms that she, Chloe, and Rick will join tomorrow.",
                },
                {
                    "requirement": "Tony gets clean clothes, hugs Barnaby, and vows to bring Tiffany home.",
                    "status": "met",
                    "evidence": "He fetches clean clothes, hugs Barnaby in Tiffany's room and silently vows to bring his daughter home.",
                },
                {
                    "requirement": "Tony ends with chamomile tea at the kitchen table.",
                    "status": "met",
                    "evidence": "He then makes chamomile tea and sits with Maya at the kitchen table.",
                },
            ],
        }
        captured = {}

        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return validator_result

        with patch.object(
            scene_contract, "_run_validator", side_effect=fake_validator
        ):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                contract,
                {"chapter": 2, "scene": 4, "current_situation": "Tony is comforting Maya."},
                prose,
            )

        self.assertTrue(result["pass"], result)
        self.assertEqual(result["missed_beats"], [])
        self.assertIn("could be a little more explicit", result["notes"])
        self.assertIn("purely incidental detail is missing", captured["prompt"])
        self.assertIn(
            "A specified bubble bath replaced with a shower is a material substitution",
            captured["prompt"],
        )
        self.assertIn(prose, captured["prompt"])

    def test_guidance_builds_contract_from_legacy_fields_and_active_modules(self):
        guidance = {
            "direction": "Let the characters talk naturally.",
            "end_condition": "Stop when they reach the house.",
            "required_events": ["They leave the store."],
            "required_facts": ["Ignore this legacy fact gate."],
            "required_sequence": ["Ignore this legacy sequence gate."],
            "forbidden_details": ["Ignore this legacy forbidden detail."],
            "do_not_advance": ["Ignore this legacy do-not-advance gate."],
            "scene_contract": {
                "required_facts": ["Ignore nested facts."],
                "required_sequence": ["Ignore nested sequence."],
                "forbidden": ["Ignore nested prohibition."],
                "forbidden_details": ["Ignore nested details."],
            },
        }
        modules = [{
            "required_events": ["A dog barks."],
            "do_not_advance": ["Do not introduce a second dog."],
            "scene_contract": {
                "required_sequence": ["Ignore module sequence."],
                "forbidden": ["Ignore module prohibition."],
            },
        }]

        contract = scene_contract.SceneContract.from_guidance(guidance, modules)

        self.assertEqual(
            contract["required_beats"],
            ["They leave the store.", "A dog barks."],
        )
        self.assertNotIn("required_facts", contract)
        self.assertNotIn("required_sequence", contract)
        self.assertNotIn("forbidden", contract)
        self.assertNotIn("forbidden_details", contract)
        self.assertEqual(contract["hard_stop"], "Stop when they reach the house.")

    def test_plain_english_idea_survives_as_primary_writer_intent(self):
        idea = (
            "Continue from the accepted scene without repeating Maya's account. "
            "Tony offers her a warm bubble bath and gives her privacy. While she has time "
            "to herself, he invites Beth to breakfast, then invites Jessica, Chloe, and Rick "
            "together without revealing the abduction. He gets Maya clean clothes, briefly "
            "holds Barnaby in Tiffany's room and returns the rabbit to its usual place. "
            "Later he makes chamomile tea and sits with Maya at the kitchen table. End there, "
            "before bedtime or rescue planning."
        )
        guidance = {
            "scene_idea": idea,
            "direction": "Tony takes care of Maya and handles arrangements.",
            "end_condition": "Before bedtime or rescue planning begins.",
            "scene_contract": {
                "required_beats": [],
                "hard_stop": "Before bedtime or rescue planning begins.",
                "max_attempts": 3,
            },
        }

        contract = SceneContract.from_guidance(guidance)
        writer_context = SceneContract.writer_prompt_context(
            "Chapter 2, Scene 4. Maya is curled against Tony on the bed.",
            contract,
        )

        self.assertEqual(contract["author_idea"], idea)
        self.assertIn("AUTHOR'S ORIGINAL PLAIN-ENGLISH SCENE IDEA (PRIMARY INTENT):", writer_context)
        self.assertIn(idea, writer_context)
        self.assertIn("COMPACT SUPPORTING CONTRACT (SECONDARY):", writer_context)
        self.assertIn("AUTHOR ACTION FIDELITY", writer_context)
        self.assertIn("a bubble bath is not a shower", writer_context)
        self.assertIn("Treat wording such as 'can' or 'may' as permission", writer_context)
        self.assertIn("Natural dialogue, gestures, pacing, transitions, and connective", writer_context)
        self.assertLess(
            writer_context.index("AUTHOR'S ORIGINAL PLAIN-ENGLISH SCENE IDEA"),
            writer_context.index("CURRENT SCENE CONTEXT AND CONTINUITY"),
        )
        self.assertLess(
            writer_context.index("CURRENT SCENE CONTEXT AND CONTINUITY"),
            writer_context.index("COMPACT SUPPORTING CONTRACT"),
        )
        self.assertIn("kitchen table", writer_context)
        self.assertIn("Barnaby", writer_context)
        self.assertIn("It is not a word-for-word prose checklist", writer_context)
        self.assertIn("must not overrule or contradict the author's intent", writer_context)

    def test_validator_receives_original_plain_english_idea(self):
        idea = (
            "Tony offers Maya a warm bubble bath, makes the breakfast calls without revealing "
            "the abduction, returns Barnaby to Tiffany's room, and ends at the kitchen table "
            "with chamomile tea."
        )
        captured = {}

        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return {
                "pass": True,
                "missed_beats": [],
                "violations": [],
                "checks": [
                    {
                        "requirement": "Tony offers Maya a warm bubble bath.",
                        "status": "missing",
                        "evidence": "",
                    },
                    {
                        "requirement": "Tony makes the breakfast calls without revealing the abduction.",
                        "status": "missing",
                        "evidence": "",
                    },
                    {
                        "requirement": "Tony returns Barnaby to Tiffany's room.",
                        "status": "missing",
                        "evidence": "",
                    },
                    {
                        "requirement": "The scene ends with chamomile tea at the kitchen table.",
                        "status": "missing",
                        "evidence": "",
                    },
                ],
                "notes": "",
            }

        contract = {
            "author_idea": idea,
            "direction": "Tony takes care of Maya.",
            "hard_stop": "Before bedtime.",
            "required_beats": [],
        }
        with patch.object(
            scene_contract, "_run_validator", side_effect=fake_validator
        ):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                contract,
                {
                    "chapter": 2,
                    "scene": 4,
                    "current_situation": "Maya is curled against Tony on the bed.",
                },
                "Tony remained beside Maya in the bedroom.",
            )

        self.assertFalse(result["pass"])
        self.assertTrue(any("warm bubble bath" in item for item in result["missed_beats"]))
        self.assertIn(idea, captured["prompt"])
        self.assertNotIn('"author_idea"', captured["prompt"])
        self.assertIn("The idea is primary", captured["prompt"])
        self.assertIn('"checks": [{"requirement": "", "status": "met", "evidence": ""}]', captured["prompt"])
        self.assertIn("original idea", scene_contract.VALIDATOR_SYSTEM_PROMPT)

    def test_validator_receives_stable_author_guidance_and_checks_context_fidelity(self):
        captured = {}
        result_value = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {
                    "requirement": "Tony respects Maya's request to keep things quiet.",
                    "status": "missing",
                    "evidence": "",
                },
                {
                    "requirement": "Tony retrieves clean pajamas from Tiffany's bedroom.",
                    "status": "missing",
                    "evidence": "",
                },
            ],
            "notes": "",
        }
        author_guidance = (
            "Recurring writing instructions:\n"
            "- Do not introduce floral scents.\n"
            "- Keep an acknowledged request for quiet consistent with later actions."
        )

        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return result_value

        with patch.object(
            scene_contract, "_run_validator", side_effect=fake_validator
        ):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {
                    "author_idea": (
                        "Maya asks Tony to keep things quiet. He agrees, then goes to "
                        "Tiffany's bedroom to retrieve clean pajamas for her."
                    ),
                    "required_beats": [],
                    "hard_stop": "Tony and Maya settle with tea.",
                },
                {"chapter": 2, "scene": 4, "current_situation": "Tony is caring for Maya."},
                "Tony agrees to keep things quiet, then plays music. He fetches pajamas from a linen closet.",
                author_guidance=author_guidance,
            )

        self.assertFalse(result["pass"])
        self.assertTrue(any("keep things quiet" in item for item in result["missed_beats"]))
        self.assertIn(author_guidance, captured["prompt"])
        self.assertIn("source locations", captured["prompt"])
        self.assertIn("explicit requests, preferences, boundaries, or needs", captured["prompt"])
        self.assertIn("Check explicit requests/preferences against later actions", scene_contract.VALIDATOR_SYSTEM_PROMPT)

    def test_max_attempts_is_safe_and_configurable(self):
        self.assertEqual(scene_contract.SceneContract.max_attempts({}), 3)
        self.assertEqual(scene_contract.SceneContract.max_attempts({"max_attempts": 99}), 5)
        self.assertEqual(scene_contract.SceneContract.max_attempts({"max_attempts": 0}), 1)

    def test_contract_lint_detects_conflicting_rules(self):
        contract = {
            "required_beats": ["The door opens."],
            "forbidden": ["The door opens."],
            "max_attempts": 3,
        }

        errors = scene_contract.SceneContract.lint(contract)

        self.assertTrue(errors)
        self.assertIn("requirement and prohibition", errors[0])

    def test_invalid_regex_is_rejected_before_generation(self):
        contract = {
            "local_hard_checks": {
                "forbidden_patterns": ["("],
            }
        }

        errors = scene_contract.SceneContract.lint(contract)
        self.assertTrue(errors)
        self.assertIn("Invalid scene contract regex", errors[0])

    def test_author_contract_ignores_active_module_merging(self):
        guidance = {
            "scene_contract": {
                "required_beats": ["Author beat"],
                "hard_stop": "Author ending.",
            }
        }
        modules = [{
            "scene_contract": {
                "required_beats": ["Module beat"],
            }
        }]

        author_contract = scene_contract.SceneContract.from_guidance(guidance, [])
        effective_contract = scene_contract.SceneContract.from_guidance(guidance, modules)

        self.assertEqual(author_contract["required_beats"], ["Author beat"])
        self.assertEqual(
            effective_contract["required_beats"],
            ["Author beat", "Module beat"],
        )

    def test_empty_contract_still_passes(self):
        result = scene_contract.SceneContract.validate_with_engine(
            FakeEngine(),
            {},
            {},
            "Any prose",
        )
        self.assertTrue(result["pass"])


    def test_generate_from_idea_preserves_labeled_author_sections(self):
        idea = """Beginning
Tony keeps comforting Maya patiently as she struggles to speak.

Middle
Maya remembers the blow and becomes upset again while Tony stays calm and reassuring.

End
Maya begins to tell Tony that the man hit her.

Required Beats
- Tony notices the visible mark on Maya's cheek and asks if she is hurt.
- Maya tells Tony that the man hit her.
"""
        generated = {
            "direction": "Tony comforts Maya patiently.",
            "hard_stop": "Tony finishes the comforting gesture.",
            "required_beats": ["AI-invented checkpoint that the author never requested."],
            "required_facts": ["This extra requirement should be ignored."],
            "required_sequence": ["This extra sequence gate should be ignored."],
            "max_attempts": 3,
        }

        with patch.object(Path, "is_file", return_value=True), patch.object(
            scene_contract, "_run_contract_builder", return_value=generated
        ):
            contract = scene_contract.SceneContract.generate_from_idea(
                "/tmp/test-model.gguf",
                {"chapter": 2, "scene": 1, "current_situation": "Tony comforts Maya."},
                idea,
            )

        self.assertEqual(
            contract["hard_stop"],
            "Maya begins to tell Tony that the man hit her.",
        )
        self.assertIn("Author-defined beginning:", contract["direction"])
        self.assertIn("Tony keeps comforting Maya patiently", contract["direction"])
        self.assertIn("Author-defined progression:", contract["direction"])
        self.assertIn("becomes upset again", contract["direction"])
        self.assertIn(
            "Tony notices the visible mark on Maya's cheek and asks if she is hurt.",
            contract["required_beats"],
        )
        self.assertIn(
            "Maya tells Tony that the man hit her.",
            contract["required_beats"],
        )
        self.assertEqual(
            len(contract["required_beats"]),
            2,
            "Only Required Beats explicitly labeled by the author should survive.",
        )
        self.assertNotIn(
            "AI-invented checkpoint that the author never requested.",
            contract["required_beats"],
        )
        self.assertNotIn("required_facts", contract)
        self.assertNotIn("required_sequence", contract)
        self.assertNotIn("forbidden", contract)
        self.assertNotIn("forbidden_details", contract)

    def test_generated_beats_are_ignored_when_idea_has_no_required_section(self):
        idea = (
            "Tony cares for Maya, invites the family to breakfast, has a private "
            "moment with Barnaby, and ends quietly with tea at the kitchen table."
        )
        generated = {
            "direction": "Tony moves through the evening's care routines.",
            "hard_stop": "Tony and Maya sit together at the kitchen table.",
            "required_beats": [
                "Tony opens the bathroom cabinet before calling Beth.",
                "Tony uses the exact phrase the validator expected.",
                "Tony hugs Barnaby for exactly two sentences.",
            ],
            "max_attempts": 3,
        }

        with patch.object(Path, "is_file", return_value=True), patch.object(
            scene_contract, "_run_contract_builder", return_value=generated
        ):
            contract = scene_contract.SceneContract.generate_from_idea(
                "/tmp/test-model.gguf",
                {"chapter": 2, "scene": 4, "current_situation": "Tony is with Maya."},
                idea,
            )

        self.assertEqual(contract["required_beats"], [])

    def test_saved_generated_beats_do_not_override_plain_english_scene_idea(self):
        idea = (
            "Tony offers Maya a bath, calls the family about breakfast, spends a "
            "private moment with Barnaby, and ends with tea at the kitchen table."
        )
        guidance = {
            "scene_idea": idea,
            "direction": "Tony takes care of Maya.",
            "end_condition": "End at the kitchen table.",
            "scene_contract": {
                "required_beats": [
                    "The AI-generated bath beat with added subdetails.",
                    "The AI-generated phone call beat with an exact required sequence.",
                    "The AI-generated Barnaby beat with extra gestures.",
                    "The AI-generated tea beat with a mandated phrase.",
                ],
                "hard_stop": "End at the kitchen table.",
                "max_attempts": 3,
            },
        }

        contract = scene_contract.SceneContract.from_guidance(guidance)

        self.assertEqual(contract["required_beats"], [])
        self.assertEqual(contract["hard_stop"], "End at the kitchen table.")
        self.assertEqual(contract["author_idea"], idea)

    def test_saved_contract_keeps_only_author_labeled_required_beats(self):
        idea = (
            "Beginning: The driver leaves California.\n\n"
            "End: The driver arrives in New York.\n\n"
            "Required Beats\n"
            "- Stop in Denver.\n"
            "- Stop in Chicago.\n"
        )
        guidance = {
            "scene_idea": idea,
            "scene_contract": {
                "required_beats": [
                    "Stop in Denver.",
                    "Stop in Chicago.",
                    "AI-invented stop in Nebraska.",
                ],
                "hard_stop": "New York.",
            },
        }

        contract = scene_contract.SceneContract.from_guidance(guidance)

        self.assertEqual(contract["required_beats"], ["Stop in Denver.", "Stop in Chicago."])
        self.assertNotIn("AI-invented stop in Nebraska.", contract["required_beats"])

    def test_live_writer_engine_is_reused_for_contract_build(self):
        generated = {
            "direction": "Tony comforts Maya.",
            "hard_stop": "They reach the kitchen table.",
            "required_beats": ["Tony offers Maya a warm bubble bath."],
            "required_facts": ["Ignore auxiliary facts."],
            "required_sequence": ["Ignore auxiliary sequence."],
            "max_attempts": 3,
        }

        class LiveEngine:
            class Child:
                def isalive(self):
                    return True

            def __init__(self):
                self.child = self.Child()
                self.model_path = Path("/tmp/test-model.gguf")
                self.calls = []

            def reset_context(self, model, system_prompt):
                self.calls.append(("reset", str(model), system_prompt,
                    os.environ.get("STORY_WRITER_CONTEXT"),
                    os.environ.get("STORY_WRITER_MAX_TOKENS")))

            def generate(self, prompt, timeout=None):
                self.calls.append(("generate", prompt, timeout))
                return json.dumps(generated)

        engine = LiveEngine()
        old_context = os.environ.get("STORY_WRITER_CONTEXT")
        old_tokens = os.environ.get("STORY_WRITER_MAX_TOKENS")
        with patch.object(Path, "is_file", return_value=True):
            contract = SceneContract.generate_from_idea(
                "/tmp/test-model.gguf",
                {"chapter": 2, "scene": 4, "current_situation": "Maya is with Tony."},
                "Tony comforts Maya and offers a warm bubble bath. End when they sit together at the kitchen table.",
                engine=engine,
            )

        self.assertEqual(len(engine.calls), 2)
        self.assertEqual(engine.calls[0][3], "6144")
        self.assertEqual(engine.calls[0][4], "700")
        self.assertEqual(engine.calls[1][2], 300)
        self.assertNotIn("required_facts", contract)
        self.assertNotIn("required_sequence", contract)
        self.assertNotIn("forbidden", contract)
        self.assertNotIn("forbidden_details", contract)
        # Model-generated beats are suggestions, not mandatory author beats.
        self.assertEqual(contract["required_beats"], [])
        self.assertEqual(os.environ.get("STORY_WRITER_CONTEXT"), old_context)
        self.assertEqual(os.environ.get("STORY_WRITER_MAX_TOKENS"), old_tokens)

    def test_live_writer_engine_is_reused_for_validation(self):
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
        }

        class LiveEngine:
            class Child:
                def isalive(self):
                    return True

            def __init__(self):
                self.child = self.Child()
                self.model_path = Path("/tmp/test-model.gguf")
                self.calls = []

            def reset_context(self, model, system_prompt):
                self.calls.append(("reset", system_prompt,
                    os.environ.get("STORY_WRITER_CONTEXT"),
                    os.environ.get("STORY_WRITER_MAX_TOKENS")))

            def generate(self, prompt, timeout=None):
                self.calls.append(("generate", prompt, timeout))
                return json.dumps(validator_result)

        engine = LiveEngine()
        old_context = os.environ.get("STORY_WRITER_CONTEXT")
        old_tokens = os.environ.get("STORY_WRITER_MAX_TOKENS")
        result = SceneContract.validate_with_engine(
            engine,
            self.contract,
            {
                "chapter": 2,
                "scene": 1,
                "current_situation": "Tony and Maya are together.",
                "physical_state": {"Tony": {"position": "sitting on the bed"}},
                "unrelated_archive_blob": "Do not send old archive data to validation.",
            },
            "Tony and Maya are together.",
        )

        self.assertTrue(result["pass"])
        self.assertEqual(engine.calls[0][2], "6144")
        self.assertEqual(engine.calls[0][3], "1500")
        self.assertEqual(engine.calls[1][2], 300)
        self.assertIn("sitting on the bed", engine.calls[1][1])
        self.assertNotIn("unrelated_archive_blob", engine.calls[1][1])
        self.assertEqual(os.environ.get("STORY_WRITER_CONTEXT"), old_context)
        self.assertEqual(os.environ.get("STORY_WRITER_MAX_TOKENS"), old_tokens)


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builder import scene_contract
from builder.scene_contract import (
    SceneContract,
    SceneContractResponseError,
    SceneContractValidationUnavailable,
    extract_authored_scene_sections,
    extract_scene_header_metadata,
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

    def test_compound_end_hard_stop_label_is_extracted_as_author_ending(self):
        idea = """Breakfast disclosure and the first offers to help

**Beginning:**
- Tony prepares breakfast and gently wakes Maya.

**Middle: The disclosure and the first response**
- Tony tells the group what happened and they begin discussing how to help.

**End / HARD STOP:** End after the group begins sketching basic roles for the private search. Leave detailed assignments and the rescue plan for later scenes. No one calls the police.

Preserve all established character roles and knowledge boundaries; do not invent new clues.
"""
        sections = extract_authored_scene_sections(idea)

        self.assertTrue(sections["end"].startswith("End after the group begins sketching basic roles"))
        self.assertIn("No one calls the police.", sections["end"])
        self.assertNotIn("Preserve all established character roles", sections["end"])
        self.assertNotIn("**", sections["end"])
        self.assertNotIn("Tony prepares breakfast", sections["end"])
        self.assertNotIn("Tony tells the group", sections["end"])
        self.assertNotIn("HARD STOP", sections["middle"])

    def test_explicit_author_hard_stop_overrides_model_repeating_whole_idea(self):
        idea = """Breakfast disclosure and the first offers to help

**Beginning:**
- Tony prepares breakfast and gently wakes Maya.

**Middle: The disclosure and the first response**
- Tony tells the group what happened and they begin discussing how to help.

**End / HARD STOP:** End after the group begins sketching basic roles for the private search. Leave detailed assignments and the rescue plan for later scenes. No one calls the police.

Preserve all established character roles and knowledge boundaries; do not invent new clues.
"""
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp, "writer.gguf")
            model_path.write_text("test fixture", encoding="utf-8")
            # Reproduce the failure mode: the model echoes the entire idea as
            # its hard_stop instead of returning a concise endpoint.
            raw_result = {
                "direction": "Move from breakfast to disclosure, then initial roles.",
                "hard_stop": idea,
                "required_beats": [],
                "max_attempts": 3,
            }
            with patch.object(
                scene_contract, "_run_contract_builder", return_value=raw_result
            ):
                result = SceneContract.generate_from_idea(
                    model_path,
                    {"chapter": 3, "scene": 2, "current_situation": "Daybreak at Tony's home."},
                    idea,
                )

        self.assertIn("End after the group begins sketching basic roles", result["hard_stop"])
        self.assertIn("No one calls the police.", result["hard_stop"])
        self.assertNotIn("Preserve all established character roles", result["hard_stop"])
        self.assertNotIn("**", result["hard_stop"])
        self.assertNotIn("Tony prepares breakfast", result["hard_stop"])
        self.assertNotIn("Tony tells the group", result["hard_stop"])

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

    def test_semantic_validator_can_use_a_separate_model_path(self):
        prose = "A man waves."
        validator_model = Path("/tmp/secondary-checker.gguf")
        captured = {}
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {
                    "requirement": "Someone waves.",
                    "status": "met",
                    "evidence": "A man waves.",
                }
            ],
            "notes": "",
        }

        def fake_validator(model, _prompt):
            captured["model"] = model
            return validator_result

        with patch.object(scene_contract, "_run_validator", side_effect=fake_validator):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                dict(self.contract, author_idea="Someone waves."),
                {"chapter": 1, "scene": 1},
                prose,
                model_path=validator_model,
            )

        self.assertTrue(result["pass"], result)
        self.assertEqual(captured["model"], validator_model)

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

    def test_shared_contract_prompts_are_genre_neutral(self):
        prompts = (
            scene_contract.CONTRACT_BUILDER_SYSTEM_PROMPT,
            scene_contract.VALIDATOR_SYSTEM_PROMPT,
            SceneContract.writer_prompt_context(
                "Saved starting-state summary (verify historical claims).",
                {"author_idea": "A crew gathers to decide its next safe step."},
            ),
        )
        for prompt in prompts:
            lowered = prompt.casefold()
            for story_specific_term in ("bubble bath", "abduction", "tiffany", "barnaby"):
                self.assertNotIn(story_specific_term, lowered)
        context = prompts[2].casefold()
        self.assertIn("distinguish established facts from speculation", context)
        self.assertIn("must not overrule or contradict the author's intent", context)

    def test_validator_treats_required_beats_as_narrative_goals(self):
        prompt = scene_contract.VALIDATOR_SYSTEM_PROMPT
        self.assertIn("Judge meaning, not keywords", prompt)
        self.assertIn("A check is met only when its main action and defining details are present", prompt)
        self.assertIn("Do not accept a superficially similar substitute for a specifically requested action or object", prompt)
        self.assertIn("preserve the author's defining details", prompt)
        self.assertIn('"checks": [{"requirement": "", "status": "met", "evidence": ""}]', prompt)
        self.assertIn("Evidence is optional diagnostic text from COMPLETED SCENE only", prompt)
        self.assertIn("COMPLETED SCENE only", prompt)
        self.assertIn("never quote the idea, instructions, contract", prompt)
        self.assertIn("Preserve stated backstory", prompt)
        self.assertIn("a different action, object, person, order, or outcome is not", prompt)
        self.assertIn("Create a SHORT EVENT-LEVEL checklist, usually 4–8 checks total", prompt)
        self.assertIn("Group related details from the same event", prompt)
        self.assertIn("Ignore incidental details unless the idea makes them defining", prompt)
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
            "Treat Planned Beats and Required Beats as narrative-level goals, not a word-for-word checklist",
            captured["prompt"],
        )
        self.assertIn(
            "If the main action occurs but only a purely incidental detail is missing, do not fail for that alone",
            captured["prompt"],
        )
        self.assertIn(
            "Replacing a specifically requested action or object with a superficially similar substitute is a material change",
            captured["prompt"],
        )
        self.assertIn(
            "Search the whole scene for paraphrases before marking missing",
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

    def test_many_missing_checks_get_semantic_recheck_in_small_batches(self):
        requirements = [
            "A red car is present.",
            "Tony sits on the porch.",
            "Maya gives a nod.",
            "Beth calls before sunset.",
            "Jessica confirms she will come.",
            "A kettle boils.",
            "The rain stops.",
            "The door closes.",
        ]
        prose = (
            "A maroon sedan waited by the gate. Tony sat on the porch. Maya nodded once. "
            "Beth called before sunset. Jessica confirmed she would come. The kettle boiled. "
            "The rain stopped. The door clicked shut."
        )
        first_pass = {
            "pass": False,
            "missed_beats": requirements.copy(),
            "violations": [],
            "checks": [
                {"requirement": requirement, "status": "missing", "evidence": ""}
                for requirement in requirements
            ],
            "notes": "",
        }
        first_batch = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {"requirement": requirements[0], "status": "met", "evidence": "A maroon sedan waited by the gate."},
                {"requirement": requirements[1], "status": "met", "evidence": "Tony sat on the porch."},
                {"requirement": requirements[2], "status": "met", "evidence": "Maya nodded once."},
                {"requirement": requirements[3], "status": "met", "evidence": "Beth called before sunset."},
                {"requirement": requirements[4], "status": "met", "evidence": "Jessica confirmed she would come."},
                {"requirement": requirements[5], "status": "met", "evidence": "The kettle boiled."},
            ],
            "notes": "",
        }
        second_batch = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {"requirement": requirements[6], "status": "met", "evidence": "The rain stopped."},
                {"requirement": requirements[7], "status": "met", "evidence": "The door clicked shut."},
            ],
            "notes": "",
        }

        with patch.object(
            scene_contract,
            "_run_validator",
            side_effect=[first_pass, first_batch, second_batch],
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": "The scene contains the listed actions and details.", "required_beats": []},
                {"chapter": 1, "scene": 1},
                prose,
            )

        self.assertTrue(result["pass"], result)
        self.assertEqual(result["missed_beats"], [])
        self.assertEqual(run_validator.call_count, 3)
        self.assertIn("red car", run_validator.call_args_list[1].args[1])
        self.assertIn("maroon sedan", run_validator.call_args_list[1].args[1])
        self.assertIn("Judge meaning, not keyword overlap", run_validator.call_args_list[1].kwargs["system_prompt"])


    def test_short_event_checklist_is_rechecked_when_most_items_are_missing(self):
        requirements = [
            "Maya takes a bath.",
            "Tony makes the breakfast calls.",
            "Tony retrieves clothes and picks up Barnaby.",
            "Tony and Maya end with tea at the kitchen table.",
        ]
        prose = (
            "Maya settled into the bath. Tony called Beth, then Jessica, about breakfast. "
            "He retrieved the clean clothes and picked up Barnaby. Later, they settled "
            "at the kitchen table with chamomile tea."
        )
        first_pass = {
            "pass": False,
            "missed_beats": requirements.copy(),
            "violations": [],
            "checks": [
                {"requirement": item, "status": "missing", "evidence": ""}
                for item in requirements
            ],
            "notes": "",
        }
        second_pass = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {"requirement": requirements[0], "status": "met", "evidence": "Maya settled into the bath."},
                {"requirement": requirements[1], "status": "met", "evidence": "Tony called Beth, then Jessica, about breakfast."},
                {"requirement": requirements[2], "status": "met", "evidence": "He retrieved the clean clothes and picked up Barnaby."},
                {"requirement": requirements[3], "status": "met", "evidence": "they settled at the kitchen table with chamomile tea."},
            ],
            "notes": "",
        }

        with patch.object(
            scene_contract, "_run_validator", side_effect=[first_pass, second_pass]
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": "The scene includes these four events.", "required_beats": []},
                {"chapter": 2, "scene": 4},
                prose,
            )

        self.assertTrue(result["pass"], result)
        self.assertEqual(result["missed_beats"], [])
        self.assertEqual(run_validator.call_count, 2)
        self.assertIn("SEMANTIC COVERAGE RECHECK", run_validator.call_args_list[1].args[1])


    def test_common_model_status_variants_normalize_to_missing(self):
        self.assertEqual(scene_contract._normalize_check_status("not met"), "missing")
        self.assertEqual(scene_contract._normalize_check_status("NOT_MET"), "missing")
        self.assertEqual(scene_contract._normalize_check_status("missed"), "missing")
        self.assertEqual(scene_contract._normalize_check_status("partially met"), "missing")
        self.assertEqual(scene_contract._normalize_check_status("present"), "met")
        self.assertEqual(scene_contract._normalize_check_status("Satisfied"), "met")
        self.assertIsNone(scene_contract._normalize_check_status("unclear"))

    def test_model_status_variants_do_not_bypass_missing_event_validation(self):
        idea = "Maya takes a bath, and Tony makes tea."
        prose = "Maya settled into the bath. Tony made tea."
        raw_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {"requirement": "Maya takes a bath.", "status": "present", "evidence": "Maya settled into the bath."},
                {"requirement": "Tony makes tea.", "status": "not met", "evidence": ""},
                {"requirement": "A third event happens.", "status": "missed", "evidence": "unsupported quote"},
            ],
            "notes": "",
        }

        with patch.object(scene_contract, "_run_validator", return_value=raw_result):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 1, "scene": 1},
                prose,
            )

        self.assertFalse(result["pass"])
        self.assertTrue(any("Tony makes tea" in item for item in result["missed_beats"]))
        self.assertTrue(any("A third event happens" in item for item in result["missed_beats"]))
        self.assertTrue(result["missed_beats"][0].endswith("Tony makes tea."))
        self.assertTrue(result["missed_beats"][1].endswith("A third event happens."))

    def test_missing_checks_do_not_duplicate_existing_missed_beats(self):
        idea = "Tony helps Maya settle and makes her tea."
        raw_result = {
            "pass": False,
            "missed_beats": ["Tony helps Maya settle.", "Tony makes her tea."],
            "violations": [],
            "checks": [
                {"requirement": "Tony helps Maya settle.", "status": "missing", "evidence": ""},
                {"requirement": "Tony makes her tea.", "status": "missing", "evidence": ""},
            ],
            "notes": "",
        }
        with patch.object(scene_contract, "_run_validator", return_value=raw_result):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 1, "scene": 1},
                "Tony helped Maya settle. Tony made her tea.",
            )
        self.assertEqual(result["missed_beats"], raw_result["missed_beats"])

    def test_invalid_evidence_does_not_trigger_retry(self):
        idea = "Tony offers Maya a warm bubble bath and gives her privacy."
        prose = "Tony offered Maya a warm bath, then left the room to give her privacy."
        raw = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [{
                "requirement": "Tony offers Maya a warm bath.",
                "status": "met",
                "evidence": "An explanation that is not copied from the scene.",
            }],
            "notes": "",
        }
        with patch.object(
            scene_contract, "_run_validator", return_value=raw
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 2, "scene": 4},
                prose,
            )
        self.assertTrue(result["pass"], result)
        self.assertEqual(run_validator.call_count, 1)

    def test_missing_event_still_fails_with_invalid_evidence_elsewhere(self):
        idea = "Elena gathers Morgan and gives clear next steps."
        prose = "Morgan entered. Elena reviewed the situation."
        raw = {
            "pass": False,
            "missed_beats": ["Elena gives clear next steps."],
            "violations": [],
            "checks": [
                {"requirement": "Elena gathers Morgan.", "status": "met",
                 "evidence": "A paraphrase not copied from the draft."},
                {"requirement": "Elena gives clear next steps.", "status": "missing",
                 "evidence": ""},
            ],
            "notes": "",
        }
        with patch.object(
            scene_contract, "_run_validator", return_value=raw
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 1, "scene": 3},
                prose,
            )
        self.assertFalse(result["pass"], result)
        self.assertTrue(result["missed_beats"], result)
        self.assertEqual(run_validator.call_count, 1)

    def test_schema_correction_does_not_require_evidence_retry(self):
        idea = "Tony offers Maya a warm bath and gives her privacy."
        prose = "Tony offered Maya a warm bath, then left the room."
        raw = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [{
                "requirement": idea,
                "status": "met",
                "evidence": "Evidence phrased differently from the prose.",
            }],
            "notes": "",
        }
        with patch.object(
            scene_contract,
            "_run_validator",
            side_effect=[
                SceneContractResponseError("invalid 'pass' value"),
                raw,
            ],
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 2, "scene": 4},
                prose,
            )
        self.assertTrue(result["pass"], result)
        self.assertEqual(run_validator.call_count, 2)
        self.assertIn("CORRECTION REQUIRED", run_validator.call_args_list[1].args[1])

    def test_invalid_evidence_does_not_make_validation_unavailable(self):
        idea = "Tony offers Maya a warm bubble bath and gives her privacy."
        prose = "Tony offered Maya a warm bath, then left the room to give her privacy."
        raw = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [{
                "requirement": idea,
                "status": "met",
                "evidence": "A paraphrased explanation that is not present verbatim.",
            }],
            "notes": "",
        }
        with patch.object(
            scene_contract, "_run_validator", return_value=raw
        ) as run_validator:
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "required_beats": []},
                {"chapter": 2, "scene": 4},
                prose,
            )
        self.assertTrue(result["pass"], result)
        self.assertEqual(run_validator.call_count, 1)

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
            "Avery checks the kitchen tap, calls Jordan about repair supplies, "
            "and asks Casey to meet tomorrow."
        )
        guidance = "\n".join([
            "- Unrelated guidance about distant plot arcs.",
            "- Avery prefers quiet rooms when making difficult calls.",
            "- Only characters explicitly listed in the scene cast participate.",
            "- Do not import details from discarded drafts.",
            "- Keep action sentences short during tense moments.",
        ] + [
            "- Unrelated guidance about distant plot arcs and background lore."
            for _ in range(20)
        ])
        compact_guidance = scene_contract._compact_validator_guidance(
            guidance, idea, ["Avery", "Jordan"]
        )
        self.assertLessEqual(len(compact_guidance), 1600)
        self.assertIn("Only characters explicitly listed", compact_guidance)
        self.assertIn("Do not import details from discarded drafts", compact_guidance)
        self.assertNotIn("distant plot arcs", compact_guidance)

        state = {
            "chapter": 2,
            "scene": 4,
            "scene_cast": ["Avery", "Jordan"],
            "current_situation": "Avery is checking a leaking kitchen tap.",
            "location": {
                "primary": "Home kitchen",
                "Avery": "In the kitchen",
                "Jordan": "At the hardware store",
                "Casey": "At work",
            },
            "physical_state": {
                "Avery": {"position": "standing at the sink"},
                "Jordan": {"position": "at the hardware store"},
                "Casey": {"position": "at work"},
            },
            "character_knowledge": {
                "Avery": ["Knows the tap is leaking."],
                "Jordan": ["Received a call about supplies."],
                "Casey": ["Has not yet been contacted."],
            },
            "active_objectives": {
                "Avery": "Arrange a repair",
                "Jordan": "Find the necessary supplies",
            },
            "unrelated_history": "Do not send this to the validator.",
        }
        compact_state = scene_contract._compact_validation_state(
            state, ["Avery", "Jordan"], idea
        )
        self.assertIn("Avery", compact_state["character_knowledge"])
        self.assertIn("Jordan", compact_state["character_knowledge"])
        self.assertNotIn("Casey", compact_state["character_knowledge"])
        self.assertNotIn("unrelated_history", compact_state)
        self.assertIn("Casey", compact_state["location"])
        self.assertIn("Casey", compact_state["physical_state"])

        captured = {}
        prose = "Avery inspected the tap. Jordan said he could bring supplies later."
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
            "checks": [
                {
                    "requirement": "Avery inspects the tap.",
                    "status": "met",
                    "evidence": "Avery inspected the tap.",
                }
            ],
        }

        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return validator_result

        with patch.object(scene_contract, "_run_validator", side_effect=fake_validator):
            SceneContract.validate_with_engine(
                FakeEngine(),
                {"author_idea": idea, "direction": "Arrange a repair and end after the call."},
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
        self.assertIn("Only characters explicitly listed in the scene cast participate.", prompt)
        self.assertNotIn("unrelated_history", prompt)

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
        self.assertIn("concise non-empty event checklist", retry_prompt)
        self.assertIn("4-8 meaningful scene events", retry_prompt)
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
            "Replacing a specifically requested action or object with a superficially similar substitute is a material change",
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
        self.assertLess(
            len(writer_context),
            len(idea) + len("Chapter 2, Scene 4. Maya is curled against Tony on the bed.") + 3000,
            "Scene boilerplate must stay compact instead of duplicating global Writer rules.",
        )
        self.assertIn("AUTHOR'S ORIGINAL PLAIN-ENGLISH SCENE IDEA (PRIMARY INTENT):", writer_context)
        self.assertIn(idea, writer_context)
        self.assertIn("COMPACT SUPPORTING CONTRACT (SECONDARY):", writer_context)
        self.assertIn("AUTHOR ACTION FIDELITY", writer_context)
        self.assertIn("do not substitute a merely similar action or object", writer_context)
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
        self.assertIn("SCENE SCOPE AND EVENT PROVENANCE", writer_context)
        self.assertIn("concise direction must not shrink it", writer_context)
        self.assertIn("Present sights, sounds, dialogue, or actions as personal memory only when witnessed", writer_context)
        self.assertIn("attribute second-hand information", writer_context)
        self.assertIn("SCENE PROGRESSION AND SCOPE", writer_context)
        self.assertIn("does not automatically authorize", writer_context)
        self.assertIn("Treat the explicit endpoint as a ceiling", writer_context)
        self.assertIn(
            "If an explicit endpoint is named, including a time or passage-of-time boundary, carry the scene through to it",
            writer_context,
        )
        self.assertIn(
            "Use a natural stopping point only when the idea leaves the endpoint open",
            writer_context,
        )
        self.assertIn(
            "When the idea gives a clear endpoint, put that endpoint in hard_stop",
            scene_contract.CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn("temporal boundary", scene_contract.CONTRACT_BUILDER_SYSTEM_PROMPT)

    def test_validator_receives_original_plain_english_idea(self):
        idea = (
            "Tony offers Maya a warm bubble bath, makes the breakfast calls without revealing "
            "the abduction, returns Barnaby to Tiffany's room, and ends at the kitchen table "
            "with chamomile tea."
        )
        captured = {"prompts": []}

        def fake_validator(_model, prompt, **kwargs):
            captured["prompts"].append(prompt)
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
        self.assertIn(idea, captured["prompts"][0])
        self.assertNotIn('"author_idea"', captured["prompts"][0])
        self.assertIn("Prioritize the idea over generated hints", captured["prompts"][0])
        self.assertIn('"checks": [{"requirement": "", "status": "met", "evidence": ""}]', captured["prompts"][0])
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
        self.assertIn("Check acknowledged requests/preferences against later actions", scene_contract.VALIDATOR_SYSTEM_PROMPT)

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


    def test_extract_scene_header_metadata_preserves_authored_time_and_location(self):
        idea = """Breakfast disclosure and the first offers to help

**Scene header:**

CHAPTER 3, SCENE 2
Location: Tony's home
Time: Saturday morning at daybreak

**Starting point:** Continue after Scene 1.
Later in the idea, someone might mention the time in a sentence.
"""
        self.assertEqual(
            extract_scene_header_metadata(idea),
            {"location": "Tony's home", "time": "Saturday morning at daybreak"},
        )

    def test_extract_scene_header_metadata_does_not_infer_from_body_text(self):
        idea = """Tony prepares breakfast at daybreak.
The story's location is Tony's home."""
        self.assertEqual(extract_scene_header_metadata(idea), {})


    def test_planned_beats_and_boundaries_become_structured_author_constraints(self):
        idea = """Forming the Private Effort

**Purpose:** Transition from the initial shock to a preliminary private effort.

**Starting Point:** Immediately after the group commits to helping find Tiffany.

**Planned Beats:**
* **Emotional Connection:** Tony shares a long, emotional hug with Chloe, sincerely thanks her, and calls her "my little wildcat" for the first time; Chloe accepts the nickname.
* **Shifting Focus:** The conversation naturally turns toward forming a preliminary private approach to locating Tiffany.
* **Skill Integration:** Jessica's technical expertise, Beth's community connections, and Rick's practical military/logistical thinking emerge organically.
* **Group Input:** Maya and Chloe contribute meaningful perspectives suited to their current abilities.
* **Tentative Roles:** Tony gently connects the ideas into broad, tentative roles without finalizing assignments.

**Hard Stop:** End when the rough framework for the private effort begins to take shape among the group.

**Boundaries:** Do not introduce new clues, identify the kidnapper or a buyer, or call the police. Do not finalize assignments or begin detailed investigation, training, or rescue planning. Maya and Chloe must contribute meaningful ideas suited to their current abilities.
"""
        sections = extract_authored_scene_sections(idea)
        self.assertEqual(len(sections["required_beats"]), 5)
        self.assertIn("my little wildcat", sections["required_beats"][0])
        self.assertIn("Tony gently connects", sections["required_beats"][4])
        self.assertEqual(len(sections["boundaries"]), 1)
        self.assertIn("call the police", sections["boundaries"][0])

        generated = {
            "direction": "Move toward the preliminary framework.",
            "hard_stop": "A model-generated stop that must be replaced.",
            "required_beats": ["Model-invented beat must be ignored."],
            "max_attempts": 3,
        }
        with patch.object(Path, "is_file", return_value=True), patch.object(
            scene_contract, "_run_contract_builder", return_value=generated
        ):
            contract = SceneContract.generate_from_idea(
                "/tmp/test-model.gguf",
                {"chapter": 3, "scene": 3, "current_situation": "The group has committed to help."},
                idea,
            )

        self.assertEqual(contract["required_beats"], sections["required_beats"])
        self.assertEqual(contract["boundaries"], sections["boundaries"])
        self.assertIn("rough framework for the private effort begins", contract["hard_stop"])
        self.assertNotIn("Model-invented beat must be ignored.", contract["required_beats"])

    def test_boundaries_survive_saved_guidance_and_reach_writer_and_validator(self):
        idea = """Scene 3

**Planned Beats:**
- Tony thanks Chloe and calls her "my little wildcat".
- The group begins identifying broad, tentative roles.

**Hard Stop:** End as the rough framework begins to take shape.

**Boundaries:** Do not identify the kidnapper. Do not call the police. Do not begin rescue planning.
"""
        guidance = {
            "scene_idea": idea,
            "direction": "The group is at Tony's home.",
            "scene_contract": {
                "required_beats": ["Old model-generated beat must be replaced."],
                "hard_stop": "Old stop must be replaced.",
                "max_attempts": 3,
            },
        }
        contract = SceneContract.from_guidance(guidance)
        self.assertEqual(
            contract["required_beats"],
            [
                'Tony thanks Chloe and calls her "my little wildcat".',
                "The group begins identifying broad, tentative roles.",
            ],
        )
        self.assertEqual(
            contract["boundaries"],
            ["Do not identify the kidnapper. Do not call the police. Do not begin rescue planning."],
        )
        writer_context = SceneContract.writer_prompt_context("Current scene context.", contract)
        self.assertIn("AUTHOR-DEFINED BOUNDARIES (MANDATORY)", writer_context)
        self.assertIn("Do not identify the kidnapper.", writer_context)
        self.assertIn("Do not call the police.", writer_context)
        self.assertIn("Preserve beat direction and agency", writer_context)
        self.assertIn("Distinguish established facts from speculation", writer_context)
        self.assertIn("Do not add forbidden facts or unsupported consequential events", writer_context)

        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "checks": [
                {
                    "requirement": "Tony thanks Chloe.",
                    "status": "met",
                    "evidence": 'Tony thanked Chloe and called her "my little wildcat".',
                }
            ],
            "notes": "",
        }
        captured = {}
        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return validator_result

        with patch.object(scene_contract, "_run_validator", side_effect=fake_validator):
            result = SceneContract.validate_with_engine(
                FakeEngine(),
                contract,
                {"chapter": 3, "scene": 3, "scene_cast": ["Tony", "Chloe"]},
                'Tony thanked Chloe and called her "my little wildcat".',
            )
        self.assertTrue(result["pass"], result)
        self.assertIn('"boundaries"', captured["prompt"])
        self.assertIn("Do not identify the kidnapper.", captured["prompt"])
        self.assertIn("Do not begin rescue planning.", captured["prompt"])

if __name__ == "__main__":
    unittest.main()

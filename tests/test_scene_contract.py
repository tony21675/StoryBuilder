import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from builder import scene_contract
from builder.scene_contract import SceneContract


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
        prose = "A valid creative scene."
        validator_result = {
            "pass": True,
            "missed_beats": [],
            "violations": [],
            "notes": "",
        }
        captured = {}

        def fake_validator(model, prompt):
            captured["model"] = model
            captured["prompt"] = prompt
            return validator_result

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
        self.assertLess(len(captured["prompt"]), 2500)
        self.assertLess(len(scene_contract.VALIDATOR_SYSTEM_PROMPT), 800)


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
        self.assertNotIn("Rewrite the scene from the beginning", prompt)

    def test_validator_prompt_distinguishes_required_beats_from_incidental_details(self):
        self.assertIn("Judge the whole scene, not incidental details", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("Every item in required_beats is mandatory", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("set pass=false", scene_contract.VALIDATOR_SYSTEM_PROMPT)
        self.assertIn("Ignore incidental omissions from free-form prose", scene_contract.VALIDATOR_SYSTEM_PROMPT)

    def test_validator_checks_whole_scene_before_calling_a_beat_missing(self):
        prompt = scene_contract.VALIDATOR_SYSTEM_PROMPT
        self.assertIn(
            "Search the whole scene for each beat's equivalent action",
            prompt,
        )
        self.assertIn(
            "If an action occurs but a detail is missing, report only that detail, not the beat as absent.",
            prompt,
        )
        self.assertLess(len(prompt), 800)


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
        self.assertIn("not as a line-by-line checklist", writer_context)
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

        self.assertTrue(result["pass"])
        self.assertIn(idea, captured["prompt"])
        self.assertIn('"author_idea"', captured["prompt"])
        self.assertIn("The idea is primary", captured["prompt"])
        self.assertIn("original idea", scene_contract.VALIDATOR_SYSTEM_PROMPT)

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
            "required_beats": [],
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
        self.assertNotIn("required_facts", contract)
        self.assertNotIn("required_sequence", contract)
        self.assertNotIn("forbidden", contract)
        self.assertNotIn("forbidden_details", contract)

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
        self.assertEqual(contract["required_beats"], ["Tony offers Maya a warm bubble bath."])
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
        self.assertEqual(engine.calls[0][3], "220")
        self.assertEqual(engine.calls[1][2], 300)
        self.assertIn("sitting on the bed", engine.calls[1][1])
        self.assertNotIn("unrelated_archive_blob", engine.calls[1][1])
        self.assertEqual(os.environ.get("STORY_WRITER_CONTEXT"), old_context)
        self.assertEqual(os.environ.get("STORY_WRITER_MAX_TOKENS"), old_tokens)


if __name__ == "__main__":
    unittest.main()

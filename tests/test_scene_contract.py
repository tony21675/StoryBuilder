import unittest
from pathlib import Path
from unittest.mock import patch

from builder import scene_contract


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

        with patch.object(scene_contract, "_run_validator", side_effect=fake_validator):
            result = scene_contract.SceneContract.validate_with_engine(
                engine,
                self.contract,
                {"chapter": 2, "scene": 1, "current_situation": "Tony and Maya are together."},
                prose,
            )

        self.assertEqual(result, validator_result)
        self.assertEqual(captured["model"], engine.model_path)
        self.assertIn("required_beats", captured["prompt"])
        self.assertIn("hard_stop", captured["prompt"])
        self.assertNotIn('"local_hard_checks"', captured["prompt"])
        self.assertNotIn("Old wording gate", captured["prompt"])

    def test_empty_contract_still_passes(self):
        result = scene_contract.SceneContract.validate_with_engine(
            FakeEngine(),
            {},
            {},
            "Any prose",
        )
        self.assertTrue(result["pass"])


if __name__ == "__main__":
    unittest.main()

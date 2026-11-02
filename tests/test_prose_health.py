import unittest

from builder.prose_health import analyze_draft, format_draft_health_report


class ProseHealthTests(unittest.TestCase):
    def test_empty_draft_has_no_findings(self):
        self.assertEqual(analyze_draft(" \\n\\n"), [])

    def test_finds_identical_substantial_paragraphs(self):
        paragraph = (
            "The old station lights flickered above the empty corridor while the "
            "recycler pushed cold air through the ventilation grates."
        )
        findings = analyze_draft(paragraph + "\\n\\nA distinct paragraph separates them.\\n\\n" + paragraph)
        self.assertTrue(any(f.category == "Duplicate paragraph" for f in findings))

    def test_finds_duplicate_complete_sentence(self):
        sentence = (
            "The station lights flickered above the empty corridor while the recycler "
            "pushed cold air through the ventilation grates."
        )
        text = (
            f"{sentence} Aris checked the display again.\\n\\n"
            "A different paragraph introduces another moment in the scene.\\n\\n"
            f"{sentence} The signal continued without changing."
        )
        self.assertTrue(any(f.category == "Duplicate sentence" for f in analyze_draft(text)))

    def test_short_dialogue_fragments_are_ignored(self):
        findings = analyze_draft('"Run!"\\n\\nShe turned away.\\n\\n"Run!"')
        self.assertFalse(any(f.category in {"Duplicate sentence", "Duplicate paragraph"} for f in findings))

    def test_finds_repeated_distinctive_phrase(self):
        text = (
            "The silver dust settled across the control panel, and Aris looked away. "
            "Later, the silver dust settled across the control panel as alarms began. "
            "By dawn, the silver dust settled across the control panel once again."
        )
        self.assertTrue(any(f.category == "Repeated phrase" for f in analyze_draft(text)))

    def test_ignores_short_dialogue_refrain(self):
        text = (
            '"Come back," she said. He did not answer. '
            '"Come back," she said again. The room remained silent. '
            '"Come back," she whispered.'
        )
        self.assertFalse(any(f.category == "Repeated phrase" for f in analyze_draft(text)))

    def test_detects_clear_abrupt_ending_and_unmatched_bracket(self):
        self.assertTrue(any(f.category == "Possible abrupt ending" for f in analyze_draft("He reached for the switch, but")))
        self.assertTrue(any(f.category == "Possible truncation" for f in analyze_draft("She opened the panel (")))

    def test_detects_ai_preamble_and_closing_but_not_natural_dialogue(self):
        opening = analyze_draft("Certainly! Here is your scene.\\n\\nAris entered the room.")
        closing = analyze_draft("Aris left the room.\\n\\nI hope you enjoy the story!")
        dialogue = analyze_draft("Certainly, Aris said, and turned toward the door.")
        self.assertTrue(any(f.category == "Possible AI commentary" for f in opening))
        self.assertTrue(any(f.category == "Possible AI commentary" for f in closing))
        self.assertFalse(any(f.category == "Possible AI commentary" for f in dialogue))

    def test_report_is_advisory_and_does_not_claim_to_change_prose(self):
        original = "He reached for the switch, but"
        report = format_draft_health_report(analyze_draft(original))
        self.assertIn("advisory only", report)
        self.assertIn("Nothing has been changed", report)
        self.assertEqual(original, "He reached for the switch, but")

    def test_clean_scene_has_no_findings(self):
        text = (
            "The recycler hummed beneath the floor while Aris studied the dark console.\\n\\n"
            "He checked the power couplings, then glanced toward the observation window. "
            "Nothing moved beyond the glass except a slow drift of snow.\\n\\n"
            "A soft click came from behind him. Aris turned, holding his breath."
        )
        self.assertEqual(analyze_draft(text), [])


if __name__ == "__main__":
    unittest.main()

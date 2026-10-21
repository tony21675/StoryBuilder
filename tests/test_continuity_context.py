import tempfile
import unittest
from pathlib import Path

import storybuilder as storybuilder_app
from builder.continuity_context import (
    build_scene_relevance_query,
    estimate_tokens_from_chars,
    is_low_value_detail,
    select_active_character_knowledge,
)
from builder.manuscript import ManuscriptManager


class ContinuityContextTests(unittest.TestCase):
    def test_active_view_prunes_incidental_drink_but_preserves_durable_facts(self):
        ledger = {
            "Tony": [
                "Tony knows Tiffany is his daughter.",
                "Tony promised Sarah he would not return to his old military ways.",
                "Tiffany and Maya drank root beer soda while discussing the school fundraiser.",
                "Tony closed the kitchen door and brewed tea.",
                "Tony knows the kidnapper scratched Tiffany and left an injury.",
                "Tony does not know who abducted Tiffany or where she was taken.",
            ],
            "Maya": [
                "Maya saw the van accelerate and heard its engine.",
                "Maya and Tiffany chose grape soda at lunch.",
            ],
        }
        untouched = {name: list(facts) for name, facts in ledger.items()}

        active, metrics = select_active_character_knowledge(
            ledger,
            "Maya saw the van accelerate and the kidnapper's identifying cheek scratch during the search for Tiffany.",
            character_names=["Tony", "Maya", "Tiffany"],
        )

        all_active = [fact for facts in active.values() for fact in facts]
        self.assertIn("Tony knows Tiffany is his daughter.", all_active)
        self.assertFalse(any("promised Sarah" in fact for fact in all_active),
                         "An unrelated promise should not be loaded into every scene.")
        self.assertTrue(any("scratched Tiffany" in fact for fact in all_active))
        self.assertTrue(any("does not know who abducted" in fact for fact in all_active))
        self.assertTrue(any("van accelerate" in fact for fact in all_active))
        self.assertFalse(any("root beer soda" in fact for fact in all_active))
        self.assertFalse(any("grape soda" in fact for fact in all_active))
        self.assertEqual(ledger, untouched, "Pruning the active view must not mutate persistent knowledge.")
        self.assertLess(metrics["after_chars"], metrics["before_chars"])
        self.assertEqual(metrics["before_estimated_tokens"], estimate_tokens_from_chars(metrics["before_chars"]))
        self.assertGreater(metrics["reduction_percent"], 0)

    def test_incidental_detail_is_available_when_scene_explicitly_needs_it(self):
        ledger = {
            "Maya": [
                "Maya and Tiffany drank grape soda at lunch.",
                "Maya knows Tony is Tiffany's father.",
            ]
        }
        active, _metrics = select_active_character_knowledge(
            ledger,
            "Maya recalls the grape soda that Tiffany drank at lunch.",
        )
        self.assertTrue(any("grape soda" in fact for fact in active["Maya"]))

    def test_large_ledger_has_measurable_context_reduction(self):
        ledger = {
            name: [
                f"{name} routinely watched television after dinner on ordinary evenings, detail {i}."
                for i in range(40)
            ] + [
                f"{name} promised to keep Tiffany's location secret.",
                f"{name} knows the kidnapper left an identifying scratch on his cheek.",
            ]
            for name in ("Tony", "Maya", "Chloe")
        }

        active, metrics = select_active_character_knowledge(
            ledger,
            "Tony and Maya discuss the kidnapper's identifying cheek scratch and search for Tiffany.",
            max_items_per_character=4,
            max_total_items=12,
            character_names=["Tony", "Maya", "Chloe", "Tiffany"],
        )

        all_active = [fact for values in active.values() for fact in values]
        self.assertLessEqual(len(all_active), 12)
        self.assertEqual(metrics["before_items"], 126)
        self.assertLess(metrics["after_items"], 12)
        self.assertLess(metrics["after_chars"], metrics["before_chars"])
        self.assertGreater(metrics["reduction_percent"], 65.0)
        self.assertFalse(any("routinely watched television" in fact for fact in all_active))
        self.assertTrue(any("promised to keep" in fact for fact in all_active),
                        "A secret about Tiffany's location directly affects the search.")
        self.assertTrue(any("identifying scratch" in fact for fact in all_active))

    def test_unrelated_protected_facts_do_not_leak_into_scene_context(self):
        ledger = {
            "Maya": [
                "Maya described the kidnapper smelling like pine needles.",
                "Maya and Tiffany drank grape soda during their lunch conversation.",
                "Tony helped Maya get cleaned up and made her tea the previous night.",
            ],
            "Tony": ["Tony knows Tiffany is his daughter."],
        }
        query = "Tony thanks Chloe for her hug; the group defines broad search roles."
        active, _metrics = select_active_character_knowledge(
            ledger, query, character_names=["Tony", "Maya", "Chloe", "Tiffany"]
        )
        facts = [fact for values in active.values() for fact in values]
        self.assertIn("Tony knows Tiffany is his daughter.", facts)
        self.assertFalse(any("pine needles" in fact for fact in facts))
        self.assertFalse(any("grape soda" in fact for fact in facts))
        self.assertFalse(any("tea the previous night" in fact for fact in facts))

    def test_location_overlap_does_not_keep_incidental_tea_or_bathing_details(self):
        ledger = {
            "Tony": [
                "Tony sat with Maya at the kitchen table drinking tea.",
                "Tony helped Maya get cleaned up in the bathroom and tub.",
            ],
            "Maya": [],
        }
        active, _metrics = select_active_character_knowledge(
            ledger,
            "Tony thanks Chloe for the hug as the group plans search roles from Tony's kitchen.",
            character_names=["Tony", "Maya", "Chloe", "Tiffany"],
        )
        facts = [fact for values in active.values() for fact in values]
        self.assertFalse(any("drinking tea" in fact for fact in facts))
        self.assertFalse(any("bathroom and tub" in fact for fact in facts))

    def test_author_pinned_continuity_focus_selects_specific_historical_facts(self):
        ledger = {
            "Maya": [
                "Maya described the kidnapper smelling like pine needles.",
                "Maya and Tiffany drank grape soda during their lunch conversation.",
            ],
        }
        focus = "Maya's eyewitness clue: the kidnapper's pine-needle scent."
        query = build_scene_relevance_query(
            ["Tony", "Maya", "Chloe"],
            "Tony's kitchen",
            "The group begins a private search for Tiffany.",
            "Tony and Chloe define the initial search roles.",
            continuity_focus=focus,
        )
        active, _metrics = select_active_character_knowledge(
            ledger, query, character_names=["Tony", "Maya", "Chloe", "Tiffany"]
        )
        facts = [fact for values in active.values() for fact in values]
        self.assertTrue(any("pine needles" in fact for fact in facts))
        self.assertFalse(any("grape soda" in fact for fact in facts))

    def test_historical_search_recovers_requested_detail_but_excludes_current_and_future_scenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_dir = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "Chapter_01_Section_01.txt").write_text(
                "At lunch, Tiffany and Maya shared grape soda while talking about the school fundraiser.\n",
                encoding="utf-8",
            )
            (chapter_dir / "Chapter_01_Section_02.txt").write_text(
                "In the current scene, Maya is waiting by the front window and checking the street.\n",
                encoding="utf-8",
            )
            (chapter_dir / "Chapter_01_Section_03.txt").write_text(
                "In the future scene, Tiffany opens a letter and reads its private contents.\n",
                encoding="utf-8",
            )

            result = ManuscriptManager(root).search_historical_context(
                "What soda did Tiffany and Maya drink at lunch?",
                before_chapter=1,
                before_scene=2,
                character_names=["Tiffany", "Maya"],
                limit=4,
                max_chars=1200,
            )

        self.assertEqual(len(result["snippets"]), 1)
        self.assertIn("grape soda", result["text"])
        self.assertIn("Chapter_01_Section_01.txt", result["text"])
        self.assertNotIn("Chapter_01_Section_02.txt", result["text"])
        self.assertNotIn("Chapter_01_Section_03.txt", result["text"])
        self.assertGreater(result["estimated_tokens"], 0)
        self.assertLessEqual(result["characters"], 1200)

    def test_historical_search_supports_legacy_scene_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_dir = root / "Manuscript" / "Chapters" / "Chapter_02"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "Scene_01.txt").write_text(
                "At lunch, Tiffany chose orange soda while Maya picked grape soda.\n",
                encoding="utf-8",
            )

            result = ManuscriptManager(root).search_historical_context(
                "What soda did Maya choose at lunch?",
                before_chapter=3,
                before_scene=1,
                character_names=["Tiffany", "Maya"],
            )

        self.assertEqual(len(result["snippets"]), 1)
        self.assertIn("Scene_01.txt", result["text"])
        self.assertIn("grape soda", result["text"])

    def test_historical_search_does_not_return_unrelated_detail_by_character_name_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_dir = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "Chapter_01_Section_01.txt").write_text(
                "Tiffany and Maya shared grape soda at lunch before returning to class.\n",
                encoding="utf-8",
            )

            result = ManuscriptManager(root).search_historical_context(
                "Tiffany and Maya begin coordinating a search for the unidentified kidnapper.",
                before_chapter=1,
                before_scene=2,
                character_names=["Tiffany", "Maya"],
            )

        self.assertEqual(result["snippets"], [])

    def test_historical_archive_is_explicitly_subordinate_to_current_state(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        prompt = app._writer_system_prompt([])
        self.assertIn("RETRIEVED HISTORICAL CONTINUITY ARCHIVE", prompt)
        self.assertIn("current saved state and explicit present-scene direction take precedence", prompt)
        self.assertIn("never let a stale excerpt override what is true now", prompt)

    def test_historical_search_rejects_generic_narrative_word_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_dir = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter_dir.mkdir(parents=True)
            (chapter_dir / "Chapter_01_Section_01.txt").write_text(
                "Even though no one called the police, the group's focus immediately shifted.\n",
                encoding="utf-8",
            )
            (chapter_dir / "Chapter_01_Section_02.txt").write_text(
                "Maya remained standing on the rough concrete after the shock of the abduction.\n",
                encoding="utf-8",
            )
            (chapter_dir / "Chapter_01_Section_03.txt").write_text(
                "Maya and Tiffany shared grape soda at lunch and chatted casually.\n",
                encoding="utf-8",
            )

            result = ManuscriptManager(root).search_historical_context(
                "The group transitions from initial shock to a private search; no police call has been made.",
                before_chapter=2,
                before_scene=1,
                character_names=["Tiffany", "Maya"],
            )

        self.assertEqual(
            result["snippets"],
            [],
            "One generic or incidental lexical overlap must not inject an unrelated historical passage.",
        )

    def test_routine_detail_classifier_only_guides_active_context(self):
        self.assertTrue(is_low_value_detail("They shared soda after lunch."))
        self.assertFalse(is_low_value_detail("The witness smelled old cigarettes, a clue to the kidnapper."))


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builder.story_package import StoryPackage
from builder.writer_notes import (
    WRITER_NOTES_CONTEXT_TOKENS,
    WRITER_NOTES_MAX_TOKENS,
    WRITER_NOTES_TIMEOUT_SECONDS,
    WRITER_NOTES_AUTO_UPDATE_ENV,
    WRITER_NOTES_FILENAME,
    writer_notes_auto_update_enabled,
    build_writer_notes_review_prompt,
    collect_recent_accepted_scenes,
    collect_initial_seed_scenes,
    default_writer_notes,
    load_writer_notes,
    merge_writer_notes,
    parse_writer_notes_response,
    save_writer_notes,
)


class WriterNotesTests(unittest.TestCase):
    def test_automatic_writing_notes_are_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(writer_notes_auto_update_enabled())

    def test_automatic_writing_notes_require_explicit_opt_in(self):
        for value in ("1", "true", "yes", "on", " TRUE "):
            with self.subTest(value=value), patch.dict(
                os.environ, {WRITER_NOTES_AUTO_UPDATE_ENV: value}, clear=True
            ):
                self.assertTrue(writer_notes_auto_update_enabled())

        for value in ("", "0", "false", "off", "no", "anything else"):
            with self.subTest(value=value), patch.dict(
                os.environ, {WRITER_NOTES_AUTO_UPDATE_ENV: value}, clear=True
            ):
                self.assertFalse(writer_notes_auto_update_enabled())

    def test_optional_notes_review_has_small_generation_budget(self):
        self.assertLessEqual(WRITER_NOTES_CONTEXT_TOKENS, 6144)
        self.assertLessEqual(WRITER_NOTES_MAX_TOKENS, 350)
        self.assertLessEqual(WRITER_NOTES_TIMEOUT_SECONDS, 180)

    def test_new_package_save_creates_an_empty_per_novel_notes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "New Novel"
            package = StoryPackage.new("New Novel")
            package.save(package_path)

            notes_path = package_path / WRITER_NOTES_FILENAME
            self.assertTrue(notes_path.is_file())
            saved = json.loads(notes_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["learned_notes"], [])
            self.assertEqual(saved["reviewed_scenes"], [])

    def test_notes_persist_across_loading_and_saving_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "Novel"
            package = StoryPackage.new("Novel")
            package.writer_notes = {
                **default_writer_notes(),
                "learned_notes": [{
                    "note": "Use selective description when a clear action already communicates the emotion.",
                    "evidence_scenes": ["Chapter 1, Scene 1", "Chapter 1, Scene 2"],
                    "last_updated_scene": "Chapter 1, Scene 2",
                }],
            }
            package.save(package_path)

            reopened = StoryPackage.load(package_path)
            self.assertEqual(
                reopened.writer_notes["learned_notes"][0]["note"],
                package.writer_notes["learned_notes"][0]["note"],
            )

    def test_only_notes_supported_by_two_known_scenes_are_added(self):
        current = default_writer_notes()
        suggestions = [
            {
                "note": "Prefer one useful emotional cue rather than explaining the same feeling repeatedly.",
                "evidence_scenes": ["Chapter 1, Scene 1"],
            },
            {
                "note": "Use concrete action to convey emotion, then move the scene forward.",
                "evidence_scenes": ["Chapter 1, Scene 1", "Chapter 1, Scene 2"],
            },
            {
                "note": "Maya lives next door to Tony.",
                "evidence_scenes": ["Chapter 1, Scene 1", "Chapter 1, Scene 2"],
            },
            {
                "note": "This unsupported observation has one real and one unknown scene.",
                "evidence_scenes": ["Chapter 1, Scene 1", "Chapter 9, Scene 9"],
            },
        ]

        merged, added = merge_writer_notes(
            current,
            suggestions,
            ["Chapter 1, Scene 1", "Chapter 1, Scene 2"],
            "Chapter 1, Scene 2",
        )

        self.assertEqual(added, 1)
        self.assertEqual(len(merged["learned_notes"]), 1)
        self.assertEqual(
            merged["learned_notes"][0]["note"],
            "Use concrete action to convey emotion, then move the scene forward.",
        )

    def test_duplicate_notes_merge_evidence_instead_of_growing_the_list(self):
        current = {
            **default_writer_notes(),
            "learned_notes": [{
                "note": "Use selective description rather than repeating the emotion.",
                "evidence_scenes": ["Chapter 1, Scene 1", "Chapter 1, Scene 2"],
                "last_updated_scene": "Chapter 1, Scene 2",
            }],
        }
        merged, added = merge_writer_notes(
            current,
            [{
                "note": "Use selective description rather than repeating the emotion in multiple ways.",
                "evidence_scenes": ["Chapter 1, Scene 2", "Chapter 1, Scene 3"],
            }],
            ["Chapter 1, Scene 1", "Chapter 1, Scene 2", "Chapter 1, Scene 3"],
            "Chapter 1, Scene 3",
        )
        self.assertEqual(added, 0)
        self.assertEqual(len(merged["learned_notes"]), 1)
        self.assertIn("Chapter 1, Scene 3", merged["learned_notes"][0]["evidence_scenes"])

    def test_notes_file_is_created_for_an_older_package_when_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "Old Novel"
            package_path.mkdir()
            (package_path / "story_bible.json").write_text(
                json.dumps({"title": "Old Novel", "character_cards": []}),
                encoding="utf-8",
            )
            loaded = StoryPackage.load(package_path)
            self.assertEqual(loaded.writer_notes["learned_notes"], [])
            loaded.save()
            self.assertTrue((package_path / WRITER_NOTES_FILENAME).exists())

    def test_notes_reviewer_prompt_is_explicitly_craft_only(self):
        prompt = build_writer_notes_review_prompt(
            default_writer_notes(),
            [
                {"scene": "Chapter 1, Scene 1", "prose": "A character walks into the room."},
                {"scene": "Chapter 1, Scene 2", "prose": "The character sits down."},
            ],
        )
        self.assertIn("Do not store canon, plot, character, relationship, or world facts", prompt)
        self.assertIn("at least two different scene labels", prompt)

    def test_note_response_parser_accepts_json_surrounded_by_commentary(self):
        parsed = parse_writer_notes_response(
            'Result:\n{"suggestions":[{"note":"Use natural dialogue.","evidence_scenes":["Chapter 1, Scene 1","Chapter 1, Scene 2"]}]}\nDone.'
        )
        self.assertEqual(len(parsed), 1)

    def test_initial_seed_scans_every_accepted_scene_in_first_multi_scene_chapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapters = root / "Manuscript" / "Chapters"
            chapter_one = chapters / "Chapter_01"
            chapter_two = chapters / "Chapter_02"
            chapter_one.mkdir(parents=True)
            chapter_two.mkdir(parents=True)

            (chapter_one / "Chapter_01_Section_01.txt").write_text("Chapter one scene one.", encoding="utf-8")
            (chapter_one / "Chapter_01_Section_02.txt").write_text("Chapter one scene two.", encoding="utf-8")
            (chapter_one / "Chapter_01_Section_03.txt").write_text("Chapter one scene three.", encoding="utf-8")
            (chapter_one / "Chapter_01_Section_03_draft.txt").write_text("Draft only, not accepted.", encoding="utf-8")
            (chapter_two / "Chapter_02_Section_01.txt").write_text("Chapter two scene one.", encoding="utf-8")
            (chapter_two / "Chapter_02_Section_02.txt").write_text("Chapter two scene two.", encoding="utf-8")

            samples = collect_initial_seed_scenes(root)

            self.assertEqual(
                [item["scene"] for item in samples],
                ["Chapter 1, Scene 1", "Chapter 1, Scene 2", "Chapter 1, Scene 3"],
            )
            self.assertNotIn("Draft only", " ".join(item["prose"] for item in samples))

    def test_initial_seed_uses_first_chapter_with_two_accepted_scenes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_one = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter_two = root / "Manuscript" / "Chapters" / "Chapter_02"
            chapter_one.mkdir(parents=True)
            chapter_two.mkdir(parents=True)
            (chapter_one / "Chapter_01_Section_01.txt").write_text("Only one scene.", encoding="utf-8")
            (chapter_two / "Chapter_02_Section_01.txt").write_text("First scene of the next chapter.", encoding="utf-8")
            (chapter_two / "Chapter_02_Section_02.txt").write_text("Second scene of the next chapter.", encoding="utf-8")

            samples = collect_initial_seed_scenes(root)

            self.assertEqual(
                [item["scene"] for item in samples],
                ["Chapter 2, Scene 1", "Chapter 2, Scene 2"],
            )

    def test_initial_seed_keeps_opening_and_ending_when_sampling_long_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (chapter / "Chapter_01_Section_01.txt").write_text("A" * 900, encoding="utf-8")
            (chapter / "Chapter_01_Section_02.txt").write_text("B" * 900, encoding="utf-8")

            samples = collect_initial_seed_scenes(root, per_scene_limit=500, total_limit=1000)

            self.assertEqual(len(samples), 2)
            self.assertIn("[Middle omitted for the initial writing-craft review.]", samples[0]["prose"])
            self.assertTrue(samples[0]["prose"].startswith("A"))
            self.assertTrue(samples[0]["prose"].endswith("A"))

    def test_notes_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            notes = default_writer_notes()
            saved_path = save_writer_notes(tmp, notes)
            self.assertTrue(saved_path.exists())
            self.assertEqual(load_writer_notes(tmp)["learned_notes"], [])

    def test_recent_samples_include_saved_sections_but_skip_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (chapter / "Chapter_01_Section_01.txt").write_text("First accepted scene.", encoding="utf-8")
            (chapter / "Chapter_01_Section_01_draft.txt").write_text("Unaccepted draft.", encoding="utf-8")
            (chapter / "Chapter_01_Section_02.txt").write_text("Second accepted scene.", encoding="utf-8")

            samples = collect_recent_accepted_scenes(
                root,
                1,
                2,
                "Second accepted scene.",
                limit=3,
            )

            self.assertEqual([item["scene"] for item in samples], [
                "Chapter 1, Scene 1",
                "Chapter 1, Scene 2",
            ])
            self.assertNotIn("Unaccepted draft.", " ".join(item["prose"] for item in samples))


if __name__ == "__main__":
    unittest.main()

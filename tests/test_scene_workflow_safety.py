import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import storybuilder as storybuilder_app
from builder.scene_contract import CONTRACT_BUILDER_SYSTEM_PROMPT, SceneContract


class FakeButton:
    def __init__(self):
        self.options = {}

    def configure(self, **kwargs):
        self.options.update(kwargs)


class FakeText:
    def __init__(self, value=""):
        self.value = value

    def get(self, _start, _end):
        return self.value

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


class SceneWorkflowSafetyTests(unittest.TestCase):
    def make_app(self, package_path, prose, context=(2, 1), accepted=""):
        # Avoid opening a real Tk window; these tests exercise the file/state
        # safety helpers and replace UI callbacks with harmless fakes.
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            path=Path(package_path),
            current_state={"chapter": 2, "scene": 2, "scene_completed": False},
        )
        app.generated_scene = prose
        app.accepted_scene = accepted
        app.generated_scene_context = context
        app.generated_scene_start_state = None
        app.writer_generation_context = None
        app.writer_generation_start_state = None
        app.writer_generation_in_progress = False
        app.scene_contract_building = False
        app.pending_state_patch = None
        app.writer_output_text = FakeText(prose)
        app._refresh_manuscript = lambda: None
        app._chat = lambda *_args, **_kwargs: None
        return app

    def test_unfinished_writer_text_is_saved_to_origin_scene_not_current_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(tmp, "Scene 1 draft text", context=(2, 1))
            with patch.object(storybuilder_app.messagebox, "showwarning"), patch.object(
                storybuilder_app.messagebox, "showerror"
            ):
                self.assertTrue(app._save_unsaved_writer_draft())

            expected = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_01_draft.txt"
            )
            wrong_scene = (
                Path(tmp)
                / "Manuscript"
                / "Chapters"
                / "Chapter_02"
                / "Chapter_02_Section_02_draft.txt"
            )
            self.assertEqual(expected.read_text(encoding="utf-8"), "Scene 1 draft text\n")
            self.assertFalse(wrong_scene.exists())

    def test_edited_prose_must_pass_contract_before_acceptance(self):
        class ImmediateThread:
            def __init__(self, target, daemon=False):
                self.target = target

            def start(self):
                self.target()

        with tempfile.TemporaryDirectory() as tmp:
            state = {
                "chapter": 2,
                "scene": 1,
                "status": "in_progress",
                "scene_completed": False,
                "current_situation": "Maya has reached Tony but has not told him Tiffany is gone.",
            }
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(path=Path(tmp), current_state=state)
            app.generated_scene = "Original generated prose"
            app.accepted_scene = ""
            app.generated_scene_context = (2, 1)
            app.generated_scene_start_state = json.loads(json.dumps(state))
            app.writer_generation_context = None
            app.writer_generation_start_state = None
            edited_prose = "Edited prose omits Tony noticing the mark."
            app.writer_output_text = FakeText(edited_prose)
            app.writer_state_preview = FakeText()
            app.writer_status = SimpleLabel()
            app.writer_accept_button = FakeButton()
            app.writer_reject_button = FakeButton()
            app.writer_engine = SimpleNamespace(model_path=Path("/tmp/fake-writer.gguf"))
            app._writer_editor_prose = lambda: edited_prose
            app._scene_contract = lambda *_args: {
                "required_beats": ["Tony notices the slap mark."],
                "hard_stop": "Maya begins to tell Tony that the man hit her.",
            }
            app._save_unsaved_writer_draft = lambda: True
            app._refresh_manuscript = lambda: None
            app._chat = lambda *_args, **_kwargs: None
            app._update_writer_buttons = lambda: None
            app.after = lambda _delay, callback: callback()

            failed = {
                "pass": False,
                "missed_beats": ["Tony does not notice the slap mark."],
                "violations": [],
                "notes": "",
            }
            with (
                patch.object(storybuilder_app.threading, "Thread", ImmediateThread),
                patch.object(SceneContract, "validate_with_engine", return_value=failed),
                patch.object(storybuilder_app.messagebox, "showwarning") as warning,
            ):
                storybuilder_app.StoryBuilderApp._accept_generated_scene(app)

            warning.assert_called_once()
            self.assertFalse(
                (Path(tmp) / "Manuscript" / "Chapters" / "Chapter_02" /
                 "Chapter_02_Section_01.txt").exists()
            )
            self.assertEqual(app.generated_scene, "Original generated prose")

    def test_apply_state_update_saves_end_state_snapshot_before_advancing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = {
                "chapter": 2,
                "scene": 1,
                "status": "in_progress",
                "scene_completed": False,
                "chapter_completed": False,
                "current_situation": "Scene 1 starting situation.",
                "scene_cast": ["Maya", "Tony"],
            }
            guidance = {
                "chapter_plans": {
                    "2": {
                        "scene_plan": {
                            "1": {"cast": ["Maya", "Tony"]},
                            "2": {"cast": ["Maya", "Tony"]},
                        }
                    }
                }
            }
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = SimpleNamespace(
                path=root,
                current_state=state,
                extra_json={"writing_guidance.json": guidance},
            )
            app.pending_state_patch = {
                "current_situation": (
                    "Maya has told Tony that Tiffany is gone and is too shaken to explain more."
                )
            }
            app.generated_scene = ""
            app.accepted_scene = ""
            app.generated_scene_context = None
            app.generated_scene_start_state = None
            app.writer_generation_context = None
            app.writer_generation_start_state = None
            app.writer_generation_in_progress = False
            app.scene_contract_building = False
            app.writer_output_text = FakeText()
            app.writer_state_preview = FakeText()
            app.writer_status = SimpleLabel()
            app._writer_editor_prose = lambda: ""
            app._save_unsaved_writer_draft = lambda: True
            app._final_planned_scene_for_chapter = lambda _chapter: 4
            app._scene_plan_cast = lambda chapter, scene: ["Maya", "Tony"] if (chapter, scene) == (2, 2) else []
            app._refresh_all = lambda: None
            app._save = lambda: setattr(app, "dirty", False)
            app._build_scene_direction = lambda: None
            app._chat = lambda *_args, **_kwargs: None
            app._update_writer_buttons = lambda: None

            storybuilder_app.StoryBuilderApp._apply_state_update(app)

            snapshot_path = (
                root / "Manuscript" / "Chapters" / "Chapter_02" /
                "Chapter_02_Section_01_after_state.json"
            )
            self.assertTrue(snapshot_path.is_file())
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual((snapshot["chapter"], snapshot["scene"]), (2, 1))
            self.assertEqual(
                snapshot["current_situation"],
                "Maya has told Tony that Tiffany is gone and is too shaken to explain more.",
            )
            self.assertEqual(app.package.current_state["scene"], 2)

    def test_scene_switch_is_blocked_until_accepted_scene_state_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.make_app(
                tmp,
                "Accepted scene",
                context=(2, 1),
                accepted="Accepted scene",
            )
            app.package.current_state = {
                "chapter": 2,
                "scene": 1,
                "scene_completed": False,
            }
            with patch.object(storybuilder_app.messagebox, "showwarning") as warning:
                self.assertFalse(app._prepare_for_scene_change(2, 2))
            warning.assert_called_once()

    def test_contract_builder_prioritizes_current_situation_over_stale_physical_state(self):
        self.assertIn(
            "current_situation as the authoritative narrative snapshot",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "If they conflict, follow current_situation",
            CONTRACT_BUILDER_SYSTEM_PROMPT,
        )

    def test_writer_prompt_preserves_uncontradicted_physical_continuity(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        prompt = app._writer_system_prompt([])

        self.assertIn(
            "Silence in current_situation does not cancel physical continuity",
            prompt,
        )
        self.assertIn(
            "Avoid an incongruous relationship metaphor",
            prompt,
        )
        self.assertIn(
            "Prefer what characters say and do over narration",
            prompt,
        )
        self.assertIn(
            "Let dialogue and interaction carry scenes whenever the situation allows",
            prompt,
        )
        self.assertIn(
            "give one brief, natural cue that makes the relationship or gesture understandable",
            prompt,
        )
        self.assertIn(
            "rather than explaining the same meaning or emotion again",
            prompt,
        )
        self.assertIn(
            "don't turn gentle concern into insistence or pressure unless the scene calls for it",
            prompt,
        )
        self.assertNotIn("plainly affectionate, non-sensual language", prompt)
        self.assertIn(
            "Let the opening naturally orient the reader to important positions, posture, and contact",
            prompt,
        )
        self.assertIn(
            "Avoid restating one feeling through several descriptions, metaphors, or interpretations",
            prompt,
        )

        notes_prompt = app._writer_system_prompt([
            ("working_writer_notes.json", '{"learned_notes":[{"note":"Use selective description and avoid repeating an emotion."}]}')
        ])
        self.assertIn("temporary per-novel working writer notes are supplied", notes_prompt)
        self.assertIn("Use selective description and avoid repeating an emotion.", notes_prompt)

    def test_semantic_validator_checks_opening_physical_continuity(self):
        current_state = {
            "chapter": 2,
            "scene": 1,
            "current_situation": (
                "Maya is against Tony's chest. Tony is comforting her."
            ),
            "physical_state": {
                "Tony": {
                    "position": "sitting upright against the headboard",
                    "contact": "holding Maya against his chest",
                }
            },
        }
        contract = {
            "direction": "Tony provides a familiar fatherly comfort gesture.",
            "required_beats": ["Tony comforts Maya"],
            "required_facts": [],
            "required_sequence": [],
            "forbidden": [],
            "forbidden_details": [],
            "max_attempts": 3,
        }
        captured = {}

        def fake_validator(_model, prompt):
            captured["prompt"] = prompt
            return {
                "pass": True,
                "missed_beats": [],
                "violations": [],
                "notes": "",
            }

        with patch.object(
            SceneContract,
            "_local_hard_checks",
            return_value={
                "pass": True,
                "missed_beats": [],
                "violations": [],
                "notes": "",
            },
        ), patch("builder.scene_contract._run_validator", side_effect=fake_validator):
            SceneContract.validate_with_engine(
                SimpleNamespace(model_path=Path("/tmp/test-model.gguf")),
                contract,
                current_state,
                "Tony sat on the edge of the bed and held Maya.",
            )

        self.assertIn("compare the prose opening with the supplied current story state", captured["prompt"])
        self.assertIn("does not show a transition that explains the change", captured["prompt"])
        self.assertIn("sitting upright against the headboard", captured["prompt"])
        self.assertIn("sensualized or lingering body-focused wording", captured["prompt"])
        self.assertIn("Tony provides a familiar fatherly comfort gesture.", captured["prompt"])

    def make_save_app(self, package_path, situation, writer_generation=False):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        persisted = {}
        state = {
            "chapter": 2,
            "scene": 1,
            "scene_completed": False,
            "current_situation": "Old saved situation",
        }
        package = SimpleNamespace(path=Path(package_path), current_state=state)
        package.save = lambda: persisted.update(
            current_situation=package.current_state["current_situation"]
        )
        app.package = package
        app.situation_text = FakeText(situation)
        app.generated_scene = ""
        app.accepted_scene = ""
        app.writer_generation_in_progress = writer_generation
        app.scene_contract_building = False
        app.dirty = False
        app._save_unsaved_writer_draft = lambda: True
        app._clear_writer_scene_workspace = lambda *_args: None
        app._update_path_label = lambda: None
        app._build_scene_direction = lambda: None
        app._chat = lambda *_args, **_kwargs: None

        # Isolate the normal save pipeline so the test focuses on whether the
        # Current Situation editor reaches package state before persistence.
        for method_name in (
            "_apply_story_edits",
            "_apply_planning_edits",
            "_apply_scene_contract_edits",
            "_apply_character_edits",
            "_apply_supporting_person_edit",
            "_apply_relationship_edits",
            "_apply_location_edits",
            "_apply_state_edits",
        ):
            setattr(app, method_name, lambda: None)
        return app, persisted

    def test_normal_save_applies_and_persists_current_situation(self):
        with tempfile.TemporaryDirectory() as tmp:
            corrected = "Maya is already curled against Tony's chest."
            app, persisted = self.make_save_app(tmp, corrected)

            storybuilder_app.StoryBuilderApp._save(app)

            self.assertEqual(app.package.current_state["current_situation"], corrected)
            self.assertEqual(persisted["current_situation"], corrected)
            self.assertFalse(app.dirty)

    def test_save_is_blocked_if_current_situation_cannot_be_applied_during_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, persisted = self.make_save_app(
                tmp,
                "A changed situation that must not be applied during generation.",
                writer_generation=True,
            )
            with patch.object(storybuilder_app.messagebox, "showwarning") as warning:
                storybuilder_app.StoryBuilderApp._save(app)

            warning.assert_called_once()
            self.assertEqual(
                app.package.current_state["current_situation"],
                "Old saved situation",
            )
            self.assertNotIn("current_situation", persisted)


class SimpleLabel:
    def __init__(self):
        self.text = ""

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


class SceneResetSafetyTests(unittest.TestCase):
    def make_restore_app(self, package_path, current_state):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        persisted = {}
        package = SimpleNamespace(
            path=Path(package_path),
            current_state=current_state,
            extra_json={},
        )
        package.save = lambda: persisted.update(
            current_state=json.loads(json.dumps(package.current_state))
        )
        app.package = package
        app.dirty = False
        app.writer_generation_in_progress = False
        app.scene_contract_building = False
        app.writer_notes_update_in_progress = False
        app.generated_scene = ""
        app.accepted_scene = ""
        app._save_unsaved_writer_draft = lambda: True
        app._clear_writer_scene_workspace = lambda *_args: None
        app._refresh_all = lambda: None
        app._build_scene_direction = lambda: None
        app._update_path_label = lambda: None
        app._chat = lambda *_args, **_kwargs: None
        return app, persisted

    def test_restore_previous_scene_end_state_resets_pointer_and_restores_situation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (chapter / "Chapter_01_Section_06.txt").write_text(
                "Maya tells Tony Tiffany is gone.", encoding="utf-8"
            )
            saved_end_state = {
                "chapter": 1,
                "scene": 6,
                "status": "story_start",
                "scene_completed": False,
                "chapter_completed": False,
                "current_situation": (
                    "Maya has reached Tony and told him that Tiffany is gone. "
                    "Tony has not yet noticed the slap mark."
                ),
                "scene_cast": ["Maya", "Tony"],
                "physical_state": {"Tony": {"contact": "holding Maya against his chest"}},
            }
            (chapter / "Chapter_01_Section_06_after_state.json").write_text(
                json.dumps(saved_end_state), encoding="utf-8"
            )
            current = {
                "chapter": 2,
                "scene": 1,
                "status": "in_progress",
                "scene_completed": False,
                "current_situation": "STALE: Tony has already noticed the slap mark.",
            }
            app, persisted = self.make_restore_app(root, current)

            with patch.object(
                storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=True
            ) as confirm:
                storybuilder_app.StoryBuilderApp._restore_previous_scene_end_state(app)

            restored = app.package.current_state
            self.assertEqual((restored["chapter"], restored["scene"]), (2, 1))
            self.assertEqual(restored["status"], "in_progress")
            self.assertFalse(restored["scene_completed"])
            self.assertFalse(restored["chapter_completed"])
            self.assertIn("has not yet noticed the slap mark", restored["current_situation"])
            self.assertNotIn("STALE:", restored["current_situation"])
            self.assertEqual(restored["physical_state"], saved_end_state["physical_state"])
            self.assertEqual(persisted["current_state"], restored)
            self.assertIn("Chapter 1, Scene 6", confirm.call_args.args[1])

    def test_restore_previous_scene_end_state_cancel_leaves_state_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "Manuscript" / "Chapters" / "Chapter_01"
            chapter.mkdir(parents=True)
            (chapter / "Chapter_01_Section_06.txt").write_text("Accepted prose", encoding="utf-8")
            (chapter / "Chapter_01_Section_06_after_state.json").write_text(
                json.dumps({
                    "chapter": 1, "scene": 6,
                    "current_situation": "Correct start state.",
                }),
                encoding="utf-8",
            )
            current = {
                "chapter": 2, "scene": 1,
                "current_situation": "Leave this alone.",
                "scene_completed": False,
            }
            app, persisted = self.make_restore_app(root, current)
            original = json.loads(json.dumps(current))

            with patch.object(
                storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=False
            ) as confirm:
                storybuilder_app.StoryBuilderApp._restore_previous_scene_end_state(app)

            self.assertEqual(app.package.current_state, original)
            self.assertFalse(persisted)
            confirm.assert_called_once()

    def test_reset_scene_contract_clears_generated_fields_but_preserves_idea(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = {
                "scene_idea": "Preserve my scene idea.",
                "direction": "Stale direction based on the wrong start state.",
                "end_condition": "Stale end.",
                "scene_contract": {"required_beats": ["Stale beat"]},
                "cast": ["Maya", "Tony"],
            }
            guidance = {"chapter_plans": {"2": {"scene_plan": {"1": entry}}}}
            saved = []
            package = SimpleNamespace(
                path=Path(tmp),
                current_state={"chapter": 2, "scene": 1},
                extra_json={"writing_guidance.json": guidance},
            )
            package.save = lambda: saved.append(True)
            app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
            app.package = package
            app.dirty = False
            app.scene_contract_building = False
            app.writer_generation_in_progress = False
            app.scene_idea_text = FakeText("Preserve my scene idea.")
            app.scene_contract_status = SimpleLabel()
            app._update_path_label = lambda: None
            app._refresh_scene_contract_editor = lambda: None
            app._build_scene_direction = lambda: None
            app._chat = lambda *_args, **_kwargs: None

            with patch.object(
                storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=True
            ):
                storybuilder_app.StoryBuilderApp._reset_current_scene_contract(app)

            self.assertEqual(entry["scene_idea"], "Preserve my scene idea.")
            self.assertNotIn("direction", entry)
            self.assertNotIn("end_condition", entry)
            self.assertNotIn("scene_contract", entry)
            self.assertEqual(entry["cast"], ["Maya", "Tony"])
            self.assertEqual(saved, [True])

    def test_clear_writer_context_requires_confirmation(self):
        class Child:
            def isalive(self):
                return True

        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace()
        app.writer_engine = SimpleNamespace(child=Child(), model_path=Path("/tmp/model.gguf"))
        app._save = lambda: self.fail("Save should not run when reset is cancelled.")
        with patch.object(
            storybuilder_app.StoryBuilderApp, "_ask_yes_no", return_value=False
        ) as confirm:
            storybuilder_app.StoryBuilderApp._clear_writer_context(app)
        confirm.assert_called_once()


if __name__ == "__main__":
    unittest.main()

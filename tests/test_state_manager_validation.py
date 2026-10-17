import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import builder.state_manager as state_manager_module
from builder.state_manager import (
    StateManager,
    extract_json_object,
    remove_prior_chapter_opening_markers,
)


class StateUpdateValidationTests(unittest.TestCase):
    def test_extracts_final_patch_instead_of_echoed_before_state(self):
        before_state = {
            "story_format_version": "1.0",
            "chapter": 1,
            "scene": 1,
            "scene_completed": False,
            "chapter_completed": False,
            "status": "story_start",
            "time_of_day": "",
            # Legacy packages can contain a plain-text location value.
            "location": "",
            "scene_cast": [],
            "events": [],
            "continuity_notes": [],
            "physical_state": {},
            "current_situation": "",
        }
        model_patch = {
            "location": {
                "primary": "Community garden",
                "Maya": "Kneeling near the first planted row",
                "Alex": "Kneeling beside Maya",
            },
            "physical_state": {
                "Maya": {"posture": "kneeling"},
                "Alex": {"posture": "kneeling"},
            },
            "current_situation": (
                "Maya and Alex have finished planting the first row in the garden."
            ),
        }
        output = (
            "llama.cpp output and echoed prompt\\n"
            "CURRENT STATE BEFORE THIS SECTION:\\n"
            + json.dumps(before_state, indent=2)
            + "\\nFinal model response:\\n"
            + json.dumps(model_patch, indent=2)
            + "\\n[ Generation stats ]"
        )

        self.assertEqual(extract_json_object(output), model_patch)

    def setUp(self):
        self.state = {
            "chapter": 2,
            "scene": 1,
            "location": {
                "primary": "Tony's bedroom",
                "Tony": "Holding Maya close",
                "Maya": "Curled against Tony's chest",
            },
            "character_knowledge": {
                "Tony": ["Tony knows Maya is Tiffany's best friend."],
                "Maya": [],
            },
            "physical_state": {
                "Tony": {"position": "sitting"},
                "Maya": {"position": "curled against Tony"},
            },
        }

    def test_merge_patch_reconciles_character_locations_and_removes_legacy_duplicates(self):
        base = {
            "current_situation": "Tony and Maya are in the bedroom.",
            "location": {
                "primary": "Tony's bedroom",
                "Tony": "Tony's bedroom",
                "Maya": "Tony's bedroom",
            },
            # Older saved states may retain duplicate top-level descriptions.
            "Tony": "At home, awake in his bedroom with Maya.",
            "Maya": "In Tony's bedroom, clinging to Tony.",
            "physical_state": {
                "Tony": {
                    "location": "Tony's bedroom",
                    "position": "sitting on the bed",
                    "posture": "relaxed",
                },
                "Maya": {
                    "location": "Tony's bedroom",
                    "position": "lying beside Tony",
                    "posture": "relaxed",
                },
            },
            "character_knowledge": {
                "Tony": ["Tony knows Tiffany is missing."],
            },
            "recent_events": ["Tony reassured Maya in the bedroom."],
        }
        before = json.loads(json.dumps(base))
        patch = {
            "current_situation": (
                "Tony and Maya are sharing a quiet moment over tea at the kitchen table."
            ),
            "location": {
                "primary": "Kitchen",
                "Tony": "Kitchen",
                "Maya": "Kitchen",
            },
            "physical_state": {
                "Tony": {"position": "seated at the kitchen table"},
                "Maya": {"position": "seated opposite Tony at the kitchen table"},
            },
        }

        merged = StateManager.merge_patch(base, patch)

        self.assertEqual(merged["location"]["primary"], "Kitchen")
        self.assertEqual(merged["location"]["Tony"], "Kitchen")
        self.assertEqual(merged["location"]["Maya"], "Kitchen")
        self.assertEqual(merged["physical_state"]["Tony"]["location"], "Kitchen")
        self.assertEqual(merged["physical_state"]["Maya"]["location"], "Kitchen")
        self.assertEqual(
            merged["physical_state"]["Tony"]["position"],
            "seated at the kitchen table",
        )
        self.assertEqual(
            merged["physical_state"]["Maya"]["position"],
            "seated opposite Tony at the kitchen table",
        )
        self.assertNotIn("Tony", merged)
        self.assertNotIn("Maya", merged)
        self.assertEqual(merged["character_knowledge"], base["character_knowledge"])
        self.assertEqual(merged["recent_events"], base["recent_events"])
        self.assertEqual(base, before, "Merging must not mutate the original state.")

    def test_knowledge_audit_filters_routine_action_logs_but_keeps_material_facts(self):
        current_state = {
            "scene_cast": ["Maya", "Tony"],
            "character_knowledge": {
                "Tony": [
                    "Knows Tiffany is his daughter.",
                    "Know that Tony called Beth and asked if she was free tomorrow morning.",
                    "Know that Tony closed the bathroom door.",
                    "Know that Tony brewed chamomile tea for Maya.",
                ],
                "Maya": [
                    "Witnessed Tiffany being taken.",
                    "Has told Tony that Tiffany is gone.",
                    "Tony helped her sit up and guided her toward the bathroom.",
                    "Tony lowered her carefully into the tub.",
                    "Tony offered her tea when she emerged from the bathroom.",
                ],
            },
        }
        patch = {}
        delta = {
            "Tony": [
                "Knows Tiffany is his daughter.",
                "Now knows from Maya that Tiffany is gone.",
                "Now knows from Maya that Tiffany swung her elbow twice into the unidentified man's solar plexus.",
                "Know that Tony called Beth and asked if she was free tomorrow morning for breakfast.",
                "Know that Tony called Jessica and suggested a larger gathering tomorrow.",
                "Know that Tony suggested getting Maya cleaned up with warm water and unscented bubbles.",
                "Know that Tony helped Maya sit up and guided her toward the bathroom.",
                "Know that Tony closed the bathroom door to give Maya privacy.",
                "Know that Tony brewed chamomile tea for Maya.",
                "Know that Tiffany's bedroom is tidy.",
                "Know that Barnaby, a soft and threadbare rabbit, was on the chair in Tiffany's room.",
                "Know that Tiffany has clean pajamas laid out on her bed.",
            ],
            "Maya": [
                "Witnessed Tiffany being taken.",
                "Know one unidentified male kidnapper was involved.",
                "Know Tony is awake and with her in his bedroom.",
                "Has told Tony that Tiffany is gone.",
                "Tony helped her sit up and guided her toward the bathroom.",
                "Tony lowered her carefully into the tub.",
                "Tony gave her peace by closing the bathroom door.",
                "Tony offered her tea when she emerged from the bathroom.",
                "Observed Tiffany scratch the kidnapper three times down his left cheek, causing it to bleed.",
            ],
        }

        StateManager._merge_knowledge_delta(current_state, patch, delta)

        knowledge = patch["character_knowledge"]
        tony = knowledge["Tony"]
        maya = knowledge["Maya"]
        self.assertIn("Knows Tiffany is his daughter.", tony)
        self.assertIn("Now knows from Maya that Tiffany is gone.", tony)
        self.assertIn(
            "Now knows from Maya that Tiffany swung her elbow twice into the unidentified man's solar plexus.",
            tony,
        )
        self.assertIn("Know that Tiffany's bedroom is tidy.", tony)
        self.assertIn(
            "Know that Barnaby, a soft and threadbare rabbit, was on the chair in Tiffany's room.",
            tony,
        )
        self.assertIn("Know that Tiffany has clean pajamas laid out on her bed.", tony)
        self.assertIn("Witnessed Tiffany being taken.", maya)
        self.assertIn(
            "Observed Tiffany scratch the kidnapper three times down his left cheek, causing it to bleed.",
            maya,
        )
        for owner_facts in (tony, maya):
            combined_text = " ".join(owner_facts).casefold()
            for phrase in (
                "called beth",
                "called jessica",
                "suggested getting maya cleaned",
                "helped maya sit up",
                "closed the bathroom door",
                "brewed chamomile tea",
                "lowered her carefully into the tub",
                "offered her tea",
                "has told tony",
                "gave her peace",
            ):
                self.assertNotIn(phrase, combined_text)
        self.assertEqual(
            current_state["character_knowledge"]["Tony"][0],
            "Knows Tiffany is his daughter.",
            "The audit must not mutate the source state.",
        )

    def test_knowledge_audit_does_not_erase_prior_facts_when_only_action_logs_return(self):
        current_state = {
            "scene_cast": ["Tony"],
            "character_knowledge": {
                "Tony": ["Knows Tiffany is his daughter."],
            },
        }
        patch = {}
        delta = {
            "Tony": [
                "Know that Tony called Beth about breakfast.",
                "Know that Tony brewed chamomile tea.",
            ],
        }

        StateManager._merge_knowledge_delta(current_state, patch, delta)

        self.assertNotIn("character_knowledge", patch)
        self.assertEqual(
            current_state["character_knowledge"]["Tony"],
            ["Knows Tiffany is his daughter."],
        )

    def test_rejects_unrecognized_singular_event_field(self):
        with self.assertRaisesRegex(ValueError, "unsupported singular 'event' field"):
            StateManager.validate_patch(
                self.state,
                {"event": "Tony carried Maya back onto the bed."},
            )

    def test_retries_event_log_and_knowledge_pollution_then_returns_ending_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "writer.gguf"
            llama = root / "llama-cli"
            model.touch()
            llama.touch()

            current_state = {
                "story_format_version": "1.0",
                "chapter": 1,
                "scene": 4,
                "scene_completed": False,
                "chapter_completed": False,
                "status": "story_start",
                "time_of_day": "",
                "location": "",
                "scene_cast": [],
                "events": [],
                "continuity_notes": [],
                "physical_state": {},
                "current_situation": "",
            }
            invalid_output = json.dumps({
                "event": "Tony scooped Maya up gently and carried her back onto the sheets.",
                "character_knowledge": {
                    "Tony": [
                        "He helped Maya sit up and guided her toward the bathroom.",
                        "He called Beth and invited her to breakfast.",
                    ],
                    "Maya": ["Tony offered her tea."],
                },
            })
            valid_patch = {
                "current_situation": (
                    "Maya sits opposite Tony at the kitchen table, holding a warm mug of chamomile "
                    "while they share a quiet moment."
                ),
                "location": {
                    "primary": "Kitchen",
                    "Tony": "Seated at the kitchen table opposite Maya",
                    "Maya": "Seated at the kitchen table holding a mug of chamomile",
                },
                "physical_state": {
                    "Tony": {"posture": "seated at the kitchen table"},
                    "Maya": {"posture": "seated", "holding": "a mug of chamomile"},
                },
            }

            class FakeProcess:
                returncode = 0

                def __init__(self, output):
                    self.output = output

                def communicate(self, timeout=None):
                    return self.output, None

            with (
                patch.object(state_manager_module, "DEFAULT_LLAMA", llama),
                patch.object(
                    state_manager_module.subprocess,
                    "Popen",
                    side_effect=[
                        FakeProcess(invalid_output),
                        FakeProcess(json.dumps(valid_patch)),
                    ],
                ) as popen,
                patch.object(StateManager, "_detect_accelerator", return_value=None),
                patch.object(StateManager, "_propose_knowledge_delta", return_value={}),
            ):
                result = StateManager.propose(
                    model,
                    current_state,
                    (
                        "Maya emerged from the bathroom in a robe. Tony offered her chamomile tea. "
                        "She sat opposite him at the kitchen table and held the warm mug in both hands. "
                        "They sat in comfortable silence."
                    ),
                )

            self.assertEqual(result, valid_patch)
            self.assertNotIn("event", result)
            self.assertNotIn("character_knowledge", result)
            self.assertEqual(popen.call_count, 2)
            repair_args = popen.call_args_list[1].args[0]
            repair_prompt = repair_args[repair_args.index("--prompt") + 1]
            self.assertIn("Do not return event, events", repair_prompt)
            self.assertIn("current_situation", repair_prompt)

    def test_rejects_character_knowledge_lists_inside_location(self):
        patch = {
            "location": {
                "Tony": ["Tony now knows Tiffany is gone."],
                "Maya": ["Maya told Tony the man hit her."],
            }
        }

        with self.assertRaisesRegex(ValueError, "Character knowledge belongs"):
            StateManager.validate_patch(self.state, patch)

    def test_rejects_non_object_location(self):
        with self.assertRaisesRegex(ValueError, "'location' must be an object"):
            StateManager.validate_patch(self.state, {"location": ["wrong shape"]})

    def test_rejects_app_managed_scene_control_fields(self):
        for field, value in (
            ("chapter", 3),
            ("scene", 2),
            ("status", "story_start"),
            ("scene_completed", True),
            ("chapter_completed", True),
            ("scene_cast", ["Tiffany"]),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "controlled by StoryBuilder"):
                    StateManager.validate_patch(self.state, {field: value})

    def test_accepts_location_text_and_character_knowledge_in_correct_fields(self):
        patch = {
            "location": {"Maya": "Sitting beside Tony"},
            "character_knowledge": {
                "Tony": [
                    "Tony knows Maya witnessed the abduction.",
                    "Tony knows the man hit Maya.",
                ]
            },
        }

        self.assertIs(StateManager.validate_patch(self.state, patch), patch)

    def test_rejects_non_text_character_knowledge_items(self):
        patch = {"character_knowledge": {"Maya": ["Valid fact", {"fact": "bad shape"}]}}

        with self.assertRaisesRegex(ValueError, "list of text facts"):
            StateManager.validate_patch(self.state, patch)

    def test_removes_prior_chapter_opening_marker_but_preserves_shared_notes(self):
        state = {
            "continuity_notes": [
                "Chapter 1 begins here.",
                "Tony is protective of the girls.",
                "Tiffany's dog tags contain a hidden tracker.",
            ]
        }

        restored = remove_prior_chapter_opening_markers(state, 1, 2)

        self.assertEqual(
            restored["continuity_notes"],
            [
                "Tony is protective of the girls.",
                "Tiffany's dog tags contain a hidden tracker.",
            ],
        )
        self.assertEqual(len(state["continuity_notes"]), 3)

    def test_removes_opening_marker_from_continuity_requirements_too(self):
        state = {
            "continuity_requirements": [
                "Chapter 1 begins here.",
                "Tony and Tiffany live together.",
            ],
            "continuity_notes": [
                "Chapter 1 starts here.",
                "Keep this shared note.",
            ],
        }

        restored = remove_prior_chapter_opening_markers(state, 1, 2)

        self.assertEqual(
            restored["continuity_requirements"],
            ["Tony and Tiffany live together."],
        )
        self.assertEqual(restored["continuity_notes"], ["Keep this shared note."])

    def test_does_not_remove_opening_marker_within_same_chapter(self):
        state = {
            "continuity_notes": ["Chapter 1 begins here.", "Keep this shared note."],
            "continuity_requirements": ["Chapter 1 begins here."],
        }

        restored = remove_prior_chapter_opening_markers(state, 1, 1)

        self.assertEqual(restored, state)

    def test_retries_once_when_character_knowledge_is_put_under_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "writer.gguf"
            llama = root / "llama-cli"
            model.touch()
            llama.touch()

            current_state = {
                "chapter": 2,
                "scene": 2,
                "location": {
                    "primary": "Tony's bedroom",
                    "Tony": "Holding Maya close",
                    "Maya": "Curled against Tony's chest",
                },
                "current_situation": "Maya is distressed.",
                "scene_cast": ["Maya", "Tony"],
                "character_knowledge": {
                    "Tony": ["Tony knows Tiffany is gone."],
                    "Maya": [],
                },
            }
            invalid_output = json.dumps({
                "location": {
                    "Tony": ["Tony now knows the man hit Maya."],
                }
            })
            corrected_patch = {
                "character_knowledge": {
                    "Tony": [
                        "Tony knows Tiffany is gone.",
                        "Tony knows the man hit Maya.",
                    ]
                },
                "current_situation": (
                    "Maya has begun telling Tony what she witnessed, but remains shaken."
                ),
            }
            valid_output = json.dumps(corrected_patch)

            class FakeProcess:
                returncode = 0

                def __init__(self, output):
                    self.output = output

                def communicate(self, timeout=None):
                    return self.output, None

            with (
                patch.object(state_manager_module, "DEFAULT_LLAMA", llama),
                patch.object(
                    state_manager_module.subprocess,
                    "Popen",
                    side_effect=[
                        FakeProcess(invalid_output),
                        FakeProcess(valid_output),
                    ],
                ) as popen,
                patch.object(StateManager, "_detect_accelerator", return_value=None),
                patch.object(StateManager, "_propose_knowledge_delta", return_value={}),
            ):
                result = StateManager.propose(
                    model,
                    current_state,
                    "Maya tells Tony she witnessed the man take Tiffany, but remains shaken.",
                )

            self.assertEqual(
                result,
                {
                    "current_situation": (
                        "Maya has begun telling Tony what she witnessed, but remains shaken."
                    )
                },
            )
            self.assertEqual(popen.call_count, 2)
            second_args = popen.call_args_list[1].args[0]
            repair_prompt = second_args[second_args.index("--prompt") + 1]
            self.assertIn("AUTOMATIC CORRECTION REQUIRED", repair_prompt)
            self.assertIn("SCHEMA REMINDER", repair_prompt)

    def test_drops_malformed_location_values_after_retry_and_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "writer.gguf"
            llama = root / "llama-cli"
            model.touch()
            llama.touch()

            current_state = {
                "chapter": 2,
                "scene": 2,
                "location": {
                    "primary": "Tony's bedroom",
                    "Tony": "Holding Maya close",
                    "Maya": "Curled against Tony's chest",
                },
                "current_situation": "Maya is distressed.",
                "scene_cast": ["Maya", "Tony"],
                "character_knowledge": {
                    "Tony": ["Tony knows Tiffany is gone."],
                    "Maya": [],
                },
            }
            malformed_output = json.dumps({
                "location": {
                    "Tony": [
                        {"event": "Tony continues comforting Maya."},
                    ],
                },
                # Legacy top-level character fields are normalized into
                # location, so include one to guard against sanitizing too early.
                "Maya": [
                    {"event": "Maya remains curled against Tony."},
                ],
                "physical_state": {
                    "Maya": {
                        "posture": "crying against Tony",
                    },
                },
                "current_situation": (
                    "Maya has begun describing the abduction but remains shaken."
                ),
            })

            class FakeProcess:
                returncode = 0

                def communicate(self, timeout=None):
                    return malformed_output, None

            with (
                patch.object(state_manager_module, "DEFAULT_LLAMA", llama),
                patch.object(
                    state_manager_module.subprocess,
                    "Popen",
                    return_value=FakeProcess(),
                ) as popen,
                patch.object(StateManager, "_detect_accelerator", return_value=None),
                patch.object(StateManager, "_propose_knowledge_delta", return_value={}),
            ):
                result = StateManager.propose(
                    model,
                    current_state,
                    "Maya tells Tony what she witnessed, but remains shaken.",
                )

            self.assertEqual(popen.call_count, 2)
            self.assertNotIn("location", result)
            self.assertEqual(
                result["current_situation"],
                "Maya has begun describing the abduction but remains shaken.",
            )
            self.assertIn("physical_state", result)
            merged = StateManager.merge_patch(current_state, result)
            self.assertEqual(merged["location"], current_state["location"])

    def test_planned_end_state_hint_does_not_override_state_from_completed_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "writer.gguf"
            llama = root / "llama-cli"
            model.touch()
            llama.touch()

            current_state = {
                "chapter": 2,
                "scene": 1,
                "current_situation": "Before the accepted scene.",
                "scene_cast": [],
                "character_knowledge": {},
            }
            prose_derived_patch = {
                "current_situation": (
                    "Maya has told Tony that Tiffany is gone, but has not explained the abduction."
                )
            }
            planned_hint = {
                "current_situation": (
                    "Tony knows that the kidnapper hit Maya and asks for details."
                )
            }

            class FakeProcess:
                returncode = 0

                def communicate(self, timeout=None):
                    return json.dumps(prose_derived_patch), None

            with (
                patch.object(state_manager_module, "DEFAULT_LLAMA", llama),
                patch.object(state_manager_module.subprocess, "Popen", return_value=FakeProcess()),
                patch.object(StateManager, "_detect_accelerator", return_value=None),
                patch.object(StateManager, "_propose_knowledge_delta", return_value={}),
            ):
                result = StateManager.propose(
                    model,
                    current_state,
                    "Maya tells Tony that Tiffany is gone, then remains too shaken to explain more.",
                    scene_end_guidance=(
                        "EXPECTED END STATE HINT:\n"
                        + json.dumps(planned_hint)
                    ),
                )

            self.assertEqual(result, prose_derived_patch)

if __name__ == "__main__":
    unittest.main()

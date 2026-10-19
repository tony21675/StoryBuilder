import unittest
from types import SimpleNamespace

import storybuilder as storybuilder_app
from builder.state_manager import (
    KNOWLEDGE_AUDIT_SYSTEM_PROMPT,
    STATE_SYSTEM_PROMPT,
    StateManager,
    append_recent_events,
    clean_knowledge_action_logs,
    filter_new_clue_items,
    normalize_location_patch,
    recover_clues_from_knowledge,
    recover_explicit_unresolved_questions,
    normalize_physical_state_patch,
    validate_state_proposal,
)


class StateAnalysisTransitionTests(unittest.TestCase):
    def test_recent_events_append_new_facts_without_erasing_history_or_duplicates(self):
        existing = [
            {"event": "Tony learned Tiffany was missing."},
            "Maya described the slap.",
        ]
        updated = append_recent_events(
            existing,
            [
                "  TONY learned Tiffany was missing. ",
                "Maya described the slap",
                "Chloe hugged Tony.",
                "Rick pushed his chair back.",
            ],
        )

        self.assertEqual(updated[:2], existing)
        self.assertEqual(
            updated[2:],
            [
                {"event": "Chloe hugged Tony."},
                {"event": "Rick pushed his chair back."},
            ],
        )

    def test_recent_event_identity_normalizes_whitespace(self):
        updated = append_recent_events(
            [{"event": "Tony   told Beth the news."}],
            ["Tony told Beth the news."],
        )
        self.assertEqual(len(updated), 1)

    def test_recent_events_are_capped_to_latest_twelve(self):
        existing = [{"event": f"Earlier event {index}"} for index in range(12)]
        updated = append_recent_events(existing, ["New breakfast disclosure."])

        self.assertEqual(len(updated), 12)
        self.assertEqual(updated[-1], {"event": "New breakfast disclosure."})
        self.assertNotIn({"event": "Earlier event 0"}, updated)

    def test_transition_proposal_accepts_partial_objectives_and_new_events(self):
        base = {
            "current_situation": "The scene is beginning.",
            "active_objectives": {"Chloe": "Remain home sick and uninvolved."},
            "recent_events": [],
        }
        proposal = {
            "current_situation": "Chloe hugs Tony as the group commits to help.",
            "active_objectives": {
                "Chloe": "Support Tony and help find Tiffany."
            },
            "new_recent_events": [
                "Tony disclosed Tiffany's abduction to the group.",
                "Chloe hugged Tony and reassured him.",
            ],
        }

        validated = validate_state_proposal(base, proposal)
        self.assertIs(validated, proposal)

    def test_transition_proposal_rejects_malformed_objectives_and_events(self):
        base = {"current_situation": "Starting point."}
        with self.assertRaisesRegex(ValueError, "active_objectives"):
            validate_state_proposal(
                base,
                {
                    "current_situation": "Ending point.",
                    "active_objectives": ["not", "an", "object"],
                },
            )

        with self.assertRaisesRegex(ValueError, "new_recent_events"):
            validate_state_proposal(
                base,
                {
                    "current_situation": "Ending point.",
                    "new_recent_events": "not a list",
                },
            )

    def test_knowledge_merge_deduplicates_variants_and_removes_superseded_temporary_fact(self):
        before = {
            "scene_cast": ["Tony"],
            "character_knowledge": {
                "Tony": [
                    "Knows Tiffany is his daughter.",
                    "Know Tiffany is his daughter.",
                    "Is wearing borrowed pajamas.",
                ]
            },
        }
        patch = {}
        delta = {
            "Tony": [
                "Knows that Tiffany is his daughter.",
                "Knows Tiffany is his daughter.",
            ],
            "_superseded_facts": {
                "Tony": ["Is wearing borrowed pajamas."]
            },
        }

        StateManager._merge_knowledge_delta(before, patch, delta)

        facts = patch["character_knowledge"]["Tony"]
        self.assertEqual(
            sum("tiffany is his daughter" in fact.casefold() for fact in facts),
            1,
        )
        self.assertNotIn("Is wearing borrowed pajamas.", facts)

    def test_state_prompts_treat_objectives_events_and_temporary_clothing_as_transitions(self):
        self.assertIn("active_objectives", STATE_SYSTEM_PROMPT)
        self.assertIn("new_recent_events", STATE_SYSTEM_PROMPT)
        self.assertIn("sleepwear", STATE_SYSTEM_PROMPT)
        self.assertIn("Replace objectives directly contradicted", STATE_SYSTEM_PROMPT)
        self.assertNotIn("Return only these ending-state fields", STATE_SYSTEM_PROMPT)
        self.assertIn("Treat legacy cast restrictions", STATE_SYSTEM_PROMPT)
        self.assertIn("merely discussed does not learn from the conversation", KNOWLEDGE_AUDIT_SYSTEM_PROMPT)
        self.assertIn("not every later arrival", KNOWLEDGE_AUDIT_SYSTEM_PROMPT)
        self.assertIn("Deduplicate paraphrases of the same observation", KNOWLEDGE_AUDIT_SYSTEM_PROMPT)
        self.assertIn("visible injury or mark", STATE_SYSTEM_PROMPT)
        self.assertIn("do not invent an additional scent", STATE_SYSTEM_PROMPT)
        self.assertIn("first-time nickname", STATE_SYSTEM_PROMPT)

    def test_state_analysis_candidates_include_later_named_characters(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(
            current_state={
                "scene_cast": ["Tony", "Maya"],
                "location": {"primary": "Tony's home"},
                "physical_state": {},
                "character_knowledge": {},
                "active_objectives": {},
            },
            characters={
                "beth.json": {"name": "Beth"},
                "jessica.json": {"name": "Jessica"},
                "chloe.json": {"name": "Chloe"},
                "rick.json": {"name": "Rick"},
                "tiffany.json": {"name": "Tiffany"},
            },
        )
        app._scene_plan_cast = lambda *_args: ["Tony", "Maya"]

        accepted = (
            "Beth, Jessica, Chloe, and Rick arrive for breakfast. Tony tells them "
            "that Tiffany was abducted. Chloe hugs Tony while Maya watches."
        )
        names = app._state_analysis_character_candidates(accepted, 3, 2)

        for name in ("Tony", "Maya", "Beth", "Jessica", "Chloe", "Rick", "Tiffany"):
            self.assertIn(name, names)
        self.assertEqual(len(names), len({name.casefold() for name in names}))

    def test_misplaced_later_arrival_physical_states_are_nested_safely(self):
        base = {
            "scene_cast": ["Tony", "Maya"],
            "location": {
                "primary": "Tony's home",
                "Tony": "Kitchen area",
                "Beth": "Kitchen area",
                "Jessica": "Kitchen area",
                "Rick": "Kitchen area",
            },
            "physical_state": {
                "Tony": {"location": "Kitchen area", "posture": "standing"},
            },
            "character_knowledge": {},
            "active_objectives": {},
        }
        malformed = {
            "current_situation": "The group has begun forming a private effort to find Tiffany.",
            "physical_state": {
                "Tony": {"location": "Kitchen area", "posture": "receiving hug"},
            },
            "Beth": {
                "location": "Kitchen area",
                "position": "seated at the table",
                "posture": "focused",
                "contact": "near Tony",
                "movement": "stationary",
            },
            "Jessica": {
                "location": "Kitchen area",
                "position": "seated at the table",
                "posture": "concentrating",
                "contact": "none",
                "movement": "stationary",
            },
            "Rick": {
                "location": "Kitchen area",
                "position": "seated at the table",
                "posture": "alert",
                "contact": "none",
                "movement": "stationary",
            },
        }

        normalized = normalize_location_patch(base, malformed)
        normalized = normalize_physical_state_patch(
            base,
            normalized,
            scene_characters=["Tony", "Maya", "Beth", "Jessica", "Rick"],
        )
        validate_state_proposal(base, normalized)

        self.assertEqual(
            set(normalized["physical_state"]),
            {"Tony", "Beth", "Jessica", "Rick"},
        )
        for character in ("Beth", "Jessica", "Rick"):
            self.assertEqual(
                normalized["physical_state"][character]["position"],
                "seated at the table",
            )
            self.assertNotIn(character, normalized)

    def test_physical_state_normalizer_leaves_unknown_fields_for_validation(self):
        base = {
            "scene_cast": ["Tony"],
            "physical_state": {"Tony": {"location": "Kitchen area"}},
        }
        malformed = {
            "current_situation": "The scene ends in the kitchen.",
            "unrecognized_metadata": {"location": "do not relocate"},
        }

        normalized = normalize_physical_state_patch(base, malformed)
        with self.assertRaisesRegex(ValueError, "unrecognized_metadata"):
            validate_state_proposal(base, normalized)


    def test_action_log_cleanup_runs_even_when_the_knowledge_audit_returns_nothing(self):
        before = {
            "Tony": [
                "Knows Tiffany is his daughter.",
                "Helped Maya get cleaned up by guiding her to the bathroom and lowering her into the tub.",
                "Closed the bathroom door after helping Maya.",
                "Brewed chamomile tea for Maya.",
                "Sat with Maya at the kitchen table drinking tea.",
                "Now knows from Maya that Tiffany scratched the unidentified man's left cheek three times, causing it to bleed.",
            ],
            "Maya": [
                "Saw Tiffany standing there laughing before the man moved.",
                "Saw Tiffany smiling while standing before the man moved.",
                "Witnessed Tiffany being taken.",
            ],
        }

        cleaned = clean_knowledge_action_logs(before, {}, ["Tony", "Maya"])

        tony = cleaned["Tony"]
        maya = cleaned["Maya"]
        self.assertEqual(tony, [
            "Knows Tiffany is his daughter.",
            "Now knows from Maya that Tiffany scratched the unidentified man's left cheek three times, causing it to bleed.",
        ])
        self.assertEqual(len([
            item for item in maya
            if "tiffany" in item.casefold() and "before the man moved" in item.casefold()
        ]), 1)
        self.assertIn("Witnessed Tiffany being taken.", maya)
        self.assertNotIn("Closed the bathroom door after helping Maya.", tony)
        self.assertNotIn("Brewed chamomile tea for Maya.", tony)
        self.assertEqual(len(before["Tony"]), 6, "Cleanup must not mutate the saved baseline.")

    def test_missing_investigative_clues_are_recovered_and_not_reported_as_new(self):
        knowledge = {
            "Tony": [
                "Now knows from Maya that Tiffany scratched the unidentified man's left cheek three times, causing it to bleed.",
                "Now knows from Maya that the kidnapper smelled like old cigarettes and cheap cologne, with pine needles.",
                "Now knows from Maya that the kidnapper's van accelerated rapidly upon arrival.",
            ],
            "Maya": [
                "Observed Tiffany scratch the kidnapper three times down his left cheek, causing it to bleed.",
            ],
        }

        recovered = recover_clues_from_knowledge(knowledge)
        scratch_clues = [
            item for item in recovered
            if "scratch" in item.casefold() and "cheek" in item.casefold()
        ]
        self.assertEqual(len(scratch_clues), 1)
        self.assertIn("bleed", scratch_clues[0].casefold())

        active = [
            "The kidnapper's van accelerated rapidly upon arrival at the location.",
            "The kidnapper smelled of old cigarettes, cheap cologne, and pine needles, along with an additional sweet scent.",
        ]
        self.assertEqual(
            filter_new_clue_items(active, [
                "The kidnapper's van accelerated rapidly upon arrival at the location.",
                "The kidnapper smelled like old cigarettes and cheap cologne, with pine needles and a sweet scent.",
            ]),
            [],
        )
        self.assertTrue(any(
            "scratch" in item.casefold() and "cheek" in item.casefold()
            for item in filter_new_clue_items(active, recovered)
        ))

    def test_explicit_unknown_identity_destination_and_plate_are_preserved_as_questions(self):
        state = {
            "scene_cast": ["Tony", "Maya"],
            "location": {"primary": "Tony's home", "Tiffany": "inside the van"},
            "active_objectives": {"Tony": "Find Tiffany"},
            "character_knowledge": {
                "Jessica": [
                    "Learned from Tony that Tiffany was taken from the corner by an unidentified man in a van.",
                    "Learned from Tony that he does not know who the kidnapper is or where they took her.",
                    "Learned from Tony that there was no concrete license plate information available.",
                ],
            },
            "unresolved_questions": [],
        }

        questions = recover_explicit_unresolved_questions(state)
        self.assertEqual(questions, [
            "Who abducted Tiffany?",
            "Where was Tiffany taken?",
            "What was the van's license plate?",
        ])

        answered = recover_explicit_unresolved_questions(
            state,
            completed_text=(
                "The kidnapper was identified as Marcus. They took Tiffany to the abandoned warehouse. "
                "The license plate was ABC-123."
            ),
        )
        self.assertEqual(answered, [])

        resolved = recover_explicit_unresolved_questions(
            state,
            resolved_questions=["Who abducted Tiffany?"],
        )
        self.assertNotIn("Who abducted Tiffany?", resolved)


if __name__ == "__main__":
    unittest.main()

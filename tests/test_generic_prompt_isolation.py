import inspect
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

import storybuilder as storybuilder_app
from builder import conversation, guided_setup
from builder.continuity_context import select_active_character_knowledge
from builder.scene_completion import INTEGRITY_AUDIT_SYSTEM_PROMPT
from builder.state_manager import recover_clues_from_knowledge
from builder.scene_contract import (
    CONTRACT_BUILDER_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
    SceneContract,
)
from builder.scene_idea_suggestion import SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT
from builder.state_manager import KNOWLEDGE_AUDIT_SYSTEM_PROMPT, recover_explicit_unresolved_questions


class GenericStoryPromptTests(unittest.TestCase):
    def test_shared_runtime_prompts_do_not_contain_novel_specific_examples(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        writer_prompt = app._writer_system_prompt([])
        contract_context = SceneContract.writer_prompt_context(
            "Saved starting-state summary (verify historical claims).",
            {"author_idea": "The crew gathers to decide its next safe step."},
        )
        prompts = (
            writer_prompt,
            contract_context,
            CONTRACT_BUILDER_SYSTEM_PROMPT,
            VALIDATOR_SYSTEM_PROMPT,
            SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT,
            KNOWLEDGE_AUDIT_SYSTEM_PROMPT,
            INTEGRITY_AUDIT_SYSTEM_PROMPT,
        )
        for prompt in prompts:
            lowered = prompt.casefold()
            for novel_specific_term in ("bubble bath", "abduction", "tiffany", "barnaby", "tony", "maya"):
                self.assertNotIn(novel_specific_term, lowered)

    def test_shared_helpers_and_setup_examples_do_not_name_characters_from_another_novel(self):
        sources = (
            inspect.getsource(guided_setup.GuidedSetupSession),
            inspect.getsource(conversation),
            inspect.getsource(select_active_character_knowledge),
            inspect.getsource(recover_clues_from_knowledge),
            inspect.getsource(storybuilder_app.StoryBuilderApp._interview_character_current_answer),
        )
        for source in sources:
            lowered = source.casefold()
            for old_novel_name in ("tony", "tiffany", "maya", "barnaby"):
                self.assertNotIn(old_novel_name, lowered)

    def test_relationship_interview_reads_generic_character_specific_fields(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.package = SimpleNamespace(characters={
            "Ari.json": {
                "name": "Ari",
                "relationship_with_zoe": "Ari trusts Zoe with technical decisions.",
            }
        })
        app.interview_target_var = SimpleNamespace(get=lambda: "Ari.json")

        answer = storybuilder_app.StoryBuilderApp._interview_character_current_answer(
            app, "Relationships"
        )

        self.assertIn("Relationship With Zoe", answer)
        self.assertIn("Ari trusts Zoe with technical decisions.", answer)

    def test_reloading_scene_idea_refreshes_writer_direction(self):
        source = inspect.getsource(storybuilder_app.StoryBuilderApp._reload_saved_scene_idea)
        self.assertIn("self._refresh_writer_scene_guidance()", source)
        self.assertIn("without", source.casefold())

    def test_writer_scene_direction_is_read_only_and_has_copy_action(self):
        source = inspect.getsource(storybuilder_app.StoryBuilderApp._build_writer_tab)
        self.assertIn('text="Scene Direction (read-only guidance)"', source)
        self.assertIn('state="disabled"', source)
        self.assertIn('text="Copy Scene Direction"', source)
        self.assertIn('command=self._copy_writer_direction', source)

    def test_copy_writer_direction_copies_complete_text_to_clipboard(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        app.writer_direction_text = SimpleNamespace(
            get=Mock(return_value="  CHAPTER 1, SCENE 3\nEnd: The crew agrees on next steps.  ")
        )
        app.writer_status = SimpleNamespace(configure=Mock())
        app.clipboard_clear = Mock()
        app.clipboard_append = Mock()
        app.update_idletasks = Mock()

        storybuilder_app.StoryBuilderApp._copy_writer_direction(app)

        app.clipboard_clear.assert_called_once_with()
        app.clipboard_append.assert_called_once_with(
            "CHAPTER 1, SCENE 3\nEnd: The crew agrees on next steps."
        )
        app.update_idletasks.assert_called_once_with()
        app.writer_status.configure.assert_called_once_with(
            text="Scene Direction copied. Paste it into chat with Ctrl+V."
        )

    def test_state_knowledge_audit_prompt_is_genre_neutral(self):
        prompt = KNOWLEDGE_AUDIT_SYSTEM_PROMPT.casefold()
        for novel_specific_term in ("tony", "tiffany", "abduction", "kidnapping"):
            self.assertNotIn(novel_specific_term, prompt)
        self.assertIn("technical findings", prompt)
        self.assertIn("do not invent motives, identities, locations, evidence, history", prompt)

    def test_missing_person_without_explicit_abduction_does_not_create_kidnapper_question(self):
        state = {
            "scene_cast": ["Zoe Bennett"],
            "character_knowledge": {
                "Zoe Bennett": [
                    "Zoe does not know who disabled the oxygen scrubber.",
                    "Zoe has not identified the kidnapper.",
                    "The communications officer is missing.",
                ],
            },
            "unresolved_questions": [],
        }
        questions = recover_explicit_unresolved_questions(state)
        self.assertEqual(questions, [])
        self.assertFalse(any("kidnap" in question.casefold() for question in questions))

    def test_writer_prompt_uses_evidence_for_historical_claims(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        prompt = app._writer_system_prompt([]).casefold()
        self.assertIn("treat its narrative summary as fallible", prompt)
        self.assertIn("check consequential claims about prior events", prompt)
        self.assertIn("do not repeat it as established history", prompt)
        self.assertIn("the original scene idea can explicitly correct a stale or mistaken summary", prompt)
        self.assertIn("accepted manuscript evidence explicitly rejects, corrects, or replaces an earlier explanation", prompt)
        self.assertIn("do not seed it indirectly through suggestive framing", prompt)
        self.assertIn("treat explicit unresolved_questions as open questions", prompt)
        self.assertIn("do not invent a named off-scene person", prompt)
        self.assertIn("suspected pathway, exact entry point, failure mechanism, and confirmed root cause", prompt)

    def test_scene_idea_is_authoritative_over_a_stale_summary(self):
        context = SceneContract.writer_prompt_context(
            "Saved starting-state summary (verify historical claims): a past event is alleged.",
            {"author_idea": "Continue from the accepted story and focus on the confirmed issue."},
        ).casefold()
        self.assertIn("the original scene idea defines intended direction", context)
        self.assertIn("must not overrule or contradict the author's intent", context)
        self.assertIn("distinguish established facts from speculation", context)

    def test_scene_cast_inference_uses_actual_names_not_a_fixed_novel_name_list(self):
        state = {
            "scene_cast": ["Ari", "Zoe", "Kai"],
            "current_situation": "",
            "location": {
                "primary": "Ari and Zoe's outpost office",
                "Ari": "Ari's shuttle",
                "Zoe": "Zoe's shuttle",
                "Kai": "Kai's lab",
            },
        }
        cast = storybuilder_app.StoryBuilderApp._infer_scene_cast(state)
        self.assertCountEqual(cast, ["Ari", "Zoe", "Kai"])

    def test_scene_idea_suggestion_does_not_treat_saved_summary_as_proof(self):
        prompt = SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT.casefold()
        self.assertIn("not as sole proof", prompt)
        self.assertIn("unsupported by accepted prose or canon", prompt)
        self.assertIn("explicit author corrections take precedence", prompt)


if __name__ == "__main__":
    unittest.main()

import unittest

import storybuilder as storybuilder_app
from builder.scene_contract import (
    CONTRACT_BUILDER_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
    SceneContract,
)
from builder.scene_idea_suggestion import SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT


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
        )
        for prompt in prompts:
            lowered = prompt.casefold()
            for novel_specific_term in ("bubble bath", "abduction", "tiffany", "barnaby"):
                self.assertNotIn(novel_specific_term, lowered)

    def test_writer_prompt_uses_evidence_for_historical_claims(self):
        app = storybuilder_app.StoryBuilderApp.__new__(storybuilder_app.StoryBuilderApp)
        prompt = app._writer_system_prompt([]).casefold()
        self.assertIn("treat its narrative summary as fallible", prompt)
        self.assertIn("check consequential claims about prior events", prompt)
        self.assertIn("do not repeat it as established history", prompt)
        self.assertIn("the original scene idea can explicitly correct a stale or mistaken summary", prompt)

    def test_scene_idea_is_authoritative_over_a_stale_summary(self):
        context = SceneContract.writer_prompt_context(
            "Saved starting-state summary (verify historical claims): a past event is alleged.",
            {"author_idea": "Continue from the accepted story and focus on the confirmed issue."},
        ).casefold()
        self.assertIn("the original scene idea defines intended direction", context)
        self.assertIn("must not overrule or contradict the author's intent", context)
        self.assertIn("distinguish established facts from speculation", context)

    def test_scene_idea_suggestion_does_not_treat_saved_summary_as_proof(self):
        prompt = SCENE_IDEA_SUGGESTION_SYSTEM_PROMPT.casefold()
        self.assertIn("not as sole proof", prompt)
        self.assertIn("unsupported by accepted prose or canon", prompt)
        self.assertIn("explicit author corrections take precedence", prompt)


if __name__ == "__main__":
    unittest.main()

import unittest

from builder.new_novel_assistant import (
    apply_new_novel_proposal,
    is_blank_new_package,
    normalize_new_novel_proposal,
    render_new_novel_preview,
)
from builder.story_package import StoryPackage


class NewNovelAssistantTests(unittest.TestCase):
    def sample(self):
        return {
            "title": "The Long Road",
            "premise": "A retired paramedic is drawn into a small town mystery.",
            "story_planning": {
                "genre": "mystery thriller", "tone": "grounded and tense",
                "core_conflict": "Find out what happened without putting the town at risk.",
                "opposition": "", "setting": "A mountain town in Colorado.",
                "important_elements": "An old station ledger.",
                "themes": ["trust", "responsibility"],
                "open_questions": ["Who last used the old station?"],
            },
            "canon_rules": ["No supernatural events."],
            "characters": [{
                "name": "Mara Quinn", "role": "Protagonist", "age": 34,
                "description": "A retired paramedic returning to her hometown.",
                "personality": ["observant", "stubborn"],
                "background": "She left emergency services after a difficult final year.",
                "occupation": "Not yet decided",
                "appearance": {"build": "Average", "hair": "Dark brown", "eyes": "Hazel"},
                "relationships": {"Inez": "Old friend; trust is strained."},
                "important_items": {"ledger": "An old station ledger."},
                "knowledge_rule": "She knows only what she has learned directly.",
            }],
            "supporting_people": {"Inez": "A former coworker and old friend."},
            "relationships": {"Mara and Inez": "Old friends with strained trust."},
            "locations": {"Old Station": "A disused ambulance station."},
            "opening": {
                "chapter": 1, "scene": 1, "time_of_day": "Early morning",
                "location": "Old Station", "scene_cast": ["Mara Quinn", "Inez"],
                "current_situation": "Mara arrives at the closed station before she knows what happened.",
                "continuity_notes": ["No investigation has started yet."],
            },
            "suggestions": ["Consider whether Mara still keeps her old uniform."],
            "potential_conflicts": [],
        }

    def test_unknown_appearance_fields_are_allowed_and_omitted(self):
        raw = self.sample()
        raw["characters"][0]["appearance"] = {
            "build": "",
            "hair": "Dark brown",
            "eyes": None,
            "style": "   ",
        }
        proposal = normalize_new_novel_proposal(
            raw, author_brief="A retired paramedic returns to a small town."
        )
        self.assertEqual(
            proposal["characters"][0]["appearance"],
            {"hair": "Dark brown"},
        )

    def test_relationship_values_remain_required(self):
        raw = self.sample()
        raw["relationships"]["Mara and Inez"] = ""
        with self.assertRaisesRegex(ValueError, "Relationships value"):
            normalize_new_novel_proposal(
                raw, author_brief="A retired paramedic returns to a small town."
            )

    def test_proposal_applies_only_after_normalization_and_approval(self):
        package = StoryPackage.new()
        brief = "A retired paramedic is drawn into a small town mystery."
        self.assertTrue(is_blank_new_package(package))
        proposal = normalize_new_novel_proposal(self.sample(), author_brief=brief)
        preview = render_new_novel_preview(proposal)
        self.assertIn("AI-PROPOSED DRAFT", preview)
        self.assertIn("Mara Quinn", preview)
        self.assertIn("Who last used the old station?", preview)
        summary = apply_new_novel_proposal(package, proposal)
        self.assertEqual(package.story_bible["title"], "The Long Road")
        self.assertEqual(package.story_bible["premise"], brief)
        self.assertIn("Mara_Quinn.json", package.story_bible["character_cards"])
        self.assertEqual(package.characters["Mara_Quinn.json"]["appearance"]["eyes"], "Hazel")
        self.assertEqual(package.story_bible["locations"]["Old Station"], "A disused ambulance station.")
        self.assertEqual(package.current_state["chapter"], 1)
        self.assertEqual(package.current_state["current_situation"], self.sample()["opening"]["current_situation"])
        self.assertIn("1 character card", summary)
        self.assertFalse(is_blank_new_package(package))

    def test_rejects_duplicate_character_names_and_file_names(self):
        raw = self.sample()
        raw["characters"].append({"name": "mara quinn"})
        with self.assertRaisesRegex(ValueError, "repeats the character name"):
            normalize_new_novel_proposal(raw, author_brief="A mystery about Mara Quinn.")
        raw = self.sample()
        raw["characters"].append({"name": "Mara_Quinn"})
        with self.assertRaisesRegex(ValueError, "same file name"):
            normalize_new_novel_proposal(raw, author_brief="A mystery about Mara Quinn.")

    def test_rejects_unknown_top_level_fields(self):
        raw = self.sample()
        raw["manuscript_text"] = "An unsupported field."
        with self.assertRaisesRegex(ValueError, "Unsupported starter-package fields"):
            normalize_new_novel_proposal(raw, author_brief="A small town mystery.")

    def test_rejects_nonpositive_opening_position(self):
        raw = self.sample()
        raw["opening"]["scene"] = 0
        with self.assertRaisesRegex(ValueError, "Opening scene"):
            normalize_new_novel_proposal(raw, author_brief="A small town mystery.")

    def test_will_not_overwrite_a_nonblank_novel(self):
        package = StoryPackage.new()
        package.story_bible["title"] = "Existing Novel"
        self.assertFalse(is_blank_new_package(package))
        proposal = normalize_new_novel_proposal(self.sample(), author_brief="A small town mystery.")
        with self.assertRaisesRegex(ValueError, "untouched New Novel workspace"):
            apply_new_novel_proposal(package, proposal)


if __name__ == "__main__":
    unittest.main()

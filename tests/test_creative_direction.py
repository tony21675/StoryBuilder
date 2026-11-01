import unittest

from builder.creative_direction import (
    build_creative_direction_prompt,
    format_creative_direction_preview,
    normalize_creative_direction,
)


class CreativeDirectionTests(unittest.TestCase):
    def test_normalizes_multiple_genres_and_moods_without_duplicates(self):
        profile = normalize_creative_direction({
            "genres": ["Science Fiction", "Mystery", "Science Fiction"],
            "moods": ["Tense", "Humorous"],
            "audience": "Adult",
            "explicit_adult_content": False,
        })
        self.assertEqual(profile["genres"], ["Science Fiction", "Mystery"])
        self.assertEqual(profile["moods"], ["Tense", "Humorous"])

    def test_rejects_unknown_genres_and_moods(self):
        with self.assertRaisesRegex(ValueError, "unsupported selection"):
            normalize_creative_direction({
                "genres": ["Space Opera++"],
                "moods": [],
                "audience": "",
                "explicit_adult_content": False,
            })
        with self.assertRaisesRegex(ValueError, "unsupported selection"):
            normalize_creative_direction({
                "genres": [],
                "moods": ["Whatever"],
                "audience": "",
                "explicit_adult_content": False,
            })

    def test_explicit_adult_content_requires_adult_audience(self):
        with self.assertRaisesRegex(ValueError, "only be selected for an Adult"):
            normalize_creative_direction({
                "genres": ["Romance"],
                "moods": [],
                "audience": "Young Adult",
                "explicit_adult_content": True,
            })

    def test_prompt_keeps_choices_as_loose_overall_guidance(self):
        prompt = build_creative_direction_prompt({
            "genres": ["Science Fiction", "Mystery", "Comedy"],
            "moods": ["Tense", "Humorous"],
            "audience": "Adult",
            "explicit_adult_content": True,
        })
        self.assertIn("Genres: Science Fiction, Mystery, Comedy", prompt)
        self.assertIn("Mood and tone: Tense, Humorous", prompt)
        self.assertIn("Intended audience: Adult", prompt)
        self.assertIn("Explicit adult content is permitted", prompt)
        self.assertIn("consenting adults", prompt)
        self.assertIn("not a checklist", prompt)
        self.assertIn("without forcing every genre or mood into every scene", prompt)

    def test_empty_profile_adds_no_prompt_context(self):
        self.assertEqual(build_creative_direction_prompt({}), "")
        self.assertEqual(format_creative_direction_preview({}), "Not specified.")

    def test_preview_is_plain_english(self):
        preview = format_creative_direction_preview({
            "genres": ["Science Fiction", "Mystery"],
            "moods": ["Lighthearted"],
            "audience": "Adult",
            "explicit_adult_content": True,
        })
        self.assertIn("Genres: Science Fiction, Mystery", preview)
        self.assertIn("Mood & tone: Lighthearted", preview)
        self.assertIn("Audience: Adult", preview)
        self.assertIn("Explicit adult content", preview)


if __name__ == "__main__":
    unittest.main()

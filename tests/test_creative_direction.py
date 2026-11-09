import unittest

from builder.creative_direction import (
    AUDIENCE_OPTIONS,
    AUDIENCE_PROFILES,
    GENRE_OPTIONS,
    GENRE_PROFILES,
    build_creative_direction_prompt,
    format_creative_direction_preview,
    normalize_creative_direction,
)


class CreativeDirectionTests(unittest.TestCase):
    def test_genre_and_audience_choices_come_from_profile_files(self):
        self.assertIn("Science Fiction", GENRE_OPTIONS)
        self.assertIn("Mystery", GENRE_OPTIONS)
        self.assertIn("Children's", AUDIENCE_OPTIONS)
        self.assertIn("Middle Grade", AUDIENCE_OPTIONS)
        self.assertIn("Young Adult", AUDIENCE_OPTIONS)
        self.assertIn("Adult", AUDIENCE_OPTIONS)
        self.assertIn("speculative", GENRE_PROFILES["Science Fiction"].lower())
        self.assertIn("profanity", AUDIENCE_PROFILES["Children's"].lower())

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

    def test_prompt_combines_selected_genre_audience_and_content_guidance(self):
        prompt = build_creative_direction_prompt({
            "genres": ["Science Fiction", "Mystery", "Comedy"],
            "moods": ["Tense", "Humorous"],
            "audience": "Adult",
            "explicit_adult_content": True,
        })
        self.assertIn("Genres: Science Fiction, Mystery, Comedy", prompt)
        self.assertIn("Science Fiction guidance:", prompt)
        self.assertIn("Mystery guidance:", prompt)
        self.assertIn("Mood and tone: Tense, Humorous", prompt)
        self.assertIn("Intended audience: Adult", prompt)
        self.assertIn("Adult audience guidance:", prompt)
        self.assertIn("Explicit adult content is permitted", prompt)
        self.assertIn("consenting adults", prompt)
        self.assertIn("not a checklist", prompt)
        self.assertIn("without forcing every genre or mood into every scene", prompt)

    def test_childrens_audience_guidance_excludes_profanity_and_sexual_content(self):
        prompt = build_creative_direction_prompt({
            "genres": ["Mystery"],
            "moods": [],
            "audience": "Children's",
            "explicit_adult_content": False,
        })
        self.assertIn("do not use profanity", prompt.lower())
        self.assertIn("Do not include sexual content", prompt)
        self.assertIn("Explicit adult content is not enabled", prompt)
        self.assertNotIn("Adult audience guidance", prompt)

    def test_explicit_off_is_a_real_content_boundary_for_adult_novels(self):
        prompt = build_creative_direction_prompt({
            "genres": ["Romance"],
            "moods": [],
            "audience": "Adult",
            "explicit_adult_content": False,
        })
        self.assertIn("Explicit adult content is not enabled", prompt)
        self.assertIn("keep intimacy non-graphic", prompt)
        self.assertNotIn("Explicit adult content is permitted", prompt)

    def test_empty_profile_still_carries_the_default_explicit_content_boundary(self):
        prompt = build_creative_direction_prompt({})
        self.assertIn("Explicit adult content is not enabled", prompt)
        self.assertNotIn("Genres:", prompt)
        self.assertNotIn("Intended audience:", prompt)

    def test_preview_is_plain_english_and_does_not_expand_profile_text(self):
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
        self.assertNotIn("speculative", preview.lower())


if __name__ == "__main__":
    unittest.main()

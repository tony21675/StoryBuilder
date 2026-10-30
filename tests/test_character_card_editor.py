import copy
import unittest

from builder.character_card_editor import (
    CharacterCardEditorWindow,
    _LIST_FIELDS,
    _STRING_FIELDS,
    _TEXT_FIELDS,
    _STANDARD_FIELDS,
)


class FakeValue:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeText:
    def __init__(self, value):
        self.value = value

    def get(self, _start, _end):
        return self.value


class CharacterCardEditorBuildTests(unittest.TestCase):
    def make_editor(self, original=None):
        original = copy.deepcopy(original or {})
        editor = object.__new__(CharacterCardEditorWindow)
        editor.original = original
        editor.entry_vars = {
            key: FakeValue(str(original.get(key, "")))
            for key in (*_STRING_FIELDS, "age", "name")
        }
        editor.text_widgets = {
            key: FakeText(str(original.get(key, "")))
            for key in _TEXT_FIELDS
        }
        editor.list_widgets = {
            key: FakeText("\n".join(str(v) for v in original.get(key, [])))
            for key in _LIST_FIELDS
        }
        appearance = original.get("appearance", {})
        if isinstance(appearance, str):
            appearance = {"notes": appearance}
        if not isinstance(appearance, dict):
            appearance = {}
        editor.original_appearance = copy.deepcopy(original.get("appearance", {}))
        editor.appearance_vars = {
            key: FakeValue(str(appearance.get(key, "")))
            for key in ("height", "build", "hair", "eyes", "style", "notes")
        }
        editor.relationship_rows = []
        relationships = original.get("relationships", {})
        if isinstance(relationships, dict):
            for key, value in relationships.items():
                editor.relationship_rows.append(
                    (
                        FakeValue(key),
                        FakeValue(editor._display_text(value)),
                        None,
                    )
                )
        editor.custom_field_rows = []
        for key, value in original.items():
            if key in _STANDARD_FIELDS:
                continue
            nested = isinstance(value, (dict, list))
            editor.custom_field_rows.append(
                {
                    "key": FakeValue(key),
                    "original_key": key,
                    "value": FakeValue("" if nested else editor._display_scalar(value)),
                    "nested": nested,
                    "original": True,
                    "original_value": copy.deepcopy(value),
                    "removed": False,
                }
            )
        return editor

    def test_name_is_the_only_required_field(self):
        editor = self.make_editor()

        saved = editor.build_card()

        editor.entry_vars["name"] = FakeValue("Mara")
        saved = editor.build_card()
        self.assertEqual(saved, {"name": "Mara"})
        self.assertNotIn("age", saved)
        self.assertNotIn("appearance", saved)
        self.assertNotIn("relationships", saved)

    def test_age_can_be_a_number_or_plain_english_text(self):
        editor = self.make_editor()
        editor.entry_vars["name"] = FakeValue("Mara")
        editor.entry_vars["age"] = FakeValue("early thirties")

        self.assertEqual(editor.build_card()["age"], "early thirties")

        editor.entry_vars["age"] = FakeValue("32")
        self.assertEqual(editor.build_card()["age"], 32)

    def test_edit_preserves_existing_nested_fields_and_custom_data(self):
        original = {
            "name": "Daniel Okafor",
            "age": 28,
            "gender": "male",
            "role": "Biologist",
            "description": "A steady specialist.",
            "personality": ["patient", "analytical"],
            "skills": ["biology", "life-support monitoring"],
            "appearance": {
                "height": "6 ft",
                "eyes": "brown",
                "other_detail": {"scar": "small"},
            },
            "relationships": {
                "Elena": "trusted colleague",
                "Ryan": {"type": "friend", "history": "Worked together."},
            },
            "school": {"performance": "Not applicable."},
            "custom_number": 7,
        }
        editor = self.make_editor(original)
        editor.entry_vars["role"] = FakeValue("Senior biologist")
        editor.custom_field_rows.append(
            {
                "key": FakeValue("new_note"),
                "original_key": None,
                "value": FakeValue("Has a dry sense of humor."),
                "nested": False,
                "original": False,
                "original_value": "",
                "removed": False,
            }
        )

        saved = editor.build_card()

        expected = copy.deepcopy(original)
        expected["role"] = "Senior biologist"
        expected["new_note"] = "Has a dry sense of humor."
        self.assertEqual(saved, expected)

    def test_relationship_rows_use_plain_text_and_add_new_relationship(self):
        editor = self.make_editor(
            {"name": "Mara", "relationships": {"Elena": "trusted commander"}}
        )
        editor.relationship_rows.append(
            (FakeValue("Ryan"), FakeValue("Good friend and crewmate."), None)
        )

        saved = editor.build_card()

        self.assertEqual(
            saved["relationships"],
            {
                "Elena": "trusted commander",
                "Ryan": "Good friend and crewmate.",
            },
        )

    def test_nested_information_is_presented_without_json_brackets(self):
        display = CharacterCardEditorWindow._human_readable_value(
            {
                "school": {"performance": "Does okay."},
                "interests": ["Reading", "Music"],
            }
        )

        self.assertIn("School:", display)
        self.assertIn("Performance: Does okay.", display)
        self.assertIn("Reading", display)
        self.assertNotIn("{", display)
        self.assertNotIn("}", display)
        self.assertNotIn('"', display)

    def test_removing_a_custom_field_removes_only_that_field(self):
        original = {"name": "Mara", "private_note": "Remove me"}
        editor = self.make_editor(original)
        editor.custom_field_rows[0]["removed"] = True

        saved = editor.build_card()

        self.assertEqual(saved, {"name": "Mara"})

    def test_custom_field_names_and_values_are_plain_text_not_json(self):
        editor = self.make_editor({"name": "Mara"})
        editor.custom_field_rows.append(
            {
                "key": FakeValue("favorite_food"),
                "original_key": None,
                "value": FakeValue("Fresh peaches"),
                "nested": False,
                "original": False,
                "original_value": "",
                "removed": False,
            }
        )

        saved = editor.build_card()

        self.assertEqual(saved["favorite_food"], "Fresh peaches")


if __name__ == "__main__":
    unittest.main()

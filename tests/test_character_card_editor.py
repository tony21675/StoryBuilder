import copy
import unittest
from unittest.mock import patch

from builder.character_card_editor import (
    CharacterCardEditorWindow,
    _LIST_FIELDS,
    _STRING_FIELDS,
    _TEXT_FIELDS,
    _STANDARD_FIELDS,
    _normalize_character_names,
)


class FakeValue:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeText:
    def __init__(self, value):
        self.value = value

    def get(self, _start, _end):
        return self.value


class FakeWindow:
    def __init__(self):
        self.exists = True

    def update_idletasks(self):
        pass

    def winfo_exists(self):
        return self.exists


class FakeButton:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        self.states.append(kwargs.get("state"))


class FakeFrame:
    def grid(self, *_args, **_kwargs):
        pass

    def columnconfigure(self, *_args, **_kwargs):
        pass


class FakeWidget:
    def grid(self, *_args, **_kwargs):
        pass


class CharacterNameOptionsTests(unittest.TestCase):
    def test_names_are_trimmed_deduplicated_and_sorted_case_insensitively(self):
        self.assertEqual(
            _normalize_character_names(
                [" Zoe Bennett ", "chloe", "Maya", "CHLOE", "", "  ", None]
            ),
            ("chloe", "Maya", "Zoe Bennett"),
        )

    def test_missing_character_names_produces_empty_options(self):
        self.assertEqual(_normalize_character_names(None), ())


class CharacterCardEditorBuildTests(unittest.TestCase):
    def make_editor(self, original=None):
        original = copy.deepcopy(original or {})
        editor = object.__new__(CharacterCardEditorWindow)
        editor.original = original
        school = original.get("school", {})
        if isinstance(school, str):
            school = {"performance": school}
        if not isinstance(school, dict):
            school = {}
        editor.entry_vars = {
            key: FakeValue(str(original.get(key, "")))
            for key in (*_STRING_FIELDS, "age", "name")
        }
        editor.entry_vars["school_performance"] = FakeValue(
            str(school.get("performance", ""))
        )
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

    def test_legacy_pronouns_are_hidden_but_preserved(self):
        editor = self.make_editor({"name": "Mara", "pronouns": "she/her"})

        self.assertNotIn("pronouns", editor.entry_vars)
        self.assertIn("pronouns", _STANDARD_FIELDS)
        self.assertFalse(
            any(row["key"].get() == "pronouns" for row in editor.custom_field_rows)
        )
        self.assertEqual(
            editor.build_card(),
            {"name": "Mara", "pronouns": "she/her"},
        )

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

    def test_multiline_story_fields_are_collected_from_text_widgets(self):
        original = {
            "name": "Jessica",
            "role": "Chloe's mother",
            "story_role": "Original story role.",
            "protective_nature": "Original protective nature.",
            "knowledge_rule": "Original knowledge rule.",
            "nickname_from_tony": "Jess",
        }
        editor = self.make_editor(original)
        editor.text_widgets["story_role"] = FakeText(
            "Updated story role with\na second line."
        )
        editor.text_widgets["protective_nature"] = FakeText(
            "Updated protective nature."
        )
        editor.text_widgets["knowledge_rule"] = FakeText(
            "Updated knowledge rule."
        )
        editor.entry_vars["nickname_from_tony"] = FakeValue("Jessie")

        saved = editor.build_card()

        self.assertEqual(
            saved["story_role"], "Updated story role with\na second line."
        )
        self.assertEqual(saved["protective_nature"], "Updated protective nature.")
        self.assertEqual(saved["knowledge_rule"], "Updated knowledge rule.")
        self.assertEqual(saved["nickname_from_tony"], "Jessie")
        self.assertEqual(saved["role"], "Chloe's mother")

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

    def prepare_save(self, editor, callback):
        editor.entry_vars["name"] = FakeValue("Mara")
        editor.window = FakeWindow()
        editor.save_button = FakeButton()
        editor.save_status_var = FakeValue("")
        editor.on_save = callback
        return editor

    def test_custom_field_initializer_records_original_key(self):
        editor = object.__new__(CharacterCardEditorWindow)
        editor.custom_fields_frame = FakeFrame()
        editor.window = object()
        editor._next_custom_row = 1
        editor.custom_field_rows = []

        with (
            patch("builder.character_card_editor.ttk.Frame", side_effect=lambda *_args, **_kwargs: FakeFrame()),
            patch("builder.character_card_editor.tk.StringVar", side_effect=lambda *_args, value="", **_kwargs: FakeValue(value)),
            patch("builder.character_card_editor.ttk.Entry", side_effect=lambda *_args, **_kwargs: FakeWidget()),
            patch("builder.character_card_editor.ttk.Button", side_effect=lambda *_args, **_kwargs: FakeWidget()),
        ):
            editor._add_custom_field_row("private_note", "Keep this detail", original=True)

        self.assertEqual(editor.custom_field_rows[0]["original_key"], "private_note")

    def test_build_card_tolerates_older_custom_field_rows_without_original_key(self):
        editor = self.make_editor({"name": "Mara", "private_note": "Keep this detail"})
        editor.custom_field_rows[0].pop("original_key")

        saved = editor.build_card()

        self.assertEqual(saved["private_note"], "Keep this detail")

    def test_unexpected_form_build_error_is_shown_in_character_editor(self):
        editor = self.prepare_save(self.make_editor(), lambda _card: self.fail("save callback must not run"))

        def fail_to_build():
            raise KeyError("original_key")

        editor.build_card = fail_to_build
        with patch("builder.character_card_editor.messagebox.showerror") as showerror:
            editor.save()

        showerror.assert_called_once()
        self.assertIs(showerror.call_args.kwargs["parent"], editor.window)
        self.assertIn("original_key", showerror.call_args.args[1])
        self.assertIn("original_key", editor.save_status_var.get())
        self.assertEqual(editor.save_button.states[-1], "normal")

    def test_unexpected_save_callback_error_is_shown_in_character_editor(self):
        editor = self.prepare_save(
            self.make_editor(),
            lambda _card: (_ for _ in ()).throw(RuntimeError("callback failed")),
        )

        with patch("builder.character_card_editor.messagebox.showerror") as showerror:
            editor.save()

        showerror.assert_called_once()
        self.assertIs(showerror.call_args.kwargs["parent"], editor.window)
        self.assertIn("callback failed", showerror.call_args.args[1])
        self.assertIn("callback failed", editor.save_status_var.get())
        self.assertEqual(editor.save_button.states[-1], "normal")

    def test_false_save_callback_result_is_visible_inside_editor(self):
        editor = self.prepare_save(self.make_editor(), lambda _card: False)

        with patch("builder.character_card_editor.messagebox.showerror"):
            editor.save()

        self.assertIn("Save did not complete", editor.save_status_var.get())
        self.assertEqual(editor.save_button.states[-1], "normal")

    def test_save_click_shows_progress_and_keeps_button_disabled_until_callback_returns(self):
        editor = self.prepare_save(self.make_editor(), lambda _card: False)
        seen = []

        def fail_after_progress(_card):
            seen.append(editor.save_status_var.get())
            seen.append(editor.save_button.states[-1])
            return False

        editor.on_save = fail_after_progress
        with patch("builder.character_card_editor.messagebox.showerror"):
            editor.save()

        self.assertEqual(seen, ["Save button clicked. Saving character...", "disabled"])


if __name__ == "__main__":
    unittest.main()

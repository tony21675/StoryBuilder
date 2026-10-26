import inspect
import unittest
from pathlib import Path

import storybuilder as storybuilder_app


class FakeEntry:
    def __init__(self, value):
        self.value = value
        self.get_calls = []

    def get(self, *args):
        self.get_calls.append(args)
        if args:
            raise TypeError("Entry.get() takes 1 positional argument but 3 were given")
        return self.value


class SelectedWidgetTextTests(unittest.TestCase):
    def test_entry_selection_uses_full_value_and_slice_indices(self):
        entry = FakeEntry("daybreak / early morning")

        selected = storybuilder_app.StoryBuilderApp._selected_widget_text(
            entry, 11, 16
        )

        self.assertEqual(selected, "early")
        self.assertEqual(entry.get_calls, [()])

    def test_entry_selection_handles_prefix(self):
        entry = FakeEntry("daybreak / early morning")

        selected = storybuilder_app.StoryBuilderApp._selected_widget_text(
            entry, 0, 8
        )

        self.assertEqual(selected, "daybreak")
        self.assertEqual(entry.get_calls, [()])


if __name__ == "__main__":
    unittest.main()


class TextSelectionCoverageTests(unittest.TestCase):
    def test_popup_text_fields_get_shared_keyboard_selection_support(self):
        for method in (
            storybuilder_app.StoryBuilderApp._show_next_validator_finding,
            storybuilder_app.StoryBuilderApp._show_scene_flow_report,
        ):
            with self.subTest(method=method.__name__):
                self.assertIn("self._add_context_menu", inspect.getsource(method))

        review_source = inspect.getsource(storybuilder_app.StoryBuilderApp._show_next_validator_finding)
        self.assertIn('text="Full Scene Draft"', review_source)
        self.assertIn('self._add_context_menu(draft_text)', review_source)

    def test_entry_discovery_includes_comboboxes_and_spinboxes(self):
        source = inspect.getsource(storybuilder_app.StoryBuilderApp._find_entry_widgets)
        self.assertIn("ttk.Combobox", source)
        self.assertIn("ttk.Spinbox", source)
        self.assertIn("tk.Entry", source)

    def test_visible_copy_only_buttons_are_removed(self):
        source = Path(storybuilder_app.__file__).read_text(encoding="utf-8")
        for label in (
            "Copy Scene Direction",
            "Copy Reconstructed JSON",
            "Copy Draft Prose",
            "Copy Full Report",
            "Copy Full Error",
        ):
            with self.subTest(label=label):
                self.assertNotIn(f'text="{label}"', source)
        self.assertNotIn("copy_label=", source)

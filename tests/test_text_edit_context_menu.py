import unittest

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

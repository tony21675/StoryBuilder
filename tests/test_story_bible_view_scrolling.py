import ast
import inspect
import textwrap
import unittest
from types import SimpleNamespace

from story_bible_app import StoryBibleApp


class FakeCanvas:
    def __init__(self, *, x=100, y=100, width=400, height=300):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.scrolls = []

    def winfo_rootx(self):
        return self.x

    def winfo_rooty(self):
        return self.y

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def winfo_ismapped(self):
        return True

    def yview_scroll(self, units, mode):
        self.scrolls.append((units, mode))


class StoryBibleViewScrollingTests(unittest.TestCase):
    def test_status_message_has_its_own_row_below_json_viewer(self):
        source = inspect.getsource(StoryBibleApp._build_view_tab)
        tree = ast.parse(textwrap.dedent(source))
        grid_rows = {}

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "grid":
                continue
            receiver = node.func.value
            if not isinstance(receiver, ast.Name):
                continue
            row = next(
                (
                    keyword.value.value
                    for keyword in node.keywords
                    if keyword.arg == "row"
                    and isinstance(keyword.value, ast.Constant)
                ),
                None,
            )
            if row is not None:
                grid_rows[receiver.id] = row

        self.assertEqual(grid_rows.get("creative_direction_frame"), 7)
        self.assertEqual(grid_rows.get("writing_preferences_frame"), 8)
        self.assertEqual(grid_rows.get("viewer_frame"), 12)
        self.assertEqual(grid_rows.get("status_label"), 13)

    def make_app(self):
        app = object.__new__(StoryBibleApp)
        app._view_canvas = FakeCanvas()
        return app

    def test_mousewheel_scrolls_view_tab_down_and_up(self):
        app = self.make_app()

        down = app._on_view_mousewheel(
            SimpleNamespace(x_root=150, y_root=180, delta=-120)
        )
        up = app._on_view_mousewheel(
            SimpleNamespace(x_root=150, y_root=180, delta=120)
        )

        self.assertEqual(down, "break")
        self.assertEqual(up, "break")
        self.assertEqual(app._view_canvas.scrolls, [(1, "units"), (-1, "units")])

    def test_mousewheel_supports_small_high_resolution_deltas(self):
        app = self.make_app()

        app._on_view_mousewheel(
            SimpleNamespace(x_root=150, y_root=180, delta=-1)
        )
        app._on_view_mousewheel(
            SimpleNamespace(x_root=150, y_root=180, delta=1)
        )

        self.assertEqual(app._view_canvas.scrolls, [(1, "units"), (-1, "units")])

    def test_mousewheel_does_not_intercept_events_outside_view_tab(self):
        app = self.make_app()

        result = app._on_view_mousewheel(
            SimpleNamespace(x_root=20, y_root=20, delta=-120)
        )

        self.assertIsNone(result)
        self.assertEqual(app._view_canvas.scrolls, [])

    def test_linux_wheel_buttons_scroll_in_both_directions(self):
        app = self.make_app()

        up = app._on_view_mousewheel_linux(
            SimpleNamespace(x_root=150, y_root=180, num=4)
        )
        down = app._on_view_mousewheel_linux(
            SimpleNamespace(x_root=150, y_root=180, num=5)
        )

        self.assertEqual(up, "break")
        self.assertEqual(down, "break")
        self.assertEqual(app._view_canvas.scrolls, [(-1, "units"), (1, "units")])


if __name__ == "__main__":
    unittest.main()

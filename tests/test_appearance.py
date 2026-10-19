import subprocess
import unittest

from builder.appearance import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    detect_system_appearance,
    get_appearance_palette,
)


class AppearanceDetectionTests(unittest.TestCase):
    def test_explicit_storybuilder_override_wins(self):
        def should_not_run(*_args, **_kwargs):
            self.fail("system settings should not be queried for an explicit override")

        self.assertEqual(
            detect_system_appearance({"STORYBUILDER_THEME": "light"}, should_not_run),
            "light",
        )
        self.assertEqual(
            detect_system_appearance({"STORYBUILDER_THEME": "DARK"}, should_not_run),
            "dark",
        )

    def test_gnome_prefer_dark_color_scheme_is_used(self):
        def runner(command, **_kwargs):
            if command == [
                "gsettings", "get", "org.gnome.desktop.interface", "color-scheme"
            ]:
                return subprocess.CompletedProcess(command, 0, "'prefer-dark'\n", "")
            return subprocess.CompletedProcess(command, 1, "", "unavailable")

        self.assertEqual(detect_system_appearance({}, runner), "dark")

    def test_cinnamon_dark_theme_is_recognized(self):
        def runner(command, **_kwargs):
            if command == [
                "gsettings", "get", "org.gnome.desktop.interface", "color-scheme"
            ]:
                return subprocess.CompletedProcess(command, 0, "'default'\n", "")
            if command == [
                "gsettings", "get", "org.cinnamon.desktop.interface", "gtk-theme"
            ]:
                return subprocess.CompletedProcess(command, 0, "'Mint-Y-Dark-Aqua'\n", "")
            return subprocess.CompletedProcess(command, 1, "", "unavailable")

        self.assertEqual(detect_system_appearance({}, runner), "dark")

    def test_unsuffixed_cinnamon_theme_is_treated_as_light(self):
        def runner(command, **_kwargs):
            if command == [
                "gsettings", "get", "org.gnome.desktop.interface", "color-scheme"
            ]:
                return subprocess.CompletedProcess(command, 0, "'default'\n", "")
            if command == [
                "gsettings", "get", "org.cinnamon.desktop.interface", "gtk-theme"
            ]:
                return subprocess.CompletedProcess(command, 0, "'Mint-Y'\n", "")
            return subprocess.CompletedProcess(command, 1, "", "unavailable")

        self.assertEqual(detect_system_appearance({}, runner), "light")

    def test_color_fg_bg_is_used_if_desktop_settings_are_unavailable(self):
        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(command, 1, "", "unavailable")

        self.assertEqual(detect_system_appearance({"COLORFGBG": "15;0"}, runner), "dark")
        self.assertEqual(detect_system_appearance({"COLORFGBG": "0;15"}, runner), "light")

    def test_dark_is_the_fallback_when_no_preference_can_be_detected(self):
        def runner(command, **_kwargs):
            return subprocess.CompletedProcess(command, 1, "", "unavailable")

        self.assertEqual(detect_system_appearance({}, runner), "dark")

    def test_palettes_are_distinct_and_returned_as_fresh_dictionaries(self):
        dark = get_appearance_palette("dark")
        light = get_appearance_palette("light")
        self.assertEqual(dark, DARK_PALETTE)
        self.assertEqual(light, LIGHT_PALETTE)
        self.assertNotEqual(dark["window"], light["window"])
        dark["window"] = "changed"
        self.assertNotEqual(get_appearance_palette("dark")["window"], "changed")


if __name__ == "__main__":
    unittest.main()

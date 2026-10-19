from __future__ import annotations

import os
import re
import subprocess
from typing import Any, Callable, Mapping

_CommandRunner = Callable[..., Any]


DARK_PALETTE = {
    "window": "#1F2228",
    "panel": "#262A31",
    "panel_alt": "#303540",
    "field": "#191C21",
    "text": "#E4E7ED",
    "muted": "#B6BDC8",
    "disabled": "#858D9A",
    "border": "#454C58",
    "selection": "#3C557A",
    "accent": "#527FB8",
    "accent_text": "#FFFFFF",
    "trough": "#171A1F",
}

LIGHT_PALETTE = {
    "window": "#F1F3F6",
    "panel": "#E7EAF0",
    "panel_alt": "#DDE2EA",
    "field": "#FFFFFF",
    "text": "#252A32",
    "muted": "#525B68",
    "disabled": "#818997",
    "border": "#C3CAD5",
    "selection": "#CDDDF4",
    "accent": "#416EAD",
    "accent_text": "#FFFFFF",
    "trough": "#D3D9E2",
}


def _classify_theme_name(value: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    if not normalized:
        return None
    words = set(normalized.split())
    if words & {"dark", "night", "black"}:
        return "dark"
    if words & {"light", "bright", "day"}:
        return "light"
    # Common GTK theme names use an un-suffixed name for their light variant.
    return "light"


def _read_setting(command: list[str], runner: _CommandRunner) -> str:
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError, TypeError):
        return ""
    if getattr(result, "returncode", 1) != 0:
        return ""
    return str(getattr(result, "stdout", "") or "").strip().strip("'\"")


def detect_system_appearance(
    environ: Mapping[str, str] | None = None,
    command_runner: _CommandRunner | None = None,
) -> str:
    """Detect Linux desktop light/dark preference, defaulting to dark."""
    env = os.environ if environ is None else environ
    override = str(env.get("STORYBUILDER_THEME", "") or "").strip().casefold()
    if override in {"dark", "light"}:
        return override

    runner = command_runner or subprocess.run

    # Prefer the desktop's actual saved appearance settings over GTK_THEME.
    # GTK_THEME can be inherited from a launcher or shell and may be stale.
    # Newer GNOME-based desktops expose an explicit color-scheme preference.
    color_scheme = _read_setting(
        ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], runner
    ).casefold()
    if "prefer-dark" in color_scheme or color_scheme == "dark":
        return "dark"
    if "prefer-light" in color_scheme or color_scheme == "light":
        return "light"

    # Cinnamon (Linux Mint), GNOME and XFCE expose their selected GTK theme here.
    queries = [
        ["gsettings", "get", "org.cinnamon.desktop.interface", "gtk-theme"],
        ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
        ["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"],
    ]
    for command in queries:
        theme_name = _read_setting(command, runner)
        appearance = _classify_theme_name(theme_name)
        if appearance:
            return appearance

    # Only consult GTK_THEME when the desktop settings above are unavailable.
    gtk_theme = str(env.get("GTK_THEME", "") or "")
    if gtk_theme:
        result = _classify_theme_name(gtk_theme)
        if result:
            return result

    # Some terminal sessions expose the foreground/background color indexes.
    color_fg_bg = str(env.get("COLORFGBG", "") or "").strip()
    if ";" in color_fg_bg:
        try:
            background_index = int(color_fg_bg.rsplit(";", 1)[-1])
            return "dark" if background_index <= 6 else "light"
        except ValueError:
            pass

    # Prefer readable dark mode when the desktop does not expose its setting.
    return "dark"


def get_appearance_palette(appearance: str) -> dict[str, str]:
    """Return a fresh palette dictionary for the requested appearance."""
    if str(appearance).casefold() == "light":
        return dict(LIGHT_PALETTE)
    return dict(DARK_PALETTE)


def apply_application_appearance(root: Any, appearance: str | None = None) -> str:
    """Apply a comfortable light/dark palette to Tk and ttk widgets."""
    mode = str(appearance or detect_system_appearance()).casefold()
    if mode not in {"dark", "light"}:
        mode = "dark"
    colors = get_appearance_palette(mode)

    try:
        root.configure(background=colors["window"])
    except Exception:
        pass

    # These defaults are applied to classic Tk widgets created after this call,
    # including Text, Listbox, Canvas, Entry and context menus.
    defaults = {
        "*background": colors["window"],
        "*foreground": colors["text"],
        "*Text.background": colors["field"],
        "*Text.foreground": colors["text"],
        "*Text.insertBackground": colors["text"],
        "*Text.selectBackground": colors["selection"],
        "*Text.selectForeground": colors["text"],
        "*Entry.background": colors["field"],
        "*Entry.foreground": colors["text"],
        "*Entry.insertBackground": colors["text"],
        "*Entry.selectBackground": colors["selection"],
        "*Entry.selectForeground": colors["text"],
        "*Listbox.background": colors["field"],
        "*Listbox.foreground": colors["text"],
        "*Listbox.selectBackground": colors["selection"],
        "*Listbox.selectForeground": colors["text"],
        "*Menu.background": colors["panel"],
        "*Menu.foreground": colors["text"],
        "*Menu.activeBackground": colors["selection"],
        "*Menu.activeForeground": colors["text"],
        "*Menu.disabledForeground": colors["disabled"],
        "*Canvas.background": colors["window"],
        "*Canvas.highlightBackground": colors["window"],
        "*Toplevel.background": colors["window"],
    }
    for option, value in defaults.items():
        try:
            root.option_add(option, value)
        except Exception:
            pass

    try:
        from tkinter import ttk

        style = ttk.Style(root)
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            ".",
            background=colors["window"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["panel_alt"],
            darkcolor=colors["panel"],
            focuscolor=colors["accent"],
            troughcolor=colors["trough"],
        )
        style.configure("TFrame", background=colors["window"])
        style.configure("TLabel", background=colors["window"], foreground=colors["text"])
        style.configure(
            "TButton",
            background=colors["panel_alt"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            focusthickness=1,
            padding=(8, 4),
        )
        style.map(
            "TButton",
            background=[
                ("disabled", colors["panel"]),
                ("pressed", colors["accent"]),
                ("active", colors["selection"]),
            ],
            foreground=[
                ("disabled", colors["disabled"]),
                ("pressed", colors["accent_text"]),
                ("active", colors["text"]),
            ],
        )
        style.configure(
            "TEntry",
            fieldbackground=colors["field"],
            foreground=colors["text"],
            background=colors["field"],
            bordercolor=colors["border"],
            lightcolor=colors["panel_alt"],
            darkcolor=colors["panel"],
            selectbackground=colors["selection"],
            selectforeground=colors["text"],
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["field"],
            foreground=colors["text"],
            background=colors["panel_alt"],
            arrowcolor=colors["text"],
            bordercolor=colors["border"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["field"]), ("focus", colors["field"])],
            foreground=[("readonly", colors["text"]), ("disabled", colors["disabled"])],
            selectbackground=[("readonly", colors["selection"])],
            selectforeground=[("readonly", colors["text"])],
            background=[("active", colors["selection"])],
        )
        style.configure(
            "TCheckbutton",
            background=colors["window"],
            foreground=colors["text"],
            indicatorcolor=colors["field"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", colors["window"])],
            foreground=[("disabled", colors["disabled"])],
            indicatorcolor=[("selected", colors["accent"]), ("pressed", colors["selection"])],
        )
        style.configure("TRadiobutton", background=colors["window"], foreground=colors["text"])
        style.map(
            "TRadiobutton",
            background=[("active", colors["window"])],
            foreground=[("disabled", colors["disabled"])],
        )
        style.configure("TNotebook", background=colors["window"], bordercolor=colors["border"])
        style.configure(
            "TNotebook.Tab",
            background=colors["panel_alt"],
            foreground=colors["text"],
            padding=(10, 5),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", colors["accent"]), ("active", colors["selection"])],
            foreground=[("selected", colors["accent_text"]), ("active", colors["text"])],
        )
        style.configure(
            "TLabelframe",
            background=colors["window"],
            foreground=colors["text"],
            bordercolor=colors["border"],
        )
        style.configure("TLabelframe.Label", background=colors["window"], foreground=colors["text"])
        style.configure("TScrollbar", background=colors["panel_alt"], troughcolor=colors["trough"])
        style.map("TScrollbar", background=[("active", colors["selection"])])
        style.configure(
            "Treeview",
            background=colors["field"],
            fieldbackground=colors["field"],
            foreground=colors["text"],
            bordercolor=colors["border"],
        )
        style.map(
            "Treeview",
            background=[("selected", colors["selection"])],
            foreground=[("selected", colors["text"])],
        )
        style.configure("Treeview.Heading", background=colors["panel_alt"], foreground=colors["text"])
        style.configure("TSeparator", background=colors["border"])
        style.configure(
            "TProgressbar",
            background=colors["accent"],
            troughcolor=colors["trough"],
            bordercolor=colors["border"],
        )
        style.configure("TScale", background=colors["window"], troughcolor=colors["trough"])
        style.configure("TSpinbox", fieldbackground=colors["field"], foreground=colors["text"])
    except Exception:
        # Appearance styling should never prevent the app from opening.
        pass

    return mode

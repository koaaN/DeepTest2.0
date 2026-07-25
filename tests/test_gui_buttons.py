import tkinter as tk
import unittest
from tkinter import ttk

try:
    _probe = tk.Tk()
    _probe.destroy()
    HAS_DISPLAY = True
except tk.TclError:
    HAS_DISPLAY = False

from deeptesting.gui import DeepTestingApp

BUTTON_STYLES = (
    "Primary.TButton", "Secondary.TButton", "Danger.TButton",
    "Nav.TButton", "NavActive.TButton", "Icon.TButton", "Chip.TButton",
)


def contrast(widget: tk.Misc, foreground: str, background: str) -> float:
    """WCAG contrast ratio; 1.0 means the text is invisible against its background."""
    def luminance(color: str) -> float:
        channels = []
        for value in widget.winfo_rgb(color):
            channel = value / 65535
            channels.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
        red, green, blue = channels
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


@unittest.skipUnless(HAS_DISPLAY, "requires a display")
class ButtonRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = DeepTestingApp()
        self.app.withdraw()

    def tearDown(self) -> None:
        self.app.destroy()

    def test_no_classic_tk_buttons(self) -> None:
        # macOS ignores -background on tk.Button, so any classic button renders
        # its light-on-dark text on a white native face.
        def walk(widget: tk.Misc) -> list[str]:
            found = [str(widget)] if isinstance(widget, tk.Button) else []
            for child in widget.winfo_children():
                found.extend(walk(child))
            return found

        self.assertEqual(walk(self.app), [])

    def test_button_text_is_readable_in_every_state(self) -> None:
        style = ttk.Style(self.app)
        for name in BUTTON_STYLES:
            for state in ((), ("active",), ("pressed",), ("disabled",)):
                with self.subTest(style=name, state=state or ("normal",)):
                    foreground = style.lookup(name, "foreground", list(state))
                    background = style.lookup(name, "background", list(state))
                    self.assertGreaterEqual(contrast(self.app, foreground, background), 3.0)


if __name__ == "__main__":
    unittest.main()

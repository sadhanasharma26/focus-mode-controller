"""Optional macOS menu bar launcher for Focus Mode Controller."""

from __future__ import annotations

import subprocess
from pathlib import Path

try:
    import rumps
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"rumps is required for menubar mode: {exc}")


class FocusModeMenubar(rumps.App):
    def __init__(self) -> None:
        super().__init__("Focus", menu=["Open App", "Quit"])
        self.project_root = Path(__file__).resolve().parent

    @rumps.clicked("Open App")
    def open_app(self, _sender) -> None:
        # Opens the local web app URL in the default browser.
        subprocess.Popen(["open", "http://127.0.0.1:5000"], cwd=str(self.project_root))

    @rumps.clicked("Quit")
    def quit_app(self, _sender) -> None:
        rumps.quit_application()


if __name__ == "__main__":
    app = FocusModeMenubar()
    app.run()

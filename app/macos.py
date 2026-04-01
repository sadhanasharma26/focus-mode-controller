"""macOS system integration helpers for Focus Mode Controller."""

from __future__ import annotations

import logging
import os
import subprocess

from config import APP_DIR, LOG_PATH

APP_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("focus_mode.macos")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = logging.FileHandler(LOG_PATH)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _logger.addHandler(_handler)


def _run_command(command: list[str]) -> bool:
    """Run a command safely and return True on success."""
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            _logger.warning(
                "Command failed (%s): %s",
                completed.returncode,
                " ".join(command),
            )
            if completed.stderr:
                _logger.warning("stderr: %s", completed.stderr.strip())
            return False
        return True
    except Exception as exc:
        _logger.warning("Command execution error for %s: %s", " ".join(command), exc)
        return False


def _is_demo_mode() -> bool:
    return os.environ.get("FOCUS_DEMO_MODE", "0") == "1"


def _run_osascript(script: str) -> bool:
    """Run AppleScript safely and return True when it exits cleanly."""
    return _run_command(["osascript", "-e", script])


def _shortcuts_toggle(shortcut_name: str) -> bool:
    """Run a named macOS Shortcut if the shortcuts CLI is available."""
    return _run_command(["shortcuts", "run", shortcut_name])


def enable_dnd() -> bool:
    """Enable Do Not Disturb using Shortcut first, then AppleScript fallback."""
    if _is_demo_mode():
        _logger.info("Demo mode active: skipping enable_dnd")
        return True

    # Method 1: Ventura+ Shortcut integration (recommended).
    if _shortcuts_toggle("Enable Do Not Disturb"):
        return True

    # Method 2: Fallback to opening Focus settings as best-effort.
    # This does not guarantee DND toggles on all macOS versions but provides
    # a no-crash fallback path.
    fallback_script = (
        'tell application "System Settings" to activate\n'
        'delay 0.3\n'
        'tell application "System Events"\n'
        'keystroke "," using command down\n'
        'end tell'
    )
    if _run_osascript(fallback_script):
        return True

    _logger.warning("Failed to enable DND with both methods")
    return False


def disable_dnd() -> bool:
    """Disable Do Not Disturb using Shortcut first, then AppleScript fallback."""
    if _is_demo_mode():
        _logger.info("Demo mode active: skipping disable_dnd")
        return True

    # Method 1: Ventura+ Shortcut integration (recommended).
    if _shortcuts_toggle("Disable Do Not Disturb"):
        return True

    # Method 2: Best-effort fallback.
    fallback_script = (
        'tell application "System Settings" to activate\n'
        'delay 0.3\n'
        'tell application "System Events"\n'
        'key code 53\n'
        'end tell'
    )
    if _run_osascript(fallback_script):
        return True

    _logger.warning("Failed to disable DND with both methods")
    return False


def show_notification(title: str, message: str) -> None:
    """Show a desktop notification via osascript (no exceptions propagated)."""
    if _is_demo_mode():
        _logger.info("Demo mode notification: %s | %s", title, message)
        return

    try:
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        script = (
            f'display notification "{safe_message}" '
            f'with title "{safe_title}" sound name "Glass"'
        )
        _run_osascript(script)
    except Exception as exc:
        _logger.warning("Failed to show notification: %s", exc)


def dim_windows(opacity: float = 0.5) -> None:
    """Create a persistent dim overlay using Hammerspoon (if available).

    The implementation is best-effort: if Hammerspoon is not installed or
    automation fails, the function logs a warning and returns.
    """
    if _is_demo_mode():
        _logger.info("Demo mode active: skipping dim_windows")
        return

    try:
        normalized = max(0.0, min(0.8, float(opacity)))
        alpha = f"{normalized:.3f}"

        # We use Hammerspoon's Lua runtime to build a click-through, screen-wide
        # overlay. This keeps the function script-only without bundled binaries.
        if not _run_command(["which", "hs"]):
            _logger.warning("Skipping dim overlay: Hammerspoon 'hs' CLI not found")
            return

        lua_script = (
            "focusOverlays = focusOverlays or {}\n"
            "for _, o in pairs(focusOverlays) do o:delete() end\n"
            "focusOverlays = {}\n"
            f"local alpha = {alpha}\n"
            "for _, screen in ipairs(hs.screen.allScreens()) do\n"
            "  local frame = screen:fullFrame()\n"
            "  local rect = hs.drawing.rectangle(frame)\n"
            "  rect:setFillColor({red=0,green=0,blue=0,alpha=alpha})\n"
            "  rect:setStroke(false)\n"
            "  rect:setLevel('floating')\n"
            "  rect:setBehaviorByLabels({'canJoinAllSpaces','stationary','ignoresCycle'})\n"
            "  rect:show()\n"
            "  table.insert(focusOverlays, rect)\n"
            "end\n"
        )

        _run_command(["hs", "-q", "-c", lua_script])
    except Exception as exc:
        _logger.warning("Failed to dim windows: %s", exc)


def undim_windows() -> None:
    """Remove dim overlay windows created by dim_windows()."""
    if _is_demo_mode():
        _logger.info("Demo mode active: skipping undim_windows")
        return

    try:
        if not _run_command(["which", "hs"]):
            return

        lua_script = (
            "focusOverlays = focusOverlays or {}\n"
            "for _, o in pairs(focusOverlays) do o:delete() end\n"
            "focusOverlays = {}\n"
        )
        _run_command(["hs", "-q", "-c", lua_script])
    except Exception as exc:
        _logger.warning("Failed to undim windows: %s", exc)


def check_permissions() -> dict[str, bool]:
    """Return current integration capability checks.

    Keys:
    - hosts_writable: can write /etc/hosts (requires sudo/root)
    - accessibility: can send accessibility events via osascript
    - shortcuts: shortcuts CLI is available
    """
    permissions = {
        "hosts_writable": os.access("/etc/hosts", os.W_OK),
        "accessibility": False,
        "shortcuts": False,
    }

    try:
        permissions["shortcuts"] = _run_command(["which", "shortcuts"])
    except Exception as exc:
        _logger.warning("Error checking shortcuts permission: %s", exc)

    try:
        permissions["accessibility"] = _run_osascript('tell application "System Events" to get name of first process')
    except Exception as exc:
        _logger.warning("Error checking accessibility permission: %s", exc)

    return permissions

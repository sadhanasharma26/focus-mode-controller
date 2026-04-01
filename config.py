"""Application configuration constants."""

from pathlib import Path

APP_DIR = Path.home() / ".focus-mode"
DB_PATH = APP_DIR / "focus.db"
LOG_PATH = APP_DIR / "focus.log"
DEFAULT_SQLITE_URL = f"sqlite:///{DB_PATH}"

DEFAULT_SETTINGS = {
    "work_duration": 25,
    "short_break": 5,
    "long_break": 15,
    "long_break_after": 4,
    "block_sites": True,
    "enable_dnd": True,
    "dim_windows": True,
    "dim_opacity": 0.5,
}

DEFAULT_BLOCKLIST = [
    "youtube.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "facebook.com",
    "tiktok.com",
    "netflix.com",
]

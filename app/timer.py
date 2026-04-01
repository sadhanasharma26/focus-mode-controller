"""Pomodoro session engine with APScheduler lifecycle control."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from config import APP_DIR, LOG_PATH

from . import blocker, macos
from .database import get_session
from .models import AppSettings, BlocklistEntry, PomodoroSession

APP_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("focus_mode.timer")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = logging.FileHandler(LOG_PATH)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _logger.addHandler(_handler)

scheduler = BackgroundScheduler()
_state_lock = RLock()

session_state: dict[str, Any] = {
    "active": False,
    "session_type": None,
    "started_at": None,
    "ends_at": None,
    "duration_seconds": 0,
    "seconds_remaining": 0,
    "completed_pomodoros": 0,
    "total_pomodoros": 0,
    "paused": False,
    "pause_started_at": None,
    "current_session_id": None,
}

TICK_JOB_ID = "focus_tick"
END_JOB_ID = "focus_end"
DEMO_MODE = False


def _safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        _logger.warning("Integration call failed for %s: %s", getattr(func, "__name__", str(func)), exc)
        return None


def _utc_now() -> datetime:
    """Return timezone-aware UTC timestamp for scheduler compatibility."""
    return datetime.now(timezone.utc)


def set_demo_mode(enabled: bool) -> None:
    """Enable or disable timer demo mode runtime behavior."""
    global DEMO_MODE
    DEMO_MODE = bool(enabled)


def _remove_job_if_exists(job_id: str) -> None:
    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    except Exception as exc:
        _logger.warning("Failed to remove job %s: %s", job_id, exc)


def _duration_minutes_for_type(session_type: str, settings: AppSettings) -> int:
    if session_type == "work":
        return int(settings.work_duration)
    if session_type == "short_break":
        return int(settings.short_break)
    if session_type == "long_break":
        return int(settings.long_break)
    raise ValueError(f"Unknown session_type: {session_type}")


def _enabled_block_domains() -> list[str]:
    with get_session() as db:
        rows = db.query(BlocklistEntry).filter(BlocklistEntry.enabled.is_(True)).all()
        return [row.domain for row in rows]


def get_session_state() -> dict[str, Any]:
    """Return a JSON-serializable snapshot of the current session state."""
    with _state_lock:
        data = dict(session_state)

    started_at = data.get("started_at")
    ends_at = data.get("ends_at")
    pause_started = data.get("pause_started_at")
    data["started_at"] = started_at.isoformat() if isinstance(started_at, datetime) else None
    data["ends_at"] = ends_at.isoformat() if isinstance(ends_at, datetime) else None
    data["pause_started_at"] = pause_started.isoformat() if isinstance(pause_started, datetime) else None
    return data


def _set_idle_state() -> None:
    with _state_lock:
        completed = session_state.get("completed_pomodoros", 0)
        total = session_state.get("total_pomodoros", 0)
        session_state.update(
            {
                "active": False,
                "session_type": None,
                "started_at": None,
                "ends_at": None,
                "duration_seconds": 0,
                "seconds_remaining": 0,
                "paused": False,
                "pause_started_at": None,
                "current_session_id": None,
                "completed_pomodoros": completed,
                "total_pomodoros": total,
            }
        )


def start_session(session_type: str, settings: AppSettings) -> None:
    """Start a work/break session and schedule tick/end jobs."""
    if session_type not in {"work", "short_break", "long_break"}:
        raise ValueError("session_type must be 'work', 'short_break', or 'long_break'")

    with _state_lock:
        if session_state["active"]:
            raise RuntimeError("A session is already active")

    duration_minutes = _duration_minutes_for_type(session_type, settings)
    duration_seconds = 10 if DEMO_MODE else max(1, duration_minutes * 60)
    started_at = _utc_now()
    ends_at = started_at + timedelta(seconds=duration_seconds)

    sites_blocked = False
    dnd_enabled = False

    if session_type == "work" and bool(settings.block_sites):
        domains = _enabled_block_domains()
        _safe_call(blocker.block_sites, domains)
        sites_blocked = len(domains) > 0

    if session_type == "work" and bool(settings.enable_dnd):
        dnd_enabled = bool(_safe_call(macos.enable_dnd))

    if bool(settings.dim_windows):
        _safe_call(macos.dim_windows, float(settings.dim_opacity))

    with get_session() as db:
        row = PomodoroSession(
            started_at=started_at,
            ended_at=None,
            duration_minutes=duration_minutes,
            session_type=session_type,
            completed=False,
            sites_blocked=sites_blocked,
            dnd_enabled=dnd_enabled,
        )
        db.add(row)
        db.flush()
        session_id = row.id

    with _state_lock:
        session_state.update(
            {
                "active": True,
                "session_type": session_type,
                "started_at": started_at,
                "ends_at": ends_at,
                "duration_seconds": duration_seconds,
                "seconds_remaining": duration_seconds,
                "paused": False,
                "pause_started_at": None,
                "current_session_id": session_id,
            }
        )

    _remove_job_if_exists(TICK_JOB_ID)
    _remove_job_if_exists(END_JOB_ID)

    scheduler.add_job(tick, "interval", seconds=1, id=TICK_JOB_ID, replace_existing=True)
    scheduler.add_job(
        end_session,
        "date",
        run_date=ends_at,
        id=END_JOB_ID,
        kwargs={"completed": True},
        replace_existing=True,
    )


def tick() -> None:
    """Update seconds remaining based on end time."""
    with _state_lock:
        if not session_state["active"] or session_state["paused"]:
            return

        ends_at = session_state.get("ends_at")
        if not isinstance(ends_at, datetime):
            return

        remaining = int((ends_at - _utc_now()).total_seconds())
        session_state["seconds_remaining"] = max(0, remaining)


def pause_session() -> None:
    """Pause the active session, stopping scheduler jobs temporarily."""
    with _state_lock:
        if not session_state["active"] or session_state["paused"]:
            return
        session_state["paused"] = True
        session_state["pause_started_at"] = _utc_now()

    _remove_job_if_exists(TICK_JOB_ID)
    _remove_job_if_exists(END_JOB_ID)


def resume_session() -> None:
    """Resume a paused session and shift end time by pause duration."""
    with _state_lock:
        if not session_state["active"] or not session_state["paused"]:
            return

        pause_started = session_state.get("pause_started_at")
        ends_at = session_state.get("ends_at")
        if not isinstance(pause_started, datetime) or not isinstance(ends_at, datetime):
            return

        pause_delta = _utc_now() - pause_started
        new_ends_at = ends_at + pause_delta
        session_state["paused"] = False
        session_state["pause_started_at"] = None
        session_state["ends_at"] = new_ends_at
        session_state["seconds_remaining"] = max(0, int((new_ends_at - _utc_now()).total_seconds()))

    scheduler.add_job(tick, "interval", seconds=1, id=TICK_JOB_ID, replace_existing=True)
    scheduler.add_job(
        end_session,
        "date",
        run_date=session_state["ends_at"],
        id=END_JOB_ID,
        kwargs={"completed": True},
        replace_existing=True,
    )


def end_session(completed: bool = True) -> None:
    """End current session and restore system integrations safely."""
    with _state_lock:
        if not session_state["active"]:
            return
        current_session_id = session_state.get("current_session_id")
        current_type = session_state.get("session_type")

    ended_at = _utc_now()

    if current_session_id is not None:
        with get_session() as db:
            row = db.get(PomodoroSession, int(current_session_id))
            if row is not None:
                row.ended_at = ended_at
                row.completed = bool(completed)

    _safe_call(blocker.unblock_sites)
    _safe_call(macos.disable_dnd)
    _safe_call(macos.undim_windows)

    with _state_lock:
        if completed and current_type == "work":
            session_state["completed_pomodoros"] = int(session_state["completed_pomodoros"]) + 1
            session_state["total_pomodoros"] = int(session_state["total_pomodoros"]) + 1

    title = "Focus Complete" if completed else "Session Ended"
    if current_type == "work" and completed:
        message = "Great work. Time for a break."
    elif current_type in {"short_break", "long_break"} and completed:
        message = "Break complete. Ready for the next focus session."
    else:
        message = "Session was skipped or cancelled."
    _safe_call(macos.show_notification, title, message)

    _remove_job_if_exists(TICK_JOB_ID)
    _remove_job_if_exists(END_JOB_ID)

    with _state_lock:
        if current_type == "long_break" and completed:
            session_state["completed_pomodoros"] = 0

    _set_idle_state()


def get_next_session_type(settings: AppSettings) -> str:
    """Return recommended next session type based on cycle progress."""
    with _state_lock:
        if session_state["active"]:
            return "work"

        completed_cycle = int(session_state.get("completed_pomodoros", 0))

    threshold = max(1, int(settings.long_break_after))
    if completed_cycle > 0 and completed_cycle % threshold == 0:
        return "long_break"
    return "short_break" if completed_cycle > 0 else "work"

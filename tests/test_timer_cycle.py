from app.timer import get_next_session_type, session_state
from app.models import AppSettings


def _settings(long_break_after: int = 4) -> AppSettings:
    return AppSettings(
        work_duration=25,
        short_break=5,
        long_break=15,
        long_break_after=long_break_after,
        block_sites=True,
        enable_dnd=True,
        dim_windows=True,
        dim_opacity=0.5,
    )


def test_next_session_type_returns_work_when_idle_and_no_completed_sessions():
    old_state = dict(session_state)
    try:
        session_state["active"] = False
        session_state["completed_pomodoros"] = 0
        assert get_next_session_type(_settings()) == "work"
    finally:
        session_state.clear()
        session_state.update(old_state)


def test_next_session_type_returns_short_break_between_cycles():
    old_state = dict(session_state)
    try:
        session_state["active"] = False
        session_state["completed_pomodoros"] = 1
        assert get_next_session_type(_settings()) == "short_break"
    finally:
        session_state.clear()
        session_state.update(old_state)


def test_next_session_type_returns_long_break_at_threshold():
    old_state = dict(session_state)
    try:
        session_state["active"] = False
        session_state["completed_pomodoros"] = 4
        assert get_next_session_type(_settings(long_break_after=4)) == "long_break"
    finally:
        session_state.clear()
        session_state.update(old_state)

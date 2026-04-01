"""Database setup and initialization helpers."""

from __future__ import annotations

import random
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import APP_DIR, DB_PATH, DEFAULT_BLOCKLIST, DEFAULT_SETTINGS, DEFAULT_SQLITE_URL

from .models import AppSettings, Base, BlocklistEntry, PomodoroSession

APP_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DEFAULT_SQLITE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a DB session with commit/rollback handling."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed_default_settings(session: Session) -> None:
    existing = session.get(AppSettings, 1)
    if existing is not None:
        return

    session.add(
        AppSettings(
            id=1,
            work_duration=DEFAULT_SETTINGS["work_duration"],
            short_break=DEFAULT_SETTINGS["short_break"],
            long_break=DEFAULT_SETTINGS["long_break"],
            long_break_after=DEFAULT_SETTINGS["long_break_after"],
            block_sites=DEFAULT_SETTINGS["block_sites"],
            enable_dnd=DEFAULT_SETTINGS["enable_dnd"],
            dim_windows=DEFAULT_SETTINGS["dim_windows"],
            dim_opacity=DEFAULT_SETTINGS["dim_opacity"],
        )
    )


def _seed_default_blocklist(session: Session) -> None:
    existing_domains = {
        row[0]
        for row in session.query(BlocklistEntry.domain).all()
    }

    for domain in DEFAULT_BLOCKLIST:
        if domain not in existing_domains:
            session.add(BlocklistEntry(domain=domain, enabled=True))


def init_db() -> Path:
    """Create all tables and seed default rows.

    Returns:
        Path to the SQLite database file.
    """
    APP_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    with get_session() as session:
        _seed_default_settings(session)
        _seed_default_blocklist(session)

    return DB_PATH


def seed_demo_history(days: int = 21) -> int:
    """Seed fake session history for demo mode.

    Returns number of inserted rows. If history already exists, this function
    leaves existing data untouched and returns 0.
    """
    if days <= 0:
        return 0

    with get_session() as session:
        if session.query(PomodoroSession).count() > 0:
            return 0

        now = datetime.now(timezone.utc)
        inserted = 0

        for day_offset in range(days):
            day_start = (now - timedelta(days=day_offset)).replace(hour=8, minute=0, second=0, microsecond=0)
            sessions_today = random.randint(2, 6)

            for slot in range(sessions_today):
                is_work = slot % 2 == 0
                session_type = "work" if is_work else random.choice(["short_break", "long_break"])
                duration = 25 if session_type == "work" else (15 if session_type == "long_break" else 5)
                completed = random.random() > 0.18

                started_at = day_start + timedelta(minutes=slot * random.randint(28, 42))
                ended_at = started_at + timedelta(minutes=duration) if completed else started_at + timedelta(minutes=max(1, duration // 2))

                session.add(
                    PomodoroSession(
                        started_at=started_at,
                        ended_at=ended_at,
                        duration_minutes=duration,
                        session_type=session_type,
                        completed=completed,
                        sites_blocked=is_work,
                        dnd_enabled=is_work,
                    )
                )
                inserted += 1

        return inserted

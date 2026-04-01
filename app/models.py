"""SQLAlchemy ORM models for Focus Mode Controller."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

Base = declarative_base()


class PomodoroSession(Base):
    """A single focus or break session."""

    __tablename__ = "pomodoro_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    session_type: Mapped[str] = mapped_column(String(20), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sites_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dnd_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BlocklistEntry(Base):
    """A user-managed domain blocklist entry."""

    __tablename__ = "blocklist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class AppSettings(Base):
    """Singleton row storing app-level preferences."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_duration: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    short_break: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    long_break: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    long_break_after: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    block_sites: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enable_dnd: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dim_windows: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dim_opacity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

"""Flask routes and API endpoints for Focus Mode Controller."""

from __future__ import annotations

import json
import logging
import re
import time

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

from .database import get_session
from .macos import check_permissions
from .models import AppSettings, BlocklistEntry, PomodoroSession
from .timer import (
    end_session,
    get_next_session_type,
    get_session_state,
    pause_session,
    resume_session,
    start_session,
)

main_bp = Blueprint("main", __name__)

_logger = logging.getLogger("focus_mode.main")

_DOMAIN_SANITIZE_RE = re.compile(r"^https?://", re.IGNORECASE)


def _serialize_settings(settings: AppSettings) -> dict:
    return {
        "id": settings.id,
        "work_duration": settings.work_duration,
        "short_break": settings.short_break,
        "long_break": settings.long_break,
        "long_break_after": settings.long_break_after,
        "block_sites": settings.block_sites,
        "enable_dnd": settings.enable_dnd,
        "dim_windows": settings.dim_windows,
        "dim_opacity": settings.dim_opacity,
    }


def _serialize_blocklist(entry: BlocklistEntry) -> dict:
    return {
        "id": entry.id,
        "domain": entry.domain,
        "enabled": entry.enabled,
        "added_at": entry.added_at.isoformat() if entry.added_at else None,
    }


def _serialize_session(row: PomodoroSession) -> dict:
    return {
        "id": row.id,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "duration_minutes": row.duration_minutes,
        "session_type": row.session_type,
        "completed": row.completed,
        "sites_blocked": row.sites_blocked,
        "dnd_enabled": row.dnd_enabled,
    }


def _get_settings(db_session) -> AppSettings:
    settings = db_session.get(AppSettings, 1)
    if settings is None:
        raise RuntimeError("AppSettings row is missing. Run init_db() first.")
    return settings


def _normalize_domain(raw_domain: str) -> str:
    value = raw_domain.strip().lower()
    value = _DOMAIN_SANITIZE_RE.sub("", value)
    value = value.split("/")[0]
    if value.startswith("www."):
        value = value[4:]
    return value


def _validate_domain(domain: str) -> bool:
    if not domain:
        return False
    if " " in domain:
        return False
    if "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith("."):
        return False
    return True


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        raise ValueError("boolean integer values must be 0 or 1")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    raise ValueError("invalid boolean value")


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/settings")
def settings_page():
    return render_template("settings.html")


@main_bp.route("/history")
def history_page():
    return render_template("history.html")


@main_bp.route("/session/start", methods=["POST"])
def session_start():
    payload = request.get_json(silent=True) or {}
    session_type = payload.get("session_type", "work")

    if session_type not in {"work", "short_break", "long_break"}:
        return jsonify({"error": "Invalid session_type"}), 400

    try:
        with get_session() as db:
            settings = _get_settings(db)
            start_session(session_type, settings)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        _logger.exception("Failed to start session")
        return jsonify({"error": f"Failed to start session: {exc}"}), 500

    return jsonify({"ok": True, "state": get_session_state()})


@main_bp.route("/session/pause", methods=["POST"])
def session_pause():
    pause_session()
    return jsonify({"ok": True, "state": get_session_state()})


@main_bp.route("/session/resume", methods=["POST"])
def session_resume():
    resume_session()
    return jsonify({"ok": True, "state": get_session_state()})


@main_bp.route("/session/skip", methods=["POST"])
def session_skip():
    end_session(completed=False)

    with get_session() as db:
        settings = _get_settings(db)
        next_type = get_next_session_type(settings)

    return jsonify({"ok": True, "next_session_type": next_type, "state": get_session_state()})


@main_bp.route("/stream")
def stream():
    def event_stream():
        last_state = None
        idle_ticks = 0
        try:
            while True:
                current = json.dumps(get_session_state())
                if current != last_state:
                    yield f"data: {current}\n\n"
                    last_state = current
                    idle_ticks = 0
                else:
                    idle_ticks += 1
                    if idle_ticks >= 15:
                        yield ": keepalive\n\n"
                        idle_ticks = 0
                time.sleep(1)
        except GeneratorExit:
            _logger.info("SSE client disconnected")

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@main_bp.route("/api/settings", methods=["GET"])
def api_settings_get():
    with get_session() as db:
        settings = _get_settings(db)
        return jsonify(_serialize_settings(settings))


@main_bp.route("/api/settings", methods=["POST"])
def api_settings_post():
    payload = request.get_json(silent=True) or {}

    with get_session() as db:
        settings = _get_settings(db)

        for key in [
            "work_duration",
            "short_break",
            "long_break",
            "long_break_after",
        ]:
            if key in payload:
                try:
                    value = int(payload[key])
                except (TypeError, ValueError):
                    return jsonify({"error": f"{key} must be an integer"}), 400
                if value <= 0:
                    return jsonify({"error": f"{key} must be > 0"}), 400
                setattr(settings, key, value)

        for key in ["block_sites", "enable_dnd", "dim_windows"]:
            if key in payload:
                try:
                    parsed = _parse_bool(payload[key])
                except ValueError:
                    return jsonify({"error": f"{key} must be a boolean"}), 400
                setattr(settings, key, parsed)

        if "dim_opacity" in payload:
            try:
                opacity = float(payload["dim_opacity"])
            except (TypeError, ValueError):
                return jsonify({"error": "dim_opacity must be a float"}), 400
            if opacity < 0.0 or opacity > 0.8:
                return jsonify({"error": "dim_opacity must be between 0.0 and 0.8"}), 400
            settings.dim_opacity = opacity

        return jsonify({"ok": True, "settings": _serialize_settings(settings)})


@main_bp.route("/api/blocklist", methods=["GET"])
def api_blocklist_get():
    with get_session() as db:
        rows = db.query(BlocklistEntry).order_by(BlocklistEntry.domain.asc()).all()
        return jsonify([_serialize_blocklist(row) for row in rows])


@main_bp.route("/api/blocklist", methods=["POST"])
def api_blocklist_post():
    payload = request.get_json(silent=True) or {}
    domain = _normalize_domain(payload.get("domain", ""))

    if not _validate_domain(domain):
        return jsonify({"error": "Invalid domain"}), 400

    with get_session() as db:
        existing = db.query(BlocklistEntry).filter(BlocklistEntry.domain == domain).first()
        if existing is not None:
            return jsonify({"error": "Domain already exists"}), 409

        row = BlocklistEntry(domain=domain, enabled=True)
        db.add(row)
        db.flush()
        return jsonify({"ok": True, "entry": _serialize_blocklist(row)}), 201


@main_bp.route("/api/blocklist/<int:entry_id>", methods=["DELETE"])
def api_blocklist_delete(entry_id: int):
    with get_session() as db:
        row = db.get(BlocklistEntry, entry_id)
        if row is None:
            return jsonify({"error": "Not found"}), 404
        db.delete(row)
        return jsonify({"ok": True})


@main_bp.route("/api/blocklist/<int:entry_id>", methods=["PATCH"])
def api_blocklist_patch(entry_id: int):
    payload = request.get_json(silent=True) or {}
    with get_session() as db:
        row = db.get(BlocklistEntry, entry_id)
        if row is None:
            return jsonify({"error": "Not found"}), 404

        if "enabled" not in payload:
            row.enabled = not row.enabled
        else:
            try:
                row.enabled = _parse_bool(payload["enabled"])
            except ValueError:
                return jsonify({"error": "enabled must be a boolean"}), 400

        return jsonify({"ok": True, "entry": _serialize_blocklist(row)})


@main_bp.route("/api/history", methods=["GET"])
def api_history_get():
    with get_session() as db:
        rows = (
            db.query(PomodoroSession)
            .order_by(PomodoroSession.started_at.desc())
            .limit(30)
            .all()
        )
        return jsonify([_serialize_session(row) for row in rows])


@main_bp.route("/api/permissions", methods=["GET"])
def api_permissions_get():
    return jsonify(check_permissions())

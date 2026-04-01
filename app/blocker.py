"""Website blocking helpers using /etc/hosts markers."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from config import APP_DIR, LOG_PATH

HOSTS_FILE = "/etc/hosts"
BLOCK_MARKER_START = "# === FOCUS MODE START ==="
BLOCK_MARKER_END = "# === FOCUS MODE END ==="

APP_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("focus_mode.blocker")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = logging.FileHandler(LOG_PATH)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    _logger.addHandler(_handler)


def _hosts_file_path() -> Path:
    """Return the effective hosts file path.

    In demo/testing contexts, this can be overridden with FOCUS_HOSTS_FILE.
    """
    return Path(os.environ.get("FOCUS_HOSTS_FILE", HOSTS_FILE))


def _is_demo_mode() -> bool:
    return os.environ.get("FOCUS_DEMO_MODE", "0") == "1"


def _normalize_domain(domain: str) -> str:
    cleaned = domain.strip().lower()
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned


def _build_block_lines(domains: list[str]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    for domain in domains:
        normalized = _normalize_domain(domain)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        lines.append(f"127.0.0.1 {normalized}\n")
        lines.append(f"127.0.0.1 www.{normalized}\n")

    return lines


def _read_hosts_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return handle.readlines()


def _write_hosts_lines(path: Path, lines: list[str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.writelines(lines)


def block_sites(domains: list[str]) -> None:
    """Append redirect entries between markers to /etc/hosts.

    This function is fault-tolerant: if /etc/hosts is not writable or any
    operation fails, it logs a warning and returns without raising.
    """
    if _is_demo_mode():
        _logger.info("Demo mode active: skipping hosts file block")
        return

    path = _hosts_file_path()

    if not path.exists() or not os.access(path, os.W_OK):
        _logger.warning("Hosts file not writable or missing: %s", path)
        return

    block_lines = _build_block_lines(domains)
    if not block_lines:
        return

    try:
        existing_lines = _read_hosts_lines(path)

        # Replace any existing Focus Mode block to keep entries fresh.
        cleaned_lines: list[str] = []
        in_block = False
        for line in existing_lines:
            stripped = line.strip()
            if stripped == BLOCK_MARKER_START:
                in_block = True
                continue
            if stripped == BLOCK_MARKER_END:
                in_block = False
                continue
            if not in_block:
                cleaned_lines.append(line)

        if cleaned_lines and not cleaned_lines[-1].endswith("\n"):
            cleaned_lines[-1] = cleaned_lines[-1] + "\n"

        cleaned_lines.append(BLOCK_MARKER_START + "\n")
        cleaned_lines.extend(block_lines)
        cleaned_lines.append(BLOCK_MARKER_END + "\n")

        _write_hosts_lines(path, cleaned_lines)
    except Exception as exc:
        _logger.warning("Failed to block sites using %s: %s", path, exc)


def unblock_sites() -> None:
    """Remove all Focus Mode marker-managed host entries and flush DNS."""
    if _is_demo_mode():
        _logger.info("Demo mode active: skipping hosts file unblock")
        return

    path = _hosts_file_path()

    if not path.exists() or not os.access(path, os.W_OK):
        _logger.warning("Hosts file not writable or missing: %s", path)
        return

    try:
        existing_lines = _read_hosts_lines(path)
        updated_lines: list[str] = []
        in_block = False

        for line in existing_lines:
            stripped = line.strip()
            if stripped == BLOCK_MARKER_START:
                in_block = True
                continue
            if stripped == BLOCK_MARKER_END:
                in_block = False
                continue
            if not in_block:
                updated_lines.append(line)

        _write_hosts_lines(path, updated_lines)

        # DNS flush errors should not fail the app lifecycle.
        try:
            subprocess.run(["dscacheutil", "-flushcache"], check=False)
            subprocess.run(["killall", "-HUP", "mDNSResponder"], check=False)
        except Exception as exc:
            _logger.warning("Failed to flush DNS cache: %s", exc)
    except Exception as exc:
        _logger.warning("Failed to unblock sites using %s: %s", path, exc)


def get_blocked_domains() -> list[str]:
    """Return currently blocked domains from the marker block in /etc/hosts."""
    path = _hosts_file_path()

    if not path.exists():
        _logger.warning("Hosts file missing when reading blocked domains: %s", path)
        return []

    try:
        lines = _read_hosts_lines(path)
        in_block = False
        domains: set[str] = set()

        for line in lines:
            stripped = line.strip()
            if stripped == BLOCK_MARKER_START:
                in_block = True
                continue
            if stripped == BLOCK_MARKER_END:
                in_block = False
                continue

            if not in_block or not stripped or stripped.startswith("#"):
                continue

            parts = stripped.split()
            if len(parts) >= 2 and parts[0] == "127.0.0.1":
                domains.add(_normalize_domain(parts[1]))

        return sorted(domain for domain in domains if domain)
    except Exception as exc:
        _logger.warning("Failed to read blocked domains from %s: %s", path, exc)
        return []

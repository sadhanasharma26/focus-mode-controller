# Focus Mode Controller (macOS)

A local-only Flask + vanilla JS productivity app for Pomodoro sessions with macOS integrations.

## Features

- Pomodoro lifecycle with live countdown via Server-Sent Events (SSE)
- Automatic website blocking by editing `/etc/hosts` (marker-based)
- Automatic Do Not Disturb enable/disable (Shortcuts first, AppleScript fallback)
- Optional window dim overlay (best-effort via Hammerspoon CLI)
- Session history, stats, and chart visualization
- Settings and blocklist management UI
- Fully local runtime (no cloud services, no accounts)

## Project Structure

```text
focus-mode/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── timer.py
│   ├── blocker.py
│   ├── macos.py
│   ├── database.py
│   └── models.py
├── static/
│   ├── app.js
│   ├── settings.js
│   ├── history.js
│   └── style.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── settings.html
│   └── history.html
├── menubar.py
├── config.py
├── requirements.txt
├── run.py
└── README.md
```

## Requirements

- macOS
- Python 3.11+
- Terminal access with `sudo`

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run database initialization implicitly by launching the app (it auto-creates `~/.focus-mode/focus.db`).

## Run

### Normal mode

Use `sudo` so `/etc/hosts` edits can work:

```bash
sudo python run.py --port 5000
```

Open `http://127.0.0.1:5000`.

### Demo mode (safe testing)

```bash
python run.py --demo --port 5000
```

Demo mode behavior:

- Seeds 21 days of fake session history
- Uses 10-second sessions for fast testing
- Does not edit `/etc/hosts`
- Does not run osascript/shortcuts system effects

## Permissions and macOS Integration

### 1) `/etc/hosts` write permission

- Required for real site blocking
- Launch app with `sudo` in normal mode

If not writable, the app logs a warning and continues without crashing.

### 2) Accessibility permission (for automation/dimming checks)

Grant access at:

- `System Settings` -> `Privacy & Security` -> `Accessibility`
- Enable the terminal app (and/or Python host you use to launch the app)

If not granted, dimming/automation gracefully skips and UI shows warnings.

### 3) Do Not Disturb Shortcuts (recommended)

Create two macOS Shortcuts with exact names:

- `Enable Do Not Disturb`
- `Disable Do Not Disturb`

Then verify in terminal:

```bash
shortcuts list
```

The app tries these first, then falls back to AppleScript best-effort behavior.

## Logging

Errors/warnings from integrations are written to:

- `~/.focus-mode/focus.log`

Failures are isolated (blocking, DND, dimming fail independently) and do not crash Flask.

## Optional Menubar App

`menubar.py` provides a minimal menu bar icon using `rumps`.

Run:

```bash
python menubar.py
```

Menu options:

- `Open App` (opens browser to `http://127.0.0.1:5000`)
- `Quit`

## Notes

- Chart rendering uses Chart.js from CDN on the History page.
- All app data is local in `~/.focus-mode/`.
- SSE endpoint: `GET /stream`

## Quick API Regression Check

After starting the app, run:

```bash
./scripts/api_smoke.sh
```

Custom base URL (if using a different port):

```bash
./scripts/api_smoke.sh http://127.0.0.1:5050
```

This script uses `curl` to verify key pages and APIs:

- Session controls
- Settings CRUD
- Blocklist add/toggle/delete
- History and permissions endpoints

### One-command Demo Smoke Flow

Start app in demo mode, run smoke checks, then stop automatically:

```bash
./scripts/smoke_demo.sh
```

Custom port:

```bash
./scripts/smoke_demo.sh 5051
```


#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:5000}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() {
  printf '[PASS] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1"
  exit 1
}

request() {
  local method="$1"
  local path="$2"
  local data=""
  local out_file=""

  if [[ "$#" -eq 3 ]]; then
    out_file="$3"
  elif [[ "$#" -ge 4 ]]; then
    data="$3"
    out_file="$4"
  else
    fail "request() expected 3 or 4 args, got $#"
  fi

  if [[ -n "$data" ]]; then
    curl -sS -o "$out_file" -w '%{http_code}' \
      -X "$method" \
      -H 'Content-Type: application/json' \
      --data "$data" \
      "$BASE_URL$path"
  else
    curl -sS -o "$out_file" -w '%{http_code}' \
      -X "$method" \
      "$BASE_URL$path"
  fi
}

expect_status() {
  local label="$1"
  local expected="$2"
  local actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    pass "$label ($actual)"
  else
    fail "$label expected $expected got $actual"
  fi
}

expect_body_has() {
  local label="$1"
  local needle="$2"
  local file="$3"
  if grep -q "$needle" "$file"; then
    pass "$label"
  else
    fail "$label missing '$needle'"
  fi
}

extract_json_field() {
  local file="$1"
  local field="$2"

  if command -v jq >/dev/null 2>&1; then
    jq -r "$field" "$file" 2>/dev/null || true
    return
  fi

  python3 - "$file" "$field" <<'PY' 2>/dev/null || true
import json
import sys

path = sys.argv[1]
field = sys.argv[2]

with open(path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

if not field.startswith("."):
    raise SystemExit(1)

value = payload
for token in field[1:].split("."):
    if token == "":
        continue
    if isinstance(value, dict):
        value = value.get(token)
    else:
        value = None
        break

if value is None:
    raise SystemExit(1)

print(value)
PY
}

printf 'Running API smoke tests against %s\n' "$BASE_URL"

# Pages
status="$(request GET / "$TMP_DIR/root.html")"
expect_status 'GET /' 200 "$status"

status="$(request GET /settings "$TMP_DIR/settings.html")"
expect_status 'GET /settings' 200 "$status"

status="$(request GET /history "$TMP_DIR/history.html")"
expect_status 'GET /history' 200 "$status"

# Settings
status="$(request GET /api/settings "$TMP_DIR/settings.json")"
expect_status 'GET /api/settings' 200 "$status"
expect_body_has 'Settings payload includes work_duration' 'work_duration' "$TMP_DIR/settings.json"

status="$(request POST /api/settings '{"work_duration":25,"short_break":5,"long_break":15,"long_break_after":4,"dim_opacity":0.5}' "$TMP_DIR/settings_update.json")"
expect_status 'POST /api/settings' 200 "$status"
expect_body_has 'Settings update response includes ok' '"ok":true' "$TMP_DIR/settings_update.json"

# Blocklist
status="$(request GET /api/blocklist "$TMP_DIR/blocklist.json")"
expect_status 'GET /api/blocklist' 200 "$status"

rnd_domain="smoketest-$RANDOM.example.com"
status="$(request POST /api/blocklist "{\"domain\":\"$rnd_domain\"}" "$TMP_DIR/blocklist_add.json")"
expect_status 'POST /api/blocklist' 201 "$status"
expect_body_has 'Added blocklist entry contains domain' "$rnd_domain" "$TMP_DIR/blocklist_add.json"

entry_id="$(extract_json_field "$TMP_DIR/blocklist_add.json" '.entry.id')"
if [[ -z "$entry_id" ]]; then
  fail 'Unable to parse blocklist entry id from add response'
fi
pass "Parsed blocklist entry id: $entry_id"

status="$(request PATCH "/api/blocklist/$entry_id" '{"enabled":false}' "$TMP_DIR/blocklist_patch.json")"
expect_status 'PATCH /api/blocklist/<id>' 200 "$status"
expect_body_has 'Blocklist patch response includes enabled false' '"enabled":false' "$TMP_DIR/blocklist_patch.json"

status="$(request DELETE "/api/blocklist/$entry_id" '' "$TMP_DIR/blocklist_delete.json")"
expect_status 'DELETE /api/blocklist/<id>' 200 "$status"

# Session controls
status="$(request POST /session/start '{"session_type":"work"}' "$TMP_DIR/session_start.json")"
expect_status 'POST /session/start' 200 "$status"
expect_body_has 'Session start response includes active state' '"active":true' "$TMP_DIR/session_start.json"

status="$(request POST /session/pause '' "$TMP_DIR/session_pause.json")"
expect_status 'POST /session/pause' 200 "$status"

status="$(request POST /session/resume '' "$TMP_DIR/session_resume.json")"
expect_status 'POST /session/resume' 200 "$status"

status="$(request POST /session/skip '' "$TMP_DIR/session_skip.json")"
expect_status 'POST /session/skip' 200 "$status"
expect_body_has 'Session skip response includes next_session_type' 'next_session_type' "$TMP_DIR/session_skip.json"

# History + permissions
status="$(request GET /api/history "$TMP_DIR/history.json")"
expect_status 'GET /api/history' 200 "$status"

status="$(request GET /api/permissions "$TMP_DIR/permissions.json")"
expect_status 'GET /api/permissions' 200 "$status"
expect_body_has 'Permissions response includes hosts_writable' 'hosts_writable' "$TMP_DIR/permissions.json"

printf '\nAll smoke checks passed.\n'

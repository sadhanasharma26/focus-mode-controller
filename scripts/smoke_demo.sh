#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-5050}"
BASE_URL="http://127.0.0.1:${PORT}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
SERVER_LOG="$(mktemp)"
SERVER_PID=""

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  rm -f "${SERVER_LOG}"
}
trap cleanup EXIT

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[FAIL] Python executable not found at ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -x "./scripts/api_smoke.sh" ]]; then
  echo "[FAIL] ./scripts/api_smoke.sh is missing or not executable" >&2
  exit 1
fi

echo "Starting demo server on ${BASE_URL}..."
"${PYTHON_BIN}" run.py --demo --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
SERVER_PID="$!"

ready="0"
for _ in $(seq 1 40); do
  if curl -sS "${BASE_URL}/api/settings" >/dev/null 2>&1; then
    ready="1"
    break
  fi
  sleep 0.5
done

if [[ "${ready}" != "1" ]]; then
  echo "[FAIL] Demo server did not become ready in time" >&2
  echo "--- server log ---" >&2
  cat "${SERVER_LOG}" >&2
  exit 1
fi

echo "Server is ready. Running API smoke checks..."
./scripts/api_smoke.sh "${BASE_URL}"

echo "Demo smoke flow complete."

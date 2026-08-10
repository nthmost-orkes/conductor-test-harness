#!/usr/bin/env bash
# Stop a local test server started by start-test-server.sh.
# Usage: scripts/stop-test-server.sh [--port N]   (default 7010)
set -euo pipefail

PORT=7010
while [[ $# -gt 0 ]]; do case "$1" in
  --port) PORT="$2"; shift 2;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done

PID="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [[ -z "$PID" ]]; then
  echo "No server listening on :$PORT"
  exit 0
fi
echo "Stopping server on :$PORT (pid $PID)…"
kill "$PID"
for _ in $(seq 1 15); do
  lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || { echo "Stopped."; exit 0; }
  sleep 1
done
echo "Still up after 15s; sending SIGKILL." >&2
kill -9 "$PID" 2>/dev/null || true

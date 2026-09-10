#!/usr/bin/env bash
#
# javascript-sdk integration:oss smoke against a running Conductor server.
# Invoked by validate-image.sh (which brings up the SDK's compose stack with our
# freshly-built image). Inputs via env:
#   JS_SDK       javascript-sdk checkout
#   SERVER_API   server API base incl. /api (e.g. http://localhost:8130/api)
#   RUNDIR       where to drop junit + logs
#   HARNESS_DIR  harness root (for classifier + known-issues)
#
# Uses the SDK's own `test:integration:oss` script, which sets
# CONDUCTOR_SERVER_TYPE=oss so the suite's describeForOrkesOnly* blocks
# auto-skip Orkes-only tests. That means NO skip list to maintain here — the
# mismatch guard is upstream. A failure matching js/known-issues.txt is
# KNOWN-ISSUE, not a battery FAIL.
#
# Exit: 0 pass · 1 real failures · 2 inconclusive (nothing ran / all skipped)
#
set -uo pipefail
: "${JS_SDK:?}"; : "${SERVER_API:?}"; : "${RUNDIR:?}"; : "${HARNESS_DIR:?}"

export PATH="$HOME/.local/node/bin:$PATH"
export CONDUCTOR_SERVER_URL="$SERVER_API"
export CONDUCTOR_SERVER_TYPE="oss"           # gates Orkes-only tests out
export HTTPBIN_SERVICE_HOSTNAME="httpbin"     # server reaches httpbin over the compose net
export CONDUCTOR_REQUEST_TIMEOUT_MS="300000"
export CONDUCTOR_RETRY_SERVER_ERRORS="true"
export JEST_JUNIT_OUTPUT_DIR="$RUNDIR"
export JEST_JUNIT_OUTPUT_NAME="js-junit.xml"

echo "== javascript-sdk integration:oss =="
echo "server: $SERVER_API"
echo "sdk:    $JS_SDK ($(cd "$JS_SDK" && git rev-parse --short HEAD 2>/dev/null))"
echo "node:   $(node --version)  npm: $(npm --version)"

cd "$JS_SDK"
echo "npm ci…"
if ! npm ci > "$RUNDIR/js-npm-ci.log" 2>&1; then
  echo "npm ci failed — see js-npm-ci.log"; tail -20 "$RUNDIR/js-npm-ci.log"; exit 1
fi

npm run test:integration:oss -- --ci --runInBand --testTimeout=300000 \
  --reporters=default --reporters=jest-junit || true

echo "== classify =="
python3 "$HARNESS_DIR/sdk-smoke/lib/classify_junit.py" \
  "$RUNDIR/js-junit.xml" "$HARNESS_DIR/sdk-smoke/js/known-issues.txt"

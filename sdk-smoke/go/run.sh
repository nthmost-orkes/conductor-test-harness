#!/usr/bin/env bash
#
# go-sdk integration_tests smoke against a running Conductor server.
# Invoked by validate-image.sh. Inputs via env:
#   GO_SDK       go-sdk checkout
#   SERVER_API   server API base incl. /api  (e.g. http://localhost:8090/api)
#   RUNDIR       where to drop test json + logs
#   HARNESS_DIR  harness root (for classifier + skip/known-issue lists)
#
# Enterprise tests self-skip via RequireAtLeast(version); oss-skip.txt adds a
# belt-and-suspenders skip regex. A failure matching go/known-issues.txt is
# KNOWN-ISSUE, not a battery FAIL.
#
# Exit: 0 pass · 1 real failures · 2 inconclusive (nothing ran / all gated)
#
set -uo pipefail
: "${GO_SDK:?}"; : "${SERVER_API:?}"; : "${RUNDIR:?}"; : "${HARNESS_DIR:?}"

export PATH="$HOME/.local/go/bin:/usr/local/go/bin:$PATH"
export CONDUCTOR_SERVER_URL="$SERVER_API"

SKIP_RE="$(grep -vE '^\s*(#|$)' "$HARNESS_DIR/sdk-smoke/go/oss-skip.txt" 2>/dev/null | paste -sd'|' -)"

echo "== go-sdk integration smoke =="
echo "server:   $SERVER_API"
echo "sdk:      $GO_SDK ($(cd "$GO_SDK" && git rev-parse --short HEAD 2>/dev/null))"
echo "go:       $(go version 2>/dev/null)"
echo "skip:     /${SKIP_RE}/"

cd "$GO_SDK"
go mod download > "$RUNDIR/go-mod.log" 2>&1 || echo "warn: go mod download issues (see go-mod.log)"

# -json for machine parsing; -skip needs Go >=1.20 (loki has 1.23).
go test -count=1 -json ${SKIP_RE:+-skip "$SKIP_RE"} ./test/integration_tests/... \
  > "$RUNDIR/go-test.json" 2> "$RUNDIR/go-test.err" || true

echo "== classify =="
python3 "$HARNESS_DIR/sdk-smoke/lib/classify_go.py" \
  "$RUNDIR/go-test.json" "$HARNESS_DIR/sdk-smoke/go/known-issues.txt"

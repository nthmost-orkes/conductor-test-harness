#!/usr/bin/env bash
#
# python-sdk core-bucket smoke against a running Conductor server.
# Invoked by validate-image.sh. Inputs via env:
#   PYTHON_SDK   python-sdk checkout
#   SERVER_API   server API base incl. /api  (e.g. http://localhost:8090/api)
#   RUNDIR       where to drop junit + logs
#   HARNESS_DIR  harness root (for classifier + known-issues)
#
# Runs tests/integration --bucket=core (AI/agent suites already excluded by the
# SDK's own runner). Classifies the JUnit result; a failure matching
# python/known-issues.txt is KNOWN-ISSUE, not a battery FAIL.
#
# Exit: 0 pass · 1 real failures · 2 inconclusive (server unreachable/all skipped)
#
set -uo pipefail
: "${PYTHON_SDK:?}"; : "${SERVER_API:?}"; : "${RUNDIR:?}"; : "${HARNESS_DIR:?}"

CACHE="${SDK_VENV_DIR:-$HOME/.cache/conductor-validate}"
VENV="$CACHE/py-venv"
JUNIT="$RUNDIR/python-junit.xml"

echo "== python-sdk core smoke =="
echo "server:   $SERVER_API"
echo "sdk:      $PYTHON_SDK ($(cd "$PYTHON_SDK" && git rev-parse --short HEAD 2>/dev/null))"

mkdir -p "$CACHE"
python3 -m venv "$VENV" 2>/dev/null || true
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install -q --upgrade pip >/dev/null 2>&1
echo "installing sdk + test deps (editable)…"
if ! python -m pip install -q -e "$PYTHON_SDK" pytest pytest-asyncio pytest-xdist pytest-rerunfailures \
      > "$RUNDIR/py-install.log" 2>&1; then
  echo "pip install failed — see py-install.log"; tail -20 "$RUNDIR/py-install.log"; exit 1
fi

export CONDUCTOR_SERVER_URL="$SERVER_API"
export CONDUCTOR_HTTP2_ENABLED="false"

cd "$PYTHON_SDK"

# Build a pytest -k exclusion for Orkes-only test classes (see oss-skip.txt).
SKIPF="$HARNESS_DIR/sdk-smoke/python/oss-skip.txt"
KEXPR="$(awk '!/^[[:space:]]*(#|$)/{a=a (a?" or ":"") $0} END{print a}' "$SKIPF" 2>/dev/null)"
kargs=()
[[ -n "$KEXPR" ]] && { kargs=(-k "not ($KEXPR)"); echo "excluding (Orkes-only): $KEXPR"; }

# -p no:conductor-agents-testing avoids autoloading the agents pytest plugin
# (needs the heavy [agents] extra; the core bucket doesn't use it).
bash scripts/run_integration_tests.sh --bucket=core \
  -p no:conductor-agents-testing \
  -o cache_dir="$CACHE/pytest" \
  "${kargs[@]}" \
  "--junitxml=$JUNIT" -o junit_family=xunit2 || true

echo "== classify =="
python3 "$HARNESS_DIR/sdk-smoke/lib/classify_junit.py" \
  "$JUNIT" "$HARNESS_DIR/sdk-smoke/python/known-issues.txt"

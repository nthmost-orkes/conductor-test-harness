#!/usr/bin/env bash
#
# conductor-cli OSS smoke against a running Conductor server.
# Invoked by validate-image.sh. Inputs via env:
#   SERVER_API   server API base incl. /api (e.g. http://localhost:8092/api)
#   RUNDIR       where to drop logs
#   HARNESS_DIR  harness root
#   CLI_BIN      (optional) path to a `conductor` binary to test; else installed via npm
#
# Drives the `conductor` binary as an OSS client: task + workflow CRUD, a real
# register→start→poll(COMPLETED) execution (SET_VARIABLE completes inline, no
# worker needed), and a positive check that Orkes-only commands self-gate under
# CONDUCTOR_SERVER_TYPE=OSS (secret list must refuse locally, not 404 the server).
#
# Exit: 0 pass · 1 real failures · 2 inconclusive (CLI unavailable / server down)
#
set -uo pipefail
: "${SERVER_API:?}"; : "${RUNDIR:?}"; : "${HARNESS_DIR:?}"

export PATH="$HOME/.local/node/bin:$PATH"
export CONDUCTOR_SERVER_URL="$SERVER_API"
export CONDUCTOR_SERVER_TYPE="OSS"      # makes the CLI self-gate Orkes-only commands

# Resolve (or install) the conductor binary. Testing the released CLI is the most
# representative client check; override with CLI_BIN=/path to test a built binary.
CLI="${CLI_BIN:-conductor}"
if ! command -v "$CLI" >/dev/null 2>&1; then
  echo "installing @conductor-oss/conductor-cli via npm (user-local)…"
  if ! npm install -g @conductor-oss/conductor-cli > "$RUNDIR/cli-install.log" 2>&1; then
    echo "cli install failed — see cli-install.log"; tail -20 "$RUNDIR/cli-install.log"; exit 2
  fi
  CLI=conductor
fi
command -v "$CLI" >/dev/null 2>&1 || { echo "conductor binary not found after install"; exit 2; }

echo "== conductor-cli OSS smoke =="
echo "server: $SERVER_API"
echo "cli:    $(command -v "$CLI")  ($("$CLI" --version 2>/dev/null | head -1))"

PASS=0; FAIL=0
ok(){ echo "  PASS $1"; PASS=$((PASS+1)); }
no(){ echo "  FAIL $1: ${2:-}"; FAIL=$((FAIL+1)); }

SFX="$(date +%H%M%S)"
WF="cli_smoke_wf_$SFX"; TASKDEF="cli_smoke_task_$SFX"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/task.json" <<JSON
{"name":"$TASKDEF","retryCount":1,"timeoutSeconds":600,"responseTimeoutSeconds":180,"ownerEmail":"harness@orkes.io"}
JSON
cat > "$WORK/wf.json" <<JSON
{"name":"$WF","version":1,"schemaVersion":2,
 "tasks":[{"name":"cli_sv","taskReferenceName":"sv","type":"SET_VARIABLE","inputParameters":{"ok":"true"}}]}
JSON

# --version already exercised above.
[ -n "$("$CLI" --version 2>/dev/null)" ] && ok "version" || no "version"

"$CLI" task create "$WORK/task.json" >/dev/null 2>&1 && ok "task create" || no "task create"
"$CLI" task list 2>/dev/null | grep -q "$TASKDEF" && ok "task list" || no "task list"
"$CLI" task get "$TASKDEF" 2>/dev/null | grep -q "$TASKDEF" && ok "task get" || no "task get"

"$CLI" workflow create "$WORK/wf.json" --force >/dev/null 2>&1 && ok "workflow create" || no "workflow create"
"$CLI" workflow list 2>/dev/null | grep -q "$WF" && ok "workflow list" || no "workflow list"

WFID="$("$CLI" workflow start --workflow "$WF" --input '{}' 2>/dev/null | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' | head -1)"
if [ -n "$WFID" ]; then ok "workflow start ($WFID)"; else no "workflow start" "no execution id"; fi

if [ -n "$WFID" ]; then
  st=""; for _ in $(seq 1 15); do
    st="$("$CLI" workflow status "$WFID" 2>/dev/null | tr -d '[:space:]')"
    [ "$st" = COMPLETED ] || [ "$st" = FAILED ] || [ "$st" = TERMINATED ] && break
    sleep 2
  done
  [ "$st" = COMPLETED ] && ok "workflow reached COMPLETED" || no "workflow status" "terminal=$st"
  "$CLI" workflow get-execution "$WFID" 2>/dev/null | grep -q workflowId && ok "workflow get-execution" || no "workflow get-execution"
fi

# Positive gating check: with --server-type OSS the CLI must refuse Orkes-only
# commands locally (clean 'Enterprise' message), NOT hit the server and 404.
out="$("$CLI" secret list 2>&1)"; rc=$?
if [ $rc -ne 0 ] && echo "$out" | grep -qiE 'enterprise|orkes|not supported'; then
  ok "orkes-only self-gated (secret list refused locally)"
else
  no "orkes gating" "secret list rc=$rc out=$(echo "$out" | head -1)"
fi

echo "tests=$((PASS+FAIL)) passed=$PASS failed=$FAIL"
(( PASS + FAIL == 0 )) && exit 2
(( FAIL > 0 )) && exit 1 || exit 0

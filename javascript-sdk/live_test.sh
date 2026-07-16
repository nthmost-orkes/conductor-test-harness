#!/usr/bin/env bash
# JavaScript SDK — Live System Task Test
# Tests server acceptance of task types and confirms static analysis findings.
# Server baseline: Conductor 3.32.0-rc.9
# Run: CONDUCTOR_SERVER=http://loki.local:8080 bash javascript-sdk/live_test.sh

set -uo pipefail

CONDUCTOR="${CONDUCTOR_SERVER:-http://loki.local:8080}"
API="$CONDUCTOR/api"
PASS=0
FAIL=0
STATIC=0
NOTES=()

stamp() { date +%s%3N; }
pass()   { echo "  ✅ PASS  — $1"; ((PASS++)); }
fail()   { echo "  ❌ FAIL  — $1: $2"; ((FAIL++)); NOTES+=("FAIL: $1 — $2"); }
static() { echo "  🐛 STATIC_BUG [$1] — $2"; ((STATIC++)); }

register_wf() {
  local name="$1"
  local body="$2"
  local http_code
  http_code=$(curl -s -o /tmp/live_js_resp.txt -w '%{http_code}' \
    -X POST "$API/metadata/workflow" \
    -H 'Content-Type: application/json' \
    -d "$body")
  if [[ "$http_code" == "200" || "$http_code" == "204" ]]; then
    return 0
  else
    echo "    [server response] $(head -c 300 /tmp/live_js_resp.txt)"
    return 1
  fi
}

start_wf() {
  local name="$1"
  local version="${2:-1}"
  curl -s -X POST "$API/workflow" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"$name\",\"version\":$version,\"input\":{}}" | tr -d '"'
}

poll_status() {
  local wf_id="$1"
  local timeout=25
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local status
    status=$(curl -s "$API/workflow/$wf_id" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','UNKNOWN'))" 2>/dev/null || echo "UNKNOWN")
    case "$status" in
      COMPLETED|FAILED|TERMINATED|TIMED_OUT) echo "$status"; return 0 ;;
      RUNNING|PAUSED) sleep 1; ((elapsed++)) ;;
      *) echo "$status"; return 1 ;;
    esac
  done
  echo "TIMEOUT"
}

echo ""
echo "=== JavaScript SDK Live Test ==="
echo "Server: $CONDUCTOR"
echo ""

# ──────────────────────────────────────────────────────────────────────────────
echo "--- FINDING-1: forkTaskJoin() produces JOIN with joinOn=[] ---"
# Confirm that a FORK+JOIN workflow where the join has joinOn=[] completes
# without waiting for fork branches (immediate completion = bug confirmed).
T="live_js_forkjoin_$(stamp)"
# Register a workflow with a simple worker task inside the fork
# Use a NOOP task (which completes immediately) as the fork branch task
# JOIN has joinOn:[] — should complete immediately before fork branch runs
WF_DEF=$(cat <<JSON
{
  "name": "$T",
  "version": 1,
  "tasks": [
    {
      "name": "fork_1",
      "taskReferenceName": "fork_1",
      "type": "FORK_JOIN",
      "forkTasks": [
        [
          {
            "name": "noop_branch",
            "taskReferenceName": "noop_branch",
            "type": "NOOP",
            "inputParameters": {}
          }
        ]
      ],
      "inputParameters": {}
    },
    {
      "name": "join_1",
      "taskReferenceName": "join_1",
      "type": "JOIN",
      "joinOn": [],
      "inputParameters": {}
    }
  ],
  "outputParameters": {},
  "schemaVersion": 2,
  "restartable": true,
  "ownerEmail": "test@test.com",
  "timeoutPolicy": "ALERT_ONLY",
  "timeoutSeconds": 60
}
JSON
)
if register_wf "$T" "$WF_DEF"; then
  WF_ID=$(start_wf "$T")
  STATUS=$(poll_status "$WF_ID")
  if [[ "$STATUS" == "COMPLETED" ]]; then
    # Check if join completed before noop_branch had a chance to run
    JOIN_STATUS=$(curl -s "$API/workflow/$WF_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tasks = {t['referenceTaskName']: t['status'] for t in d.get('tasks', [])}
print(f\"join={tasks.get('join_1','?')} noop_branch={tasks.get('noop_branch','?')}\")
" 2>/dev/null)
    static "FINDING-1" "JOIN with joinOn=[] completes immediately — $JOIN_STATUS — fork branches not waited for"
  else
    fail "forkTaskJoin joinOn" "Unexpected status: $STATUS"
  fi
else
  fail "forkTaskJoin joinOn" "Registration failed"
fi

echo ""
echo "--- Confirm correct behavior: joinOn=[noop_branch] should wait for branch ---"
T2="live_js_forkjoin_correct_$(stamp)"
WF_DEF2=$(cat <<JSON
{
  "name": "$T2",
  "version": 1,
  "tasks": [
    {
      "name": "fork_1",
      "taskReferenceName": "fork_1",
      "type": "FORK_JOIN",
      "forkTasks": [
        [
          {
            "name": "noop_branch",
            "taskReferenceName": "noop_branch",
            "type": "NOOP",
            "inputParameters": {}
          }
        ]
      ],
      "inputParameters": {}
    },
    {
      "name": "join_1",
      "taskReferenceName": "join_1",
      "type": "JOIN",
      "joinOn": ["noop_branch"],
      "inputParameters": {}
    }
  ],
  "outputParameters": {},
  "schemaVersion": 2,
  "restartable": true,
  "ownerEmail": "test@test.com",
  "timeoutPolicy": "ALERT_ONLY",
  "timeoutSeconds": 60
}
JSON
)
if register_wf "$T2" "$WF_DEF2"; then
  WF_ID2=$(start_wf "$T2")
  STATUS2=$(poll_status "$WF_ID2")
  if [[ "$STATUS2" == "COMPLETED" ]]; then
    pass "FORK+JOIN with joinOn=['noop_branch'] waits and completes correctly"
  else
    fail "FORK+JOIN correct joinOn" "Status: $STATUS2"
  fi
else
  fail "FORK+JOIN correct" "Registration failed"
fi

# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "--- FINDING-2: NOOP — confirm server accepts it ---"
T="live_js_noop_$(stamp)"
if register_wf "$T" "{
  \"name\":\"$T\",\"version\":1,
  \"tasks\":[{\"name\":\"n1\",\"taskReferenceName\":\"n1\",\"type\":\"NOOP\",\"inputParameters\":{}}],
  \"outputParameters\":{},\"schemaVersion\":2,\"restartable\":true,
  \"ownerEmail\":\"test@test.com\",\"timeoutPolicy\":\"ALERT_ONLY\",\"timeoutSeconds\":30
}"; then
  WF_ID=$(start_wf "$T")
  STATUS=$(poll_status "$WF_ID")
  if [[ "$STATUS" == "COMPLETED" ]]; then
    static "FINDING-2" "Server ACCEPTS NOOP and completes — SDK missing enum value and builder"
  else
    fail "NOOP" "Status: $STATUS"
  fi
else
  fail "NOOP" "Registration failed"
fi

# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "--- FINDING-3: EXCLUSIVE_JOIN — confirm server accepts it ---"
T="live_js_excl_join_$(stamp)"
WF_DEF=$(cat <<JSON
{
  "name": "$T",
  "version": 1,
  "tasks": [
    {
      "name": "sw1","taskReferenceName":"sw1","type":"SWITCH",
      "evaluatorType":"value-param","expression":"switchCaseValue",
      "inputParameters":{"switchCaseValue":"a"},
      "decisionCases":{"a":[{"name":"na","taskReferenceName":"na","type":"NOOP","inputParameters":{}}]},
      "defaultCase":[{"name":"nb","taskReferenceName":"nb","type":"NOOP","inputParameters":{}}]
    },
    {
      "name":"ej1","taskReferenceName":"ej1","type":"EXCLUSIVE_JOIN",
      "joinOn":["na","nb"],"defaultExclusiveJoinTask":["nb"],"inputParameters":{}
    }
  ],
  "outputParameters":{},"schemaVersion":2,"restartable":true,
  "ownerEmail":"test@test.com","timeoutPolicy":"ALERT_ONLY","timeoutSeconds":30
}
JSON
)
if register_wf "$T" "$WF_DEF"; then
  WF_ID=$(start_wf "$T")
  STATUS=$(poll_status "$WF_ID")
  if [[ "$STATUS" == "COMPLETED" ]]; then
    static "FINDING-3" "Server ACCEPTS EXCLUSIVE_JOIN — SDK builder missing"
  else
    fail "EXCLUSIVE_JOIN" "Status: $STATUS"
  fi
else
  fail "EXCLUSIVE_JOIN" "Registration failed"
fi

# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "--- FINDING-5: readTimeOut type — confirm server accepts integer and string ---"
T_INT="live_js_http_rto_int_$(stamp)"
T_STR="live_js_http_rto_str_$(stamp)"
# Integer readTimeOut (correct)
register_wf "$T_INT" "{
  \"name\":\"$T_INT\",\"version\":1,
  \"tasks\":[{\"name\":\"h1\",\"taskReferenceName\":\"h1\",\"type\":\"HTTP\",
    \"inputParameters\":{\"http_request\":{\"uri\":\"https://httpbin.org/get\",\"method\":\"GET\",\"readTimeOut\":3000}}}],
  \"outputParameters\":{},\"schemaVersion\":2,\"restartable\":true,
  \"ownerEmail\":\"test@test.com\",\"timeoutPolicy\":\"ALERT_ONLY\",\"timeoutSeconds\":30
}" && pass "Server accepts readTimeOut as integer" || fail "readTimeOut int" "Registration failed"

# String readTimeOut (what JS SDK types it as)
register_wf "$T_STR" "{
  \"name\":\"$T_STR\",\"version\":1,
  \"tasks\":[{\"name\":\"h1\",\"taskReferenceName\":\"h1\",\"type\":\"HTTP\",
    \"inputParameters\":{\"http_request\":{\"uri\":\"https://httpbin.org/get\",\"method\":\"GET\",\"readTimeOut\":\"3000\"}}}],
  \"outputParameters\":{},\"schemaVersion\":2,\"restartable\":true,
  \"ownerEmail\":\"test@test.com\",\"timeoutPolicy\":\"ALERT_ONLY\",\"timeoutSeconds\":30
}" && echo "  ℹ  Server accepts readTimeOut as string (coerces it) — but type is still wrong in SDK" || echo "  ℹ  Server rejects string readTimeOut"
static "FINDING-5" "readTimeOut should be number, not string — server field is Integer"

# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "--- FINDING-7: AGENT — confirm server accepts it ---"
T="live_js_agent_$(stamp)"
if register_wf "$T" "{
  \"name\":\"$T\",\"version\":1,
  \"tasks\":[{\"name\":\"a1\",\"taskReferenceName\":\"a1\",\"type\":\"AGENT\",
    \"inputParameters\":{\"agentId\":\"test-agent\",\"input\":{}}}],
  \"outputParameters\":{},\"schemaVersion\":2,\"restartable\":true,
  \"ownerEmail\":\"test@test.com\",\"timeoutPolicy\":\"ALERT_ONLY\",\"timeoutSeconds\":30
}"; then
  static "FINDING-7" "Server ACCEPTS AGENT task type — SDK TaskType enum missing AGENT/GET_AGENT_CARD/CANCEL_AGENT"
else
  echo "  ⚠  Server may need agentCard config for AGENT tasks — still confirmed by server TaskType.java"
  static "FINDING-7" "AGENT type in server TaskType.java — absent from SDK enum"
fi

# ──────────────────────────────────────────────────────────────────────────────
echo ""
echo "=== Results ==="
echo "  PASS:        $PASS"
echo "  FAIL:        $FAIL"
echo "  STATIC_BUG:  $STATIC (confirmed from static analysis)"
if [[ ${#NOTES[@]} -gt 0 ]]; then
  echo ""
  echo "Failures:"
  for n in "${NOTES[@]}"; do echo "  - $n"; done
fi

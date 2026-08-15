#!/usr/bin/env bash
# conductor-cli agentspan — Live Operator Smoke + A2A Round-Trip (v3.32.0)
# Server baseline: Conductor v3.32.0.
# For the A2A round-trip, the server must run with:
#   conductor.integrations.ai.enabled=true
#   conductor.a2a.server.enabled=true
#   conductor.a2a.server.expose-all=true
#   conductor.a2a.client.allow-private-network=true   (for loopback agents)
#
# Run:  CONDUCTOR_SERVER=http://localhost:7003 CLI=/path/to/conductor bash live_test.sh
# Uses a CLEAN Anthropic key by default (an OpenAI project without gpt-4o access will 403).

set -uo pipefail
CONDUCTOR="${CONDUCTOR_SERVER:-http://localhost:7003}"; API="$CONDUCTOR/api"
CLI="${CLI:-conductor}"; MODEL="${AGENTSPAN_MODEL:-anthropic/claude-haiku-4-5-20251001}"
export CONDUCTOR_SERVER_URL="$API"
PASS=0; FAIL=0
pass(){ echo "  ✅ PASS — $1"; PASS=$((PASS+1)); return 0; }
fail(){ echo "  ❌ FAIL — $1: $2"; FAIL=$((FAIL+1)); return 0; }

WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
CFG="$WORK/smoke.yaml"
cat > "$CFG" <<YAML
name: harness_smoke_340
model: $MODEL
instructions: Reply with exactly the requested word.
maxTurns: 3
tools: []
YAML

echo "== version =="
V=$(curl -s -m5 "$API/admin/config" | python3 -c "import sys,json;print(json.load(sys.stdin).get('version'))" 2>/dev/null)
[[ "$V" == 3.4.* ]] && pass "server version $V" || echo "  ?? server version=$V (expected 3.4.x)"

echo "== #96 compile now wraps agentConfig =="
"$CLI" agent compile "$CFG" >/dev/null 2>&1 && pass "agent compile returns a plan" || fail "agent compile" "still failing"

echo "== happy path (run → stream → done) =="
OUT=$("$CLI" agent run --config "$CFG" "Reply with exactly this word and nothing else: BANANA42" 2>&1)
echo "$OUT" | grep -q BANANA42 && pass "agent run produced expected output" || fail "agent run" "no BANANA42 (check provider/model access)"

echo "== #97 execution --since AND --window both return rows =="
"$CLI" agent run --config "$CFG" "say ok" --no-stream >/dev/null 2>&1
S=$("$CLI" agent execution --since 1h 2>&1 | grep -c harness_smoke_340)
W=$("$CLI" agent execution --window now-1h 2>&1 | grep -c harness_smoke_340)
[[ "$S" -gt 0 ]] && pass "--since 1h returns rows ($S)" || fail "--since" "empty"
[[ "$W" -gt 0 ]] && pass "--window now-1h returns rows ($W)" || fail "--window" "empty (rc.9 server bug — needs v3.32.0)"

echo "== get / delete round-trip =="
"$CLI" agent get harness_smoke_340 2>&1 | grep -q harness_smoke_340 && pass "registered (get)" || fail "get" "missing"
"$CLI" agent delete harness_smoke_340 -y 2>&1 | grep -q Deleted && pass "delete" || fail "delete" "failed"

echo "== A2A round-trip (GET_AGENT_CARD self-hosted) =="
if [[ "$(curl -s -m5 -o /dev/null -w '%{http_code}' "$API/a2a/workflow")" == "200" ]]; then
  curl -s -o /dev/null -X POST "$API/metadata/workflow" -H 'Content-Type: application/json' -d \
    '{"name":"ht_a2a_echo","version":1,"schemaVersion":2,"tasks":[{"name":"e","taskReferenceName":"e","type":"INLINE","inputParameters":{"evaluatorType":"graaljs","expression":"(function(){return {text:$.m};})()","m":"${workflow.input.message}"}}]}'
  curl -s -o /dev/null -X POST "$API/metadata/workflow" -H 'Content-Type: application/json' -d \
    '{"name":"ht_get_card","version":1,"schemaVersion":2,"tasks":[{"name":"c","taskReferenceName":"c","type":"GET_AGENT_CARD","inputParameters":{"agentUrl":"'"$API"'/a2a/workflow/ht_a2a_echo"}}]}'
  WID=$(curl -s -X POST "$API/workflow/ht_get_card" -H 'Content-Type: application/json' -d '{}' | tr -d '"')
  sleep 3
  ST=$(curl -s "$API/workflow/$WID?includeTasks=true" | python3 -c "import sys,json;print(json.load(sys.stdin)['tasks'][0].get('status'))" 2>/dev/null)
  [[ "$ST" == "COMPLETED" ]] && pass "GET_AGENT_CARD round-trip COMPLETED" || fail "GET_AGENT_CARD" "task=$ST"
else
  echo "  -- skipped: A2A server not enabled on this server"
fi

echo; echo "== SUMMARY =="; echo "  PASS=$PASS  FAIL=$FAIL"; [[ $FAIL -eq 0 ]]

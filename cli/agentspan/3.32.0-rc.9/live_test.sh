#!/usr/bin/env bash
# conductor-cli agentspan — Live Operator Smoke + Finding Repro
# Server baseline: Conductor 3.32.0-rc.9 (needs the AI/agentspan module + a configured provider)
# Run:  CONDUCTOR_SERVER=http://localhost:7001 CLI=/path/to/conductor-dev bash live_test.sh
#
# Requires a provider whose key is CLEAN (no trailing newline). Anthropic is used by
# default because ISSUE-3 (untrimmed keys) commonly breaks OpenAI on file-loaded keys.

set -uo pipefail

CONDUCTOR="${CONDUCTOR_SERVER:-http://localhost:7001}"
API="$CONDUCTOR/api"
CLI="${CLI:-conductor}"
MODEL="${AGENTSPAN_MODEL:-anthropic/claude-haiku-4-5-20251001}"
PROVIDER="${MODEL%%/*}"
export CONDUCTOR_SERVER_URL="$API"

PASS=0; FAIL=0; STATIC=0
pass()   { echo "  ✅ PASS  — $1"; ((PASS++)); }
fail()   { echo "  ❌ FAIL  — $1: $2"; ((FAIL++)); }
static() { echo "  🐛 STATIC — $1"; ((STATIC++)); }

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
CFG="$WORK/smoke.yaml"
cat > "$CFG" <<YAML
name: harness_smoke
description: harness smoke agent
model: $MODEL
instructions: You are a test agent.
maxTurns: 5
tools: []
YAML

echo "== provider status =="
if curl -s -m 5 "$API/providers/status" | grep -q "\"name\":\"$PROVIDER\",\"configured\":true"; then
  pass "server has provider '$PROVIDER' configured"
else
  fail "provider status" "'$PROVIDER' not configured server-side — set its key in the server env"
fi

echo "== ISSUE-1: compile sends bare config (expect 500) =="
BARE=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -X POST "$API/agent/compile" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"harness_smoke\",\"model\":\"$MODEL\",\"instructions\":\"x\",\"maxTurns\":5,\"tools\":[]}")
WRAP=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -X POST "$API/agent/compile" \
  -H 'Content-Type: application/json' \
  -d "{\"agentConfig\":{\"name\":\"harness_smoke\",\"model\":\"$MODEL\",\"instructions\":\"x\",\"maxTurns\":5,\"tools\":[]}}")
if [[ "$BARE" == "500" && "$WRAP" == "200" ]]; then
  static "ISSUE-1 confirmed: bare compile=$BARE, wrapped compile=$WRAP (CLI sends bare)"
else
  echo "  ?? compile bare=$BARE wrapped=$WRAP (behavior changed — re-check ISSUE-1)"
fi

echo "== happy path: run (streamed) =="
OUT=$("$CLI" agent run --config "$CFG" "Reply with exactly this word and nothing else: BANANA42" 2>&1)
echo "$OUT" | sed 's/^/    /'
EID=$(echo "$OUT" | sed -n 's/.*Execution: \([0-9a-f-]*\)).*/\1/p' | head -1)
if echo "$OUT" | grep -q "BANANA42"; then pass "agent run produced expected output"
else fail "agent run" "no BANANA42 in stream (see ISSUE-3 if [error] with empty msg)"; fi

echo "== status =="
if [[ -n "$EID" ]] && "$CLI" agent status "$EID" 2>&1 | grep -q '"status": "COMPLETED"'; then
  pass "agent status COMPLETED for $EID"
else fail "agent status" "not COMPLETED for '$EID'"; fi

echo "== ISSUE-2: execution --since always empty =="
UNFILT=$("$CLI" agent execution 2>&1 | grep -c "COMPLETED\|FAILED\|RUNNING")
SINCE=$("$CLI" agent execution --since 1d 2>&1)
if [[ "$UNFILT" -gt 0 ]] && echo "$SINCE" | grep -q "No executions found"; then
  static "ISSUE-2 confirmed: unfiltered lists $UNFILT execs; --since 1d → 'No executions found'"
else
  echo "  ?? unfiltered=$UNFILT; --since output: $(echo "$SINCE" | tail -1)"
fi

echo "== get / list / delete round-trip =="
# `get` is the reliable existence check (registration is synchronous on run).
if "$CLI" agent get harness_smoke 2>&1 | grep -q '"name": "harness_smoke"'; then pass "agent registered (get)"
else fail "agent get" "harness_smoke not registered"; fi
if "$CLI" agent list 2>&1 | grep -q harness_smoke; then pass "agent appears in list"
else echo "  ⚠️  NOTE — harness_smoke missing from 'agent list' (present via 'get') — possible list race/cap"; fi
# delete is NOT idempotent — it 400s on a missing agent, so success proves it existed.
if "$CLI" agent delete harness_smoke -y 2>&1 | grep -q "Deleted"; then pass "agent delete"
else fail "agent delete" "failed"; fi

echo
echo "== SUMMARY =="
echo "  PASS=$PASS  FAIL=$FAIL  STATIC_BUG=$STATIC"
[[ $FAIL -eq 0 ]]

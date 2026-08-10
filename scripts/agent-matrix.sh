#!/usr/bin/env bash
# Run a trivial deterministic agent against each configured provider/model and
# report PASS/FAIL. Proves the server's provider wiring (Claude, ChatGPT, LiteLLM
# routers, local Ollama) end-to-end through `conductor agent`.
#
# Usage:
#   CONDUCTOR_SERVER=http://localhost:7010 CLI=/path/to/conductor scripts/agent-matrix.sh [model ...]
# With no args, runs the default set below. Each arg is a full "provider/model" string.
set -uo pipefail

API="${CONDUCTOR_SERVER:-http://localhost:7010}/api"
CLI="${CLI:-conductor}"
export CONDUCTOR_SERVER_URL="$API"

# Default matrix — one per provider class. Edit or pass models as args.
DEFAULT_MODELS=(
  "anthropic/claude-haiku-4-5-20251001"   # Claude
  "openai/gpt-4o"                         # ChatGPT (403s if the OpenAI project lacks gpt-4o)
  "litellm/loki/gemma3-12b"               # LiteLLM router → local backend
  "litellm/loki/gpt-oss"                  # LiteLLM router → local backend
  "ollama/llama3.1:8b"                    # direct Ollama (OLLAMA_BASE_URL host)
)
MODELS=("$@"); [[ ${#MODELS[@]} -eq 0 ]] && MODELS=("${DEFAULT_MODELS[@]}")

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
printf '%-38s %-8s %s\n' "MODEL" "RESULT" "DETAIL"
printf '%-38s %-8s %s\n' "-----" "------" "------"

pass=0; fail=0
for m in "${MODELS[@]}"; do
  name="mtx_$(echo "$m" | tr -c 'a-zA-Z0-9' '_' | cut -c1-40)"
  cat > "$WORK/$name.yaml" <<YAML
name: $name
model: $m
instructions: Reply with exactly the requested word, nothing else.
maxTurns: 3
tools: []
YAML
  out="$("$CLI" agent run --config "$WORK/$name.yaml" "Reply with exactly this word and nothing else: PING7" 2>&1)"
  eid="$(printf '%s' "$out" | grep -oE '[0-9a-f]{8}-[0-9a-f-]{27}' | head -1)"
  detail=""
  if printf '%s' "$out" | grep -q PING7; then
    printf '%-38s %-8s %s\n' "$m" "PASS" "streamed PING7"; pass=$((pass+1))
  else
    [[ -n "$eid" ]] && detail="$("$CLI" agent status "$eid" 2>/dev/null | python3 -c "import sys,json;print(str(json.load(sys.stdin).get('reasonForIncompletion'))[:90])" 2>/dev/null)"
    printf '%-38s %-8s %s\n' "$m" "FAIL" "${detail:-no PING7 in stream}"; fail=$((fail+1))
  fi
  "$CLI" agent delete "$name" -y >/dev/null 2>&1 || true
done

echo
echo "matrix: PASS=$pass FAIL=$fail"

#!/usr/bin/env bash
# Start a local Conductor test server wired to all agentspan providers from
# providers/secrets.env (Claude, ChatGPT, Ollama on loki/spartacus, a LiteLLM router),
# with the A2A server enabled. Proven config method for v3.4.0: an application.properties
# in the run dir (loads at the phase the A2A/AI conditions are evaluated).
#
# Usage:
#   scripts/start-test-server.sh [--port N] [--version V] [--foreground]
# Env:
#   CONDUCTOR_JAR=/path/to/jar   use an existing jar instead of downloading
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="$ROOT/providers/secrets.env"
RUNDIR="$ROOT/.run"
PORT=7010
VERSION=3.4.0
FOREGROUND=0
while [[ $# -gt 0 ]]; do case "$1" in
  --port) PORT="$2"; shift 2;;
  --version) VERSION="$2"; shift 2;;
  --foreground|-f) FOREGROUND=1; shift;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done

[[ -f "$SECRETS" ]] || { echo "Missing $SECRETS — copy providers/secrets.env.example and fill it in." >&2; exit 1; }
# shellcheck disable=SC1090
source "$SECRETS"

# Java 21+
JAVA_BIN="${JAVA_HOME:+$JAVA_HOME/bin/java}"; JAVA_BIN="${JAVA_BIN:-java}"
if ! "$JAVA_BIN" -version 2>&1 | grep -qE '"(21|22|23|24|25)'; then
  for h in /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home /usr/libexec/java_home; do
    [[ -x "$h/bin/java" ]] && JAVA_BIN="$h/bin/java" && break
  done
fi
echo "java: $("$JAVA_BIN" -version 2>&1 | head -1)"

mkdir -p "$RUNDIR"
JAR="${CONDUCTOR_JAR:-$RUNDIR/conductor-server-$VERSION.jar}"
if [[ ! -f "$JAR" ]]; then
  echo "Downloading conductor-server-$VERSION.jar (~450MB)…"
  curl -fSL -o "$JAR" "https://conductor-server.s3.us-east-2.amazonaws.com/conductor-server-$VERSION.jar"
fi

# Config that must be present at condition-eval time → application.properties in cwd.
cat > "$RUNDIR/application.properties" <<PROPS
conductor.integrations.ai.enabled=true
conductor.a2a.server.enabled=true
conductor.a2a.server.expose-all=true
conductor.a2a.client.allow-private-network=true
conductor.ai.ollama.baseURL=${OLLAMA_BASE_URL:-http://localhost:11434}
conductor.ai.litellm.baseURL=${LITELLM_BASE_URL:-http://localhost:4000}
conductor.ai.litellm.apiKey=${LITELLM_API_KEY:-sk-noauth}
PROPS

echo "Providers wired:"
echo "  anthropic: ${ANTHROPIC_API_KEY:+set}${ANTHROPIC_API_KEY:-MISSING}" | sed 's/set.*/set/'
echo "  openai:    ${OPENAI_API_KEY:+set}${OPENAI_API_KEY:-MISSING}" | sed 's/set.*/set/'
echo "  ollama:    ${OLLAMA_BASE_URL:-default}"
echo "  litellm:   ${LITELLM_BASE_URL:-default}"
echo "Starting Conductor $VERSION on :$PORT (rundir $RUNDIR)"

cd "$RUNDIR"
CMD=("$JAVA_BIN" -jar "$JAR" --server.port="$PORT" \
  --spring.datasource.url="jdbc:sqlite:$RUNDIR/test-$PORT.db?busy_timeout=15000&journal_mode=WAL")
if [[ "$FOREGROUND" == 1 ]]; then
  exec "${CMD[@]}"
else
  nohup "${CMD[@]}" > "$RUNDIR/server-$PORT.log" 2>&1 &
  echo "pid $! → $RUNDIR/server-$PORT.log"
  echo "Waiting for startup…"
  for _ in $(seq 1 60); do
    grep -q "Started Conductor in" "$RUNDIR/server-$PORT.log" 2>/dev/null && { echo "UP: http://localhost:$PORT/api"; exit 0; }
    sleep 2
  done
  echo "Did not confirm startup in time — check $RUNDIR/server-$PORT.log" >&2; exit 1
fi

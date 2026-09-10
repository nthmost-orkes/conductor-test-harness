#!/usr/bin/env bash
#
# validate-image.sh — Docker image validation battery for Conductor OSS.
#
# Runs ON the target host (loki by default; also works on this laptop if it has
# docker + java21 + python3 + go). Drive it remotely with scripts/run-on-loki.sh.
#
# Stages (select with --stages a,b,c or "all"):
#   local         full gradle build incl. test-harness (raw + excl-known-flaky verdicts)
#   build         docker build the server image from a git ref (JAR + UI from source)
#   health        boot the image on SQLite defaults, assert /health + UI:5000 proxy
#   kitchen-sink  raw-REST task-type battery against the running image
#   sdk-python    python-sdk tests/integration core bucket (keyless OSS)
#   sdk-go        go-sdk integration_tests (enterprise self-skips on OSS)
#
# The image is left running across kitchen-sink + sdk stages and torn down at the
# end. Every stage records a verdict; the run never aborts mid-battery so the
# report is always complete.
#
# Usage:
#   scripts/validate-image.sh --ref release/3.32.x
#   scripts/validate-image.sh --ref v3.32.4 --stages build,health
#   scripts/validate-image.sh --ref release/3.32.x --port 8090 --stages all
#   # validate a PUBLISHED image (pulls it; run on amd64 AND arm64 hosts):
#   scripts/validate-image.sh --image conductoross/conductor:3.32.4 \
#       --stages build,health,kitchen-sink,sdk-python,sdk-js,cli
#
# Config (env overridable; defaults target loki):
#   CONDUCTOR_REPO   conductor checkout to build from   (~/projects/git/conductor)
#   PYTHON_SDK       python-sdk checkout
#   GO_SDK           go-sdk checkout
#   KITCHEN_SINK     kitchen-sink battery dir           (server/3.32.0-rc.9/kitchen-sink)
#   JAVA_HOME        JDK 21 home                         (/usr/lib/jvm/java-1.21.0-openjdk-amd64)
#
set -uo pipefail   # deliberately NOT -e: collect verdicts across all stages

# ── locations ──────────────────────────────────────────────────────────────
HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDUCTOR_REPO="${CONDUCTOR_REPO:-$HOME/projects/git/conductor}"
PYTHON_SDK="${PYTHON_SDK:-$HOME/projects/git/conductor-oss/python-sdk}"
GO_SDK="${GO_SDK:-$HOME/projects/git/conductor-oss/go-sdk}"
JS_SDK="${JS_SDK:-$HOME/projects/git/conductor-oss/javascript-sdk}"
KITCHEN_SINK="${KITCHEN_SINK:-$HARNESS_DIR/server/3.32.0-rc.9/kitchen-sink}"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-1.21.0-openjdk-amd64}"
GO_VERSION="${GO_VERSION:-1.23.6}"
NODE_VERSION="${NODE_VERSION:-20.18.1}"

# Stages that run under --stages all. Go is retired (its integration suite is
# Orkes-version-gated → near-zero OSS coverage); still runnable via --stages sdk-go.
ALL_STAGES="local,build,health,kitchen-sink,sdk-python,sdk-js,cli"

# Known-flaky test-harness specs (see PLANNING/test-system-redesign-plan.md).
# Failures in these are re-run once and reported as WARN, never a real FAIL.
KNOWN_FLAKY_RE='NestedForkJoinSubWorkflowSpec|HierarchicalForkJoinSubworkflow|SubWorkflowRestartSpec|ExternalPayloadStorageSpec'

# E2E specs that need external infra (testcontainers ES/localstack, gRPC port
# binding, httpbin, AWS). Failures here are environmental, not image bugs, so
# they're reported WARN — a plain build host can't satisfy them.
KNOWN_ENVIRONMENTAL_RE='GrpcEndToEndTest|HttpEndToEndTest|ExternalPayloadStorageE2E|S3ExternalPayloadStorage|SQSEventQueue'

# ── args ─────────────────────────────────────────────────────────────────────
# --image <tag> validates a PREBUILT/published image (docker pull if absent)
# instead of building from --ref. Use it post-publish to verify the real
# multi-arch artifact: run it on an amd64 host AND an arm64 host to cover both.
REF=""; PORT=8090; STAGES="all"; RUNDIR=""; IMAGE_OVERRIDE=""
while [[ $# -gt 0 ]]; do case "$1" in
  --ref)     REF="$2"; shift 2;;
  --image)   IMAGE_OVERRIDE="$2"; shift 2;;
  --port)    PORT="$2"; shift 2;;
  --stages)  STAGES="$2"; shift 2;;
  --rundir)  RUNDIR="$2"; shift 2;;
  -h|--help) sed -n '2,45p' "$0"; exit 0;;
  *) echo "unknown arg: $1" >&2; exit 2;;
esac; done

UI_PORT=$((PORT + 1))
TS="$(date -u +%Y%m%dT%H%M%SZ)"
REF_TAG="$(echo "${REF:-${IMAGE_OVERRIDE:-noref}}" | tr '/:' '--' | tr -cd 'A-Za-z0-9._-')"
RUNDIR="${RUNDIR:-$HARNESS_DIR/runs/${TS}-${REF_TAG}}"
mkdir -p "$RUNDIR"
IMAGE="${IMAGE_OVERRIDE:-conductor:validate-${REF_TAG}}"
CONTAINER="conductor-validate-${PORT}"
API="http://localhost:${PORT}"

# ── verdict bookkeeping ───────────────────────────────────────────────────────
declare -A VERDICT NOTE
order=()
record() { local s="$1"; VERDICT[$s]="$2"; NOTE[$s]="${3:-}"; order+=("$s"); }
have_stage() { local set="$STAGES"; [[ "$STAGES" == "all" ]] && set="$ALL_STAGES"; [[ ",$set," == *",$1,"* ]]; }

log()  { printf '\n\033[1;36m▶ %s\033[0m %s\n' "$1" "${2:-}"; }
ok()   { printf '  \033[32m✓ %s\033[0m\n' "$1"; }
bad()  { printf '  \033[31m✗ %s\033[0m\n' "$1"; }

# True if TCP port $1 has no local listener (ss, fall back to nothing = free).
port_free() { ! ss -ltnH 2>/dev/null | awk '{n=split($4,a,":"); print a[n]}' | grep -qx "$1"; }
# From the requested PORT, find a free (api, api+1) pair; reassign globals.
pick_ports() {
  local p=$PORT
  for _ in $(seq 0 30); do
    if port_free "$p" && port_free "$((p+1))"; then
      PORT=$p; UI_PORT=$((p+1)); API="http://localhost:$p"; CONTAINER="conductor-validate-$p"; return 0
    fi
    p=$((p+2))
  done
  return 1
}

# ── Stage 0: preflight ────────────────────────────────────────────────────────
preflight() {
  log "preflight" "host=$(hostname) rundir=$RUNDIR"
  command -v docker >/dev/null || { bad "docker missing"; record preflight FAIL "no docker"; return 1; }
  ok "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null)"
  [[ -x "$JAVA_HOME/bin/java" ]] && ok "java $($JAVA_HOME/bin/java -version 2>&1|head -1)" || bad "JAVA_HOME invalid: $JAVA_HOME"
  command -v python3 >/dev/null && ok "python $(python3 --version 2>&1)" || bad "python3 missing"
  # Go: install once if absent (needed only for sdk-go stage).
  if have_stage sdk-go; then
    if ! command -v go >/dev/null && [[ ! -x "$HOME/.local/go/bin/go" ]] && [[ ! -x /usr/local/go/bin/go ]]; then
      log "preflight" "installing Go ${GO_VERSION} to \$HOME/.local/go (no sudo)"
      local arch; arch="$(uname -m)"; case "$arch" in x86_64) arch=amd64;; aarch64|arm64) arch=arm64;; esac
      mkdir -p "$HOME/.local"
      curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${arch}.tar.gz" -o /tmp/go.tgz \
        && rm -rf "$HOME/.local/go" && tar -C "$HOME/.local" -xzf /tmp/go.tgz \
        && ok "installed $("$HOME/.local/go/bin/go" version)" || bad "Go install failed"
    fi
    export PATH="$HOME/.local/go/bin:/usr/local/go/bin:$PATH"
    command -v go >/dev/null && ok "go $(go version)" || bad "go unavailable"
  fi
  # Node 20 + npm (for sdk-js): loki ships node 18 without npm; install a full
  # node tarball to $HOME/.local/node (no sudo) when npm is absent or node < 20.
  if have_stage sdk-js || have_stage cli; then
    export PATH="$HOME/.local/node/bin:$PATH"   # find a prior install before deciding to reinstall
    if ! command -v npm >/dev/null || ! node -e 'process.exit(+process.versions.node.split(".")[0]>=20?0:1)' 2>/dev/null; then
      log "preflight" "installing Node ${NODE_VERSION} to \$HOME/.local/node (no sudo)"
      local narch; narch="$(uname -m)"; case "$narch" in x86_64) narch=x64;; aarch64|arm64) narch=arm64;; esac
      mkdir -p "$HOME/.local"
      curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${narch}.tar.gz" -o /tmp/node.tgz \
        && rm -rf "$HOME/.local/node" && tar -C "$HOME/.local" -xzf /tmp/node.tgz \
        && mv "$HOME/.local/node-v${NODE_VERSION}-linux-${narch}" "$HOME/.local/node" \
        && ok "installed node $("$HOME/.local/node/bin/node" --version)" || bad "Node install failed"
    fi
    export PATH="$HOME/.local/node/bin:$PATH"
    command -v npm >/dev/null && ok "node $(node --version), npm $(npm --version)" || bad "npm unavailable"
    # docker compose v2 (loki's docker-compose v1 is broken: "http+docker scheme").
    # Install the CLI plugin user-level (no sudo) so `docker compose` works.
    if ! docker compose version >/dev/null 2>&1; then
      log "preflight" "installing docker compose v2 plugin (user-level, no sudo)"
      mkdir -p "$HOME/.docker/cli-plugins"
      local carch; carch="$(uname -m)"   # x86_64 | aarch64
      curl -fsSL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-${carch}" \
        -o "$HOME/.docker/cli-plugins/docker-compose" \
        && chmod +x "$HOME/.docker/cli-plugins/docker-compose" \
        && ok "installed $(docker compose version 2>&1 | head -1)" || bad "compose v2 install failed"
    else ok "docker compose $(docker compose version --short 2>/dev/null)"; fi
  fi
  # Sync the conductor checkout to the requested ref — only when building from
  # source (skipped entirely in --image mode unless the local test stage is run).
  if have_stage local || { have_stage build && [[ -z "$IMAGE_OVERRIDE" ]]; }; then
    [[ -d "$CONDUCTOR_REPO/.git" ]] || { bad "no conductor checkout at $CONDUCTOR_REPO"; record preflight FAIL "no conductor repo"; return 1; }
    [[ -n "$REF" ]] || { bad "--ref required to build from source (or pass --image)"; record preflight FAIL "no --ref"; return 1; }
    # Fetch the exact ref (branch OR tag) into FETCH_HEAD and detach onto it;
    # --force discards any dirty tree left by a prior gradle build.
    ( cd "$CONDUCTOR_REPO" && git fetch --quiet origin "$REF" && git checkout --quiet --force --detach FETCH_HEAD ) \
      && ok "conductor @ $REF ($(cd "$CONDUCTOR_REPO" && git rev-parse --short HEAD))" \
      || { bad "cannot checkout $REF"; record preflight FAIL "checkout $REF failed"; return 1; }
  fi
  # Sync SDK repos to a known ref (default main) so their runner scripts and
  # integration tests are present and we test a defined SDK version vs the image.
  if have_stage sdk-python && [[ -d "$PYTHON_SDK/.git" ]]; then
    ( cd "$PYTHON_SDK" && git fetch --quiet origin "${PYTHON_SDK_REF:-main}" && git checkout --quiet --force --detach FETCH_HEAD ) \
      && ok "python-sdk @ ${PYTHON_SDK_REF:-main} ($(cd "$PYTHON_SDK" && git rev-parse --short HEAD))" \
      || bad "python-sdk sync failed"
  fi
  if have_stage sdk-go && [[ -d "$GO_SDK/.git" ]]; then
    ( cd "$GO_SDK" && git fetch --quiet origin "${GO_SDK_REF:-main}" && git checkout --quiet --force --detach FETCH_HEAD ) \
      && ok "go-sdk @ ${GO_SDK_REF:-main} ($(cd "$GO_SDK" && git rev-parse --short HEAD))" \
      || bad "go-sdk sync failed"
  fi
  if have_stage sdk-js; then
    if [[ ! -d "$JS_SDK/.git" ]]; then
      # Derive the clone URL (and this host's SSH alias) from the conductor origin.
      local jsurl; jsurl="$(git -C "$CONDUCTOR_REPO" remote get-url origin 2>/dev/null | sed 's#/conductor\(\.git\)\{0,1\}$#/javascript-sdk.git#')"
      log "preflight" "cloning javascript-sdk ($jsurl)"
      git clone --quiet "$jsurl" "$JS_SDK" && ok "cloned javascript-sdk" || bad "javascript-sdk clone failed ($jsurl)"
    fi
    [[ -d "$JS_SDK/.git" ]] && ( cd "$JS_SDK" && git fetch --quiet origin "${JS_SDK_REF:-main}" && git checkout --quiet --force --detach FETCH_HEAD ) \
      && ok "javascript-sdk @ ${JS_SDK_REF:-main} ($(cd "$JS_SDK" && git rev-parse --short HEAD))" \
      || bad "javascript-sdk sync failed"
  fi
  record preflight PASS
}

# ── Stage 1: local tests (full gradle build) ──────────────────────────────────
local_tests() {
  have_stage local || return 0
  log "local tests" "./gradlew clean build (full, incl. test-harness)"
  # clean: the shared loki checkout accumulates stale generated protobuf under
  # */build/generated (a --force checkout doesn't wipe build/), which otherwise
  # fails :conductor-grpc:compileJava with duplicate-class errors. clean also
  # clears stale test-results XML so the failure scan below only sees this run.
  ( cd "$CONDUCTOR_REPO" && ./gradlew clean build --console=plain ) \
    > "$RUNDIR/gradle-build.log" 2>&1
  local rc=$?
  # Scan JUnit XML for failing test classes; classify env → flaky → real.
  python3 - "$CONDUCTOR_REPO" "$KNOWN_FLAKY_RE" "$KNOWN_ENVIRONMENTAL_RE" > "$RUNDIR/gradle-failures.json" <<'PY'
import sys, glob, re, json, xml.etree.ElementTree as ET
repo = sys.argv[1]
flaky_re, env_re = re.compile(sys.argv[2]), re.compile(sys.argv[3])
real, flaky, env = set(), set(), set()
for f in glob.glob(f"{repo}/**/build/test-results/**/*.xml", recursive=True):
    try: root = ET.parse(f).getroot()
    except Exception: continue
    for tc in root.iter("testcase"):
        if any(c.tag in ("failure","error") for c in tc):
            cls = tc.get("classname","")
            if env_re.search(cls):    env.add(cls)
            elif flaky_re.search(cls): flaky.add(cls)
            else:                      real.add(cls)
print(json.dumps({"real": sorted(real), "flaky": sorted(flaky),
                  "environmental": sorted(env)}, indent=2))
PY
  local real flaky env
  real=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["real"]))' "$RUNDIR/gradle-failures.json")
  flaky=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["flaky"]))' "$RUNDIR/gradle-failures.json")
  env=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["environmental"]))' "$RUNDIR/gradle-failures.json")
  if (( rc == 0 )); then
    ok "gradle build passed"; record local PASS "raw=PASS"
  elif (( real == 0 )) && (( flaky > 0 )); then
    bad "non-real failures: $flaky known-flaky, $env environmental — re-running test-harness once"
    ( cd "$CONDUCTOR_REPO" && ./gradlew :conductor-test-harness:test --console=plain ) \
      >> "$RUNDIR/gradle-build.log" 2>&1
    local rc2=$?
    (( rc2 == 0 )) && { ok "clean on re-run"; record local PASS "raw=FAIL(flaky/env only), rerun=PASS"; } \
                   || { bad "flaky/env still red (WARN, not image-related)"; record local WARN "flaky=$flaky env=$env, no real failures"; }
  elif (( real == 0 )) && (( env > 0 )); then
    bad "only environmental E2E specs failed ($env) — need testcontainers/infra, not image-related"
    record local WARN "environmental=$env (infra-dependent), no real/flaky failures"
  else
    bad "real test failures: $real class(es) (plus $flaky flaky, $env environmental)"
    record local FAIL "raw=FAIL, real=$real flaky=$flaky env=$env (see gradle-failures.json)"
  fi
}

# ── Stage 2: build image ──────────────────────────────────────────────────────
build_image() {
  have_stage build || return 0
  # --image mode: validate a prebuilt/published image — pull if not already local.
  if [[ -n "$IMAGE_OVERRIDE" ]]; then
    log "build image" "using provided image $IMAGE (pull if absent)"
    docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE" > "$RUNDIR/docker-pull.log" 2>&1
    if docker image inspect "$IMAGE" >/dev/null 2>&1; then
      local d; d=$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null)
      local arch; arch=$(docker image inspect "$IMAGE" --format '{{.Architecture}}' 2>/dev/null)
      ok "using $IMAGE ($arch, ${d:0:19})"; record build PASS "provided $IMAGE $arch $d"
    else
      bad "cannot pull $IMAGE (see docker-pull.log)"; record build FAIL "pull failed"; return 1
    fi
    return 0
  fi
  log "build image" "$IMAGE from $REF"
  ( cd "$CONDUCTOR_REPO" && docker build -f docker/server/Dockerfile -t "$IMAGE" . ) \
    > "$RUNDIR/docker-build.log" 2>&1
  if (( $? == 0 )); then
    local digest; digest=$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null)
    ok "built $IMAGE (${digest:0:19})"; record build PASS "$IMAGE $digest"
  else
    bad "docker build failed (see docker-build.log)"; record build FAIL "build error"; return 1
  fi
}

# ── Stage 3: boot + health ─────────────────────────────────────────────────────
boot_health() {
  have_stage health || have_stage kitchen-sink || have_stage sdk-python || have_stage sdk-go || have_stage cli || return 0
  pick_ports || { bad "no free port pair from :$PORT"; record health FAIL "no free ports"; return 1; }
  log "boot + health" "$CONTAINER on :$PORT (api) / :$UI_PORT (ui)"
  docker rm -f "$CONTAINER" >/dev/null 2>&1
  if ! docker run -d --name "$CONTAINER" -p "${PORT}:8080" -p "${UI_PORT}:5000" "$IMAGE" \
        > "$RUNDIR/docker-run.log" 2>&1; then
    bad "container failed to start:"; sed 's/^/    /' "$RUNDIR/docker-run.log"
    record health FAIL "docker run failed (see docker-run.log)"; return 1
  fi
  local up=0
  for _ in $(seq 1 60); do
    if curl -fsS "$API/health" 2>/dev/null | grep -q '"healthy":true'; then up=1; break; fi
    docker ps -q -f name="$CONTAINER" | grep -q . || { bad "container exited early"; break; }
    sleep 3
  done
  if (( up == 0 )); then
    docker logs --tail 40 "$CONTAINER" > "$RUNDIR/container-boot.log" 2>&1
    bad "server never became healthy (see container-boot.log)"; record health FAIL "no /health"; return 1
  fi
  ok "/health healthy"
  local ui; ui=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${UI_PORT}/" 2>/dev/null)
  local proxy; proxy=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${UI_PORT}/api/health" 2>/dev/null)
  [[ "$ui" == 200 ]] && ok "UI :$UI_PORT ($ui)" || bad "UI returned $ui"
  [[ "$proxy" == 200 ]] && ok "/api proxy ($proxy)" || bad "/api proxy returned $proxy"
  [[ "$ui" == 200 && "$proxy" == 200 ]] && record health PASS "ui+proxy 200" \
                                        || record health WARN "server healthy; ui=$ui proxy=$proxy"
}

# ── Stage 4: kitchen-sink ──────────────────────────────────────────────────────
kitchen_sink() {
  have_stage kitchen-sink || return 0
  log "kitchen-sink" "raw-REST battery vs $API"
  export CONDUCTOR_SERVER="$API"
  ( cd "$RUNDIR" && python3 "$KITCHEN_SINK/generate_and_register.py" ) > "$RUNDIR/ks-register.log" 2>&1 \
    && ok "workflows registered" || { bad "registration failed (see ks-register.log)"; record kitchen-sink FAIL "register failed"; return 1; }
  ( cd "$RUNDIR" && python3 "$KITCHEN_SINK/run_battery.py" --no-llm ) > "$RUNDIR/ks-battery.log" 2>&1
  local report; report=$(ls -t "$RUNDIR"/battery_report_*.json 2>/dev/null | head -1)
  [[ -f "$report" ]] || { bad "no battery report produced"; record kitchen-sink FAIL "no report"; return 1; }
  # Compare against the newest committed baseline in the kitchen-sink dir.
  local baseline; baseline=$(ls -t "$KITCHEN_SINK"/battery_report_*.json 2>/dev/null | head -1)
  python3 - "$report" "${baseline:-}" <<'PY' | tee "$RUNDIR/ks-summary.txt"
import json, sys
cur = json.load(open(sys.argv[1]))
res = cur.get("results", cur if isinstance(cur, list) else [])
if isinstance(cur, dict) and "results" in cur: res = cur["results"]
def failed(r): return [c for c in r if not c.get("ok")]
cf = failed(res); print(f"current: {len(res)} cases, {len(cf)} not-ok")
for c in cf: print(f"  FAIL {c.get('case')}: {c.get('status')}")
base = sys.argv[2]
if base:
    b = json.load(open(base)); br = b.get("results", b if isinstance(b,list) else [])
    bad_before = {c.get("case") for c in failed(br)}
    regress = [c for c in cf if c.get("case") not in bad_before]
    print(f"baseline: {len(br)} cases, {len(bad_before)} not-ok  ({base.split('/')[-1]})")
    print(f"REGRESSIONS vs baseline: {len(regress)}")
    for c in regress: print(f"  REGRESSION {c.get('case')}")
    sys.exit(2 if regress else 0)
sys.exit(1 if cf else 0)
PY
  case $? in
    0) ok "kitchen-sink clean vs baseline"; record kitchen-sink PASS "no regressions";;
    1) bad "failures but no baseline to compare"; record kitchen-sink WARN "failures, no baseline";;
    2) bad "regressions vs baseline"; record kitchen-sink FAIL "regressions (see ks-summary.txt)";;
  esac
}

# ── Stage 5: SDK smoke ─────────────────────────────────────────────────────────
sdk_python() {
  have_stage sdk-python || return 0
  log "sdk-python" "tests/integration core bucket vs $API/api"
  PYTHON_SDK="$PYTHON_SDK" SERVER_API="$API/api" RUNDIR="$RUNDIR" HARNESS_DIR="$HARNESS_DIR" \
    bash "$HARNESS_DIR/sdk-smoke/python/run.sh" > "$RUNDIR/sdk-python.log" 2>&1
  local rc=$?; local tail; tail=$(tail -1 "$RUNDIR/sdk-python.log" 2>/dev/null)
  case $rc in
    0) ok "python core smoke passed"; record sdk-python PASS "$(grep -m1 '^tests=' "$RUNDIR/sdk-python.log")";;
    2) bad "python inconclusive (server unreachable / all skipped)"; record sdk-python WARN "inconclusive; see sdk-python.log";;
    *) bad "python real failures (see sdk-python.log)"; record sdk-python FAIL "$(grep -m1 '^tests=' "$RUNDIR/sdk-python.log"); triage vs sdk/python/*/ISSUES.md";;
  esac
}
sdk_go() {
  have_stage sdk-go || return 0
  log "sdk-go" "integration_tests vs $API/api (enterprise self-skips)"
  export PATH="$HOME/.local/go/bin:/usr/local/go/bin:$PATH"
  GO_SDK="$GO_SDK" SERVER_API="$API/api" RUNDIR="$RUNDIR" HARNESS_DIR="$HARNESS_DIR" \
    bash "$HARNESS_DIR/sdk-smoke/go/run.sh" > "$RUNDIR/sdk-go.log" 2>&1
  local rc=$?
  case $rc in
    0) ok "go integration smoke passed"; record sdk-go PASS "$(grep -m1 '^tests=' "$RUNDIR/sdk-go.log")";;
    2) bad "go inconclusive (nothing ran / all gated)"; record sdk-go WARN "inconclusive; see sdk-go.log";;
    *) bad "go real failures (see sdk-go.log)"; record sdk-go FAIL "$(grep -m1 '^tests=' "$RUNDIR/sdk-go.log"); triage vs sdk/go/*/ISSUES.md";;
  esac
}

sdk_js() {
  have_stage sdk-js || return 0
  log "sdk-js" "integration:oss — SDK's own compose stack (our image + postgres + httpbin)"
  export PATH="$HOME/.local/node/bin:$PATH"
  local compose="$JS_SDK/scripts/docker-compose-oss.yaml"
  [[ -f "$compose" ]] || { bad "no docker-compose-oss.yaml in js-sdk"; record sdk-js FAIL "no compose file"; return 0; }
  # Use compose v2 (`docker compose`) if present, else v1 (`docker-compose`).
  local DC; if docker compose version >/dev/null 2>&1; then DC="docker compose"; \
    elif command -v docker-compose >/dev/null; then DC="docker-compose"; \
    else bad "no docker compose (v1 or v2)"; record sdk-js FAIL "no compose binary"; return 0; fi
  local jp; for jp in $(seq 8130 2 8180); do port_free "$jp" && break; done
  local proj="condval-js-$jp"
  # Override the stock conductoross/conductor:latest with our freshly-built image
  # and remap the host port. httpbin + postgres come from the SDK's compose.
  local ovr="$RUNDIR/compose-oss-override.yaml"
  # !override REPLACES the base ports list (compose otherwise appends sequences,
  # which would keep the base 8080:8080 mapping and collide on a busy host).
  printf 'services:\n  conductor-server:\n    image: %s\n    ports: !override ["%s:8080"]\n' "$IMAGE" "$jp" > "$ovr"
  log "sdk-js" "compose up (project $proj, conductor :$jp)"
  if ! $DC -p "$proj" -f "$compose" -f "$ovr" up -d > "$RUNDIR/js-compose-up.log" 2>&1; then
    bad "compose up failed:"; sed 's/^/    /' "$RUNDIR/js-compose-up.log" | tail -10
    $DC -p "$proj" -f "$compose" -f "$ovr" down -v >/dev/null 2>&1   # tear down partial stack
    record sdk-js FAIL "compose up (see js-compose-up.log)"; return 0
  fi
  local up=0
  for _ in $(seq 1 60); do
    curl -fsS "http://localhost:$jp/health" 2>/dev/null | grep -q '"healthy":true' && { up=1; break; }
    sleep 3
  done
  if (( up == 0 )); then
    $DC -p "$proj" -f "$compose" -f "$ovr" logs conductor-server > "$RUNDIR/js-compose.log" 2>&1
    bad "compose conductor never healthy (see js-compose.log)"; record sdk-js WARN "stack unhealthy"
    $DC -p "$proj" -f "$compose" -f "$ovr" down -v >/dev/null 2>&1; return 0
  fi
  ok "oss stack healthy on :$jp (postgres backend)"
  JS_SDK="$JS_SDK" SERVER_API="http://localhost:$jp/api" RUNDIR="$RUNDIR" HARNESS_DIR="$HARNESS_DIR" \
    bash "$HARNESS_DIR/sdk-smoke/js/run.sh" > "$RUNDIR/sdk-js.log" 2>&1
  local rc=$?
  $DC -p "$proj" -f "$compose" -f "$ovr" down -v >/dev/null 2>&1
  case $rc in
    0) ok "js integration:oss passed"; record sdk-js PASS "$(grep -m1 '^tests=' "$RUNDIR/sdk-js.log")";;
    2) bad "js inconclusive (nothing ran)"; record sdk-js WARN "inconclusive; see sdk-js.log";;
    *) bad "js real failures (see sdk-js.log)"; record sdk-js FAIL "$(grep -m1 '^tests=' "$RUNDIR/sdk-js.log"); triage vs sdk/javascript/*/ISSUES.md";;
  esac
}

cli_smoke() {
  have_stage cli || return 0
  log "cli" "conductor-cli OSS smoke vs $API/api (Orkes-only self-gated via --server-type OSS)"
  export PATH="$HOME/.local/node/bin:$PATH"
  CLI_BIN="${CLI_BIN:-}" SERVER_API="$API/api" RUNDIR="$RUNDIR" HARNESS_DIR="$HARNESS_DIR" \
    bash "$HARNESS_DIR/sdk-smoke/cli/run.sh" > "$RUNDIR/cli.log" 2>&1
  local rc=$?
  case $rc in
    0) ok "cli OSS smoke passed"; record cli PASS "$(grep -m1 '^tests=' "$RUNDIR/cli.log")";;
    2) bad "cli inconclusive (CLI unavailable / server unreachable)"; record cli WARN "inconclusive; see cli.log";;
    *) bad "cli real failures (see cli.log)"; record cli FAIL "$(grep -m1 '^tests=' "$RUNDIR/cli.log")";;
  esac
}

teardown() { docker rm -f "$CONTAINER" >/dev/null 2>&1 && log "teardown" "removed $CONTAINER"; }

# ── Stage 6: report ────────────────────────────────────────────────────────────
report() {
  local overall=PASS
  for s in "${order[@]}"; do [[ "${VERDICT[$s]}" == FAIL ]] && overall=FAIL; done
  {
    echo "# Docker image validation — ${REF:-$IMAGE} ($TS)"
    echo
    echo "- **Image:** \`$IMAGE\`"
    echo "- **Host:** $(hostname)"
    echo "- **Stages:** $STAGES"
    echo "- **Overall:** **$overall**"
    echo
    echo "| Stage | Verdict | Notes |"
    echo "|---|---|---|"
    for s in "${order[@]}"; do echo "| $s | ${VERDICT[$s]} | ${NOTE[$s]} |"; done
    echo
    echo "_Artifacts in \`$RUNDIR\` (gradle-build.log, docker-build.log, ks-summary.txt, sdk-*.log)._"
    echo "_FAIL = image-related regression. WARN = known-flaky or non-blocking. Cross-check SDK FAILs against \`sdk/<lang>/<ver>/ISSUES.md\` before treating as image bugs._"
  } | tee "$RUNDIR/REPORT.md"
  python3 - "$RUNDIR/report.json" "$overall" "$IMAGE" "$REF" "$TS" <<PY
import json, sys
json.dump({"overall": sys.argv[2], "image": sys.argv[3], "ref": sys.argv[4], "ts": sys.argv[5],
           "stages": { $(for s in "${order[@]}"; do printf '"%s": {"verdict": "%s", "note": "%s"}, ' "$s" "${VERDICT[$s]}" "${NOTE[$s]//\"/}"; done) }},
          open(sys.argv[1], "w"), indent=2)
PY
  [[ "$overall" == PASS ]]
}

# ── main ───────────────────────────────────────────────────────────────────────
trap teardown EXIT
preflight   || { report; exit 1; }
local_tests
build_image || { report; exit 1; }
boot_health || { report; exit 1; }
kitchen_sink
sdk_python
cli_smoke
sdk_js
sdk_go
report

# conductor-test-harness

A systematic test and analysis harness for Conductor OSS — focused on finding bugs where the
SDK libraries produce incorrect workflow definitions that either fail silently or misbehave at
runtime.

Server baseline for all work in this repo: **Conductor OSS 3.32.0-rc.9**
Live test server: `http://loki.local:8080`

---

## What this repo contains

```
conductor-test-harness/
├── README.md
├── SDK_ANALYSIS_PROCEDURE.md
├── server/
│   └── 3.32.0-rc.9/
│       ├── BUGS.md             Server-side bugs found against this version
│       └── kitchen-sink/       Raw JSON battery — tests all system task types via curl
└── sdk/
    ├── python/3.32.0-rc.9/
    ├── java/3.32.0-rc.9/
    ├── javascript/3.32.0-rc.9/
    ├── go/3.32.0-rc.9/
    ├── csharp/3.32.0-rc.9/
    └── ruby/3.32.0-rc.9/
```

Each `sdk/<language>/<server-version>/` directory contains:
- `STATIC_ANALYSIS.md` — task type coverage table + per-finding writeup
- `ISSUES.md` — punch list linking to filed GitHub issues
- `live_test.sh` (or `live_test.py`) — script to confirm findings against the live server

---

## Methodology

The full procedure is in [`SDK_ANALYSIS_PROCEDURE.md`](SDK_ANALYSIS_PROCEDURE.md). Summary:

### Phase 1: Static Analysis

Ground truth is the **Conductor OSS server source**, not documentation or prior SDK versions.

For each SDK:
1. Read the server's `TaskType.java` enum to get the complete list of system task types.
2. Read the relevant mapper/executor classes to find what `inputParameters` fields each task
   type expects, their exact JSON field names, and their types.
3. Read the SDK's task builder classes and compare field by field.
4. Flag mismatches: wrong field name, wrong type, missing field, empty list where the server
   requires content, deprecated API still in use.

**Common patterns found across SDKs:**
- **Empty `joinOn`** — FORK_JOIN builders that auto-create the companion JOIN task with
  `joinOn: []`. The server's Join executor uses `allMatch()` on an empty stream, which
  returns `true` immediately — the JOIN completes without waiting for any branch. Filed in
  JavaScript, Go, and C# SDKs.
- **Deprecated `dynamicForkJoinTasksParam`** — dynamic fork builders that set the deprecated
  JSON field instead of the current `dynamicForkTasksParam`. The server has a fallback path
  so it currently works, but the deprecated path may be removed. Filed in Python, C#, and Ruby.
- **Wrong HTTP timeout field names** — the Go SDK sends `ConnectionTimeOut` (capital C) and
  `readTimeout` (lowercase t) instead of `connectionTimeOut` and `readTimeOut`. Server silently
  ignores both; timeouts fall back to 3000ms default.
- **Missing task type constants** — NOOP, EXCLUSIVE_JOIN, and the AGENT task family added in
  3.32.0-rc.9 are missing from every SDK's enum.

### Phase 2: Live Testing

For each SDK, a test script (`live_test.sh` / `live_test.py`) runs against the live server to
confirm static findings:
- Register a workflow definition containing the suspect task
- Start it and poll for terminal status
- Compare actual behavior against expected behavior
- Distinguish SDK bugs from server bugs by running the same test via raw curl (kitchen-sink)

C# and Ruby have no runtime available in this environment — their findings are cross-validated
against confirmed findings from JS/Go audits that hit the same server code paths.

---

## SDK Audit Results

All issues mention "Conductor OSS 3.32.0-rc.9" as the tested baseline.

| SDK | Issues filed | Status | Key findings |
|-----|-------------|--------|-------------|
| [Python](sdk/python/3.32.0-rc.9/ISSUES.md) | [#426–#432](https://github.com/conductor-oss/python-sdk/issues) (7) | ✅ complete | `wait_until` wrong key, deprecated dynamic fork field, missing NOOP/EXCLUSIVE_JOIN/AGENT |
| [Java](sdk/java/3.32.0-rc.9/ISSUES.md) | [#130–#135](https://github.com/conductor-oss/conductor-java-sdk/issues) (6) | ✅ complete | NOOP/START_WORKFLOW/HUMAN/EXCLUSIVE_JOIN no builder, Http no fluent timeout, TaskType missing AGENT family; 1 false positive retracted |
| [JavaScript](sdk/javascript/3.32.0-rc.9/ISSUES.md) | [#135–#140](https://github.com/conductor-oss/javascript-sdk/issues) (6) | ✅ complete | `forkTaskJoin()` empty joinOn (live-confirmed), NOOP missing, EXCLUSIVE_JOIN no builder, `readTimeOut` wrong type, SWITCH no JS evaluator, 4 missing enum values |
| [Go](sdk/go/3.32.0-rc.9/ISSUES.md) | [#262–#265](https://github.com/conductor-oss/go-sdk/issues) (4) | ✅ complete | HTTP wrong JSON field names + int16 overflow, ForkTask empty joinOn (live-confirmed), DynamicForkTask ignores stored join, 6 missing TaskType constants |
| [C#](sdk/csharp/3.32.0-rc.9/ISSUES.md) | [#158–#161](https://github.com/conductor-oss/csharp-sdk/issues) (4) | ✅ complete | DynamicFork.Join empty joinOn, deprecated field, missing NOOP/EXCLUSIVE_JOIN/START_WORKFLOW builders, missing AGENT enum values |
| [Ruby](sdk/ruby/3.32.0-rc.9/ISSUES.md) | [#23–#25](https://github.com/conductor-oss/ruby-sdk/issues) (3) | ✅ complete | Deprecated dynamic fork field, SWITCH JS evaluator hardcoded, missing NOOP/EXCLUSIVE_JOIN DSL + AGENT constants |

**Total: 30 issues filed across 6 SDKs.**

The Ruby SDK is the only one that correctly infers `joinOn` from fork branches in its
`parallel` block — the bug that affected every other SDK.

---

## Server-Side Bugs

Found while running the kitchen-sink battery and live SDK tests. See [`BUGS.md`](BUGS.md).

Full details in [`server/3.32.0-rc.9/BUGS.md`](server/3.32.0-rc.9/BUGS.md).

| Bug | Issue | Status |
|-----|-------|--------|
| Nested DO_WHILE loopCondition TypeError | [#1307](https://github.com/conductor-oss/conductor/issues/1307) | Fix implemented, needs PR |
| Nested DO_WHILE body task name collision | [#1308](https://github.com/conductor-oss/conductor/issues/1308) | Open |
| FORK_JOIN + EXCLUSIVE_JOIN passes registration but fails at runtime | [#1309](https://github.com/conductor-oss/conductor/issues/1309) | Open |
| WAIT task misleading error for ISO-8601 duration format | [#1310](https://github.com/conductor-oss/conductor/issues/1310) | Open |
| SWITCH javascript evaluator validates expression with no bindings | [#1311](https://github.com/conductor-oss/conductor/issues/1311) | Open |

---

## Kitchen Sink Battery

`server/3.32.0-rc.9/kitchen-sink/` contains a raw JSON battery that exercises all system task
types via the REST API (no SDK involved). It serves as the server ground truth — if a task type
passes here but fails in an SDK test, the bug is in the SDK.

```shell
cd server/3.32.0-rc.9/kitchen-sink
python3 run_battery.py          # run all tests against loki.local:8080
CONDUCTOR_SERVER=http://... python3 run_battery.py   # point at another server
```

---

## Running an SDK Live Test

Each `live_test.sh` is self-contained and can be pointed at any server:

```shell
# Default: loki.local:8080
bash sdk/go/3.32.0-rc.9/live_test.sh

# Point at another server
CONDUCTOR_SERVER=http://myserver:8080 bash sdk/go/3.32.0-rc.9/live_test.sh
```

Tests print `✅ PASS`, `❌ FAIL`, or `🐛 STATIC_BUG` (confirmed by code inspection, not
runtime) for each finding.

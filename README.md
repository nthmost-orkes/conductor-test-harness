# conductor-test-harness

A versioned capabilities catalog and SDK audit harness for Conductor OSS.

> **Resuming?** See [`NEXT_STEPS.md`](NEXT_STEPS.md) for where the last session left off and the
> current top task (full-harness pass against v3.32.x, focused on the v3.31.0 → v3.32.0 diff).

Two primary purposes:

1. **Capabilities catalog** — machine-readable ground truth of what each server version
   supports: every task type, every backend, every task combination that works or doesn't.
   Used as the source-of-truth for SDK PR review, LLM grounding, and onboarding decisions.

2. **SDK audit archive** — systematic static analysis and live test results for all six
   official Conductor SDKs, surfacing bugs where an SDK produces incorrect workflow
   definitions that fail silently or misbehave at runtime.

Live test server (3.32.0-rc.9): `http://loki.local:8080`

---

## Repo structure

```
conductor-test-harness/
├── AGENTS.md                      How AI agents should use this repo for PR review
├── README.md
├── SDK_ANALYSIS_PROCEDURE.md      Full methodology for SDK audits
├── scripts/
│   └── build_changelogs.py        LiteLLM-assisted changelog generation
├── server/
│   ├── 3.30.0/
│   │   ├── CHANGES.md             SDK-relevant changes at this version (baseline)
│   │   ├── capabilities.yaml      Machine-readable feature catalog
│   │   └── FEATURE_MATRIX.md      Human-readable rendering
│   ├── 3.30.1/
│   │   └── CHANGES.md             Patch only — no schema changes
│   ├── 3.30.2/
│   │   └── CHANGES.md             GraalJS sandbox hardening (breaking for JS that used IO/native)
│   ├── 3.31.0/
│   │   ├── CHANGES.md
│   │   ├── capabilities.yaml
│   │   └── FEATURE_MATRIX.md
│   └── 3.32.0-rc.9/
│       ├── CHANGES.md
│       ├── capabilities.yaml
│       ├── FEATURE_MATRIX.md
│       ├── BUGS.md                Server-side bugs found at this version
│       └── kitchen-sink/          Raw JSON battery — tests all task types via curl
│   └── 3.32.0/                     Current stable (3.32.0-rc.* graduated; v3.4.0 was a retracted tag)
│       └── CHANGES.md               (full catalog TODO — see NEXT_STEPS.md)
├── sdk/
│   ├── python/3.32.0-rc.9/
│   ├── java/3.32.0-rc.9/
│   ├── javascript/3.32.0-rc.9/
│   ├── go/3.32.0-rc.9/
│   ├── csharp/3.32.0-rc.9/
│   └── ruby/3.32.0-rc.9/
└── cli/
    └── agentspan/
        ├── 3.32.0/                   Current baseline — FINDINGS/ISSUES/AGENT_CAPABILITIES/live_test.sh
        └── 3.32.0-rc.9/             Historical (bugs since fixed; see 3.32.0)
```

Each `sdk/<language>/<server-version>/` directory contains:
- `STATIC_ANALYSIS.md` — task type coverage table + per-finding writeup
- `ISSUES.md` — punch list linking to filed GitHub issues
- `live_test.sh` (or `live_test.py`) — script to confirm findings against the live server

---

## Capabilities Catalog

The `server/<version>/capabilities.yaml` file is the machine-readable answer to "what does
this version of Conductor OSS actually support?"

It covers:
- **System task types** — every `TaskType` enum value: category, status, behavioral notes
- **Task combination matrix** — which nesting patterns (e.g. DO_WHILE inside FORK_JOIN)
  are `supported`, `buggy`, or `untested`, with links to known issues
- **Persistence backends** — execution DAO, index/search DAO, scheduler DAO
- **Event sinks** — Conductor internal, SQS, Kafka, AMQP, NATS
- **External payload storage** — S3, Azure Blob, GCS, local filesystem, PostgreSQL
- **Server capabilities** — scheduler, secrets interpolation, A2A agent protocol, LLM tasks,
  GraalJS sandbox hardening, MCP integration

`FEATURE_MATRIX.md` is the human-readable rendering of the same data, with ✅/⚠️/🐛/❌/🔲
status icons, a known bugs table, and a "fixes landed" section.

`CHANGES.md` documents what changed from the prior version, SDK-relevant only: new/removed task
types, field changes, behavioral changes, breaking changes.

### Versions cataloged

| Server version | Task types | Catalog | Key additions vs prior |
|---------------|-----------|---------|----------------------|
| 3.30.0 | 34 | full | Baseline; GraalJS sandbox unhardened |
| 3.30.1 | 34 | CHANGES.md only | Patch; no SDK-visible changes |
| 3.30.2 | 34 | CHANGES.md only | GraalJS sandbox hardened (breaking for JS using IO/native APIs) |
| 3.31.0 | 34 | full | SWITCH empty-case fix; DO_WHILE truncation fix; nested JOIN reset fix |
| 3.32.0-rc.9 | 37 | full | AGENT + GET_AGENT_CARD + CANCEL_AGENT; MCP tasks; secrets/env interpolation |

### Using the catalog for PR review

When reviewing a PR against any Conductor SDK:

1. Load `server/<version>/capabilities.yaml` and `sdk/<lang>/<version>/STATIC_ANALYSIS.md`
2. For any changed model or field, verify the exact server field name against the Java source
   (never infer from SDK naming alone — the server is the spec)
3. Check `task_combinations` in `capabilities.yaml` for any nesting patterns the PR enables
4. Check `known_bugs` for any open server issues that affect the changed feature
5. See [`AGENTS.md`](AGENTS.md) for the full AI agent workflow and common review patterns

### LLM grounding

The catalog is small enough to inject directly as a system prompt context (~2–4 KB per version).
When combined with the issue tables, it lets an LLM reviewer:

- Detect field name mismatches without hallucinating server behavior
- Flag task type coverage gaps against the known-good list
- Identify combinations the PR enables that have known server-side bugs
- Confirm whether a "works against OSS" claim matches what OSS actually supports

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

### CLI / agentspan audit

The `conductor agent` operator surface (`conductor-oss/conductor-cli`) is audited against a live
server. **Current baseline: [`cli/agentspan/3.32.0/`](cli/agentspan/3.32.0/)**
(`FINDINGS.md`, `ISSUES.md`, `AGENT_CAPABILITIES.md`, `live_test.sh`). The original
[`3.32.0-rc.9`](cli/agentspan/3.32.0-rc.9/) run is kept for history.

**Filed and now fixed (confirmed on v3.32.0):**

| Finding | Repo/issue | Status |
|---|---|---|
| `agent compile` sent bare config → 500 (needed `{"agentConfig":…}`) | conductor-cli#96 | ✅ fixed |
| `agent execution --since/--window` returned zero | conductor-cli#97 | ✅ fixed (`--window` needed the v3.32.0 server search fix) |
| Server didn't trim provider API keys (trailing `\n` → `Authorization` error) | conductor#1437 | ✅ fixed (trim at ingestion) |
| A2A server REST layer wouldn't enable via config (rc.9 blocker) | — | ✅ resolved in v3.32.0 |

**Still open on v3.32.0:**

| Finding | Severity |
|---|---|
| `doctor` reports client-shell provider env, not server `/api/providers/status` (doubly misleading on v3.32.0) | medium |
| Streamed `[error]` events carry an empty message (cause only via `agent status`) | medium |
| `prune --older-than` int-days vs `execution --since` durations; `--dry-run` reports no count | low |

**Live-confirmed on v3.32.0:** an Anthropic agent runs green end-to-end via the CLI, and the full
A2A round-trip works — a workflow exposed as an A2A agent driven by
`GET_AGENT_CARD` / `AGENT` / `CANCEL_AGENT`, including inside `FORK_JOIN` (distinct remote
taskIds) and `DO_WHILE`. The provider matrix (`scripts/agent-matrix.sh`) runs 5/5 green:
Claude, ChatGPT (gpt-4o), LiteLLM→local ×2, and direct Ollama on loki.

The Ruby SDK is the only one that correctly infers `joinOn` from fork branches in its
`parallel` block — the bug that affected every other SDK.

---

## SDK Audit Methodology

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

## Server-Side Bugs

Found while running the kitchen-sink battery and live SDK tests.

| Bug | Issue | Status |
|-----|-------|--------|
| Nested DO_WHILE loopCondition TypeError | [#1307](https://github.com/conductor-oss/conductor/issues/1307) | Fix implemented, needs PR |
| Nested DO_WHILE body task name collision | [#1308](https://github.com/conductor-oss/conductor/issues/1308) | Open |
| FORK_JOIN + EXCLUSIVE_JOIN passes registration but fails at runtime | [#1309](https://github.com/conductor-oss/conductor/issues/1309) | Open |
| WAIT task misleading error for ISO-8601 duration format | [#1310](https://github.com/conductor-oss/conductor/issues/1310) | Open |
| SWITCH javascript evaluator validates expression with no bindings | [#1311](https://github.com/conductor-oss/conductor/issues/1311) | Open |

Full details in [`server/3.32.0-rc.9/BUGS.md`](server/3.32.0-rc.9/BUGS.md).

---

## Kitchen Sink Battery

`server/<version>/kitchen-sink/` contains a raw JSON battery that exercises all system task
types via the REST API (no SDK involved). It serves as the server ground truth — if a task type
passes here but fails in an SDK test, the bug is in the SDK.

```shell
cd server/3.32.0-rc.9/kitchen-sink
python3 run_battery.py                              # run against loki.local:8080
CONDUCTOR_SERVER=http://... python3 run_battery.py  # point at another server
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

Tests print `PASS`, `FAIL`, or `STATIC_BUG` (confirmed by code inspection, not runtime) for
each finding.

---

## Adding a new server version

See [`AGENTS.md`](AGENTS.md#how-to-add-a-new-server-version) for the full step-by-step.
Short version:

1. `mkdir -p server/<version>/kitchen-sink`
2. Diff `TaskType.java` against the prior version tag
3. Adapt the prior `capabilities.yaml` with verified diffs; write `CHANGES.md`
4. Adapt `FEATURE_MATRIX.md`; update the known bugs table
5. Run the kitchen-sink battery against the new server
6. Update the versions table in this file

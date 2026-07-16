# SDK Analysis Procedure

Systematic method for finding bugs in Conductor SDK libraries. The procedure has
two phases — static then live — applied to each SDK in turn:
Python → Java → JavaScript → Go → C# → Ruby.

Ground truth for all comparisons is the **Conductor server source code**, not
documentation or prior SDK versions.

---

## Phase 1: Static Analysis

Goal: find bugs without running anything. Read SDK source against server source.

### Step 1 — Build the server ground truth

Start from `common/src/main/java/com/netflix/conductor/common/metadata/tasks/TaskType.java`:

```
grep -A 60 "^public enum TaskType" .../TaskType.java
```

Produce a table: every `TaskType` value, whether it is a system task (handled
server-side) or user-defined, and which server class implements it. For system
tasks, note the relevant `inputParameters` fields by reading the mapper or
executor class.

### Step 2 — Map server types to SDK classes

For each server `TaskType`:

| Check | Pass | Flag |
|-------|------|------|
| SDK has a TaskType enum value for it | yes | missing enum value |
| SDK has a dedicated class/builder for it | yes | missing class |
| The class produces the correct `"type"` string | yes | wrong type string |

Mark each type: ✓ covered / ⚠ partial / ✗ missing.

### Step 3 — Field-level comparison

For each covered task type, read:
- **Server side**: the mapper (`core/.../mapper/*Mapper.java`) or executor
  (`core/.../tasks/*.java`) to find what fields are read from `inputParameters`
  and what their expected names and types are.
- **SDK side**: the task class constructor and any `to_workflow_task()` /
  serialisation method to find what fields it sets in `inputParameters`.

Flag any mismatch:
- Missing field (server reads it, SDK never sets it)
- Extra field (SDK sets it, server ignores it — usually harmless but noisy)
- Wrong field name (camelCase vs snake_case, abbreviation differences)
- Wrong type (string vs int, nested object vs flat)
- Missing default or wrong default value

### Step 4 — Document findings

Write findings to `<sdk>/STATIC_ANALYSIS.md` in this repo. Use the template
in the next section. Each finding gets a severity:

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Task cannot function at all — wrong type string, required field missing |
| **HIGH** | Task silently misbehaves — wrong field name, wrong default |
| **MEDIUM** | Feature partial — optional but useful field missing |
| **LOW** | Cosmetic or documentation gap |

---

## Phase 2: Live Testing

Goal: verify static findings against a running server and discover runtime bugs
that static analysis misses (serialization edge cases, timing, schema validation).

### Step 1 — Write a builder script

For each SDK, create `<sdk>/build_system_tasks.py` (or `.java`, `.js`, etc.)
that uses **only the SDK** (no raw JSON/HTTP) to:

1. Construct a workflow definition containing every system task type
2. Register it with the server via the SDK's workflow client
3. Start it with representative inputs
4. Poll for terminal status
5. Assert expected output

Pattern mirrors `kitchen-sink/generate_and_register.py` (which uses raw JSON)
but uses the SDK's native types instead.

### Step 2 — Run against loki

```shell
CONDUCTOR_SERVER=http://loki.local:8080 python python-sdk/build_system_tasks.py
```

Capture: registration errors, runtime failures, unexpected task statuses,
output field mismatches.

### Step 3 — Cross-reference with kitchen-sink battery

For each task type:
- If the kitchen-sink raw JSON test PASSED but the SDK test FAILED → SDK bug
- If both failed → server bug (already tracked in BUGS.md)
- If the SDK test PASSED but kitchen-sink failed → interesting; re-examine

### Step 4 — Document findings

Add runtime findings to `<sdk>/STATIC_ANALYSIS.md` under a "Live Test Results"
section. File GitHub issues for confirmed bugs (server repo for server-side
issues; SDK repo for SDK-side issues).

---

## Finding Template

```markdown
### FINDING-<N>: <Short title>

**Severity:** CRITICAL | HIGH | MEDIUM | LOW
**Task type:** <TaskType enum value>
**SDK file:** `path/to/file.py:line`
**Server file:** `path/to/ServerFile.java:line`

**What the server expects:**
<field name, type, required/optional, default>

**What the SDK provides:**
<what the SDK actually sets, or "nothing">

**Impact:**
<What breaks or degrades at runtime>

**Fix:**
<One-sentence description of what the SDK should do differently>
```

---

## SDK Coverage Status

| SDK | Static analysis | Live test | Status |
|-----|----------------|-----------|--------|
| Python (`python-sdk/`) | `python-sdk/STATIC_ANALYSIS.md` | `python-sdk/live_test.py` | ✅ complete — 6 issues filed (#426–#432) |
| Java (`java-sdk/`) | `java-sdk/STATIC_ANALYSIS.md` | `java-sdk/live_test.sh` | ✅ complete — 6 issues filed (#130–#135); 1 false positive retracted |
| JavaScript (`javascript-sdk/`) | `javascript-sdk/STATIC_ANALYSIS.md` | `javascript-sdk/live_test.sh` | ✅ complete — 6 issues filed (#135–#140) |
| Go (`go-sdk/`) | `go-sdk/STATIC_ANALYSIS.md` | `go-sdk/live_test.sh` | ✅ complete — 4 issues filed (#262–#265) |
| C# (`csharp-sdk/`) | `csharp-sdk/STATIC_ANALYSIS.md` | (no runtime available) | ✅ complete — 4 issues filed (#158–#161); cross-validated against confirmed JS/Go findings |

---

## Server Ground Truth: System Task Types

These are the system task types as of Conductor `3.32.0-rc.9`.
Each SDK is expected to have a class that can build a valid workflow task for
each of these types.

### Core control flow
| TaskType | Required inputParameters | Notes |
|----------|--------------------------|-------|
| `NOOP` | none | No-op; completes immediately |
| `SWITCH` | `evaluatorType`, `expression`, `decisionCases` | Value-param or javascript evaluator |
| `DO_WHILE` | `loopCondition`, `loopOver` | Condition is JS; body tasks in loopOver |
| `FORK_JOIN` | `forkTasks` | Parallel branches; must be followed by JOIN |
| `JOIN` | `joinOn` (list of task refs) | Waits for all listed tasks |
| `EXCLUSIVE_JOIN` | `joinOn`, `defaultExclusiveJoinTask` | For SWITCH branches only |
| `FORK_JOIN_DYNAMIC` | `dynamicTasks`, `dynamicTasksInput`, `dynamicTasksConcurrencyLimit` | |
| `TERMINATE` | `terminationStatus`, `workflowOutput` | |
| `START_WORKFLOW` | `startWorkflow` (nested object) | Fire-and-forget child workflow |
| `SUB_WORKFLOW` | `subWorkflowParam` (nested object) | Inline child; parent waits |

### Data / scripting
| TaskType | Required inputParameters | Notes |
|----------|--------------------------|-------|
| `INLINE` | `expression`, `evaluatorType` | evaluatorType must be `"javascript"` |
| `LAMBDA` | `lambdaValue`, `scriptExpression` | Nashorn/Graal JS |
| `JSON_JQ_TRANSFORM` | `queryExpression` | jq expression |
| `SET_VARIABLE` | any key-value pairs | Sets workflow variables |

### I/O
| TaskType | Required inputParameters | Notes |
|----------|--------------------------|-------|
| `HTTP` | `http_request` (nested: uri, method, body, etc.) | |
| `WAIT` | `duration` OR `until` | duration: "1s"/"2m" format; until: epoch or date string |
| `HUMAN` | none required | Waits for external human signal |
| `EVENT` | `sink`, `asyncComplete` | Publishes to event sink |

### Agent tasks (added 3.32.0-rc.9 / #1288)
| TaskType | Notes |
|----------|-------|
| `AGENT` | Run an A2A conductor agent |
| `GET_AGENT_CARD` | Retrieve agent card |
| `CANCEL_AGENT` | Cancel a running agent |

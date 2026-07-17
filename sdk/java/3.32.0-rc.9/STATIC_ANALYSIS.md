# Java SDK — Static Analysis

SDK: `conductor-oss/java-sdk`
Server baseline: Conductor `3.32.0-rc.9`
Analysis date: 2026-07-16

Methodology: see `../SDK_ANALYSIS_PROCEDURE.md`.

Builder classes live in:
`conductor-client/src/main/java/com/netflix/conductor/sdk/workflow/def/tasks/`

---

## Coverage Table

| Server TaskType | SDK enum | SDK builder class | Status |
|----------------|----------|-------------------|--------|
| NOOP | ✓ | ✗ | MISSING BUILDER |
| SWITCH | ✓ | `Switch.java` | ✓ |
| DO_WHILE | ✓ | `DoWhile.java` | ✓ |
| FORK_JOIN | ✓ | `ForkJoin.java` | ⚠ (CRITICAL bug in joinOn) |
| JOIN | ✓ | `Join.java` | ✓ |
| EXCLUSIVE_JOIN | ✓ | ✗ | MISSING BUILDER |
| FORK_JOIN_DYNAMIC | ✓ | `DynamicFork.java` | ✓ |
| TERMINATE | ✓ | `Terminate.java` | ✓ |
| START_WORKFLOW | ✓ | ✗ | MISSING BUILDER |
| SUB_WORKFLOW | ✓ | `SubWorkflow.java` | ✓ |
| INLINE | ✓ | `Javascript.java` | ✓ |
| LAMBDA | ✓ | ✗ | MISSING BUILDER (deprecated server-side; INLINE preferred) |
| JSON_JQ_TRANSFORM | ✓ | `JQ.java` | ✓ |
| SET_VARIABLE | ✓ | `SetVariable.java` | ✓ |
| HTTP | ✓ | `Http.java` | ⚠ (missing fluent connectionTimeout) |
| WAIT | ✓ | `Wait.java` | ✓ |
| HUMAN | ✓ | ✗ | MISSING BUILDER |
| EVENT | ✓ | `Event.java` | ✓ |
| AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| GET_AGENT_CARD | ✗ | ✗ | MISSING (new in rc.9) |
| CANCEL_AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| PULL_WORKFLOW_MESSAGES | ✗ | ✗ | MISSING (not in SDK enum) |

---

## Findings

### ~~FINDING-1~~: ForkJoin — `joinOn()` (FALSE POSITIVE — retracted)

**Status:** FALSE POSITIVE — retracted after live verification.

The static analysis originally claimed `List.of(this.join.getJoinOn())` at `ForkJoin.java:119`
would produce `List<String[]>` instead of `List<String>`. This is **incorrect**.

Java's target-type inference resolves the ambiguity: because `setJoinOn(List<String>)` has
a typed parameter, the compiler infers `E = String` for the `List.of()` call and uses the
varargs overload `List.of(E... elements)`, which correctly unpacks the `String[]` into
individual elements. Live verification confirmed this with a direct Java test.

The `ForkJoin.joinOn()` implementation is correct.

---

### FINDING-2: NOOP — enum value exists, no builder class

**Severity:** HIGH
**Task type:** NOOP
**SDK file:** `TaskType.java` (enum only)

**What the server expects:**
NOOP is a valid system task that completes immediately with no `inputParameters`.

**What the SDK provides:**
`TaskType.NOOP` is in the enum but no `Noop` builder class exists in `def/tasks/`.

**Fix:**
```java
public class Noop extends Task<Noop> {
    public Noop(String taskReferenceName) {
        super(taskReferenceName, TaskType.NOOP);
    }
}
```

---

### FINDING-3: START_WORKFLOW — no builder class

**Severity:** HIGH
**Task type:** START_WORKFLOW
**SDK file:** N/A (no builder exists)

**What the server expects:**
`inputParameters` contains a `startWorkflow` object with `name`, optional `version`,
`input`, `correlationId`, and `taskToDomain`.

**What the SDK provides:**
Nothing. There is no `StartWorkflow` builder class. (A file named `StartWorkflow.java`
exists only in `examples/old/` and is an example runner, not a task builder.)

**Fix:**
```java
public class StartWorkflow extends Task<StartWorkflow> {
    public StartWorkflow(String taskReferenceName, String workflowName) {
        super(taskReferenceName, TaskType.START_WORKFLOW);
        input("startWorkflow", Map.of("name", workflowName));
    }
    public StartWorkflow version(int version) { ... }
    public StartWorkflow workflowInput(Map<String, Object> input) { ... }
}
```

---

### FINDING-4: HUMAN — no builder class

**Severity:** MEDIUM
**Task type:** HUMAN
**SDK file:** N/A (no builder exists)

**What the server expects:**
HUMAN tasks pause the workflow pending an external human signal. No required
`inputParameters`.

**What the SDK provides:**
`TaskType.HUMAN` is in the enum. No builder class exists.

**Fix:**
```java
public class Human extends Task<Human> {
    public Human(String taskReferenceName) {
        super(taskReferenceName, TaskType.HUMAN);
    }
}
```

---

### FINDING-5: EXCLUSIVE_JOIN — no builder class; `defaultExclusiveJoinTask` unreachable

**Severity:** MEDIUM
**Task type:** EXCLUSIVE_JOIN
**SDK file:** `TaskType.java` (enum only)
**Server file:** `WorkflowTask.java:130` — `defaultExclusiveJoinTask: List<String>`

**What the server expects:**
EXCLUSIVE_JOIN uses `joinOn` (list of task refs to watch) and
`defaultExclusiveJoinTask` (fallback task refs if no branch ran).

**What the SDK provides:**
`TaskType.EXCLUSIVE_JOIN` is in the enum. No builder class exists. There is no way
to set `defaultExclusiveJoinTask` through the SDK API.

**Fix:**
```java
public class ExclusiveJoin extends Task<ExclusiveJoin> {
    public ExclusiveJoin(String taskReferenceName, String... joinOn) {
        super(taskReferenceName, TaskType.EXCLUSIVE_JOIN);
    }
    @Override
    protected void updateWorkflowTask(WorkflowTask task) {
        task.setJoinOn(Arrays.asList(joinOn));
        task.setDefaultExclusiveJoinTask(defaultJoin);
    }
}
```

---

### FINDING-6: Http — no fluent `connectionTimeout()` builder method

**Severity:** MEDIUM
**Task type:** HTTP
**SDK file:** `Http.java:84`
**Server file:** `HttpTask.java:274` — `connectionTimeOut: Integer`

**What the server expects:**
`http_request.connectionTimeOut` (milliseconds) is a supported field on the server's
`HttpTask.Input`.

**What the SDK provides:**
`Http.Input` has `connectionTimeOut` field, getter, and setter (lines 116, 229, 239).
The `Http` builder class has a fluent `readTimeout(int)` method (line 84) but no
`connectionTimeout(int)` method. Users must call `getHttpRequest().setConnectionTimeOut(n)`
directly, breaking the fluent builder pattern.

**Fix:**
```java
public Http connectionTimeout(int connectionTimeout) {
    this.httpRequest.setConnectionTimeOut(connectionTimeout);
    return this;
}
```

---

### FINDING-7: TaskType enum missing AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES

**Severity:** MEDIUM (new feature gap)
**SDK file:** `TaskType.java`
**Server file:** `TaskType.java` (server enum has all four)

**What the server has:**
```java
PULL_WORKFLOW_MESSAGES,
AGENT,
GET_AGENT_CARD,
CANCEL_AGENT;
```

**What the SDK has:**
The SDK `TaskType` enum stops at `CALL_MCP_TOOL`. All four values are absent. Any code
that calls `TaskType.of("AGENT")` will return `USER_DEFINED` instead of throwing, which
is silent but misleading.

**Fix:**
Add the four missing values to the SDK `TaskType` enum to match the server.

---

## Notes / Non-Findings

- **DynamicFork hardcoded `"forkedTasks"` key** — The SDK always uses `"forkedTasks"` as
  the internal `inputParameters` key and `dynamicForkTasksParam = "forkedTasks"` to match.
  The constructor parameter `forkTasksParameter` is the VALUE (an expression) that goes
  into that key, not the key name itself. This is consistent and correct. Not a bug.

- **Wait.java field names** — Correctly uses `DURATION_INPUT = "duration"` and
  `UNTIL_INPUT = "until"`. No bug.

- **DynamicFork deprecated field** — Uses `setDynamicForkTasksParam()` (current, not
  deprecated). Python SDK had this bug; Java SDK does not.

- **LAMBDA builder missing** — LAMBDA is server-deprecated in favour of INLINE; the SDK
  provides `Javascript` (INLINE) as the replacement. Expected gap.

---

## Summary by Severity

| Severity | Count | Findings |
|----------|-------|---------|
| ~~CRITICAL~~ | ~~1~~ | ~~FINDING-1: ForkJoin `List.of(String[])` — FALSE POSITIVE~~ |
| HIGH | 2 | FINDING-2: NOOP no builder; FINDING-3: START_WORKFLOW no builder |
| MEDIUM | 4 | FINDING-4: HUMAN no builder; FINDING-5: EXCLUSIVE_JOIN no builder; FINDING-6: Http connectionTimeout; FINDING-7: 4 missing enum values |

---

## Live Test Results

Run date: 2026-07-16, server: `http://loki.local:8080` (Conductor 3.32.0-rc.9)
Script: `java-sdk/live_test.sh`

| Finding | Result | Note |
|---------|--------|------|
| FINDING-1: ForkJoin.joinOn() | FALSE POSITIVE | `List.of(String[])` correctly uses target-type inference; no bug |
| FINDING-2: NOOP no builder | 🐛 CONFIRMED | Server accepts NOOP and completes — SDK gap only |
| FINDING-3: START_WORKFLOW no builder | 🐛 CONFIRMED | Server accepts START_WORKFLOW and completes — SDK gap only |
| FINDING-4: HUMAN no builder | 🐛 CONFIRMED | Server accepts HUMAN (RUNNING, awaiting signal) — SDK gap only |
| FINDING-5: EXCLUSIVE_JOIN no builder | 🐛 CONFIRMED | Server accepts EXCLUSIVE_JOIN and completes — SDK gap only |
| FINDING-6: Http no connectionTimeout() | 🐛 CONFIRMED | Server accepts connectionTimeOut field — SDK fluent method missing |
| FINDING-7: Missing enum values | 🐛 CONFIRMED | Server accepts AGENT task type — SDK enum missing 4 values |

**Summary: 6 static findings confirmed · 1 false positive retracted**

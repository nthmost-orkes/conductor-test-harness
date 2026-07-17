# C# SDK — Static Analysis

SDK: `conductor-oss/csharp-sdk`
Server baseline: Conductor `3.32.0-rc.9`
Analysis date: 2026-07-16

Methodology: see `../SDK_ANALYSIS_PROCEDURE.md`.

Builder classes live in: `Conductor/Definition/TaskType/`
TaskType enum: `Conductor/Client/Models/WorkflowTask.cs` (`WorkflowTaskTypeEnum`)

---

## Coverage Table

| Server TaskType | SDK enum | SDK builder class | Status |
|----------------|----------|------------------|--------|
| NOOP | ✗ | ✗ | MISSING |
| SWITCH | ✓ (SWITCH=6) | `SwitchTask.cs` | ✓ (supports both evaluators) |
| DO_WHILE | ✓ (DOWHILE=8) | `DoWhileTask.cs` | ✓ |
| FORK_JOIN | ✓ (FORKJOIN=3) | `ForkJoinTask.cs` | ✓ (user must supply JoinTask separately) |
| JOIN | ✓ (JOIN=7) | `JoinTask.cs` | ✓ (takes `params WorkflowTask[] joinOn`) |
| EXCLUSIVE_JOIN | ✓ (EXCLUSIVEJOIN=18) | ✗ | MISSING BUILDER |
| FORK_JOIN_DYNAMIC | ✓ (FORKJOINDYNAMIC=4) | `DynamicFork.cs` | ⚠ (Join has empty joinOn; deprecated field) |
| TERMINATE | ✓ (TERMINATE=19) | `TerminateTask.cs` | ✓ |
| START_WORKFLOW | ✓ (STARTWORKFLOW=10) | ✗ | MISSING BUILDER |
| SUB_WORKFLOW | ✓ (SUBWORKFLOW=9) | `SubWorkflowTask.cs` | ✓ |
| INLINE | ✓ (INLINE=17) | `JavascriptTask.cs` | ✓ |
| LAMBDA | ✓ (LAMBDA=16) | ✗ | MISSING BUILDER (server-deprecated; INLINE preferred) |
| JSON_JQ_TRANSFORM | ✓ (JSONJQTRANSFORM=21) | `JQTask.cs` | ✓ |
| SET_VARIABLE | ✓ (SETVARIABLE=22) | `SetVariableTask.cs` | ✓ |
| HTTP | ✓ (HTTP=15) | `HttpTask.cs` | ✓ (field names correct) |
| WAIT | ✓ (WAIT=12) | `WaitTask.cs` | ✓ |
| HUMAN | ✓ (HUMAN=13) | `HumanTask.cs` | ✓ |
| EVENT | ✓ (EVENT=11) | `EventTask.cs` | ✓ |
| AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| GET_AGENT_CARD | ✗ | ✗ | MISSING (new in rc.9) |
| CANCEL_AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| PULL_WORKFLOW_MESSAGES | ✗ | ✗ | MISSING |

---

## Findings

### FINDING-1: `DynamicFork` auto-join has empty `joinOn` — join completes immediately

**Severity:** HIGH
**Task type:** FORK_JOIN_DYNAMIC
**SDK file:** `Conductor/Definition/TaskType/DynamicFork.cs:32`

**What the SDK provides:**
```csharp
public DynamicFork(string taskReferenceName, ...) : base(...)
{
    this.Join = new JoinTask(taskReferenceName + "_join");  // no joinOn args
    ...
}
```

`JoinTask(string taskReferenceName, params WorkflowTask[] joinOn)` — called with zero args →
`JoinOn = new List<string>()` on the companion join task.

When the user adds `dynamicFork.Join` to the workflow definition, the JOIN task has empty
`joinOn`. The server Join executor: `joinOn.stream().allMatch(...)` on empty stream →
`true` → JOIN completes immediately without waiting for any dynamic fork branches.

**Impact:** Any workflow using `DynamicFork` whose join comes from `DynamicFork.Join` will
skip waiting for the dynamic branches. Dynamic tasks run in the background while downstream
tasks proceed immediately.

**Same root cause:** javascript-sdk#135, go-sdk#263, go-sdk#264.

**Fix:**
For dynamic forks, the branch tasks are determined at runtime, so there is no static list
to infer `joinOn` from. The API should document that users must supply `joinOn` explicitly,
or `DynamicFork` should not expose a zero-arg `Join` as a ready-to-use component:
```csharp
// Option: require explicit joinOn in DynamicFork
public DynamicFork(string taskReferenceName, string forkTasksParameter,
    string forkTasksInputsParameter, params WorkflowTask[] joinOn)
{
    this.Join = new JoinTask(taskReferenceName + "_join", joinOn);
    ...
}
```

---

### FINDING-2: `DynamicFork` uses deprecated `dynamicForkJoinTasksParam` field

**Severity:** MEDIUM
**Task type:** FORK_JOIN_DYNAMIC
**SDK file:** `Conductor/Definition/TaskType/DynamicFork.cs:41`

**What the SDK provides:**
```csharp
public override void UpdateWorkflowTask(WorkflowTask task)
{
    task.SetDynamicForkJoinTasksParam("forkedTasks");    // ← deprecated
    task.SetDynamicForkTasksInputParamName("forkedTasksInputs");
}
```

`SetDynamicForkJoinTasksParam()` sets `WorkflowTask.DynamicForkJoinTasksParam`, which
serializes as `"dynamicForkJoinTasksParam"` (deprecated JSON field).

The current field is `"dynamicForkTasksParam"` (set via `DynamicForkTasksParam` property
or a `SetDynamicForkTasksParam()` method that does not currently exist).

**Server behavior:** `ForkJoinDynamicTaskMapper.java:156` tries `getDynamicForkTasksParam()`
first; if null, falls back to the deprecated `getDynamicForkJoinTasksParam()`. The deprecated
field still works, but may be removed in a future server version.

**Fix:**
Add `SetDynamicForkTasksParam()` to `WorkflowTask` and call it from `DynamicFork`:
```csharp
task.SetDynamicForkTasksParam("forkedTasks");
```

---

### FINDING-3: Missing builders — NOOP, EXCLUSIVE_JOIN, START_WORKFLOW

**Severity:** MEDIUM
**SDK files:** `Conductor/Definition/TaskType/` (builders directory), `WorkflowTask.cs` (enum)

**Missing enum values:**
- `NOOP` — absent from `WorkflowTaskTypeEnum`; no builder

**Missing builders (enum exists, no builder class):**
- `EXCLUSIVE_JOIN` (enum: EXCLUSIVEJOIN=18) — no builder; `defaultExclusiveJoinTask` unreachable
- `START_WORKFLOW` (enum: STARTWORKFLOW=10) — no builder; `StartWorkflow` model class exists but
  no `StartWorkflowTask` task builder

**Fix (examples):**
```csharp
// NoopTask.cs
public class NoopTask : Task
{
    public NoopTask(string taskReferenceName)
        : base(taskReferenceName, WorkflowTask.WorkflowTaskTypeEnum.NOOP) { }
}

// ExclusiveJoinTask.cs
public class ExclusiveJoinTask : Task
{
    public ExclusiveJoinTask(string taskReferenceName, string[] joinOn,
        string[] defaultExclusiveJoinTask = null)
        : base(taskReferenceName, WorkflowTask.WorkflowTaskTypeEnum.EXCLUSIVEJOIN)
    {
        JoinOn = new List<string>(joinOn);
        if (defaultExclusiveJoinTask != null)
            DefaultExclusiveJoinTask = new List<string>(defaultExclusiveJoinTask);
    }
}
```

---

### FINDING-4: Missing TaskType enum values — AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES

**Severity:** MEDIUM (new feature gap)
**SDK file:** `Conductor/Client/Models/WorkflowTask.cs` — `WorkflowTaskTypeEnum`

**What the server has** (added in server PR #1288 / 3.32.0-rc.9):
- `AGENT`
- `GET_AGENT_CARD`
- `CANCEL_AGENT`
- `PULL_WORKFLOW_MESSAGES`

**What the SDK has:**
Enum ends at `WAITFORWEBHOOK = 30`. All four values absent.

**Fix:**
```csharp
[EnumMember(Value = "PULL_WORKFLOW_MESSAGES")]
PULLWORKFLOWMESSAGES = 31,

[EnumMember(Value = "AGENT")]
AGENT = 32,

[EnumMember(Value = "GET_AGENT_CARD")]
GETAGENTCARD = 33,

[EnumMember(Value = "CANCEL_AGENT")]
CANCELAGENT = 34,
```

Builder classes should follow once the agent task API stabilizes.

---

## Notes / Non-Findings

- **`HttpTaskSettings` field names** — `connectionTimeOut` (lowercase c) and `readTimeOut`
  (capital T in Out) are both correct. Unlike the Go SDK, the C# HTTP task uses the right
  field names. ✓

- **`ForkJoinTask.JoinOn`** — The `ForkJoinTask` constructor sets `JoinOn = new List<string>()`
  on the FORK_JOIN task itself. The server ignores `joinOn` on FORK tasks; `joinOn` is only
  meaningful on the companion JOIN task, which users must create separately using `JoinTask`.
  The `JoinTask` constructor correctly accepts `params WorkflowTask[] joinOn` — if called with
  the right arguments, joinOn will be properly set. **Not a bug**, but the API could be clearer.

- **`WaitTask` field names** — Uses `duration` and `until` correctly. ✓

- **`SwitchTask` evaluator** — Supports both `"value-param"` and `"javascript"` evaluator
  types. ✓ (JavaScript SDK lacked this.)

- **`LAMBDA`** — Enum exists, no builder. Server-deprecated in favour of INLINE. Not filing.

---

## Summary by Severity

| Severity | Count | Findings |
|----------|-------|---------|
| HIGH | 1 | FINDING-1: DynamicFork.Join empty joinOn — immediate completion |
| MEDIUM | 3 | FINDING-2: deprecated dynamicForkJoinTasksParam; FINDING-3: 3 missing builders; FINDING-4: 4 missing enum values |

---

## Live Test Status

No live test run — no C# runtime available in this environment.

- FINDING-1 (empty joinOn): same root cause as javascript-sdk#135 and go-sdk#263/#264, which were
  live-tested and confirmed against Conductor 3.32.0-rc.9 on the same server code path.
- FINDING-2 (deprecated field): server backward-compat confirmed by reading
  `ForkJoinDynamicTaskMapper.java:156`.
- FINDING-3/4 (missing constants/builders): server acceptance confirmed for same types in Java,
  JavaScript, and Go SDK audits against Conductor 3.32.0-rc.9.

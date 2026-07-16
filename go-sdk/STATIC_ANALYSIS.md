# Go SDK — Static Analysis

SDK: `conductor-oss/go-sdk`
Server baseline: Conductor `3.32.0-rc.9`
Analysis date: 2026-07-16

Methodology: see `../SDK_ANALYSIS_PROCEDURE.md`.

Builder structs live in: `sdk/workflow/`
TaskType constants: `sdk/workflow/task.go`

---

## Coverage Table

| Server TaskType | SDK constant | SDK builder | Status |
|----------------|-------------|-------------|--------|
| NOOP | ✗ | ✗ | MISSING |
| SWITCH | ✓ | `switch.go → NewSwitchTask()` | ✓ (has `UseJavascript()`) |
| DO_WHILE | ✓ | `do_while.go → NewDoWhileTask()`, `NewLoopTask()` | ✓ |
| FORK_JOIN | ✓ | `fork_join.go → NewForkTask()` | ⚠ (auto-join empty joinOn bug) |
| JOIN | ✓ | `join.go → NewJoinTask()` | ✓ |
| EXCLUSIVE_JOIN | ✗ | ✗ | MISSING |
| FORK_JOIN_DYNAMIC | ✓ | `fork_join_dynamic.go → NewDynamicForkTask()` | ⚠ (auto-join ignores stored join; joinOn always empty) |
| TERMINATE | ✓ | `terminate.go → NewTerminateTask()` | ✓ |
| START_WORKFLOW | ✓ | `start_workflow.go → NewStartWorkflowTask()` | ✓ |
| SUB_WORKFLOW | ✓ | `sub_workflow.go → NewSubWorkflowTask()` | ✓ |
| INLINE | ✓ | `inline.go → NewInlineTask()`, `NewInlineGraalJSTask()` | ✓ |
| LAMBDA | ✗ | ✗ | MISSING (server-deprecated; INLINE preferred) |
| JSON_JQ_TRANSFORM | ✓ | `json_jq.go → NewJQTask()` | ✓ |
| SET_VARIABLE | ✓ | `set_variable.go → NewSetVariableTask()` | ✓ |
| HTTP | ✓ | `http.go → NewHttpTask()` | ⚠ CRITICAL (wrong JSON field names) |
| WAIT | ✓ | `wait.go → NewWaitTask()`, `NewWaitForDurationTask()`, `NewWaitUntilTask()` | ✓ |
| HUMAN | ✓ | `human.go → NewHumanTask()` | ✓ |
| EVENT | ✓ | `event.go → NewSqsEventTask()`, `NewConductorEventTask()` | ✓ |
| AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| GET_AGENT_CARD | ✗ | ✗ | MISSING (new in rc.9) |
| CANCEL_AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| PULL_WORKFLOW_MESSAGES | ✗ | ✗ | MISSING |

### Extra builders (Orkes/OSS-specific, not in core server task types)

| Builder | TaskType constant | Notes |
|---------|-----------------|-------|
| `http_poll.go` | HTTP_POLL | Orkes enterprise |
| `kafka_publish.go` | KAFKA_PUBLISH | Orkes/community |
| `dynamic.go` | DYNAMIC | OSS ✓ |
| `get_workflow.go` | GET_WORKFLOW | Orkes |
| `update.go` | UPDATE_TASK | OSS ✓ |
| `yield.go` | YIELD | Orkes |

---

## Findings

### FINDING-1: `HttpInput` JSON field names wrong — `connectionTimeOut` and `readTimeOut` silently ignored

**Severity:** HIGH
**Task type:** HTTP
**SDK file:** `sdk/workflow/http.go` (HttpInput struct)
**Server file:** `http-task/.../HttpTask.java:274-275`

**What the server expects:**
```java
private Integer connectionTimeOut = 3000;
private Integer readTimeOut = 3000;
```
Jackson serializes these as `"connectionTimeOut"` (lowercase c) and `"readTimeOut"` (capital T).

**What the SDK provides:**
```go
type HttpInput struct {
    ...
    ConnectionTimeOut int16 `json:"ConnectionTimeOut,omitempty"`  // wrong: capital C
    ReadTimeout       int16 `json:"readTimeout,omitempty"`         // wrong: lowercase t (should be readTimeOut)
}
```

The Go SDK serializes:
- `"ConnectionTimeOut"` — server reads `"connectionTimeOut"` → **capital C mismatch, field ignored**
- `"readTimeout"` — server reads `"readTimeOut"` → **missing capital T in Out, field ignored**

Both timeout values are silently discarded; the server uses its defaults (3000ms each).

**Secondary issue:** `int16` max value is 32,767. Any timeout above ~32 seconds overflows to a
negative value. Server field is `Integer` — both fields should be `int` or `int32` in Go.

**Fix:**
```go
type HttpInput struct {
    ...
    ConnectionTimeOut int `json:"connectionTimeOut,omitempty"`  // lowercase c; int not int16
    ReadTimeout       int `json:"readTimeOut,omitempty"`         // capital T in Out; int not int16
}
```

---

### FINDING-2: `NewForkTask()` auto-join has empty `joinOn` — join completes immediately

**Severity:** HIGH
**Task type:** FORK_JOIN
**SDK file:** `sdk/workflow/fork_join.go` — `getJoinTask()` function

**What the server expects:**
`JoinOn` on the JOIN task must list task reference names to wait for. Empty → join
completes immediately (same root cause as javascript-sdk#135).

**What the SDK provides:**
```go
func (task *ForkTask) getJoinTask() model.WorkflowTask {
    join := task.join
    if join == nil {
        join = NewJoinTask(task.taskReferenceName + "_join")  // no joinOn args
    }
    return (join.toWorkflowTask())[0]
}
```

`NewJoinTask(name)` with no varargs → `joinOn: nil` → serialized as empty → join
completes immediately.

Workaround exists: `NewForkTaskWithJoin(ref, joinTask, ...)` lets the user supply a
`*JoinTask` with explicit `joinOn`. But `NewForkTask()` (the common path) always produces
a broken auto-join.

**Fix:**
Infer `joinOn` from the last task reference name in each fork branch:
```go
func (task *ForkTask) getJoinTask() model.WorkflowTask {
    join := task.join
    if join == nil {
        joinOn := make([]string, len(task.forkedTasks))
        for i, branch := range task.forkedTasks {
            if len(branch) > 0 {
                joinOn[i] = branch[len(branch)-1].toWorkflowTask()[0].TaskReferenceName
            }
        }
        join = NewJoinTask(task.taskReferenceName+"_join", joinOn...)
    }
    return (join.toWorkflowTask())[0]
}
```

---

### FINDING-3: `DynamicForkTask.getJoinTask()` ignores the stored `join` field; `joinOn` always empty

**Severity:** HIGH
**Task type:** FORK_JOIN_DYNAMIC
**SDK file:** `sdk/workflow/fork_join_dynamic.go` — `getJoinTask()`, `NewDynamicForkWithJoinTask()`

**What the SDK provides:**
```go
// NewDynamicForkWithJoinTask stores a join — but getJoinTask() never uses it:
func (task *DynamicForkTask) getJoinTask() model.WorkflowTask {
    join := NewJoinTask(task.taskReferenceName + "_join")  // always creates new, ignores task.join
    return (join.toWorkflowTask())[0]
}
```

`task.join` is populated by `NewDynamicForkWithJoinTask()` but is permanently ignored.
Every `DynamicForkTask` — regardless of how it was constructed — produces a JOIN with
empty `joinOn`. The constructor offering a `join` parameter is misleading.

**Fix:**
```go
func (task *DynamicForkTask) getJoinTask() model.WorkflowTask {
    if task.join.joinOn != nil {
        return (task.join.toWorkflowTask())[0]
    }
    // for dynamic fork, no auto-detection is possible (tasks are dynamic)
    // fall back to empty join but at least use the stored join's name
    return (NewJoinTask(task.taskReferenceName + "_join")).toWorkflowTask()[0]
}
```

---

### FINDING-4: Missing TaskType constants — NOOP, EXCLUSIVE_JOIN, AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES

**Severity:** MEDIUM (HIGH for NOOP — commonly used)
**SDK file:** `sdk/workflow/task.go` (TaskType constants block)

**What the server has:**
NOOP, EXCLUSIVE_JOIN (both OSS), and AGENT/GET_AGENT_CARD/CANCEL_AGENT/PULL_WORKFLOW_MESSAGES
(added in PR #1288 / 3.32.0-rc.9).

**What the SDK has:**
```go
const (
    SIMPLE            TaskType = "SIMPLE"
    // ... 21 constants total
    // NOOP, EXCLUSIVE_JOIN, AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES absent
)
```

No builder structs exist for any of these types.

**Fix:**
Add to `task.go`:
```go
NOOP             TaskType = "NOOP"
EXCLUSIVE_JOIN   TaskType = "EXCLUSIVE_JOIN"
AGENT            TaskType = "AGENT"
GET_AGENT_CARD   TaskType = "GET_AGENT_CARD"
CANCEL_AGENT     TaskType = "CANCEL_AGENT"
PULL_WORKFLOW_MESSAGES TaskType = "PULL_WORKFLOW_MESSAGES"
```

Add `noop.go` with `NewNoopTask(taskRefName string)` and `exclusive_join.go` with
`NewExclusiveJoinTask(taskRefName string, joinOn ...string)`.

---

## Notes / Non-Findings

- **`SwitchTask.UseJavascript(true)`** — correctly sets `evaluatorType = "javascript"` and
  uses the raw expression as the JS script. JS SDK had this gap; Go SDK does not.

- **`WaitTask` field names** — `NewWaitForDurationTask` uses `"duration"` key and
  `NewWaitUntilTask` uses `"until"` key. Both correct. Python SDK had the `wait_until` bug;
  Go SDK does not.

- **`DynamicForkTask` field names** — sets `DynamicForkTasksParam = "forkedTasks"` and
  `DynamicForkTasksInputParamName = "forkedTasksInputs"` (non-deprecated). Python SDK had
  the deprecated-field bug; Go SDK does not.

- **LAMBDA missing** — LAMBDA is server-deprecated in favour of INLINE. Not filing.

---

## Summary by Severity

| Severity | Count | Findings |
|----------|-------|---------|
| HIGH | 3 | FINDING-1: HttpInput wrong JSON field names; FINDING-2: ForkTask empty joinOn; FINDING-3: DynamicForkTask ignores stored join |
| MEDIUM | 1 | FINDING-4: 6 missing TaskType constants (NOOP, EXCLUSIVE_JOIN, AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES) |

---

## Live Test Results

Run date: 2026-07-16, server: `http://loki.local:8080` (Conductor 3.32.0-rc.9)
Script: `go-sdk/live_test.sh`

| Finding | Result | Note |
|---------|--------|------|
| FINDING-1: HttpInput wrong JSON field names | 🐛 CONFIRMED | Server accepts `connectionTimeOut`/`readTimeOut`; Go SDK serializes `ConnectionTimeOut`/`readTimeout` — both silently ignored |
| FINDING-2: ForkTask empty joinOn | 🐛 CONFIRMED | `joinOn=[]` → `join1=COMPLETED` while `w1=IN_PROGRESS` (10s WAIT branch, checked at 3s) |
| FINDING-3: DynamicForkTask ignores stored join | 🐛 CONFIRMED | Static — code inspection; same root cause as FINDING-2 |
| FINDING-4: Missing TaskType constants | 🐛 CONFIRMED | Server accepts NOOP; EXCLUSIVE_JOIN, AGENT confirmed in java+js tests |

**Key live evidence for FINDING-2:**
```
After 3s (10s WAIT branch):
  joinOn=[]   → wf=RUNNING join1=COMPLETED w1=IN_PROGRESS  ← BUG
  joinOn=[w1] → wf=RUNNING join1=IN_PROGRESS w1=IN_PROGRESS  ← CORRECT
```

**Summary: 4 confirmed (2 runtime, 2 static/code-inspection)**

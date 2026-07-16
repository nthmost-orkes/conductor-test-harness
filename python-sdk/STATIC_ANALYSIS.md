# Python SDK — Static Analysis

SDK: `conductor-oss/python-sdk`
Server baseline: Conductor `3.32.0-rc.9`
Analysis date: 2026-07-16

Methodology: see `../SDK_ANALYSIS_PROCEDURE.md`.

---

## Coverage Table

For each server `TaskType`, whether the Python SDK has (a) an enum value in
`task_type.py` and (b) a builder class in `workflow/task/`.

| Server TaskType | SDK enum | SDK builder class | Status |
|----------------|----------|-------------------|--------|
| NOOP | ✗ | ✗ | MISSING |
| SWITCH | ✓ | `switch_task.py` → `SwitchTask` | ✓ |
| DO_WHILE | ✓ | `do_while_task.py` → `DoWhileTask`, `LoopTask`, `ForEachTask` | ✓ |
| FORK_JOIN | ✓ | `fork_task.py` → `ForkTask` | ✓ |
| JOIN | ✓ | `join_task.py` → `JoinTask` | ✓ |
| EXCLUSIVE_JOIN | ✓ | ✗ (no builder) | PARTIAL |
| FORK_JOIN_DYNAMIC | ✓ | `dynamic_fork_task.py` → `DynamicForkTask` | ⚠ (deprecated field) |
| TERMINATE | ✓ | `terminate_task.py` → `TerminateTask` | ✓ |
| START_WORKFLOW | ✓ | `start_workflow_task.py` → `StartWorkflowTask` | ✓ |
| SUB_WORKFLOW | ✓ | `sub_workflow_task.py` → `SubWorkflowTask` | ✓ |
| INLINE | ✓ | `inline.py` → `InlineTask` | ✓ |
| LAMBDA | ✓ | ✗ (no builder) | MISSING BUILDER |
| JSON_JQ_TRANSFORM | ✓ | `json_jq_task.py` → `JsonJQTask` | ✓ |
| SET_VARIABLE | ✓ | `set_variable_task.py` → `SetVariableTask` | ✓ |
| HTTP | ✓ | `http_task.py` → `HttpTask`, `HttpInput` | ✓ |
| WAIT | ✓ | `wait_task.py` → `WaitTask`, `WaitForDurationTask`, `WaitUntilTask` | ⚠ (base class bug) |
| HUMAN | ✓ | `human_task.py` → `HumanTask` | ✓ |
| EVENT | ✓ | `event_task.py` → `ConductorEventTask`, `SqsEventTask` | ✓ |
| AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| GET_AGENT_CARD | ✗ | ✗ | MISSING (new in rc.9) |
| CANCEL_AGENT | ✗ | ✗ | MISSING (new in rc.9) |

---

## Findings

### FINDING-1: WAIT task — WaitTask base class uses wrong field name

**Severity:** HIGH
**Task type:** WAIT
**SDK file:** `src/conductor/client/workflow/task/wait_task.py:26`
**Server file:** `core/src/main/java/com/netflix/conductor/core/execution/tasks/Wait.java:31`

**What the server expects:**
```java
public static final String UNTIL_INPUT = "until";
```
The WAIT executor reads `inputParameters["until"]` for date/time input.

**What the SDK provides:**
`WaitTask.__init__()` (the base class) sets `"wait_until"` when `wait_until` is given:
```python
self.input_parameters = {"wait_until": wait_until}   # WRONG KEY
```

**Impact:**
`WaitTask(ref, wait_until="2023-12-25 05:25 PST")` silently fails — the `wait_until` key
is unknown to the server, the task waits indefinitely. The subclass `WaitUntilTask`
correctly uses `"until"` and is unaffected. Only the base class when called with
`wait_until=` is broken.

**Fix:**
```python
self.input_parameters = {"until": wait_until}   # line 26 of wait_task.py
```

---

### FINDING-2: LAMBDA task — enum value exists but no builder class

**Severity:** CRITICAL
**Task type:** LAMBDA
**SDK file:** `src/conductor/client/workflow/task/task_type.py:22`
**Server file:** N/A (LAMBDA is a server system task; inputs: `scriptExpression`, `lambdaValue`)

**What the server expects:**
LAMBDA tasks expect `inputParameters` with `scriptExpression` (the JS body) and
optionally `lambdaValue`.

**What the SDK provides:**
`TaskType.LAMBDA` exists in the enum, but there is no `LambdaTask` builder class anywhere
in the SDK. Users cannot construct a LAMBDA workflow task via the SDK — they would need
to fall back to raw dicts.

**Fix:**
Create `lambda_task.py` with a `LambdaTask` class analogous to `InlineTask`:
```python
class LambdaTask(TaskInterface):
    def __init__(self, task_ref_name: str, script: str, bindings: Optional[Dict[str, str]] = None):
        super().__init__(task_ref_name, TaskType.LAMBDA,
                         input_parameters={"scriptExpression": script})
        if bindings:
            self.input_parameters.update(bindings)
```

---

### FINDING-3: FORK_JOIN_DYNAMIC — sets deprecated field

**Severity:** HIGH
**Task type:** FORK_JOIN_DYNAMIC
**SDK file:** `src/conductor/client/workflow/task/dynamic_fork_task.py:24`
**Server file:** `common/src/main/java/com/netflix/conductor/common/metadata/workflow/WorkflowTask.java:92-95`

**What the server expects:**
```java
@Deprecated private String dynamicForkJoinTasksParam;  // line 92
private String dynamicForkTasksParam;                   // line 95 — current field
```

**What the SDK provides:**
```python
wf_task.dynamic_fork_join_tasks_param = self.tasks_param   # sets the deprecated field
```
The SDK sets `dynamicForkJoinTasksParam` (deprecated) rather than `dynamicForkTasksParam`
(current). The deprecated field may still be read by the server mapper, so this may not
break immediately, but it is incorrect and will break when the deprecated field is removed.

**Fix:**
```python
wf_task.dynamic_fork_tasks_param = self.tasks_param   # use current field
```

---

### FINDING-4: EXCLUSIVE_JOIN — no builder class; defaultExclusiveJoinTask unavailable

**Severity:** MEDIUM
**Task type:** EXCLUSIVE_JOIN
**SDK file:** `src/conductor/client/workflow/task/task_type.py` (enum only)
**Server file:** `common/src/main/java/com/netflix/conductor/common/metadata/workflow/WorkflowTask.java:130`

**What the server expects:**
EXCLUSIVE_JOIN uses two fields on `WorkflowTask`:
- `joinOn`: list of task ref names to watch
- `defaultExclusiveJoinTask`: list — task ref name(s) to use if no branch ran

**What the SDK provides:**
`TaskType.EXCLUSIVE_JOIN` is in the enum but there is no `ExclusiveJoinTask` class.
`JoinTask` always produces `TaskType.JOIN`. Users cannot create a typed EXCLUSIVE_JOIN
task or set `defaultExclusiveJoinTask` through any SDK path.

**Fix:**
Create `ExclusiveJoinTask` in `join_task.py` or a new file:
```python
class ExclusiveJoinTask(TaskInterface):
    def __init__(self, task_ref_name: str, join_on: List[str],
                 default_exclusive_join_task: Optional[List[str]] = None):
        super().__init__(task_ref_name, TaskType.EXCLUSIVE_JOIN)
        self._join_on = join_on
        self._default = default_exclusive_join_task or []

    def to_workflow_task(self) -> WorkflowTask:
        wf = super().to_workflow_task()
        wf.join_on = self._join_on
        wf.default_exclusive_join_task = self._default
        return wf
```

---

### FINDING-5: NOOP — completely absent from SDK

**Severity:** HIGH
**Task type:** NOOP
**SDK file:** N/A
**Server file:** `common/src/main/java/com/netflix/conductor/common/metadata/tasks/TaskType.java:44`

**What the server expects:**
NOOP is a system task that completes immediately with no inputParameters. It appears in
`TaskType.TASK_TYPE_NOOP = "NOOP"` and in `TaskType.NOOP`. No mapper required — it
transitions to COMPLETED on first poll.

**What the SDK provides:** Nothing. `TaskType.NOOP` is not in the enum; no builder class exists.

**Fix:**
Add to `task_type.py`:
```python
NOOP = "NOOP"
```
Add `noop_task.py`:
```python
class NoopTask(TaskInterface):
    def __init__(self, task_ref_name: str):
        super().__init__(task_ref_name, TaskType.NOOP)
```

---

### FINDING-6: AGENT / GET_AGENT_CARD / CANCEL_AGENT — new server types, no SDK support

**Severity:** HIGH (new feature gap)
**Task types:** AGENT, GET_AGENT_CARD, CANCEL_AGENT
**SDK file:** N/A
**Server file:** `common/src/main/java/com/netflix/conductor/common/metadata/tasks/TaskType.java` (added in PR #1288)

**What the server expects:** Three new task types added in conductor 3.32.0-rc.9 to support
A2A conductor agent workflows.

**What the SDK provides:** None — these types are not in the Python SDK `TaskType` enum and
no builder classes exist.

**Fix:** Implement after the server API for these types is stable. At minimum, add the enum
values so users can construct raw WorkflowTask dicts with the correct type string.

---

## Notes / Non-Findings

- **InlineTask uses `"graaljs"` evaluatorType** — The server's `GraalJSEvaluator` registers
  under name `"graaljs"` and `JavascriptEvaluator` registers under `"javascript"`. Both are
  valid. The SDK's choice of `"graaljs"` works but diverges from the server's documented
  default (`"javascript"`). Not a bug.

- **HTTP task `encode` field** — Agent initially flagged this as missing. Confirmed: the server's
  `HttpTask.Input` class does not have an `encode` field. Not a gap.

- **DO_WHILE `items` field** — `ForEachTask` correctly calls
  `super().input_parameter("items", iterate_over)`. Covered.

---

## Summary by Severity

| Severity | Count | Findings |
|----------|-------|---------|
| CRITICAL | 1 | LAMBDA — enum exists, builder missing |
| HIGH | 4 | WAIT base class wrong key; NOOP absent; FORK_JOIN_DYNAMIC deprecated field; AGENT tasks absent |
| MEDIUM | 1 | EXCLUSIVE_JOIN — no builder, `defaultExclusiveJoinTask` inaccessible |

---

## Live Test Status

Not yet run. See `../SDK_ANALYSIS_PROCEDURE.md` Phase 2 for procedure.
When run, results will be added here under "Live Test Results."

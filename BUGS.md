# Conductor OSS — Bugs Found by Kitchen Sink Battery

Bugs discovered by running the kitchen-sink workflow battery against `3.32.0-rc.9`
on 2026-07-16. Each section lists the symptom, the root cause, the affected
workflow(s), and the file(s) to look at for a fix.

---

## BUG-1 (CONFIRMED): Nested DO_WHILE loopCondition TypeError

**GitHub issue:** conductor-oss/conductor#1307

**Status:** Fix implemented in `DoWhile.java` — **needs PR**

**Symptom:** When a DO_WHILE task is nested inside another DO_WHILE's loopOver,
the inner loop fails immediately with:
```
Unable to evaluate condition if ($.innerRef['iteration'] < $.maxIter) ...
TypeError: Cannot read property 'iteration' of undefined
```

**Root cause:** `DoWhile.java::evaluateCondition()` (line 518) puts the
DO_WHILE task's own output into the condition evaluation context using the raw
`task.getReferenceTaskName()`. For a nested task, this name includes the outer
loop's iteration suffix (e.g. `dwdw_inner__1` instead of `dwdw_inner`). The
loopCondition references `$.dwdw_inner['iteration']` (no suffix), so the lookup
fails.

The loop body tasks (lines 534-536) correctly call
`TaskUtils.removeIterationFromTaskRefName()` to strip the suffix — but the
self-reference on line 518 does not.

**Fix:**
```java
// DoWhile.java line 518 — original
conditionInput.put(task.getReferenceTaskName(), task.getOutputData());

// Fixed
conditionInput.put(
    TaskUtils.removeIterationFromTaskRefName(task.getReferenceTaskName()),
    task.getOutputData());
```

**Affected workflows:** `ks_combo_do_while_do_while`, `ks_deep_nesting` (deep variant)

**Files:** `core/src/main/java/com/netflix/conductor/core/execution/tasks/DoWhile.java`

---

## BUG-2 (CONFIRMED): Nested DO_WHILE body tasks collide when outer loop iterates N>1

**GitHub issue:** conductor-oss/conductor#1308

**Status:** Open — needs investigation

**Symptom:** When an outer DO_WHILE runs more than 1 iteration and contains an
inner DO_WHILE, the inner loop's body tasks use names that collide with names
already created in the first outer iteration. The workflow gets stuck in RUNNING
state and never completes (timeout).

**Example:** With outer=2, inner=2:
- Outer iter 1 creates: `dwdw_inner__1`, body tasks `dwdw_body__1`, `dwdw_body__2`
- Outer iter 2 creates: `dwdw_inner__2`, but tries to create body tasks named
  `dwdw_body__1` and `dwdw_body__2` again — those already exist!

The naming scheme only appends one level of iteration suffix. Nested loops
need compound suffixes (e.g. `dwdw_body__outer_iter__inner_iter`) or equivalent.

**Workaround:** Limit outer DO_WHILE to 1 iteration in tests. The inner loop
can still run multiple iterations safely (only body task naming is affected).

**Affected workflows (as tested):** `ks_combo_do_while_do_while`, `ks_deep_nesting` (deep variant)

**Files:** Task scheduling code in `DoWhile.java`, `WorkflowExecutorOps.java`, and
wherever `appendIteration` is called for loopOver task scheduling.

---

## BUG-3 (CONFIRMED): FORK_JOIN + EXCLUSIVE_JOIN fails at runtime but passes registration

**GitHub issue:** conductor-oss/conductor#1309

**Status:** Open — needs validator fix

**Symptom:** A workflow definition with FORK_JOIN followed immediately by
EXCLUSIVE_JOIN (instead of JOIN) registers successfully via `PUT /api/metadata/workflow`
but fails at runtime with:
```
Fork task definition is not followed by a join task.  Check the blueprint
```

**Root cause:** `ForkJoinTaskMapper.java` checks:
```java
if (joinWorkflowTask == null || !joinWorkflowTask.getType().equals(TaskType.JOIN.name())) {
    throw new TerminateWorkflowException("Fork task definition is not followed by a join task...");
}
```
`TaskType.JOIN.name()` is the literal string `"JOIN"`. EXCLUSIVE_JOIN does not
match, so it always fails at runtime. The workflow registration validator does
not perform this check.

**Design question:** EXCLUSIVE_JOIN is designed for SWITCH branches (where only
one branch executes). FORK_JOIN runs all branches in parallel and requires JOIN
to wait for all. Whether EXCLUSIVE_JOIN-after-FORK should be *supported* (pick
first completed) or *prohibited* (documentation) needs a decision. Either way,
the registration-time validator should catch this and reject the definition with
a clear error, rather than letting it pass and fail silently at runtime.

**Files:**
- `core/src/main/java/com/netflix/conductor/core/execution/mapper/ForkJoinTaskMapper.java`
- Validation code in `WorkflowTaskTypeConstraint.java` or wherever workflow definitions are validated on registration

---

## BUG-4 (CONFIRMED): WAIT task emits misleading error for wrong duration format

**GitHub issue:** conductor-oss/conductor#1310

**Status:** Open

**Symptom:** Using ISO-8601 duration format (`"PT1S"`) in a WAIT task produces:
```
Either date or duration is passed as null
```

**Actual cause:** `DateTimeUtils.parseDuration()` uses a custom regex that only
accepts `"1s"`, `"2m"`, `"1h 30m"` etc. It does NOT accept ISO-8601. When the
regex fails to match, it throws `IllegalArgumentException` which is caught and
wrapped in the misleading "passed as null" message.

The error message implies a missing value, but the real issue is format mismatch.
"PT1S" is a perfectly reasonable thing to try.

**Fix options:**
1. Accept both formats in `parseDuration()`
2. Emit a clearer error: "WAIT duration must use format '1s', '2m', '1h 30m' — ISO-8601 (e.g. 'PT1S') is not supported"
3. At minimum, update the error message and API docs

**Files:** `core/src/main/java/com/netflix/conductor/core/utils/DateTimeUtils.java`

---

## BUG-5 (CONFIRMED): SWITCH javascript evaluator validates expression at registration with no bindings

**GitHub issue:** conductor-oss/conductor#1311

**Status:** Open — needs validator fix

**Symptom:** A SWITCH task with `"evaluatorType": "javascript"` fails registration
with `Expression is not well formatted: ReferenceError: <var> is not defined` if
the expression references any variable (including `inputParameters` keys). Example:
```json
"expression": "value > 10 ? 'big' : 'small'"
```
fails even though `value` would be available at runtime via inputParameters.

**Root cause:** The registration validator actually executes the JS expression with
no bindings to "validate" it. Any runtime-bound variable is undefined at
validation time, so expressions that depend on inputParameters are impossible.

**Impact:** Only constant-valued SWITCH JS expressions work (e.g. `"'big'"`, `"1+1"`).
This makes the javascript evaluator essentially useless for dynamic dispatch, which
is its primary use case.

**Files:** `core/src/main/java/com/netflix/conductor/validations/WorkflowTaskTypeConstraint.java`

---

## Documentation Gap: INLINE task inputParameters accessible only as `$`, not bare names

**Status:** Documentation only; not a bug

INLINE task expressions receive inputParameters bound as the `$` global variable
only. Bare variable names are not injected into scope. Example:

```json
{
  "type": "INLINE",
  "inputParameters": {
    "expression": "(function(){ return {x: counter}; })()",   // WRONG: counter is undefined
    "evaluatorType": "javascript",
    "counter": "${workflow.variables.counter}"
  }
}
```

The expression must use `$.counter`, not `counter`:
```json
"expression": "(function(){ return {x: $.counter}; })()"   // CORRECT
```

This is correct behavior (matches the ScriptEvaluator implementation), but it
should be documented more prominently in the INLINE task docs and the error
"ReferenceError: counter is not defined" could include a hint about using `$.counter`.

**Files:** `core/src/main/java/com/netflix/conductor/core/events/ScriptEvaluator.java`

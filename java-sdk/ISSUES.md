# Java SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`).
Server baseline: Conductor **3.32.0-rc.9**.

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## CRITICAL

- [ ] **ForkJoin `joinOn()` produces `List<String[]>` instead of `List<String>`**
  `ForkJoin.java:119` — `List.of(this.join.getJoinOn())` wraps the `String[]` returned
  by `Join.getJoinOn()` as a single element, producing `List<String[]>`. Jackson
  serializes this as `[["task_a","task_b"]]` instead of `["task_a","task_b"]`. Join
  logic fails silently.
  Fix: `Arrays.asList(this.join.getJoinOn())`

## HIGH

- [ ] **NOOP: no builder class** — `TaskType.NOOP` in enum, no `Noop` builder.
  Fix: trivial — `new Noop(ref)` with no required inputParameters.

- [ ] **START_WORKFLOW: no builder class** — `TaskType.START_WORKFLOW` in enum but
  no builder. Users cannot programmatically start a child workflow.
  Fix: `StartWorkflow(ref, workflowName)` wrapping a `startWorkflow` object.

## MEDIUM

- [ ] **HUMAN: no builder class** — `TaskType.HUMAN` in enum, no `Human` builder.
  Fix: trivial — `new Human(ref)` with no required inputParameters.

- [ ] **EXCLUSIVE_JOIN: no builder class** — `TaskType.EXCLUSIVE_JOIN` in enum but
  no builder; `defaultExclusiveJoinTask` field unreachable.
  Fix: `ExclusiveJoin(ref, joinOn...)` with `defaultExclusiveJoinTask` setter.

- [ ] **Http: no fluent `connectionTimeout()` method** — `Http.Input` has field and
  setter but the `Http` builder only has `readTimeout()`. Breaks fluent builder pattern.
  Fix: add `connectionTimeout(int)` method mirroring `readTimeout(int)`.

- [ ] **TaskType enum missing 4 server values**: AGENT, GET_AGENT_CARD, CANCEL_AGENT,
  PULL_WORKFLOW_MESSAGES — all in server but absent from SDK enum. `TaskType.of()` silently
  returns `USER_DEFINED` for these.
  Fix: add to `TaskType.java` to match server.

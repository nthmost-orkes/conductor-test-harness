# Java SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`).
Server baseline: Conductor **3.32.0-rc.9**.

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## ~~CRITICAL~~ (retracted)

- [~] ~~**ForkJoin `joinOn()` produces `List<String[]>` instead of `List<String>`**~~ **FALSE POSITIVE**
  Live verification proved this works correctly. Java's target-type inference forces `E=String`
  when passing `String[]` to `List.of()` in context of `setJoinOn(List<String>)`.
  No issue to file.

## HIGH

- [x] **#130 — NOOP: no builder class** — `TaskType.NOOP` in enum, no `Noop` builder.
  Fix: trivial — `new Noop(ref)` with no required inputParameters.
  *[~] Live: server completes NOOP correctly via raw WorkflowTask*

- [x] **#131 — START_WORKFLOW: no builder class** — `TaskType.START_WORKFLOW` in enum but
  no builder. Users cannot programmatically start a child workflow.
  Fix: `StartWorkflow(ref, workflowName)` wrapping a `startWorkflow` object.
  *[~] Live: server completes START_WORKFLOW correctly via raw WorkflowTask*

## MEDIUM

- [x] **#132 — HUMAN: no builder class** — `TaskType.HUMAN` in enum, no `Human` builder.
  Fix: trivial — `new Human(ref)` with no required inputParameters.
  *[~] Live: server accepts HUMAN (RUNNING, awaiting human signal) via raw WorkflowTask*

- [x] **#133 — EXCLUSIVE_JOIN: no builder class** — `TaskType.EXCLUSIVE_JOIN` in enum but
  no builder; `defaultExclusiveJoinTask` field unreachable.
  Fix: `ExclusiveJoin(ref, joinOn...)` with `defaultExclusiveJoinTask` setter.
  *[~] Live: server completes EXCLUSIVE_JOIN in SWITCH workflow via raw WorkflowTask*

- [x] **#134 — Http: no fluent `connectionTimeout()` method** — `Http.Input` has field and
  setter but the `Http` builder only has `readTimeout()`. Breaks fluent builder pattern.
  Fix: add `connectionTimeout(int)` method mirroring `readTimeout(int)`.
  *[~] Live: server accepts `connectionTimeOut` field in `http_request`*

- [x] **#135 — TaskType enum missing 4 server values**: AGENT, GET_AGENT_CARD, CANCEL_AGENT,
  PULL_WORKFLOW_MESSAGES — all in server but absent from SDK enum. `TaskType.of()` silently
  returns `USER_DEFINED` for these.
  Fix: add to `TaskType.java` to match server.
  *[~] Live: server accepts AGENT task type via raw WorkflowTask*

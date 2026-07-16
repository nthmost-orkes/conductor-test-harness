# Python SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`) and live testing (`live_test.py`).
Server baseline: Conductor **3.32.0-rc.9**.

Status key: `[x]` = filed · `[~]` = verified by live test

---

## CRITICAL

- [x] **#427 — LAMBDA task: no builder class** (enum value exists in `task_type.py` but
  no `LambdaTask` class)
  Files: `src/conductor/client/workflow/task/task_type.py`
  Fix: add `lambda_task.py` with `LambdaTask(task_ref_name, script, bindings=None)`
  *[~] Live: server runs LAMBDA correctly via raw dict*

- [x] **#428 — FORK_JOIN_DYNAMIC broken: deprecated field now rejected by server**
  `DynamicForkTask.to_workflow_task()` sets `dynamic_fork_join_tasks_param` (deprecated);
  server returns HTTP 400. `DynamicForkTask` is completely unusable via SDK.
  Fix: use `dynamic_fork_tasks_param` + `dynamic_fork_tasks_input_param_name`.
  File: `src/conductor/client/workflow/task/dynamic_fork_task.py:24`
  *[~] Live: registration fails with HTTP 400*

## HIGH

- [x] **#426 — WaitTask base class wrong field name**: `__init__(wait_until=...)` sets
  `"wait_until"` key; server reads `"until"`. Task stays RUNNING indefinitely.
  File: `src/conductor/client/workflow/task/wait_task.py:26`
  Fix: change `"wait_until"` → `"until"` in base class constructor
  *[~] Live: task remained RUNNING for 10 s; WaitUntilTask subclass unaffected*

- [x] **#430 — NOOP task: completely absent** — not in enum, no builder
  Fix: add `NOOP = "NOOP"` to enum; add `noop_task.py` with `NoopTask`
  *[~] Live: server runs NOOP correctly via raw dict*

- [x] **#431 — AGENT / GET_AGENT_CARD / CANCEL_AGENT: missing from SDK** — new in server
  3.32.0-rc.9 (conductor-oss/conductor PR #1288), not yet in Python SDK

## MEDIUM

- [x] **#429 — EXCLUSIVE_JOIN: no builder class** — `TaskType.EXCLUSIVE_JOIN` in enum but
  no `ExclusiveJoinTask` builder; `defaultExclusiveJoinTask` field unreachable
  Fix: add `ExclusiveJoinTask(task_ref_name, join_on, default_exclusive_join_task=None)`
  *[~] Live: EXCLUSIVE_JOIN works fine via raw WorkflowTask*

- [x] **#432 — `ConductorWorkflow` requires live executor at construction time** — cannot
  build workflow definitions offline (unit tests, code gen, offline serialization).
  Fix: make `executor` optional; raise only when `.register()` / `.start_workflow()` called.
  File: `src/conductor/client/workflow/conductor_workflow.py:27`

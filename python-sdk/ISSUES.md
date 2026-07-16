# Python SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`). Each item needs a GitHub
issue filed in `conductor-oss/python-sdk` (or whichever repo tracks SDK bugs).

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## CRITICAL

- [ ] **LAMBDA task: no builder class** (enum value exists in `task_type.py` but
  no `LambdaTask` class)
  Files: `src/conductor/client/workflow/task/task_type.py`
  Fix: add `lambda_task.py` with `LambdaTask(task_ref_name, script, bindings=None)`

## HIGH

- [ ] **WaitTask base class wrong field name**: `__init__(wait_until=...)` sets
  `"wait_until"` key; server reads `"until"`. Silent infinite-wait.
  File: `src/conductor/client/workflow/task/wait_task.py:26`
  Fix: change `"wait_until"` → `"until"` in base class constructor

- [ ] **NOOP task: completely absent** — not in enum, no builder
  Fix: add `NOOP = "NOOP"` to enum; add `noop_task.py` with `NoopTask`

- [ ] **FORK_JOIN_DYNAMIC broken — deprecated field now rejected by server** *(upgraded from FINDING-3; CRITICAL)*:
  `DynamicForkTask.to_workflow_task()` sets `dynamic_fork_join_tasks_param` (deprecated);
  server returns HTTP 400 on registration. `DynamicForkTask` cannot be used at all via SDK.
  Fix: change to `dynamic_fork_tasks_param` + `dynamic_fork_tasks_input_param_name`.
  File: `src/conductor/client/workflow/task/dynamic_fork_task.py:24`

- [ ] **AGENT / GET_AGENT_CARD / CANCEL_AGENT: missing from SDK** — new in server
  3.32.0-rc.9 (conductor-oss/conductor PR #1288), not yet in Python SDK

## MEDIUM

- [ ] **EXCLUSIVE_JOIN: no builder class** — `TaskType.EXCLUSIVE_JOIN` in enum but
  no `ExclusiveJoinTask` builder; `defaultExclusiveJoinTask` field unreachable
  Fix: add `ExclusiveJoinTask(task_ref_name, join_on, default_exclusive_join_task=None)`
  *Live test: server-side EXCLUSIVE_JOIN works fine via raw `WorkflowTask`*

- [ ] **`ConductorWorkflow` requires live executor at construction time** — cannot build
  workflow definitions offline (for unit tests, code gen, or offline serialization).
  Fix: make `executor` optional; raise only when `.register()` / `.start_workflow()` is called.
  File: `src/conductor/client/workflow/conductor_workflow.py:27`

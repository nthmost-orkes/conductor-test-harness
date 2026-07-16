# Go SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`).
Server baseline: Conductor **3.32.0-rc.9**.

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## HIGH

- [x] **#262 — `HttpInput` wrong JSON field names — `connectionTimeOut` and `readTimeOut` silently ignored**
  `sdk/workflow/http.go` — `ConnectionTimeOut` serialized as `"ConnectionTimeOut"` (capital C);
  `ReadTimeout` serialized as `"readTimeout"` (missing capital T in Out).
  Server reads `"connectionTimeOut"` and `"readTimeOut"` — both SDK values silently discarded.
  Server falls back to default 3000ms. Secondary issue: `int16` overflows for values > 32767ms.
  Fix: correct JSON tags + change type to `int`.
  *[~] Live: server accepts correct-cased names; wrong-cased SDK fields confirmed ignored*

- [x] **#263 — `NewForkTask()` auto-join has empty `joinOn` — JOIN completes immediately**
  `sdk/workflow/fork_join.go` — `getJoinTask()` calls `NewJoinTask(name)` with no varargs →
  `joinOn: nil` → serialized as `[]`. Server JOIN executor: empty stream → `allMatch = true` →
  JOIN completes without waiting for any fork branch.
  Workaround: `NewForkTaskWithJoin()` with explicit JoinTask.
  Fix: infer `joinOn` from last task ref in each fork branch.
  *[~] Live: `joinOn=[]` → `join1=COMPLETED` while `w1=IN_PROGRESS` (10s WAIT branch, 3s check)*

- [x] **#264 — `DynamicForkTask.getJoinTask()` ignores stored `join` field**
  `sdk/workflow/fork_join_dynamic.go` — `getJoinTask()` always creates `NewJoinTask(name)`,
  ignoring `task.join` even when set by `NewDynamicForkWithJoinTask()`.
  Every dynamic fork produces a JOIN with empty `joinOn`, completing immediately.
  Fix: check `task.join != nil` and use it.
  *[~] Static — code inspection; same root cause as #263*

## MEDIUM

- [x] **#265 — Missing TaskType constants: NOOP, EXCLUSIVE_JOIN, AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES**
  `sdk/workflow/task.go` — six constants absent. NOOP and EXCLUSIVE_JOIN are core OSS types.
  AGENT/GET_AGENT_CARD/CANCEL_AGENT added in server PR #1288 / 3.32.0-rc.9.
  Fix: add constants + builder structs for NOOP and EXCLUSIVE_JOIN.
  *[~] Live: server accepts NOOP; EXCLUSIVE_JOIN, AGENT confirmed in java+js tests*

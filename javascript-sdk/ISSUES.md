# JavaScript SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`).
Server baseline: Conductor **3.32.0-rc.9**.

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## HIGH

- [x] **#135 — `forkTaskJoin()` generates JOIN with empty `joinOn` — join completes immediately**
  `forkJoin.ts:22` — `generateJoinTask({ name, optional })` never passes `joinOn`, so
  the JOIN task is created with `joinOn: []`. Server JOIN executor: empty `joinOn` →
  `allTasksTerminal = true` immediately → join COMPLETES without waiting for fork branches.
  Fix: infer `joinOn` from last task ref in each fork branch.
  Also: `factory.test.ts:141` expects `joinOn: []` — test should be updated.
  *[~] Live: JOIN reached COMPLETED while branch still IN_PROGRESS (10s WAIT branch test)*

- [x] **#136 — NOOP: not in enum, no builder** — `TaskType.NOOP` absent from enum; no `noopTask()`
  builder. Generated `types.gen.ts` has `'NOOP'` in union literals but not promoted to enum.
  Fix: add enum value + `noopTask(ref, optional?)` builder.
  *[~] Live: server accepts NOOP via raw task*

## MEDIUM

- [x] **#137 — EXCLUSIVE_JOIN: in enum, no builder** — `TaskType.EXCLUSIVE_JOIN` exists but no
  builder function; `defaultExclusiveJoinTask` unreachable.
  Fix: add `exclusiveJoinTask(ref, joinOn, defaultExclusiveJoinTask?, optional?)`.
  *[~] Live: server accepts EXCLUSIVE_JOIN via raw task*

- [ ] **LAMBDA: in enum, no builder** — `TaskType.LAMBDA` exists but no `lambdaTask()`.
  Server-deprecated in favour of INLINE; not filing (would close immediately as wontfix).

- [x] **#138 — `HttpInputParameters.readTimeOut` typed as `string` — server expects integer**
  `src/open-api/types.ts:156` — `readTimeOut?: string` should be `readTimeOut?: number`.
  `connectionTimeOut` is correctly `number`; `readTimeOut` is the odd one out.
  Fix: `readTimeOut?: number`.
  *[~] Live: server accepts both integer and string (Jackson coerces) — TypeScript type still wrong*

- [x] **#139 — `switchTask()` hardcodes `value-param` evaluator** — no way to use JavaScript
  evaluator via builder. `SwitchTaskDef.evaluatorType` supports `"value-param" | "javascript"`
  but the builder locks to `"value-param"`.
  Fix: add optional `evaluatorType` parameter.

- [x] **#140 — TaskType enum missing 4 server values** — AGENT, GET_AGENT_CARD, CANCEL_AGENT,
  PULL_WORKFLOW_MESSAGES absent from enum. All four in server since 3.32.0-rc.9.
  Fix: add to `TaskType` enum; builder classes to follow.
  *[~] Live: server accepts AGENT task type*

# C# SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`).
Server baseline: Conductor **3.32.0-rc.9**.

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## HIGH

- [x] **#158 — `DynamicFork.Join` has empty `joinOn` — JOIN completes immediately**
  `DynamicFork.cs:32` — `new JoinTask(taskReferenceName + "_join")` with no args →
  `JoinOn = []` on the companion join task. Any workflow using `DynamicFork.Join`
  has a join that completes before dynamic branches finish.
  Fix: require explicit joinOn args or document that Join must be populated.
  *[~] Same root cause as javascript-sdk#135 and go-sdk#264 — live-confirmed on Conductor 3.32.0-rc.9*

## MEDIUM

- [x] **#159 — `DynamicFork` sets deprecated `dynamicForkJoinTasksParam` field**
  `DynamicFork.cs:41` — `SetDynamicForkJoinTasksParam()` sets the deprecated JSON field.
  Server falls back to deprecated field (works now) but will remove support eventually.
  Fix: add `SetDynamicForkTasksParam()` and use it instead.

- [x] **#160 — Missing builders: NOOP (no enum), EXCLUSIVE_JOIN, START_WORKFLOW**
  `Conductor/Definition/TaskType/` — no builder for NOOP (also missing from enum),
  EXCLUSIVE_JOIN (enum exists), or START_WORKFLOW (enum exists, StartWorkflow model exists).
  Fix: add NoopTask, ExclusiveJoinTask, StartWorkflowTask builder classes.
  *[~] Server accepts all types — confirmed in parallel Java/JS SDK audits against Conductor 3.32.0-rc.9*

- [x] **#161 — Missing enum values: AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES**
  `WorkflowTask.cs` `WorkflowTaskTypeEnum` ends at WAITFORWEBHOOK=30. All four absent.
  Added in server 3.32.0-rc.9 (AGENT/GET_AGENT_CARD/CANCEL_AGENT via PR #1288).
  Fix: add four enum members + builder classes once agent API stabilizes.
  *[~] Server accepts AGENT — confirmed in JavaScript SDK audit against Conductor 3.32.0-rc.9*

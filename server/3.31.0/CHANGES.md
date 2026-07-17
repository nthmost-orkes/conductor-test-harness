# Changes in Conductor OSS 3.31.0

## New Task Types
None (TaskType enum is identical to 3.30.2)

## Removed / Renamed Task Types
None

## Task Input Parameter Changes
None

## Deprecated Fields / Behaviors
- **`conductor-standalone` Docker image** deprecated. Operators must migrate to
  `conductor-server` or a multi-container setup. This affects server deployment
  docs/scripts that SDK authors maintain for their CI/CD; no change to workflow definitions.

## Behavioral Changes

### SWITCH task: empty matched case no longer falls through to defaultCase (#1159)

**Before 3.31.0:** A SWITCH case key that matched but had an empty task list
(`"someKey": []`) was treated as "no match" and fell through to `defaultCase`.

**As of 3.31.0:** An empty task list is a valid (zero-task) match. The workflow
proceeds without executing `defaultCase` tasks. The fallback to `defaultCase` now
triggers only when **no key matches at all** (i.e., the expression result is not a
key in `decisionCases`).

**SDK impact:** Workflow definitions that relied on the fall-through behavior (empty
case → execute defaultCase) must be updated. Replace empty case lists with explicit
routing to the defaultCase or remove the empty case key.

### HUMAN tasks no longer churn the decider queue (#1171)

HUMAN tasks previously re-queued themselves to the decider repeatedly while waiting
for an external signal, causing CPU load. As of 3.31.0 they wait passively.
No change to SDK workflow definitions — this is a pure server-side efficiency fix
with the same observable behavior for workflow authors.

### DO_WHILE iteration list truncation fixed (#1172)

Long DO_WHILE iteration lists were previously truncated in the server's internal
representation. This affected visibility in the UI and in workflow output, though
task execution was not affected. Fixed in 3.31.0.

### Nested JOIN task reset on sub-workflow restart (#1212)

When a sub-workflow containing JOIN tasks is restarted, the JOIN tasks are now
transitively reset. Previously, stale JOIN task state could prevent the restarted
sub-workflow from completing.

## Breaking Changes
None (the SWITCH change is a fix for incorrect behavior, but see Behavioral Changes above
for the edge case where existing workflows relied on the old incorrect fall-through).

## Notes
- `WAIT_FOR_WEBHOOK` OSS port was merged (#1106) and immediately reverted (#1202).
  `WAIT_FOR_WEBHOOK` is **not present** in Conductor OSS 3.31.0.
- AI HTTP client read timeout defaults to 600s (docs only, no behavior change from #1201).
- `conductor.ai.http.*` properties documented: `connectTimeout`, `readTimeout`,
  `writeTimeout` configurable via `application.properties`.

# JavaScript SDK — Static Analysis

SDK: `conductor-oss/javascript-sdk`
Server baseline: Conductor `3.32.0-rc.9`
Analysis date: 2026-07-16

Methodology: see `../SDK_ANALYSIS_PROCEDURE.md`.

Builder functions live in:
`src/sdk/builders/tasks/`

Type definitions (TaskType enum, task interfaces) live in:
`src/open-api/types.ts`

---

## Coverage Table

| Server TaskType | SDK enum | SDK builder | Status |
|----------------|----------|-------------|--------|
| NOOP | ✗ | ✗ | MISSING |
| SWITCH | ✓ | `switch.ts → switchTask()` | ⚠ (JS evaluator not exposed) |
| DO_WHILE | ✓ | `doWhile.ts → doWhileTask()`, `newLoopTask()` | ✓ |
| FORK_JOIN | ✓ | `forkJoin.ts → forkTask()`, `forkTaskJoin()` | ⚠ CRITICAL (empty joinOn bug) |
| JOIN | ✓ | `join.ts → joinTask()` | ✓ |
| EXCLUSIVE_JOIN | ✓ | ✗ | MISSING BUILDER |
| FORK_JOIN_DYNAMIC | ✓ | `dynamicFork.ts → dynamicForkTask()` | ✓ |
| TERMINATE | ✓ | `terminate.ts → terminateTask()` | ✓ |
| START_WORKFLOW | ✓ | `startWorkflow.ts → startWorkflowTask()` | ✓ |
| SUB_WORKFLOW | ✓ | `subWorkflow.ts → subWorkflowTask()` | ✓ |
| INLINE | ✓ | `inline.ts → inlineTask()` | ✓ |
| LAMBDA | ✓ | ✗ | MISSING BUILDER |
| JSON_JQ_TRANSFORM | ✓ | `jsonJq.ts → jsonJqTask()` | ✓ |
| SET_VARIABLE | ✓ | `setVariable.ts → setVariableTask()` | ✓ |
| HTTP | ✓ | `http.ts → httpTask()` | ⚠ (readTimeOut wrong type) |
| WAIT | ✓ | `wait.ts → waitTaskDuration()`, `waitTaskUntil()` | ✓ |
| HUMAN | ✓ | `humanTask.ts → humanTask()` | ✓ |
| EVENT | ✓ | `event.ts → eventTask()`, `sqsEventTask()`, `conductorEventTask()` | ✓ |
| AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| GET_AGENT_CARD | ✗ | ✗ | MISSING (new in rc.9) |
| CANCEL_AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| PULL_WORKFLOW_MESSAGES | ✗ | ✗ | MISSING (not in SDK) |

### Extra builders (Orkes-specific, not in OSS server)

| SDK builder | TaskType | Notes |
|-------------|----------|-------|
| `httpPoll.ts` | HTTP_POLL | Orkes enterprise |
| `humanTask.ts` | HUMAN | ✓ (OSS) |
| `kafkaPublish.ts` | KAFKA_PUBLISH | Orkes enterprise |
| `getDocument.ts` | GET_DOCUMENT | Orkes enterprise |
| `waitForWebhook.ts` | WAIT_FOR_WEBHOOK | Orkes enterprise |
| `llm/*.ts` | LLM_* | Orkes enterprise |
| `dynamic.ts` | DYNAMIC | ✓ (OSS) |

---

## Findings

### FINDING-1: `forkTaskJoin()` generates JOIN with empty `joinOn` — join completes immediately

**Severity:** HIGH
**Task type:** FORK_JOIN + JOIN
**SDK file:** `src/sdk/builders/tasks/forkJoin.ts:22`
**Server file:** `core/.../mapper/JoinTaskMapper.java:61`

**What the server expects:**
The JOIN task's `joinOn` field lists task reference names to wait for. The mapper reads
`workflowTask.getJoinOn()` at schedule time and puts the list into the task's input data
under key `"joinOn"`. The Join executor reads that list and waits until all listed tasks
are terminal.

If `joinOn` is empty, `joinOn.stream().allMatch(...)` evaluates to `true` (empty-stream
shortcut), and the JOIN immediately transitions to `COMPLETED` without waiting for any
fork branches.

**What the SDK provides:**
```typescript
// forkJoin.ts:22
export const forkTaskJoin = (
  taskReferenceName: string,
  forkTasks: TaskDefTypes[],
  optional?: boolean
): [ForkJoinTaskDef, JoinTaskDef] => [
  forkTask(taskReferenceName, forkTasks),
  generateJoinTask({ name: `${taskReferenceName}_join`, optional }),
];
```

`generateJoinTask` defaults to `joinOn: []`. No `joinOn` is passed — the join task is
created with an empty list. The test suite explicitly expects `joinOn: []`
(`factory.test.ts:141`), confirming this behavior is unintentionally tested-in.

**Impact:**
Any workflow using `forkTaskJoin()` will have a JOIN that completes immediately when
first evaluated. Fork branches run concurrently in the background, but the downstream
workflow does not wait for them — the JOIN is already COMPLETED.

**Fix:**
Infer `joinOn` from the last task reference name in the fork branch:
```typescript
export const forkTaskJoin = (
  taskReferenceName: string,
  forkTasks: TaskDefTypes[],
  optional?: boolean
): [ForkJoinTaskDef, JoinTaskDef] => {
  const joinOn = forkTasks.length > 0
    ? [forkTasks[forkTasks.length - 1].taskReferenceName]
    : [];
  return [
    forkTask(taskReferenceName, forkTasks),
    generateJoinTask({ name: `${taskReferenceName}_join`, joinOn, optional }),
  ];
};
```

---

### FINDING-2: NOOP — not in enum, no builder

**Severity:** HIGH
**Task type:** NOOP
**SDK file:** `src/open-api/types.ts` (TaskType enum, line 40-80)

**What the server expects:**
NOOP is a system task that completes immediately with no `inputParameters`.

**What the SDK provides:**
`TaskType.NOOP` is absent from the enum. No builder function exists. The generated
`types.gen.ts` includes `'NOOP'` in `workflowTaskType` string unions but it is not
promoted to the `TaskType` enum.

**Fix:**
Add to `TaskType` enum:
```typescript
NOOP = "NOOP",
```
Add builder to `src/sdk/builders/tasks/noop.ts`:
```typescript
export const noopTask = (
  taskReferenceName: string,
  optional?: boolean
): WorkflowTask => ({
  name: taskReferenceName,
  taskReferenceName,
  type: TaskType.NOOP,
  inputParameters: {},
  optional,
});
```

---

### FINDING-3: EXCLUSIVE_JOIN — in enum, no builder; `defaultExclusiveJoinTask` unreachable

**Severity:** MEDIUM
**Task type:** EXCLUSIVE_JOIN
**SDK file:** `src/open-api/types.ts:61` (enum value exists; no builder in `builders/tasks/`)

**What the server expects:**
EXCLUSIVE_JOIN uses `joinOn` (which branch tasks to watch) and optionally
`defaultExclusiveJoinTask` (fallback refs if no branch ran).

**What the SDK provides:**
`TaskType.EXCLUSIVE_JOIN` is in the enum but no builder function exists and no
`ExclusiveJoinTaskDef` interface is defined. `defaultExclusiveJoinTask` is unreachable.

**Fix:**
Add builder:
```typescript
export const exclusiveJoinTask = (
  taskReferenceName: string,
  joinOn: string[],
  defaultExclusiveJoinTask?: string[],
  optional?: boolean
): WorkflowTask => ({
  name: taskReferenceName,
  taskReferenceName,
  type: TaskType.EXCLUSIVE_JOIN,
  joinOn,
  defaultExclusiveJoinTask,
  inputParameters: {},
  optional,
});
```

---

### FINDING-4: LAMBDA — in enum, no builder

**Severity:** MEDIUM
**Task type:** LAMBDA
**SDK file:** `src/open-api/types.ts:59` (enum value exists; no builder)

**What the server expects:**
LAMBDA tasks use `inputParameters.scriptExpression` (JS body) and optionally
`lambdaValue`.

**What the SDK provides:**
`TaskType.LAMBDA` is in the enum. No `lambdaTask()` builder function exists.
Note: LAMBDA is server-deprecated in favour of INLINE; the `inlineTask()` builder is
the preferred path. Flag as MEDIUM accordingly.

**Fix:**
Add builder for completeness:
```typescript
export const lambdaTask = (
  taskReferenceName: string,
  scriptExpression: string,
  optional?: boolean
): WorkflowTask => ({
  name: taskReferenceName,
  taskReferenceName,
  type: TaskType.LAMBDA,
  inputParameters: { scriptExpression },
  optional,
});
```

---

### FINDING-5: `HttpInputParameters.readTimeOut` typed as `string` — server expects integer

**Severity:** MEDIUM
**SDK file:** `src/open-api/types.ts:156`
**Server file:** `http-task/.../HttpTask.java:275` — `private Integer readTimeOut = 3000`

**What the server expects:**
`http_request.readTimeOut` is a millisecond integer (default 3000). Server field type:
`Integer`.

**What the SDK provides:**
```typescript
// types.ts:155-156
connectionTimeOut?: number;   // ✓ correct — Integer maps to number
readTimeOut?: string;         // ✗ wrong — should be number
```

`connectionTimeOut` is correctly typed as `number`. `readTimeOut` is incorrectly typed
as `string`. Passing `readTimeOut: 5000` (number) is a TypeScript type error; passing
`readTimeOut: "5000"` (string) may or may not be coerced by the server's Jackson
deserialization (Jackson can coerce strings to ints with `@JsonProperty`).

**Fix:**
```typescript
readTimeOut?: number;
```

---

### FINDING-6: `switchTask()` hardcodes `value-param` evaluator; JavaScript evaluator unreachable

**Severity:** MEDIUM
**SDK file:** `src/sdk/builders/tasks/switch.ts`
**Server:** SWITCH supports `"value-param"` and `"javascript"` evaluator types

**What the server expects:**
`SwitchTaskDef.evaluatorType` is `"value-param" | "javascript"`. The JS evaluator
allows arbitrary JS expressions instead of plain value lookups.

**What the SDK provides:**
```typescript
export const switchTask = (
  taskReferenceName: string,
  expression: string,          // treated as switchCaseValue key, not JS expression
  ...
): SwitchTaskDef => ({
  evaluatorType: "value-param",  // hardcoded — no parameter to change this
  inputParameters: { switchCaseValue: expression },
  expression: "switchCaseValue",
  ...
});
```

Users who need a JavaScript evaluator switch must construct `SwitchTaskDef` manually.

**Fix:**
Add optional `evaluatorType` parameter:
```typescript
export const switchTask = (
  taskReferenceName: string,
  expression: string,
  decisionCases: Record<string, TaskDefTypes[]> = {},
  defaultCase: TaskDefTypes[] = [],
  evaluatorType: "value-param" | "javascript" = "value-param",
  optional?: boolean
): SwitchTaskDef => ({
  ...
  evaluatorType,
  inputParameters: evaluatorType === "value-param"
    ? { switchCaseValue: expression }
    : {},
  expression: evaluatorType === "value-param" ? "switchCaseValue" : expression,
  ...
});
```

---

### FINDING-7: TaskType enum missing AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES

**Severity:** MEDIUM (new feature gap)
**SDK file:** `src/open-api/types.ts:40-80`
**Server file:** server `TaskType.java` (added in PR #1288 / 3.32.0-rc.9)

**What the server has:**
```java
PULL_WORKFLOW_MESSAGES,
AGENT,
GET_AGENT_CARD,
CANCEL_AGENT;
```

**What the SDK has:**
The `TaskType` enum ends at `LIST_MCP_TOOLS`. All four values are absent.

**Fix:**
```typescript
PULL_WORKFLOW_MESSAGES = "PULL_WORKFLOW_MESSAGES",
AGENT = "AGENT",
GET_AGENT_CARD = "GET_AGENT_CARD",
CANCEL_AGENT = "CANCEL_AGENT",
```

Builder functions should follow once the agent task API is stable.

---

## Notes / Non-Findings

- **`dynamicForkTask()` uses correct fields** — Sets `dynamicForkTasksParam` and
  `dynamicForkTasksInputParamName` (non-deprecated). Python SDK had the deprecated-field
  bug; JS SDK does not.

- **`waitTaskDuration()` / `waitTaskUntil()`** — Both use correct field names (`duration`,
  `until`). Python SDK base class had the wrong `wait_until` key; JS SDK is correct.

- **`forkTask()` single-branch limitation** — `forkTask(ref, [task1, task2])` creates
  `forkTasks: [[task1, task2]]` (one branch). Multi-branch forks require manual construction.
  This is a known usability gap already tracked as
  [conductor-oss/javascript-sdk#94](https://github.com/conductor-oss/javascript-sdk/issues/94).
  Not filing a duplicate.

- **DYNAMIC task** — `dynamicTask()` builder exists and is correct. DYNAMIC is an OSS task type.

- **HUMAN task** — `humanTask()` builder is well-implemented with rich options for form
  templates, assignee, and completion strategy. No issue.

---

## Summary by Severity

| Severity | Count | Findings |
|----------|-------|---------|
| HIGH | 2 | FINDING-1: forkTaskJoin empty joinOn; FINDING-2: NOOP missing |
| MEDIUM | 5 | FINDING-3: EXCLUSIVE_JOIN no builder; FINDING-4: LAMBDA no builder; FINDING-5: readTimeOut wrong type; FINDING-6: switchTask no JS evaluator; FINDING-7: 4 missing enum values |

---

## Live Test Results

Run date: 2026-07-16, server: `http://loki.local:8080` (Conductor 3.32.0-rc.9)
Script: `javascript-sdk/live_test.sh`

| Finding | Result | Note |
|---------|--------|------|
| FINDING-1: forkTaskJoin empty joinOn | 🐛 CONFIRMED | `joinOn=[]` JOIN reached COMPLETED while branch still IN_PROGRESS; correct `joinOn=[branch]` waited properly |
| FINDING-2: NOOP no enum/builder | 🐛 CONFIRMED | Server accepts NOOP and completes — SDK gap only |
| FINDING-3: EXCLUSIVE_JOIN no builder | 🐛 CONFIRMED | Server accepts EXCLUSIVE_JOIN in SWITCH workflow — SDK gap only |
| FINDING-4: LAMBDA no builder | (not live-tested; server-deprecated, static sufficient) | |
| FINDING-5: readTimeOut wrong type | 🐛 CONFIRMED (partial) | Server accepts both integer and string (coerces) — type in SDK is still wrong |
| FINDING-6: switchTask no JS evaluator | (not live-tested; static sufficient) | |
| FINDING-7: AGENT missing enum | 🐛 CONFIRMED | Server accepts AGENT task type — SDK enum missing |

**Key live evidence for FINDING-1:**
```
After 2 seconds (10s WAIT branch):
  joinOn=[]       → wf=RUNNING  join1=COMPLETED  wait_branch=IN_PROGRESS  ← BUG
  joinOn=[wait]   → wf=RUNNING  join1=IN_PROGRESS  wait_branch=IN_PROGRESS  ← CORRECT
```

**Summary: 5 confirmed · 2 static-only (LAMBDA deprecated; switchTask API gap)**

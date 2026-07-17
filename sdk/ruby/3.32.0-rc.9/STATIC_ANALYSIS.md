# Ruby SDK — Static Analysis

SDK: `conductor-oss/ruby-sdk`
Server baseline: Conductor `3.32.0-rc.9`
Analysis date: 2026-07-16

Methodology: see `../SDK_ANALYSIS_PROCEDURE.md`.

Task type constants: `lib/conductor/workflow/task_type.rb`
DSL builder methods: `lib/conductor/workflow/dsl/workflow_builder.rb`
Task serialization: `lib/conductor/workflow/dsl/task_ref.rb`

---

## Coverage Table

| Server TaskType | SDK constant | SDK DSL method | Status |
|----------------|-------------|---------------|--------|
| NOOP | ✗ | ✗ | MISSING |
| SWITCH | ✓ | `decide()` | ⚠ (JS evaluator unreachable) |
| DO_WHILE | ✓ | `loop_times()`, `loop_while()`, `loop_over()` | ✓ |
| FORK_JOIN | ✓ | `parallel {}` block | ✓ (correct joinOn inference) |
| JOIN | ✓ | (auto by `parallel`) | ✓ |
| EXCLUSIVE_JOIN | ✓ | ✗ | MISSING DSL METHOD |
| FORK_JOIN_DYNAMIC | ✓ | `dynamic_fork()` | ⚠ (deprecated JSON field) |
| TERMINATE | ✓ | `terminate()` | ✓ |
| START_WORKFLOW | ✓ | `start_workflow()` | ✓ |
| SUB_WORKFLOW | ✓ | `sub_workflow()` | ✓ |
| INLINE | ✓ | `javascript()` | ✓ |
| LAMBDA | ✓ | ✗ | MISSING DSL (server-deprecated) |
| JSON_JQ_TRANSFORM | ✓ | `jq()` | ✓ |
| SET_VARIABLE | ✓ | `set()` | ✓ |
| HTTP | ✓ | `http()` | ✓ |
| WAIT | ✓ | `wait()` | ✓ (`"N seconds"` format valid) |
| HUMAN | ✓ | `human()` | ✓ |
| EVENT | ✓ | `event()` | ✓ |
| AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| GET_AGENT_CARD | ✗ | ✗ | MISSING (new in rc.9) |
| CANCEL_AGENT | ✗ | ✗ | MISSING (new in rc.9) |
| PULL_WORKFLOW_MESSAGES | ✗ | ✗ | MISSING |

---

## Findings

### FINDING-1: `dynamic_fork` sets deprecated `dynamicForkJoinTasksParam` field

**Severity:** MEDIUM
**Task type:** FORK_JOIN_DYNAMIC
**SDK file:** `lib/conductor/workflow/dsl/task_ref.rb:172`

**What the SDK provides:**
```ruby
def apply_dynamic_fork_fields(wf_task)
  wf_task.dynamic_fork_join_tasks_param = @options[:dynamic_fork_tasks_param]  # ← deprecated field
  wf_task.dynamic_fork_tasks_input_param_name = @options[:dynamic_fork_tasks_input_param]
end
```

The `WorkflowTask` model (`lib/conductor/http/models/workflow_task.rb`) has:
- `dynamic_fork_join_tasks_param` → JSON `"dynamicForkJoinTasksParam"` (deprecated)
- `dynamic_fork_tasks_param` → JSON `"dynamicForkTasksParam"` (current)

The DSL method in `workflow_builder.rb:312` passes `dynamic_fork_tasks_param:` in options, but
`apply_dynamic_fork_fields` assigns it to the deprecated field instead of the current one.

**Server behavior:** `ForkJoinDynamicTaskMapper.java:156` reads `getDynamicForkTasksParam()` first,
then falls back to `getDynamicForkJoinTasksParam()`. Currently works via fallback, but the
deprecated path may be removed in a future server version.

**Fix:**
```ruby
def apply_dynamic_fork_fields(wf_task)
  wf_task.dynamic_fork_tasks_param = @options[:dynamic_fork_tasks_param]        # non-deprecated
  wf_task.dynamic_fork_tasks_input_param_name = @options[:dynamic_fork_tasks_input_param]
end
```

---

### FINDING-2: `decide` (SWITCH) hardcodes `value-param` evaluator — JavaScript evaluator unreachable

**Severity:** MEDIUM
**Task type:** SWITCH
**SDK file:** `lib/conductor/workflow/dsl/task_ref.rb:111`

**What the SDK provides:**
```ruby
def apply_switch_fields(wf_task)
  wf_task.evaluator_type = 'value-param'  # hardcoded — cannot use 'javascript'
  wf_task.expression = @options[:expression]
  ...
end
```

The server supports `"value-param"` and `"javascript"` evaluator types. The `decide` DSL
and `add_switch_task` pass no `evaluator_type` option; `apply_switch_fields` hardcodes
`'value-param'`. Users who need a JavaScript switch expression must construct `WorkflowTask`
manually.

**Fix:**
Pass `evaluator_type` through from `decide()`:
```ruby
# workflow_builder.rb — add optional evaluator_type param to decide()
def decide(expression, evaluator_type: 'value-param', &block)
  builder = SwitchBuilder.new(resolve_value(expression), self)
  builder.instance_eval(&block)
  add_switch_task(builder, evaluator_type: evaluator_type)
end

# task_ref.rb — read evaluator_type from options
def apply_switch_fields(wf_task)
  wf_task.evaluator_type = @options[:evaluator_type] || 'value-param'
  ...
end
```

---

### FINDING-3: Missing NOOP — no constant, no DSL method

**Severity:** MEDIUM
**SDK files:** `lib/conductor/workflow/task_type.rb` (constant), `lib/conductor/workflow/dsl/workflow_builder.rb` (DSL method)

**What the server expects:**
`NOOP` is a system task that completes immediately with no inputs.

**What the SDK provides:**
`NOOP` is absent from `TaskType` constants. No `noop()` DSL method exists.

**Fix:**
Add to `task_type.rb`:
```ruby
NOOP = 'NOOP'
```
Add to `workflow_builder.rb`:
```ruby
def noop(task_name = 'noop', **options)
  add_task(task_name, TaskType::NOOP, {}, options)
end
```

---

### FINDING-4: Missing `exclusive_join` DSL method

**Severity:** MEDIUM
**Task type:** EXCLUSIVE_JOIN
**SDK file:** `lib/conductor/workflow/dsl/workflow_builder.rb`

**What the SDK provides:**
The `EXCLUSIVE_JOIN = 'EXCLUSIVE_JOIN'` constant exists in `task_type.rb`. However, there is
no `exclusive_join()` DSL method in `workflow_builder.rb`. `defaultExclusiveJoinTask` is
unreachable via the builder.

**Fix:**
```ruby
def exclusive_join(task_name, join_on:, default_join_on: [], **options)
  add_task(
    task_name,
    TaskType::EXCLUSIVE_JOIN,
    {},
    { join_on: join_on, default_exclusive_join_task: default_join_on }.merge(options)
  )
end
```

---

### FINDING-5: Missing TaskType constants — AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES

**Severity:** MEDIUM (new feature gap)
**SDK file:** `lib/conductor/workflow/task_type.rb`

**What the server has** (added in server PR #1288 / 3.32.0-rc.9):
- `AGENT`, `GET_AGENT_CARD`, `CANCEL_AGENT`, `PULL_WORKFLOW_MESSAGES`

**What the SDK has:**
`task_type.rb` ends at `CALL_MCP_TOOL` — all four values absent.

**Fix:**
```ruby
AGENT = 'AGENT'
GET_AGENT_CARD = 'GET_AGENT_CARD'
CANCEL_AGENT = 'CANCEL_AGENT'
PULL_WORKFLOW_MESSAGES = 'PULL_WORKFLOW_MESSAGES'
```
DSL methods should follow once the agent task API stabilizes.

---

## Notes / Non-Findings

- **`parallel` block joinOn** — `workflow_builder.rb:635` correctly infers `joinOn` from the
  **last** task in each branch: `branches.map { |branch| branch.last.ref_name }`. ✓
  This is the bug that hit JavaScript (#135), Go (#263), and C# (#158) SDKs. Ruby gets it right.

- **`wait` duration format** — `workflow_builder.rb:121` uses `"#{seconds} seconds"` format
  (e.g. `"5 seconds"`). The server's `DateTimeUtils.parseDuration` regex accepts `seconds?`,
  so `"5 seconds"` is valid. ✓

- **`dynamic_fork` no auto-join** — `workflow_builder.rb:306-316` creates the `FORK_JOIN_DYNAMIC`
  task but not a companion JOIN. For dynamic forks, the branch tasks are determined at runtime —
  no static `joinOn` can be inferred. Users must add a `join` call manually. This is by design.

- **HTTP task no `connectionTimeOut`/`readTimeOut` exposure** — `http()` builder sets only
  `uri` and `method`. Users cannot configure timeouts via the DSL. This is a usability gap
  (LOW severity); users can pass them manually via raw `WorkflowTask`. Not filing.

- **`javascript()` evaluator** — `task_ref.rb:103` sets `evaluator_type` from options or
  defaults to `'javascript'`. `workflow_builder.rb:184` passes `evaluator_type: 'javascript'`.
  INLINE task works correctly. ✓

---

## Summary by Severity

| Severity | Count | Findings |
|----------|-------|---------|
| HIGH | 0 | — |
| MEDIUM | 5 | FINDING-1: deprecated dynamicForkJoinTasksParam; FINDING-2: SWITCH JS evaluator; FINDING-3: NOOP missing; FINDING-4: EXCLUSIVE_JOIN no DSL; FINDING-5: 4 missing agent constants |

---

## Live Test Status

No live test run — no Ruby runtime available in this environment.

- FINDING-1 (deprecated field): server backward-compat confirmed by reading
  `ForkJoinDynamicTaskMapper.java:156`.
- FINDING-2 (switch evaluator): static code analysis sufficient.
- FINDING-3/4/5 (missing constants/DSL): server acceptance confirmed for same types in Java,
  JavaScript, and Go SDK audits against Conductor 3.32.0-rc.9.

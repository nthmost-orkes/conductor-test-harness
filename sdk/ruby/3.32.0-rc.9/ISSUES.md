# Ruby SDK — Issues Punch List

Derived from static analysis (`STATIC_ANALYSIS.md`).
Server baseline: Conductor OSS **3.32.0-rc.9**.

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## MEDIUM

- [x] **#23 — `dynamic_fork` sets deprecated `dynamicForkJoinTasksParam` field**
  `task_ref.rb:172` — `wf_task.dynamic_fork_join_tasks_param = @options[:dynamic_fork_tasks_param]`
  Sets deprecated JSON field instead of current `dynamicForkTasksParam`.
  Server falls back to deprecated (works now); may break in future server version.
  Fix: `wf_task.dynamic_fork_tasks_param = @options[:dynamic_fork_tasks_param]`.

- [x] **#24 — `decide()` DSL hardcodes `value-param` evaluator — JavaScript evaluator unreachable**
  `task_ref.rb:111` — `wf_task.evaluator_type = 'value-param'` hardcoded.
  No way to use `'javascript'` evaluator through the builder.
  Fix: thread `evaluator_type` option through `decide()` → `add_switch_task()` → `apply_switch_fields()`.

- [x] **#25 — Missing TaskType constants and DSL methods: NOOP, EXCLUSIVE_JOIN, AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES**
  `task_type.rb` — NOOP, AGENT, GET_AGENT_CARD, CANCEL_AGENT, PULL_WORKFLOW_MESSAGES absent.
  `workflow_builder.rb` — no `noop()` method; EXCLUSIVE_JOIN constant exists but no `exclusive_join()` method.
  Fix: add constants + `noop()` + `exclusive_join()` DSL methods.
  *[~] Server accepts all types — confirmed in Java/JS/Go SDK audits against Conductor OSS 3.32.0-rc.9*

---

## Highlights

The Ruby SDK is the **only SDK** that correctly handles `parallel` block `joinOn` inference —
`workflow_builder.rb:635` uses `branches.map { |branch| branch.last.ref_name }`.
The JavaScript, Go, and C# SDKs all had the empty-joinOn bug; Ruby avoids it. ✓

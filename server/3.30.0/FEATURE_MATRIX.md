# Conductor OSS 3.30.0 Feature Matrix

Generated from source inspection and version-specific known issue analysis.
This is the oldest version in the capabilities catalog.

## Legend

| Icon | Meaning |
|------|---------|
| ✅ | Supported — works correctly, tested |
| ⚠️ | Partial — works in basic cases, gaps exist (untested scenarios or incomplete module) |
| 🐛 | Buggy — known defect affects this feature; workaround available |
| ❌ | Not supported — absent from this version |
| 🔲 | Untested — no evidence for or against; source code does not prevent it |

---

## System Task Types

### Structural / Control-Flow Tasks

| Task Type | Status | Notes |
|-----------|--------|-------|
| FORK_JOIN | ✅ | Static fork; must be followed by JOIN |
| FORK_JOIN_DYNAMIC | ✅ | Runtime-generated branches from list/map expression |
| JOIN | ✅ | Waits for all (or configured subset of) branches |
| EXCLUSIVE_JOIN | ✅ | Completes on first branch completion; for SWITCH branches only — see #1309 when used after FORK_JOIN |
| SWITCH | ✅ | javascript or value-param evaluator; replacement for deprecated DECISION. Note: empty matched case incorrectly falls through to defaultCase in this version (fixed in 3.31.0) |
| DECISION | ⚠️ | Deprecated alias for SWITCH; still functional, use SWITCH instead |
| DO_WHILE | ✅ | Iterative loop with loop condition evaluator. Known issue: iteration list may be truncated in task output (fixed in 3.31.0) |
| SUB_WORKFLOW | ✅ | Executes a named workflow as a task; supports inline definition. Known issue: nested JOIN not transitively reset after restart (fixed in 3.31.0) |
| START_WORKFLOW | ✅ | Fire-and-forget workflow launch |

### Worker / Processing Tasks

| Task Type | Status | Notes |
|-----------|--------|-------|
| SIMPLE | ✅ | Poll-driven worker task; fundamental unit of user work |
| DYNAMIC | ✅ | Resolves task type at runtime from input |
| USER_DEFINED | ✅ | Fallback for unrecognized task type strings |
| HTTP | ✅ | Outbound HTTP/HTTPS requests (GET, POST, PUT, DELETE, HEAD, PATCH) |
| LAMBDA | ✅ | Synchronous JS eval via GraalVM; prefer INLINE. Sandbox not yet hardened (hardened in 3.30.2): load(), print(), console, file I/O, env vars accessible |
| INLINE | ✅ | Synchronous JS or Python eval via GraalVM. Sandbox not yet hardened (hardened in 3.30.2): load(), print(), console, file I/O, env vars accessible |
| JSON_JQ_TRANSFORM | ✅ | jq expression transforms on JSON payload |
| SET_VARIABLE | ✅ | Writes workflow-scoped variables (`${workflow.variables.X}`) |
| KAFKA_PUBLISH | ✅ | Publishes to Apache Kafka topic |

### Control Tasks

| Task Type | Status | Notes |
|-----------|--------|-------|
| WAIT | ✅ | Pauses until external signal or ISO-8601 duration/timestamp elapses |
| HUMAN | ⚠️ | Functional stub: transitions to IN_PROGRESS, awaits external completion. Full assignment UI/forms are Orkes Enterprise. Known issue: repeatedly re-queues to decider while waiting (fixed in 3.31.0). |
| TERMINATE | ✅ | Immediately terminates workflow with COMPLETED / FAILED / TERMINATED |
| NOOP | ✅ | No-operation; transitions immediately to COMPLETED |
| EVENT | ✅ | Publishes message to event sink (conductor, sqs, kafka, amqp, nats) |
| PULL_WORKFLOW_MESSAGES | ✅ | Polls workflow message queue for inter-workflow messaging |

### AI / LLM Tasks

| Task Type | Status | Notes |
|-----------|--------|-------|
| LLM_TEXT_COMPLETE | ✅ | Text completion via configured LLM provider |
| LLM_CHAT_COMPLETE | ✅ | Multi-turn chat completion; supports tool calling |
| LLM_INDEX_TEXT | ✅ | Index text into vector database |
| LLM_SEARCH_INDEX | ✅ | Semantic search against vector database |
| LLM_GENERATE_EMBEDDINGS | ✅ | Generate vector embeddings |
| LLM_STORE_EMBEDDINGS | ✅ | Store pre-generated embeddings |
| LLM_GET_EMBEDDINGS | ✅ | Retrieve stored embeddings |
| LIST_MCP_TOOLS | ✅ | List tools from MCP server |
| CALL_MCP_TOOL | ✅ | Invoke tool on MCP server |
| AGENT | ❌ | Not available in 3.30.0; added in 3.32.0-rc.9 |
| GET_AGENT_CARD | ❌ | Not available in 3.30.0; added in 3.32.0-rc.9 |
| CANCEL_AGENT | ❌ | Not available in 3.30.0; added in 3.32.0-rc.9 |

---

## Task Combination Matrix

Rows are the **outer** (containing) task; columns are the **inner** (nested) task type.

### DO_WHILE as Outer Container

| Inner Task | Status | Notes |
|-----------|--------|-------|
| DO_WHILE | 🐛 | Two open bugs: #1307 (loopCondition TypeError), #1308 (task name collision). Inner loop limited to 1 safe outer iteration. Iteration list truncation also applies. |
| FORK_JOIN | ✅ | Tested; iteration suffixes applied correctly via TaskUtils.appendIteration(). Iteration list truncation bug present. |
| FORK_JOIN_DYNAMIC | ✅ | Confirmed working in kitchen-sink battery. Iteration list truncation bug present. |
| SUB_WORKFLOW | ✅ | Explicitly e2e tested including rerun/retry scenarios. Iteration list truncation bug present. |
| SWITCH | ✅ | Timing bug #895 fixed prior to 3.30.0 (commit 69faed274). SWITCH empty-case fall-through bug present in this version (fixed in 3.31.0). Iteration list truncation bug present. |
| WAIT | ✅ | Compatible with DO_WHILE async iteration logic. Iteration list truncation bug present. |
| HTTP | ✅ | Confirmed working across multiple iterations. Iteration list truncation bug present. |
| INLINE | ✅ | Regression-tested; premature iteration bug fixed. Sandbox not yet hardened. Iteration list truncation bug present. |
| TERMINATE | ✅ | Terminates workflow (not just loop); by design. Iteration list truncation bug present. |
| HUMAN | 🔲 | No code prevents it; no e2e tests confirm multi-iteration behavior. Note: HUMAN tasks churn the decider queue while waiting in this version. |
| LAMBDA | ✅ | Same engine as INLINE; sandbox not yet hardened. |
| NOOP | ✅ | No restrictions |
| EVENT | ✅ | No restrictions |
| SET_VARIABLE | ✅ | No restrictions |
| JSON_JQ_TRANSFORM | ✅ | No restrictions |

### FORK_JOIN as Outer Container

| Inner Task | Status | Notes |
|-----------|--------|-------|
| DO_WHILE | ✅ | Tested via do_while_multiple_integration_test.json |
| FORK_JOIN | ✅ | Nested fork confirmed e2e (ForkJoinSyncModeIntegrationTest.testSync_nestedForkJoin) |
| SUB_WORKFLOW | ✅ | Documented; WorkflowExecutorOps handles SUB_WORKFLOW completion in FORK_JOIN context |
| SWITCH | ✅ | JOIN includes SWITCH-aware completion logic (commit 02aa4a5ca). Note: SWITCH empty-case fall-through bug present in this version (fixed in 3.31.0). |
| EXCLUSIVE_JOIN | 🐛 | Fails at runtime: ForkJoinTaskMapper requires JOIN, not EXCLUSIVE_JOIN, as successor. See #1309. |
| WAIT | ✅ | No restrictions |
| HTTP | ✅ | No restrictions |
| TERMINATE | ✅ | No restrictions |
| HUMAN | ✅ | No restrictions. Note: HUMAN tasks churn the decider queue while waiting in this version. |

### SWITCH as Outer Container

| Inner Task | Status | Notes |
|-----------|--------|-------|
| DO_WHILE | ✅ | Well-tested; same timing fix applies |
| FORK_JOIN | ⚠️ | Test definition exists (switch_and_fork_join_integration_test.json); e2e execution unconfirmed |
| EXCLUSIVE_JOIN | ✅ | Canonical use case for EXCLUSIVE_JOIN; explicitly designed for SWITCH branches |
| TERMINATE | ✅ | Common pattern; payment_transfer example demonstrates |
| SUB_WORKFLOW | ✅ | No restrictions |
| WAIT | ✅ | No restrictions |
| HTTP | ✅ | No restrictions |

### SUB_WORKFLOW as Outer Container

| Inner Task | Status | Notes |
|-----------|--------|-------|
| DO_WHILE | ✅ | e2e tested including rerun scenarios |
| FORK_JOIN | ✅ | e2e tested; any task type supported inside sub-workflow. Known issue: nested JOIN not transitively reset after sub-workflow restart (fixed in 3.31.0). |
| SWITCH | ✅ | No restrictions |
| All others | ✅ | Sub-workflow executes as a complete workflow; all task types available |

---

## Persistence Backends

### Execution DAO

| Backend | Status | Notes |
|---------|--------|-------|
| SQLite | ✅ | Default for development. `conductor.db.type=sqlite` |
| MySQL | ✅ | Production-grade. `conductor.db.type=mysql` |
| PostgreSQL | ✅ | Production-grade. `conductor.db.type=postgres` |
| Cassandra | ✅ | Distributed NoSQL. `conductor.db.type=cassandra` |
| Redis | ✅ | In-memory with optional persistence. `conductor.db.type=redis` |
| In-Memory | ✅ | Testing only; no persistence across restarts |

### Index / Search DAO

| Backend | Status | Notes |
|---------|--------|-------|
| Elasticsearch 8 | ✅ | Recommended search backend (es8-persistence) |
| Elasticsearch 7 | ✅ | Supported (es7-persistence) |
| OpenSearch 2 | ✅ | Shaded dependency (os-persistence-v2) |
| OpenSearch 3 | ✅ | Shaded dependency (os-persistence-v3) |
| OpenSearch (generic) | ⚠️ | Deprecated shim only; use v2 or v3 |
| Elasticsearch 6 | ⚠️ | Deprecated; ES 6.x is EOL upstream |
| SQLite index | ✅ | Development use. `conductor.indexing.type=sqlite` |
| None (disabled) | ✅ | Workflow search unavailable. `conductor.indexing.type=none` |

### Scheduler DAO

| Backend | Status | Notes |
|---------|--------|-------|
| MySQL | ✅ | `scheduler/mysql-persistence`; V1+V2 Flyway migrations present |
| PostgreSQL | ✅ | `scheduler/postgres-persistence`; V1+V2 Flyway migrations present |
| SQLite | ✅ | `scheduler/sqlite-persistence`; V1+V2 Flyway migrations present |

---

## Event Sinks

| Sink | Status | Module | Queue Prefix | Notes |
|------|--------|--------|-------------|-------|
| Conductor Internal | ✅ | core | `conductor:` | Default; backed by QueueDAO. Disable with `conductor.event-queues.default.enabled=false` |
| AWS SQS | ✅ | awssqs-event-queue | `sqs:` | SQSEventQueueProvider |
| Apache Kafka | ✅ | kafka-event-queue | `kafka:` | KafkaEventQueueProvider |
| AMQP (RabbitMQ) | ✅ | amqp | `amqp:` | AMQPEventQueueProvider |
| NATS JetStream | ✅ | nats | `jstream:` | JetStreamEventQueueProvider |
| NATS (core) | ✅ | nats | `nats:` | NATSEventQueueProvider |
| NATS Streaming | ✅ | nats-streaming | `sqs_stan:` | NATSStreamEventQueueProvider. Note: NATS Streaming is EOL upstream. |

---

## External Payload Storage

| Provider | Status | Module | Notes |
|----------|--------|--------|-------|
| AWS S3 | ✅ | awss3-storage | Large workflow inputs/outputs stored in S3 |
| Azure Blob | ✅ | azureblob-storage | Azure Blob Storage |
| Google Cloud Storage | ✅ | gcs-storage | GCS |
| Local Filesystem | ✅ | local-file-storage | Development / single-node |
| PostgreSQL (external) | ✅ | postgres-external-storage | Separate from main postgres execution DAO |

---

## Server Capabilities

| Capability | Status | Since | Notes |
|-----------|--------|-------|-------|
| Workflow Scheduler | ✅ | pre-3.30.0 | Cron-expression scheduler. `conductor.scheduler.enabled=true` (default). Backends: SQLite, MySQL, PostgreSQL (all fully implemented). |
| HUMAN Task (basic) | ⚠️ | pre-3.30.0 | Task goes IN_PROGRESS; external completion via task API. Known issue: repeatedly re-queues to decider while waiting (fixed in 3.31.0). |
| HUMAN Task Assignments / Forms | ❌ | — | Assignment management and form templates are Orkes Enterprise only |
| Wait-for-Webhook | ❌ | — | webhooks-oss module stub only; no runtime implementation in this version |
| HTTP Poll Task | ❌ | — | Not present in TaskType enum for this version |
| Secrets Interpolation | ❌ | — | `${workflow.secrets.X}` not available in this version |
| Env Interpolation | ❌ | — | `${workflow.env.X}` not available in this version |
| A2A Agent Protocol | ❌ | — | AGENT, GET_AGENT_CARD, CANCEL_AGENT task types not present; added in 3.32.0-rc.9 |
| Worker Poll Visibility | ❌ | — | Not available; added in 3.32.0-rc.9 (PR #1287) |
| LLM / AI Tasks | ✅ | pre-3.30.0 | 13 LLM providers (see table below). Enabled via AIIntegrationEnabledCondition |
| MCP Integration | ✅ | pre-3.30.0 | LIST_MCP_TOOLS, CALL_MCP_TOOL tasks; MCPService |
| GraalVM JS Sandbox | ⚠️ | 3.30.2 | Sandbox NOT yet hardened in this version. load(), print(), console, file I/O, env vars, host class loading all accessible in JS expressions. Hardened in 3.30.2. |
| Python Evaluator | ✅ | pre-3.30.0 | Via GraalVM polyglot python runtime (PythonEvaluator.java) |
| Event Handlers | ✅ | pre-3.30.0 | DefaultEventProcessor + ActionProcessor |
| Workflow Variables | ✅ | pre-3.30.0 | SET_VARIABLE task + `${workflow.variables.X}` expressions |
| Input/Output Expressions | ✅ | pre-3.30.0 | `${workflow.input.X}`, `${task_ref.output.X}`, etc. |
| Workflow Metrics (Prometheus) | ✅ | pre-3.30.0 | Prometheus endpoint |

### LLM Providers

| Provider Name (in config) | Status | Notes |
|--------------------------|--------|-------|
| `openai` | ✅ | Full support; image generation |
| `anthropic` | ✅ | `supportsAssistantPrefill=false` — trailing assistant messages suppressed to avoid 400 errors |
| `azure_openai` | ✅ | Azure OpenAI endpoint |
| `vertex_ai` | ✅ | Google Vertex AI (Gemini) |
| `bedrock` | ✅ | AWS Bedrock |
| `cohere` | ✅ | Cohere AI |
| `mistral` | ✅ | Mistral AI |
| `ollama` | ✅ | Local Ollama models |
| `huggingface` | ✅ | HuggingFace Inference API |
| `perplexity` | ✅ | Perplexity AI |
| `Grok` | ✅ | xAI Grok |
| `stabilityai` | ✅ | Stability AI (image generation) |
| `litellm` | ✅ | LiteLLM proxy (routes to any provider) |

---

## Known Bugs (3.30.0)

| Issue | Area | Severity | Status | Workaround |
|-------|------|----------|--------|-----------|
| [#1307](https://github.com/conductor-oss/conductor/issues/1307) | Nested DO_WHILE: loopCondition TypeError | High | Open (partial fix in source) | Limit outer loop to 1 iteration |
| [#1308](https://github.com/conductor-oss/conductor/issues/1308) | Nested DO_WHILE: task name collision | High | Open | Limit outer loop to 1 iteration |
| [#1309](https://github.com/conductor-oss/conductor/issues/1309) | FORK_JOIN + EXCLUSIVE_JOIN: runtime failure | Medium | Open | Use JOIN after FORK_JOIN; restructure |
| [#1310](https://github.com/conductor-oss/conductor/issues/1310) | WAIT task: misleading error for some ISO-8601 formats | Low | Open | Use fully-qualified durations (e.g. PT10S) |
| [#1311](https://github.com/conductor-oss/conductor/issues/1311) | SWITCH JS evaluator: validates with no bindings | Low | Open | Ensure all expression variables are bound in input |
| switch-empty-case-fallthrough | SWITCH: empty matched case falls through to defaultCase | Medium | Open in 3.30.0 (fixed in 3.31.0, PR #1159) | Ensure all SWITCH cases have at least one task |
| human-decider-churn | HUMAN task repeatedly re-queues to decider while waiting | Medium | Open in 3.30.0 (fixed in 3.31.0) | Minimize concurrent long-running HUMAN tasks |
| do-while-iteration-truncation | DO_WHILE iteration list truncated in task output | Medium | Open in 3.30.0 (fixed in 3.31.0, PR #1172) | Read results from individual task outputs instead |
| sub-workflow-join-reset | Nested JOIN not transitively reset after sub-workflow restart | Medium | Open in 3.30.0 (fixed in 3.31.0, PR #1212) | Avoid restarting sub-workflows with nested FORK_JOIN |
| graaljs-sandbox-unhardened | GraalJS sandbox not hardened: load(), print(), file I/O, env vars accessible | High | Open in 3.30.0 (hardened in 3.30.2) | Do not rely on sandbox isolation for security; upgrade to 3.30.2+ |

## Known Fixes Landed Prior to 3.30.0

| Fix | Commit / PR |
|-----|------------|
| DO_WHILE + SWITCH premature iteration advancement | commit 69faed274, PR #1001 (present in 3.30.0) |

## Fixes That Arrived AFTER 3.30.0

| Fix | Version |
|-----|---------|
| SWITCH empty-case no longer falls through to defaultCase | 3.31.0 (PR #1159) |
| DO_WHILE iteration list truncation | 3.31.0 (PR #1172) |
| Nested JOIN transitive reset after sub-workflow restart | 3.31.0 (PR #1212) |
| HUMAN task decider re-queue performance fix | 3.31.0 |
| GraalJS sandbox hardened | 3.30.2 |
| A2A Agent Protocol (AGENT, GET_AGENT_CARD, CANCEL_AGENT) | 3.32.0-rc.9 (PR #1288) |
| Secrets interpolation (`${workflow.secrets.X}`) | 3.32.0-rc.9 |
| Env interpolation (`${workflow.env.X}`) | 3.32.0-rc.9 |
| Worker poll visibility | 3.32.0-rc.9 (PR #1287) |
| MCP Integration (LIST_MCP_TOOLS, CALL_MCP_TOOL) | 3.32.0-rc.9 |

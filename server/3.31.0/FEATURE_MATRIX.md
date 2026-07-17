# Conductor OSS 3.31.0 Feature Matrix

Generated from source inspection and kitchen-sink battery test results.

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
| SWITCH | ✅ | javascript or value-param evaluator; replacement for deprecated DECISION |
| DECISION | ⚠️ | Deprecated alias for SWITCH; still functional, use SWITCH instead |
| DO_WHILE | ✅ | Iterative loop with loop condition evaluator |
| SUB_WORKFLOW | ✅ | Executes a named workflow as a task; supports inline definition |
| START_WORKFLOW | ✅ | Fire-and-forget workflow launch |

### Worker / Processing Tasks

| Task Type | Status | Notes |
|-----------|--------|-------|
| SIMPLE | ✅ | Poll-driven worker task; fundamental unit of user work |
| DYNAMIC | ✅ | Resolves task type at runtime from input |
| USER_DEFINED | ✅ | Fallback for unrecognized task type strings |
| HTTP | ✅ | Outbound HTTP/HTTPS requests (GET, POST, PUT, DELETE, HEAD, PATCH) |
| LAMBDA | ✅ | Synchronous JS eval via GraalVM; prefer INLINE |
| INLINE | ✅ | Synchronous JS or Python eval via GraalVM; hardened sandbox |
| JSON_JQ_TRANSFORM | ✅ | jq expression transforms on JSON payload |
| SET_VARIABLE | ✅ | Writes workflow-scoped variables (`${workflow.variables.X}`) |
| KAFKA_PUBLISH | ✅ | Publishes to Apache Kafka topic |

### Control Tasks

| Task Type | Status | Notes |
|-----------|--------|-------|
| WAIT | ✅ | Pauses until external signal or ISO-8601 duration/timestamp elapses |
| HUMAN | ⚠️ | Functional stub: transitions to IN_PROGRESS, awaits external completion. Full assignment UI/forms are Orkes Enterprise. |
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
| AGENT | ❌ | Not available in 3.31.0. Added in 3.32.0-rc.9 (PR #1288). |
| GET_AGENT_CARD | ❌ | Not available in 3.31.0. Added in 3.32.0-rc.9 (PR #1288). |
| CANCEL_AGENT | ❌ | Not available in 3.31.0. Added in 3.32.0-rc.9 (PR #1288). |

---

## Task Combination Matrix

Rows are the **outer** (containing) task; columns are the **inner** (nested) task type.

### DO_WHILE as Outer Container

| Inner Task | Status | Notes |
|-----------|--------|-------|
| DO_WHILE | 🐛 | Two open bugs: #1307 (loopCondition TypeError), #1308 (task name collision). Inner loop limited to 1 safe outer iteration. |
| FORK_JOIN | ✅ | Tested; iteration suffixes applied correctly via TaskUtils.appendIteration() |
| FORK_JOIN_DYNAMIC | ✅ | Confirmed working in kitchen-sink battery |
| SUB_WORKFLOW | ✅ | Explicitly e2e tested including rerun/retry scenarios |
| SWITCH | ✅ | Timing bug #895 fixed in commit 69faed274; regression-tested |
| WAIT | ✅ | Compatible with DO_WHILE async iteration logic |
| HTTP | ✅ | Confirmed working across multiple iterations |
| INLINE | ✅ | Regression-tested; premature iteration bug fixed |
| TERMINATE | ✅ | Terminates workflow (not just loop); by design |
| HUMAN | 🔲 | No code prevents it; no e2e tests confirm multi-iteration behavior |
| LAMBDA | ✅ | Same engine as INLINE; supported |
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
| SWITCH | ✅ | JOIN includes SWITCH-aware completion logic (commit 02aa4a5ca) |
| EXCLUSIVE_JOIN | 🐛 | Fails at runtime: ForkJoinTaskMapper requires JOIN, not EXCLUSIVE_JOIN, as successor. See #1309. |
| WAIT | ✅ | No restrictions |
| HTTP | ✅ | No restrictions |
| TERMINATE | ✅ | No restrictions |
| HUMAN | ✅ | No restrictions |

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
| FORK_JOIN | ✅ | e2e tested; any task type supported inside sub-workflow |
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
| Workflow Scheduler | ✅ | pre-3.31.0 | Cron-expression scheduler. `conductor.scheduler.enabled=true` (default). Backends: SQLite, MySQL, PostgreSQL (all fully implemented). |
| HUMAN Task (basic) | ✅ | pre-3.31.0 | Task goes IN_PROGRESS; external completion via task API |
| HUMAN Task Assignments / Forms | ❌ | — | Assignment management and form templates are Orkes Enterprise only |
| Wait-for-Webhook | ❌ | — | webhooks-oss module stub only; no runtime implementation in this version |
| HTTP Poll Task | ❌ | — | Not present in TaskType enum for this version |
| Secrets Interpolation (`${workflow.secrets.X}`) | ❌ | — | Not available in 3.31.0; added in 3.32.0-rc.9 |
| Env Interpolation (`${workflow.env.X}`) | ❌ | — | Not available in 3.31.0; added in 3.32.0-rc.9 |
| A2A Agent Protocol | ❌ | — | AGENT/GET_AGENT_CARD/CANCEL_AGENT tasks not present; added in 3.32.0-rc.9 (PR #1288) |
| LLM / AI Tasks | ✅ | pre-3.31.0 | 13 LLM providers (see table below). Enabled via AIIntegrationEnabledCondition |
| MCP Integration | ✅ | pre-3.31.0 | LIST_MCP_TOOLS, CALL_MCP_TOOL tasks; MCPService |
| GraalVM JS Sandbox | ✅ | 3.30.2 | Fully hardened (inherited from 3.30.2 patch): no IO, no reflection, no native, no threads/processes, 4-second timeout |
| Python Evaluator | ✅ | pre-3.31.0 | Via GraalVM polyglot python runtime (PythonEvaluator.java) |
| Event Handlers | ✅ | pre-3.31.0 | DefaultEventProcessor + ActionProcessor |
| Workflow Variables | ✅ | pre-3.31.0 | SET_VARIABLE task + `${workflow.variables.X}` expressions |
| Input/Output Expressions | ✅ | pre-3.31.0 | `${workflow.input.X}`, `${task_ref.output.X}`, etc. |
| Workflow Metrics (Prometheus) | ✅ | pre-3.31.0 | Prometheus endpoint; includes HTTP webhook publisher metrics (PR #1149) |
| Worker Poll Visibility | ❌ | — | Not available in 3.31.0; added in 3.32.0-rc.9 (PR #1287) |
| POST /metadata/workflow overwrite enforcement | ❌ | — | Overwrite flag not enforced in 3.31.0; all updates overwrite silently |

### LLM Providers

| Provider Name (in config) | Status | Notes |
|--------------------------|--------|-------|
| `openai` | ✅ | Full support; image generation; Responses API with previousResponseId |
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

## Known Bugs (3.31.0)

| Issue | Area | Severity | Status | Workaround |
|-------|------|----------|--------|-----------|
| [#1307](https://github.com/conductor-oss/conductor/issues/1307) | Nested DO_WHILE: loopCondition TypeError | High | Open (partial fix in source) | Limit outer loop to 1 iteration |
| [#1308](https://github.com/conductor-oss/conductor/issues/1308) | Nested DO_WHILE: task name collision | High | Open | Limit outer loop to 1 iteration |
| [#1309](https://github.com/conductor-oss/conductor/issues/1309) | FORK_JOIN + EXCLUSIVE_JOIN: runtime failure | Medium | Open | Use JOIN after FORK_JOIN; restructure |
| [#1310](https://github.com/conductor-oss/conductor/issues/1310) | WAIT task: misleading error for some ISO-8601 formats | Low | Open | Use fully-qualified durations (e.g. PT10S) |
| [#1311](https://github.com/conductor-oss/conductor/issues/1311) | SWITCH JS evaluator: validates with no bindings | Low | Open | Ensure all expression variables are bound in input |

## Known Fixes Landed in 3.31.0

| Fix | Commit / PR |
|-----|------------|
| DO_WHILE + SWITCH premature iteration advancement | commit 69faed274, PR #1001 |
| SWITCH empty-case no longer falls through to defaultCase | PR #1159 |
| DO_WHILE iteration list truncation | PR #1172 |
| Nested JOIN transitive reset after sub-workflow restart | PR #1212 |
| DO_WHILE loopCondition TypeError (BUG-1 of #1307) | DoWhile.java lines 521-523 |
| LLM task topP/temperature null handling for Claude | PR #1290 |
| Prometheus metrics for HTTP webhook publishers | PR #1149 |

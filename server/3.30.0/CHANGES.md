# Conductor OSS 3.30.0 — Baseline Inventory

This is the oldest version tracked in this catalog. The task type list below
is derived directly from `TaskType.java` at the `v3.30.0` tag.

## System Task Types Present at Baseline

### Control Flow
| TaskType | Description |
|----------|-------------|
| `DECISION` | Legacy branching (deprecated in favor of SWITCH) |
| `SWITCH` | Multi-branch conditional; supports `value-param` and `javascript` evaluators |
| `FORK_JOIN` | Static parallel branches; must be followed by a JOIN |
| `FORK_JOIN_DYNAMIC` | Dynamic parallel branches generated at runtime |
| `JOIN` | Waits for tasks listed in `joinOn` to complete |
| `EXCLUSIVE_JOIN` | Join for SWITCH branches; completes on first completed branch |
| `DO_WHILE` | Loop with JS condition; body tasks listed in `loopOver` |
| `TERMINATE` | Terminate workflow with a given status and output |

### Workflow Composition
| TaskType | Description |
|----------|-------------|
| `SUB_WORKFLOW` | Inline child workflow; parent waits for completion |
| `START_WORKFLOW` | Fire-and-forget child workflow; parent does not wait |
| `DYNAMIC` | Task type determined at runtime from workflow input |

### Data / Scripting
| TaskType | Description |
|----------|-------------|
| `INLINE` | Evaluate a JavaScript expression inline (`evaluatorType: "javascript"`) |
| `LAMBDA` | Evaluate a JS script via Nashorn/GraalVM (`lambdaValue` + `scriptExpression`) |
| `JSON_JQ_TRANSFORM` | Apply a jq expression to transform workflow data |
| `SET_VARIABLE` | Set workflow-level variables |
| `NOOP` | No-op; completes immediately with no output |

### I/O
| TaskType | Description |
|----------|-------------|
| `HTTP` | Make an HTTP request (`http_request` inputParameter object) |
| `EVENT` | Publish to an event sink |
| `WAIT` | Pause until a duration or timestamp (`duration`/`until` inputParameter) |
| `HUMAN` | Wait for an external human signal |
| `KAFKA_PUBLISH` | Publish a message to Kafka |

### AI / LLM
| TaskType | Description |
|----------|-------------|
| `LLM_TEXT_COMPLETE` | Text completion via LLM |
| `LLM_CHAT_COMPLETE` | Chat completion via LLM |
| `LLM_INDEX_TEXT` | Index text into a vector store |
| `LLM_SEARCH_INDEX` | Search a vector index |
| `LLM_GENERATE_EMBEDDINGS` | Generate vector embeddings |
| `LLM_STORE_EMBEDDINGS` | Store embeddings to a vector store |
| `LLM_GET_EMBEDDINGS` | Retrieve stored embeddings |

### MCP (Model Context Protocol)
| TaskType | Description |
|----------|-------------|
| `LIST_MCP_TOOLS` | List available MCP tools |
| `CALL_MCP_TOOL` | Invoke an MCP tool |

### Other
| TaskType | Description |
|----------|-------------|
| `SIMPLE` | User-defined worker task |
| `USER_DEFINED` | Alias for custom task types |
| `PULL_WORKFLOW_MESSAGES` | Pull messages from a workflow message queue |

## Notes

- `WAIT_FOR_WEBHOOK` and `HTTP_POLL` are **not present** in Conductor OSS 3.30.0
  (they appear in Orkes Enterprise builds).
- `DECISION` is the legacy switch-like task; `SWITCH` is preferred.
- The LLM and MCP task families require external AI/vector store configuration
  in `conductor.yml` to function.

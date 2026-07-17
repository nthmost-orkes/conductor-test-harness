# Changes in Conductor OSS 3.32.0-rc.9

_Relative to v3.31.0_

## New Task Types

Three new A2A (Agent-to-Agent) task types added in the `ai` module (`#1288`).
These require `conductor.ai.enabled=true` and the `ai` module on the classpath.

### `AGENT`
Send a message to a remote A2A agent and await the result. Supports polling,
push-notification (webhook), and SSE streaming modes.

**Required inputParameters:** at least one of `text`, `parts`, or `message`  
**For remote A2A agents:** also `agentUrl` (the agent's JSON-RPC endpoint)  
**For Conductor agents:** also `agentName` (registered agent name)

Full inputParameter reference (all fields optional unless noted):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agentType` | string | `"a2a"` | `"a2a"` for remote A2A protocol; `"conductor"` for embedded agent runtime |
| `agentUrl` | string | required for a2a | Remote agent's JSON-RPC endpoint URL (from agent card) |
| `agentName` | string | required for conductor | Registered Conductor agent name |
| `agentVersion` | integer | latest | Agent version for `conductor` type |
| `text` | string | — | Convenience: single text part to send |
| `parts` | array | — | Explicit A2A message parts (advanced) |
| `message` | object | — | Full A2A message override; takes precedence over `parts`/`text` |
| `contextId` | string | — | Context id to continue an existing session |
| `taskId` | string | — | Task id to resume an existing remote task |
| `headers` | object | — | HTTP headers for the request (e.g. `Authorization`) |
| `historyLength` | integer | — | How much message history to return in the task |
| `pollIntervalSeconds` | integer | `5` | Poll interval while remote task is running |
| `maxDurationSeconds` | integer | `86400` (24h) | Absolute deadline; task fails terminally if exceeded |
| `maxPollFailures` | integer | `30` | Max consecutive transient poll failures before terminal failure |
| `streaming` | boolean | `false` | Use SSE streaming (`message/stream`) instead of send+poll |
| `pushNotification` | boolean | `false` | Use webhook push mode (requires `conductor.a2a.callback.url`) |
| `pushBackstopPollSeconds` | integer | `300` | Backstop poll interval in push mode |
| `metadata` | object | — | Extra metadata for `message/send` call |
| `sessionId` | string | — | Session id for `conductor` type agent run |
| `runId` | string | — | Run id for `conductor` type agent execution |
| `executionId` | string | — | Resume an in-flight `conductor` agent execution |
| `context` | object | — | Additional context for `conductor` agent run |

### `GET_AGENT_CARD`
Retrieve the agent card (capability manifest) from a remote A2A agent endpoint.

### `CANCEL_AGENT`
Cancel a running A2A agent task.

## Removed / Renamed Task Types
None

## Task Input Parameter Changes

**`TaskDef.runtimeMetadata`** — new field on task definitions (`#1251`).
Allows task definitions to declare secrets/env vars to be injected at poll time.
The injected values are wire-only (never persisted in task output).

## Deprecated Fields / Behaviors
None

## Behavioral Changes

### Secrets and environment variable references in workflow definitions (`#1251`)
New variable interpolation syntax:
- `${workflow.secrets.KEY}` — resolves from `CONDUCTOR_SECRET_KEY` env var; value is
  **never persisted** in task input/output (deferred resolution only)
- `${workflow.env.KEY}` — resolves from `CONDUCTOR_ENV_KEY` env var

New read-only REST endpoints: `GET /api/environment` and `GET /api/secrets`.

### POST /metadata/workflow now honors `?overwrite=false` (`#1264`)
Previously the `overwrite` query parameter was accepted but ignored; all POSTs
overwrote existing definitions. As of rc.9, `?overwrite=false` (the default when
omitted) rejects the update if the workflow definition already exists. SDK authors
who relied on idempotent re-registration must now pass `?overwrite=true` explicitly.

### JOIN task: AgentSpan key propagation limited
For workflows that use JOIN after AGENT tasks in AgentSpan mode, only
`_state_updates` and `state` keys are propagated from fork-branch outputs into the
JOIN output. Previously all fork-branch output keys were propagated.
This only affects workflows that use the AgentSpan runtime (agentspan module).

### LiteLLM added as AI gateway provider (`#1249`)
`LLM_*` task types can now target LiteLLM as an AI provider integration,
in addition to existing providers (Anthropic, OpenAI, Cohere, Gemini, etc.).

## Breaking Changes

### POST /metadata/workflow: `overwrite` now enforced
If your SDK code registers workflows without `?overwrite=true` and a definition
already exists, the server will now return an error instead of silently overwriting.
Add `overwrite=true` to all registration calls that should be idempotent.

## Notes

- `AGENT` task requires the `ai` module and `conductor.ai.enabled=true`.
- `AGENT` push-notification mode requires `conductor.a2a.callback.url` to be set
  to an externally-reachable URL; without it the task falls back to polling with a
  warning logged.
- `AGENT` uses a deterministic `messageId` across retries (`a2a-{workflowId}:{ref}:{iter}`)
  so agents that deduplicate on `messageId` get effectively-once delivery.
- LLM task: UI now clears empty `temperature`/`topP` to null rather than 0 for Claude
  (Claude rejects both fields set simultaneously). Server-side behavior unchanged;
  SDK authors building LLM workflows for Claude should set unused numeric params to null.

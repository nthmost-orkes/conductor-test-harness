> **Historical (2026-07-30).** Superseded by
> [`../3.32.0/AGENT_CAPABILITIES.md`](../3.32.0/AGENT_CAPABILITIES.md). "BLOCKER-1" (A2A server
> wouldn't enable) is **resolved in v3.32.0**, where the full round-trip — GET_AGENT_CARD / AGENT
> / CANCEL_AGENT, incl. FORK_JOIN and DO_WHILE — is live-confirmed.

# AGENT task family (A2A) — Capability Checks

Server baseline: Conductor `3.32.0-rc.9`
Date: 2026-07-30
Catalog source: `server/3.32.0-rc.9/capabilities.yaml` (`AGENT`, `GET_AGENT_CARD`,
`CANCEL_AGENT`, `a2a_agent_protocol`, and the AGENT `task_combinations`).

Two servers used: shared 7001 (defaults) for client-side task checks; a purpose-built
7002 (SQLite, `conductor.integrations.ai.enabled=true`, `conductor.a2a.server.enabled=true`,
`expose-all=true`, `allow-private-network=true`, clean Anthropic key) to attempt a
self-hosted A2A round-trip.

Legend: ✅ live-confirmed · 🔎 wiring-confirmed (executes/validates, full behavior not
live-tested) · ⛔ blocked (see BLOCKER) · 🧩 open question.

---

## Results vs catalog claims

| Catalog claim | Result | Evidence |
|---|---|---|
| `AGENT` supported | 🔎 | Worker `A2AWorkers`/`AgentTask` loads (`AGENT initialized`); task executes and validates `agentUrl`. Full remote round-trip not live-tested (no reachable A2A agent). |
| `GET_AGENT_CARD` supported | 🔎 | `@WorkerTask getAgentCard … taskType=GET_AGENT_CARD` loads; task **executed** and reached the fetch stage (failed only at SSRF guard — see below). |
| `CANCEL_AGENT` supported | 🔎 | Worker present; input contract is `{agentUrl, taskId}`. Not executed live. |
| `AGENT` inside `DO_WHILE` (resume path) | ⛔ | Requires a working AGENT round-trip; blocked by BLOCKER-1. Catalog cites `ConductorAgentEndToEndTest` (Java). |
| `AGENT` inside `FORK_JOIN` (independence) | ⛔ | Blocked by BLOCKER-1. Catalog already notes the Java test `AgentTaskTests.concurrentCalls…` is class-level `@Disabled`. |
| `a2a_agent_protocol` / `A2AWorkflowAgent` exposes a workflow as an A2A endpoint | 🧩 | Could not enable the A2A **server** REST layer via config — see BLOCKER-1. |

---

## Confirmed findings

### ✅ AGENT client tasks are wired, validate input, and enforce SSRF protection
Running `ai/examples/11-a2a-get-agent-card.json` (agentUrl `http://localhost:9999`) on the
default 7001 server:
```
GET_AGENT_CARD  FAILED_WITH_TERMINAL_ERROR
Non-retryable error: agentUrl resolves to a private/reserved address —
SSRF blocked: 127.0.0.1 (set conductor.a2a.client.allow-private-network=true
to allow private-network agents)
```
This confirms three things at once: the task type is registered, it executes, and the A2A
client blocks private/reserved addresses by default. `AGENT` and `CANCEL_AGENT` share the
same validation (`requires 'agentUrl'`).

### ⚠️ Shipped `ai/examples/*a2a*.json` cannot run out-of-the-box
Every A2A example targets `http://localhost:9999`, which fails two ways on a default server:
(1) nothing is listening there, and (2) even if an agent were running locally, the SSRF
guard blocks `127.0.0.1` unless `conductor.a2a.client.allow-private-network=true` is set.
A first-time user running these examples per the `ai/examples/README.md` hits an immediate
terminal failure with no hint that a private-network flag is required.
- Suggested fix: document the flag in `ai/examples/README.md`, and/or ship the examples with
  `agentUrl` as a `${workflow.input.agentUrl}` with setup instructions.

---

## BLOCKER-1 (🧩 open question — needs maintainer confirmation)

**Could not enable the A2A *server* REST layer via documented configuration.** To stand up a
self-hosted round-trip, a Conductor workflow must be exposed as an A2A agent by
`A2AServerResource` (`/api/a2a/workflow/{wf}/.well-known/agent-card.json`, gated by
`A2AServerEnabledCondition` on `conductor.a2a.server.enabled=true`).

On a 3.32.0-rc.9 boot jar, that resource returns **404** under every configuration attempt:
- `--conductor.a2a.server.enabled=true` (CLI arg)
- `CONDUCTOR_A2A_SERVER_ENABLED=true` (env var)
- `application.properties` in cwd, with and without `conductor.integrations.ai.enabled=true`
- `conductor.a2a.server.expose-all=true` in all combinations

The AI **task/worker** layer initializes normally in the same run (`AGENT initialized`,
`GET_AGENT_CARD` worker found, `LLMWorkers`/`VectorDBWorkers` initialized), and the
`agentspan`-module controllers register fine (`GET /api/providers/status` → 200). But **both**
`ai`-module conditional REST controllers 404: `A2AServerResource` (`/api/a2a/workflow`) and
`A2ACallbackResource` (`/api/a2a/agent-card`, `/api/a2a/callback/{taskId}`, gated on
`conductor.integrations.ai.enabled`).

Interpretation (unconfirmed): the `ai`-module `@RestController`s may not be registered in the
server boot jar's web layer even when their enable-conditions are satisfied — while `ai`-module
`@WorkerTask` beans (scanned by `WorkerTaskAnnotationScanner`) are. This would block hosting a
Conductor workflow as an A2A agent, which the catalog lists as supported.

**Do not file as a bug yet** — confirm with a maintainer whether an additional flag/profile is
required or this is a packaging/scan gap.

---

## To finish these checks (next pass)
A working AGENT round-trip needs a reachable A2A agent. Options once BLOCKER-1 is resolved:
1. Enable the A2A server, register a trivial workflow with `a2a.enabled=true` metadata, fetch
   its card, then drive `GET_AGENT_CARD` → `AGENT` → `CANCEL_AGENT` against it (loopback, with
   `allow-private-network=true`).
2. Then wrap the `AGENT` task in `DO_WHILE` (resume) and in `FORK_JOIN` (independence) to close
   the two combination rows above.

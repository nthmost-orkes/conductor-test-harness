# AGENT task family (A2A) — Capability Checks (v3.4.0)

Server baseline: Conductor **v3.4.0**
Date: 2026-08-10
Test server: local v3.4.0 boot jar on `:7003`, SQLite, with
`conductor.integrations.ai.enabled=true`, `conductor.a2a.server.enabled=true`,
`conductor.a2a.server.expose-all=true`, `conductor.a2a.client.allow-private-network=true`.

**Headline: every AGENT/A2A capability the catalog lists is now live-confirmed.** The
`3.32.0-rc.9` blocker (A2A server REST layer wouldn't register) is resolved in v3.4.0, so a full
self-hosted round-trip works: a Conductor workflow is exposed as an A2A agent and driven by
`GET_AGENT_CARD` / `AGENT` / `CANCEL_AGENT` tasks — including inside `FORK_JOIN` and `DO_WHILE`.

Legend: ✅ live-confirmed.

| Catalog claim | Result | Evidence |
|---|---|---|
| A2A server exposes a workflow as an agent (`A2AWorkflowAgent`) | ✅ | `GET /api/a2a/workflow` → 200; `…/{wf}/.well-known/agent-card.json` serves a valid AgentCard (protocol 0.3.0, JSONRPC). |
| `GET_AGENT_CARD` | ✅ | Task COMPLETED; returned the target's `agentCard` (name `a2a_echo_wf`). |
| `AGENT` | ✅ | Task COMPLETED; remote workflow executed and returned `state=completed` + remote `taskId`. |
| `CANCEL_AGENT` (cancel contract, conductor#1342) | ✅ | Task COMPLETED; remote task returned `{"status":{"state":"canceled"}}`. |
| `AGENT` inside `FORK_JOIN` (independence) | ✅ | Two AGENT branches both COMPLETED with **distinct** remote taskIds. |
| `AGENT` inside `DO_WHILE` | ✅ | 2 iterations (`a__1`, `a__2`) both COMPLETED; DO_WHILE COMPLETED. |

---

## How the round-trip was set up

1. Enabled the A2A server + private-network on a v3.4.0 instance (the exact flags that were
   inert on the rc.9 jar).
2. Registered a trivial workflow `a2a_echo_wf`; with `expose-all=true` it is served as an A2A
   agent at `http://localhost:7003/api/a2a/workflow/a2a_echo_wf`.
3. Drove the AGENT task types against that URL (loopback is allowed because
   `allow-private-network=true`).

A first attempt returned a *remote* failure — a bug in the echo workflow's INLINE graaljs
(`return` isn't valid at top level; use `(function(){ return … })()`). That the AGENT task
faithfully surfaced the remote error (`state=failed`, remote `taskId`, `agentMessage`) is itself
evidence the request/response propagation works; after fixing the script the call returned
`state=completed`.

## Notes
- The shipped `ai/examples/*a2a*.json` still target `http://localhost:9999` and still need
  `conductor.a2a.client.allow-private-network=true` to reach a loopback agent — the SSRF guard
  blocks private addresses by default. (Onboarding note carried over from rc.9; the guard is
  correct, the examples just need the flag documented.)
- `CANCEL_AGENT` was exercised against an already-terminal remote task (the WAIT-based agent
  completed immediately — `WAIT duration:"120s"` did not hold), which still returned a proper
  canceled Task. A mid-flight cancel of a genuinely long-running remote agent wasn't isolated.

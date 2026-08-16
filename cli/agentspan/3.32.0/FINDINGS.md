# conductor-cli agentspan — Findings (v3.32.0 baseline)

CLI: `conductor-oss/conductor-cli` @ `main` (b21bc31), built from source
Server baseline: Conductor **v3.32.0** (the graduated stable of the `3.32.0-rc.*` line; current Latest is v3.32.1)
Analysis date: 2026-08-10
Test server: local SQLite boot jar on `http://localhost:7003/api`, both providers configured

> **Provenance / versioning note.** These findings were validated against the boot jar originally
> tagged **v3.4.0** — a transient tag that was later **retracted** (its release now 404s). That
> build is the same codebase that shipped as **v3.32.0** stable (the `3.32.0-rc.*` line graduating
> to release), so the findings apply to 3.32.0/3.32.1. The `TaskType` enum is unchanged from
> `3.32.0-rc.9`, so the capability-catalog content still holds. Prior baseline: `../3.32.0-rc.9/`
> (historical).

This baseline supersedes `3.32.0-rc.9`: the two CLI bugs and the server key-trim bug filed
there are now fixed, and the A2A-server blocker is resolved. See `AGENT_CAPABILITIES.md` for
the full A2A round-trip results.

---

## Command coverage (v3.32.0)

| Command | Result | Notes |
|---|---|---|
| `agent init` | ✅ | Flat YAML/JSON `AgentConfig`. |
| `agent compile` | ✅ **fixed** | Now wraps `{"agentConfig":…}` and returns the compiled workflow. (was #96) |
| `agent run --config` | ✅ | Anthropic ran green end-to-end (`run`→stream→`done`→`status COMPLETED`). |
| `agent stream` | ⚠️ | Works, but `[error]` events still carry an empty message (ISSUE-5, still open). |
| `agent status` | ✅ | |
| `agent execution` (`--name`, `--status`) | ✅ | |
| `agent execution --since` | ✅ **fixed** | All formats return matches. (was #97) |
| `agent execution --window now-X` | ✅ **fixed (server)** | Works on the v3.32.0 server; the rc.9 residual was a server search limit — see below. |
| `agent list` / `get` / `delete` | ✅ | `delete` correctly 400s on a missing agent (not idempotent). |
| `agent prune --dry-run` | ✅ | `--older-than` still int-days vs `--since` durations (minor). |
| `doctor` | ⚠️ | Still reports client-shell provider env, not server providers (ISSUE-4) — now *doubly* misleading, see below. |
| `skill` | 🗑️ removed | The `skill` (and `code`) commands were deleted from the CLI since rc.9. |
| `agent respond` (HITL) / `deploy` (project) | ⏭️ | Still not exercised. |

---

## Resolved since the 3.32.0-rc.9 baseline

- **compile envelope — conductor-cli#96** (closed Aug 7). CLI now wraps the config; `agent compile` returns the workflow. Live-confirmed.
- **execution time filter — conductor-cli#97** (closed Aug 10). `--since` fixed. `--window` also works against the v3.32.0 server (see next), so it's effectively resolved on current.
- **provider key trimming — conductor#1437** (closed Aug 5). Fixed at ingestion (`AgentspanAIModelProvider` + provider keys). Live-confirmed indirectly: a trailing-newline key no longer throws `Unexpected char 0x0a`; the key reaches OpenAI and gets a normal API response.
- **A2A server exposure (BLOCKER-1 from rc.9)**. `/api/a2a/workflow` returns 200 on v3.32.0 with the same flags that 404'd on the rc.9 jar. Full A2A round-trip now works — see `AGENT_CAPABILITIES.md`.

### `--window` was a server-side search limit, fixed in v3.32.0
On the rc.9 server, `--window now-X` always returned zero. Isolated cause: the SQLite
`/workflow/search` could not intersect two range predicates on the same field
(`startTime>A AND startTime<B` → 0, though each bound worked alone). On the **v3.32.0 server the
same intersection returns the expected rows**, so `--window` now works. (Tracked as a follow-up
note on conductor-cli#97.)

---

## Still open on v3.32.0

### ⚠️ ISSUE-4 — `doctor` reports client-shell env, not the server it targets
`doctor`'s "AI Providers" section reads only `os.Getenv(...)` (`cmd/doctor.go`) and never calls
`/api/providers/status`. Concrete repro: pointed at the 7010 server (openai, anthropic,
perplexity, huggingface, ollama all configured), a shell with the provider vars unset prints
**"0 AI provider(s) configured"** — yet `agent run` on that server works. `doctor` prints the
server URL one line above the provider list, so the list reads as the server's. It should also
surface `GET /api/providers/status`. (The client-env check is legitimate for the local
deploy/runtime path — keep both, don't replace.)
- Repo: **conductor-cli** · `cmd/doctor.go` · framing: enhancement

### ⚠️ ISSUE-5 — Stream renderer reads several wrong field names (systemic)
`terminalSink` (`cmd/agent_stream.go`) reads field names that don't match the server's SSE schema
(`common/.../agent/AgentSSEEvent.java`: `content, toolName, args, result, target, output,
guardrailName`). Mismatched renderers emit blank text — most importantly the failure reason.

| Event | CLI reads | Server field | Status |
|---|---|---|---|
| thinking | `message` | `content` | ❌ empty (confirmed live) |
| error | `message` | `content` | ❌ empty (confirmed live) |
| toolCall input | `input` | `args` | ❌ empty (schema) |
| handoff | `agentName` | `target` | ❌ empty (schema) |
| guardrail fail reason | `reason` | *(no `reason` field)* | ❌ empty (schema) |
| toolResult | `result` | `result` | ✅ |
| message | `content` | `content` | ✅ |
| waiting | `executionId` | `executionId` | ✅ |
| guardrail pass | `guardrailName` | `guardrailName` | ✅ |
| done | `output` | `output` | ✅ |

Raw proof for `error` (via `/api/agent/stream/{id}`):
```
event:error
data:{"type":"error","content":"Task … failed … reason: 'Task execution failed: 404 - model … not found'","toolName":"workflow"}
```
The failure reason is in the stream but discarded. **Not a server bug** — payload is complete; the
CLI just reads the wrong keys. Fix: align each renderer with `AgentSSEEvent` field names.
- Repo: **conductor-cli** · `cmd/agent_stream.go`

### ℹ️ Minor
`prune --older-than` (int days) vs `execution --since` (duration strings) — inconsistent units;
`prune --dry-run` reports no count.

---

## Environment note (not a bug)
The audit run above used an OpenAI project key that lacked `gpt-4o` access (HTTP 403
`model_not_found`), so OpenAI runs failed at the time — an account limitation, not a Conductor
issue. **Resolved:** with a dedicated harness key wired via `providers/secrets.env`,
`openai/gpt-4o` runs green (see `providers/` and `scripts/agent-matrix.sh` → PASS=5/5).

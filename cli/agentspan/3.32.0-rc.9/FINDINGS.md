> **Historical (2026-07-30).** Superseded by [`../3.4.0/`](../3.4.0/). The two CLI bugs
> (compile #96, execution #97) and the server key-trim bug (#1437) below are **fixed**; the A2A
> "BLOCKER-1" is **resolved** in v3.4.0. Kept for the record.

# conductor-cli agentspan — Findings

CLI: `conductor-oss/conductor-cli` (built from source — see note below)
Server baseline: Conductor `3.32.0-rc.9`
Analysis date: 2026-07-30
Test server: local boot jar on `http://localhost:7001/api` (OpenAI + Anthropic configured server-side)

Methodology: exercise the full `conductor agent` operator surface against a live
3.32.0-rc.9 server, using two minimal instructions-only agent configs (one per
provider) so no Python tool-worker is required — the clean CLI-only path. A native
agent config compiles to a Conductor workflow whose single task is `LLM_CHAT_COMPLETE`.

> **Release note:** the whole agentspan surface (`agent`, `skill`, `deploy`, `doctor`)
> exists only in `conductor-cli` source. The **Homebrew-released `conductor` binary has
> none of these commands** — anyone following agentspan docs with an installed CLI hits
> "unknown command". Tested against a `go build` of current `main`.

---

## Command coverage

| Command | Result | Notes |
|---|---|---|
| `agent init` | ✅ | Writes flat YAML/JSON `AgentConfig` (`name/description/model/instructions/maxTurns/tools`). Requires a server *configured* (not live). |
| `agent run --config` | ✅ | Wraps config as `{"agentConfig":…}` (correct envelope). Anthropic ran green end-to-end. |
| `agent stream` | ✅ | SSE renders thinking/tool/message/done. See ISSUE-5 (empty error events). |
| `agent status <id>` | ✅ | Returns status + output + `reasonForIncompletion`. |
| `agent execution` (no filter, `--name`, `--status`) | ✅ | Lists executions correctly. |
| `agent execution --since` / `--window` | 🐛 | **Always returns zero** — see ISSUE-2. |
| `agent list` / `get` / `delete` | ✅ | `run --config` auto-registers the agent def. |
| `agent prune --dry-run` | ✅ | Works; `--older-than` is int-days (see ISSUE-6). |
| `agent compile <file>` | 🐛 | **500 on every call** — see ISSUE-1. |
| `doctor` | ⚠️ | Reports client-shell provider env, not server providers — see ISSUE-4. |
| `agent respond` (HITL) | ⏭️ | Not covered — needs a human-in-the-loop agent. |
| `deploy` (top-level, project) | ⏭️ | Not covered — scans a python/typescript project; framework path. |

---

## Findings

### 🐛 ISSUE-1 — `agent compile` sends the bare config (always 500)
`restClient.Compile` POSTs the raw config bytes to `/api/agent/compile`. The server's
`AgentController.compileAgent` binds `@RequestBody AgentStartRequest`, which carries the
config under `agentConfig`. The bare payload has no `agentConfig` key → server NPE:

```
500: Cannot invoke "…AgentConfig.getName()" because "config" is null
```

`restClient.Run` already wraps correctly (`startRequest{AgentConfig: def}`); `Compile`
does not. Confirmed by curl — wrapping the identical config in `{"agentConfig":…}`
returns the compiled `workflowDef` (an `LLM_CHAT_COMPLETE` task).
- Repo: **conductor-cli** · File: `internal/agent/client.go` (`Compile`)
- Fix: wrap like `Run` — `startRequest{AgentConfig: def}`.

### 🐛 ISSUE-2 — `agent execution --since` / `--window` always return zero
Every documented format (`1h`, `6h`, `1d`, `7d`, `now-7d`) returns "No executions found",
even with executions created seconds earlier. The CLI builds
`freeText=startTime:[<ms> TO *]`; the server's execution search (SQLite persistence)
does not honor that Lucene-style range. Confirmed via raw endpoint:
`freeText=*` → `totalHits=69`; `freeText=startTime:[<ms> TO *]` → `totalHits=0`.
- Repo: **conductor-cli** (emits an unsupported query) + **conductor** (backend lacks range support)
- File: `internal/agent/client.go` (`buildExecutionFreeText`) / server execution search DAO
- Impact: users conclude they have no recent executions.

### ⚠️ ISSUE-3 — Server does not trim provider API keys
The test server's `OPENAI_API_KEY` had a trailing `\n`; every OpenAI call failed with:
```
Task execution failed: Unexpected char 0x0a at 80 in Authorization value
```
(`"Bearer "` = 7 chars + a 72-char key ⇒ the `0x0a` sits at position 80.) The OpenAI
provider builds `"Bearer " + apiKey` with no `.trim()`; the credentials resolver doesn't
sanitize either. A trailing newline (common when keys are loaded from a file or `echo`'d)
produces a cryptic runtime error instead of a clear "malformed key" at config time.
Anthropic's clean 108-char key worked, proving the path is otherwise fine.
- Repo: **conductor** · Files: `ai/.../providers/openai/api/OpenAI*Api.java`, agentspan credentials resolver
- Fix: trim provider keys on load; optionally surface validity in `/api/providers/status`.

### ⚠️ ISSUE-4 — `doctor` reports client-shell provider env, not server providers
`doctor`'s "AI Providers" section reflects the local shell's env vars, so it listed
Anthropic as unconfigured even though the server has it (and ran an Anthropic agent).
Since agent execution uses **server-side** providers, `doctor` should also read
`GET /api/providers/status` and report what the server can actually dial.
- Repo: **conductor-cli** · File: `cmd/doctor.go`

### ⚠️ ISSUE-5 — Streamed `[error]` events carry an empty message
The failed OpenAI run streamed `[error]` with no text; the cause
(`reasonForIncompletion`) was only visible via `agent status`. The SSE error event
should include the reason so streaming users see why a run failed.
- Repo: **conductor-cli** (event render) and/or **conductor** (SSE payload)

### ℹ️ ISSUE-6 — Minor UX
- `prune --older-than` takes a bare int (days) while `execution --since` takes duration
  strings (`1d`) — inconsistent units across sibling commands.
- `prune --dry-run` reports intent ("would prune executions older than N days") but not a
  **count** of affected records — limited usefulness.
- `agent doctor` (as a subcommand) silently prints `agent` help; `doctor` is top-level.

---

## What worked (positive confirmations)
- Native `AgentConfig` → server compiles to an `LLM_CHAT_COMPLETE` workflow (matches
  catalog `ai_llm: supported`).
- `run` → SSE stream (`thinking` → `message`/`done`) → `status COMPLETED` with structured
  `{result, finishReason}` — full happy path via CLI, Anthropic provider.
- `run --config` auto-registers the agent; `list`/`get`/`delete` round-trip cleanly.
- Server `/api/providers/status` correctly reports configured/reachable providers
  (openai, anthropic, perplexity, huggingface, ollama-reachable).

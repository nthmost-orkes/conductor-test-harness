# conductor-cli agentspan — Issues Punch List (v3.4.0)

Server baseline: Conductor **v3.4.0**. Supersedes `../3.32.0-rc.9/ISSUES.md`.

Status key: `[x]` filed · `[✓]` fixed/closed · `[~]` verified by live test

---

## Fixed since 3.32.0-rc.9

- [✓][~] **conductor-cli#96 — `agent compile` 500** → wraps `{"agentConfig":…}`; returns workflow. (closed Aug 7)
- [✓][~] **conductor-cli#97 — `agent execution --since/--window`** → `--since` fixed; `--window` works on the v3.4.0 server. (closed Aug 10; follow-up note left re: `--window`/server search)
- [✓][~] **conductor#1437 — provider keys not trimmed** → stripped at ingestion; newline key no longer breaks the auth header. (closed Aug 5)
- [✓][~] **BLOCKER-1 — A2A server REST layer wouldn't enable** → `/api/a2a/workflow` returns 200 on v3.4.0; full round-trip works.

## Still open

- [ ] [~] **doctor reports client-shell env, not the server it targets** (conductor-cli, `cmd/doctor.go`).
  The "AI Providers" section reads only `os.Getenv(...)` and never calls `/api/providers/status`.
  Repro: pointed at a server with openai/anthropic/perplexity/huggingface/ollama configured, a clean
  shell prints **"0 AI provider(s) configured"** — while `agent run` on that server works. It shows the
  server URL one line above, so users read the provider list as the server's. Enhancement: also surface
  `/api/providers/status`. (Client-env check is legitimate for the local deploy/runtime path — keep both.)
- [ ] [~] **streamed `[thinking]` and `[error]` render empty — CLI reads the wrong field** (conductor-cli, `cmd/agent_stream.go`).
  `terminalSink` does `mapStr(data, "message")` for `EventThinking` (L110) and `EventError` (L128), but the
  server's SSE payload carries the text in **`content`** (confirmed via raw `/api/agent/stream/{id}`:
  `event:error … data:{"type":"error","content":"Task … failed … reason: '…'"}`). So the failure reason is
  present in the stream but discarded; `[error]`/`[thinking]` print blank. Fix: read `content` (as
  `EventMessage` already does). Also audit tool/handoff/guardrail/waiting renderers for the same mismatch.
  NOT a server bug — the payload is complete.
- [ ] **prune `--older-than` int-days vs `execution --since` durations**; `prune --dry-run` reports no count (minor).

## Not yet covered
- `agent respond` (needs a HITL agent); top-level `deploy` (needs a project scaffold).

## Environment (not an issue)
- OpenAI project key lacks `gpt-4o`/`gpt-4o-mini` access (403) in this env — account limitation, not a bug.

> **Historical (2026-07-30).** Superseded by [`../3.32.0/ISSUES.md`](../3.32.0/ISSUES.md).
> #96/#97/#1437 are fixed and the A2A blocker resolved in v3.32.0.

# conductor-cli agentspan — Issues Punch List

Derived from `FINDINGS.md` and live testing (`live_test.sh`).
Server baseline: Conductor **3.32.0-rc.9**.

Status key: `[ ]` = not filed · `[x]` = filed · `[~]` = verified by live test

---

## CRITICAL

- [ ] [~] **compile — `agent compile <file>` returns 500 on every call** (conductor-cli)
  CLI POSTs the bare config; server expects `{"agentConfig":…}`.
  File: `internal/agent/client.go` → `Compile`
  Fix: wrap like `Run` (`startRequest{AgentConfig: def}`).
  *Live: bare → 500 NPE; wrapped → compiled workflowDef*

## HIGH

- [ ] [~] **execution — `--since` / `--window` always return zero** (conductor-cli + conductor)
  CLI builds `freeText=startTime:[<ms> TO *]`; SQLite search returns nothing.
  Files: `internal/agent/client.go` → `buildExecutionFreeText`; server execution search DAO
  *Live: `freeText=*` → 69 hits; range query → 0*

- [ ] [~] **provider keys — server does not trim API keys** (conductor)
  Trailing `\n` in `OPENAI_API_KEY` → `Unexpected char 0x0a … in Authorization value`.
  Files: `ai/.../providers/openai/api/OpenAI*Api.java` (`"Bearer " + apiKey`, no trim)
  Fix: trim on load; validate at provider-config time.
  *Live: OpenAI failed on newline key; clean Anthropic key succeeded*

## MEDIUM

- [ ] **doctor — reports client-shell env, not server providers** (conductor-cli)
  Should read `GET /api/providers/status`.
  File: `cmd/doctor.go`

- [ ] [~] **stream — `[error]` events carry empty message** (conductor-cli / conductor)
  Cause only visible via `agent status` (`reasonForIncompletion`).

## LOW

- [ ] **prune `--older-than` int-days vs `execution --since` duration strings** — inconsistent units
- [ ] **prune `--dry-run` reports no count** of affected records
- [ ] **Homebrew `conductor` lacks the entire agentspan surface** (`agent`/`skill`/`deploy`/`doctor`) — release/packaging gap

---

## Not yet covered (next pass)
- `agent respond` — needs a human-in-the-loop agent that reaches `[waiting]`.
- `deploy` (top-level) — needs a python/typescript project scaffold with agent defs.
- AGENT-task capability checks (AGENT-in-DO_WHILE resume, AGENT-in-FORK_JOIN independence,
  GET_AGENT_CARD, CANCEL_AGENT) — see `AGENT_CAPABILITIES.md`.

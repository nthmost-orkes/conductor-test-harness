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

- [ ] [~] **doctor reports client-shell env, not server providers** (conductor-cli, `cmd/doctor.go`). On v3.4.0 doubly misleading: OpenAI shown "ok" but 403s server-side; Anthropic shown unconfigured but works.
- [ ] [~] **streamed `[error]` events carry empty message** (conductor-cli / conductor). Cause only via `agent status`.
- [ ] **prune `--older-than` int-days vs `execution --since` durations**; `prune --dry-run` reports no count (minor).

## Not yet covered
- `agent respond` (needs a HITL agent); top-level `deploy` (needs a project scaffold).

## Environment (not an issue)
- OpenAI project key lacks `gpt-4o`/`gpt-4o-mini` access (403) in this env — account limitation, not a bug.

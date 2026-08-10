# Where we're leaving off (2026-08-11)

## Done this stretch — conductor-cli agentspan + v3.4.0 rebaseline

- **agentspan CLI audit.** `cli/agentspan/3.32.0-rc.9/` (historical) and `cli/agentspan/3.4.0/`
  (current baseline): FINDINGS, ISSUES, AGENT_CAPABILITIES, live_test.sh.
- **Bugs filed and fixed** (verified on v3.4.0): conductor-cli **#96** (compile envelope),
  **#97** (execution `--since`/`--window`), conductor **#1437** (provider key trimming); the
  rc.9 A2A-server blocker is resolved.
- **Bugs filed, still open:** conductor-cli **#116** (stream renderer reads wrong SSE field
  names → blank `[thinking]`/`[error]`), **#117** (doctor should also report the server's
  `/api/providers/status`, not just local env).
- **AGENT/A2A capabilities live-confirmed on v3.4.0** (see `cli/agentspan/3.4.0/AGENT_CAPABILITIES.md`):
  GET_AGENT_CARD / AGENT / CANCEL_AGENT, incl. inside FORK_JOIN and DO_WHILE.
- **Provider harness** (`providers/` + `scripts/`): gitignored `secrets.env` (Claude/ChatGPT keys +
  loki/spartacus Ollama & LiteLLM endpoints), `models.yaml` catalog, `start-test-server.sh` /
  `agent-matrix.sh` / `stop-test-server.sh`. Matrix verified 5/5 (Claude, ChatGPT, LiteLLM→local ×2,
  direct Ollama on loki).
- **`server/3.4.0/CHANGES.md`** written (scheme reset; TaskType enum unchanged vs rc.9; A2A/cancel/
  key-trim behavior verified).

## Next: run the FULL harness against v3.4.0 — focus on last-RC → 3.4.0 diffs

The agentspan/CLI slice is done. The remaining work is the **whole-harness** pass against the
v3.4.0 stable, with special attention to what changed between the final RC of the old line and the
3.4.0 cut.

1. **Pin the diff endpoints.** "Last RC" is a moving target: the `3.32.0-rc.*` line kept advancing
   *after* 3.4.0 shipped — as of 2026-08-11 the newest is **v3.32.0-rc.25** (2026-08-10), vs 3.4.0
   (2026-08-07). Decide with the team whether the intended comparison is `3.4.0` vs the last RC
   *before* the cut (**v3.32.0-rc.24**, 2026-08-06) or vs the newest RC (**rc.25**). Default to
   **rc.24 → 3.4.0** (what actually became the stable), and note rc.25 separately.
2. **Diff the source.** In the `conductor` repo:
   `git fetch --tags && git diff v3.32.0-rc.24 v3.4.0 -- common/.../tasks/TaskType.java`
   plus the mapper/model classes. (rc.9 → 3.4.0 TaskType was unchanged; verify rc.24 → 3.4.0 too.)
   Capture new/removed task types, field renames, behavioral/breaking changes — SDK-relevant only.
3. **Build the full `server/3.4.0/` catalog.** It currently has only `CHANGES.md`. Adapt from the
   last full catalog (`server/3.32.0-rc.9/`) applying verified diffs: `capabilities.yaml`,
   `FEATURE_MATRIX.md`, `BUGS.md`, and a `kitchen-sink/` copy. Follow
   [`AGENTS.md`](AGENTS.md) → "how to add a new server version".
4. **Run the kitchen-sink battery** against a live v3.4.0 server:
   `CONDUCTOR_SERVER=http://localhost:7010 python3 server/3.4.0/kitchen-sink/run_battery.py`
   Compare pass/fail against rc.9's battery; record regressions/fixes in `server/3.4.0/BUGS.md`.
5. **(Optional) Re-run the SDK live tests** (`sdk/<lang>/.../live_test.*`) against v3.4.0 to refresh
   the SDK audit rows for the new baseline.

## Environment / pointers for resuming

- **v3.4.0 jar** cached at `.run/conductor-server-3.4.0.jar`. Bring up a wired server with
  `scripts/start-test-server.sh --port 7010`; stop with `scripts/stop-test-server.sh --port 7010`.
  (A 7010 instance may still be running from this session.)
- **Provider keys** in `providers/secrets.env` (gitignored). loki/spartacus reachable over `.local`
  (Ollama :11434, LiteLLM :4000); swap for WG/Tailscale host if `.local` won't resolve.
- **CLI** built from `conductor-cli` `main` at `conductor-cli/conductor-dev` (agentspan surface;
  the Homebrew release still lacks it).
- Branching: all work goes on a branch + PR now — do not commit to `main` directly, and don't push
  `main` without asking.

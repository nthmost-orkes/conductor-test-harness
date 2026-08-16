# Where we're leaving off (2026-08-15)

## Done this stretch — conductor-cli agentspan + v3.32.0 baseline

- **agentspan CLI audit.** `cli/agentspan/3.32.0-rc.9/` (historical) and `cli/agentspan/3.32.0/`
  (current baseline): FINDINGS, ISSUES, AGENT_CAPABILITIES, live_test.sh.
- **Bugs filed and fixed** (verified on the 3.32.0 codebase): conductor-cli **#96** (compile
  envelope), **#97** (execution `--since`/`--window`), conductor **#1437** (provider key trimming);
  the rc.9 A2A-server blocker is resolved.
- **Bugs filed, still open:** conductor-cli **#116** (stream renderer reads wrong SSE field names →
  blank `[thinking]`/`[error]`), **#117** (doctor should also report the server's
  `/api/providers/status`, not just local env).
- **AGENT/A2A capabilities live-confirmed** (see `cli/agentspan/3.32.0/AGENT_CAPABILITIES.md`):
  GET_AGENT_CARD / AGENT / CANCEL_AGENT, incl. inside FORK_JOIN and DO_WHILE.
- **Provider harness** (`providers/` + `scripts/`): gitignored `secrets.env` (Claude/ChatGPT keys +
  loki/spartacus Ollama & LiteLLM endpoints), `models.yaml` catalog, `start-test-server.sh` /
  `agent-matrix.sh` / `stop-test-server.sh`. Matrix verified **5/5** (Claude, ChatGPT/gpt-4o,
  LiteLLM→local ×2, direct Ollama on loki).
- **`server/3.32.0/CHANGES.md`** written (3.32.0 graduated from the rc line; TaskType unchanged vs
  rc.9; A2A/cancel/key-trim behavior verified).

### Versioning resolved (2026-08-15)
`v3.4.0` was **retracted** (release 404s; only the git tag lingers) — an anomalous tag, not the
mainline. The `3.32.0-rc.*` line **graduated to stable**: **v3.32.0** (08-11), **v3.32.1** (08-12,
now *Latest*), **v3.32.2** draft. The 3.4.0-labeled baselines have been **re-based to 3.32.0**
(`git mv`; the code tested as "3.4.0" is the 3.32.0 codebase, so findings carry over).

## Next: full harness against v3.32.x — the `v3.31.0 → v3.32.0` diff

The agentspan/CLI slice is done. Remaining work is the **whole-harness** pass, diffing
**stable minor → stable minor** (not RC → stable).

1. **Diff endpoints = `v3.31.0 → v3.32.0`** (last stable minor → new stable minor); track `v3.32.1`
   as the current patch. No RCs. All tags exist on origin.
2. **Diff the source.** In the `conductor` repo:
   `git fetch --tags && git diff v3.31.0 v3.32.0 -- common/.../tasks/TaskType.java`
   plus the mapper/model classes. *Large* delta — the whole agent/A2A/LLM-task/agentspan body of
   work landed across the 3.32 cycle. Capture new/removed task types, field renames,
   behavioral/breaking changes — SDK-relevant only.
3. **Build the full `server/3.32.0/` catalog** (currently only `CHANGES.md`). Adapt from the last
   full catalog (`server/3.32.0-rc.9/`) — which already captured most of the agent-family additions
   — applying the diff: `capabilities.yaml`, `FEATURE_MATRIX.md`, `BUGS.md`, `kitchen-sink/`.
   Follow [`AGENTS.md`](AGENTS.md) → "how to add a new server version".
4. **Run the kitchen-sink battery** against a live 3.32.x server
   (`scripts/start-test-server.sh --version 3.32.1 --port 7010`):
   `CONDUCTOR_SERVER=http://localhost:7010 python3 server/3.32.0/kitchen-sink/run_battery.py`
   Compare pass/fail against rc.9's battery; record regressions/fixes in `server/3.32.0/BUGS.md`.
5. **(Optional) Re-run the SDK live tests** (`sdk/<lang>/.../live_test.*`) against 3.32.x to refresh
   the SDK audit rows for the new baseline.

## Environment / pointers for resuming

- **Server jar:** `scripts/start-test-server.sh` defaults to **v3.32.1** now (downloads to `.run/`).
  Stop with `scripts/stop-test-server.sh --port 7010`. (The old `.run/conductor-server-3.4.0.jar`
  cache is stale — from the retracted tag; safe to delete.)
- **Provider keys** in `providers/secrets.env` (gitignored). loki/spartacus reachable over `.local`
  (Ollama :11434, LiteLLM :4000); swap for WG/Tailscale host if `.local` won't resolve.
- **CLI** built from `conductor-cli` `main` at `conductor-cli/conductor-dev` (agentspan surface;
  the Homebrew release still lacks it).
- Branching: all work goes on a branch + PR — no direct commits to `main`, and don't push `main`
  without asking.

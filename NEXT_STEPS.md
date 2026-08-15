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
current stable, diffing **stable minor → stable minor** (not RC → stable).

> **Versioning update (2026-08-15).** `v3.4.0` was **pulled** (its GitHub release now 404s; only
> the git tag lingers) — it was an anomalous tag, not the mainline. The `3.32.0-rc.*` line
> **graduated to stable**: **v3.32.0** (2026-08-11), **v3.32.1** (2026-08-12, now *Latest*),
> **v3.32.2** draft. So the real target is the **3.32.x** line, and the diff is clean stable-to-stable.
>
> **Action item — re-base the 3.4.0 work.** `server/3.4.0/` and `cli/agentspan/3.4.0/` are pinned to
> a retracted release. Re-label to **3.32.0** (or 3.32.1). The code we tested as "3.4.0" is
> essentially what shipped as 3.32.0 stable, so the findings carry over — only the labels are wrong.

1. **Diff endpoints = last stable minor → new stable minor: `v3.31.0 → v3.32.0`** (track `v3.32.1`
   as the current patch). No RCs. All tags exist on origin.
2. **Diff the source.** In the `conductor` repo:
   `git fetch --tags && git diff v3.31.0 v3.32.0 -- common/.../tasks/TaskType.java`
   plus the mapper/model classes. This is a *large* delta — the whole agent/A2A/LLM-task/agentspan
   body of work landed across the 3.32 cycle. Capture new/removed task types, field renames,
   behavioral/breaking changes — SDK-relevant only.
3. **Build the full `server/3.32.0/` catalog** (rename the `3.4.0` stub). Adapt from the last full
   catalog (`server/3.32.0-rc.9/`) — which already captured most of the agent-family additions —
   applying verified diffs: `capabilities.yaml`, `FEATURE_MATRIX.md`, `BUGS.md`, `kitchen-sink/`.
   Follow [`AGENTS.md`](AGENTS.md) → "how to add a new server version".
4. **Run the kitchen-sink battery** against a live 3.32.x server
   (`scripts/start-test-server.sh --version 3.32.1 --port 7010`):
   `CONDUCTOR_SERVER=http://localhost:7010 python3 server/3.32.0/kitchen-sink/run_battery.py`
   Compare pass/fail against rc.9's battery; record regressions/fixes in `server/3.32.0/BUGS.md`.
5. **(Optional) Re-run the SDK live tests** (`sdk/<lang>/.../live_test.*`) against 3.32.x to refresh
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

# Conductor OSS v3.32.0 — SDK-relevant changes

Baseline: **v3.32.0** (published 2026-08-11), the stable graduation of the `3.32.0-rc.*` line.
Current Latest patch: **v3.32.1** (2026-08-12); **v3.32.2** is a draft.
Prior full catalog: `server/3.32.0-rc.9/`.

## Versioning note

A **v3.4.0** tag briefly appeared (2026-08-07) and was marked "Latest," but it was **retracted** —
its GitHub release now 404s (only the git tag lingers). It was an anomaly, not a scheme change; the
mainline is the **3.32.x** line, where `3.32.0-rc.*` graduated to **v3.32.0** stable. Early
agentspan/A2A validation in this harness was run against the (since-pulled) 3.4.0 boot jar, which is
the same codebase as 3.32.0 stable — findings carry over.

## Task types

**No change vs `3.32.0-rc.9`.** The `TaskType` enum is identical — the AGENT family
(`AGENT`, `GET_AGENT_CARD`, `CANCEL_AGENT`) and all system tasks carry over. The
`3.32.0-rc.9/capabilities.yaml` task-type content still applies.

> **TODO (next session):** the canonical minor-to-minor diff for this baseline is
> **`v3.31.0 → v3.32.0`** (last stable minor → new stable minor — *not* RC → stable). That spans the
> whole 3.32 cycle (all the agent/A2A/LLM-task/agentspan work), so it's a large delta. Build the full
> `server/3.32.0/` catalog (`capabilities.yaml`, `FEATURE_MATRIX.md`, `BUGS.md`, `kitchen-sink/`) from
> `3.32.0-rc.9` applying that diff. See `../../NEXT_STEPS.md`.

## Behavioral changes verified (against the 3.32.0 codebase)

- **A2A server exposure registers.** With `conductor.a2a.server.enabled=true` (+
  `integrations.ai.enabled=true`), `/api/a2a/workflow` and the per-workflow
  `.well-known/agent-card.json` are served, and a full self-hosted A2A round-trip works
  (`GET_AGENT_CARD` / `AGENT` / `CANCEL_AGENT`, incl. inside `FORK_JOIN` and `DO_WHILE`).
  See `../../cli/agentspan/3.32.0/AGENT_CAPABILITIES.md`.
- **"Task cancel contract" (conductor#1342).** `CANCEL_AGENT` returns a proper A2A Task with
  `status.state=canceled`.
- **Provider API keys are trimmed at ingestion (conductor#1437).** A trailing-newline key no
  longer produces `Unexpected char 0x0a in Authorization value`.

## Related CLI fixes (conductor-cli, shipped alongside)

- `agent compile` envelope (#96), `agent execution` time filters (#97) — fixed.
- Open: stream renderer field-name mismatch (#116), doctor server-provider status (#117).

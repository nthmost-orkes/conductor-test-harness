# Conductor OSS v3.4.0 — SDK-relevant changes

Baseline: **v3.4.0** (published 2026-08-07, the current GitHub "Latest" release).
Prior harness baseline: `3.32.0-rc.9`.

## Version scheme reset

v3.4.0 is a **clean stable release under a new `3.4.x` scheme**, published *after* the
`3.32.0-rc.*` prerelease line reached `rc.24`. Numerically `3.4.0 < 3.32.0`, so this is a
scheme reset, not a `3.32 → 3.33` increment; treat the `3.32.0-rc.*` tags as the legacy line.
`conductor server start` (default `latest`) and the S3 `conductor-server-latest.jar` now
resolve to v3.4.0.

## Task types

**No change.** The `TaskType` enum is identical to `3.32.0-rc.9` — the AGENT family
(`AGENT`, `GET_AGENT_CARD`, `CANCEL_AGENT`) and all system tasks carry over. The
`3.32.0-rc.9/capabilities.yaml` task-type content still applies.

## Behavioral changes verified against v3.4.0

- **A2A server exposure now registers.** With `conductor.a2a.server.enabled=true` (+
  `integrations.ai.enabled=true`), `/api/a2a/workflow` and the per-workflow
  `.well-known/agent-card.json` are served. On the `3.32.0-rc.9` jar these 404'd under every
  config attempt (the rc.9 "BLOCKER-1"). A full self-hosted A2A round-trip now works
  (`GET_AGENT_CARD` / `AGENT` / `CANCEL_AGENT`, incl. inside `FORK_JOIN` and `DO_WHILE`).
  See `../cli/agentspan/3.4.0/AGENT_CAPABILITIES.md`.
- **"Task cancel contract" (conductor#1342).** `CANCEL_AGENT` returns a proper A2A Task with
  `status.state=canceled`.
- **Provider API keys are trimmed at ingestion (conductor#1437).** A trailing-newline key no
  longer produces `Unexpected char 0x0a in Authorization value`.

## Notes

- The changelog highlights are agent-task support + a batch of `ui-next` fixes (PRs #1329–#1346).
- Related CLI fixes shipped alongside in `conductor-cli`: `agent compile` envelope (#96) and
  `agent execution` time filters (#97).

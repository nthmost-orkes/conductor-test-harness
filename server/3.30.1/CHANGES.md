# Changes in Conductor OSS 3.30.1

## New Task Types
None

## Removed / Renamed Task Types
None

## Task Input Parameter Changes
None

## Deprecated Fields / Behaviors
None

## Behavioral Changes
None

## Breaking Changes
None

## Notes
- Patch release with no SDK-impacting changes.
- `fix(ai): rewrite thinkingTokenLimit to adaptive thinking on Claude Opus 4.7` — Claude
  Opus 4.7 removed `thinkingTokenLimit`; the AI provider now uses `budgetTokens` inside the
  `thinking` object. Affects LLM_TEXT_COMPLETE / LLM_CHAT_COMPLETE tasks targeting Anthropic
  Opus 4.7 when `thinking` mode is enabled.

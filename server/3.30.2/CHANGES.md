# Changes in Conductor OSS 3.30.2

## New Task Types
None

## Removed / Renamed Task Types
None

## Task Input Parameter Changes
None

## Deprecated Fields / Behaviors
None

## Behavioral Changes

### JavaScript execution sandbox hardened (`ScriptEvaluator.java`)

INLINE tasks, SWITCH tasks using `evaluatorType: "javascript"`, and workflow condition
expressions now run in a stricter GraalVM sandbox. The following capabilities are
explicitly **disabled** as of 3.30.2:

| Capability | Was | Now |
|------------|-----|-----|
| `load()` function | available | disabled (`js.load=false`) |
| `print()` function | available | disabled (`js.print=false`) |
| `console` object | available | disabled (`js.console=false`) |
| Host class loading | allowed | `allowHostClassLoading(false)` |
| Native library access | allowed | `allowNativeAccess(false)` |
| Thread creation | allowed | `allowCreateThread(false)` |
| Process spawning | allowed | `allowCreateProcess(false)` |
| File system I/O | allowed | `allowIO(IOAccess.NONE)` |
| Environment variable access | allowed | `allowEnvironmentAccess(EnvironmentAccess.NONE)` |

**SDK impact:** Any INLINE or SWITCH (javascript evaluator) task whose expression
uses `load()`, `print()`, `console.log()`, file I/O, process spawning, or environment
variable reads will now throw a `PolyglotException` at runtime. These were security
risks; the sandbox now prevents them.

If existing workflows depended on these capabilities, they must be refactored —
there is no configuration flag to re-enable them.

## Breaking Changes
- JavaScript expressions in INLINE/SWITCH tasks that used `load()`, `print()`,
  `console`, `System.getenv()`, file I/O, or thread/process creation **will break**.
  This affects all workflow definitions, not just SDK-built ones.

## Notes
- `GENERATE_PDF` AI task: fixed classpath conflict with `openhtmltopdf-pdfbox` on
  PDFBox 3.x; `GENERATE_PDF` was non-functional in 3.30.1 on PDFBox 3.x builds.
- MySQL deployments: `FlywayAutoConfiguration` import fix — Flyway migration beans
  were not registered in some MySQL configurations.
- MCP for Workflow (#978) was merged and immediately reverted (#1137) in this release.
  No net change to MCP task types from the MCP-for-workflow work.

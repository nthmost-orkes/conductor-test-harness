# AGENTS.md — conductor-test-harness

Guidance for AI agents working with this repository.

## What this repo is

A versioned capabilities catalog and SDK audit harness for Conductor OSS. The two
central artifacts are:

- **`server/<version>/capabilities.yaml`** — machine-readable ground truth for what
  the server supports at a given version: every task type, every persistence backend,
  every task combination that works or doesn't, every server-side capability.

- **`server/<version>/FEATURE_MATRIX.md`** — human-readable rendering of the same data.

Use these as your primary source of truth before reading server Java source. They are
derived from `TaskType.java`, mapper/executor classes, and live test results — not from
documentation or LLM inference.

---

## Using the catalog for PR review

When reviewing a PR against any Conductor SDK:

**1. Identify the server version**

Look for the Docker image tag, server URL, or explicit version string in the PR. Map it
to the closest `server/<version>/` directory here. If the PR uses `conductor:latest`,
treat it as the most recent version in this catalog until pinned.

**2. Load the relevant catalog files**

```
server/<version>/capabilities.yaml    # server-side ground truth
sdk/<lang>/<version>/STATIC_ANALYSIS.md  # known gaps for this SDK
sdk/<lang>/<version>/ISSUES.md           # issues already filed
```

**3. For any changed model or field, verify the server shape**

Check `capabilities.yaml` under `system_tasks` first. If the field is at the task
level, look for it in the relevant section. If it's a shared model (like
`onStateChange`, `StateChangeEvent`), read the corresponding Java source:

```
conductor-oss/conductor/common/src/main/java/com/netflix/conductor/common/metadata/
```

Never infer a server field name or type from SDK naming alone — the server is the spec.

**4. Cross-reference against the combination matrix**

`capabilities.yaml → task_combinations` tells you which task nesting patterns are
supported, buggy, or untested. When a PR adds support for a structural task (DO_WHILE,
FORK_JOIN, SWITCH, SUB_WORKFLOW), check whether the combinations it enables are in the
matrix and what their status is.

**5. Check the known-bugs table**

`server/<version>/BUGS.md` and the `known_bugs` section of `capabilities.yaml` list
open server-side issues. If a PR works around or is affected by a known bug, say so
explicitly in the review.

---

## Common review patterns

### SDK adds or changes a task type builder

1. Find the task type in `capabilities.yaml → system_tasks`.
2. Read `notes` for any caveats (e.g. "Must be immediately followed by a JOIN task").
3. Check `task_combinations` for any restrictions on how this type can be nested.
4. Verify the SDK's field names match the server's `inputParameters` field names
   (the Java mapper/executor class is the authoritative source; `capabilities.yaml`
   notes the most important ones).
5. Check `sdk/<lang>/<version>/STATIC_ANALYSIS.md` for any filed findings on this type.

### SDK changes a shared model class

1. Find the Java source in `conductor-oss/conductor/common/src/main/java/`.
2. Compare the server field names and types to the SDK's property names.
3. Verify JSON serialization annotation names match (e.g. `@JsonProperty("joinOn")` →
   the SDK must send the key `joinOn`, not `join_on` or `JoinOn`).

### PR claims a feature "works against OSS"

1. Check `capabilities.yaml → server_capabilities` for the feature's status.
2. If status is `not_supported`, the claim is wrong — cite the catalog.
3. If status is `partial`, note what the limitation is.
4. Features absent from OSS: `WAIT_FOR_WEBHOOK` task, `HTTP_POLL` task, HUMAN task
   assignment/form management. These are Orkes Enterprise only.

### PR adds OSS CI but excludes a test category

Check `capabilities.yaml` to verify whether the excluded feature is actually absent from
OSS or just untested. If it's in the catalog as `supported`, the exclusion should be
explained in the test with a comment (not a permanent blind exclusion).

---

## How to add a new server version

When a new Conductor OSS server version ships and needs to be cataloged:

**Step 1 — Create the version directory**

```shell
mkdir -p server/<new-version>/kitchen-sink
```

**Step 2 — Generate `capabilities.yaml`**

Use the previous version's `capabilities.yaml` as a base. Apply diffs verified from
`git tag`:

```shell
# Find what's new in TaskType.java
git -C path/to/conductor show v<new>:common/.../TaskType.java | grep -A5 "public enum"

# Diff against prior version
git -C path/to/conductor diff v<prev>..v<new> -- common/.../TaskType.java

# Check what combinations changed
git -C path/to/conductor log v<prev>..v<new> --oneline --no-merges | \
  grep -iE "do.while|fork|join|switch|terminate|sub.workflow"
```

The `scripts/build_changelogs.py` script uses LiteLLM on `loki.local:4000` to do an
initial pass on release notes; Sonnet agents then verify against source. Run it for
`CHANGES.md`, then write `capabilities.yaml` from the verified diff.

**Step 3 — Write `CHANGES.md`**

Document only SDK-relevant changes:
- New/removed `TaskType` enum values
- Task `inputParameters` field changes (added, removed, renamed, type-changed)
- Deprecated fields or behaviors
- Behavioral changes affecting how SDK-built workflows execute
- Breaking changes to workflow definition structure

**Step 4 — Update `FEATURE_MATRIX.md`**

Adapt the previous version's `FEATURE_MATRIX.md`. Update:
- Status icons for any changed combinations
- Known bugs table (add new, remove fixed)
- "Fixes landed" section

**Step 5 — Run the kitchen-sink battery**

```shell
cd server/<new-version>/kitchen-sink
python3 run_battery.py  # requires loki.local:8080 or CONDUCTOR_SERVER=...
```

Any new failures → add to `BUGS.md` and file issues. Any fixed failures → update
the combination matrix status in `capabilities.yaml`.

**Step 6 — Update `README.md`**

Add the new version to the server versions table. If it's the new working baseline,
update the baseline note at the top.

---

## What the catalog covers and doesn't

**Covered:**
- Every `TaskType` enum value and its server-side behavior
- Task combination support matrix (which nesting patterns work)
- Persistence backends (execution DAO, index DAO, scheduler DAO)
- Event sinks and external storage providers
- Server capabilities (scheduler, webhooks, secrets interpolation, A2A agents, etc.)

**Not covered:**
- REST API endpoint signatures (read `WorkflowResource.java`, `TaskResource.java`)
- Authentication/authorization (Orkes Enterprise concern)
- Multi-tenancy (`orgId` propagation — Orkes Enterprise only)
- Performance characteristics or SLAs
- SDK-specific bugs (those live in `sdk/<lang>/<version>/STATIC_ANALYSIS.md`)

---

## Key file locations

| What you need | Where to find it |
|---------------|-----------------|
| Is feature X supported? | `server/<version>/capabilities.yaml → server_capabilities` |
| Server field names for task type Y | `capabilities.yaml → system_tasks.Y.notes` + Java mapper |
| Does nesting A inside B work? | `capabilities.yaml → task_combinations.A.B` |
| Known bugs at this version | `server/<version>/BUGS.md` |
| What changed from the previous version | `server/<version>/CHANGES.md` |
| SDK gaps already filed | `sdk/<lang>/<version>/ISSUES.md` |
| Full SDK audit methodology | `SDK_ANALYSIS_PROCEDURE.md` |
| Java model source | `conductor-oss/conductor/common/src/main/java/com/netflix/conductor/common/` |
| Java executor source | `conductor-oss/conductor/core/src/main/java/.../execution/tasks/` |
| Java mapper source | `conductor-oss/conductor/core/src/main/java/.../execution/mapper/` |

---

## Ground rules

- **The server is the spec.** When the catalog and a PR's claim conflict, verify against
  Java source before deciding which is wrong. The catalog may lag a new version; the
  Java source is always correct.
- **Don't infer field names.** `dynamicForkTasksParam` and `dynamicForkJoinTasksParam`
  are different fields — one current, one deprecated. Always read the mapper to confirm
  which name the server actually reads.
- **"untested" means unknown, not safe.** A combination marked `untested` in the matrix
  has no evidence for or against. Do not describe it as supported in a review.
- **OSS vs Orkes.** When a feature is missing from OSS (`not_supported` in the catalog),
  say so. Don't soften it to "may not be available" — that obscures a real gap.

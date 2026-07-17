#!/usr/bin/env python3
"""
Back-catalog Conductor OSS CHANGES.md files from v3.30.0 to v3.32.0-rc.9.

Uses LiteLLM on loki (loki/gemma3-12b) for cheap per-version analysis of
release notes + git diffs. Writes server/<version>/CHANGES.md files.

Usage:
    python3 scripts/build_changelogs.py
    LITELLM_MODEL=spartacus/gemma3-27b python3 scripts/build_changelogs.py
"""

import os
import subprocess
import sys
import json
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LITELLM_BASE = os.getenv("LITELLM_BASE", "http://loki.local:4000")
MODEL = os.getenv("LITELLM_MODEL", "loki/gemma3-12b")
CONDUCTOR_REPO = "/Users/nthmost/projects/git/conductor-oss/conductor"
HARNESS_REPO = "/Users/nthmost/projects/git/conductor-oss/conductor-test-harness"

# Versions to process in order.  prev=None means "catalog baseline" — document
# what exists rather than diffing against a predecessor.
TARGET_VERSIONS = [
    {"version": "3.30.0",     "tag": "v3.30.0",     "prev": None},
    {"version": "3.30.1",     "tag": "v3.30.1",     "prev": "v3.30.0"},
    {"version": "3.30.2",     "tag": "v3.30.2",     "prev": "v3.30.1"},
    {"version": "3.31.0",     "tag": "v3.31.0",     "prev": "v3.30.2"},
    {"version": "3.32.0-rc.9","tag": "v3.32.0-rc.9","prev": "v3.31.0"},
]

GH_HEADERS = {}  # populated in main()

# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def fetch_release_notes(tag: str) -> str:
    url = f"https://api.github.com/repos/conductor-oss/conductor/releases/tags/{tag}"
    r = requests.get(url, headers=GH_HEADERS, timeout=30)
    if r.status_code != 200:
        return f"(release notes unavailable: HTTP {r.status_code})"
    return r.json().get("body") or "(no release body)"


def git(args: list[str], cwd: str = CONDUCTOR_REPO) -> str:
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()


def fetch_git_log(tag: str, prev: str | None, max_lines: int = 80) -> str:
    if prev:
        raw = git(["log", f"{prev}..{tag}", "--oneline", "--no-merges"])
    else:
        # For the baseline version, show the 80 most recent commits at that tag
        raw = git(["log", tag, "--oneline", "--no-merges", f"-{max_lines}"])
    lines = raw.splitlines()[:max_lines]
    return "\n".join(lines)


def fetch_diff(tag: str, prev: str | None, path: str, max_chars: int = 4000) -> str:
    if not prev:
        return "(no previous version — baseline entry)"
    raw = git(["diff", f"{prev}..{tag}", "--", path])
    return raw[:max_chars] if raw else "(no changes to this file)"


# ---------------------------------------------------------------------------
# LiteLLM analysis
# ---------------------------------------------------------------------------

BASELINE_PROMPT = """\
You are documenting Conductor OSS {version} as the starting baseline for an SDK compatibility catalog.

Given the release notes and recent commits, produce a structured CHANGES.md that inventories
the SDK-relevant features present in this version. Focus on:
- Task types available (TaskType enum values)
- Key input parameter fields for each system task
- REST API endpoints SDK authors use
- Any notable SDK behaviors or constraints

RELEASE NOTES:
{release_notes}

GIT LOG (recent commits at this tag):
{git_log}

Format your response as:
# Conductor OSS {version} — Baseline Inventory

## System Task Types
(list all TaskType values present and a one-line description of each)

## Notable SDK Behaviors
(anything SDK authors should know that isn't obvious from task names)

## REST API Baseline
(key endpoints: workflow CRUD, task polling, workflow execution)

Keep it concise — one line per item.
"""

DIFF_PROMPT = """\
You are documenting what changed in Conductor OSS {version} (relative to {prev}) for SDK authors.

SDK-relevant changes include:
- New or removed TaskType enum values
- Added/removed/renamed fields in task inputParameters
- Changed JSON field names (serialization-level)
- Deprecated fields or behaviors (even if backward-compat fallback exists)
- Changed REST endpoint paths or signatures
- Breaking changes to workflow definition structure
- New workflow/task validation rules

NOT relevant: infrastructure changes, deployment config, UI changes, build system,
performance improvements with no SDK behavioral effect, internal refactoring.

RELEASE NOTES for {version}:
{release_notes}

GIT LOG (commits between {prev} and {version}):
{git_log}

DIFF of TaskType.java:
{tasktype_diff}

DIFF of core/src/main/java/com/netflix/conductor/core/execution/tasks/ (first 2000 chars):
{tasks_diff}

Format your response as:
# Changes in Conductor OSS {version}

## New Task Types
(list new TaskType values added, or "None")

## Removed / Renamed Task Types
(list any removed or renamed values, or "None")

## Task Input Parameter Changes
(per task type: which fields were added, removed, renamed, or type-changed; or "None")

## Deprecated Fields / Behaviors
(anything SDK authors should stop using even if still working; or "None")

## Behavioral Changes
(how SDK-built workflows execute differently; or "None")

## Breaking Changes
(anything that will break existing SDK code; or "None")

## Notes
(anything else SDK authors should know; omit section if nothing)

Be concise. One line per item with enough context to understand the change.
"""


def analyze(v: dict) -> str:
    release_notes = fetch_release_notes(v["tag"])
    git_log = fetch_git_log(v["tag"], v["prev"])

    is_baseline = v["prev"] is None

    if is_baseline:
        prompt = BASELINE_PROMPT.format(
            version=v["version"],
            release_notes=release_notes[:3000],
            git_log=git_log[:2000],
        )
    else:
        tasktype_diff = fetch_diff(
            v["tag"], v["prev"],
            "common/src/main/java/com/netflix/conductor/common/metadata/tasks/TaskType.java",
        )
        tasks_diff = fetch_diff(
            v["tag"], v["prev"],
            "core/src/main/java/com/netflix/conductor/core/execution/tasks/",
            max_chars=2000,
        )
        prompt = DIFF_PROMPT.format(
            version=v["version"],
            prev=v["prev"],
            release_notes=release_notes[:3000],
            git_log=git_log[:2000],
            tasktype_diff=tasktype_diff,
            tasks_diff=tasks_diff,
        )

    print(f"  → calling {MODEL}...", flush=True)
    resp = requests.post(
        f"{LITELLM_BASE}/v1/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1800,
            "temperature": 0.1,
        },
        headers={"Authorization": "Bearer anything"},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Resolve GitHub token
    try:
        token = subprocess.check_output(
            "gh auth switch --user nthmost-orkes 2>/dev/null && gh auth token",
            shell=True, text=True, timeout=15,
        ).strip()
        GH_HEADERS["Authorization"] = f"Bearer {token}"
        GH_HEADERS["Accept"] = "application/vnd.github+json"
    except Exception as e:
        print(f"Warning: could not get GitHub token ({e}). Release notes will be limited.")

    results = {}
    for v in TARGET_VERSIONS:
        print(f"\n{'='*60}")
        print(f"Processing {v['version']} (prev: {v['prev'] or 'none — baseline'})")

        try:
            content = analyze(v)
        except Exception as e:
            print(f"  ERROR: {e}")
            content = f"# Changes in Conductor OSS {v['version']}\n\n(Analysis failed: {e})\n"

        # Write output
        outdir = os.path.join(HARNESS_REPO, "server", v["version"])
        os.makedirs(outdir, exist_ok=True)
        outfile = os.path.join(outdir, "CHANGES.md")
        with open(outfile, "w") as f:
            f.write(content + "\n")

        print(f"  ✓ written to {outfile}")
        print(content[:400])
        results[v["version"]] = outfile

    print(f"\n{'='*60}")
    print("Done. Files written:")
    for ver, path in results.items():
        print(f"  {ver}: {path}")


if __name__ == "__main__":
    main()

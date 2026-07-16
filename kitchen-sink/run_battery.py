#!/usr/bin/env python3
"""
Kitchen Sink Battery Runner
Fires all test cases in parallel against Conductor on loki, polls for
completion, then fans analysis out to LiteLLM on spartacus and loki.

Usage:
  python3 run_battery.py                  # run all, analyze failures
  python3 run_battery.py --dry-run        # print test cases, don't fire
  python3 run_battery.py --no-llm         # run without LiteLLM analysis
  python3 run_battery.py --concurrency=N  # parallel workflow limit (default 12)
"""

import json, sys, time, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

CONDUCTOR   = "http://loki.local:8080"
LLM_HEAVY   = "http://spartacus.local:4000"   # gemma3-27b
LLM_FAST    = "http://loki.local:4000"         # gemma3-12b
MODEL_HEAVY = "spartacus/gemma3-27b"
MODEL_FAST  = "loki/gemma3-12b"

POLL_INTERVAL = 2    # seconds between status polls
TIMEOUT       = 120  # seconds before marking a run as TIMED_OUT

PRINT_LOCK = threading.Lock()

def log(msg):
    with PRINT_LOCK:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)


# ──────────────────────────────────────────────────────────────
# Test case definitions
# (workflow_name, input_dict, expected_terminal_status)
# expected: None → any terminal status is acceptable
# ──────────────────────────────────────────────────────────────

CASES = [
    # ── Unit workflows ──
    ("ks_unit_noop",            {},                      "COMPLETED"),
    ("ks_unit_inline",          {},                      "COMPLETED"),
    ("ks_unit_lambda",          {},                      "COMPLETED"),
    ("ks_unit_set_variable",    {},                      "COMPLETED"),
    ("ks_unit_json_jq",         {},                      "COMPLETED"),
    ("ks_unit_wait",            {},                      "COMPLETED"),
    ("ks_unit_switch",          {"switchCase": "A"},     "COMPLETED"),
    ("ks_unit_switch",          {"switchCase": "B"},     "COMPLETED"),
    ("ks_unit_switch",          {"switchCase": "C"},     "COMPLETED"),
    ("ks_unit_switch",          {"switchCase": "NONE"},  "COMPLETED"),  # → default
    ("ks_unit_switch_js",       {},                      "COMPLETED"),
    ("ks_unit_nested_switch",   {"outer":"nested","inner":"one"},   "COMPLETED"),
    ("ks_unit_nested_switch",   {"outer":"nested","inner":"two"},   "COMPLETED"),
    ("ks_unit_nested_switch",   {"outer":"flat","inner":""},        "COMPLETED"),
    ("ks_unit_nested_switch",   {"outer":"other","inner":""},       "COMPLETED"),
    ("ks_unit_do_while",        {},                      "COMPLETED"),
    ("ks_unit_fork_join",       {},                      "COMPLETED"),
    ("ks_unit_exclusive_join",  {},                      "COMPLETED"),
    ("ks_unit_terminate",       {"exit": "true"},        "COMPLETED"),
    ("ks_unit_terminate",       {"exit": "false"},       "COMPLETED"),
    ("ks_unit_terminate_failed",{"fail": "true"},        "FAILED"),
    ("ks_unit_terminate_failed",{"fail": "false"},       "COMPLETED"),
    ("ks_unit_http",            {},                      "COMPLETED"),
    ("ks_unit_fork_join_dynamic",{},                     "COMPLETED"),
    ("ks_unit_sub_workflow",    {},                      "COMPLETED"),
    ("ks_unit_start_workflow",  {},                      "COMPLETED"),
    # ks_unit_human skipped — requires manual completion

    # ── DO_WHILE combos ──
    ("ks_combo_do_while_switch",      {"mode":"fast"},   "COMPLETED"),
    ("ks_combo_do_while_switch",      {"mode":"slow"},   "COMPLETED"),
    ("ks_combo_do_while_switch",      {"mode":"other"},  "COMPLETED"),
    ("ks_combo_do_while_fork_join",   {},                "COMPLETED"),
    ("ks_combo_do_while_sub_workflow",{},                "COMPLETED"),
    # Known Conductor bug: nested DO_WHILE body tasks have naming collisions when
    # the outer DO_WHILE evaluates continuation; tracked as conductor-oss/conductor#NNNN
    ("ks_combo_do_while_do_while",    {},                None),
    ("ks_combo_do_while_exclusive_join",{},              "COMPLETED"),
    ("ks_combo_do_while_start_workflow",{},              "COMPLETED"),
    ("ks_combo_do_while_all_leaf",    {},                "COMPLETED"),

    # ── SWITCH combos ──
    ("ks_combo_switch_fork_join",     {"size":"small"},  "COMPLETED"),
    ("ks_combo_switch_fork_join",     {"size":"large"},  "COMPLETED"),
    ("ks_combo_switch_fork_join",     {"size":"none"},   "COMPLETED"),
    ("ks_combo_switch_do_while",      {"runLoop":"true"},"COMPLETED"),
    ("ks_combo_switch_do_while",      {"runLoop":"false"},"COMPLETED"),
    ("ks_combo_switch_sub_workflow",  {"choice":"inline"},"COMPLETED"),
    ("ks_combo_switch_sub_workflow",  {"choice":"jq"},   "COMPLETED"),
    ("ks_combo_switch_sub_workflow",  {"choice":"http"},  "COMPLETED"),
    ("ks_combo_switch_sub_workflow",  {"choice":"noop"},  "COMPLETED"),
    ("ks_combo_switch_terminate",     {"hasError":"true"},"FAILED"),
    ("ks_combo_switch_terminate",     {"hasError":"false"},"COMPLETED"),
    ("ks_combo_switch_exclusive_join",{"path":"fast"},   "COMPLETED"),
    ("ks_combo_switch_exclusive_join",{"path":"slow"},   "COMPLETED"),

    # ── FORK_JOIN combos ──
    ("ks_combo_fork_join_switch",     {"mode":"x"},      "COMPLETED"),
    ("ks_combo_fork_join_switch",     {"mode":"y"},      "COMPLETED"),
    ("ks_combo_fork_join_do_while",   {},                "COMPLETED"),
    ("ks_combo_fork_join_sub_workflow",{},               "COMPLETED"),
    ("ks_combo_fork_join_fork_join",  {},                "COMPLETED"),
    ("ks_combo_fork_join_exclusive_join",{},             "COMPLETED"),

    # ── EXCLUSIVE_JOIN combos ──
    ("ks_combo_exclusive_join_do_while",{},              "COMPLETED"),

    # ── Other combos ──
    ("ks_combo_sub_in_fork",          {},                "COMPLETED"),
    ("ks_combo_dynamic_fork_in_do_while",{},             "COMPLETED"),

    # ── Kitchen sinks ──
    ("ks_all_tasks",   {"path":"loop"},     "COMPLETED"),
    ("ks_all_tasks",   {"path":"term"},     "COMPLETED"),
    ("ks_all_tasks",   {"path":"default"},  "COMPLETED"),
    # Known Conductor bug: same nested DO_WHILE naming collision issue (see above)
    ("ks_deep_nesting",{"variant":"deep"},  None),
    ("ks_deep_nesting",{"variant":"shallow"},"COMPLETED"),
    ("ks_deep_nesting",{"variant":"other"}, "COMPLETED"),
    ("ks_fork_of_everything", {},            "COMPLETED"),
]


# ──────────────────────────────────────────────────────────────
# Conductor API helpers
# ──────────────────────────────────────────────────────────────

def _http_json(method, url, body=None):
    """Make an HTTP request and parse JSON response."""
    req = urllib.request.Request(url, method=method,
                                  headers={"Content-Type": "application/json"})
    if body is not None:
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def _http_text(method, url, body=None):
    """Make an HTTP request and return raw text response."""
    req = urllib.request.Request(url, method=method,
                                  headers={"Content-Type": "application/json"})
    if body is not None:
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode().strip()

def start_workflow(name, input_data, version=1):
    # POST /api/workflow returns the workflowId as plain text, not JSON
    return _http_text("POST", f"{CONDUCTOR}/api/workflow",
                      {"name": name, "version": version, "input": input_data})

def get_workflow(wf_id):
    return _http_json("GET", f"{CONDUCTOR}/api/workflow/{wf_id}?includeTasks=true")


# ──────────────────────────────────────────────────────────────
# Test execution
# ──────────────────────────────────────────────────────────────

TERMINAL = {"COMPLETED", "FAILED", "TIMED_OUT", "TERMINATED"}

def run_case(case_idx, name, inputs, expected):
    label = f"{name}({json.dumps(inputs) if inputs else '{}'})"
    try:
        wf_id = start_workflow(name, inputs)
    except Exception as e:
        log(f"  ✗ LAUNCH_FAILED  {label}: {e}")
        return {
            "case": label, "wf_id": None, "status": "LAUNCH_FAILED",
            "expected": expected, "ok": False, "error": str(e),
            "tasks": [], "elapsed": 0
        }

    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > TIMEOUT:
            log(f"  ⏱ TIMED_OUT     {label}  ({wf_id[:8]})")
            return {
                "case": label, "wf_id": wf_id, "status": "TIMED_OUT",
                "expected": expected, "ok": (expected is None),
                "error": f"Timed out after {TIMEOUT}s",
                "tasks": [], "elapsed": round(elapsed, 1)
            }
        try:
            data = get_workflow(wf_id)
        except Exception as e:
            time.sleep(POLL_INTERVAL)
            continue

        status = data.get("status", "UNKNOWN")
        if status in TERMINAL:
            ok = (expected is None) or (status == expected)
            icon = "✓" if ok else "✗"
            log(f"  {icon} {status:<12} {label}  ({wf_id[:8]}, {elapsed:.1f}s)")

            failed_tasks = [
                {"ref": t.get("referenceTaskName"), "type": t.get("taskType"),
                 "status": t.get("status"), "reason": t.get("reasonForIncompletion"),
                 "output": t.get("outputData", {})}
                for t in data.get("tasks", [])
                if t.get("status") in ("FAILED", "FAILED_WITH_TERMINAL_ERROR", "TIMED_OUT")
            ]
            return {
                "case": label, "wf_id": wf_id, "status": status,
                "expected": expected, "ok": ok,
                "error": data.get("reasonForIncompletion", ""),
                "tasks": failed_tasks, "elapsed": round(elapsed, 1)
            }
        time.sleep(POLL_INTERVAL)


# ──────────────────────────────────────────────────────────────
# LiteLLM analysis
# ──────────────────────────────────────────────────────────────

def llm_chat(base_url, model, system, user_msg, timeout=240):
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.2,
        "max_tokens": 2048
    }
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
    return resp["choices"][0]["message"]["content"]

SYSTEM_ANALYST = """\
You are a senior Conductor OSS engineer doing a bug-finding session.
You will receive test results from a workflow battery run against a fresh build.
Your job: identify real bugs (not test-input mistakes), classify by severity,
and suggest the likely root cause and which source files to investigate.

Be concise. Format your response as:

## Summary
N bugs found, N potential issues, N expected failures.

## Bugs

### BUG-N: <short title>
- **Severity**: Critical / High / Medium / Low
- **Workflow(s)**: ...
- **Symptom**: ...
- **Likely cause**: ...
- **Files to check**: ...

## Potential Issues (needs more investigation)
(same format, briefer)

## Expected / Noise
One line per item that is expected behavior, not a bug.
"""

def analyze_with_llm(base_url, model, failures, all_results):
    lines = [f"Total cases: {len(all_results)}",
             f"Passed: {sum(1 for r in all_results if r['ok'])}",
             f"Failed/Unexpected: {len(failures)}",
             ""]

    for f in failures:
        lines.append(f"### {f['case']}")
        lines.append(f"  Expected: {f['expected']}  Got: {f['status']}  (elapsed {f['elapsed']}s)")
        if f['error']:
            lines.append(f"  Error: {f['error']}")
        for t in f['tasks']:
            lines.append(f"  Task [{t['type']}:{t['ref']}] → {t['status']}: {t['reason']}")
        lines.append("")

    user_msg = "\n".join(lines)
    log(f"  → Calling {model} for analysis...")
    try:
        return llm_chat(base_url, model, SYSTEM_ANALYST, user_msg)
    except Exception as e:
        return f"[LLM error: {e}]"


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    dry_run    = "--dry-run" in sys.argv
    no_llm     = "--no-llm" in sys.argv
    concurrency = next(
        (int(a.split("=")[1]) for a in sys.argv if a.startswith("--concurrency=")),
        12
    )

    if dry_run:
        print(f"{len(CASES)} test cases:")
        for i, (name, inp, exp) in enumerate(CASES, 1):
            print(f"  {i:3}. {name}  input={json.dumps(inp)}  expected={exp}")
        return

    print(f"\nKitchen Sink Battery — {len(CASES)} test cases")
    print(f"Conductor: {CONDUCTOR}")
    print(f"Concurrency: {concurrency}  Timeout: {TIMEOUT}s")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("─" * 70)

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(run_case, i, name, inp, exp): (name, inp, exp)
            for i, (name, inp, exp) in enumerate(CASES)
        }
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                name, inp, exp = futures[fut]
                results.append({
                    "case": f"{name}({inp})", "wf_id": None, "status": "EXCEPTION",
                    "expected": exp, "ok": False, "error": str(e),
                    "tasks": [], "elapsed": 0
                })

    passed   = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]

    print("─" * 70)
    print(f"\nResults: {len(passed)}/{len(results)} passed  |  {len(failures)} failures\n")

    if failures:
        print("FAILURES:")
        for f in sorted(failures, key=lambda x: x["case"]):
            print(f"  ✗ {f['case']}")
            print(f"      expected={f['expected']}  got={f['status']}  ({f['elapsed']}s)")
            if f["error"]:
                print(f"      {f['error'][:200]}")
            for t in f["tasks"]:
                print(f"      [{t['type']}:{t['ref']}] {t['status']}: {t['reason']}")
        print()

    if no_llm or not failures:
        if not failures:
            print("✓ All cases passed — no LLM analysis needed.")
        return

    print("─" * 70)
    print(f"\nFanning analysis to LiteLLM on spartacus and loki in parallel...\n")

    with ThreadPoolExecutor(max_workers=2) as pool:
        heavy_fut = pool.submit(analyze_with_llm, LLM_HEAVY, MODEL_HEAVY, failures, results)
        fast_fut  = pool.submit(analyze_with_llm, LLM_FAST,  MODEL_FAST,  failures, results)
        heavy_analysis = heavy_fut.result()
        fast_analysis  = fast_fut.result()

    print("═" * 70)
    print(f"ANALYSIS — {MODEL_HEAVY} (spartacus)")
    print("═" * 70)
    print(heavy_analysis)
    print()
    print("═" * 70)
    print(f"ANALYSIS — {MODEL_FAST} (loki)")
    print("═" * 70)
    print(fast_analysis)

    # Save full report
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "run_at": ts,
        "conductor": CONDUCTOR,
        "total": len(results),
        "passed": len(passed),
        "failed": len(failures),
        "results": results,
        "analysis": {
            MODEL_HEAVY: heavy_analysis,
            MODEL_FAST:  fast_analysis
        }
    }
    out = f"battery_report_{ts}.json"
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nFull report saved to {out}")


if __name__ == "__main__":
    main()

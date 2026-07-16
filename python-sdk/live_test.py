#!/usr/bin/env python3
"""
Python SDK live test — verifies that SDK-built workflow definitions register and
run correctly against a live Conductor server.

Each test case:
  1. Builds a workflow definition using ONLY the Python SDK (no raw JSON/HTTP)
  2. Registers it via PUT /api/metadata/workflow
  3. Starts it via POST /api/workflow
  4. Polls until terminal status or timeout
  5. Reports PASS / FAIL / STATIC_BUG (known static-analysis finding)

Run:
    CONDUCTOR_SERVER=http://loki.local:8080 python3 python-sdk/live_test.py

Cross-reference with static analysis findings in python-sdk/STATIC_ANALYSIS.md.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
import traceback
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

# ── SDK imports ──────────────────────────────────────────────────────────────
from conductor.client.configuration.configuration import Configuration
from conductor.client.workflow.conductor_workflow import ConductorWorkflow
from conductor.client.http.api_client import ApiClient
from conductor.client.workflow.executor.workflow_executor import WorkflowExecutor
from conductor.client.http.models.start_workflow_request import StartWorkflowRequest
from conductor.client.workflow.task.do_while_task import LoopTask
from conductor.client.workflow.task.fork_task import ForkTask
from conductor.client.workflow.task.http_task import HttpInput, HttpMethod, HttpTask
from conductor.client.workflow.task.inline import InlineTask
from conductor.client.workflow.task.join_task import JoinTask
from conductor.client.workflow.task.json_jq_task import JsonJQTask
from conductor.client.workflow.task.set_variable_task import SetVariableTask
from conductor.client.workflow.task.dynamic_fork_task import DynamicForkTask
from conductor.client.workflow.task.switch_task import SwitchTask
from conductor.client.workflow.task.task_type import TaskType
from conductor.client.workflow.task.terminate_task import TerminateTask, WorkflowStatus
from conductor.client.workflow.task.wait_task import WaitForDurationTask, WaitTask, WaitUntilTask

# ── Config ────────────────────────────────────────────────────────────────────
CONDUCTOR    = os.environ.get("CONDUCTOR_SERVER", "http://loki.local:8080")
POLL_INTERVAL = 2   # seconds
POLL_TIMEOUT  = 60  # seconds

# Build executor + api_client once — shared by all test cases
_config     = Configuration(server_api_url=f"{CONDUCTOR}/api")
_executor   = WorkflowExecutor(_config)
_api_client = ApiClient(_config)


def _sdk_serialize(obj) -> dict:
    """Convert any SDK model object to a camelCase-keyed plain dict."""
    return _api_client.sanitize_for_serialization(obj)


def new_wf(name: str, version: int = 1) -> ConductorWorkflow:
    """Create a ConductorWorkflow bound to the live server executor."""
    return ConductorWorkflow(executor=_executor, name=name, version=version)

# ── Result types ──────────────────────────────────────────────────────────────
PASS       = "PASS"
FAIL       = "FAIL"
STATIC_BUG = "STATIC_BUG"   # confirms a static-analysis finding at runtime
SKIP       = "SKIP"
ERROR      = "ERROR"


@dataclass
class Result:
    name: str
    status: str
    finding: Optional[str] = None
    detail: str = ""
    workflow_id: Optional[str] = field(default=None, repr=False)


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _http_json(method: str, url: str, body=None):
    req = urllib.request.Request(url, method=method,
                                 headers={"Content-Type": "application/json"})
    if body is not None:
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _http_text(method: str, url: str, body=None) -> str:
    req = urllib.request.Request(url, method=method,
                                 headers={"Content-Type": "application/json"})
    if body is not None:
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode().strip()


def poll_workflow(wf_id: str, timeout: int = POLL_TIMEOUT) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        wf = _http_json("GET", f"{CONDUCTOR}/api/workflow/{wf_id}?includeTasks=true")
        if wf.get("status") in ("COMPLETED", "FAILED", "TIMED_OUT", "TERMINATED"):
            return wf
        time.sleep(POLL_INTERVAL)
    return _http_json("GET", f"{CONDUCTOR}/api/workflow/{wf_id}?includeTasks=true")


def register_and_start(wf: ConductorWorkflow, inputs: dict) -> str:
    """Register and start a ConductorWorkflow via the SDK's own clients. Returns workflow ID."""
    _executor.register_workflow(overwrite=True, workflow=wf.to_workflow_def())
    req = StartWorkflowRequest(name=wf.name, version=wf.version or 1, input=inputs)
    return _executor.start_workflow(req)


def run_wf(wf: ConductorWorkflow, inputs: dict,
           timeout: int = POLL_TIMEOUT) -> tuple[str, str]:
    wf_id = register_and_start(wf, inputs)
    final = poll_workflow(wf_id, timeout)
    return final.get("status", "UNKNOWN"), wf_id


# ── Test cases ────────────────────────────────────────────────────────────────

def test_set_variable() -> Result:
    """SET_VARIABLE: store a workflow variable."""
    wf = new_wf("sdk_lt_set_variable")
    wf >> SetVariableTask("sv_ref").input_parameter("color", "${workflow.input.color}")
    status, wid = run_wf(wf, {"color": "blue"})
    return Result("set_variable", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_inline() -> Result:
    """INLINE: javascript expression doubles an input value."""
    wf = new_wf("sdk_lt_inline")
    t = InlineTask("il_ref",
                   "(function(){ return { doubled: $.x * 2 }; })()",
                   bindings={"x": "${workflow.input.x}"})
    wf >> t
    status, wid = run_wf(wf, {"x": 7})
    return Result("inline", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_jq() -> Result:
    """JSON_JQ_TRANSFORM: pluck names from a list of objects."""
    wf = new_wf("sdk_lt_jq")
    t = JsonJQTask("jq_ref", ".items | map(.name)")
    t.input_parameter("items", "${workflow.input.items}")
    wf >> t
    status, wid = run_wf(wf, {"items": [{"name": "a"}, {"name": "b"}]})
    return Result("json_jq", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_switch_value_param() -> Result:
    """SWITCH: value-param evaluator, branch A."""
    wf = new_wf("sdk_lt_switch_vp")
    sw = SwitchTask("sw_ref", "${workflow.input.branch}")
    sw.switch_case("A", [SetVariableTask("sw_a").input_parameter("branch", "A")])
    sw.switch_case("B", [SetVariableTask("sw_b").input_parameter("branch", "B")])
    wf >> sw
    status, wid = run_wf(wf, {"branch": "A"})
    return Result("switch_value_param", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_do_while_loop() -> Result:
    """DO_WHILE: LoopTask with 2 iterations."""
    wf = new_wf("sdk_lt_do_while_loop")
    body = SetVariableTask("dw_body").input_parameter("tick", "1")
    wf >> LoopTask("dw_ref", iterations=2, tasks=[body])
    status, wid = run_wf(wf, {})
    return Result("do_while_loop", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_fork_join() -> Result:
    """FORK_JOIN + JOIN: two parallel branches, SDK-built join."""
    wf = new_wf("sdk_lt_fork_join")
    branch_a = [SetVariableTask("fj_a").input_parameter("side", "A")]
    branch_b = [SetVariableTask("fj_b").input_parameter("side", "B")]
    fork = ForkTask("fj_fork", forked_tasks=[branch_a, branch_b],
                    join_on=["fj_a", "fj_b"])
    wf >> fork
    status, wid = run_wf(wf, {})
    return Result("fork_join", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_terminate() -> Result:
    """TERMINATE: workflow should end with TERMINATED status."""
    wf = new_wf("sdk_lt_terminate")
    wf >> TerminateTask("term_ref", WorkflowStatus.TERMINATED, "sdk live test")
    status, wid = run_wf(wf, {})
    return Result("terminate", PASS if status == "TERMINATED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_http() -> Result:
    """HTTP: GET the Conductor health endpoint."""
    wf = new_wf("sdk_lt_http")
    t = HttpTask("http_ref", HttpInput(
        method=HttpMethod.GET,
        uri=f"{CONDUCTOR}/health",
        accept="application/json",
    ))
    wf >> t
    status, wid = run_wf(wf, {})
    return Result("http", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_wait_for_duration() -> Result:
    """WAIT: WaitForDurationTask — sets 'duration' key (expected correct)."""
    wf = new_wf("sdk_lt_wait_duration")
    wf >> WaitForDurationTask("wfd_ref", duration_time_seconds=1)
    status, wid = run_wf(wf, {})
    return Result("wait_for_duration", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status}", workflow_id=wid)


def test_wait_until_subclass() -> Result:
    """WAIT: WaitUntilTask — sets 'until' key (expected correct)."""
    # A moment in the past so the server completes immediately
    past = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M UTC")
    wf = new_wf("sdk_lt_wait_until_sub")
    wf >> WaitUntilTask("wus_ref", date_time=past)
    status, wid = run_wf(wf, {})
    return Result("wait_until_subclass", PASS if status == "COMPLETED" else FAIL,
                  detail=f"status={status} (WaitUntilTask — correct subclass)",
                  workflow_id=wid)


def test_wait_base_class_bug() -> Result:
    """
    WAIT base class — FINDING-1 (HIGH).
    WaitTask(wait_until=...) sets key 'wait_until'; server reads 'until'.
    Expected: task never triggers → still RUNNING after 10 s → confirms bug.
    If COMPLETED: server is lenient about the key (bug may be moot).
    """
    past = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M UTC")
    wf = new_wf("sdk_lt_wait_base_bug")
    wf >> WaitTask("wbc_ref", wait_until=past)
    wf_id = register_and_start(wf, {})
    final = poll_workflow(wf_id, timeout=10)
    status = final.get("status", "UNKNOWN")
    if status == "COMPLETED":
        return Result("wait_base_class_bug", PASS,
                      detail="WaitTask base completed — 'wait_until' key accepted by server",
                      workflow_id=wf_id)
    return Result("wait_base_class_bug", STATIC_BUG,
                  finding="FINDING-1",
                  detail=f"status={status} after 10 s — 'wait_until' key ignored by server, task never triggers",
                  workflow_id=wf_id)


def test_lambda_no_builder() -> Result:
    """
    LAMBDA — FINDING-2 (CRITICAL).
    No LambdaTask builder class exists. Verified by import attempt.
    Also attempt to run a LAMBDA via raw WorkflowTask to confirm server support.
    """
    try:
        from conductor.client.workflow.task.lambda_task import LambdaTask  # noqa
        return Result("lambda_no_builder", PASS,
                      detail="LambdaTask class found — static finding may be resolved")
    except ImportError:
        pass

    # Confirm server still runs LAMBDA tasks fine (via raw dict)
    from conductor.client.http.models.workflow_task import WorkflowTask as WFTask
    lambda_t = WFTask()
    lambda_t.name = "lambda_raw"
    lambda_t.task_reference_name = "lambda_raw_ref"
    lambda_t.type = "LAMBDA"
    lambda_t.input_parameters = {
        "scriptExpression": "(function(){ return {out: $.x + 1}; })()",
        "x": "${workflow.input.x}",
    }
    wf = new_wf("sdk_lt_lambda_raw")
    wf_def = wf.to_workflow_def()
    wf_def.tasks = [lambda_t]
    _http_text("PUT", f"{CONDUCTOR}/api/metadata/workflow",
               [_sdk_serialize(wf_def)])
    wf_id = _http_text("POST", f"{CONDUCTOR}/api/workflow",
                        {"name": wf.name, "version": 1, "input": {"x": 5}})
    final = poll_workflow(wf_id)
    server_status = final.get("status", "UNKNOWN")
    return Result("lambda_no_builder", STATIC_BUG,
                  finding="FINDING-2",
                  detail=f"No LambdaTask class in SDK. Raw LAMBDA via dict: server status={server_status}",
                  workflow_id=wf_id)


def test_noop() -> Result:
    """
    NOOP — FINDING-5 (HIGH).
    TaskType.NOOP absent from SDK enum. Try running NOOP via raw WorkflowTask.
    """
    if hasattr(TaskType, "NOOP"):
        # Enum exists — try building and running
        from conductor.client.workflow.task.task import TaskInterface
        class NoopTask(TaskInterface):
            def __init__(self, ref: str):
                super().__init__(task_reference_name=ref, task_type=TaskType.NOOP)
        wf = new_wf("sdk_lt_noop")
        wf >> NoopTask("noop_ref")
        status, wid = run_wf(wf, {})
        return Result("noop", PASS if status == "COMPLETED" else FAIL,
                      detail=f"TaskType.NOOP exists; server status={status}",
                      workflow_id=wid)

    # Enum missing — verify server handles NOOP via raw dict
    from conductor.client.http.models.workflow_task import WorkflowTask as WFTask
    noop_t = WFTask()
    noop_t.name = "noop_raw"
    noop_t.task_reference_name = "noop_raw_ref"
    noop_t.type = "NOOP"
    noop_t.input_parameters = {}
    wf = new_wf("sdk_lt_noop_raw")
    wf_def = wf.to_workflow_def()
    wf_def.tasks = [noop_t]
    _http_text("PUT", f"{CONDUCTOR}/api/metadata/workflow",
               [_sdk_serialize(wf_def)])
    wf_id = _http_text("POST", f"{CONDUCTOR}/api/workflow",
                        {"name": wf.name, "version": 1, "input": {}})
    final = poll_workflow(wf_id)
    server_status = final.get("status", "UNKNOWN")
    return Result("noop", STATIC_BUG,
                  finding="FINDING-5",
                  detail=f"TaskType.NOOP absent from SDK. Raw NOOP via dict: server status={server_status}",
                  workflow_id=wf_id)


def test_dynamic_fork_deprecated_field() -> Result:
    """
    FORK_JOIN_DYNAMIC — FINDING-3 (HIGH).
    DynamicForkTask sets deprecated dynamicForkJoinTasksParam.
    Test whether the server still accepts it.
    """
    wf = new_wf("sdk_lt_dyn_fork")
    join = JoinTask("dyn_join_ref")
    fork = DynamicForkTask("dyn_fork_ref", join_task=join)
    fork.input_parameter("dynamicTasks", "${workflow.input.tasks}")
    fork.input_parameter("dynamicTasksInputs", "${workflow.input.taskInputs}")
    wf >> fork

    dyn_task = {
        "name": "sdk_lt_dyn_fork_body",
        "taskReferenceName": "dyn_body_ref",
        "type": "SET_VARIABLE",
        "inputParameters": {"x": "1"},
    }
    inputs = {"tasks": [dyn_task], "taskInputs": {"dyn_body_ref": {}}}
    try:
        status, wid = run_wf(wf, inputs)
        ok = status == "COMPLETED"
        return Result("dynamic_fork_deprecated_field",
                      PASS if ok else STATIC_BUG,
                      finding=None if ok else "FINDING-3",
                      detail=f"status={status}; deprecated dynamicForkJoinTasksParam {'accepted' if ok else 'rejected'} by server",
                      workflow_id=wid)
    except Exception as e:
        return Result("dynamic_fork_deprecated_field", FAIL, detail=f"Exception: {e}")


def test_exclusive_join_no_builder() -> Result:
    """
    EXCLUSIVE_JOIN — FINDING-4 (MEDIUM).
    No ExclusiveJoinTask builder. Build via raw WorkflowTask to test server-side.
    Also verifies TaskType.EXCLUSIVE_JOIN string is correct.
    """
    from conductor.client.http.models.workflow_task import WorkflowTask as WFTask

    wf = new_wf("sdk_lt_exclusive_join")
    sw = SwitchTask("ej_sw", "${workflow.input.branch}")
    sw.switch_case("A", [SetVariableTask("ej_a").input_parameter("x", "A")])
    sw.switch_case("B", [SetVariableTask("ej_b").input_parameter("x", "B")])
    wf >> sw

    ej = WFTask()
    ej.name = "ej_join"
    ej.task_reference_name = "ej_join_ref"
    ej.type = "EXCLUSIVE_JOIN"
    ej.join_on = ["ej_a", "ej_b"]
    ej.default_exclusive_join_task = ["ej_a"]

    wf_def = wf.to_workflow_def()
    wf_def.tasks.append(ej)
    _http_text("PUT", f"{CONDUCTOR}/api/metadata/workflow",
               [_sdk_serialize(wf_def)])
    wf_id = _http_text("POST", f"{CONDUCTOR}/api/workflow",
                        {"name": wf.name, "version": 1, "input": {"branch": "A"}})
    final = poll_workflow(wf_id)
    status = final.get("status", "UNKNOWN")
    note = "no SDK ExclusiveJoinTask builder (FINDING-4); raw WorkflowTask works"
    return Result("exclusive_join_no_builder",
                  PASS if status == "COMPLETED" else FAIL,
                  finding="FINDING-4",
                  detail=f"status={status} — {note}",
                  workflow_id=wf_id)


# ── Runner ─────────────────────────────────────────────────────────────────────
TESTS = [
    test_set_variable,
    test_inline,
    test_jq,
    test_switch_value_param,
    test_do_while_loop,
    test_fork_join,
    test_terminate,
    test_http,
    test_wait_for_duration,
    test_wait_until_subclass,
    test_wait_base_class_bug,
    test_lambda_no_builder,
    test_noop,
    test_dynamic_fork_deprecated_field,
    test_exclusive_join_no_builder,
]


def run_all() -> int:
    print(f"\nPython SDK live test  —  server: {CONDUCTOR}\n")
    print(f"{'Test':<40} {'Status':<18} Detail")
    print("-" * 100)

    results: list[Result] = []
    for test_fn in TESTS:
        name = test_fn.__name__.replace("test_", "")
        try:
            r = test_fn()
        except Exception as e:
            r = Result(name, ERROR, detail=traceback.format_exc(limit=3))
        results.append(r)
        tag = f"[{r.finding}]" if r.finding else ""
        col = f"{r.status} {tag}".strip()
        print(f"  {r.name:<38} {col:<18} {r.detail[:55]}")

    print("\n" + "=" * 100)
    counts = {s: sum(1 for r in results if r.status == s)
              for s in [PASS, FAIL, STATIC_BUG, SKIP, ERROR]}
    total = len(results)
    print(f"  {counts[PASS]}/{total} PASS  |  "
          f"{counts[FAIL]} FAIL  |  "
          f"{counts[STATIC_BUG]} STATIC_BUG confirmed  |  "
          f"{counts[ERROR]} ERROR\n")

    issues = [r for r in results if r.status in (STATIC_BUG, FAIL, ERROR)]
    if issues:
        print("Issues:")
        for r in issues:
            tag = f" [{r.finding}]" if r.finding else ""
            print(f"  {r.status}{tag}: {r.name}")
            print(f"    {r.detail}")
            if r.workflow_id:
                print(f"    {CONDUCTOR}/api/workflow/{r.workflow_id}")
        print()

    return counts[FAIL] + counts[ERROR]


if __name__ == "__main__":
    sys.exit(run_all())

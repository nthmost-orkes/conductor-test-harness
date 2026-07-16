#!/usr/bin/env python3
"""
Kitchen Sink Workflow Battery — Generator & Registrar
Produces workflow definitions that exercise every system task type and every
pairwise/triple nesting of the structural control-flow tasks:
  DO_WHILE, SWITCH, FORK_JOIN, FORK_JOIN_DYNAMIC, EXCLUSIVE_JOIN,
  SUB_WORKFLOW, START_WORKFLOW, TERMINATE
Leaf tasks used: NOOP, INLINE, LAMBDA, SET_VARIABLE, JSON_JQ_TRANSFORM, WAIT, HTTP, HUMAN

Duration format (NOT ISO-8601): "1s", "2m", "1h", "1d 2h 30m 5s"

Usage:
  python3 generate_and_register.py              # register to loki.local:8080
  python3 generate_and_register.py --url=http://localhost:8080
  python3 generate_and_register.py --dry-run    # dump JSON to stdout
  python3 generate_and_register.py --list       # list workflow names only
"""

import json, sys, urllib.request, urllib.error

CONDUCTOR_URL = "http://loki.local:8080"


# ──────────────────────────────────────────────────────────────
# Task helpers — produce minimal valid task dicts
# NOTE: taskReferenceName == ref parameter (used in ${ref.output.*})
# ──────────────────────────────────────────────────────────────

def _task(name, ref, type_, ip=None, **extra):
    t = {"name": name, "taskReferenceName": ref, "type": type_,
         "inputParameters": ip or {}}
    t.update(extra)
    return t

def noop(ref):
    return _task(f"ks_noop_{ref}", ref, "NOOP")

def inline(ref, expr, **bindings):
    """INLINE javascript task. bindings become top-level variables in the JS context."""
    ip = {"expression": expr, "evaluatorType": "javascript"}
    ip.update(bindings)
    return _task(f"ks_inline_{ref}", ref, "INLINE", ip)

def lambda_(ref, script):
    """LAMBDA (deprecated) — scriptExpression uses 'return' syntax."""
    return _task(f"ks_lambda_{ref}", ref, "LAMBDA",
                 {"scriptExpression": script})

def set_variable(ref, **vars_):
    return _task(f"ks_sv_{ref}", ref, "SET_VARIABLE", dict(vars_))

def jq(ref, query, **ip):
    """JSON_JQ_TRANSFORM. Query is applied to all inputParameters as root."""
    ip["queryExpression"] = query
    return _task(f"ks_jq_{ref}", ref, "JSON_JQ_TRANSFORM", ip)

def wait(ref, duration=None):
    """WAIT. duration format: '1s', '2m', '1h 30m'. Omit for manual wait."""
    ip = {"duration": duration} if duration else {}
    return _task(f"ks_wait_{ref}", ref, "WAIT", ip)

def http_get(ref, uri):
    return _task(f"ks_http_{ref}", ref, "HTTP",
                 {"http_request": {"uri": uri, "method": "GET",
                                    "connectionTimeOut": 3000, "readTimeOut": 5000}})

def terminate(ref, status="COMPLETED", reason=""):
    return _task(f"ks_term_{ref}", ref, "TERMINATE",
                 {"terminationStatus": status, "terminationReason": reason})

def sub_wf(ref, name, version=1, ip=None):
    return _task(f"ks_sub_{ref}", ref, "SUB_WORKFLOW",
                 ip or {}, subWorkflowParam={"name": name, "version": version})

def start_wf(ref, name, version=1, wf_input=None):
    return _task(f"ks_start_{ref}", ref, "START_WORKFLOW",
                 {"startWorkflow": {"name": name, "version": version,
                                     "input": wf_input or {}}})

def human(ref):
    return _task(f"ks_human_{ref}", ref, "HUMAN", {})

def switch(ref, case_ip, cases, default=None):
    """value-param SWITCH. case_ip must include {"case": ...} key."""
    return {
        "name": f"ks_switch_{ref}", "taskReferenceName": ref,
        "type": "SWITCH", "evaluatorType": "value-param", "expression": "case",
        "inputParameters": case_ip,
        "decisionCases": cases, "defaultCase": default or []
    }

def switch_js(ref, expr, ip, cases, default=None):
    """JavaScript-evaluator SWITCH. expr must be a constant or use only literals."""
    return {
        "name": f"ks_swjs_{ref}", "taskReferenceName": ref,
        "type": "SWITCH", "evaluatorType": "javascript", "expression": expr,
        "inputParameters": ip,
        "decisionCases": cases, "defaultCase": default or []
    }

def do_while(ref, max_iter, loop_over):
    """Loop exactly max_iter times. Condition: iteration < max_iter."""
    return {
        "name": f"ks_dw_{ref}", "taskReferenceName": ref,
        "type": "DO_WHILE",
        "inputParameters": {"maxIter": max_iter},
        "loopCondition":
            f"if ($.{ref}['iteration'] < $.maxIter) {{ true; }} else {{ false; }}",
        "loopOver": loop_over
    }

def fork(ref, branches):
    """FORK_JOIN. ref is this fork's taskReferenceName — must differ from join's."""
    return {"name": f"ks_fork_{ref}", "taskReferenceName": ref,
            "type": "FORK_JOIN", "forkTasks": branches, "inputParameters": {}}

def join(ref, join_on):
    """JOIN. ref must differ from the paired fork's ref."""
    return {"name": f"ks_join_{ref}", "taskReferenceName": ref,
            "type": "JOIN", "joinOn": join_on, "inputParameters": {}}

def exclusive_join(ref, join_on, defaults=None):
    return {"name": f"ks_excl_{ref}", "taskReferenceName": ref,
            "type": "EXCLUSIVE_JOIN", "joinOn": join_on,
            "defaultExclusiveJoinTask": defaults or []}

def dynamic_fork(ref, tasks_expr, inputs_expr):
    """FORK_JOIN_DYNAMIC. ref must differ from the paired dynamic_join's ref."""
    return {"name": f"ks_dynfork_{ref}", "taskReferenceName": ref,
            "type": "FORK_JOIN_DYNAMIC",
            "dynamicForkTasksParam": "dynamicTasks",
            "dynamicForkTasksInputParamName": "dynamicTasksInput",
            "inputParameters": {"dynamicTasks": tasks_expr,
                                 "dynamicTasksInput": inputs_expr}}

def dynamic_join(ref):
    return {"name": f"ks_dynjoin_{ref}", "taskReferenceName": ref,
            "type": "JOIN", "joinOn": [], "inputParameters": {}}

def wf(name, desc, tasks, inputs=None, outputs=None):
    return {
        "name": name, "description": desc, "version": 1,
        "tasks": tasks,
        "inputParameters": inputs or [],
        "outputParameters": outputs or {},
        "schemaVersion": 2,
        "restartable": True, "workflowStatusListenerEnabled": False,
        "timeoutPolicy": "ALERT_ONLY", "timeoutSeconds": 0,
        "ownerEmail": "test@conductor-oss.org"
    }


# ──────────────────────────────────────────────────────────────
# UNIT WORKFLOWS — one task type each, no external services
# ──────────────────────────────────────────────────────────────

def unit_noop():
    return wf("ks_unit_noop", "[KS] Unit: NOOP",
               [noop("u1")])

def unit_inline():
    return wf("ks_unit_inline", "[KS] Unit: INLINE javascript",
               [inline("u1", "(function(){ var x=6*7; return {result:x,sq:x*x}; })()")])

def unit_lambda():
    return wf("ks_unit_lambda", "[KS] Unit: LAMBDA scriptExpression (deprecated)",
               [lambda_("u1", "return {msg:'lambda ok', value: 2+2}")])

def unit_set_variable():
    return wf("ks_unit_set_variable", "[KS] Unit: SET_VARIABLE",
               [
                   set_variable("u1", counter=0, tag="ks-test"),
                   # Read back via ${workflow.variables.*} — passed as bindings to inline
                   inline("u2", "(function(){ return {counter:counter,tag:tag}; })()",
                          counter="${workflow.variables.counter}",
                          tag="${workflow.variables.tag}")
               ])

def unit_json_jq():
    # ref "u1" → taskReferenceName "u1"; reference as ${u1.output.result}
    return wf("ks_unit_json_jq", "[KS] Unit: JSON_JQ_TRANSFORM chained queries",
               [
                   jq("u1", ".nums | map(. * 2)", nums=[1, 2, 3, 4, 5]),
                   jq("u2", ".doubled | add",
                      doubled="${u1.output.result}"),          # taskRef u1, not name
               ])

def unit_wait():
    return wf("ks_unit_wait", "[KS] Unit: WAIT timed 1 second",
               [wait("u1", "1s")])                             # NOT "PT1S"

def unit_switch_value_param():
    return wf("ks_unit_switch", "[KS] Unit: SWITCH value-param 3 cases + default",
               [
                   switch("u1", {"case": "${workflow.input.switchCase}"},
                          {
                              "A": [inline("sw_a", "(function(){ return {branch:'A'}; })()")],
                              "B": [inline("sw_b", "(function(){ return {branch:'B'}; })()")],
                              "C": [inline("sw_c", "(function(){ return {branch:'C'}; })()")]
                          },
                          default=[inline("sw_def", "(function(){ return {branch:'default'}; })()")])
               ],
               inputs=["switchCase"])

def unit_switch_js():
    # JS evaluator: expression is validated at registration time — must not
    # reference unbound variables. We test with a pure-literal expression.
    return wf("ks_unit_switch_js", "[KS] Unit: SWITCH javascript evaluator (constant expr)",
               [
                   switch_js("u1",
                              "'big'",    # constant — always hits 'big' case
                              {},
                              {
                                  "big":   [inline("swjs_big",   "(function(){ return {size:'big'}; })()")],
                                  "small": [inline("swjs_small", "(function(){ return {size:'small'}; })()")]
                              },
                              default=[inline("swjs_def", "(function(){ return {size:'default'}; })()")])
               ])

def unit_nested_switch():
    return wf("ks_unit_nested_switch", "[KS] Unit: SWITCH inside SWITCH",
               [
                   switch("outer", {"case": "${workflow.input.outer}"},
                          {
                              "nested": [
                                  switch("inner", {"case": "${workflow.input.inner}"},
                                         {
                                             "one": [inline("ns_one", "(function(){ return {path:'outer.nested.one'}; })()")],
                                             "two": [inline("ns_two", "(function(){ return {path:'outer.nested.two'}; })()")]
                                         },
                                         default=[inline("ns_def", "(function(){ return {path:'outer.nested.default'}; })()")])
                              ],
                              "flat": [inline("ns_flat", "(function(){ return {path:'flat'}; })()")]
                          },
                          default=[inline("ns_outer_def", "(function(){ return {path:'outer.default'}; })()")])
               ],
               inputs=["outer", "inner"])

def unit_do_while():
    # DO_WHILE taskRef is "u1"; reference its iteration as ${u1.output.iteration}
    return wf("ks_unit_do_while", "[KS] Unit: DO_WHILE 3 iterations",
               [
                   do_while("u1", 3, [
                       inline("dw_body", "(function(){ return {iter: iter}; })()",
                              iter="${u1.output.iteration}")    # taskRef u1, not name
                   ])
               ])

def unit_fork_join():
    # fork and join MUST have different taskReferenceNames
    return wf("ks_unit_fork_join", "[KS] Unit: FORK_JOIN 3 parallel branches",
               [
                   fork("fj_f", [                              # ref = fj_f
                       [inline("fj_a", "(function(){ return {branch:'A',val:1}; })()")],
                       [inline("fj_b", "(function(){ return {branch:'B',val:2}; })()")],
                       [inline("fj_c", "(function(){ return {branch:'C',val:3}; })()")]
                   ]),
                   join("fj_j", ["fj_a", "fj_b", "fj_c"])     # ref = fj_j ≠ fj_f
               ])

def unit_exclusive_join():
    # fork ref ≠ exclusive_join ref
    return wf("ks_unit_exclusive_join", "[KS] Unit: EXCLUSIVE_JOIN fast-path wins",
               [
                   fork("ej_f", [                              # ref = ej_f
                       [inline("ej_fast", "(function(){ return {path:'fast'}; })()")],
                       [wait("ej_slow_w", "2s"),               # "2s" not "PT2S"
                        inline("ej_slow", "(function(){ return {path:'slow'}; })()")]
                   ]),
                   exclusive_join("ej1",                       # ref = ej1 ≠ ej_f
                                   ["ej_fast", "ej_slow"],
                                   defaults=["ej_fast", "ej_slow"])
               ])

def unit_terminate():
    return wf("ks_unit_terminate", "[KS] Unit: TERMINATE COMPLETED on flag",
               [
                   switch("term_sw", {"case": "${workflow.input.exit}"},
                          {"true": [terminate("t_ok", "COMPLETED", "Early exit")]},
                          default=[inline("t_cont", "(function(){ return {continued:true}; })()")])
               ],
               inputs=["exit"])

def unit_terminate_failed():
    return wf("ks_unit_terminate_failed", "[KS] Unit: TERMINATE FAILED on flag",
               [
                   switch("tfail_sw", {"case": "${workflow.input.fail}"},
                          {"true": [terminate("t_fail", "FAILED", "Forced failure")]},
                          default=[inline("t_pass", "(function(){ return {failed:false}; })()")])
               ],
               inputs=["fail"])

def unit_http():
    return wf("ks_unit_http", "[KS] Unit: HTTP GET conductor /api/version",
               [http_get("u1", "http://localhost:8080/api/version")])

def unit_sub_workflow():
    return wf("ks_unit_sub_workflow", "[KS] Unit: SUB_WORKFLOW call ks_unit_inline",
               [sub_wf("u1", "ks_unit_inline")])

def unit_start_workflow():
    return wf("ks_unit_start_workflow", "[KS] Unit: START_WORKFLOW fire-and-forget",
               [
                   start_wf("u1", "ks_unit_noop"),
                   inline("sw_after", "(function(){ return {fired:true}; })()")
               ])

def unit_human():
    return wf("ks_unit_human", "[KS] Unit: HUMAN manual-approval gate",
               [human("u1")])

def unit_fork_join_dynamic():
    """LAMBDA generates the dynamic task list; FORK_JOIN_DYNAMIC runs them.
    fork ref ≠ join ref."""
    gen = lambda_("dyn_gen",
        "return {"
        "  dynamicTasks: ["
        "    {name:'ks_dynA',taskReferenceName:'ks_dynA',type:'INLINE',"
        "     inputParameters:{expression:'(function(){return {r:1};})()',evaluatorType:'javascript'}},"
        "    {name:'ks_dynB',taskReferenceName:'ks_dynB',type:'INLINE',"
        "     inputParameters:{expression:'(function(){return {r:2};})()',evaluatorType:'javascript'}}"
        "  ],"
        "  dynamicTasksInput:{ks_dynA:{},ks_dynB:{}}"
        "}")
    return wf("ks_unit_fork_join_dynamic",
               "[KS] Unit: FORK_JOIN_DYNAMIC LAMBDA-generated tasks",
               [
                   gen,
                   dynamic_fork("u1_f",                        # ref = u1_f
                                 "${dyn_gen.output.result.dynamicTasks}",
                                 "${dyn_gen.output.result.dynamicTasksInput}"),
                   dynamic_join("u1_j")                        # ref = u1_j ≠ u1_f
               ])


# ──────────────────────────────────────────────────────────────
# COMBINATION WORKFLOWS — every structural-task pair nested
# ──────────────────────────────────────────────────────────────

# ── DO_WHILE as outer ──────────────────────────────────────────

def combo_do_while_switch():
    return wf("ks_combo_do_while_switch",
               "[KS] Combo: DO_WHILE → SWITCH each iteration",
               [
                   do_while("dws", 3, [
                       switch("dws_sw", {"case": "${workflow.input.mode}"},
                              {
                                  "fast": [inline("dws_fast", "(function(){ return {mode:'fast'}; })()")],
                                  "slow": [inline("dws_slow", "(function(){ return {mode:'slow'}; })()")]
                              },
                              default=[noop("dws_noop")])
                   ])
               ],
               inputs=["mode"])

def combo_do_while_fork_join():
    return wf("ks_combo_do_while_fork_join",
               "[KS] Combo: DO_WHILE → FORK_JOIN each iteration",
               [
                   do_while("dwfj", 2, [
                       fork("dwfj_f", [
                           [inline("dwfj_a", "(function(){ return {b:'A'}; })()")],
                           [inline("dwfj_b", "(function(){ return {b:'B'}; })()")]
                       ]),
                       join("dwfj_j", ["dwfj_a", "dwfj_b"])
                   ])
               ])

def combo_do_while_sub_workflow():
    return wf("ks_combo_do_while_sub_workflow",
               "[KS] Combo: DO_WHILE → SUB_WORKFLOW each iteration",
               [do_while("dwsub", 3, [sub_wf("dwsub_call", "ks_unit_inline")])])

def combo_do_while_do_while():
    return wf("ks_combo_do_while_do_while",
               "[KS] Combo: DO_WHILE inside DO_WHILE — nested loops",
               [
                   do_while("dwdw_outer", 2, [
                       do_while("dwdw_inner", 2, [
                           inline("dwdw_body", "(function(){ return {nested:true}; })()")
                       ])
                   ])
               ])

def combo_do_while_exclusive_join():
    return wf("ks_combo_do_while_exclusive_join",
               "[KS] Combo: DO_WHILE → FORK + EXCLUSIVE_JOIN each iteration",
               [
                   do_while("dwej", 2, [
                       fork("dwej_f", [
                           [inline("dwej_fast", "(function(){ return {p:'fast'}; })()")],
                           [wait("dwej_slow_w", "1s"),
                            inline("dwej_slow", "(function(){ return {p:'slow'}; })()")]
                       ]),
                       exclusive_join("dwej_ej", ["dwej_fast", "dwej_slow"],
                                       defaults=["dwej_fast"])
                   ])
               ])

def combo_do_while_start_workflow():
    return wf("ks_combo_do_while_start_workflow",
               "[KS] Combo: DO_WHILE fires START_WORKFLOW each iteration",
               [
                   do_while("dwst", 3, [
                       start_wf("dwst_fire", "ks_unit_noop"),
                       inline("dwst_after", "(function(){ return {fired:true}; })()")
                   ])
               ])

def combo_do_while_all_leaf():
    """DO_WHILE running LAMBDA + JQ + INLINE + SET_VARIABLE + HTTP each iteration."""
    return wf("ks_combo_do_while_all_leaf",
               "[KS] Combo: DO_WHILE → LAMBDA+JQ+INLINE+SET_VARIABLE+HTTP each iter",
               [
                   do_while("dal", 2, [
                       lambda_("dal_lam",
                               "return {msg:'iter ok', value: 7}"),
                       # dal_lam taskRef = "dal_lam"; reference as ${dal_lam.output.result.*}
                       jq("dal_jq", "{ tripled: (.value * 3) }",
                          value="${dal_lam.output.result.value}"),
                       # dal_jq taskRef = "dal_jq"; reference as ${dal_jq.output.result}
                       inline("dal_inline",
                              "(function(){ return {combined: combined}; })()",
                              combined="${dal_jq.output.result}"),
                       set_variable("dal_sv", lastIter="${dal.output.iteration}"),
                       http_get("dal_http", "http://localhost:8080/api/version")
                   ])
               ])

# ── SWITCH as outer ────────────────────────────────────────────

def combo_switch_fork_join():
    return wf("ks_combo_switch_fork_join",
               "[KS] Combo: SWITCH → different FORK_JOIN per case",
               [
                   switch("sfj_sw", {"case": "${workflow.input.size}"},
                          {
                              "small": [
                                  fork("sfj_sm_f", [
                                      [inline("sfj_sm_a", "(function(){ return {s:'a'}; })()")],
                                      [inline("sfj_sm_b", "(function(){ return {s:'b'}; })()")]
                                  ]),
                                  join("sfj_sm_j", ["sfj_sm_a", "sfj_sm_b"])
                              ],
                              "large": [
                                  fork("sfj_lg_f", [
                                      [inline("sfj_lg_a", "(function(){ return {l:'a'}; })()")],
                                      [inline("sfj_lg_b", "(function(){ return {l:'b'}; })()")],
                                      [inline("sfj_lg_c", "(function(){ return {l:'c'}; })()")]
                                  ]),
                                  join("sfj_lg_j", ["sfj_lg_a", "sfj_lg_b", "sfj_lg_c"])
                              ]
                          },
                          default=[noop("sfj_none")])
               ],
               inputs=["size"])

def combo_switch_do_while():
    # DO_WHILE taskRef = "sdw_loop"; reference as ${sdw_loop.output.iteration}
    return wf("ks_combo_switch_do_while",
               "[KS] Combo: SWITCH → DO_WHILE only when selected",
               [
                   switch("sdw_sw", {"case": "${workflow.input.runLoop}"},
                          {
                              "true": [
                                  do_while("sdw_loop", 3, [
                                      inline("sdw_body", "(function(){ return {step:step}; })()",
                                             step="${sdw_loop.output.iteration}")
                                  ])
                              ]
                          },
                          default=[inline("sdw_skip", "(function(){ return {looped:false}; })()")])
               ],
               inputs=["runLoop"])

def combo_switch_sub_workflow():
    return wf("ks_combo_switch_sub_workflow",
               "[KS] Combo: SWITCH → SUB_WORKFLOW dispatch by case",
               [
                   switch("ssub_sw", {"case": "${workflow.input.choice}"},
                          {
                              "inline": [sub_wf("ssub_inline", "ks_unit_inline")],
                              "jq":     [sub_wf("ssub_jq",     "ks_unit_json_jq")],
                              "http":   [sub_wf("ssub_http",   "ks_unit_http")]
                          },
                          default=[sub_wf("ssub_noop", "ks_unit_noop")])
               ],
               inputs=["choice"])

def combo_switch_terminate():
    return wf("ks_combo_switch_terminate",
               "[KS] Combo: SWITCH → TERMINATE on error path",
               [
                   switch("st_sw", {"case": "${workflow.input.hasError}"},
                          {"true": [terminate("st_fail", "FAILED", "Input error")]},
                          default=[inline("st_ok", "(function(){ return {ok:true}; })()")])
               ],
               inputs=["hasError"])

def combo_switch_exclusive_join():
    return wf("ks_combo_switch_exclusive_join",
               "[KS] Combo: SWITCH selects path, EXCLUSIVE_JOIN takes first done",
               [
                   fork("sej_fork", [
                       [
                           switch("sej_sw", {"case": "${workflow.input.path}"},
                                  {
                                      "fast": [inline("sej_f_fast", "(function(){ return {p:'fast'}; })()")],
                                  },
                                  default=[wait("sej_f_slow_w", "2s"),
                                           inline("sej_f_slow", "(function(){ return {p:'slow'}; })()")])
                       ],
                       [inline("sej_instant", "(function(){ return {p:'instant'}; })()")]
                   ]),
                   exclusive_join("sej_ej", ["sej_sw", "sej_instant"],
                                   defaults=["sej_instant"])
               ],
               inputs=["path"])

# ── FORK_JOIN as outer ─────────────────────────────────────────

def combo_fork_join_switch():
    return wf("ks_combo_fork_join_switch",
               "[KS] Combo: FORK_JOIN → SWITCH in each branch",
               [
                   fork("fjs_f", [
                       [
                           switch("fjs_sw_a", {"case": "${workflow.input.mode}"},
                                  {"x": [inline("fjs_ax", "(function(){ return {b:1,c:'x'}; })()")]},
                                  default=[inline("fjs_ad", "(function(){ return {b:1,c:'def'}; })()")])
                       ],
                       [
                           switch("fjs_sw_b", {"case": "${workflow.input.mode}"},
                                  {"x": [inline("fjs_bx", "(function(){ return {b:2,c:'x'}; })()")]},
                                  default=[inline("fjs_bd", "(function(){ return {b:2,c:'def'}; })()")])
                       ]
                   ]),
                   join("fjs_j", ["fjs_sw_a", "fjs_sw_b"])
               ],
               inputs=["mode"])

def combo_fork_join_do_while():
    return wf("ks_combo_fork_join_do_while",
               "[KS] Combo: FORK_JOIN → DO_WHILE in each branch (parallel loops)",
               [
                   fork("fjdw_f", [
                       [do_while("fjdw_la", 2,
                                  [inline("fjdw_la_b", "(function(){ return {branch:'A'}; })()")])],
                       [do_while("fjdw_lb", 3,
                                  [inline("fjdw_lb_b", "(function(){ return {branch:'B'}; })()")])],
                   ]),
                   join("fjdw_j", ["fjdw_la", "fjdw_lb"])
               ])

def combo_fork_join_sub_workflow():
    return wf("ks_combo_fork_join_sub_workflow",
               "[KS] Combo: FORK_JOIN → SUB_WORKFLOW in each branch",
               [
                   fork("fjsub_f", [
                       [sub_wf("fjsub_a", "ks_unit_inline")],
                       [sub_wf("fjsub_b", "ks_unit_json_jq")],
                       [sub_wf("fjsub_c", "ks_unit_noop")]
                   ]),
                   join("fjsub_j", ["fjsub_a", "fjsub_b", "fjsub_c"])
               ])

def combo_fork_join_fork_join():
    """Nested FORK_JOIN — inner fork inside one branch of outer fork."""
    return wf("ks_combo_fork_join_fork_join",
               "[KS] Combo: FORK_JOIN inside FORK_JOIN (nested parallelism)",
               [
                   fork("nfj_outer_f", [
                       [
                           fork("nfj_inner_f", [
                               [inline("nfj_ia", "(function(){ return {level:'inner',b:'A'}; })()")],
                               [inline("nfj_ib", "(function(){ return {level:'inner',b:'B'}; })()")]
                           ]),
                           join("nfj_inner_j", ["nfj_ia", "nfj_ib"])
                       ],
                       [inline("nfj_outer_b", "(function(){ return {level:'outer',b:'B'}; })()")]
                   ]),
                   join("nfj_outer_j", ["nfj_inner_j", "nfj_outer_b"])
               ])

def combo_fork_join_exclusive_join():
    """FORK_JOIN where branch A completes quickly; EXCLUSIVE_JOIN races them."""
    return wf("ks_combo_fork_join_exclusive_join",
               "[KS] Combo: FORK_JOIN branches race into EXCLUSIVE_JOIN",
               [
                   fork("fjej_f", [
                       [inline("fjej_fast", "(function(){ return {p:'fast'}; })()")],
                       [wait("fjej_slow_w", "2s"),
                        inline("fjej_slow", "(function(){ return {p:'slow'}; })()")]
                   ]),
                   exclusive_join("fjej_ej", ["fjej_fast", "fjej_slow"],
                                   defaults=["fjej_fast", "fjej_slow"])
               ])

# ── EXCLUSIVE_JOIN combinations ────────────────────────────────

def combo_exclusive_join_do_while():
    """EXCLUSIVE_JOIN on two branches each with a loop — takes whichever ends first."""
    return wf("ks_combo_exclusive_join_do_while",
               "[KS] Combo: EXCLUSIVE_JOIN on two DO_WHILE branches",
               [
                   fork("ejdw_f", [
                       [do_while("ejdw_la", 1, [inline("ejdw_la_b", "(function(){ return {b:'A'}; })()")])],
                       [do_while("ejdw_lb", 3, [inline("ejdw_lb_b", "(function(){ return {b:'B'}; })()")])],
                   ]),
                   exclusive_join("ejdw_ej", ["ejdw_la", "ejdw_lb"],
                                   defaults=["ejdw_la", "ejdw_lb"])
               ])

# ── SUB_WORKFLOW combinations ──────────────────────────────────

def combo_sub_workflow_in_fork_join():
    return wf("ks_combo_sub_in_fork",
               "[KS] Combo: SUB_WORKFLOW + INLINE racing in FORK_JOIN",
               [
                   fork("subfk_f", [
                       [sub_wf("subfk_sub", "ks_unit_inline")],
                       [inline("subfk_inline", "(function(){ return {direct:true}; })()")]
                   ]),
                   join("subfk_j", ["subfk_sub", "subfk_inline"])
               ])

# ── Dynamic fork combinations ──────────────────────────────────

def combo_dynamic_fork_in_do_while():
    """DO_WHILE → FORK_JOIN_DYNAMIC each iteration (LAMBDA generates tasks)."""
    gen = lambda_("dynloop_gen",
        "return {"
        "  dynamicTasks: ["
        "    {name:'ks_dldyn_a',taskReferenceName:'ks_dldyn_a',type:'INLINE',"
        "     inputParameters:{expression:'(function(){return {r:1};})()',evaluatorType:'javascript'}},"
        "    {name:'ks_dldyn_b',taskReferenceName:'ks_dldyn_b',type:'INLINE',"
        "     inputParameters:{expression:'(function(){return {r:2};})()',evaluatorType:'javascript'}}"
        "  ],"
        "  dynamicTasksInput:{ks_dldyn_a:{},ks_dldyn_b:{}}"
        "}")
    return wf("ks_combo_dynamic_fork_in_do_while",
               "[KS] Combo: DO_WHILE → FORK_JOIN_DYNAMIC each iteration",
               [
                   do_while("dynloop", 2, [
                       gen,
                       # dynloop_gen taskRef = "dynloop_gen"
                       dynamic_fork("dynloop_df",
                                     "${dynloop_gen.output.result.dynamicTasks}",
                                     "${dynloop_gen.output.result.dynamicTasksInput}"),
                       dynamic_join("dynloop_dj")
                   ])
               ])


# ──────────────────────────────────────────────────────────────
# KITCHEN SINK WORKFLOWS
# ──────────────────────────────────────────────────────────────

def kitchen_sink_all_tasks():
    """One workflow exercising every self-contained system task type."""
    # Phase 1 — sequential leaf tasks
    phase1 = [
        noop("ks_all_noop"),
        inline("ks_all_inline", "(function(){ return {x:6*7}; })()"),
        lambda_("ks_all_lam", "return {y:'lambda result'}"),
        set_variable("ks_all_sv", counter=0, tag="ks"),
        jq("ks_all_jq", ".ns | map(. * 3)", ns=[1, 2, 3]),
        http_get("ks_all_http", "http://localhost:8080/api/version"),
        wait("ks_all_wait", "1s"),
    ]
    # Phase 2 — parallel fan-out (fork ref ≠ join ref)
    f1 = fork("ks_all_f1", [
        [inline("ks_all_f1a", "(function(){ return {fa:1}; })()")],
        [jq("ks_all_f1b", ".n | . + 100", n=5)],
        [sub_wf("ks_all_f1c", "ks_unit_noop")],
        [start_wf("ks_all_f1d", "ks_unit_noop"),
         inline("ks_all_f1d2", "(function(){ return {fired:true}; })()")]
    ])
    j1 = join("ks_all_j1", ["ks_all_f1a", "ks_all_f1b", "ks_all_f1c", "ks_all_f1d2"])
    # Phase 3 — conditional gate
    sw = switch("ks_all_sw", {"case": "${workflow.input.path}"},
                {
                    "loop": [do_while("ks_all_loop", 2,
                                       [inline("ks_all_lb", "(function(){ return {looped:true}; })()")])],
                    "term": [terminate("ks_all_term", "COMPLETED", "path=term")]
                },
                default=[inline("ks_all_sw_def", "(function(){ return {path:'default'}; })()")])
    # Phase 4 — exclusive join
    f2 = fork("ks_all_f2", [
        [inline("ks_all_ej_fast", "(function(){ return {ep:'fast'}; })()")],
        [wait("ks_all_ej_slw", "2s"),
         inline("ks_all_ej_slow", "(function(){ return {ep:'slow'}; })()")]
    ])
    ej = exclusive_join("ks_all_ej", ["ks_all_ej_fast", "ks_all_ej_slow"],
                         defaults=["ks_all_ej_fast"])

    return wf("ks_all_tasks",
               "[KS] Kitchen Sink: All self-contained system tasks in one workflow",
               phase1 + [f1, j1, sw, f2, ej],
               inputs=["path"])

def kitchen_sink_deep_nesting():
    """DO_WHILE → FORK_JOIN → SWITCH → DO_WHILE → INLINE (4 levels deep)."""
    deepest_loop = do_while("ksd_deep_loop", 2, [
        inline("ksd_deepest", "(function(){ return {depth:'max'}; })()")
    ])

    inner_f = fork("ksd_inner_f", [
        [
            switch("ksd_sw_a", {"case": "${workflow.input.variant}"},
                   {
                       "deep":    [deepest_loop],
                       "shallow": [inline("ksd_sh_a", "(function(){ return {depth:'shallow',b:'a'}; })()")]
                   },
                   default=[noop("ksd_noop_a")])
        ],
        [
            switch("ksd_sw_b", {"case": "${workflow.input.variant}"},
                   {
                       "deep":    [inline("ksd_dp_b", "(function(){ return {depth:'deep',b:'b'}; })()")],
                       "shallow": [inline("ksd_sh_b", "(function(){ return {depth:'shallow',b:'b'}; })()")]
                   },
                   default=[noop("ksd_noop_b")])
        ]
    ])
    inner_j = join("ksd_inner_j", ["ksd_sw_a", "ksd_sw_b"])

    return wf("ks_deep_nesting",
               "[KS] Kitchen Sink: Deep nesting — DO_WHILE→FORK_JOIN→SWITCH→DO_WHILE",
               [do_while("ksd_outer", 2, [inner_f, inner_j])],
               inputs=["variant"])

def kitchen_sink_everything_forks():
    """Every system task type as its own FORK_JOIN branch."""
    return wf("ks_fork_of_everything",
               "[KS] Kitchen Sink: Every system task type as a FORK_JOIN branch",
               [
                   fork("kef_f", [
                       [noop("kef_noop")],
                       [inline("kef_inline", "(function(){ return {r:'inline'}; })()")],
                       [lambda_("kef_lam", "return {r:'lambda'}")],
                       [set_variable("kef_sv", kef_tag="fork")],
                       [jq("kef_jq", ".v | . * 2", v=21)],
                       [http_get("kef_http", "http://localhost:8080/api/version")],
                       [wait("kef_wait", "1s")],
                       [sub_wf("kef_sub", "ks_unit_noop")],
                       [start_wf("kef_start", "ks_unit_noop"),
                        inline("kef_start_af", "(function(){ return {fired:true}; })()")],
                       [do_while("kef_dw", 1,
                                  [inline("kef_dw_b", "(function(){ return {dw:true}; })()")])],
                       [
                           switch("kef_sw", {"case": "always"},
                                  {"always": [inline("kef_sw_b", "(function(){ return {sw:true}; })()")]})
                       ],
                   ]),
                   join("kef_j", [
                       "kef_noop", "kef_inline", "kef_lam", "kef_sv",
                       "kef_jq", "kef_http", "kef_wait", "kef_sub",
                       "kef_start_af", "kef_dw", "kef_sw"
                   ])
               ])


# ──────────────────────────────────────────────────────────────
# REGISTRY
# ──────────────────────────────────────────────────────────────

ALL_WORKFLOWS = [
    # ── Units (no deps) ──
    unit_noop(),
    unit_inline(),
    unit_lambda(),
    unit_set_variable(),
    unit_json_jq(),
    unit_wait(),
    unit_switch_value_param(),
    unit_switch_js(),
    unit_nested_switch(),
    unit_do_while(),
    unit_fork_join(),
    unit_exclusive_join(),
    unit_terminate(),
    unit_terminate_failed(),
    unit_http(),
    unit_fork_join_dynamic(),
    unit_human(),
    # ── Units (depend on others above) ──
    unit_sub_workflow(),
    unit_start_workflow(),
    # ── Combinations: DO_WHILE outer ──
    combo_do_while_switch(),
    combo_do_while_fork_join(),
    combo_do_while_sub_workflow(),
    combo_do_while_do_while(),
    combo_do_while_exclusive_join(),
    combo_do_while_start_workflow(),
    combo_do_while_all_leaf(),
    # ── Combinations: SWITCH outer ──
    combo_switch_fork_join(),
    combo_switch_do_while(),
    combo_switch_sub_workflow(),
    combo_switch_terminate(),
    combo_switch_exclusive_join(),
    # ── Combinations: FORK_JOIN outer ──
    combo_fork_join_switch(),
    combo_fork_join_do_while(),
    combo_fork_join_sub_workflow(),
    combo_fork_join_fork_join(),
    combo_fork_join_exclusive_join(),
    # ── Combinations: EXCLUSIVE_JOIN ──
    combo_exclusive_join_do_while(),
    # ── Combinations: SUB_WORKFLOW ──
    combo_sub_workflow_in_fork_join(),
    # ── Combinations: DYNAMIC_FORK ──
    combo_dynamic_fork_in_do_while(),
    # ── Kitchen Sinks ──
    kitchen_sink_all_tasks(),
    kitchen_sink_deep_nesting(),
    kitchen_sink_everything_forks(),
]


def register(workflows, base_url):
    data = json.dumps(workflows).encode()
    req = urllib.request.Request(
        f"{base_url}/api/metadata/workflow",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req) as r:
            print(f"✓ Registered {len(workflows)} workflows — HTTP {r.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"✗ HTTP {e.code}: {body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if "--list" in sys.argv:
        for w in ALL_WORKFLOWS:
            print(w["name"])
        sys.exit(0)

    if "--dry-run" in sys.argv or "-n" in sys.argv:
        print(json.dumps(ALL_WORKFLOWS, indent=2))
        sys.exit(0)

    url = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--url=")),
               CONDUCTOR_URL)

    print(f"Registering {len(ALL_WORKFLOWS)} workflows to {url}:")
    for w in ALL_WORKFLOWS:
        print(f"  {w['name']}")
    print()

    ok = register(ALL_WORKFLOWS, url)
    sys.exit(0 if ok else 1)

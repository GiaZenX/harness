#!/usr/bin/env python3
"""The light kit's PILOT RIG (DEC-0092 (6), PR-0011 AC-12): scaffold a project per kit with the kit's
OWN installer, hand its lead three orders of obviously different size, and record what the kernel
leases -- rung and effort per order, the second-builder gate's verdict with and without a
`check-scopes` record, the spawn gate's four-line checkpoint as a process -- plus the routes the
light form rests on: the auditor's read-only route (AC-8), the lead's refused code write (AC-1) and
the solo default the entry file installs (AC-5).

Run at every kit stamp that touches the ladder or the lead texts: `tools/test_light_kit.py::
test_the_pilot_rig_leases_three_orders_of_different_size_per_kit` runs it, and the delivery run of
every stamp includes that test. It can also be run by hand:

    python tools/light_kit_pilot.py --out <directory outside this repo>

WHAT IT WRITES, AND WHERE: the pilots and a JSON log under `--out` only. The kit store is a copy of
this checkout's `team-kits/` under a HOME of its own, so nothing here touches the user's home or
this repository. The scaffold refuses a store that does not hash to its own stamp -- which is why
this rig is a measurement of a STAMPED tree and reads red on an unstamped one.

Refuses to run without `--out`; opens every file it writes with an explicit newline policy.
"""
import argparse
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, TEAM_KITS)

import conftest  # noqa: E402 -- the suite's approval mint and architect-step helper
from kernel import approvals, dispatch  # noqa: E402
from kernel.state import ProjectState  # noqa: E402

# The root item per kit, and its three orders: (role, type, allowed scope, expected outputs, ask).
# The three sizes are what DEC-0092 (6) asks for -- a one-file mechanical edit, a slice with design
# room, and a judgment-heavy piece -- and the ask beside each is the lead's derivation for it
# (DEC-0091 (1)): sonnet / opus / fable at high, the third at xhigh as a NAMED step.
ROOTS = {
    "dev-team": ("PR", {"title": "Kasse mit Bon", "class": "normal", "problem": "p", "goal": "g",
                        "acceptance_criteria": [{"id": "AC-1", "text": "done"}], "invariants": [],
                        "out_of_scope": [], "priority": "high"}),
    "research-team": ("RQ", {"title": "Frage", "class": "normal", "question": "q", "motivation": "m",
                             "acceptance_criteria": [{"id": "AC-1", "text": "answered"}],
                             "out_of_scope": [], "priority": "high"}),
    "office-team": ("PROC", {"title": "Monatsabschluss", "steps": ["collect", "book"],
                             "roles": ["bookkeeper"],
                             "acceptance_criteria": [{"id": "AC-1", "text": "booked"}]}),
}
BUILDERS = {"dev-team": "backend-developer", "research-team": "researcher", "office-team": "bookkeeper"}
ORDERS = [
    ("small", "implementation", ["src/small/README.md"], ["src/small/README.md"], {"rung": "sonnet", "effort": "high"}),
    ("medium", "implementation", ["src/medium/**"], ["src/medium/api.py", "tests/test_medium.py"], {"rung": "opus", "effort": "high"}),
    ("large", "implementation", ["src/large/**", "docs/large/**"],
     ["src/large/core.py", "src/large/model.py", "docs/large/design.md"], {"rung": "fable", "effort": "xhigh"}),
]
AUDIT_ROLE = "project-auditor"


def smallest_preset(store, kit):
    """The preset with the FEWEST roles -- the light form's default (DEC-0087 (2)/(4)), derived from
    the kit's own `presets.yaml` rather than named: `solo` in dev/research, `core` in office. `all`
    is every role and never the smallest."""
    presets = {}
    with io.open(os.path.join(store, kit, "presets.yaml"), encoding="utf-8", newline="") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if ":" in line:
                name, roles = line.split(":", 1)
                presets[name.strip()] = roles.split()
    roles_of = {name: (float("inf") if roles == ["all"] else len(roles)) for name, roles in presets.items()}
    name = min(roles_of, key=lambda candidate: (roles_of[candidate], candidate))
    return name, presets[name]


def _clock():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run(args, cwd, env, body=None, timeout=900):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=timeout, input=body)
    return {"rc": proc.returncode, "out": proc.stdout[-4000:], "err": proc.stderr[-4000:]}


def _hook(repo, name, payload, env):
    return _run([sys.executable, "-B", os.path.join(repo, ".claude", "hooks", name)], repo,
                dict(env, CLAUDE_PROJECT_DIR=repo), body=json.dumps(payload), timeout=120)


def _installer(store, script):
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                os.path.join(store, script + ".ps1")]
    return ["bash", os.path.join(store, script + ".sh")]


def _team_flag(script):
    return ["-Team"] if os.name == "nt" else []


def pilot(kit, out, store, env):
    """One kit's pilot, as a record."""
    record = {"clock": _clock(), "kit": kit}
    root_type, root_fields = ROOTS[kit]
    repo = os.path.join(out, kit.replace("-team", ""))
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], capture_output=True, timeout=60)
    preset, preset_roles = smallest_preset(store, kit)
    for script in ("init_project_memory", "scaffold_team"):
        args = _installer(store, script) + _team_flag(script) + [kit]
        if script == "scaffold_team":
            args += (["-Preset", preset] if os.name == "nt" else [preset])
        result = _run(args, repo, env)
        record["scaffold_" + script] = result["rc"]
        if result["rc"] != 0:
            record["scaffold_error"] = result
            return record
    # AC-5: the smallest preset is what the entry file writes, and what the installer installed
    installed = sorted(name[:-3] for name in os.listdir(os.path.join(repo, ".claude", "agents"))
                       if name.endswith(".md"))
    record["smallest_preset"] = {"name": preset, "roles": preset_roles, "installed_roles": installed}
    # the restart the installer asks for, walked honestly: the kit's own SessionStart hook clears it
    cleared = _hook(repo, "clear_handover_marker.py",
                    {"hook_event_name": "SessionStart", "source": "startup", "cwd": repo}, env)
    record["session_start_clears_marker"] = {
        "rc": cleared["rc"], "marker_gone": not os.path.exists(os.path.join(repo, ".claude", "HANDOVER_PENDING"))}
    state = ProjectState(os.path.join(repo, "project_memory"))
    entry = lambda *args, body=None: _run(  # noqa: E731 -- the entry point, once per line
        [sys.executable, os.path.join("scripts", "harness.py"), *args], repo, env, body=body)
    captured = entry("capture", root_type, body=json.dumps(root_fields))
    record["capture_root"] = captured["rc"]
    if captured["rc"] != 0:
        record["capture_error"] = captured
        return record
    root_id = captured["out"].split()[0]
    conftest.approve(state, root_id, "scope")
    # AC-1: the LEAD's own code write is refused -- by the Edit|Write chain the kit REGISTERS
    # (`_gate.py guard_pm_scope.py`, then `gate_write_scope.py`): `guard_pm_scope` is the door
    # that keeps the PM out of production code (a file property, no agent_id = the lead), and the
    # scope gate behind it holds the specialists to their orders. Run as the registered chain,
    # which is what the PM's Write call really meets.
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": repo,
               "agent_type": "project-manager",
               "tool_input": {"file_path": os.path.join(repo, "src", "x.py"), "content": "x"}}
    refused = _run([sys.executable, "-B", os.path.join(repo, ".claude", "hooks", "_gate.py"),
                    "guard_pm_scope.py", "gate_write_scope.py"], repo,
                   dict(env, CLAUDE_PROJECT_DIR=repo), body=json.dumps(payload), timeout=120)
    record["lead_code_write"] = {"rc": refused["rc"], "stderr": refused["err"][-400:]}
    # the three orders, each with its ask, all READY before the check
    record["orders"] = []
    role = BUILDERS[kit]
    for name, task_type, allowed, outputs, ask in ORDERS:
        args = ["create-task", "--product-requirement", root_id, "--derives-from", root_id,
                "--type", task_type, "--assigned-role", role, "--acceptance-ref", "AC-1",
                "--rung", ask["rung"], "--effort", ask["effort"]]
        for path in allowed:
            args += ["--allowed-scope", path]
        for path in outputs:
            args += ["--expected-output", path]
        created = entry(*args)
        order = {"size": name, "role": role, "ask": ask, "create": created["rc"],
                 "create_err": created["err"][-300:]}
        record["orders"].append(order)
        if created["rc"] != 0:
            continue
        order["task"] = created["out"].split()[0]
        entry("transition", order["task"], "READY")
        conftest.satisfy_the_architect_step(state, state.read_item(order["task"]), state.read_item(root_id))
    tasks = [order["task"] for order in record["orders"] if order.get("task")]
    if len(tasks) < 3:
        return record
    # the second builder WITHOUT a record: refused; then the record, then every lease
    first = entry("dispatch", tasks[0])
    record["orders"][0]["dispatch"] = {"rc": first["rc"], "ladder_line": first["err"].strip()[-400:]}
    unmeasured = entry("dispatch", tasks[1])
    record["second_builder_without_record"] = {"rc": unmeasured["rc"], "stderr": unmeasured["err"][-500:]}
    checked = entry("check-scopes")
    record["check_scopes"] = {"rc": checked["rc"], "out": checked["out"][-1200:]}
    for index, task_id in enumerate(tasks[1:], 1):
        leased = entry("dispatch", task_id)
        record["orders"][index]["dispatch"] = {"rc": leased["rc"], "ladder_line": leased["err"].strip()[-400:]}
    for order in record["orders"]:
        item = state.read_item(order["task"])
        order["leased"] = {key: item.get(key) for key in (dispatch.LEASE_RUNG_FIELD, dispatch.LEASE_EFFORT_FIELD)}
        try:
            lease = dispatch._read_lease(state, order["task"])
            order["measured_disjoint"] = lease.get(dispatch.MEASURED_DISJOINT_KEY)
            order["header"] = dispatch.dispatch_header(lease)
        except dispatch.DispatchError:
            order["measured_disjoint"] = None
    # the spawn gate's checkpoint, as a process, for the first builder
    header = record["orders"][0].get("header")
    if header:
        model = record["orders"][0]["leased"][dispatch.LEASE_RUNG_FIELD]
        gate = _hook(repo, "gate_dispatch.py", {
            "hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": repo, "session_id": "pilot",
            "prompt_id": "p-1", "tool_input": {"subagent_type": role, "run_in_background": False,
                                                "model": model, "prompt": header + "\nobjective: build"}}, env)
        context = ""
        try:
            context = json.loads(gate["out"])["hookSpecificOutput"]["additionalContext"]
        except (ValueError, KeyError, TypeError):
            pass
        record["checkpoint"] = {"rc": gate["rc"], "lines": context.splitlines(), "stderr": gate["err"][-300:]}
    # AC-8: the auditor on its read-only route, from the entry point
    # the typed values in the user's language (BUG-0073: what the user judges is German)
    asked = entry("request-approval", "routine", root_id, "--role", AUDIT_ROLE, "--scope",
                  "project_memory/**", "--trigger", "jede Woche und nach jedem Kit-Update",
                  "--cadence", "wöchentlich", "--expires-in-days", "30")
    audit = {"request_rc": asked["rc"], "err": asked["err"][-300:]}
    record["auditor_route"] = audit
    if asked["rc"] == 0:
        question = json.loads(asked["out"])
        audit["question"] = question["question"]
        request_id = question["question"].rsplit("[APR-REQ:", 1)[1].rstrip("]")
        conftest.mint_via_hook(state, approvals.pending_request(state, request_id))
        audit["root_approval_ref_after_mint"] = state.read_item(root_id).get("approval_ref")
        created = entry("create-task", "--product-requirement", root_id, "--derives-from", root_id,
                        "--type", "analysis", "--assigned-role", AUDIT_ROLE, "--acceptance-ref", "AC-1",
                        "--read-only", "--expected-output", "staging/audit/findings.md")
        audit["create_rc"] = created["rc"]
        if created["rc"] == 0:
            audit_id = created["out"].split()[0]
            entry("transition", audit_id, "READY")
            leased = entry("dispatch", audit_id)
            audit["dispatch"] = {"rc": leased["rc"], "ladder_line": leased["err"].strip()[-300:]}
            audit["allowed_scope"] = state.read_item(audit_id).get("allowed_scope")
    record["clock_end"] = _clock()
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="a directory OUTSIDE this repository; created fresh")
    parser.add_argument("--kits", nargs="*", default=sorted(ROOTS), help="which kits (default all)")
    args = parser.parse_args(argv)
    out = os.path.abspath(args.out)
    if os.path.abspath(ROOT) in (out, os.path.dirname(out)) or out.startswith(os.path.abspath(ROOT) + os.sep):
        sys.exit("--out lies inside this repository; the rig writes only outside it")
    if os.path.isdir(out):
        shutil.rmtree(out)
    home = os.path.join(out, "home")
    store = os.path.join(home, ".claude", "team-kits")
    # THE WHOLE STORE, recorder included: `write_kit_state.py` is one of the kit hash's inputs
    # (`kernel.hashing.kit_hash_inputs`), so a copy without it hashes to something else and every
    # stamp check downstream (`update-kit`, `request-approval kit_update`) refuses the copy as an
    # edited tree -- measured 2026-09-11 (1e2664f5005e against the stamp's cf05ce7e9cb9). The
    # scaffold itself only WARNS when the recorder is missing and then records no bundle trust,
    # which is how an older rig ran green with `hook_trust: unverified` pilots.
    shutil.copytree(TEAM_KITS, store, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".*_cache"))
    env = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "PYTHONPYCACHEPREFIX")}
    env.update(HOME=home, USERPROFILE=home)
    os.environ["HOME"] = home
    os.environ["USERPROFILE"] = home
    started = time.time()
    log = {"clock_start": _clock(), "kits": {}}
    for kit in args.kits:
        log["kits"][kit] = pilot(kit, out, store, env)
    log["clock_end"] = _clock()
    log["seconds"] = round(time.time() - started, 1)
    path = os.path.join(out, "light_kit_pilot.log.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(log, handle, indent=2, sort_keys=True)
    print(json.dumps({kit: {"orders": [(o.get("size"), o.get("leased")) for o in rec.get("orders", [])],
                            "second_builder_without_record_rc": rec.get("second_builder_without_record", {}).get("rc"),
                            "checkpoint_rc": rec.get("checkpoint", {}).get("rc"),
                            "auditor_dispatch_rc": rec.get("auditor_route", {}).get("dispatch", {}).get("rc"),
                            "lead_code_write_rc": rec.get("lead_code_write", {}).get("rc"),
                            "scaffold_error": rec.get("scaffold_error", {}).get("err", "")[-300:]}
                      for kit, rec in log["kits"].items()}, indent=1))
    print("log:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

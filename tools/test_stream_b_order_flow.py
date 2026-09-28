#!/usr/bin/env python3
"""Order flow, stream B of order 7 (TSK-0154): the dispatch lifecycle as the provider really drives
it, the cut the PM makes, and the name a started agent carries.

EVERY TEST NAMES THE ITEM IT CLOSES (DEC-0100), and the ones about the lifecycle drive the SHIPPED
hook as a process with the payload shapes measured on the provider (claude 2.1.258, headless, a
logging observer on every event -- staging/TSK-0154/protocol.md, "payload rig"). What was measured
there and is used here: a child's own PreToolUse(Bash) carries `agent_id` and
`tool_input.run_in_background`; its SubagentStop carries `background_tasks`, a session-wide list
whose running shell entries read `{type: shell, status: running, command: ...}`; and when that run
completes the provider fires SubagentStart AGAIN for the same agent_id.
"""
import json
import os
import subprocess
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM_KITS = os.path.join(os.path.dirname(HERE), "team-kits")
sys.path.insert(0, TEAM_KITS)

from conftest import drive_task_to  # noqa: E402
from test_hooks_v2 import (_stage_launcher, dispatched_repo, run_dispatch,  # noqa: E402
                           run_dispatch_env, run_scope, spawn_payload, write_payload)
from test_ladder import Store  # noqa: E402
from kernel import dispatch  # noqa: E402

CHILD = "child-1"
ROLE = "backend-developer"
RED_RUN = "python -m pytest tests/test_checkout.py -q"


def kernel_cli(tmp_path, *argv, env=None):
    """The kernel's own entry point, as a process -- what `scripts/harness.py` hands over to."""
    environment = dict(os.environ, PYTHONPATH=TEAM_KITS, **(env or {}))
    return subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root",
                           str(tmp_path / "project_memory")] + list(argv),
                          capture_output=True, text=True, encoding="utf-8", env=environment,
                          timeout=120, cwd=str(tmp_path))


def run_gate_utf8(repo, payload, env):
    """The shipped `gate_dispatch.py` as a process, its streams read as the UTF-8 `_compat` sets."""
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo), HARNESS_KERNEL_PATH=TEAM_KITS,
                       **env)
    return subprocess.run([sys.executable, os.path.join(TEAM_KITS, "dev-team", "hooks",
                                                        "gate_dispatch.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          encoding="utf-8", env=environment, timeout=120)


def child_event(tmp_path, event, agent_id=CHILD, **extra):
    return dict({"hook_event_name": event, "cwd": str(tmp_path), "agent_id": agent_id,
                 "agent_type": ROLE, "session_id": "lead-session"}, **extra)


def child_bash(tmp_path, command, background):
    return child_event(tmp_path, "PreToolUse", tool_name="Bash",
                       tool_input={"command": command, "description": "run it",
                                   "run_in_background": background})


def running_shell(command):
    """One entry of the provider's `background_tasks`, spelled as measured (payload rig run 2)."""
    return {"id": "bdg0v4ntq", "type": "shell", "status": "running",
            "description": command, "command": command}


def lead_stop(tmp_path):
    return {"hook_event_name": "Stop", "cwd": str(tmp_path), "stop_hook_active": False}


def started_child(tmp_path):
    """Spawn claimed, child bound by its SubagentStart -- the first two events of a real spawn."""
    state, task, header = dispatched_repo(tmp_path)
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, header)).returncode == 0
    started = run_dispatch(tmp_path, child_event(tmp_path, "SubagentStart"))
    assert started.returncode == 0, started.stderr
    return state, task, header


# -- BUG-0313 -------------------------------------------------------------------------------------

def test_a_child_waiting_on_its_own_background_run_is_not_reported_stopped_bug_0313(tmp_path):
    """BUG-0313, the field chain of synaipse TSK-0448 driven through the shipped gate.

    The child starts its red run in the background and ends its turn to wait. RED on 2026.09.26-5:
    the lead's next turn end is refused with "its child stopped ... no result was booked" and the
    no-progress status FAILED offered -- the lead booked it, and a second builder ran beside the
    first. Here the stop is a WAIT while the stop's own `background_tasks` still runs that command,
    the turn end passes untouched, the RESUME (a second SubagentStart for the same agent) is taken,
    and the child's real end afterwards is still reported -- so this cannot pass by never reporting.
    """
    state, task, _header = started_child(tmp_path)
    assert run_dispatch(tmp_path, child_bash(tmp_path, RED_RUN, True)).returncode == 0

    waited = run_dispatch(tmp_path, child_event(
        tmp_path, "SubagentStop", last_assistant_message="waiting for the red run",
        background_tasks=[{"id": "a1", "type": "subagent", "status": "running"},
                          running_shell(RED_RUN)]))
    assert waited.returncode == 0, waited.stderr
    assert not state.read_item(task["id"]).get(dispatch.CHILD_ENDED)
    turn_end = run_dispatch(tmp_path, lead_stop(tmp_path))
    assert turn_end.returncode == 0, turn_end.stderr
    assert task["id"] not in turn_end.stderr and "FAILED" not in turn_end.stderr

    assert run_dispatch(tmp_path, child_event(tmp_path, "SubagentStart")).returncode == 0
    assert not state.read_item(task["id"]).get(dispatch.CHILD_WAITING)
    assert run_dispatch(tmp_path, child_event(
        tmp_path, "SubagentStop", last_assistant_message="done, nothing booked",
        background_tasks=[])).returncode == 0
    reported = run_dispatch(tmp_path, lead_stop(tmp_path))
    assert reported.returncode == 2 and task["id"] in reported.stderr, reported.stderr


def test_a_running_shell_the_child_did_not_start_does_not_make_its_stop_a_wait_bug_0313(tmp_path):
    """The attribution half: the provider's list is SESSION-wide and names no owner, so the lead's
    own background run -- the FR-0093 line tells the lead to start its long runs that way -- must
    not turn a child's real end into a wait. Only a command the child itself started counts --
    here the child DID start one, which has completed by its stop, so a reader that counted any
    running shell once the child had started something is caught too."""
    state, task, _header = started_child(tmp_path)
    assert run_dispatch(tmp_path, child_bash(tmp_path, RED_RUN, True)).returncode == 0
    assert run_dispatch(tmp_path, child_event(
        tmp_path, "SubagentStop", background_tasks=[running_shell("python -m pytest tools/ -q")]
    )).returncode == 0
    assert state.read_item(task["id"]).get(dispatch.CHILD_ENDED)
    assert run_dispatch(tmp_path, lead_stop(tmp_path)).returncode == 2


# -- BUG-0314 -------------------------------------------------------------------------------------

def test_a_foreground_self_path_child_books_its_own_result_bug_0314(tmp_path):
    """BUG-0314 dead end 2 (synaipse TSK-0437): a foreground spawn's PostToolUse fires only after
    the child finished, so a self-path child that booked from inside its run met "LEASED --
    submit-result needs IN_PROGRESS". RED on 2026.09.26-5: the submit-result below exits non-zero.
    The run starts at the bind now; and the late PostToolUse finds the run booked and reports
    nothing false about it."""
    state, task, header = started_child(tmp_path)
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"
    booked = kernel_cli(tmp_path, "submit-result", "--task-id", task["id"], "--role", ROLE,
                        "--status-proposal", "SUBMITTED", "--summary", "built it")
    assert booked.returncode == 0, booked.stdout + booked.stderr
    assert state.read_item(task["id"])["status"] == "SUBMITTED"
    late = run_dispatch(tmp_path, spawn_payload(
        tmp_path, header, event="PostToolUse",
        tool_response={"status": "completed", "agentId": CHILD}))
    assert late.returncode == 0 and not late.stderr.strip(), late.stderr


def test_a_swept_lease_leaves_the_started_run_bookable_bug_0314(tmp_path):
    """BUG-0314 dead end 3: the lease of a started run expired and `sweep-leases` put the order back
    to READY -- committed work with no booking route (RED on 2026.09.26-5: the sweep says
    "released to READY" and the submit is refused). A started run keeps IN_PROGRESS and books."""
    state, task, _header = started_child(tmp_path)
    path = os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml")
    lease = state._read_yaml(path)
    lease["created_epoch"] = time.time() - float(lease["ttl"]) - 1.0
    state._write_yaml_atomic(path, lease)
    swept = kernel_cli(tmp_path, "sweep-leases")
    assert swept.returncode == 0, swept.stderr
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"
    booked = kernel_cli(tmp_path, "submit-result", "--task-id", task["id"], "--role", ROLE,
                        "--status-proposal", "SUBMITTED", "--summary", "built it")
    assert booked.returncode == 0, booked.stdout + booked.stderr


def test_an_expired_lease_of_a_started_run_is_leased_again_where_it_stands_bug_0314(tmp_path):
    """BUG-0314 dead end 1 (synaipse TSK-0358): the re-spawn on an expired lease was told "task
    returned to READY" while it stayed IN_PROGRESS, `dispatch` then refused "not READY", and
    IN_PROGRESS -> READY is no edge. RED on 2026.09.26-5 at the first assertion on the message.
    Now the refusal says what stands and names the re-lease, `dispatch` re-leases where the task
    stands, and the spawn on the new header is accepted."""
    state, task, header = started_child(tmp_path)
    assert run_dispatch(tmp_path, child_event(tmp_path, "SubagentStop",
                                              background_tasks=[])).returncode == 0
    path = os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml")
    lease = state._read_yaml(path)
    lease["created_epoch"] = time.time() - float(lease["ttl"]) - 1.0
    state._write_yaml_atomic(path, lease)

    respawn = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert respawn.returncode == 2
    assert "returned to READY" not in respawn.stderr, respawn.stderr
    assert "stays IN_PROGRESS" in respawn.stderr and "dispatch %s" % task["id"] in respawn.stderr

    relet = kernel_cli(tmp_path, "dispatch", task["id"])
    assert relet.returncode == 0, relet.stderr
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"
    fresh = relet.stdout.strip().splitlines()[0]
    assert run_dispatch(tmp_path, spawn_payload(tmp_path, fresh)).returncode == 0


def test_a_started_run_whose_child_has_no_recorded_end_is_not_leased_again_bug_0314(tmp_path):
    """The counter-direction of the re-lease, and it is the BUG-0313 guard: without a recorded end
    the child may still be going (a child can outlive its lease), and one that is WAITING on its
    own background run resumes by itself -- a second lease would be a second builder."""
    state, task, _header = started_child(tmp_path)
    run_dispatch(tmp_path, child_bash(tmp_path, RED_RUN, True))
    run_dispatch(tmp_path, child_event(tmp_path, "SubagentStop",
                                       background_tasks=[running_shell(RED_RUN)]))
    os.remove(os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml"))
    refused = kernel_cli(tmp_path, "dispatch", task["id"])
    assert refused.returncode != 0
    assert "WAITING" in refused.stderr and "second builder" in refused.stderr, refused.stderr
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"


# -- BUG-0326 -------------------------------------------------------------------------------------

def _expire_the_lease(state, task_id):
    path = os.path.join(state.root, "tasks", "leases", task_id + ".lease.yaml")
    lease = state._read_yaml(path)
    lease["created_epoch"] = time.time() - float(lease["ttl"]) - 1.0
    state._write_yaml_atomic(path, lease)
    return path


def _waiting_child(tmp_path):
    """A started child that ended its turn WAITING on its own background run (BUG-0313)."""
    state, task, header = started_child(tmp_path)
    assert run_dispatch(tmp_path, child_bash(tmp_path, RED_RUN, True)).returncode == 0
    assert run_dispatch(tmp_path, child_event(
        tmp_path, "SubagentStop", background_tasks=[running_shell(RED_RUN)])).returncode == 0
    assert state.read_item(task["id"]).get(dispatch.CHILD_WAITING)
    return state, task, header


def test_a_swept_lease_of_a_waiting_child_does_not_strand_its_task_bug_0326(tmp_path):
    """BUG-0326, the verifier's chain of TSK-0156 F4 through the shipped gates: the child waits on
    its own background run, its lease expires, the lead runs `sweep-leases` (the kernel's own
    remedy line sends it there). RED on 2026.09.27-4: the sweep dropped the lease, the resume found
    no binding, the child's write was refused "not bound to a task", its end was never recorded,
    and `dispatch` kept saying "wait for its result" forever. Now the sweep keeps a waiting child's
    lease and NAMES it, so the resume binds, the child writes, and its real end is reported."""
    state, task, _header = _waiting_child(tmp_path)
    lease_file = _expire_the_lease(state, task["id"])

    swept = kernel_cli(tmp_path, "sweep-leases")
    assert swept.returncode == 0, swept.stderr
    assert os.path.exists(lease_file), "the sweep dropped the lease of a waiting child"
    waiting_line = [line for line in swept.stdout.splitlines() if "WAITING" in line]
    assert waiting_line and task["id"] in waiting_line[0], swept.stdout

    assert run_dispatch(tmp_path, child_event(tmp_path, "SubagentStart")).returncode == 0
    assert not state.read_item(task["id"]).get(dispatch.CHILD_WAITING)
    wrote = run_scope(tmp_path, write_payload(tmp_path, tmp_path / "src" / "checkout.py",
                                              agent_id=CHILD))
    assert wrote.returncode == 0, wrote.stderr
    assert run_dispatch(tmp_path, child_event(tmp_path, "SubagentStop",
                                              background_tasks=[])).returncode == 0
    assert state.read_item(task["id"]).get(dispatch.CHILD_ENDED)
    reported = run_dispatch(tmp_path, lead_stop(tmp_path))
    assert reported.returncode == 2 and task["id"] in reported.stderr, reported.stderr


def test_every_refusal_that_meets_a_waiting_child_names_the_failed_way_out_bug_0326(tmp_path):
    """BUG-0326 AC-2: a waiting child that never resumes (its session ended, it was stopped) must
    not leave the lead with "wait" as the only word. Both refusals that meet it -- `dispatch` while
    its lease stands, and the re-spawn on its expired header -- name `transition <id> FAILED`, the
    re-spawn keeps the lease (an expiry does not release a waiting child's lease at either release
    site), and the transition named is the one that works: it drops the lease."""
    state, task, header = _waiting_child(tmp_path)
    lease_file = _expire_the_lease(state, task["id"])
    way_out = "transition %s FAILED" % task["id"]

    again = kernel_cli(tmp_path, "dispatch", task["id"])
    assert again.returncode != 0
    assert "WAITING" in again.stderr and way_out in again.stderr, again.stderr

    respawn = run_dispatch(tmp_path, spawn_payload(tmp_path, header))
    assert respawn.returncode == 2
    assert "WAITING" in respawn.stderr and way_out in respawn.stderr, respawn.stderr
    assert os.path.exists(lease_file), "the expired re-spawn released a waiting child's lease"

    failed = kernel_cli(tmp_path, *way_out.split())
    assert failed.returncode == 0, failed.stdout + failed.stderr
    assert state.read_item(task["id"])["status"] == "FAILED"
    assert not os.path.exists(lease_file)


def test_a_waiting_childs_kept_lease_still_owns_its_files_bug_0326(tmp_path):
    """The lease the sweep now keeps is a claim somebody still holds: the waiting child resumes and
    writes through it. So the file-ownership rule (`running_leases`) counts it past its expiry, and
    a second order over the same files is refused while that child waits -- RED with the TTL as the
    only reading of "running", where the second order was leased beside the waiting child: the
    second builder of BUG-0313, one order over. Kernel calls in the order the hooks make them."""
    from test_parallel_streams import orders_project

    _repo, state, ids = orders_project(
        tmp_path, [(["src/**"], []), (["src/**"], [])], files=["src/a.py"], status="READY")
    dispatch.create_lease(state, ids[0])
    dispatch.spawn_outcome(state, ids[0], ok=True)
    dispatch.bind_agent(state, ids[0], CHILD)
    assert dispatch.record_background_start(state, CHILD, RED_RUN) == ids[0]
    assert dispatch.record_child_end(state, CHILD, background_tasks=[running_shell(RED_RUN)]) \
        == ids[0]
    _expire_the_lease(state, ids[0])
    assert dispatch.sweep_expired_leases(state) == ([], [])

    with pytest.raises(dispatch.DispatchError) as refusal:
        dispatch.create_lease(state, ids[1])
    assert "src/a.py" in str(refusal.value) and ids[0] in str(refusal.value), refusal.value


def test_a_new_lease_after_the_failed_way_out_is_a_new_dispatch_bug_0326(tmp_path):
    """The way out BUG-0326's refusals name, walked to the retry (TSK-0157 verify round 1, N2):
    the child waits, the lead takes the order to FAILED, the user approves the retry, `dispatch`
    leases it again and no spawn comes within the TTL. RED on 2026.09.27-5: the waiting mark of
    the ENDED run survived FAILED, READY and the new lease, so the sweep kept that lease as a
    waiting child's ("lease kept, status LEASED"), it held its files with no time bound, and
    `dispatch` stayed refused. A new lease is a new dispatch: the sweep releases it to READY."""
    state, task, _header = _waiting_child(tmp_path)
    tid = task["id"]
    assert kernel_cli(tmp_path, "transition", tid, "FAILED").returncode == 0
    state.transition(tid, "READY", approved_retry=True)
    leased = kernel_cli(tmp_path, "dispatch", tid)
    assert leased.returncode == 0, leased.stderr
    assert not state.read_item(tid).get(dispatch.CHILD_WAITING)

    lease_file = _expire_the_lease(state, tid)
    swept = kernel_cli(tmp_path, "sweep-leases")
    assert swept.returncode == 0, swept.stderr
    assert not os.path.exists(lease_file) and state.read_item(tid)["status"] == "READY", swept.stdout
    assert kernel_cli(tmp_path, "dispatch", tid).returncode == 0


def test_the_sweep_names_each_waiting_tasks_own_way_out_bug_0326(tmp_path):
    """The sweep's WAITING line names the way out the refusals name -- the task's own no-progress
    status (`no_progress_status`), not a fixed FAILED. A kernel of 2026.09.27-5 left a waiting mark
    on a LEASED order (the chain of the test above), and there `transition <id> FAILED` is no edge:
    RED on that line, which named FAILED. The named transition is run, and it drops the lease."""
    state, task, _header = dispatched_repo(tmp_path)
    tid = task["id"]
    item = state.read_item(tid)
    item[dispatch.CHILD_WAITING] = "2026-09-27T19:00:00 on %s" % RED_RUN
    state._write_yaml_atomic(state.active_path(tid), item)
    lease_file = _expire_the_lease(state, tid)

    swept = kernel_cli(tmp_path, "sweep-leases")
    waiting_line = [line for line in swept.stdout.splitlines() if "WAITING" in line]
    target = dispatch.no_progress_status(item["status"])
    way_out = "transition %s %s" % (tid, target)
    assert waiting_line and way_out in waiting_line[0], swept.stdout
    ran = kernel_cli(tmp_path, *way_out.split())
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert state.read_item(tid)["status"] == target and not os.path.exists(lease_file)


# -- BUG-0324 -------------------------------------------------------------------------------------

def test_the_verifier_classifies_the_run_it_judges_and_the_climb_skips_it_bug_0324(
        tmp_path, monkeypatch):
    """BUG-0324 (synaipse TSK-0454), as a process: the verifying role classifies the failed run it
    is judging as mechanical, and the next lease of that order does not climb.

    The window the process really has is the verifier's own run: its lease is bound (so the hook
    and the kernel can attribute the line) while the order it judges is being judged, not yet
    FAILED. RED on 2026.09.26-5: the kernel refuses "is SUBMITTED, and a fail classification is
    about a run that ended in FAILED" (rc 2) -- and once the order IS failed, the verifier's lease
    is gone. The hook half is run too, so the line the verifier types is the one that passes.
    """
    store = Store(tmp_path, monkeypatch)
    store.kit("kit")
    state, pr = store.project("p", "kit", {ROLE: "sonnet", "quality-engineer": "opus"})
    repo = tmp_path / "p"
    env = {"HOME": str(store.home), "USERPROFILE": str(store.home)}
    build = store.order(state, pr)
    judge = store.order(state, pr, role="quality-engineer")
    drive_task_to(state, build["id"], "SUBMITTED")               # handed back, now being judged
    header = dispatch.dispatch_header(dispatch.create_lease(state, judge["id"]))
    assert run_dispatch_env(repo, spawn_payload(repo, header, role="quality-engineer"),
                            env).returncode == 0
    assert run_dispatch_env(repo, dict(child_event(repo, "SubagentStart", agent_id="judge-1"),
                                       agent_type="quality-engineer"), env).returncode == 0

    argv = ["evidence", "--kind", "test", "--result", "fail", "--fail-class", "mechanical",
            "--related", build["id"], "--summary", "a renamed path the fix missed",
            "--artifact-ref", "staging/x/run.txt", "--run-command", "python -m pytest -q",
            "--run-scope", "selection"]
    line = "python scripts/harness.py " + " ".join(
        '"%s"' % word if " " in word else word for word in argv)
    typed = run_dispatch_env(repo, dict(child_event(repo, "PreToolUse", agent_id="judge-1"),
                                        agent_type="quality-engineer", tool_name="Bash",
                                        tool_input={"command": line}), env)
    assert typed.returncode == 0, typed.stderr
    recorded = kernel_cli(repo, *argv, env=env)
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert "mechanical" in recorded.stdout and build["id"] in recorded.stdout

    state.transition(build["id"], "FAILED")
    state.transition(build["id"], "READY", approved_retry=True)
    retry = dispatch.create_lease(state, build["id"])
    assert state.read_item(build["id"])[dispatch.FAILED_RUNS] == 0, "the mechanical fail climbed"
    assert retry[dispatch.RUNG_KEY] == "sonnet", retry[dispatch.RUNG_KEY]


def test_a_classification_the_verdict_overruled_discounts_nothing_bug_0324(tmp_path, monkeypatch):
    """The bound on the wider window: a stamp written while the run is judged is about THAT run, so
    a verdict that moves the order FORWARD instead drops it -- a later, different FAILED then climbs.
    RED with `drop_an_overruled_classification` made a no-op: the stamp survives DONE and the
    later failure comes back on the cheap rung."""
    store = Store(tmp_path, monkeypatch)
    store.kit("kit")
    state, pr = store.project("p", "kit", {ROLE: "sonnet", "quality-engineer": "opus"})
    build = store.order(state, pr)
    judge = store.order(state, pr, role="quality-engineer")
    drive_task_to(state, build["id"], "SUBMITTED")
    dispatch.create_lease(state, judge["id"])
    dispatch.bind_agent(state, judge["id"], "judge-1")
    assert dispatch.fail_class_refusal(state, "quality-engineer", [build["id"]], "fail",
                                       "mechanical") is None
    dispatch.record_fail_class(state, [build["id"]], "mechanical", "quality-engineer")
    state.transition(build["id"], "DONE")                          # the verdict went the other way
    assert dispatch.FAIL_CLASS_FIELD not in state.read_item(build["id"])
    state.transition(build["id"], "FAILED")
    state.transition(build["id"], "READY", approved_retry=True)
    dispatch.create_lease(state, build["id"])
    assert state.read_item(build["id"])[dispatch.FAILED_RUNS] == 1


# -- BUG-0322 -------------------------------------------------------------------------------------

def _architect_kit_project(store, goal_class):
    """A project of a kit that SHIPS the architect step (its template carries the SR home), with an
    architect and a builder installed, and nothing derived yet."""
    from test_ladder import TSK_FIELDS as LADDER_TSK_FIELDS

    store.kit("kit", with_architect_step=True)
    state, pr = store.project("p", "kit", {"software-architect": "opus", ROLE: "sonnet"},
                              goal_class=goal_class)

    def order(role, **overrides):
        fields = dict(LADDER_TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"],
                      assigned_role=role,
                      allowed_scope=["src/%s-%d/**" % (role, len(list(state.iter_active_items("TSK"))))])
        fields.update(overrides)
        task = dispatch.create_task(state, fields)
        state.transition(task["id"], "READY")
        return task
    return state, pr, order, {"HOME": str(store.home), "USERPROFILE": str(store.home)}


def test_the_architects_own_order_is_not_asked_for_the_step_it_takes_bug_0322(tmp_path,
                                                                               monkeypatch):
    """BUG-0322 shape 1 (synaipse TSK-0444): under a LARGE goal with no accepted requirement the
    architect's own order -- the one that derives it -- was refused "no SR in status ACCEPTED".
    RED on 2026.09.26-5: the `dispatch` below exits 2. The counter-direction stays: the BUILD order
    under the same goal is still refused, and its refusal says what it examined."""
    state, pr, order, env = _architect_kit_project(Store(tmp_path, monkeypatch), "large")
    repo = tmp_path / "p"
    architect = order("software-architect", type="architecture")
    leased = kernel_cli(repo, "dispatch", architect["id"], env=env)
    assert leased.returncode == 0, leased.stderr
    build = order(ROLE)
    refused = kernel_cli(repo, "dispatch", build["id"], env=env)
    assert refused.returncode != 0 and "no SR hangs from %s at all" % pr["id"] in refused.stderr, (
        refused.stderr)


def test_an_accepted_requirement_with_a_second_parent_counts_for_its_goal_bug_0322(tmp_path,
                                                                                   monkeypatch):
    """BUG-0322 shape 2 (synaipse TSK-0445): SR-0280..0283 were ACCEPTED under the goal and each
    ALSO derived from a change request of other goals -- one stray parent voided them for the
    check, and the refusal named none. RED on 2026.09.26-5: the `dispatch` below exits 2 with
    "no SR in status ACCEPTED". A requirement counts for every goal it derives from; one that does
    not count is NAMED with its reason (the PROPOSED one below)."""
    state, pr, order, env = _architect_kit_project(Store(tmp_path, monkeypatch), "normal")
    repo = tmp_path / "p"
    from test_ladder import PR_FIELDS as LADDER_PR_FIELDS

    other = state.capture("PR", dict(LADDER_PR_FIELDS, title="another goal"))
    change = state.capture("CR", {"title": "express lane", "target_pr": other["id"],
                                  "target_revision": 1, "change_description": "express lane",
                                  "acceptance_criteria": [{"id": "AC-CR-1", "text": "one click"}]})
    proposed = state.capture("SR", {"title": "not yet agreed", "derives_from": [pr["id"]],
                                    "contract": "c", "affected_components": ["src"]})
    build = order(ROLE)
    refused = kernel_cli(repo, "dispatch", build["id"], env=env)
    assert refused.returncode != 0
    assert "%s (status PROPOSED, not ACCEPTED)" % proposed["id"] in refused.stderr, refused.stderr

    shared = state.capture("SR", {"title": "shared design", "derives_from": [pr["id"], change["id"]],
                                  "contract": "c", "affected_components": ["src"]})
    state.transition(shared["id"], dispatch._accepted_requirement_status())
    leased = kernel_cli(repo, "dispatch", build["id"], env=env)
    assert leased.returncode == 0, leased.stderr


# -- BUG-0315 -------------------------------------------------------------------------------------

def test_the_launcher_form_of_the_approval_hook_counts_as_wired_bug_0315(tmp_path):
    """BUG-0315 (synaipse, request-approval plan PR-0018..0030): the SHIPPED registration runs the
    approval hook as the ARGUMENT of `_gate.py`, and `report._runs_no_file` looked for that argument
    at the repo root -- so `approval_mint_is_wired` said False and every plan question warned "will
    approve nothing" at a project that mints. RED on 2026.09.26-5 at the first assertion.

    Read off the kit's own `settings.json` and its own hook files, so the registration measured is
    the one that ships. Two counterweights: the launcher's sibling rule is RUN (the shipped `_gate.py`
    starts a probe that exists only beside it, from a working directory where it does not), and a
    launcher whose sibling is missing still reads unwired -- the under-warning direction BUG-0173
    closed stays closed.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals, report

    kit_hooks = os.path.join(TEAM_KITS, "dev-team", "hooks")
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    _stage_launcher(hooks)                            # `_gate.py` and what it imports
    with open(os.path.join(kit_hooks, approvals.APPROVAL_HOOK), "rb") as source:
        (hooks / approvals.APPROVAL_HOOK).write_bytes(source.read())
    with open(os.path.join(TEAM_KITS, "dev-team", "settings", "settings.json"), "rb") as source:
        (tmp_path / ".claude" / "settings.json").write_bytes(source.read())
    assert report.approval_mint_is_wired(str(tmp_path)) is True

    (hooks / "gate_probe.py").write_bytes(b"import sys\nsys.exit(7)\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    ran = subprocess.run([sys.executable, str(hooks / "_gate.py"), "gate_probe.py"], input="{}",
                         capture_output=True, text=True, cwd=str(elsewhere), timeout=60,
                         env=dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path)))
    assert ran.returncode == 7, "the launcher no longer runs its argument as a sibling: %s" % (
        ran.stdout + ran.stderr)

    (hooks / approvals.APPROVAL_HOOK).unlink()
    assert report.approval_mint_is_wired(str(tmp_path)) is False


# -- BUG-0321 -------------------------------------------------------------------------------------

def test_a_later_passing_selection_supersedes_an_older_failing_one_bug_0321(tmp_path):
    """BUG-0321 (synaipse BUG-0001 VERIFIED vs EVD-0025): the READER is
    `report.contradicted_confirmations`, in this stream's files. A bug confirmed on a passing
    regression run -- a selection by nature, the run its own edge asks for -- was reported as
    contradicted by an OLDER failing selection, because the check read the delivery question, where
    a passing selection is dropped. RED on 2026.09.26-5: the first `== {}` is `{BUG-0001: [EVD-0001]}`
    and the validator carries the error. The counterweight: a failing selection AFTER the pass
    contradicts the confirmation again -- the reading is "newest wins", not "never contradicted"."""
    sys.path.insert(0, TEAM_KITS)
    from conftest import walk_to_status
    from kernel import report
    from kernel.state import ProjectState
    from test_report import PR_FIELDS as REPORT_PR_FIELDS, evd, make_bug

    (tmp_path / "project_memory").mkdir()
    state = ProjectState(str(tmp_path / "project_memory"))
    root = state.capture("PR", dict(REPORT_PR_FIELDS))
    bug = make_bug(state, root["id"])
    evd(state, result="fail", related=(bug["id"],), created="2026-01-01T00:00:00",
        run_command="python -m pytest tests/test_x.py -q", run_scope="selection")
    evd(state, result="pass", related=(bug["id"],), created="2026-02-01T00:00:00",
        run_command="python -m pytest tests/test_x.py -q", run_scope="selection")
    walk_to_status(state, bug, "VERIFIED")
    assert report.contradicted_confirmations(state) == {}
    assert not [finding for finding in report.validate_state(state)
                if finding["item"] == bug["id"] and finding["severity"] == "error"]

    later = evd(state, result="fail", related=(bug["id"],), created="2026-03-01T00:00:00",
                run_command="python -m pytest tests/test_x.py -q", run_scope="selection")
    assert report.contradicted_confirmations(state) == {bug["id"]: [later]}


# -- DEC-0118 -------------------------------------------------------------------------------------

# DEC-0118 (1)/(2) AS DATA: on Claude the top rung is opus at xhigh, on Codex the top stays the
# declared one at the kit's default effort. The kit whose top is opus by its OWN declaration (office,
# DEC-0078 (1)) is not capped by Claude, so nothing changes there. Keyed by the kit's declared top,
# which is what the decision is about -- not by kit name.
DEC_0118 = {"fable": {"claude": ("opus", "xhigh"), "codex": ("fable", "high")},
            "opus": {"claude": ("opus", "medium"), "codex": ("opus", "medium")}}


def test_the_architecture_step_starts_at_xhigh_on_claude_and_at_the_default_on_codex_dec_0118(
        tmp_path, monkeypatch):
    """DEC-0118, measured through `kernel.cli ladder --provider` -- the command the constitutions
    name -- for every shipped kit on both providers: every role whose class starts on `top`, at
    FAIL 0 under a normal goal. RED on 2026.09.26-5 for dev and research on Claude (opus at `high`,
    the kit's default). The control per kit is a role whose class does NOT start on the top: its
    Claude answer keeps the kit's default effort, so the rule is the class's and not the kit's."""
    from test_ladder import kit_dirs, shipped_ladder

    store = Store(tmp_path, monkeypatch)
    env = {"HOME": str(store.home), "USERPROFILE": str(store.home)}
    measured = []
    for kit in [os.path.basename(path) for path in kit_dirs()]:
        declared = shipped_ladder(kit)
        store.kit(kit, ladder=declared)
        pins = {role: str(dispatch.role_pin(os.path.join(TEAM_KITS, kit, "agents"), role))
                for role in declared["roles"]}
        state, pr = store.project("p-" + kit, kit, pins)
        tops = [role for role, cls in declared["roles"].items()
                if declared["classes"][cls] == dispatch.CLASS_TOP]
        control = next(role for role, cls in declared["roles"].items()
                       if declared["classes"][cls] != "top" and role not in tops
                       and role not in (declared.get("exceptions") or {}))
        assert tops, "%s declares no class that starts on the top" % kit
        for role in tops + [control]:
            order = Store.order(state, pr, role=role)
            for provider in ("claude", "codex"):
                shown = kernel_cli(tmp_path / ("p-" + kit), "ladder", order["id"], "--provider",
                                   provider, env=env)
                assert shown.returncode == 0, shown.stderr
                answer = json.loads(shown.stdout)
                got = (answer[dispatch.RUNG_KEY], answer[dispatch.EFFORT_KEY])
                if role in tops:
                    assert got == DEC_0118[declared["top"]][provider], (kit, role, provider,
                                                                       answer["why"])
                else:
                    assert answer[dispatch.EFFORT_KEY] == declared["effort"]["default"], (
                        kit, role, provider, answer["why"])
                measured.append((kit, role, provider) + got)
    assert {row[0] for row in measured} == {os.path.basename(path) for path in kit_dirs()}


# -- BUG-0318 -------------------------------------------------------------------------------------

def _cut_project(tmp_path, monkeypatch):
    """A kit project whose declaration classes a builder and a verifier, and the create-task line
    the PM types, as a process."""
    store = Store(tmp_path, monkeypatch)
    store.kit("kit")
    state, pr = store.project("p", "kit", {ROLE: "sonnet", "quality-engineer": "opus"})
    repo = tmp_path / "p"
    env = {"HOME": str(store.home), "USERPROFILE": str(store.home)}

    def create(role, root, origin, *outputs, acceptance="AC-1"):
        argv = ["create-task", "--product-requirement", root, "--derives-from", origin,
                "--type", "implementation" if role == ROLE else "test", "--assigned-role", role,
                "--acceptance-ref", acceptance,
                "--allowed-scope", "src/%s-%d/**" % (role, len(list(state.iter_active_items("TSK"))))]
        for output in outputs:
            argv += ["--expected-output", output]
        return kernel_cli(repo, *argv, env=env)
    return state, pr, repo, env, create


def test_create_task_says_the_cut_it_makes_and_refuses_nothing_bug_0318(tmp_path, monkeypatch):
    """BUG-0318 (a), as the process the PM runs: `create-task` for a SECOND open build order under
    one goal, and for a QA order on a change whose build order carries ONE expected output, prints
    a fact line naming DEC-0087/0088 -- and still exits 0, because it is a fact and not a refusal.
    RED on 2026.09.26-5: no `[cut]` line on either. The controls: the FIRST build order gets none,
    and a QA order at the goal itself (the verifier round DEC-0088 (b) asks for) gets none."""
    state, pr, repo, env, create = _cut_project(tmp_path, monkeypatch)
    first = create(ROLE, pr["id"], pr["id"], "src/a.py")
    assert first.returncode == 0 and "[cut]" not in first.stderr, first.stderr
    second = create(ROLE, pr["id"], pr["id"], "src/b.py")
    assert second.returncode == 0, second.stderr
    assert "[cut]" in second.stderr and "DEC-0087" in second.stderr and "TSK-0001" in second.stderr

    at_the_goal = create("quality-engineer", pr["id"], pr["id"], "a verdict")
    assert at_the_goal.returncode == 0 and "DEC-0088 (d)" not in at_the_goal.stderr

    change = state.capture("CR", {"title": "a wording", "target_pr": pr["id"],
                                  "target_revision": pr["revision"],
                                  "change_description": "one label",
                                  "acceptance_criteria": [{"id": "AC-CR-1", "text": "reads right"}]})
    small = create(ROLE, pr["id"], change["id"], "src/label.py", acceptance="AC-CR-1")
    assert small.returncode == 0, small.stderr
    verifier = create("quality-engineer", pr["id"], change["id"], "a verdict", acceptance="AC-CR-1")
    assert verifier.returncode == 0, verifier.stderr
    assert "DEC-0088 (d)" in verifier.stderr and change["id"] in verifier.stderr, verifier.stderr


def test_the_brief_shows_the_cut_and_the_parallel_candidates_bug_0318(tmp_path, monkeypatch):
    """BUG-0318 (b)/(d): the session brief carries open orders per goal, the verifier share, and --
    once `check-scopes` measured two goals' next build orders disjoint -- those goals as parallel
    build candidates. RED on 2026.09.26-5: the brief's `lease_distribution` has no `cut_line`.
    Read off the generated file, the thing a session starts from."""
    yaml = pytest.importorskip("yaml")
    from test_ladder import PR_FIELDS as LADDER_PR_FIELDS
    from conftest import approve

    state, pr, repo, env, create = _cut_project(tmp_path, monkeypatch)
    other = state.capture("PR", dict(LADDER_PR_FIELDS, title="a second goal"))
    approve(state, other["id"], "scope")
    assert create(ROLE, pr["id"], pr["id"], "src/a.py").returncode == 0
    assert create("quality-engineer", pr["id"], pr["id"], "a verdict").returncode == 0
    assert create(ROLE, other["id"], other["id"], "src/b.py").returncode == 0

    def brief():
        made = kernel_cli(repo, "generate-session-brief", "--kit", "kit", "--kit-version", "x",
                          "--enforcement", "hard", env=env)
        assert made.returncode == 0, made.stderr
        with open(str(repo / "project_memory" / "generated" / "session_brief.yaml"),
                  encoding="utf-8") as handle:
            return yaml.safe_load(handle)["lease_distribution"]

    before = brief()
    assert before["orders_per_goal"][pr["id"]] == {"build": 1, "qa": 1}
    assert before["verifier_share"] == [1, 3]
    assert before["parallel_candidates"] == [] and "check-scopes" in before["cut_line"]

    for task in ("TSK-0001", "TSK-0002", "TSK-0003"):
        state.transition(task, "READY")
    checked = kernel_cli(repo, "check-scopes", env=env)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    after = brief()
    assert len(after["parallel_candidates"]) == 1, after["cut_line"]
    assert pr["id"] in after["parallel_candidates"][0] and other["id"] in after["parallel_candidates"][0]


# -- FR-0092 --------------------------------------------------------------------------------------

def test_the_spawn_carries_the_name_the_lease_composed_fr_0092(tmp_path, monkeypatch):
    """FR-0092: every started agent's visible name carries role, rung and effort -- and a letter
    when more than one lease of that role is live under the goal. The `dispatch` command prints the
    name, the header carries it, and the shipped spawn gate refuses a description that is not it
    (the payload carries `description`, measured). The letters: two live leases A and B, a third C;
    a finished one frees its letter. RED on 2026.09.26-5: the wrongly named spawn is allowed (rc 0)."""
    state, pr, repo, env, create = _cut_project(tmp_path, monkeypatch)
    for output in ("src/a.py", "src/b.py", "src/c.py", "src/d.py"):
        assert create(ROLE, pr["id"], pr["id"], output).returncode == 0
    for task in ("TSK-0001", "TSK-0002", "TSK-0003", "TSK-0004"):
        state.transition(task, "READY")
    assert kernel_cli(repo, "check-scopes", env=env).returncode == 0

    first = kernel_cli(repo, "dispatch", "TSK-0001", env=env)
    assert first.returncode == 0, first.stderr
    assert "spawn with description: Backend Developer \u00b7 Sonnet high\n" in first.stderr
    second = kernel_cli(repo, "dispatch", "TSK-0002", env=env)
    assert second.returncode == 0, second.stderr
    name = "Backend Developer \u00b7 Sonnet high \u00b7 B"
    header = second.stdout.strip().splitlines()[0]
    assert json.loads(header[len(dispatch.HEADER_PREFIX):])[dispatch.SPAWN_NAME_KEY] == name

    wrong = dict(spawn_payload(repo, header), session_id="s", prompt_id="p")
    wrong["tool_input"]["description"] = "Bug-Null order 1 (Opus)"
    refused = run_gate_utf8(repo, wrong, env)
    assert refused.returncode == 2 and "FR-0092" in refused.stderr and name in refused.stderr, (
        refused.stderr)
    right = dict(spawn_payload(repo, header), session_id="s", prompt_id="p")
    right["tool_input"]["description"] = name
    allowed = run_gate_utf8(repo, right, env)
    assert allowed.returncode == 0, allowed.stderr

    third = kernel_cli(repo, "dispatch", "TSK-0003", env=env)
    assert third.returncode == 0 and third.stderr.rstrip().endswith("\u00b7 C"), third.stderr
    state.transition("TSK-0001", "READY")                   # the first one's lease is gone: A is free
    fourth = kernel_cli(repo, "dispatch", "TSK-0004", env=env)
    assert fourth.returncode == 0 and fourth.stderr.rstrip().endswith("\u00b7 A"), fourth.stderr


def test_the_cut_line_is_bounded_for_the_brief_budget_bug_0318(tmp_path, monkeypatch):
    """The brief carries a byte budget, and the cut line spells goals and pairs -- 7 goals with one
    build order each, all measured disjoint, are 21 pairs. The line names the largest goals and the
    first pairs and counts the rest (`report._BRIEF_CUT_SHOWN`); the per-goal counts stay whole.
    RED with the bound removed: 21 candidates come back."""
    sys.path.insert(0, TEAM_KITS)
    from test_ladder import PR_FIELDS as LADDER_PR_FIELDS
    from conftest import approve
    from kernel import report

    state, pr, repo, env, create = _cut_project(tmp_path, monkeypatch)
    goals = [pr] + [state.capture("PR", dict(LADDER_PR_FIELDS, title="goal %d" % number))
                    for number in range(6)]
    for goal in goals[1:]:
        approve(state, goal["id"], "scope")
    for number, goal in enumerate(goals):
        assert create(ROLE, goal["id"], goal["id"], "src/g%d.py" % number).returncode == 0
    assert kernel_cli(repo, "check-scopes", env=env).returncode == 0
    cut = report.order_cut(state)
    shown = report._BRIEF_CUT_SHOWN
    assert len(cut["orders_per_goal"]) == 7
    assert len(cut["parallel_candidates"]) == shown + 1, cut["parallel_candidates"]
    assert cut["parallel_candidates"][-1] == "... and %d more pair(s)" % (21 - shown)
    assert "... and %d more goal(s)" % (7 - shown) in cut["cut_line"], cut["cut_line"]

#!/usr/bin/env python3
"""The light kit's kernel contract (PR-0011, generation 6): the tier ask per order (DEC-0091), the
structural gate on a second builder (DEC-0092 (2)), the fact-based checkpoint the spawn gate hands
the PM (DEC-0092 (3)) and the distribution both mirrors read (DEC-0092 (4)).

Measured against the kernel and the SHIPPED spawn gate as a process, on projects built the way the
scaffold builds them (`test_ladder.Store`: a kit store under a HOME of its own, a scaffold record,
installed role definitions with pins) -- never against a copy of a rule. The kit-less shape this
repository runs in is measured too, because it is the one that must keep dispatching without a
ladder and without the second-builder rule.
"""
import io
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
sys.path.insert(0, TEAM_KITS)

from conftest import approve, drive_task_to, satisfy_the_architect_step  # noqa: E402 -- shared suite helpers
from kernel import backlog_types, dispatch, scopes  # noqa: E402
from kernel.dispatch import DispatchError  # noqa: E402
from kernel.state import ProjectState, StateError  # noqa: E402
from test_ladder import LADDER, PR_FIELDS, Store, TSK_FIELDS, kit_dirs, write  # noqa: E402

yaml = pytest.importorskip("yaml")

DEV_HOOKS = os.path.join(TEAM_KITS, "dev-team", "hooks")
# The office-shaped effort pair (DEC-0078 (2)): the highest effort this ladder runs is `high`.
OFFICE_LIKE = dict(LADDER, effort={"default": "medium", "large": "high"})


@pytest.fixture
def store(tmp_path, monkeypatch):
    return Store(tmp_path, monkeypatch)


def draft_order(state, pr, role="backend-developer", **overrides):
    """Like `Store.order`, but the order stays DRAFT -- for the tests that re-plan one."""
    fields = dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"], assigned_role=role,
                  allowed_scope=["src/order-%d/**" % (len(list(state.iter_active_items("TSK"))) + 1)])
    fields.update(overrides)
    return dispatch.create_task(state, fields)


def ready(state, task, pr):
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), pr)
    return state.read_item(task["id"])


def kernel(state, store, *args):
    """The kernel's command surface as a PROCESS, the way a lead types it."""
    env = dict(os.environ, HOME=str(store.home), USERPROFILE=str(store.home), PYTHONPATH=TEAM_KITS)
    return subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", state.root] + list(args),
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)


# ================================================== 1. the contract (DEC-0091 (1))

def test_the_order_fields_are_the_contracts_and_frozen_with_the_plan(store):
    """DEC-0091 (1): `rung` and `effort` are optional TSK fields, spelled ONCE in the contract and
    read from there by the dispatcher, and they change only while the order is DRAFT -- the plan
    freeze the contract already had, not a second mechanism.

    RED WITHOUT the two names in `TSK_PLAN_FIELDS`: the READY order below takes the update.
    """
    assert dispatch.RUNG_KEY is backlog_types.TSK_RUNG_FIELD
    assert dispatch.EFFORT_KEY is backlog_types.TSK_EFFORT_FIELD
    for field in (dispatch.RUNG_KEY, dispatch.EFFORT_KEY):
        assert field in backlog_types.OPTIONAL_FIELDS["TSK"], field
        assert field not in backlog_types.REQUIRED_FIELDS["TSK"], (
            "most orders take the ladder's own answer; a required ask is a field every planner "
            "types to say nothing")
        assert field in backlog_types.TSK_PLAN_FIELDS, field
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    task = draft_order(state, pr)
    state.update_item(task["id"], {dispatch.RUNG_KEY: "opus", dispatch.EFFORT_KEY: "xhigh"})
    assert dispatch.order_tiers(state.read_item(task["id"])) == ("opus", "xhigh")
    ready(state, task, pr)
    with pytest.raises(StateError) as refusal:
        state.update_item(task["id"], {dispatch.RUNG_KEY: "fable"})
    assert "frozen" in str(refusal.value) and dispatch.RUNG_KEY in str(refusal.value)
    assert dispatch.order_tiers(state.read_item(task["id"])) == ("opus", "xhigh")


# ================================================== 2. the derivation (DEC-0091 (2))

def test_an_order_rung_lifts_the_start_and_the_climb_begins_there(store):
    """DEC-0091 (2): the lease rung is the HIGHER of the ladder's floor and the order's ask; the
    climb of DEC-0034 rule 2 starts where the order starts; an ask below the floor lowers nothing.

    RED WITHOUT the `max()`: the builder below leases on its pin (sonnet) and climbs to opus after
    the failed run, not to fable; and the `why` names no ask.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet", "software-architect": "opus"})
    lifted = store.order(state, pr, **{dispatch.RUNG_KEY: "opus"})
    lease = dispatch.create_lease(state, lifted["id"])
    answer = lease[dispatch.LADDER_KEY]
    assert lease[dispatch.RUNG_KEY] == "opus", answer
    assert (answer["floor"], answer["start"], answer["order"][dispatch.RUNG_KEY]) == ("sonnet", "opus", "opus")
    assert "the order asks opus" in answer["why"], answer["why"]
    drive_task_to(state, lifted["id"], "FAILED")
    state.transition(lifted["id"], "READY", approved_retry=True)
    climbed = dispatch.create_lease(state, lifted["id"])
    assert climbed[dispatch.RUNG_KEY] == "fable", climbed[dispatch.LADDER_KEY]
    assert climbed[dispatch.LADDER_KEY]["failed_runs"] == 1
    # the ask never lowers a class with NO BAND: an architect (class `top`, a bare rung, so
    # default == floor == fable) asked for sonnet still starts on fable, and the `why` names the
    # floor rather than the acceptance -- below the floor DEC-0097 (2) grants nothing at all.
    kept = store.order(state, pr, role="software-architect", type="architecture",
                       expected_outputs=["tools/test_arch.py"], **{dispatch.RUNG_KEY: "sonnet"})
    lease = dispatch.create_lease(state, kept["id"])
    assert lease[dispatch.RUNG_KEY] == "fable", lease[dispatch.LADDER_KEY]
    assert "asks sonnet below the floor fable" in lease[dispatch.LADDER_KEY]["why"], \
        lease[dispatch.LADDER_KEY]["why"]


def test_an_order_rung_above_the_roles_top_is_capped_and_the_answer_says_so(store):
    """`top` still caps (DEC-0091 (2)): an ask inside the vocabulary but above the role's top is
    neither refused nor granted -- the lease lands on the top and the answer carries both."""
    store.kit("kit", ladder=dict(LADDER, exceptions={"backend-developer": {"top": "opus"}}))
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    lease = dispatch.create_lease(state, store.order(state, pr, **{dispatch.RUNG_KEY: "fable"})["id"])
    answer = lease[dispatch.LADDER_KEY]
    assert lease[dispatch.RUNG_KEY] == "opus", answer
    assert answer["order"][dispatch.RUNG_KEY] == "fable" and answer["top"] == "opus"
    assert "the order asks fable" in answer["why"] and "top opus" in answer["why"], answer["why"]


def test_an_order_effort_lifts_the_goals_effort_and_the_kits_highest_effort_caps_it(store):
    """DEC-0091 (2): the lease effort is the HIGHER of the goal's and the order's; the ceiling is
    the highest effort the kit's own pair declares (office: `high`, DEC-0078 (2)).

    RED WITHOUT the effort `max()`: the first order leases on the goal's `high`; RED WITHOUT the
    ceiling: the office-shaped order leases on `xhigh`, an effort that kit never runs.
    """
    store.kit("dev-like")
    store.kit("office-like", ladder=OFFICE_LIKE)
    state, pr = store.project("p", "dev-like", {"backend-developer": "sonnet"})
    lifted = dispatch.create_lease(state, store.order(state, pr, **{dispatch.EFFORT_KEY: "xhigh"})["id"])
    assert lifted[dispatch.EFFORT_KEY] == "xhigh", lifted[dispatch.LADDER_KEY]
    assert "the order asks xhigh" in lifted[dispatch.LADDER_KEY]["why"]
    # under a second goal, so the second-builder rule of DEC-0092 (2) is not what this measures
    other = state.capture("PR", dict(PR_FIELDS, title="second goal"))
    approve(state, other["id"], "scope")
    lowered = dispatch.create_lease(state, store.order(state, other, **{dispatch.EFFORT_KEY: "low"})["id"])
    assert lowered[dispatch.EFFORT_KEY] == "high", lowered[dispatch.LADDER_KEY]
    office, proc = store.project("o", "office-like", {"backend-developer": "sonnet"})
    capped = dispatch.create_lease(office, store.order(office, proc, **{dispatch.EFFORT_KEY: "xhigh"})["id"])
    assert capped[dispatch.EFFORT_KEY] == "high", capped[dispatch.LADDER_KEY]
    assert "capped at the kit's highest effort high" in capped[dispatch.LADDER_KEY]["why"]


# ================================================== 3. the vocabulary (DEC-0091 (3))

def test_an_order_rung_outside_the_ladder_and_an_effort_outside_the_vocabulary_are_refused(store):
    """DEC-0091 (3): refused at CREATION with the vocabulary named -- and again at the LEASE for
    an order re-planned into garbage while DRAFT, so no `update` slips past.

    RED WITHOUT `_assert_the_order_tiers_are_placeable`: the first two orders are created, and the
    garbage sits on a READY order until the first dispatch.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    with pytest.raises(DispatchError) as refusal:
        draft_order(state, pr, **{dispatch.RUNG_KEY: "haiku"})
    assert "haiku" in str(refusal.value) and "sonnet, opus, fable" in str(refusal.value), refusal.value
    with pytest.raises(DispatchError) as refusal:
        draft_order(state, pr, **{dispatch.EFFORT_KEY: "ultra"})
    assert "ultra" in str(refusal.value) and "low|medium|high|xhigh" in str(refusal.value), refusal.value
    assert list(state.iter_active_items("TSK")) == [], "a refused order was stored anyway"
    task = draft_order(state, pr)
    state.update_item(task["id"], {dispatch.RUNG_KEY: "haiku"})
    ready(state, task, pr)
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, task["id"])
    assert "haiku" in str(refusal.value) and "DRAFT" in str(refusal.value), refusal.value
    assert state.read_item(task["id"])["status"] == "READY", "the refused lease moved the order"


def test_a_kit_less_project_places_an_order_rung_against_the_reference_vocabulary(tmp_path):
    """This repository's own shape: no scaffold record, so the vocabulary is the tiers table beside
    the kernel package -- `opus` is placed, `haiku` is refused with that table named.

    RED WITHOUT the kit-less branch of `rung_vocabulary`: the ask is refused for want of a ladder
    (or, with the check dropped, `haiku` is stored). The reference row is found by its property
    (`_reference_rungs`: the row whose names are its model ids), and the shipped ladders' rungs
    are exactly that vocabulary -- the second assertion is the tripwire on the property.
    """
    (tmp_path / "project_memory").mkdir()
    state = ProjectState(str(tmp_path / "project_memory"))
    pr = state.capture("PR", dict(PR_FIELDS))
    approve(state, pr["id"], "scope")
    rungs, source = dispatch.rung_vocabulary(state)
    assert source.endswith(dispatch.TIERS_FILE), source
    for kit in kit_dirs():
        with io.open(os.path.join(kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
            declared = yaml.safe_load(handle)["rungs"]
        assert set(declared) <= set(rungs), (kit, declared, rungs)
    task = Store.order(state, pr, **{dispatch.RUNG_KEY: "opus"})
    assert dispatch.order_tiers(task) == ("opus", None)
    with pytest.raises(DispatchError) as refusal:
        Store.order(state, pr, **{dispatch.RUNG_KEY: "haiku"})
    assert dispatch.TIERS_FILE in str(refusal.value), refusal.value
    # a kit-less lease still carries no rung: the ask is recorded, the ladder is absent
    lease = dispatch.create_lease(state, task["id"])
    assert "absent" in lease[dispatch.LADDER_KEY] and dispatch.RUNG_KEY not in lease


def test_every_kit_ladder_declares_the_build_class_and_only_ordered_efforts():
    """Both ends of two declaration rules the light kit adds to `_valid_ladder`: every shipped
    ladder names the `build` class DEC-0092 (2) keys on and only efforts the ordering can compare
    (DEC-0091 (2)) -- and a declaration without either is REFUSED with the field named.

    RED WITHOUT the two checks: the mutated declarations below pass validation.
    """
    for kit in kit_dirs():
        with io.open(os.path.join(kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
            declared = yaml.safe_load(handle)
        assert dispatch.BUILD_CLASS in declared["classes"], kit
        assert set(declared["effort"].values()) <= set(dispatch.EFFORT_LEVELS), kit
        for role, rule in (declared.get("exceptions") or {}).items():
            if dispatch.EFFORT_KEY in rule:
                assert rule[dispatch.EFFORT_KEY] in dispatch.EFFORT_LEVELS, (kit, role)
    without_build = json.loads(json.dumps(LADDER))
    without_build["classes"].pop("build")
    without_build["roles"] = {role: cls for role, cls in without_build["roles"].items() if cls != "build"}
    with pytest.raises(DispatchError) as refusal:
        dispatch._valid_ladder("kit", without_build)
    assert "`build`" in str(refusal.value), refusal.value
    odd_effort = json.loads(json.dumps(LADDER))
    odd_effort["effort"]["large"] = "ultra"
    with pytest.raises(DispatchError) as refusal:
        dispatch._valid_ladder("kit", odd_effort)
    assert "ultra" in str(refusal.value) and "effort.large" in str(refusal.value), refusal.value


def test_the_create_task_command_accepts_the_two_asks_and_check_scopes_shows_them_beside_the_order(
        store, tmp_path):
    """The command surface (DEC-0091 (1)/(3)): `create-task --rung --effort` stores the ask, an
    effort outside the vocabulary is refused at the line, and `check-scopes` prints each order's
    ask beside it -- two parallel orders show their two rungs side by side.

    RED WITHOUT the two options: argparse refuses `--rung`; RED WITHOUT `asks_line`: the output
    names no rung.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    subprocess.run(["git", "init", "-q", str(tmp_path / "p")], check=True, capture_output=True)
    base = ["create-task", "--product-requirement", pr["id"], "--derives-from", pr["id"],
            "--type", "implementation", "--assigned-role", "backend-developer",
            "--acceptance-ref", "AC-1", "--expected-output", "src/x.py"]
    first = kernel(state, store, *base, "--allowed-scope", "src/api/", "--rung", "opus",
                   "--effort", "xhigh")
    assert first.returncode == 0, first.stdout + first.stderr
    second = kernel(state, store, *base, "--allowed-scope", "src/web/")
    assert second.returncode == 0, second.stdout + second.stderr
    refused = kernel(state, store, *base, "--allowed-scope", "src/x/", "--effort", "ultra")
    assert refused.returncode != 0 and "invalid choice" in refused.stderr, refused.stderr
    ids = [line.split()[0] for line in (first.stdout, second.stdout)]
    assert dispatch.order_tiers(state.read_item(ids[0])) == ("opus", "xhigh")
    assert dispatch.order_tiers(state.read_item(ids[1])) == (None, None)
    checked = kernel(state, store, "check-scopes")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "order %s under %s: asks rung opus, effort xhigh" % (ids[0], pr["id"]) in checked.stdout, checked.stdout
    assert "order %s under %s: no tier ask" % (ids[1], pr["id"]) in checked.stdout, checked.stdout
    assert "recorded: tasks/scope-checks/" in checked.stdout, checked.stdout


# ================================================== 4. the structural gate (DEC-0092 (2))

def test_a_second_build_lease_under_one_goal_needs_a_check_scopes_record(store):
    """DEC-0092 (2) / DEC-0087 (2) / PR-0011 AC-1: two DISJOINT build orders under one goal --
    the first leases, the second is refused until `check-scopes` has measured the pair, and the
    lease it then gets names the record it was admitted on.

    RED WITHOUT `_assert_a_second_builder_was_measured_locked`: the second lease is granted with
    no record anywhere (the overlap check alone lets disjoint pairs through, which is the habit
    the rule exists for).
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    first = store.order(state, pr)
    second = store.order(state, pr)
    dispatch.create_lease(state, first["id"])
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, second["id"])
    said = str(refusal.value)
    assert "SECOND builder" in said and "check-scopes" in said and first["id"] in said, said
    assert state.read_item(second["id"])["status"] == "READY", "the refused order was moved anyway"
    assert dispatch.LEASE_RUNG_FIELD not in state.read_item(second["id"]), "a refused lease wrote its answer"
    assert scopes.records(state) == []
    code, lines = scopes.check(state)
    assert code == 0, lines
    assert len(scopes.records(state)) == 1
    lease = dispatch.create_lease(state, second["id"])
    covered = lease[dispatch.MEASURED_DISJOINT_KEY]
    assert set(covered) == {first["id"]}, covered
    assert covered[first["id"]].startswith("tasks/scope-checks/"), covered
    assert os.path.isfile(os.path.join(state.root, covered[first["id"]]))
    assert dispatch.MEASURED_DISJOINT_KEY not in dispatch._read_lease(state, first["id"]), (
        "the FIRST builder's lease claims evidence it never needed")


def test_a_record_stops_covering_an_order_whose_scope_moved_since(store):
    """A record covers an order by DIGEST: re-scoped while DRAFT after the check, the order is
    unmeasured again and the second lease is refused until a new check ran.

    RED WITHOUT the digest comparison in `covering_record`: the stale record admits the re-scoped
    order.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    first = store.order(state, pr)
    second = draft_order(state, pr)
    dispatch.create_lease(state, first["id"])
    assert scopes.check(state)[0] == 0
    assert scopes.covering_record(state, first["id"], second["id"]) is not None
    state.update_item(second["id"], {"allowed_scope": ["src/order-2/**", "docs/**"]})
    assert scopes.covering_record(state, first["id"], second["id"]) is None
    ready(state, second, pr)
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, second["id"])
    assert "no check-scopes record" in str(refusal.value), refusal.value
    assert scopes.check(state)[0] == 0
    assert dispatch.create_lease(state, second["id"])[dispatch.MEASURED_DISJOINT_KEY]


def test_a_second_lease_of_another_class_or_under_another_goal_needs_no_record(store):
    """The rule's two edges, so it cannot be satisfied by refusing every second lease: a QA order
    beside a running builder is not a second BUILDER, and a builder under ANOTHER goal is the
    parallel form DEC-0087 (2) names -- neither asks for a record."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet", "quality-engineer": "sonnet"})
    dispatch.create_lease(state, store.order(state, pr)["id"])
    qa = dispatch.create_lease(state, store.order(state, pr, role="quality-engineer", type="review")["id"])
    assert qa[dispatch.LADDER_KEY]["role_class"] == "qa" and dispatch.MEASURED_DISJOINT_KEY not in qa
    other = state.capture("PR", dict(PR_FIELDS, title="second goal"))
    approve(state, other["id"], "scope")
    elsewhere = dispatch.create_lease(state, store.order(state, other)["id"])
    assert elsewhere[dispatch.LADDER_KEY]["role_class"] == "build"
    assert dispatch.MEASURED_DISJOINT_KEY not in elsewhere
    assert scopes.records(state) == [], "a lease that needed no record wrote one"


def test_a_kit_less_project_is_outside_the_second_builder_rule(tmp_path):
    """No ladder, no class, no rule: two disjoint orders under one goal both lease with no record
    -- said here rather than in the kernel's prose, so the reach of DEC-0092 (2) is a measurement."""
    (tmp_path / "project_memory").mkdir()
    state = ProjectState(str(tmp_path / "project_memory"))
    pr = state.capture("PR", dict(PR_FIELDS))
    approve(state, pr["id"], "scope")
    first, second = Store.order(state, pr), Store.order(state, pr)
    dispatch.create_lease(state, first["id"])
    lease = dispatch.create_lease(state, second["id"])
    assert "absent" in lease[dispatch.LADDER_KEY] and dispatch.MEASURED_DISJOINT_KEY not in lease


# ================================================== 5. the checkpoint (DEC-0092 (3))

def spawn_payload(repo, header, role, model):
    return {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": repo,
            "session_id": "s-1", "prompt_id": "p-1",
            "tool_input": {"subagent_type": role, "run_in_background": False, "model": model,
                           "prompt": header + "\nobjective: build\noutput: summary"}}


def shipped_spawn_gate(store, payload):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=payload["cwd"], HARNESS_KERNEL_PATH=TEAM_KITS,
               HOME=str(store.home), USERPROFILE=str(store.home))
    return subprocess.run([sys.executable, "-B", os.path.join(DEV_HOOKS, "gate_dispatch.py")],
                          input=json.dumps(payload), capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=60)


def test_the_shipped_spawn_gate_prints_the_four_line_checkpoint_and_never_blocks_on_it(store):
    """DEC-0092 (3): before a BUILDER starts, the kit's own `gate_dispatch.py` hands the model the
    four fact lines and the one question on the allowed call -- rc 0, `additionalContext`, audited
    as a note -- and hands a QA spawn nothing, because the habit mirrored is the builder count.

    RED WITHOUT `_mirror_the_builder_start`: rc 0 and an empty stdout for the builder. That a
    checkpoint which cannot be derived still exits 0 is the red-first rig's row (the derivation
    made to raise), not a case this test can produce against a healthy state.
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet", "quality-engineer": "sonnet"})
    repo = str(store.tmp_path / "p")
    builder = store.order(state, pr, **{dispatch.RUNG_KEY: "opus"})
    lease = dispatch.create_lease(state, builder["id"])
    result = shipped_spawn_gate(store, spawn_payload(repo, dispatch.dispatch_header(lease),
                                                     "backend-developer", lease[dispatch.RUNG_KEY]))
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]
    assert context["hookEventName"] == "PreToolUse"
    text = context["additionalContext"]
    assert builder["id"] in text and "DEC-0092 (3)" in text, text
    assert "(a) this goal is one set: 1 open order(s)" in text, text
    assert "(b) this order: 1 allowed-scope entry, 1 expected output(s), goal class normal" in text, text
    # ...and the FAIL-count derivation DEC-0096 (4) asks the checkpoint to SHOW, so a PM reading
    # "rung opus" on a retry can see whether the rung stood still because the effort moved instead.
    # RED WITHOUT the escalation sentence on the (c) line: the assertion below stops at the asks.
    # ...and the class's DEFAULT beside its FLOOR (DEC-0097 (3)), because the two differ exactly
    # where an ask can move the rung and a line showing one of them reads the same either way.
    # ...and the BAND only where the declaration gives one: this fixture's build class is the bare
    # rung `pin`, so the line says there is none instead of offering an ask the kernel would refuse
    # (verifier round 1). The banded case is
    # `tools/test_ladder.py::test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance`.
    assert ("(c) about to lease: rung opus, effort high -- the ladder for backend-developer starts "
            "on sonnet by default, with no band below it (pin sonnet, "
            "class build), top fable; the order asked rung opus / effort "
            "nothing; FAIL 0: rung +0, effort +0 -- this kit spends the first 0 failed run(s) of "
            "every 1 on the effort axis (DEC-0096)") in text, text
    assert "(d) last 1 order(s) by their latest lease" in text and "opus x 1" in text, text
    assert "efforts high x 1" in text, ("DEC-0097 (4): the distribution line shows both axes", text)
    # THE TWO SIGNALS AS THE MODEL RECEIVES THEM (DEC-0097 (3), FR-0091 precision 1): asserted
    # against the gate's OUTPUT and not against `CHECKPOINT_QUESTION`, which the line below
    # compares with itself. RED WITHOUT them: the question asks "does the rung fit" and leaves the
    # PM to guess which axis a failed run buys.
    for signal in ("confidently wrong no matter how much context you give it",
                   "skipped a file, not running the tests, or bailing on a refactor partway through"):
        assert signal in text, (signal, text)
    assert text.rstrip().endswith(dispatch.CHECKPOINT_QUESTION), text
    with io.open(os.path.join(state.root, ".audit", "hook_events.jsonl"), encoding="utf-8") as handle:
        assert "CHECKPOINT before builder %s" % builder["id"] in handle.read()
    assert "dispatched_at" in dispatch._read_lease(state, builder["id"]), "the mirrored spawn did not claim"
    qa = store.order(state, pr, role="quality-engineer", type="review")
    lease = dispatch.create_lease(state, qa["id"])
    result = shipped_spawn_gate(store, spawn_payload(repo, dispatch.dispatch_header(lease),
                                                     "quality-engineer", lease[dispatch.RUNG_KEY]))
    assert result.returncode == 0 and result.stdout.strip() == "", (result.stdout, result.stderr)


def test_the_mirror_still_exits_zero_when_its_audit_sink_is_gone(store, tmp_path):
    """B1 of the mid-goal check: the mirror stands AFTER the claim is spent, so a failure of its own
    -- here the audit sink raising -- may not become a refusal. The shipped hooks are copied and
    `_kernel.record_note` is made to raise in the copy; the gate is then run from there as a
    process: rc 0, and the context still written (it goes out BEFORE the note).

    RED WITHOUT the outer guard in `_mirror_the_builder_start`: `fail_closed` turns the raise into
    rc 2 with `dispatched_at` already set (measured so by the verifier before this line).
    """
    import shutil

    hooks = str(tmp_path / "hooks")
    shutil.copytree(DEV_HOOKS, hooks, ignore=shutil.ignore_patterns("__pycache__"))
    kernel_shim = os.path.join(hooks, "_kernel.py")
    with io.open(kernel_shim, encoding="utf-8", newline="") as handle:
        source = handle.read()
    anchor = "def record_note(hook, message):\n"
    assert source.count(anchor) == 1, "the hook helper moved; this test's mutation no longer lands"
    mutated = source.replace(anchor, anchor + '    raise RuntimeError("the audit sink is gone")\n')
    with io.open(kernel_shim, "w", encoding="utf-8", newline="") as handle:
        handle.write(mutated)
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    repo = str(store.tmp_path / "p")
    lease = dispatch.create_lease(state, store.order(state, pr)["id"])
    payload = spawn_payload(repo, dispatch.dispatch_header(lease), "backend-developer",
                            lease[dispatch.RUNG_KEY])
    env = dict(os.environ, CLAUDE_PROJECT_DIR=repo, HARNESS_KERNEL_PATH=TEAM_KITS,
               HOME=str(store.home), USERPROFILE=str(store.home))
    result = subprocess.run([sys.executable, "-B", os.path.join(hooks, "gate_dispatch.py")],
                            input=json.dumps(payload), capture_output=True, text=True,
                            encoding="utf-8", env=env, timeout=60)
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert "CHECKPOINT before builder" in json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "dispatched_at" in dispatch._read_lease(state, lease["task_id"]), "the spawn did not claim"


def test_a_newer_overlap_record_revokes_an_older_disjoint_verdict(store, tmp_path):
    """B3 of the mid-goal check: the record asked is the NEWEST one naming the pair, whatever it
    found. Two orders, unchanged in scope, measured disjoint first (with a seam declared on the
    check's line) and then overlapping (without it): the older disjoint verdict no longer covers.

    WHAT THIS SHAPE CANNOT SHOW, said rather than claimed: at the lease the LIVE file check
    (`_assert_no_running_lease_owns_the_same_file_locked`) sees the shared witness first and
    refuses on it -- the bound the mid-goal check measured as P4d. The structural gate's own
    reading is therefore asserted on `covering_record` directly, and the lease is asserted refused
    whichever of the two spoke.
    RED WITHOUT the "newest record naming the pair" reading in `covering_record`: the older record
    answers (`is None` fails).
    """
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    first = store.order(state, pr, allowed_scope=["src/**"])
    second = store.order(state, pr, allowed_scope=["src/shared/**", "docs/**"])
    dispatch.create_lease(state, first["id"])
    assert scopes.check(state, declared=["src/shared/**"])[0] == 0
    assert scopes.covering_record(state, first["id"], second["id"]) is not None
    assert scopes.check(state)[0] == 2, "without the seam the pair overlaps by witness"
    assert scopes.covering_record(state, first["id"], second["id"]) is None
    with pytest.raises(DispatchError):
        dispatch.create_lease(state, second["id"])
    assert state.read_item(second["id"])["status"] == "READY"


def test_a_check_scopes_record_about_closed_orders_is_dropped_at_the_next_run(store):
    """The bound on `tasks/scope-checks/`: a record none of whose orders is open any more answers
    nothing and goes at the next run; a record about a still-open order stays. RED WITHOUT
    `_drop_records_about_closed_orders`: three records remain."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    first, second = store.order(state, pr), store.order(state, pr)
    assert scopes.check(state)[0] == 0
    stale = scopes.records(state)[0]["path"]
    for task in (first, second):
        state.transition(task["id"], "CANCELLED")
        state.archive(task["id"])
    third, fourth = store.order(state, pr), store.order(state, pr)
    assert scopes.check(state)[0] == 0
    kept = [record["path"] for record in scopes.records(state)]
    assert stale not in kept and len(kept) == 1, kept
    assert set(scopes.records(state)[0]["orders"]) == {third["id"], fourth["id"]}


def test_the_reference_row_is_found_by_its_property_and_not_by_a_name(tmp_path):
    """B5 of the mid-goal check: `_reference_rungs` claims to find the reference row by the
    pass-through property. Against the shipped table a name-wired reader gives the same answer,
    so the claim is measured on SYNTHETIC tables: the pass-through row under another provider's
    name while `claude:` translates; the `rungs:` line as the order; zero and two pass-through
    rows refused; an order line that does not name the row's rungs refused.

    RED WITH `provider == "claude"` wired in: the first table answers claude's translating row.
    """
    def table(text):
        path = str(tmp_path / ("tiers-%d.yaml" % len(os.listdir(str(tmp_path)))))
        write(path, text)
        return path

    acme = table("rungs: [small, mid, big]\n"
                 "tiers:\n"
                 "  claude:\n    big: claude-big\n    mid: claude-mid\n    small: claude-small\n"
                 "    effort_field: effort\n"
                 "  acme:\n    big: big\n    mid: mid\n    small: small\n"
                 "    effort_field: reasoning\n")
    assert dispatch._reference_rungs(acme) == ("small", "mid", "big")
    with pytest.raises(DispatchError) as refusal:
        dispatch._reference_rungs(table("rungs: [a]\ntiers:\n  claude:\n    a: claude-a\n"
                                        "    effort_field: effort\n"))
    assert "0 pass-through rows" in str(refusal.value), refusal.value
    with pytest.raises(DispatchError) as refusal:
        dispatch._reference_rungs(table("rungs: [a]\ntiers:\n  one:\n    a: a\n    effort_field: e\n"
                                        "  two:\n    a: a\n    effort_field: e\n"))
    assert "2 pass-through rows" in str(refusal.value), refusal.value
    with pytest.raises(DispatchError) as refusal:
        dispatch._reference_rungs(table("rungs: [big, mid]\ntiers:\n  acme:\n    big: big\n"
                                        "    mid: mid\n    small: small\n    effort_field: e\n"))
    assert "`rungs:` line" in str(refusal.value), refusal.value
    # ...and the shipped table's order is low -> high (B4): the kit-less vocabulary indexes like a ladder
    shipped = dispatch._reference_rungs(os.path.join(TEAM_KITS, dispatch.TIERS_FILE))
    for kit in kit_dirs():
        with io.open(os.path.join(kit, dispatch.LADDER_FILE), encoding="utf-8") as handle:
            declared = yaml.safe_load(handle)["rungs"]
        assert [rung for rung in shipped if rung in declared] == list(declared), (kit, shipped, declared)


def test_the_two_name_split_is_what_keeps_a_climbed_order_from_climbing_twice(store):
    """P7 of the mid-goal check: the reason `rung`/`effort` on a task are the ASK and the lease's
    answer lands under `lease_rung` is the double climb -- and on the shipped three rungs `top`
    hides it, so it is measured on a SIX-rung ladder: one FAILED run per lease, and the rungs the
    order runs on are r1, r2, r3, r4 -- one step each. RED WITH the answer written back under
    `rung` (rig row M16): r1, r2, r4, r5.
    """
    six = dict(LADDER, rungs=["r1", "r2", "r3", "r4", "r5", "r6"], top="r6",
               classes=dict(LADDER["classes"], design="r2", qa="r2"))
    store.kit("six", ladder=six)
    state, pr = store.project("p", "six", {"backend-developer": "r1"})
    task = store.order(state, pr)
    climbed = [dispatch.create_lease(state, task["id"])[dispatch.RUNG_KEY]]
    for _round in range(3):
        drive_task_to(state, task["id"], "FAILED")
        state.transition(task["id"], "READY", approved_retry=True)
        climbed.append(dispatch.create_lease(state, task["id"])[dispatch.RUNG_KEY])
    assert climbed == ["r1", "r2", "r3", "r4"], climbed


# ================================================== 5. the pilot rig (DEC-0092 (6); AC-1, AC-5, AC-8, AC-12)

def test_the_pilot_rig_leases_three_orders_of_different_size_per_kit(tmp_path):
    """DEC-0092 (6) / PR-0011 AC-12: `tools/light_kit_pilot.py`, run as the process it is, on a
    project per kit scaffolded by the kit's OWN installer from a store copy under a HOME of its
    own. Per kit: the smallest preset is what got installed (AC-5, the entry files' default); the
    lead's code write is refused by the registered Edit|Write chain (AC-1); three orders of
    obviously different size lease inside the kit's ladder, so the
    office bookkeeper's `fable`/`xhigh` ask lands on its `opus`/`high` ceiling (DEC-0078) -- and in
    dev and research the SMALL order's `sonnet` ask no longer reaches sonnet at all, because
    DEC-0095 (1) starts the `build` class on opus and an ask never lowers a floor (DEC-0091 (2)).
    That last row is the measured price of the builder default and is named in TSK-0136's protocol;
    the second
    builder is refused without a check-scopes record and admitted on one, named on its lease; the
    shipped spawn gate prints the four-line checkpoint with rc 0; the auditor runs on the routine
    route from the entry point with no writable scope (AC-8), and the goal's presented approval is
    untouched by that mint.

    THE STAMP IS THE PRECONDITION: the installer refuses a store that does not hash to its own
    VERSION, so this test is red on an unstamped tree -- which is what "run at every stamp that
    touches the ladder or the lead texts" means in this suite.
    """
    out = str(tmp_path / "pilots")
    result = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "tools", "light_kit_pilot.py"),
                             "--out", out], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=900)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    with io.open(os.path.join(out, "light_kit_pilot.log.json"), encoding="utf-8") as handle:
        log = json.load(handle)
    assert set(log["kits"]) == {os.path.basename(kit) for kit in kit_dirs()}
    for kit, record in log["kits"].items():
        assert "scaffold_error" not in record, (kit, record.get("scaffold_error", {}).get("err", "")[-600:])
        preset = record["smallest_preset"]
        assert set(preset["installed_roles"]) >= set(preset["roles"]), (kit, preset)
        assert record["lead_code_write"]["rc"] == 2, (kit, record["lead_code_write"])
        assert record["second_builder_without_record"]["rc"] != 0, (kit, record["second_builder_without_record"])
        assert "no check-scopes record" in record["second_builder_without_record"]["stderr"], kit
        sizes = {order["size"]: order for order in record["orders"]}
        assert set(sizes) == {"small", "medium", "large"} and all(o["dispatch"]["rc"] == 0 for o in sizes.values()), (
            kit, {size: o.get("dispatch") for size, o in sizes.items()})
        rungs = [sizes[size]["leased"][dispatch.LEASE_RUNG_FIELD] for size in ("small", "medium", "large")]
        efforts = [sizes[size]["leased"][dispatch.LEASE_EFFORT_FIELD] for size in ("small", "medium", "large")]
        if kit == "office-team":
            # office keeps DEC-0078's floors (`build: pin`), so its small order still reaches sonnet
            assert rungs == ["sonnet", "opus", "opus"] and efforts == ["high", "high", "high"], (rungs, efforts)
        else:
            assert rungs == ["opus", "opus", "fable"] and efforts == ["high", "high", "xhigh"], (rungs, efforts)
            # ...and the first row is the class DEFAULT beating the ASK, not an ask of opus: the rig
            # asks sonnet for the small order, and after DEC-0097 (2) that ask is inside the build
            # class's band (default opus, floor pin) -- so what refuses it here is the ACCEPTANCE,
            # and the ladder line says so on a scaffolded project rather than in a fixture. The
            # rig's small order owes `src/small/README.md` and names AC-1 ("done"): a description,
            # no test. RED WITHOUT the test condition: this row leases sonnet and the sentence is
            # absent -- the cheap rung handed to an order with no pass/fail oracle.
            assert sizes["small"]["ask"][dispatch.RUNG_KEY] == "sonnet", sizes["small"]["ask"]
            assert "refused: the acceptance names no test, only a description" in \
                sizes["small"]["dispatch"]["ladder_line"], sizes["small"]["dispatch"]
        assert sizes["small"]["measured_disjoint"] is None, "the first builder carries evidence it never needed"
        assert sizes["medium"]["measured_disjoint"] and sizes["large"]["measured_disjoint"], kit
        checkpoint = record["checkpoint"]
        assert checkpoint["rc"] == 0 and len(checkpoint["lines"]) == 6, (kit, checkpoint)
        assert checkpoint["lines"][1].startswith("(a) ") and checkpoint["lines"][4].startswith("(d) "), checkpoint
        audit = record["auditor_route"]
        assert audit["request_rc"] == 0 and audit["create_rc"] == 0 and audit["dispatch"]["rc"] == 0, (kit, audit)
        assert audit["allowed_scope"] == [] and "Rolle: project-auditor" in audit["question"], (kit, audit)
        assert audit["root_approval_ref_after_mint"] == "APR-0001", (kit, audit)


# ================================================== 5a. the texts (AC-4): the cadence, read off the kit texts

def _lead_and_constitution_texts():
    """Every kit's constitution and lead skill -- the texts that order verification rounds."""
    import glob

    for constitution in sorted(glob.glob(os.path.join(TEAM_KITS, "*", "constitution", "AGENTS.md"))):
        kit = os.path.dirname(os.path.dirname(constitution))
        yield constitution
        for skill in sorted(glob.glob(os.path.join(kit, "skills", "*", "SKILL.md"))):
            with io.open(skill, encoding="utf-8") as handle:
                head = handle.read(600)
            if "name: project-manager" in head or "name: office-manager" in head:
                yield skill


# A sentence that ORDERS a verifier round after every rework / change, without a negation in it. The
# subject words are a vocabulary (a reader over prose has no other footing), so both ends are
# measured below: the sentence the light form removed must be caught, the cadence sentence that
# says "not after every rework" must not.
_VERIFIER_RX = re.compile(r"verif|review(er)? round|QA round|Pr(ü|u|ue)fer", re.IGNORECASE)
_EVERY_REWORK_RX = re.compile(r"after (every|each) (rework|change|fix|iteration)|jede[rn]? Nacharbeit",
                              re.IGNORECASE)
# THE NEGATED ORDER, not any negation word: "…runs the whole package again, and this is NOT
# optional" is an order with a "not" in it (the goal-round verifier's AC-4 b, measured GREEN under
# the wider reader), so what excuses a sentence is a negated verb of ordering or a negated verifier.
_NEGATED_RX = re.compile(
    r"\b(do|does|should|will|shall|may|must) not\b|\bnever\b|"
    r"\bno (separate |second )?(verifier|reviewer|review|QA|Pr(ü|u|ue)fer)\b|"
    r"\bkein(e[nr]?)? (Pr(ü|u|ue)fer|Review)\b", re.IGNORECASE)


def _orders_a_verifier_after_every_rework(text):
    """The sentences that order it -- split at sentence ends, each judged on its own words."""
    found = []
    for sentence in re.split(r"(?<=[.;!?])\s+", re.sub(r"\s+", " ", text)):
        if _VERIFIER_RX.search(sentence) and _EVERY_REWORK_RX.search(sentence) and not _NEGATED_RX.search(sentence):
            found.append(sentence.strip())
    return found


def test_no_kit_text_still_orders_a_verifier_after_every_rework():
    """PR-0011 AC-4 (DEC-0088 cadence): the verifier runs at the GOAL -- one round, one rework, one
    short second round -- and no kit text may order one after every rework any more. Every
    constitution and lead skill is read sentence by sentence; a sentence that names a verifier round
    and "after every rework/change" without a negation is red. The cadence itself has to be present
    in every lead text as well, so a kit that simply says nothing is red too.
    RED on the sentence `test_the_cadence_reader_can_tell_an_order_from_its_negation` measures.
    """
    offenders, judged = {}, 0
    for path in _lead_and_constitution_texts():
        judged += 1
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        found = _orders_a_verifier_after_every_rework(text)
        if found:
            offenders[os.path.relpath(path, ROOT)] = found
        # whitespace-flattened: the constitutions wrap "one rework" across a line break
        flat = re.sub(r"\s+", " ", text).lower()
        assert "dec-0088" in flat and "one rework" in flat, (
            "%s carries no cadence at the goal" % os.path.relpath(path, ROOT))
    assert judged >= 6, judged
    assert not offenders, offenders


def test_the_cadence_reader_can_tell_an_order_from_its_negation():
    """Both ends, including the two the goal round found open: an order that happens to carry a
    "not" (AC-4 b) is still an order, and the ASCII transliteration the codex twin is written in
    (`Pruefer`, AC-4 c) is still a verifier."""
    caught = "After every rework the verifier runs the whole package again."
    not_optional = "After every rework the verifier runs the whole package again, and this is NOT optional."
    transliterated = "Der Pruefer laeuft nach jeder Nacharbeit erneut."
    negated = "You do not order a verifier after every rework -- that was the measured cost driver."
    no_separate = "A small change gets no separate verifier after every change."
    assert _orders_a_verifier_after_every_rework(caught) == [caught]
    assert _orders_a_verifier_after_every_rework(not_optional) == [not_optional]
    assert _orders_a_verifier_after_every_rework(transliterated) == [transliterated]
    assert _orders_a_verifier_after_every_rework(negated) == []
    assert _orders_a_verifier_after_every_rework(no_separate) == []


# ================================================== 6. the approval question (AC-7) and the auditor route (AC-8)

def test_every_approval_kind_has_one_plain_word_label_and_no_label_is_orphaned():
    """BUG-0271 AC-3: the kind-to-label table beside the enum has its two-sided tripwire -- a kind
    without a label is refused by `kind_label`, a label without a kind is dead. RED WITHOUT either
    end: a kind added to `APR_KINDS` without a label, or a label left behind by a removed kind."""
    from kernel import approvals

    assert set(approvals.KIND_LABELS) == set(approvals.APR_KINDS), (
        set(approvals.KIND_LABELS) ^ set(approvals.APR_KINDS))
    assert len(set(approvals.KIND_LABELS.values())) == len(approvals.KIND_LABELS), "two kinds share a label"
    for kind in approvals.APR_KINDS:
        assert approvals.kind_label(kind) == approvals.KIND_LABELS[kind]
        # the label is the user's word, not the enum value; `Plan` is German for `plan` and is the
        # one label that coincides with its kind up to the capital
        assert approvals.KIND_LABELS[kind] != kind, kind
    with pytest.raises(approvals.ApprovalError) as refusal:
        approvals.kind_label("vibes")
    assert "KIND_LABELS" in str(refusal.value)


def _placeholder_manifest(builder):
    """A manifest shaped like a line builder's, out of its own signature: a list where the key is
    plural, a goal record for `goals`, a string otherwise -- the keys the target forms read. The
    builder itself is not called: several validate their values (a proposal path, a head), and
    what is measured here is the SENTENCE, not the builder."""
    import inspect

    from kernel import approvals

    values = {}
    for name in inspect.signature(builder).parameters:
        if name == "goals":
            values[name] = [{approvals.GOAL_ITEM_FIELD: "PR-0001", "title": "Kasse", "revision": 1}]
        elif name.endswith("s"):
            values[name] = ["x-%s" % name]
        else:
            values[name] = "x-%s" % name
    return values


def test_no_approval_question_shows_an_english_enum_word_a_hash_or_a_path():
    """BUG-0271 AC-1 / PR-0011 AC-7: the question a non-developer answers names the kind in plain
    words, the item by its title and a manifest with German labels; the manifest hash, the
    request's file path and the second request id are in the approving option's DESCRIPTION,
    which the gate still compares. Every kind is rendered, the request marker is the one machine
    token left in the sentence (the gate resolves the request by it), and a checksum a target form
    shows on purpose stands behind the word "Prüfsumme" -- an unlabelled hex run is red.

    RED WITHOUT the label table in `build_question`: `scope`, `routine` and `kit_update` stand in
    the sentence as English enum words; RED WITHOUT the move: the hash prefix stands in it.
    """
    import re

    from kernel import approvals

    marker = re.compile(r" \[APR-REQ:[0-9a-f]{32}\]$")
    hexes = re.compile(r"(?<![0-9a-f])[0-9a-f]{12,}")
    for kind in approvals.APR_KINDS:
        request = {"request_id": "ab" * 16, "kind": kind, "item": None, "revision": None,
                   "item_title": "", "mint_code": "c0ffee", "subject_manifest": {}}
        builder = approvals.LINE_MANIFEST_BUILDERS.get(kind)
        if builder is not None:
            request["subject_manifest"] = _placeholder_manifest(builder)
        if kind in approvals.item_derived_kinds() or kind == approvals.ROUTINE_KIND:
            request.update(item="PR-0001", item_title="Kasse mit Bon", revision=2)
        if kind == "analysis":
            request["subject_manifest"] = {"question": "warum langsam", "scope": "nur lesen",
                                           "expected_result": "ein Befund", "tasks": ["TSK-0001"]}
        if kind in approvals.EXPIRING_KINDS:
            request["subject_manifest"][approvals.EXPIRY_FIELD] = 1_800_000_000.0
        request["subject_manifest_hash"] = "deadbeef" * 8
        question = approvals.build_question(request)
        sentence = question["question"]
        assert marker.search(sentence), sentence
        body = marker.sub("", sentence)
        assert body.startswith("Freigabe erbeten: %s für " % approvals.KIND_LABELS[kind]), body
        for enum_word in approvals.APR_KINDS:
            assert not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(enum_word), body), (kind, enum_word, body)
        assert "approvals/pending" not in body and "sha256" not in body, body
        for run in hexes.finditer(body):
            assert body[:run.start()].endswith("Prüfsumme "), (kind, run.group(0), body)
        if request["item"]:
            assert "„Kasse mit Bon“ (PR-0001)" in body and "(Revision 2)" in body, body
        for field in request["subject_manifest"]:
            if builder is None or kind not in approvals.TARGET_FORMS:
                assert "%s:" % field not in body, (kind, field, body)
        approving = question["options"][0]["description"]
        assert request["subject_manifest_hash"][:approvals.DIGEST_SHOWN] in approving
        assert "approvals/pending/%s.yaml" % request["request_id"] in approving
        assert approvals.KIND_LABELS[kind] in approving


def test_the_auditor_runs_on_the_routine_route_from_the_command_line_without_a_writable_scope(tmp_path):
    """PR-0011 AC-8 (BUG-0266 / H184), end to end on the command surface: `request-approval
    routine <ROOT> --role ... --expires-in-days` opens a German question that names the role and
    the date; the user's answer mints it (through the shipped hook); `create-task --read-only`
    is a work order with no writable scope; `dispatch` leases it on the routine approval -- and
    the goal's presented scope approval is untouched, so a builder under the same goal still
    leases beside the audit.

    RED WITHOUT the routine branch of `request-approval`: the kind is not on the parser; RED
    WITHOUT `--read-only`: `create-task` demands `--allowed-scope`; RED WITHOUT
    `approvals.presents`: the builder's lease is refused after the routine mint.
    """
    from conftest import mint_via_hook
    from kernel import approvals

    (tmp_path / "project_memory").mkdir()
    state = ProjectState(str(tmp_path / "project_memory"))
    pr = state.capture("PR", dict(PR_FIELDS, title="Kasse mit Bon"))
    approve(state, pr["id"], "scope")
    env = dict(os.environ, PYTHONPATH=TEAM_KITS)

    def kernel_cli(*args):
        return subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", state.root] + list(args),
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)

    without_term = kernel_cli("request-approval", "routine", pr["id"], "--role", "project-auditor",
                              "--scope", "project_memory/**", "--trigger", "weekly", "--cadence", "weekly")
    assert without_term.returncode != 0 and "expires-in-days" in without_term.stderr, without_term.stderr
    asked = kernel_cli("request-approval", "routine", pr["id"], "--role", "project-auditor",
                       "--scope", "project_memory/**", "--trigger", "weekly + after kit update",
                       "--cadence", "weekly", "--expires-in-days", "30")
    assert asked.returncode == 0, asked.stdout + asked.stderr
    question = json.loads(asked.stdout)
    sentence = question["question"]
    assert sentence.startswith("Freigabe erbeten: %s für „Kasse mit Bon“ (%s)"
                               % (approvals.KIND_LABELS["routine"], pr["id"])), sentence
    assert "Rolle: project-auditor" in sentence and "gültig bis: " in sentence, sentence
    request_id = sentence.rsplit("[APR-REQ:", 1)[1].rstrip("]")
    request = approvals.pending_request(state, request_id)
    mint_via_hook(state, request)
    routine = sorted(name for name in os.listdir(os.path.join(state.root, "approvals"))
                     if name.startswith("APR-"))[-1][:-5]
    assert approvals.read_apr(state, routine)["kind"] == "routine"
    assert state.read_item(pr["id"])["approval_ref"] != routine, "the routine displaced the scope approval"

    base = ["create-task", "--product-requirement", pr["id"], "--derives-from", pr["id"],
            "--type", "analysis", "--assigned-role", "project-auditor", "--acceptance-ref", "AC-1",
            "--expected-output", "staging/audit/findings.md"]
    neither = kernel_cli(*base)
    assert neither.returncode != 0 and "--read-only" in neither.stderr, neither.stderr
    both = kernel_cli(*base, "--allowed-scope", "src/", "--read-only")
    assert both.returncode != 0 and "both were given" in both.stderr, both.stderr
    created = kernel_cli(*base, "--read-only")
    assert created.returncode == 0, created.stdout + created.stderr
    audit_id = created.stdout.split()[0]
    assert state.read_item(audit_id)["allowed_scope"] == []
    state.transition(audit_id, "READY")
    satisfy_the_architect_step(state, state.read_item(audit_id), state.read_item(pr["id"]))
    leased = kernel_cli("dispatch", audit_id)
    assert leased.returncode == 0, leased.stdout + leased.stderr
    assert leased.stdout.startswith(dispatch.HEADER_PREFIX)
    # ...and the builder under the same goal still leases on the goal's own scope approval
    builder = Store.order(state, pr)
    assert dispatch.create_lease(state, builder["id"])["task_id"] == builder["id"]


def _tool_input_keys_the_gate_reads(path):
    """Every `tool_input.get("<key>")` in a hook's source -- the spawn surface it judges."""
    import ast

    with io.open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    keys = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "tool_input" and node.args
                and isinstance(node.args[0], ast.Constant)):
            keys.add(node.args[0].value)
    return keys


def test_no_spawn_or_lease_surface_carries_a_free_text_justification_field(store):
    """DEC-0092 (1) / PR-0011 AC-12: no free-text justification field anywhere on the way from an
    order to a running builder. The surfaces are read off the running code and held CLOSED, so a
    required "why" -- or any other new field -- on any of them is red on purpose; a new key there
    means re-deciding DEC-0092 (1), not editing this set.

    What is held: the keys the shipped spawn gate reads off the tool input, the keys `parse_header`
    decides on, the parameters of `create_lease` / `validate_dispatch`, the REQUIRED options of
    `create-task` (every one a contract field) and the TSK contract's required fields.
    """
    import inspect

    from kernel.cli import build_parser

    assert _tool_input_keys_the_gate_reads(os.path.join(DEV_HOOKS, "gate_dispatch.py")) == {
        "prompt", "subagent_type", "model"}
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    lease = dispatch.create_lease(state, store.order(state, pr)["id"])
    assert set(dispatch.parse_header(dispatch.dispatch_header(lease))) == {"task_id", "root_revision", "lease"}
    assert list(inspect.signature(dispatch.create_lease).parameters) == ["state", "task_id", "ttl", "worktree"]
    assert list(inspect.signature(dispatch.validate_dispatch).parameters) == [
        "state", "header", "subagent_type", "claim", "prompt_id", "session_id", "spawn_model"]
    parser = build_parser()._subparsers._group_actions[0].choices["create-task"]
    # a required option feeds a contract field under its dest (`acceptance_refs`) or under its own
    # spelling (`--type` -> `type`, dest `task_type`); one of the two has to be the field
    contract = set(backlog_types.REQUIRED_FIELDS["TSK"])
    strangers = [action.option_strings for action in parser._actions if action.required
                 and not ({action.dest, action.option_strings[0].lstrip("-").replace("-", "_")} & contract)]
    assert not strangers, "required options that feed no contract field: %s" % strangers
    assert set(backlog_types.REQUIRED_FIELDS["TSK"]) == {
        "product_requirement", "root_revision", "derives_from", "type", "assigned_role",
        "acceptance_refs", "required_inputs", "allowed_scope", "forbidden_scope",
        "expected_outputs", "dependencies"}


def test_the_checkpoints_first_line_counts_the_goals_measured_disjoint_sets(store, tmp_path):
    """Line (a) is a statement about FILE OWNERSHIP: three open orders of which two share a file
    are two sets, and the line says which orders form each. RED WITHOUT `goal_partition`'s
    union over overlapping pairs: three orders read as three sets."""
    store.kit("kit")
    state, pr = store.project("p", "kit", {"backend-developer": "sonnet"})
    repo = str(store.tmp_path / "p")
    subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True)
    write(os.path.join(repo, "src", "shared", "a.py"), "x\n")
    alone = store.order(state, pr, allowed_scope=["src/alone/**"])
    left = store.order(state, pr, allowed_scope=["src/shared/**"])
    right = store.order(state, pr, allowed_scope=["src/shared/a.py"])
    assert scopes.goal_partition(state, pr["id"]) == [[alone["id"]], sorted([left["id"], right["id"]])]
    lease = dispatch.create_lease(state, alone["id"])
    lines = dispatch.reflection_checkpoint(state, state.read_item(alone["id"]), pr, lease)
    assert lines[0] == ("(a) this goal splits into 2 disjoint sets among 3 open order(s) (computed now; a "
                        "second builder still needs a check-scopes record): %s; %s + %s"
                        % (alone["id"], left["id"], right["id"])), lines[0]
    # B6 of the mid-goal check: the line is bounded like the check's printout -- above
    # `scopes.PATHS_SHOWN` open orders the groups are a count, not a list in the model's context
    for _more in range(scopes.PATHS_SHOWN):
        store.order(state, pr)
    lines = dispatch.reflection_checkpoint(state, state.read_item(alone["id"]), pr, lease)
    assert lines[0].startswith("(a) this goal splits into %d disjoint sets among %d open order(s)"
                               % (2 + scopes.PATHS_SHOWN, 3 + scopes.PATHS_SHOWN)), lines[0]
    assert lines[0].endswith("not listed above %d open orders" % scopes.PATHS_SHOWN), lines[0]
    assert len(lines[0]) < 200, len(lines[0])

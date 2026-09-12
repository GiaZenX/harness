"""Tests for the approval protocol + dispatch leases (HARNESS_V2_SPEC.md II.2/II.4)."""
import ast
import contextlib
import inspect
import io
import json
import os
import pathlib
import re
import shutil
import sys
import time

import pytest

TEAM_KITS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits")
sys.path.insert(0, TEAM_KITS)

from conftest import (  # noqa: E402 -- shared suite helpers
    approve,
    drive_task_to,
    mint_via_hook,
    satisfy_the_architect_step,
)
from kernel import approvals, backlog_types, checkpoints, cli, dispatch, hashing, staging  # noqa: E402
from kernel.approvals import ApprovalError  # noqa: E402
from kernel.backlog_types import ACTIVE_DIRS  # noqa: E402
from kernel.dispatch import DispatchError  # noqa: E402
from kernel.state import ProjectState, names_a_drive  # noqa: E402


PR_FIELDS = {
    "title": "Checkout flow",
    "class": "normal",
    "problem": "no checkout",
    "goal": "working checkout",
    "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
    "invariants": [],
    "out_of_scope": [],
    "priority": "high",
}

TSK_FIELDS = {
    "derives_from": "PR-0001",
    "type": "implementation",
    "assigned_role": "backend-developer",
    "acceptance_refs": ["AC-1"],
    "required_inputs": [],
    "allowed_scope": ["src/"],
    "forbidden_scope": ["secrets/"],
    "expected_outputs": ["src/x.py"],
    "dependencies": [],
}


@pytest.fixture
def state(tmp_path):
    """A bare state directory -- and since DEC-0079 that is a project the architect step IS asked of.

    THE DUTY IS READ OFF THE KIT'S DELIVERY, not off this directory: no scaffold record here names
    a kit, so the reader cannot say which kit runs, and it fails CLOSED. That is why every test in
    this file about the duty still meets it. A first cut of DEC-0074 asked the project's own stock
    and this fixture created `system/active` for it; that line is gone, because it would teach the
    next reader a rule the kernel does not have (merge verify round 2, R2-B1/R2-B2).

    Both directions of the rule that IS built have their own node:
    `test_the_architect_step_is_owed_by_the_kits_delivery_not_the_projects_stock`.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    return ProjectState(str(root))


def approve_scope(state, item_id):
    return approve(state, item_id, "scope")



def a_scope_of_its_own(state):
    """A writable scope no other order in this store owns.

    SINCE C-2 (PR-0005 AC-5) two LIVE leases over one path are refused, and most tests in this file
    are about something else entirely -- the approval routes, the bind window, the idle findings.
    Giving each order its own subdirectory keeps them measuring what they are about; the tests that
    measure the overlap rule itself set their scopes deliberately
    (`tools/test_parallel_streams.py::test_the_second_lease_is_refused_when_the_scopes_overlap`).
    """
    return ["src/order-%d/**" % (len(list(state.iter_active_items("TSK"))) + 1)]


def make_ready_task(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=pr["id"],
                                            allowed_scope=a_scope_of_its_own(state)))
    state.transition(task["id"], "READY")
    # ...and the architect step the goal's class asks for (FR-0085) -- through the kernel's own
    # predicate, so this helper cannot walk past a duty `create_lease` cannot walk past.
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    return pr, state.read_item(task["id"])


# -- approval protocol ---------------------------------------------------------

def test_a_status_an_approval_commits_is_an_approved_status():
    """`approved_statuses` must not contradict its own first sentence — for ANY type.

    The property, over every (type, kind) pair in `APPROVAL_TRANSITIONS` rather than over PROC
    alone: the status an approval WALKS AN ITEM INTO is by definition a status the item stands in
    because a user approved it, so it has to be in the answer. The first cut subtracted every
    terminal and therefore dropped `ACCEPTED` from PR and RQ — the exact status an `acceptance`
    approval commits — while `PROC`, whose terminals all lie off its chain, agreed with both
    readings and hid it. Its only consumer today is the office spawn gate, so this was latent, not
    live; a check over the pairs is what keeps it that way.

    The counter-direction is asserted too, so "return every state" cannot satisfy it: a terminal
    NO approval targets stays out (`PROC` RETIRED, `BUG` VERIFIED, `CR` APPLIED, `EXP` ANALYZED),
    and a type nothing approves answers with nothing.
    """
    for (item_type, kind), (_source, target) in approvals.APPROVAL_TRANSITIONS.items():
        answer = approvals.approved_statuses(item_type)
        assert target in answer, (
            "%s %s commits %s -> %s, but %s is not an approved status of %s"
            % (item_type, kind, _source, target, target, item_type))
    for item_type, automaton in backlog_types.AUTOMATA.items():
        answer = approvals.approved_statuses(item_type)
        targets = {edge[1] for (typ, _kind), edge in approvals.APPROVAL_TRANSITIONS.items()
                   if typ == item_type}
        assert not (answer & (automaton.terminals - targets)), (
            "%s: a terminal no approval targets is not an approved status" % item_type)
        if not targets:
            assert answer == frozenset(), item_type
    assert approvals.approved_statuses("INV") == frozenset()
    assert approvals.approved_statuses("EVD") == frozenset()


def test_scope_approval_happy_path(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    apr = approve_scope(state, pr["id"])
    item = state.read_item(pr["id"])
    assert item["approval_ref"] == apr["id"]
    assert item["status"] == "APPROVED"  # (PR, scope) side-effect transition
    assert apr["revision"] == 1 and apr["revoked"] is False
    # request consumed, auditable
    assert os.path.exists(os.path.join(state.root, "approvals", "consumed", apr["request_id"] + ".yaml"))
    assert not os.path.exists(os.path.join(state.root, "approvals", "pending", apr["request_id"] + ".yaml"))


def test_question_is_deterministic_and_marked(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    q1 = approvals.build_question(request)
    q2 = approvals.build_question(request)
    assert q1 == q2
    assert "[APR-REQ:%s]" % request["request_id"] in q1["question"]
    assert q1["options"][0]["label"] == approvals.approve_label(request["mint_code"])
    assert [o["label"] for o in q1["options"][1:]] == ["Ändern", "Ablehnen"]
    assert len(request["mint_code"]) == 6  # per-request entropy (S2b)
    # SECRECY INVARIANT: the code must live ONLY in the approval option label --
    # leaking it into the question/header/descriptions would destroy the whole
    # mechanism (a user could then retype it without ever clicking)
    exposed = q1["question"] + q1["header"] + "".join(o["description"] for o in q1["options"])
    assert request["mint_code"] not in exposed


def test_free_text_freigeben_never_mints(state):
    """S2b amendment: the platform cannot distinguish a clicked option from
    'Other'-typed text (verified 2026-07-24) -- the per-request mint code does:
    a plain typed 'Freigeben' never mints."""
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    for typed in ("Freigeben", "freigeben", "ja", "ok, passt", "Freigeben [000000]"):
        with pytest.raises(ApprovalError, match="does not mint"):
            approvals.mint(state, request["request_id"], typed)
    # request survives until TTL (no auto-invalidation)
    assert os.path.exists(os.path.join(state.root, "approvals", "pending", request["request_id"] + ".yaml"))


def test_label_of_another_request_never_mints(state):
    """Cross-request: a VALID label only mints ITS own request."""
    pr_a = state.capture("PR", dict(PR_FIELDS))
    pr_b = state.capture("PR", dict(PR_FIELDS))
    req_a = approvals.create_pending_request(state, "scope", pr_a["id"])
    req_b = approvals.create_pending_request(state, "scope", pr_b["id"])
    assert req_a["mint_code"] != req_b["mint_code"]
    with pytest.raises(ApprovalError, match="does not mint"):
        approvals.mint(state, req_a["request_id"], approvals.approve_label(req_b["mint_code"]))


def test_apr_records_mint_code(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    mint_via_hook(state, request)
    apr = _latest_apr(state)
    assert apr["mint_code"] == request["mint_code"]  # spec II.2 APR field list


def test_request_without_mint_code_fails_closed(state):
    """Pre-amendment or hand-written pending file -> refuse, never mint."""
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    path = os.path.join(state.root, "approvals", "pending", request["request_id"] + ".yaml")
    import yaml
    original = yaml.safe_load(open(path, encoding="utf-8"))
    for broken in ("__delete__", None, "", "TOOLONG", "ZZZZZZ"):
        raw = dict(original)
        if broken == "__delete__":
            del raw["mint_code"]
        else:
            raw["mint_code"] = broken
        yaml.safe_dump(raw, open(path, "w", encoding="utf-8"), sort_keys=False, allow_unicode=True)
        # the guessable label a malformed code would produce must not mint either
        for attempt in ("Freigeben [abc123]", "Freigeben [None]", "Freigeben []",
                        "Freigeben [%s]" % broken):
            with pytest.raises(ApprovalError, match="no valid mint_code"):
                approvals.mint(state, request["request_id"], attempt)


def test_aendern_and_ablehnen_never_mint(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    for label in ("Ändern", "Ablehnen"):
        with pytest.raises(ApprovalError):
            approvals.mint(state, request["request_id"], label)


def test_expired_request_never_mints(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"], ttl_seconds=0.01)
    time.sleep(0.05)
    with pytest.raises(ApprovalError, match="expired"):
        approvals.mint(state, request["request_id"], approvals.approve_label(request["mint_code"]))


def test_unknown_request_never_mints(state):
    with pytest.raises(ApprovalError, match="never mint"):
        approvals.mint(state, "deadbeef", "Freigeben [x]")


def test_out_of_band_edit_kills_mint(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    state.update_item(pr["id"], {"goal": "changed after the question"})
    with pytest.raises(ApprovalError, match="changed since the request|out-of-band"):
        approvals.mint(state, request["request_id"], approvals.approve_label(request["mint_code"]))


def test_analysis_requires_explicit_manifest_and_bundles_tasks(state):
    with pytest.raises(ApprovalError, match="manifest"):
        approvals.create_pending_request(state, "analysis",
                                        approval_expires=time.time() + 3600)
    request = approvals.create_pending_request(
        state, "analysis",
        manifest={"question": "why is X slow", "read_only_scope": ["src/"],
                  "expected_result": "profile", "tasks": ["TSK-0001", "TSK-0002"]},
        approval_expires=time.time() + 3600,
    )
    mint_via_hook(state, request)
    apr = _latest_apr(state)
    assert apr["item"] is None and apr["kind"] == "analysis"


def test_revoke(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    apr = approve_scope(state, pr["id"])
    assert approvals.revoke(state, apr["id"])["revoked"] is True


def test_a_hypothesis_cannot_be_given_a_scope_approval(state):
    """The measured chain of BUG-0084, at the door it enters through.

    On a scaffolded research project `request-approval scope HYP-0001` was rc 0 and the mint
    produced a real APR that unlocked dispatch -- while covering nothing: the pair walks no edge,
    the scope manifest of a HYP is `{item, revision}` because the type shares no field with
    `_SCOPE_FIELDS`, and `HASHED_FIELDS` names no HYP field, so no later edit ever invalidated it.
    The control in the same breath is the question above it, whose scope approval is real.
    """
    state.capture("RQ", {"title": "q", "class": "exploratory", "question": "why", "motivation": "m",
                         "acceptance_criteria": [{"id": "AC-1", "text": "x"}],
                         "out_of_scope": [], "priority": "high"})
    state.capture("HYP", {"derives_from": "RQ-0001", "statement": "s",
                          "testable_prediction": "p"})
    with pytest.raises(ApprovalError) as exc:
        approvals.create_pending_request(state, "scope", "HYP-0001")
    assert "no scope approval exists for a HYP" in str(exc.value), exc.value
    assert approvals.create_pending_request(state, "scope", "RQ-0001")["kind"] == "scope"
    assert os.listdir(os.path.join(state.root, "approvals", "pending")), "the control minted none"


def test_no_item_type_can_be_approved_on_a_kind_that_commits_no_edge(state):
    """AC-2 of BUG-0084 over EVERY type of all three kits, and in both directions.

    The types come from `backlog_types.AUTOMATA` rather than from a list here, so a type a kit
    adds tomorrow arrives judged; the kinds come from `item_derived_kinds()`, which asks
    `item_subject_manifest` itself. What the pairs may do is read off `APPROVAL_TRANSITIONS` --
    the same table the guard reads, which is the point: the guard must not hold a second opinion
    about which pairs exist.

    That the RUNNING request path consults this guard is what
    `test_a_hypothesis_cannot_be_given_a_scope_approval` measures; this one measures its verdict.
    """
    listed = set(approvals.APPROVAL_TRANSITIONS)
    seen = set()
    for item_type in sorted(backlog_types.AUTOMATA):
        if item_type not in backlog_types.ACTIVE_DIRS:
            continue
        for kind in approvals.item_derived_kinds():
            refused = None
            try:
                approvals._assert_the_pair_commits_an_edge("%s-0001" % item_type, kind)
            except ApprovalError as exc:
                refused = str(exc)
            if (item_type, kind) in listed:
                assert refused is None, "%s/%s commits an edge and was refused: %s" % (
                    item_type, kind, refused)
                seen.add((item_type, kind))
            else:
                assert refused is not None, (
                    "%s/%s commits no transition and was let through" % (item_type, kind))
                assert item_type in refused and kind in refused, refused
    assert seen == {pair for pair in listed if pair[1] in approvals.item_derived_kinds()}, (
        "a listed pair was never reached -- the derivation over AUTOMATA missed a type")


# -- dispatch ------------------------------------------------------------------

def test_create_task_denormalizes_root_revision(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"]))
    assert task["root_revision"] == 1
    with pytest.raises(DispatchError, match="kernel-set"):
        dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"], root_revision=7))


def test_lease_happy_path_and_header_roundtrip(state):
    _pr, task = make_ready_task(state)
    lease = dispatch.create_lease(state, task["id"])
    assert state.read_item(task["id"])["status"] == "LEASED"
    header = dispatch.parse_header("objective: x\n" + dispatch.dispatch_header(lease))
    assert dispatch.validate_lease(state, header)["nonce"] == lease["nonce"]


def test_lease_requires_ready(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"]))
    with pytest.raises(DispatchError, match="not READY"):
        dispatch.create_lease(state, task["id"])


def test_lease_requires_an_approval_by_either_route(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"]))
    state.transition(task["id"], "READY")
    with pytest.raises(DispatchError, match="no subagent without a user approval"):
        dispatch.create_lease(state, task["id"])


def test_lease_blocked_for_invalidated_root_revision(state):
    pr, task = make_ready_task(state)
    # hashed edit on approved root -> revision bump + approval cleared
    state.update_item(pr["id"], {"goal": "moved goalposts"})
    with pytest.raises(DispatchError, match="no subagent without a user approval"):
        dispatch.create_lease(state, task["id"])
    # even with a fresh approval, the OLD task revision stays unleasable
    request = approvals.create_pending_request(state, "scope", pr["id"])
    mint_via_hook(state, request)
    with pytest.raises(DispatchError, match="not leasable|invalidated root revision"):
        dispatch.create_lease(state, task["id"])


def test_second_claim_blocked(state):
    _pr, task = make_ready_task(state)
    dispatch.create_lease(state, task["id"])
    # normal path: the LEASED status blocks the second claim first
    with pytest.raises(DispatchError, match="not READY"):
        dispatch.create_lease(state, task["id"])
    # inconsistent state (lease file present but task forced back to READY,
    # e.g. after a crash between writes): the dedicated guard still blocks
    with state.lock:
        raw = state.read_item(task["id"])
        raw["status"] = "READY"
        state._write_yaml_atomic(state.active_path(task["id"]), raw)
    with pytest.raises(DispatchError, match="second claim"):
        dispatch.create_lease(state, task["id"])


def test_revoked_approval_blocks_lease(state):
    pr, task = make_ready_task(state)
    approvals.revoke(state, state.read_item(pr["id"])["approval_ref"])
    with pytest.raises(DispatchError, match="revoked"):
        dispatch.create_lease(state, task["id"])


def test_missing_header_blocks(state):
    with pytest.raises(DispatchError, match="no HARNESS_DISPATCH header"):
        dispatch.parse_header("objective: build\noutput: yaml")


def test_random_task_id_prose_blocks(state):
    """II.12: free prose with a random TSK id -> block (header required)."""
    with pytest.raises(DispatchError):
        dispatch.parse_header("please work on TSK-0099 thanks")


def test_spawn_failure_returns_to_ready(state):
    _pr, task = make_ready_task(state)
    dispatch.create_lease(state, task["id"])
    dispatch.spawn_outcome(state, task["id"], ok=False)
    assert state.read_item(task["id"])["status"] == "READY"
    assert not os.path.exists(os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml"))


def test_lease_timeout_sweep_returns_to_ready(state):
    _pr, task = make_ready_task(state)
    dispatch.create_lease(state, task["id"], ttl=0.01)
    time.sleep(0.05)
    assert dispatch.sweep_expired_leases(state) == ([task["id"]], [])
    assert state.read_item(task["id"])["status"] == "READY"


def test_bind_agent_records_subagent_id(state):
    _pr, task = make_ready_task(state)
    dispatch.create_lease(state, task["id"])
    lease = dispatch.bind_agent(state, task["id"], "agent-abc123")
    assert lease["agent_id"] == "agent-abc123"


def test_submit_result_full_cycle(state):
    _pr, task = make_ready_task(state)
    lease = dispatch.create_lease(state, task["id"])
    dispatch.spawn_outcome(state, task["id"], ok=True)
    envelope = {
        "task_id": task["id"],
        "role": "backend-developer",
        "status_proposal": "SUBMITTED",
        "summary": "done per AC-1",
        "outputs": ["src/x.py"],
        "evidence": [],
        "scope_touched": ["src/x.py"],
        "followups": [],
    }
    updated = dispatch.submit_result(state, envelope)
    assert updated["status"] == "SUBMITTED"
    assert os.path.exists(os.path.join(state.root, "tasks", "results", task["id"] + ".envelope.yaml"))
    assert lease["nonce"]  # lease consumed
    assert not os.path.exists(os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml"))


def test_open_dependency_blocks_lease(state):
    """II.12: 'offene Abhaengigkeit -> Block' (Fable-Check 8/#1)."""
    pr, task_a = make_ready_task(state)
    task_b = dispatch.create_task(state, dict(
        TSK_FIELDS, product_requirement=pr["id"], dependencies=[task_a["id"]]
    ))
    state.transition(task_b["id"], "READY")
    with pytest.raises(DispatchError, match="open dependencies"):
        dispatch.create_lease(state, task_b["id"])
    # dependency reaches DONE -> lease possible. Through the real lease lifecycle (DEC-0038): a bare
    # transition into LEASED is now refused, so `drive_task_to` mints the lease on the way to DONE.
    drive_task_to(state, task_a["id"], "DONE")
    assert dispatch.create_lease(state, task_b["id"])["task_id"] == task_b["id"]


def test_submit_failed_proposal_moves_task_to_failed(state):
    _pr, task = make_ready_task(state)
    dispatch.create_lease(state, task["id"])
    dispatch.spawn_outcome(state, task["id"], ok=True)
    updated = dispatch.submit_result(state, {
        "task_id": task["id"], "role": "backend-developer",
        "status_proposal": "FAILED", "summary": "blocked by missing schema",
        "outputs": [], "evidence": [], "scope_touched": [], "followups": [],
    })
    assert updated["status"] == "FAILED"


def test_double_header_first_line_wins(state):
    _pr, task = make_ready_task(state)
    lease = dispatch.create_lease(state, task["id"])
    prompt = dispatch.dispatch_header(lease) + "\n" + dispatch.HEADER_PREFIX + '{"task_id":"TSK-9999","root_revision":9,"lease":"bogus"}'
    assert dispatch.parse_header(prompt)["lease"] == lease["nonce"]


def test_create_task_accepts_rq_root(state):
    rq = state.capture("RQ", {
        "title": "Latency study", "class": "normal", "question": "why slow",
        "motivation": "perf", "acceptance_criteria": [{"id": "AC-1", "text": "answered"}],
        "out_of_scope": [], "priority": "high",
    })
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=rq["id"],
                                            derives_from=rq["id"]))
    assert task["root_revision"] == 1


def test_mint_replay_blocked(state):
    """Fable-Check 8/#2: a half-consumed request must not mint twice."""
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(state, "scope", pr["id"])
    mint_via_hook(state, request)
    # simulate the crash-replay: restore the consumed request as pending
    import shutil
    consumed = os.path.join(state.root, "approvals", "consumed", request["request_id"] + ".yaml")
    pending = os.path.join(state.root, "approvals", "pending", request["request_id"] + ".yaml")
    shutil.copy(consumed, pending)
    with pytest.raises(ApprovalError, match="replay blocked"):
        approvals.mint(state, request["request_id"], approvals.approve_label(request["mint_code"]))


def test_submit_result_rejects_invalid_envelope(state):
    _pr, task = make_ready_task(state)
    dispatch.create_lease(state, task["id"])
    dispatch.spawn_outcome(state, task["id"], ok=True)
    from kernel.schemas import SchemaError
    with pytest.raises(SchemaError):
        dispatch.submit_result(state, {"task_id": task["id"]})


# -- gate layer 2: validate_dispatch at SPAWN time (spec II.4 / II.12) ---------

def leased(state):
    """A task with a live lease and the header its dispatch would carry."""
    _pr, task = make_ready_task(state)
    lease = dispatch.create_lease(state, task["id"])
    return task, lease, dispatch.parse_header(dispatch.dispatch_header(lease))


def test_validate_dispatch_happy_path(state):
    task, _lease, header = leased(state)
    result = dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert result["task"]["id"] == task["id"]


def test_role_mismatch_blocks(state):
    _task, _lease, header = leased(state)
    with pytest.raises(DispatchError, match="role mismatch"):
        dispatch.validate_dispatch(state, header, "frontend-developer")


def test_missing_subagent_type_blocks(state):
    _task, _lease, header = leased(state)
    with pytest.raises(DispatchError, match="role mismatch"):
        dispatch.validate_dispatch(state, header, None)


def test_foreign_lease_nonce_blocks(state):
    _task, _lease, header = leased(state)
    header["lease"] = "0" * 32
    with pytest.raises(DispatchError, match="nonce mismatch"):
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def _edit_around_the_kernel(state, item_id, changes):
    """Write an item file directly -- what an IDE edit does (spec II.4 gate 4)."""
    import yaml
    path = state.active_path(item_id)
    with open(path, encoding="utf-8") as fh:
        item = yaml.safe_load(fh)
    item.update(changes)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(item, fh, sort_keys=False, allow_unicode=True)


def test_out_of_band_edit_between_lease_and_spawn_blocks(state):
    """create_lease checked the approval; this checks it AGAIN at spawn time, because an edit
    around the kernel leaves approval_ref pointing at an approval that no longer describes the
    item."""
    _task, _lease, header = leased(state)
    _edit_around_the_kernel(state, "PR-0001", {"goal": "something the user never approved"})
    with pytest.raises(DispatchError, match="out-of-band edit"):
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_re_approval_after_an_out_of_band_edit_restores_dispatch(state):
    """II.12: "ungueltiger APR-Hash -> Block (nach Re-Approve + Hash-Update -> pass)". Without
    this the block above could be a permanent dead end."""
    task, _lease, header = leased(state)
    _edit_around_the_kernel(state, "PR-0001", {"goal": "an edit the user then approves"})
    approve_scope(state, "PR-0001")
    state.transition(task["id"], "CANCELLED")
    fresh = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001"))
    state.transition(fresh["id"], "READY")
    new_lease = dispatch.create_lease(state, fresh["id"])
    new_header = dispatch.parse_header(dispatch.dispatch_header(new_lease))
    assert dispatch.validate_dispatch(state, new_header, TSK_FIELDS["assigned_role"])


def test_revoked_approval_blocks_dispatch_even_with_a_live_lease(state):
    _task, _lease, header = leased(state)
    approvals.revoke(state, state.read_item("PR-0001")["approval_ref"])
    with pytest.raises(DispatchError, match="revoked"):
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_a_scalar_dependency_is_one_dependency(state):
    """BUG-0015 on `dependencies`: `_assert_dependencies_met_locked` iterated the field itself.

    A task whose one dependency is written as a bare string — which `capture` accepts and which
    `--map TSK.dependencies=<v1 field>` writes from any V1 scalar — became one dependency per
    LETTER, and every letter resolved to no item, so a SATISFIED dependency blocked the lease with
    `T (missing), S (missing), K (missing), ...`. The finished dependency is walked to DONE first,
    so what this measures is the shape and not the status."""
    _pr, first = make_ready_task(state)
    drive_task_to(state, first["id"], "DONE")
    second = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001",
                                              dependencies=first["id"]))
    state.transition(second["id"], "READY")
    assert dispatch.create_lease(state, second["id"])["task_id"] == second["id"]


def test_dependency_that_opens_after_the_lease_blocks_dispatch(state):
    _pr, first = make_ready_task(state)
    second = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001",
                                              dependencies=[first["id"]]))
    state.transition(second["id"], "READY")
    # `first` reaches DONE through the real lease lifecycle (DEC-0038), not a bare transition.
    drive_task_to(state, first["id"], "DONE")
    lease = dispatch.create_lease(state, second["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    state.transition(first["id"], "FAILED")
    with pytest.raises(DispatchError, match="open dependencies"):
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_task_without_acceptance_refs_is_not_dispatchable(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            acceptance_refs=[]))
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    with pytest.raises(DispatchError, match="acceptance_refs"):
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def _ui_task(state, **overrides):
    """A UI task under a root whose confirmed design REALLY EXISTS.

    It used to hand-write `design_refs: ["DSN-0001"]` with no such design anywhere, which is how
    `test_ui_task_with_design_ref_dispatches` proved a spawn against a dangling reference. The
    design is frozen through `staging.freeze_design` now -- the one producer of the field -- so
    what the gate is measured against is the shape the freezer writes (a state-relative path to
    the frozen revision), not a shape only this fixture ever produced.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    staging_dir = os.path.join(state.root, "staging", pr["id"])
    os.makedirs(staging_dir, exist_ok=True)
    with open(os.path.join(staging_dir, "preview.html"), "w", encoding="utf-8") as handle:
        handle.write("<html><body>design</body></html>")
    frozen = staging.freeze_design(state, pr["id"], "DSN-0001", pr["id"], "preview.html")
    approve_scope(state, pr["id"])
    fields = dict(TSK_FIELDS, product_requirement=pr["id"], type="ui",
                  assigned_role="frontend-developer",
                  allowed_scope=a_scope_of_its_own(state))
    fields.update(overrides)
    if fields.get("design_ref") == "DSN-0001":
        # the task references what the freezer actually wrote, not the bare id
        fields["design_ref"] = frozen["root"]["design_refs"][0]
    task = dispatch.create_task(state, fields)
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"])
    return dispatch.parse_header(dispatch.dispatch_header(lease))


def test_ui_task_without_design_ref_blocks_when_a_design_is_confirmed(state):
    header = _ui_task(state)
    with pytest.raises(DispatchError, match="design_ref"):
        dispatch.validate_dispatch(state, header, "frontend-developer")


def test_ui_task_with_design_ref_dispatches(state):
    header = _ui_task(state, design_ref="DSN-0001")
    assert dispatch.validate_dispatch(state, header, "frontend-developer")


def test_a_dangling_design_ref_does_not_satisfy_the_design_gate(state):
    """Truthiness is not resolution: `design_ref: "TBD"` passed a non-empty test while pointing at
    nothing, so the specialist would implement against no frozen revision — the exact failure II.6
    exists to prevent. Third defect in a row on this rule, each one the gate's INPUT going
    unvalidated a level further out."""
    header = _ui_task(state, design_ref="a revision that exists nowhere")
    with pytest.raises(DispatchError, match="design_ref"):
        dispatch.validate_dispatch(state, header, "frontend-developer")


def _dispatchable(state, root_id, **task_overrides):
    fields = dict(TSK_FIELDS, product_requirement=root_id,
                  allowed_scope=a_scope_of_its_own(state))
    fields.update(task_overrides)
    task = dispatch.create_task(state, fields)
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(root_id))
    lease = dispatch.create_lease(state, task["id"])
    return dispatch.parse_header(dispatch.dispatch_header(lease))


@pytest.mark.parametrize("origin", ["not an item at all", "PR-9999", 42, ["PR-0001", "nonsense"]])
def test_a_task_cannot_derive_from_something_that_does_not_exist(state, origin):
    """`derives_from` became a gate input the moment acceptance_refs started resolving against it,
    so a phantom id, an integer or a free-text note would let a task look derived while
    contributing no criteria at all. The cheap half is enforced here; whether the origin belongs to
    this root's TREE is a reference-graph question and sits on the validator's duty list."""
    pr = state.capture("PR", dict(PR_FIELDS))
    with pytest.raises(Exception):
        dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                         derives_from=origin))


def test_a_task_may_derive_from_an_archived_item(state):
    """Archived origins still resolve: a fix task for a closed bug is legitimate, and staleness is
    the validator's judgement rather than a hard capture-time refusal."""
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    bug = state.capture("BUG", {"title": "old", "related_pr": pr["id"], "observed": "x",
                                "expected": "y", "repro": "z", "severity": "low",
                                "acceptance_criteria": [{"id": "AC-OLD", "text": "fixed"}]})
    state.transition(bug["id"], "TRIAGED")
    state.transition(bug["id"], "REJECTED")
    state.archive(bug["id"])
    header = _dispatchable(state, pr["id"], type="bugfix", derives_from=bug["id"],
                           acceptance_refs=["AC-OLD"])
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_a_bugfix_task_may_reference_the_bugs_own_fix_criteria(state):
    """spec II.2 gives BUG its own acceptance_criteria (Fix-Kriterien). Resolving a task's refs
    against the PR/RQ root ALONE blocked the correct shape and would have passed only the wrong
    one — a bugfix referencing the PR's AC instead of the BUG's."""
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    bug = state.capture("BUG", {"title": "checkout 500s", "related_pr": pr["id"],
                                "observed": "500", "expected": "200", "repro": "click",
                                "severity": "high",
                                "acceptance_criteria": [{"id": "AC-FIX-1", "text": "no 500"}]})
    header = _dispatchable(state, pr["id"], type="bugfix", derives_from=bug["id"],
                           acceptance_refs=["AC-FIX-1"])
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_a_cr_derived_task_may_reference_the_crs_own_criteria(state):
    """A CR exists precisely because its AC differ from the PR revision it changes.

    NAMING THE CR IN `derives_from` IS STILL THE RIGHT SHAPE and still dispatches -- what changed
    with BUG-0040 is WHICH HOP carries it: an amendment's criteria now arrive through the
    approval-gated amendment path, so this shape works once the user has approved the CR and not
    before. The task below is otherwise the one this test always ran.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    cr = state.capture("CR", {"title": "add express checkout", "target_pr": pr["id"],
                              "target_revision": 1, "change_description": "express lane",
                              "acceptance_criteria": [{"id": "AC-CR-1", "text": "one click"}]})
    approve_scope(state, cr["id"])
    header = _dispatchable(state, pr["id"], derives_from=cr["id"], acceptance_refs=["AC-CR-1"])
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_an_exp_derived_task_may_reference_success_criteria(state):
    """Research: an execution task delivers against the EXP's success_criteria (spec II.2)."""
    rq = state.capture("RQ", {"title": "why slow", "class": "normal", "question": "why?",
                              "motivation": "users wait",
                              "acceptance_criteria": [{"id": "AC-RQ-1", "text": "answered"}],
                              "out_of_scope": [], "priority": "high"})
    approve_scope(state, rq["id"])
    exp = state.capture("EXP", {"derives_from": rq["id"], "design": "A/B", "variables": ["n"],
                                "success_criteria": [{"id": "SC-1", "text": "p<0.05"}],
                                "evidence_refs": []})
    header = _dispatchable(state, rq["id"], type="research", derives_from=exp["id"],
                           acceptance_refs=["SC-1"])
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_plain_string_criteria_resolve_too(state):
    """Real items carry both shapes; a strict check understanding only mappings would block the
    other one."""
    pr = state.capture("PR", dict(PR_FIELDS, acceptance_criteria=["AC-PLAIN"]))
    approve_scope(state, pr["id"])
    header = _dispatchable(state, pr["id"], acceptance_refs=["AC-PLAIN"])
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


@pytest.mark.parametrize("criteria,refs,dispatchable", [
    ("AC-1", ["AC-1"], True),
    ([{"id": "AC-1", "text": "order completes"}], "AC-1", True),
    ("AC-1", "AC-1", True),
    ("AC-1", "1-CA", False),
])
def test_a_scalar_acceptance_ref_is_one_ref_not_four_letters(state, criteria, refs, dispatchable):
    """BUG-0015 on the pair this gate is built from: both fields were iterated directly.

    A scalar `acceptance_criteria: AC-1` became the criterion ids {A, C, -, 1} and a scalar
    `acceptance_refs: AC-1` the references [A, C, -, 1]. Two consequences, and the last row is the
    one that matters: the two letter sets MATCH, so "a task nobody can check against the approved
    criteria is not dispatchable" passed on criteria nobody wrote — measured as SPAWN ALLOWED for
    `1-CA`, an anagram that resolves against nothing. The first two rows are the same defect in
    its loud direction: one field spelled as a list and the other as a string refused a reference
    the root really declares (`exist nowhere: A, C, -, 1`).

    `kernel.capture` takes either spelling and `migrate`'s `--map` carries the V1 one over
    verbatim, so both reach this gate exactly as the item holds them."""
    pr = state.capture("PR", dict(PR_FIELDS, acceptance_criteria=criteria))
    approve_scope(state, pr["id"])
    header = _dispatchable(state, pr["id"], acceptance_refs=refs)
    if dispatchable:
        assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    else:
        with pytest.raises(DispatchError, match="exist nowhere"):
            dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_acceptance_refs_must_point_at_criteria_that_exist(state):
    """The same shape as the design_ref defect, on the field right next to it: non-emptiness was
    checked, resolution was not."""
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            acceptance_refs=["AC-1", "AC-does-not-exist"]))
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    with pytest.raises(DispatchError, match="exist nowhere"):
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_non_ui_task_needs_no_design_ref(state):
    pr = state.capture("PR", dict(PR_FIELDS))
    state.update_item(pr["id"], {"design_refs": ["DSN-0001"]})
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"]))
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


# -- analysis route (spec II.2 Buendelung; II.12 "Draft-Analyse ohne APR") -----

def _analysis_task(state, **overrides):
    """A task under an UNAPPROVED root -- the draft-analysis situation."""
    pr = state.capture("PR", dict(PR_FIELDS))
    # `derives_from` follows the root rather than keeping `TSK_FIELDS`' PR-0001: a task whose
    # origin is ANOTHER root is refused at creation, and in a test that captures a second root
    # first the helper was building exactly that (`report.origin_root_conflict`).
    fields = dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"],
                  type="analysis", assigned_role="software-architect",
                  allowed_scope=a_scope_of_its_own(state))
    fields.update(overrides)
    task = dispatch.create_task(state, fields)
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    return pr, task


def _analysis_apr(state, task_ids, expires_in=3600):
    request = approvals.create_pending_request(
        state, "analysis",
        manifest={"question": "how does checkout fail?", "scope": "read-only",
                  "expected_result": "a written finding",
                  dispatch.ANALYSIS_TASKS_KEY: list(task_ids)},
        approval_expires=time.time() + expires_in)
    mint_via_hook(state, request)
    return _latest_apr(state)


def _latest_apr(state):
    names = sorted(n for n in os.listdir(os.path.join(state.root, "approvals"))
                   if n.startswith("APR-") and n.endswith(".yaml"))
    return approvals.read_apr(state, names[-1][:-5])


def test_draft_analysis_without_an_analysis_approval_blocks(state):
    _pr, task = _analysis_task(state)
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.create_lease(state, task["id"])


def test_bundled_analysis_approval_covers_its_listed_tasks(state):
    _pr, task = _analysis_task(state)
    _analysis_apr(state, [task["id"]])
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    assert dispatch.validate_dispatch(state, header, "software-architect")


def test_an_analysis_approval_does_not_cover_an_unlisted_task(state):
    _pr, listed = _analysis_task(state)
    unlisted = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001",
                                                type="analysis",
                                                assigned_role="software-architect"))
    state.transition(unlisted["id"], "READY")
    _analysis_apr(state, [listed["id"]])
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.create_lease(state, unlisted["id"])


def test_revoked_analysis_approval_stops_covering(state):
    _pr, task = _analysis_task(state)
    apr = _analysis_apr(state, [task["id"]])
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    approvals.revoke(state, apr["id"])
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.validate_dispatch(state, header, "software-architect")


def test_expired_approval_blocks_dispatch(state):
    """spec II.10a: an expired ANALYSIS approval blocks the dispatch.

    "routine/analysis" is what this said while only the analysis half was built, so no test here
    could have covered the routine one. The routine ROUTE shipped on 2026-07-31 and has its own
    expiry assertion below (`test_an_expired_routine_approval_blocks_the_audit_dispatch`); this
    stays the analysis half, deliberately, so neither route rides on the other's measurement.
    """
    _pr, task = _analysis_task(state)
    _analysis_apr(state, [task["id"]], expires_in=-1)
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.create_lease(state, task["id"])


def test_editing_the_approval_file_cannot_resurrect_an_expired_approval(state):
    """The expiry is read from the HASH-COVERED manifest of the minted request, so the copy in
    the approval file is decoration. Reading it there made a lapsed standing permission one
    YAML line away from being valid again."""
    _pr, task = _analysis_task(state)
    apr = _analysis_apr(state, [task["id"]], expires_in=-1)
    path = os.path.join(state.root, "approvals", apr["id"] + ".yaml")
    forged = state._read_yaml(path)
    forged["expires"] = time.time() + 3600
    state._write_yaml_atomic(path, forged)
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.create_lease(state, task["id"])


# -- routine route (spec II.1/II.10a Auditor-Routine; disposition line 100) ----

# What an audit task looks like: a role, criteria it can be judged against, and NO writable scope.
# `allowed_scope: []` is not decoration here -- it is the kernel's only expression of "read-only"
# (see `dispatch._claims_writable_scope`), so it is what makes this task eligible for the routine
# route at all.
AUDIT_TSK_FIELDS = dict(TSK_FIELDS, type="review", assigned_role="project-auditor",
                        allowed_scope=[], forbidden_scope=[], expected_outputs=["findings"])


def _audit_task(state, **overrides):
    """An audit task under a root with NO scope/delivery approval -- the recurring-run situation."""
    pr = state.capture("PR", dict(PR_FIELDS))
    fields = dict(AUDIT_TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"])
    fields.update(overrides)
    task = dispatch.create_task(state, fields)
    state.transition(task["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    return state.read_item(pr["id"]), state.read_item(task["id"])


def _routine_apr(state, item_id, role="project-auditor", expires_in=3600, **manifest_overrides):
    """Mint a routine approval for `item_id` -- request through the kernel, mint through the hook."""
    manifest = {"role": role, "scope": ["project_memory/**"],
                "trigger": "weekly + after kit update", "cadence": "weekly"}
    manifest.update(manifest_overrides)
    mint_via_hook(state, approvals.create_pending_request(
        state, "routine", item_id, manifest=manifest,
        approval_expires=time.time() + expires_in))
    return _latest_apr(state)


def test_the_routine_kind_is_walkable_on_the_command_surface_a_role_actually_types(state, capsys):
    """BUG-0266 and BUG-0195: the auditor's route existed in the kernel and not on the CLI.

    The measurement that filed both was a PROCESS on a scaffolded pilot -- `request-approval
    routine PR-0001` answered `invalid choice: 'routine'`, so the only walkable way to run the
    auditor was an ordinary work order, and `create-task` makes `--allowed-scope` mandatory: the
    very writable scope the routine route exists to avoid. So this drives the SHIPPED parser and
    the shipped entry point, not the library function behind them, and it asserts the second half
    too -- the task the minted approval authorises carries NO writable scope.

    The counterweight in the same test is the kind that is still NOT on that surface: `analysis`
    has no producer here, and a test that only asked "is routine there" would go green on a parser
    that accepted every word.
    """
    kinds = set(cli.build_parser()._subparsers._group_actions[0]
                .choices["request-approval"]._actions[1].choices)
    assert approvals.ROUTINE_KIND in kinds, kinds
    assert "analysis" not in kinds, (
        "`analysis` has no producer on this surface -- see BUG-0266's `expected`")

    pr, task = _audit_task(state)
    assert cli.main(["--root", state.root, "request-approval", approvals.ROUTINE_KIND, pr["id"],
                     "--role", "project-auditor", "--scope", "project_memory/**",
                     "--trigger", "weekly + after kit update", "--cadence", "weekly",
                     "--expires-in-days", "7"]) == 0
    question = json.loads(capsys.readouterr().out)["question"]
    found = re.search(r"APR-REQ:([A-Za-z0-9_.:-]+)", question)
    assert found, question

    request = approvals.pending_request(state, found.group(1))
    assert request["kind"] == approvals.ROUTINE_KIND, request
    assert request["subject_manifest"]["role"] == "project-auditor"

    mint_via_hook(state, request)
    assert _latest_apr(state)["kind"] == approvals.ROUTINE_KIND
    lease = dispatch.create_lease(state, task["id"])
    assert dispatch.validate_dispatch(
        state, dispatch.parse_header(dispatch.dispatch_header(lease)), "project-auditor")
    assert state.read_item(task["id"])["allowed_scope"] == [], (
        "the routine route authorises a task with no writable scope -- that is its point")


def test_a_routine_approval_authorises_the_recurring_read_only_dispatch(state):
    """Spec II.1: the auditor runs as a mandatory routine "legitimiert durch eine widerrufbare
    `APR.kind: routine`-Freigabe".

    Measured before the route existed (2026-07-26, re-measured 2026-07-31): a valid, unexpired,
    unrevoked routine APR on the root gave `dispatch REFUSED -- neither PR-0001 nor an analysis
    approval authorises dispatching TSK-0001`. The kind could be minted and was read by nobody,
    which also left the expiry check spec II.10a demands as dead code on this path.
    """
    pr, task = _audit_task(state)
    apr = _routine_apr(state, pr["id"])
    assert apr["kind"] == "routine" and apr["revoked"] is False
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    assert dispatch.validate_dispatch(state, header, "project-auditor")


def test_an_expired_routine_approval_blocks_the_audit_dispatch(state):
    """II.10a: "Abgelaufene oder widerrufene Routinefreigabe blockiert den Audit-Dispatch
    (fail-closed) und zeigt genau EINE notwendige Useraktion"."""
    pr, task = _audit_task(state)
    _routine_apr(state, pr["id"], expires_in=-1)
    with pytest.raises(DispatchError, match="expired"):
        dispatch.create_lease(state, task["id"])


def test_a_routine_approval_that_lapses_between_lease_and_spawn_blocks_the_spawn(state):
    """The clock is re-read at SPAWN time, not once when the lease was taken.

    A routine approval is the kind that can lapse while a lease is still warm, and the lease
    carries no expiry of its own -- so a check that ran only in `create_lease` would let the run
    the user time-boxed start after its box closed. The expiry is moved in the HASH-COVERED
    manifest of the minted request, i.e. through the only copy `proven_expiry` reads, and the
    rehash is consistent across request and approval so that nothing but the CLOCK refuses here.
    """
    pr, task = _audit_task(state)
    apr = _routine_apr(state, pr["id"])
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    assert dispatch.validate_dispatch(state, header, "project-auditor")
    request_path = os.path.join(state.root, "approvals", "consumed", apr["request_id"] + ".yaml")
    request = state._read_yaml(request_path)
    request["subject_manifest"]["expires"] = time.time() - 1
    request["subject_manifest_hash"] = hashing.subject_manifest_hash(request["subject_manifest"])
    state._write_yaml_atomic(request_path, request)
    apr_path = os.path.join(state.root, "approvals", apr["id"] + ".yaml")
    stored = state._read_yaml(apr_path)
    stored["subject_manifest_hash"] = request["subject_manifest_hash"]
    state._write_yaml_atomic(apr_path, stored)
    with pytest.raises(DispatchError, match="expired"):
        dispatch.validate_dispatch(state, header, "project-auditor")


def test_a_revoked_routine_approval_blocks_the_audit_dispatch(state):
    """The other half of II.10a's sentence -- and revocation is what makes a standing permission
    survivable at all, which is why II.2 calls the kind "jederzeit widerrufbar"."""
    pr, task = _audit_task(state)
    apr = _routine_apr(state, pr["id"])
    approvals.revoke(state, apr["id"])
    with pytest.raises(DispatchError, match="is revoked"):
        dispatch.create_lease(state, task["id"])


def test_a_routine_approval_does_not_cover_another_role(state):
    """Spec II.2 binds a routine to a ROLE. A route that did not check it would turn one weekly
    signature into a licence to spawn any specialist -- and the role is read from the MINTED
    request, never from the approval file."""
    pr, task = _audit_task(state)
    _routine_apr(state, pr["id"], role="backend-developer")
    with pytest.raises(DispatchError, match="covers role"):
        dispatch.create_lease(state, task["id"])


def test_a_routine_approval_never_authorises_a_task_that_may_write(state):
    """"Read-only-Scope" (II.2) is the reason `routine` stays out of `ROOT_DISPATCH_KINDS`.

    `allowed_scope` is gate layer 3's only input, so a task carrying one claims the right to
    write -- and a routine approval that authorised it would be exactly the blanket permission
    the comment on `ROOT_DISPATCH_KINDS` refuses: unlimited implementation work under a root
    whose scope nobody approved.
    """
    pr, task = _audit_task(state, allowed_scope=["src/"])
    _routine_apr(state, pr["id"])
    with pytest.raises(DispatchError, match="READ-ONLY"):
        dispatch.create_lease(state, task["id"])


def test_a_task_under_a_root_with_no_approval_at_all_stays_blocked(state):
    """The floor the routine route must not lower: no approval, no subagent (spec II.2)."""
    _pr, task = _audit_task(state)
    with pytest.raises(DispatchError, match="no user approval"):
        dispatch.create_lease(state, task["id"])


def test_a_hand_written_routine_apr_authorises_nothing(state):
    """II.12: an approval file proves nothing; the CONSUMED REQUEST does.

    The role and the expiry this route acts on are read out of that request, so a self-written
    `APR-nnnn.yaml` naming any role it likes has no manifest behind it at all.
    """
    pr, task = _audit_task(state)
    state._write_yaml_atomic(
        os.path.join(state.root, "approvals", "APR-0001.yaml"),
        {"id": "APR-0001", "kind": "routine", "item": pr["id"], "revision": pr["revision"],
         "subject_manifest_hash": "0" * 64, "request_id": "deadbeefdeadbeef",
         "mint_code": "abc123", "approved_at": "2026-07-31T00:00:00",
         "expires": time.time() + 3600, "revoked": False})
    with pytest.raises(DispatchError, match="provenance"):
        dispatch.create_lease(state, task["id"])


def test_a_routine_approval_bound_to_another_root_does_not_travel(state):
    """A routine is minted FOR a root; `assert_apr_in_force` is what refuses a foreign one."""
    _pr, task = _audit_task(state)
    other = state.capture("PR", dict(PR_FIELDS))
    _routine_apr(state, other["id"])
    with pytest.raises(DispatchError, match="no user approval"):
        dispatch.create_lease(state, task["id"])


def test_a_routine_manifest_that_binds_nothing_is_refused_at_creation(state):
    """A routine whose manifest names no role and no scope is a standing spawn permission, and
    the user would be asked to sign it. Every field II.10a hashes is required when the request is
    written, so the question is never posed for an unbound one.

    Derived from `ROUTINE_MANIFEST_FIELDS`, so a field added to that contract is covered the day
    it is added -- and the positive case proves the check is not simply always-refuse.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    complete = {"role": "project-auditor", "scope": ["project_memory/**"],
                "trigger": "weekly", "cadence": "weekly"}
    assert set(complete) == set(approvals.ROUTINE_MANIFEST_FIELDS)
    for field in approvals.ROUTINE_MANIFEST_FIELDS:
        partial = {key: value for key, value in complete.items() if key != field}
        with pytest.raises(ApprovalError, match=field):
            approvals.create_pending_request(state, "routine", pr["id"], manifest=partial,
                                             approval_expires=time.time() + 60)
    assert approvals.create_pending_request(state, "routine", pr["id"], manifest=complete,
                                            approval_expires=time.time() + 60)


def test_the_role_comes_from_the_minted_request_not_from_the_approval_file(state):
    """II.12 applied to the field this route DECIDES on -- and it had no test.

    `consumed_request` compares an approval against its minted request on `mint_code`,
    `subject_manifest_hash`, `kind`, `item` and `revision`. It does NOT compare a
    `subject_manifest` written into the APR file, because the approval is not supposed to carry
    one -- so a legitimate routine approval for one role, plus that one added key, would cover any
    role the writer likes IF the route read the approval file. Measured with the reader mutated to
    `apr.get("subject_manifest") or request[...]`: the whole module stayed green, 97 passed.

    The task here is read-only and differs from the approval ONLY in its role, so nothing but the
    role reader stands between it and authorisation.
    """
    pr, task = _audit_task(state, assigned_role="backend-developer")
    apr = _routine_apr(state, pr["id"], role="project-auditor")
    path = os.path.join(state.root, "approvals", apr["id"] + ".yaml")
    forged = state._read_yaml(path)
    forged["subject_manifest"] = {"role": "backend-developer", "scope": ["src/**"],
                                  "trigger": "weekly", "cadence": "weekly"}
    state._write_yaml_atomic(path, forged)
    # the forgery is invisible to the provenance check -- which is exactly why the ROUTE must not
    # read it: an approval that still proves its provenance now carries a second, unhashed claim
    assert approvals.consumed_request(state, state._read_yaml(path))
    with pytest.raises(DispatchError, match="covers role"):
        dispatch.create_lease(state, task["id"])


def test_a_root_approval_that_grants_nothing_does_not_hide_the_routine_route(state):
    """The audit must be dispatchable exactly when the root's own approval was withdrawn.

    The root route used to RAISE on an invalid scope/delivery approval instead of falling through,
    so a revoked scope approval made the task routes unreachable -- and the situation an auditor
    exists for is precisely the one where an approval was pulled or the root was edited past the
    kernel. Falling through grants only what the routine approval independently grants: it is
    proven, unexpired, role-bound and refuses a task planned to write, and it never reads
    `approval_ref`.
    """
    pr, task = _audit_task(state)
    mint_via_hook(state, approvals.create_pending_request(state, "scope", pr["id"]))
    scope_apr = state.read_item(pr["id"])["approval_ref"]
    _routine_apr(state, pr["id"])
    # put the scope approval back as the one the root PRESENTS, then withdraw it
    item = state.read_item(pr["id"])
    item["approval_ref"] = scope_apr
    state._write_yaml_atomic(state.active_path(pr["id"]), item)
    approvals.revoke(state, scope_apr)
    assert dispatch.create_lease(state, task["id"])


def test_a_root_approval_that_grants_nothing_still_refuses_an_uncovered_task(state):
    """...and the counter-direction, so the fall-through cannot be read as "try again, softer".

    A READ-ONLY task -- so it really does fall through -- that NO task route covers: no analysis
    approval lists it, no routine approval names its role. It is still refused, and the refusal
    still carries the ROOT's own reason rather than replacing it with a vaguer one, because that
    is what tells the role which approval broke.
    """
    pr, task = _audit_task(state)                        # read-only, no routine, no analysis
    scope_apr = approve_scope(state, pr["id"])["id"]
    item = state.read_item(pr["id"])
    item["approval_ref"] = scope_apr
    state._write_yaml_atomic(state.active_path(pr["id"]), item)
    approvals.revoke(state, scope_apr)
    with pytest.raises(DispatchError, match="no user approval") as refused:
        dispatch.create_lease(state, task["id"])
    assert scope_apr in str(refused.value) and "revoked" in str(refused.value)


def test_the_routine_question_names_everything_the_route_binds_to(state):
    """F5: the user was asked to sign a standing spawn permission without seeing its role.

    The generic question reads "Freigabe erbeten: routine für PR-0001 (Revision 1, …)". The role
    is what the dispatch route binds to, and the cadence and trigger are what makes the permission
    recurring -- none of them appeared. The same argument the `push` case in `build_question`
    already makes ("the human would be asked to authorise publishing without being told WHAT gets
    published"), for the other kind whose subject is not the item it hangs from.

    Derived from `ROUTINE_MANIFEST_FIELDS`, so a field added to the contract shows up in the
    question with no second edit -- and the two properties the whole protocol rests on are
    re-asserted here: deterministic from the request alone, and no mint code anywhere but the
    approval option's label.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    request = approvals.create_pending_request(
        state, "routine", pr["id"],
        manifest={"role": "project-auditor", "scope": ["project_memory/**", "src/**"],
                  "trigger": "weekly + after kit update", "cadence": "weekly"},
        approval_expires=time.time() + 3600)
    question = approvals.build_question(request)
    assert question == approvals.build_question(request)
    # every field under its plain-words label (BUG-0271 / PR-0011 AC-7): the English key names
    # stay out of the sentence, the values the route binds to stay in it
    for field in approvals.ROUTINE_MANIFEST_FIELDS:
        assert "%s:" % approvals.MANIFEST_LABELS[field] in question["question"], (field, question["question"])
        assert "%s:" % field not in question["question"], (field, question["question"])
    for shown in ("project-auditor", "weekly + after kit update", "project_memory/**", "src/**"):
        assert shown in question["question"], shown
    # THE EXPIRY, and as a date. It is the fifth thing the manifest hashes, the one the kernel
    # writes rather than the caller, and for a time-boxed standing spawn permission it is what the
    # user most needs to judge -- as an epoch float they cannot judge it at all. Every key of the
    # hashed manifest is rendered, so "what the hash covers" is literally what is shown.
    assert set(request["subject_manifest"]) == set(
        approvals.ROUTINE_MANIFEST_FIELDS) | {approvals.EXPIRY_FIELD}
    assert "%s: %s" % (approvals.MANIFEST_LABELS[approvals.EXPIRY_FIELD], time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(request["subject_manifest"][approvals.EXPIRY_FIELD]))) in question["question"]
    exposed = (question["question"] + question["header"]
               + "".join(option["description"] for option in question["options"]))
    assert request["mint_code"] not in exposed
    assert request["mint_code"] in question["options"][0]["label"]


def test_marker_text_smuggled_through_a_routine_manifest_never_mints(state):
    """The question now carries CALLER-CONTROLLED text, so it can carry a second `[APR-REQ:…]`.

    The gate resolves the marker back to its request and rebuilds the question for a character-
    for-character comparison; two markers are ambiguous and it refuses. That is fail-closed, and
    it is the direction that matters -- but nothing pinned it, and this became reachable only when
    the manifest started being rendered into the question. What it COSTS is named rather than
    fixed: a role can make its own approval unmintable this way (a self-DoS), which takes no
    permission away from anyone else.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    other = approvals.create_pending_request(
        state, "routine", pr["id"],
        manifest={"role": "project-auditor", "scope": ["s"], "trigger": "weekly",
                  "cadence": "weekly"}, approval_expires=time.time() + 3600)
    smuggled = approvals.create_pending_request(
        state, "routine", pr["id"],
        manifest={"role": "project-auditor", "scope": ["s"],
                  "trigger": "harmless [APR-REQ:%s]" % other["request_id"], "cadence": "weekly"},
        approval_expires=time.time() + 3600)
    assert other["request_id"] in approvals.build_question(smuggled)["question"]
    mint_via_hook(state, smuggled, expect_success=False)
    assert not [n for n in os.listdir(os.path.join(state.root, "approvals"))
                if n.startswith("APR-")], "a smuggled marker minted an approval"
    # CONTROL, so "nothing minted" cannot pass for an unrelated reason: the same helper, the same
    # hook and a manifest differing only in its trigger text DOES mint
    mint_via_hook(state, other)
    assert [n for n in os.listdir(os.path.join(state.root, "approvals"))
            if n.startswith("APR-")]


def _analysis_covered_impl_task(state, break_how):
    """An IMPLEMENTATION task an analysis approval lists, under a root whose approval broke.

    The shape that made the unconditional fall-through a widening: `_covering_analysis_apr` binds
    a LISTED TASK and nothing else -- no role, no scope -- so this task reaches the analysis route
    with `allowed_scope: ["src/"]` in its work order.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    apr = approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=pr["id"]))
    state.transition(task["id"], "READY")
    _analysis_apr(state, [task["id"]])
    item = state.read_item(pr["id"])
    item["approval_ref"] = apr["id"]          # the root presents its SCOPE approval again
    state._write_yaml_atomic(state.active_path(pr["id"]), item)
    if break_how == "revoke":
        approvals.revoke(state, apr["id"])
    elif break_how == "edit":
        # out of band: revision NOT bumped, so the root_revision check cannot see it either
        edited = state._read_yaml(state.active_path(pr["id"]))
        edited["goal"] = "edited past the kernel"
        state._write_yaml_atomic(state.active_path(pr["id"]), edited)
    elif break_how == "missing":
        os.remove(os.path.join(state.root, "approvals", apr["id"] + ".yaml"))
    return pr, task, apr


@pytest.mark.parametrize("break_how,expected", [
    ("revoke", "is revoked"),
    ("edit", "content hash"),
    ("missing", "no approval"),
])
def test_a_writable_task_may_not_run_under_a_root_whose_approval_grants_nothing(
        state, break_how, expected):
    """THE condition on the read-only fall-through -- and without it, a measured widening.

    A root whose approval no longer grants anything may still be READ, never WRITTEN. The first
    cut of the fall-through argued that the task routes "read no approval_ref, so falling through
    can widen nothing"; that is true of the ROUTINE route, which refuses a task claiming a
    writable scope, and false of the ANALYSIS route, which binds a listed task and nothing else.
    Measured 2026-07-31 with the analysis approval in place: root revoked -> IMPLEMENTATION
    dispatch ALLOWED, root edited out of band -> ALLOWED. Both are exactly the two tripwires
    `assert_apr_in_force` exists for, and the revocation is the worse of them because a user
    deliberately withdrew it.

    The refusal must also still carry the ROOT's own reason rather than the aggregated one -- a
    role that broke its scope approval needs to be told which approval broke.
    """
    _pr, task, _apr = _analysis_covered_impl_task(state, break_how)
    assert task["allowed_scope"], "this task must claim a writable scope or it measures nothing"
    with pytest.raises(DispatchError, match=expected):
        dispatch.create_lease(state, task["id"])


@pytest.mark.parametrize("break_how", ["revoke", "edit", "missing"])
def test_a_read_only_task_still_runs_under_a_root_whose_approval_grants_nothing(state, break_how):
    """...and the counter-direction, over ALL THREE reasons a root approval stops granting.

    `missing` is here because it used to be the odd one out: `read_apr` was called outside the
    try, so a deleted APR file raised `ApprovalError` -- not a `DispatchError` -- and the audit
    stayed blocked for that one reason while revocation and an out-of-band edit fell through.
    Inconsistent, and it reached the user as "the harness is broken, run the doctor".
    """
    pr, task = _audit_task(state)
    apr = approve_scope(state, pr["id"])
    _routine_apr(state, pr["id"])
    item = state.read_item(pr["id"])
    item["approval_ref"] = apr["id"]
    state._write_yaml_atomic(state.active_path(pr["id"]), item)
    if break_how == "revoke":
        approvals.revoke(state, apr["id"])
    elif break_how == "edit":
        edited = state._read_yaml(state.active_path(pr["id"]))
        edited["goal"] = "edited past the kernel"
        state._write_yaml_atomic(state.active_path(pr["id"]), edited)
    else:
        os.remove(os.path.join(state.root, "approvals", apr["id"] + ".yaml"))
    assert not state.read_item(task["id"])["allowed_scope"]
    assert dispatch.create_lease(state, task["id"])


def test_a_root_approval_that_cannot_be_read_refuses_in_the_dispatch_vocabulary(state):
    """`ApprovalError` is not a `DispatchError`, and the hook reports anything else as an internal
    error -- so a stale `approval_ref` reached the user as "the harness is broken, run the doctor"
    instead of "this root's approval is gone". The same re-raise `_assert_root_approval_locked`
    argues for, on the one path that reaches `read_apr` before it."""
    _pr, task, apr = _analysis_covered_impl_task(state, "missing")
    with pytest.raises(DispatchError) as refused:
        dispatch.create_lease(state, task["id"])
    assert not isinstance(refused.value, ApprovalError) or isinstance(refused.value, DispatchError)
    assert apr["id"] in str(refused.value)


def test_minting_a_routine_on_a_live_root_leaves_its_approval_ref_alone(state):
    """PR-0011 AC-8 (BUG-0266): the routine approval the auditor's route is written for no longer
    displaces the goal's presented approval -- `approvals.presents` keeps a HANGING kind out of
    `approval_ref` -- so the builder under that goal still leases after the routine is minted, and
    the routine still covers the auditor, read off the approvals directory.

    UNTIL GENERATION 6 THIS TEST PINNED THE OPPOSITE ("takes its approval_ref"): a routine minted
    for a root moved the scope approval out of the field and every implementation task under it
    stopped dispatching until the scope question was asked again -- at every weekly renewal. The
    light form runs the auditor from the session-start due reading beside a goal being built, so
    that interaction had to go rather than stay named. `acceptance` after `delivery` still moves
    the field, because it commits an edge of the root's own automaton.
    RED WITHOUT `presents` in `mint`: the builder's lease below is refused with "obtain the scope
    approval".
    """
    pr, task = make_ready_task(state)                      # scope approval, task dispatchable
    assert dispatch.create_lease(state, task["id"])
    dispatch._remove_lease(state, task["id"])
    state.transition(task["id"], "READY")
    scope_apr = state.read_item(pr["id"])["approval_ref"]

    routine = _routine_apr(state, pr["id"])
    assert state.read_item(pr["id"])["approval_ref"] == scope_apr, "the routine mint moved approval_ref"
    assert approvals.read_apr(state, scope_apr)["revoked"] is False
    assert dispatch.create_lease(state, task["id"])["task_id"] == task["id"]
    dispatch._remove_lease(state, task["id"])
    # ...and the routine covers the auditor's read-only order under the same root
    audit = dispatch.create_task(state, dict(AUDIT_TSK_FIELDS, product_requirement=pr["id"],
                                             derives_from=pr["id"]))
    state.transition(audit["id"], "READY")
    covering, _refusals = dispatch._covering_routine_apr(
        state, state.read_item(audit["id"]), state.read_item(pr["id"]))
    assert covering is not None and covering["id"] == routine["id"]
    assert not approvals.presents("PR", "routine") and approvals.presents("PR", "acceptance")


def test_the_routine_route_leaves_the_other_three_alone(state):
    """The routes are independent, and this asserts it instead of assuming it.

    Each of scope, delivery and analysis authorises its own dispatch with no routine approval
    anywhere, and none of those tasks is read-only -- so a routine route that had leaked into the
    shared path would show up here as an ALLOWANCE, not only as a refusal somewhere else.
    """
    pr, task = make_ready_task(state)                      # the scope route
    assert approvals.read_apr(
        state, state.read_item(pr["id"])["approval_ref"])["kind"] == "scope"
    assert dispatch.create_lease(state, task["id"])

    delivered = state.capture("PR", dict(PR_FIELDS))       # the delivery route
    mint_via_hook(state, approvals.create_pending_request(state, "scope", delivered["id"]))
    mint_via_hook(state, approvals.create_pending_request(state, "delivery", delivered["id"]))
    second = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=delivered["id"],
                                              derives_from=delivered["id"],
                                              allowed_scope=a_scope_of_its_own(state)))
    state.transition(second["id"], "READY")
    satisfy_the_architect_step(state, state.read_item(second["id"]),
                               state.read_item(delivered["id"]))
    assert approvals.read_apr(
        state, state.read_item(delivered["id"])["approval_ref"])["kind"] == "delivery"
    assert dispatch.create_lease(state, second["id"])

    _root, analysis_task = _analysis_task(state)           # the analysis route
    _analysis_apr(state, [analysis_task["id"]])
    assert dispatch.create_lease(state, analysis_task["id"])


def test_editing_the_minted_manifest_breaks_provenance(state):
    """Moving the expiry where it IS hash-covered does not help either: consumed_request
    recomputes the hash from the manifest rather than comparing two stored copies."""
    _pr, task = _analysis_task(state)
    apr = _analysis_apr(state, [task["id"]], expires_in=-1)
    path = os.path.join(state.root, "approvals", "consumed", apr["request_id"] + ".yaml")
    request = state._read_yaml(path)
    request["subject_manifest"]["expires"] = time.time() + 3600
    state._write_yaml_atomic(path, request)
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.create_lease(state, task["id"])


def test_unreadable_expiry_grants_nothing(state):
    _pr, task = _analysis_task(state)
    apr = _analysis_apr(state, [task["id"]])
    path = os.path.join(state.root, "approvals", "consumed", apr["request_id"] + ".yaml")
    request = state._read_yaml(path)
    request["subject_manifest"]["expires"] = "whenever"
    state._write_yaml_atomic(path, request)
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.create_lease(state, task["id"])


def test_flipping_revoked_back_does_not_restore_an_approval(state):
    """Revocation is recorded by MOVING the minted request out of approvals/consumed/, so the
    boolean in the approval file is what a human reads, not what a gate trusts."""
    _pr, task = _analysis_task(state)
    apr = _analysis_apr(state, [task["id"]])
    approvals.revoke(state, apr["id"])
    path = os.path.join(state.root, "approvals", apr["id"] + ".yaml")
    forged = state._read_yaml(path)
    forged["revoked"] = False
    state._write_yaml_atomic(path, forged)
    with pytest.raises(DispatchError, match="analysis"):
        dispatch.create_lease(state, task["id"])


def test_revoking_a_scope_approval_also_blocks_via_provenance(state):
    _pr, task = make_ready_task(state)
    approvals.revoke(state, state.read_item("PR-0001")["approval_ref"])
    path = state.active_path("PR-0001")
    with pytest.raises(DispatchError):
        dispatch.create_lease(state, task["id"])
    assert os.path.exists(path)


def test_a_forged_scope_approval_on_the_root_is_refused_as_a_dispatch_error(state):
    """The root route must speak the dispatch vocabulary: an ApprovalError leaking through would
    reach the user as "internal error -- the harness is broken" instead of "this approval is not
    proven" (spec II.13 wants the remedy named)."""
    pr = state.capture("PR", dict(PR_FIELDS))
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"]))
    state.transition(task["id"], "READY")
    state._write_yaml_atomic(
        os.path.join(state.root, "approvals", "APR-0001.yaml"),
        {"id": "APR-0001", "kind": "scope", "item": pr["id"], "revision": 1,
         "subject_manifest_hash": "0" * 64, "request_id": "made-up",
         "mint_code": "000000", "approved_at": "2026-07-25T00:00:00",
         "expires": None, "revoked": False})
    path = state.active_path(pr["id"])
    item = state._read_yaml(path)
    item["approval_ref"] = "APR-0001"
    state._write_yaml_atomic(path, item)
    with pytest.raises(DispatchError, match="provenance cannot be proven"):
        dispatch.create_lease(state, task["id"])


def test_a_dispatched_tasks_work_order_is_frozen(state):
    """gate layer 3 reads `allowed_scope` from the task record, so widening it on a LEASED, BOUND
    task hands a running specialist the whole repo -- with no approval and no revision bump. The
    work-order fields are frozen outside DRAFT; re-planning has to be a visible transition."""
    _task, _lease, header = leased(state)
    task_id = header["task_id"]
    for field, value in (("allowed_scope", ["/"]), ("forbidden_scope", []),
                         ("assigned_role", "frontend-developer"), ("acceptance_refs", ["AC-9"]),
                         ("dependencies", []), ("type", "implementation")):
        with pytest.raises(Exception, match="frozen outside"):
            state.update_item(task_id, {field: value})
    # the value the FIXTURE gave this order, not a literal: `a_scope_of_its_own` hands out one
    # per order since C-2, and what is measured here is that the frozen field did not move
    assert state.read_item(task_id)["allowed_scope"] == _task["allowed_scope"]


def test_a_draft_task_can_still_be_re_planned(state):
    """The freeze must not make planning impossible -- DRAFT is where re-planning belongs."""
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"]))
    assert state.update_item(task["id"], {"allowed_scope": ["src/", "tests/"]})[
        "allowed_scope"] == ["src/", "tests/"]


def test_flags_stay_writable_on_a_dispatched_task(state):
    """`blocked_by` is a flag, not a status (spec II.2 Querregeln), and design_ref is set by the
    design-promotion path -- neither may be caught by the freeze."""
    _task, _lease, header = leased(state)
    assert state.update_item(header["task_id"], {"blocked_by": "BUG-0001"})
    assert state.update_item(header["task_id"], {"design_ref": "DSN-0001"})


def test_update_item_cannot_retype_a_task_out_of_the_design_gate(state):
    """The sanctioned edit path has to enforce the same closed vocabulary as capture -- otherwise
    an orchestrator that hits the capture-time refusal simply re-types the task afterwards."""
    header = _ui_task(state, design_ref=None)
    # an ILLEGAL value is refused by the vocabulary...
    with pytest.raises(Exception, match="unknown TSK type"):
        state.update_item(header["task_id"], {"type": "ui-implementation"})
    # ...and a vocabulary-LEGAL one by the freeze, which is the half the closed
    # vocabulary alone did not cover
    with pytest.raises(Exception, match="frozen outside"):
        state.update_item(header["task_id"], {"type": "implementation"})
    with pytest.raises(DispatchError, match="design_ref"):
        dispatch.validate_dispatch(state, header, "frontend-developer")


# -- agent binding (spike S3; the platform gives SubagentStart no join key) ----

def test_role_claim_binds_the_single_pending_dispatch(state):
    _task, _lease, header = leased(state)
    dispatch.mark_awaiting_bind(state, header["task_id"])
    bound = dispatch.bind_agent_by_role(state, "agent-abc", TSK_FIELDS["assigned_role"])
    assert bound["agent_id"] == "agent-abc"
    assert dispatch.task_for_agent(state, "agent-abc")["id"] == header["task_id"]


def test_role_claim_ignores_a_different_role(state):
    _task, _lease, header = leased(state)
    dispatch.mark_awaiting_bind(state, header["task_id"])
    with pytest.raises(dispatch.NoPendingDispatch):
        dispatch.bind_agent_by_role(state, "agent-abc", "frontend-developer")


def test_two_same_role_dispatches_refuse_to_guess(state):
    """The platform limit, made visible: SubagentStart carries no key back to the tool call, so
    two concurrent same-role dispatches cannot be told apart. Binding the wrong one would run
    one specialist under another's allowed_scope -- a silent hole in gate layer 3."""
    _pr, first = make_ready_task(state)
    second = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001",
                                              allowed_scope=a_scope_of_its_own(state)))
    state.transition(second["id"], "READY")
    for task_id in (first["id"], second["id"]):
        dispatch.create_lease(state, task_id)
        dispatch.mark_awaiting_bind(state, task_id)
    with pytest.raises(dispatch.AmbiguousBinding, match="refusing to"):
        dispatch.bind_agent_by_role(state, "agent-abc", TSK_FIELDS["assigned_role"])


def test_different_roles_in_parallel_bind_cleanly(state):
    """The restriction is same-role only; parallel batches across roles must keep working."""
    _pr, backend = make_ready_task(state)
    frontend = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001",
                                                assigned_role="frontend-developer",
                                                allowed_scope=a_scope_of_its_own(state)))
    state.transition(frontend["id"], "READY")
    for task_id in (backend["id"], frontend["id"]):
        dispatch.create_lease(state, task_id)
        dispatch.mark_awaiting_bind(state, task_id)
    assert dispatch.bind_agent_by_role(state, "a1", "backend-developer")["task_id"] == backend["id"]
    assert dispatch.bind_agent_by_role(state, "a2", "frontend-developer")["task_id"] == frontend["id"]


def test_an_expired_bind_window_is_not_claimable(state):
    """A failed spawn must not leave a slot a later, undispatched subagent can walk into."""
    _task, _lease, header = leased(state)
    dispatch.mark_awaiting_bind(state, header["task_id"])
    path = os.path.join(state.root, "tasks", "leases", header["task_id"] + ".lease.yaml")
    stale = state._read_yaml(path)
    stale["awaiting_bind_until"] = time.time() - 1
    state._write_yaml_atomic(path, stale)
    with pytest.raises(dispatch.NoPendingDispatch):
        dispatch.bind_agent_by_role(state, "agent-abc", TSK_FIELDS["assigned_role"])


def test_task_for_agent_is_none_for_an_unbound_agent(state):
    leased(state)
    assert dispatch.task_for_agent(state, "never-bound") is None
    assert dispatch.task_for_agent(state, None) is None


# -- what makes a claim stand, and what returns one that produced nothing ----------------------

def _age_the_claim(state, task_id):
    """Push a claim's bind window into the past -- the only lever a test has on a clock."""
    path = os.path.join(state.root, "tasks", "leases", task_id + ".lease.yaml")
    lease = state._read_yaml(path)
    lease["awaiting_bind_until"] = time.time() - 1
    state._write_yaml_atomic(path, lease)
    return lease


def test_a_claim_stands_only_while_its_child_can_still_arrive(state):
    """The definition, read off the running code: a claim is evidence that a child was asked for,
    and it is worth something for exactly as long as the ask can still produce one.

    The term it replaces was an eternal `dispatched_at`, undone only by two hook events -- one of
    which (`PermissionDenied`) fired in none of twelve measured real sessions. That made a claim
    on a spawn nobody ever started a ~900 s dead end."""
    _task, _lease, header = leased(state)
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    lease = state._read_yaml(os.path.join(state.root, "tasks", "leases",
                                          header["task_id"] + ".lease.yaml"))
    assert "awaiting its child" in dispatch.spent_claim_reason(lease)
    assert dispatch.spent_claim_reason(_age_the_claim(state, header["task_id"])) is None


def test_a_bound_child_makes_a_claim_stand_for_as_long_as_it_runs(state):
    """The term that never expires. A child can outlive any window, and its lease must stay
    unclaimable while it does -- otherwise the second-claim rule would evaporate BIND_WINDOW
    seconds after every successful spawn."""
    _task, _lease, header = leased(state)
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    dispatch.bind_agent(state, header["task_id"], "child-1")
    _age_the_claim(state, header["task_id"])
    lease = state._read_yaml(os.path.join(state.root, "tasks", "leases",
                                          header["task_id"] + ".lease.yaml"))
    assert "already bound" in dispatch.spent_claim_reason(lease)


def test_a_claim_that_produced_no_child_is_reconciled_back_to_ready(state):
    """The way back, and it asks no hook event for permission -- which is the point: measured
    2026-08-02, a permission refusal delivers no event at all. Four conditions, all four
    load-bearing; the three tests below take one away each."""
    task, _lease, header = leased(state)
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    _age_the_claim(state, task["id"])
    assert dispatch.reconcile_unstarted_dispatches(state) == [task["id"]]
    assert state.read_item(task["id"])["status"] == "READY"
    with pytest.raises(DispatchError, match="no lease"):
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)


def test_the_reconciliation_leaves_an_undispatched_lease_alone(state):
    """No claim, nothing failed. Sweeping here would take a task away from the role that is about
    to spawn against it."""
    task, _lease, _header = leased(state)
    assert dispatch.reconcile_unstarted_dispatches(state) == []
    assert state.read_item(task["id"])["status"] == "LEASED"


def test_the_reconciliation_leaves_a_running_child_alone(state):
    """A bound child is a child that started. Freeing its task would let somebody else lease work
    that is already being done, by an agent still holding that task's allowed_scope."""
    task, _lease, header = leased(state)
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    dispatch.bind_agent(state, task["id"], "child-1")
    _age_the_claim(state, task["id"])
    assert dispatch.reconcile_unstarted_dispatches(state) == []
    assert state.read_item(task["id"])["status"] == "LEASED"


def test_the_reconciliation_leaves_a_claim_inside_its_window_alone(state):
    """The child may still be on its way. Reconciling here would race the spawn it is about to
    clean up after."""
    task, _lease, header = leased(state)
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    assert dispatch.reconcile_unstarted_dispatches(state) == []
    assert state.read_item(task["id"])["status"] == "LEASED"


def test_the_sweep_command_reports_a_claim_that_produced_no_child(state, capsys):
    """THE THIRD CALL SITE, and the one a role is SENT to. `create_lease`'s refusal says "wait,
    then `python scripts/harness.py sweep-leases`", and the sweep only ran the TTL backstop — so a
    lease spent on a spawn the permission layer refused was reported as "released to READY: -" by
    the very command the message named, and stayed for the rest of its 900 s.

    Both lines are read, because the second is what made the wait measurable in the first place:
    the id must appear as released, and nothing must still be listed as leased."""
    from kernel import cli
    task, _lease, header = leased(state)
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    _age_the_claim(state, task["id"])
    assert cli.main(["--root", state.root, "sweep-leases"]) == 0
    output = capsys.readouterr().out
    assert "released to READY: %s" % task["id"] in output, output
    assert "still leased: -" in output, output
    assert state.read_item(task["id"])["status"] == "READY"


def _pending(state, name):
    return os.path.join(state.root, "approvals", "pending", name + ".yaml")


def test_the_request_sweep_removes_what_can_never_mint_and_nothing_else(state, capsys):
    """P4-12: three unanswered approval requests, no command to clear them.

    MEASURED (pilot 4, half 3): an office project ended with three requests in
    `approvals/pending/` that nobody had answered. They were already inert -- expired requests do
    not mint, `open_requests` leaves them out -- but the user asked what those files were and the
    apparatus had to say that nothing removes them.

    THE THREE OUTCOMES ARE MEASURED IN ONE RUN, because the risk of a cleanup is what it takes with
    it: the expired one goes, the LIVE one stays and still mints afterwards, and a file this
    command cannot read is left standing AND named. Run through the entry point's parser, so the
    command is measured on the surface a role types.
    """
    from kernel import cli
    pr = state.capture("PR", dict(PR_FIELDS))
    live = approvals.create_pending_request(state, "scope", pr["id"])
    dead = approvals.create_pending_request(state, "scope", pr["id"], ttl_seconds=-1)
    with open(_pending(state, "APR-REQ-broken"), "w", encoding="utf-8") as handle:
        handle.write("this: [is not: yaml\n")

    assert cli.main(["--root", state.root, "sweep-requests"]) == 0
    output = capsys.readouterr().out
    assert dead["request_id"] in output and live["request_id"] in output, output
    assert "APR-REQ-broken.yaml" in output, output

    assert not os.path.exists(_pending(state, dead["request_id"]))
    assert os.path.exists(_pending(state, live["request_id"]))
    assert os.path.exists(_pending(state, "APR-REQ-broken"))
    # ...and the survivor is not merely a file: the answer to its question still mints.
    mint_via_hook(state, live)
    assert state.read_item(pr["id"])["approval_ref"], "the surviving request no longer mints"


def test_the_reconciliation_does_not_undo_a_recorded_outcome(state):
    """`IN_PROGRESS` means PostToolUse already said the spawn started. A window that closed
    afterwards says nothing about that, and rolling the task back would contradict a measurement
    with the absence of one."""
    task, _lease, header = leased(state)
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    dispatch.spawn_outcome(state, task["id"], True)
    _age_the_claim(state, task["id"])
    assert dispatch.reconcile_unstarted_dispatches(state) == []
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"


# -- the transition gate: an edge an approval COMMITS is that approval's to walk ----------------

def _gated_edges():
    """{(item type, from, to) -> kinds} for every edge some approval kind commits.

    Read out of `APPROVAL_TRANSITIONS` here as well, because the tests below need the SUBJECTS,
    not a second opinion about them. What is not tautological is what each test then does with an
    edge -- build a real item, walk it, and see the kernel refuse or allow.
    """
    edges = {}
    for (item_type, kind), edge in approvals.APPROVAL_TRANSITIONS.items():
        edges.setdefault((item_type,) + edge, set()).add(kind)
    return edges


def test_a_root_item_cannot_leave_its_initial_status_without_the_users_approval(state):
    """The measured hole: `transition PR-0002 APPROVED` walked a root item out of DRAFT.

    HOW WIDE THE NET UNDER THIS GATE IS, measured so the next reader does not overestimate it:
    stubbing `assert_transition_approved` to `return None` turns FOUR tests red, all in this
    module. `test_state`, `test_report`, `test_e2e` and `test_staging_cli` stay green, because
    `conftest.walk_to_status` mints on every gated edge and therefore never depends on the refusal.
    That is the correct behaviour for a fixture -- it walks the sanctioned route -- and it does
    mean the gate's proof lives here and in the two scaffolded acceptance tests, nowhere else.

    `gate_git` refuses a merge for an item still in its initial status BECAUSE nothing has
    approved the work, so a status the supervised party can set itself was a value that gate had
    no business reading. The refusal names the kind, the item and the revision, because a role
    that hits it has to know which approval to ask for.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    with pytest.raises(ApprovalError) as refused:
        state.transition(pr["id"], "APPROVED")
    message = str(refused.value)
    assert "scope" in message and pr["id"] in message and "revision 1" in message, message
    assert state.read_item(pr["id"])["status"] == "DRAFT"


def test_the_gated_edges_are_exactly_the_ones_the_mint_walks(state):
    """WHICH edges are gated, pinned as an answer rather than derived twice.

    The derivation itself (`required_approval_kinds` inverts `APPROVAL_TRANSITIONS`) cannot fail a
    test written from the same map, so what is asserted is the four CONSEQUENCES the review asked
    about by name. Each is a live decision, and the day one changes this test is where the change
    has to be made deliberately:

      * the TSK middle rides on leases and `submit-result`, never on an approval -- so no edge of
        the TSK automaton is gated, and the retry rule stays a caller argument;
      * `SR` (PROPOSED -> ACCEPTED) is NOT gated, and that is the finding rather than the design:
        accepting a technical contract under a root looks like something a user should sign, but
        no APR kind has a manifest that describes an SR. Gating it needs a KIND first, which is a
        spec decision;
      * an ABANDONMENT edge is never gated -- dropping work is not approving it. What counts as
        abandonment is DERIVED and no longer a list of status words: a terminal reachable from
        SEVERAL statuses at once is the shape of "closed because it was given up" (REJECTED,
        SUPERSEDED, CANCELLED, DUPLICATE, ABORTED, RETIRED), which is the same distinction
        `backlog_types.confirming_edge` draws one level up. The list this line used to carry had
        already been patched once with a bare `target != "ACCEPTED"`, and it was the second
        outcome terminal (`ACCEPTED_EXCEPTION`, FR-0087) that showed the enumeration for what it
        was;
      * an OUTCOME terminal -- one with exactly one incoming edge -- MAY be gated, and which ones
        are is a decision, so both ends of that set are held below;
      * `DEC`/`INV` have no automaton at all, so the question never reaches the approval check.
    """
    gated = set(_gated_edges())
    for item_type, automaton in backlog_types.AUTOMATA.items():
        for source, target in sorted(automaton.allowed):
            kinds = approvals.required_approval_kinds(item_type, source, target)
            assert bool(kinds) == ((item_type, source, target) in gated)
            if item_type == "TSK":
                assert not kinds, "a TSK edge became approval-bound: %s -> %s" % (source, target)
            sources = {src for src, dst in automaton.allowed if dst == target}
            if target in automaton.terminals and len(sources) > 1:
                assert not kinds, (
                    "%s %s -> %s ends in a terminal several statuses reach, which is what "
                    "abandonment looks like, and it is now gated -- an item that cannot be "
                    "abandoned is the other failure" % (item_type, source, target))
    # BOTH ENDS of the outcome half: an outcome terminal that quietly stopped being gated is as
    # much a change as one that quietly became gated, and each of these two was a user decision.
    outcomes = {edge for edge in gated
                if edge[2] in backlog_types.AUTOMATA[edge[0]].terminals}
    assert outcomes == {("PR", "DELIVERED", "ACCEPTED"), ("RQ", "DELIVERED", "ACCEPTED"),
                        ("BUG", "TRIAGED", "ACCEPTED_EXCEPTION")}, sorted(outcomes)
    assert not approvals.required_approval_kinds("SR", "PROPOSED", "ACCEPTED"), (
        "SR acceptance became approval-bound -- if an APR kind now describes an SR, delete this "
        "assertion and say so in the docstring above")
    for item_type in ("DEC", "INV"):
        assert item_type not in backlog_types.AUTOMATA


def _apr_of_kind(state, item_id, kind):
    directory = os.path.join(state.root, "approvals")
    for name in sorted(os.listdir(directory)):
        if name.startswith("APR-") and name.endswith(".yaml"):
            apr = state._read_yaml(os.path.join(directory, name))
            if apr.get("item") == item_id and apr.get("kind") == kind:
                return apr
    raise AssertionError("no %s approval for %s" % (kind, item_id))


def _delivery_then_scope(state):
    """A PR that is APPROVED and carries a valid, unused DELIVERY approval at revision 1.

    WHY THE ORDER IS THIS WAY ROUND, because it looks odd and is the honest answer to "show the
    gate letting a legitimate transition through". A mint WALKS the edge it commits, so a scope
    approval and a PR still in DRAFT cannot coexist -- the moment the scope APR exists the item is
    already APPROVED, and the automaton, not the approval check, is what answers
    `transition PR-0001 APPROVED`. A delivery approval minted while the item is still DRAFT has no
    status effect (its source is APPROVED), so it is the one way to hold a valid approval for an
    edge nobody has walked yet. Everything downstream of that -- valid, revoked, edited -- is then
    measurable on a real transition.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    mint_via_hook(state, approvals.create_pending_request(state, "delivery", pr["id"]))
    assert state.read_item(pr["id"])["status"] == "DRAFT"
    approve_scope(state, pr["id"])
    assert state.read_item(pr["id"])["status"] == "APPROVED"
    return pr, _apr_of_kind(state, pr["id"], "delivery")


def test_a_valid_approval_lets_the_gated_edge_through(state):
    pr, _apr = _delivery_then_scope(state)
    assert state.transition(pr["id"], "IN_DELIVERY")["status"] == "IN_DELIVERY"


def test_a_revoked_approval_does_not_authorise_the_transition(state):
    """BOTH halves of a revocation, because `revoke` writes two things and only one is the proof.

    A full `revoke` MOVES the minted request out of `approvals/consumed/`, so the provenance check
    refuses before the flag is ever read -- which is exactly why `revoke` writes the flag first:
    its own docstring records that a crash between the two writes can leave the flag WITHOUT the
    move, never the move without the flag. So the second half here is that crash state, written by
    hand: flag set, request still consumed. Without it, deleting the flag check entirely left this
    test green (mutation-measured), i.e. the flag branch was asserted by nothing.
    """
    pr, apr = _delivery_then_scope(state)
    approvals.revoke(state, apr["id"])
    with pytest.raises(ApprovalError, match="revoked|REVOKED"):
        state.transition(pr["id"], "IN_DELIVERY")
    assert state.read_item(pr["id"])["status"] == "APPROVED"

    second, other = _delivery_then_scope(state)
    path = os.path.join(state.root, "approvals", other["id"] + ".yaml")
    record = state._read_yaml(path)
    record["revoked"] = True                       # the crash window: flag written, move pending
    state._write_yaml_atomic(path, record)
    with pytest.raises(ApprovalError, match="is revoked"):
        state.transition(second["id"], "IN_DELIVERY")
    assert state.read_item(second["id"])["status"] == "APPROVED"


def test_an_out_of_band_edit_closes_the_gated_edge(state):
    """The hash is recomputed from the item's CURRENT content, so an IDE edit shuts the door.

    `risks` rather than `goal`, because the delivery manifest is what this approval hashes and
    `goal` is not in it -- editing a field the approval does not cover would prove the check runs
    on the wrong manifest and still pass.
    """
    pr, _apr = _delivery_then_scope(state)
    path = state.active_path(pr["id"])
    item = state._read_yaml(path)
    item["risks"] = ["a risk nobody approved"]
    state._write_yaml_atomic(path, item)
    with pytest.raises(ApprovalError, match="out-of-band"):
        state.transition(pr["id"], "IN_DELIVERY")


def test_an_expiring_approval_kind_cannot_even_be_created_for_a_gated_edge(state):
    """"Expired" is unreachable for the gated kinds, BY CONSTRUCTION -- so it is pinned, not faked.

    Spec II.2 time-boxes `routine`/`analysis`/`push` and content-invalidates `scope`/`delivery`/
    `acceptance`; `create_pending_request` refuses an expiry on the second group, and no
    (item type, expiring kind) pair exists in `APPROVAL_TRANSITIONS`. So the expiry branch in
    `assert_apr_in_force` is dead for transitions and live for dispatch, which is where
    `routine`/`analysis` approvals actually authorise something. Asserted rather than explained:
    the day a gated edge gets an expiring kind, this goes red and that branch needs a test of its
    own on the transition path too.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    for kinds in _gated_edges().values():
        assert not (kinds & approvals.EXPIRING_KINDS), kinds
    with pytest.raises(ApprovalError, match="carry an expiry"):
        approvals.create_pending_request(state, "scope", pr["id"],
                                         approval_expires=time.time() + 60)


def test_no_optional_argument_of_transition_can_skip_the_approval_check(state):
    """Spec II.4: bootstrap "ist kein Config-Flag (der Lead koennte sein eigenes Gate umgehen)".

    Derived from the SIGNATURE, not from a list of forbidden names: every optional parameter of
    both transition entry points is tried with truthy and falsy values, and the gated edge has to
    stay refused for all of them. A `force=`/`bootstrap=`/`skip_approval=` added later is caught
    the day it is added, whatever it is called -- a test that matched names would only catch the
    names somebody had already thought of.

    A VARIADIC PARAMETER IS ITSELF THE DEFECT, and that half was missing: with
    `(self, item_id, to_status, approved_retry=False, **kwargs)` the loop above enumerates nothing
    new, so `bootstrap=True` reached the body and moved the item -- measured. A `*args`/`**kwargs`
    on a gate entry point means the surface cannot be enumerated at all, so it is refused outright
    rather than probed.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    for entry in (ProjectState.transition, ProjectState._transition_locked):
        parameters = inspect.signature(entry).parameters
        variadic = [name for name, parameter in parameters.items()
                    if parameter.kind in (inspect.Parameter.VAR_KEYWORD,
                                          inspect.Parameter.VAR_POSITIONAL)]
        assert not variadic, (
            "%s takes %s -- a gate entry point whose arguments cannot be enumerated cannot be "
            "proven free of a bypass, and this test would silently stop covering the new ones"
            % (entry.__qualname__, variadic))
        optional = [name for name, parameter in parameters.items()
                    if parameter.default is not inspect.Parameter.empty]
        assert optional, "%s has no optional parameter -- the loop below asserts nothing" % entry
        for name in optional:
            for value in (True, 1, "yes", False, None):
                # EACH ENTRY POINT IS PROBED WITH ITS OWN PARAMETERS. Until 2026-09-11 both loops
                # called `transition`, so a parameter that exists only on `_transition_locked` was
                # enumerated and then never tried on the function that has it -- the inner entry
                # point, which is the one every in-process caller (the mint included) uses. It
                # surfaced as a TypeError the day `regenerate` was added; the hole it names is that
                # a bypass parameter added to the inner entry point alone was covered by nothing.
                with pytest.raises(ApprovalError):
                    if entry is ProjectState.transition:
                        state.transition(pr["id"], "APPROVED", **{name: value})
                    else:
                        with state.lock:
                            state._transition_locked(pr["id"], "APPROVED", **{name: value})


def _possible_statuses(node, constants=None):
    """Every status an assignment expression can produce, or None when that cannot be bounded.

    FIVE KINDS OF SHAPE, and each one's values come from the kernel map that produces them rather
    than from a list here: a string literal; a module-level string constant bound to exactly one
    value (`constants`, e.g. `dispatch.LEASE_MINTED_STATUS` -- as readable as the quoted string it
    stands for, the same reason `_module_string_constants` reads such a name as a KEY); a
    conditional between two of them (`submit_result`); a call to a kernel function whose whole range
    is a kernel map (`initial_status`, `invalidation_target`, `migration_archive_status`,
    `widest_status`); a lookup in `_NON_AUTOMATON_INITIAL_STATUS`. Anything else is None, which the
    caller reports -- fail-closed, because the shape this whole check exists for
    (`item["status"] = transition[1]` in the old `mint`) is exactly an expression a reader cannot
    bound. `constants` defaults to empty, so a caller that passes none reads only literals.

    `migration_archive_status` is the V1 import's archive write (SR-0004), and reading it here is
    what keeps the caller's verdict honest rather than excusing it: the function is bounded by
    `migration_writable_statuses`, and the caller re-derives what that set may hold from the
    kernel's own gate (`approvals.required_approval_kinds`) instead of trusting it. Widening it to
    hand back a status behind an approval edge turns the caller RED.

    A KERNEL FUNCTION TAKING THE ITEM TYPE ANSWERS PER TYPE, so its values come back as
    `(item type, status)` pairs and the caller judges each against THAT type. Flattening them was
    measured wrong the day the archive path became a per-type answer: `SR ACCEPTED` is reachable
    without any approval, `PR ACCEPTED` is not, and one set of bare strings has to call that pair
    either an offender or safe -- both of which are false about one of the two. WHAT THE PAIRING
    ASSUMES, since nothing here can check it: that the type handed to such a function is the type
    of the item being written. Every call site in this kernel writes the item it just asked about;
    a writer that passed one type's name while stamping another type's item would be read too
    kindly here, and nothing else in this reader would catch it either.
    """
    from kernel.backlog_types import AUTOMATA, INVALIDATION_TARGET
    from kernel import state as kernel_state
    from kernel.state import migration_writable_statuses

    constants = constants or {}
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    # A SIXTH SHAPE, and it is the one that produces NO status at all: a string REPEATED. The only
    # thing such an expression can be is a filler of a length -- `migrate.item_size` builds a body
    # to measure and throws it away, and it needs a placeholder that can never be shorter than the
    # real value. Reading it as unbounded made a MEASUREMENT an offender the day `widest_status()`
    # first returned an approval-bound word (`ACCEPTED_EXCEPTION`, FR-0087); reading it as the
    # empty set is the honest answer -- no status of any type is `"x" * n`, so this writer can
    # produce none. The bound is on the SHAPE and not on the callee's name, so it does not excuse
    # one function.
    if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)
            and any(isinstance(side, ast.Constant) and isinstance(side.value, str)
                    for side in (node.left, node.right))):
        return set()
    if isinstance(node, ast.Name) and node.id in constants:
        return {constants[node.id]}
    if isinstance(node, ast.IfExp):
        left = _possible_statuses(node.body, constants)
        right = _possible_statuses(node.orelse, constants)
        return None if left is None or right is None else left | right
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "initial_status":
            return {(item_type, automaton.chain[0]) for item_type, automaton in AUTOMATA.items()}
        if node.func.id == "invalidation_target":
            return set(INVALIDATION_TARGET.items())
        if node.func.id == "migration_archive_status":
            return {(item_type, status) for item_type in AUTOMATA
                    for status in migration_writable_statuses(item_type)}
        if node.func.id == "widest_status":
            return {backlog_types.widest_status()}
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id.upper() == node.value.id):
        # A LOOKUP IN A KERNEL MAP, whatever the index is. The NAME has to be a module-level
        # constant of `kernel.state` -- published, and spelled as a constant -- so that a LOCAL
        # variable whose name happens to collide with one cannot be read as bounded; that
        # collision is the shape this whole check exists for. The index is deliberately not read:
        # what bounds the write is the map's own values, so a writer that picks its status out of
        # `kernel.state`'s vocabulary is bounded by that vocabulary even when the choice is
        # computed -- and one that picks it out of something the kernel does not publish is
        # unbounded and stays a finding. (`_NON_AUTOMATON_INITIAL_STATUS` used to be named here on
        # its own; it is one such map and needs no case of its own.)
        published = getattr(kernel_state, node.value.id, None)
        values = (published.values() if isinstance(published, dict)
                  else published if isinstance(published, (tuple, list, frozenset, set)) else None)
        if values is not None and all(isinstance(one, str) for one in values):
            return set(values)
    return None


# The one function that lands BYTES on disk. A NAME rather than the set, because the set is what
# `_store_calls` derives FROM it -- and the test named in that function is what keeps the name true.
#
# IT IS THE BYTE WRITER AND NOT THE SERIALISER, since `kernel.presets` gave the kernel a second
# shape of content to put on disk (one FIELD of a kit document, whose comments a YAML round-trip
# would delete). `_write_yaml_atomic` is now a serialiser in front of this one, so deriving the
# closure from the byte writer keeps every route that existed AND covers the ones that carry text
# rather than a mapping -- deriving it from the serialiser would have been silent about those.
_THE_WRITER = "_write_text_atomic"
# ...and the serialiser in front of it, named for the premise below: those two are the whole of
# what puts data on disk in `kernel/state.py`, and a third name there is a route the closure
# cannot see.
_THE_SERIALISER = "_write_yaml_atomic"

# HOW A FUNCTION IS SPELLED. Every reader in this file that asks "what does this function do" has
# to see both forms, because Python has two and a kernel that grows a coroutine grows it without
# telling anybody. Named once so the answer cannot differ between readers.
_DEFINITION_NODES = tuple(getattr(ast, name) for name in ("FunctionDef", "AsyncFunctionDef")
                          if hasattr(ast, name))

# WHAT MAKES A CALL A PERSISTING PRIMITIVE -- the property `_store_calls` rests on, asked of the
# call rather than of one library function's name.
#
# The premise below has to answer "does anything in `kernel/state.py` put data on disk except
# `_write_yaml_atomic`". It used to ask for the attribute `safe_dump`, which is one spelling of one
# library's one function: a `yaml.dump`, a `json.dump`, a `Path(...).write_text` or a
# `handle.write(...)` would all have been invisible to it, so the premise could be true of the name
# and false of the module. The property instead is: the call SERIALISES or WRITES, which every one
# of those spells in its own identifier, or it OPENS A PATH in a mode that is not read-only.
#
# Calls to functions the module defines itself are excluded, and that is what keeps the rule from
# collapsing: `self._write_yaml_atomic(...)` carries "write" in its name too, and counting it would
# make every caller of the writer a writer. Those routes are exactly what `_store_calls`'s closure
# already follows, so the premise is about the PRIMITIVES underneath them.
_WRITE_WORDS = ("write", "dump")
_READ_MODES = ("r", "rb")


def _persisting_primitives(tree):
    """{function name: {the primitive calls in it that can put data on disk}}.

    THREE ANSWERS FOR `open`, and the middle one is the correction of 2026-08-05: NO mode argument
    at all is reading, because that is what `open` defaults to; a mode argument this cannot read as
    a literal COUNTS, because an unknown mode is not a proof of reading; a literal read mode is
    reading. The middle case used to be folded into the first -- `open(path, mode)` with the mode
    in a variable was skipped -- while this docstring said the opposite of what the code did.
    `test_the_store_has_exactly_one_writer_for_this_derivation_to_rest_on`'s probe carries all
    three, so neither half can drift from the other again.

    WHAT THIS STILL DOES NOT SEE, named because the sentence above is only about `open`: a
    primitive that moves, copies or removes a path rather than writing bytes through a handle --
    `os.replace`, `os.rename`, `shutil.copyfile`, a `zipfile` member write. None of them carries
    `write` or `dump` in its own name, so `_WRITE_WORDS` cannot reach them, and no property of a
    bare AST call distinguishes them from a read on the same module. The probe measures that this
    is the state of affairs rather than leaving the paragraph to be believed.
    """
    defined = {node.name for node in ast.walk(tree) if isinstance(node, _DEFINITION_NODES)}
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, _DEFINITION_NODES):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            name = getattr(inner.func, "attr", getattr(inner.func, "id", ""))
            if name in defined:
                continue
            if name == "open":
                given = list(inner.args[1:2]) + [word.value for word in inner.keywords
                                                 if word.arg == "mode"]
                if not given:
                    continue
                literal = [one.value for one in given if isinstance(one, ast.Constant)]
                if literal and str(literal[0]).lower() in _READ_MODES:
                    continue
                found.setdefault(node.name, set()).add(name)
            elif any(word in name.lower() for word in _WRITE_WORDS):
                found.setdefault(node.name, set()).add(name)
    return found


def _store_calls(tree=None):
    """EVERY ROUTE A MAPPING TAKES INTO THE STORE -- derived from `kernel/state.py`'s call graph.

    THE PROPERTY: `_write_yaml_atomic` is the one function in this kernel that puts a mapping on
    disk, so a call is a store call exactly when it can REACH that function. Nothing is listed,
    which is the correction of 2026-08-04: the tuple this replaces promised "every route" in its
    own comment and did not know `capture_migrated_archive` -- the route the same round added.
    Latent that day (the new writer is guarded), and latent is not the property the comment claimed.

    THE PREMISE IS ASSERTED WHERE IT IS USED, not assumed:
    `test_the_store_has_exactly_one_writer_for_this_derivation_to_rest_on` fails the moment a
    second function in `kernel/state.py` dumps YAML of its own, because the closure below would
    then be silent about it.

    Read as bare NAMES, because that is what the two consumers can see: `_persisted_names` asks
    which local names a call persists, and `_first_store_call` asks where the earliest such call
    stands. Both parse other kernel modules too (`dispatch.py` reaches the store through
    `state.capture`), and a method name is what a call there spells.

    `tree` is the kernel's own by default; a caller passes one so the CLOSURE can be measured on a
    shape whose answer is known, which is not something the shipped file can be asked for.
    """
    if tree is None:
        with open(os.path.join(TEAM_KITS, "kernel", "state.py"), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
    called_by = {}
    for node in ast.walk(tree):
        # BOTH DEFINITION FORMS. `ast.FunctionDef` alone made a route through an `async def`
        # invisible -- the closure below would have grown no further from it, so a coroutine
        # reaching the writer would have been read as reaching nothing. Measured on a sample tree,
        # not argued: `test_the_store_has_exactly_one_writer_for_this_derivation_to_rest_on`.
        if isinstance(node, _DEFINITION_NODES):
            called_by[node.name] = {getattr(inner.func, "attr", getattr(inner.func, "id", ""))
                                    for inner in ast.walk(node) if isinstance(inner, ast.Call)}
    reaching, growing = {_THE_WRITER}, True
    while growing:
        growing = False
        for name, calls in called_by.items():
            if name not in reaching and calls & reaching:
                reaching.add(name)
                growing = True
    return frozenset(reaching)


# Computed once: the two readers below have to give ONE answer to "is this call a store call", and
# a per-call derivation would be one answer per reader again.
_STORE_CALLS = _store_calls()


def _position(node):
    """(line, column) -- what "before" means for two nodes of one parsed body."""
    return (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))


def _first_store_call(function_node):
    """Position of the earliest call in this body that hands a mapping to the store, or None."""
    positions = [_position(node) for node in ast.walk(function_node)
                 if isinstance(node, ast.Call)
                 and getattr(node.func, "attr", getattr(node.func, "id", "")) in _STORE_CALLS]
    return min(positions) if positions else None


def _ast_types(*names):
    """The `ast` classes with these names that this Python has -- `TryStar` is 3.11+."""
    return tuple(getattr(ast, name) for name in names if hasattr(ast, name))


# WHERE PYTHON CAN DECIDE NOT TO EVALUATE A CHILD. This is an enumeration, so it carries a tripwire
# at each end -- and BOTH nets are named here, because for one round only the first was, and the
# claim it made was wider than what it caught:
#   * `test_every_construct_that_can_skip_a_child_is_classified` sweeps the grammar for nodes with
#     a SUITE-shaped or comprehension field and fails on one that is in neither list, including one
#     a future Python adds. That net catches statements and comprehensions and nothing else: it
#     looks at field NAMES, and `ast.Assert._fields` is `("test", "msg")` -- so `assert x, guard()`
#     fell straight through it, `_unconditional_children` read the message as fully evaluated, and
#     a refusal in an assert message counted as a running guard although Python evaluates it only
#     when the assertion FAILS. `BoolOp` was in the list only because somebody typed it there.
#   * `test_python_itself_decides_which_of_these_places_refuses_the_write` EXECUTES every shape in
#     the two tables below and derives each one's label from whether a refusal there really stops
#     the write, so the tables state a measurement rather than a belief. The reader is then judged
#     against those labels by `test_a_guard_in_a_part_that_may_be_skipped_is_not_a_guard`, which is
#     the test that goes red when a shape here is classified wrongly.
# THE RESIDUAL, since two nets are not all of Python: a construct that can skip a child, carries no
# suite-shaped field AND is in neither table is still read as fully evaluated.
_CONDITIONALLY_EVALUATED = _ast_types(
    "If", "While", "For", "AsyncFor", "Try", "TryStar", "Match", "match_case", "ExceptHandler",
    "BoolOp", "IfExp", "ListComp", "SetComp", "DictComp", "GeneratorExp", "Assert",
    "Lambda", "FunctionDef", "AsyncFunctionDef")
# ...and the other half of that sweep: branch-shaped nodes whose body IS entered on every path
# through them. A `with` body runs (its context manager may swallow what the body raises, which is
# an argument about the RAISE and not about the guard running); a class body runs where it stands.
_UNCONDITIONAL_BODIES = _ast_types("With", "AsyncWith", "ClassDef", "Module", "Interactive",
                                   "Expression")
_TRY_TYPES = _ast_types("Try", "TryStar")


def _unconditional_children(node):
    """The children evaluated on EVERY path, given this node is evaluated at all."""
    if isinstance(node, ast.BoolOp):
        return node.values[:1]            # `a and b` / `a or b` evaluate `a`, and then maybe `b`
    if isinstance(node, ast.IfExp):
        return [node.test]
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return [node.generators[0].iter] if node.generators else []
    if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
        return []                         # a body that runs when something CALLS it, not here
    if isinstance(node, (ast.If, ast.While)):
        return [node.test]
    if isinstance(node, ast.Assert):
        # The MESSAGE is evaluated only when the assertion fails, so a guard there is a guard on
        # the failing path alone -- and `python -O` drops the whole statement.
        return [node.test]
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.iter]                # an empty iterable enters the body zero times
    if isinstance(node, ast.Match):
        return [node.subject]
    if isinstance(node, _ast_types("ExceptHandler", "match_case")):
        return []
    if isinstance(node, _TRY_TYPES):
        # A HANDLER THAT CAN FALL THROUGH TURNS THE GUARD'S RAISE INTO A NO-OP -- execution
        # continues after the `try` and reaches the write with nothing refused. So the body counts
        # only when NO handler can fall through, which is decidable without knowing which
        # exceptions a handler names: a handler whose last statement is a `raise` or a `return`
        # ends the path the write is on. `else` rides on the same condition (it is skipped exactly
        # when the body raised); `finally` runs whatever happened.
        escaping = all(handler.body and isinstance(handler.body[-1], (ast.Raise, ast.Return))
                       for handler in node.handlers)
        return (list(node.body) + list(node.orelse) if escaping else []) + list(node.finalbody)
    return list(ast.iter_child_nodes(node))


def _certainly_evaluated(function_node):
    """Every node this function evaluates on EVERY path through it.

    WHAT AN UNORDERED `ast.walk` CANNOT SAY, and this is the correction of 2026-08-04. The guard
    reader below accepted any qualifying call anywhere in the body, with no order and no
    reachability -- measured against the real `kernel/state.py`: moving `capture_preflight(...)`
    to AFTER `_write_yaml_atomic` was accepted, and so was putting it inside `if False:`. Both are
    a writer with no running guard, which is exactly what the check exists to report.

    THE FIRST CUT OF THAT FIX CLASSIFIED STATEMENTS AND HANDED THE REST TO `ast.walk`, which is the
    same hole one spelling further along: `False and self.capture_preflight(...)`, `True or ...`,
    `... if False else None`, a `match` whose case never matches and a guard inside a `try` whose
    handler swallows the refusal were all read as a running guard, and the first of those is
    literally the `if False:` mutant of the round before. So the property is applied to the whole
    grammar and in one place (`_unconditional_children`): a node is reached when every step from
    the function's body down to it is taken without a condition deciding otherwise.

    The `if` STATEMENT itself is therefore reached while its branches are not -- which is what the
    caller needs, because an inline raise-guard hangs off the test that IS evaluated.
    """
    reached, frontier = [], list(function_node.body)
    while frontier:
        node = frontier.pop()
        reached.append(node)
        frontier.extend(_unconditional_children(node))
    return reached


def _persisted_names(tree, function_name):
    """The local names a function PERSISTS as an item file, i.e. hands to `_write_yaml_atomic`.

    THE SUBJECT FILTER, and without it the reader below is unusable rather than merely narrow.
    "Can this expression write a `status` key" has no sound AST answer for a computed key or an
    opaque merge -- but the question that matters is narrower: can it write the status of a
    MAPPING THAT BECOMES AN ITEM FILE. That is decidable: the payload of `_write_yaml_atomic` is
    exactly the mapping that lands on disk, so a merge into anything else (a hashlib digest, a
    field-contract dict, a capability matrix) is not this check's business. Flagging those made
    the first cut report 31 sites, all noise -- a check nobody can keep green protects nothing.
    """
    for node in ast.walk(tree):
        if not (isinstance(node, _DEFINITION_NODES) and node.name == function_name):
            continue
        names = set()
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            called = getattr(inner.func, "attr", getattr(inner.func, "id", ""))
            # EVERY ROUTE INTO THE STORE, not just the one spelled `_write_yaml_atomic(p, item)`.
            # Two blind spots were measured: a payload that is not a bare name
            # (`_write_yaml_atomic(p, dict(item))`, `(p, {**item})`) and a mapping handed to
            # `capture`/`update_item`, which is what `dispatch.create_task` does after
            # `task_fields.update(...)`. Any Name INSIDE the argument counts, because that is the
            # mapping whose contents end up on disk.
            if called not in _STORE_CALLS:
                continue
            for argument in inner.args[1:] if called == "_write_yaml_atomic" else inner.args:
                for part in ast.walk(argument):
                    if isinstance(part, ast.Name):
                        names.add(part.id)
        return names
    return set()


_UNREADABLE_KEY = object()


def _module_string_constants(tree, imported=None):
    """{name: value} for module-level `NAME = "literal"` bindings that hold ONE string, always.

    A subscript key spelled as such a constant is as readable as a quoted one -- `item[FIELD] = x`
    where `FIELD = "approved_hash"` writes `approved_hash` and nothing else -- and reading it is
    what keeps the kernel free to name its own field constants instead of retyping the string at
    every write site. A name that is ever bound to something else, or to two different strings, is
    left out: "I can see one of its values" is not the same as "I know what it is", and the whole
    point of the reader below is that the second answer is the only safe one.

    `imported` is {name: literal} for names this module takes from a sibling where they ARE such a
    constant (`_imported_string_constants`), so a module-level ALIAS of one -- `RUNG_KEY =
    TSK_RUNG_FIELD`, which is how `dispatch` spells the field `backlog_types` declares (DEC-0091)
    -- reads as the literal it stands for. Without it the alias was an unreadable key and every
    write through it an offender (measured 2026-09-11 on `create_lease`). The same rule as for a
    literal: bound twice, or to anything else as well, and the name is out.
    """
    imported = dict(imported or {})
    values, rejected = {}, set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                literal = node.value.value
            elif isinstance(node.value, ast.Name) and node.value.id in imported:
                literal = imported[node.value.id]
            else:
                rejected.add(target.id)
                continue
            if values.setdefault(target.id, literal) != literal:
                rejected.add(target.id)
    # a name imported and then rebound in this module is rebound, whatever it was imported as
    for name in list(imported):
        if name in values or name in rejected:
            rejected.add(name)
    values.update({name: value for name, value in imported.items() if name not in rejected})
    return {name: value for name, value in values.items() if name not in rejected}


def _imported_string_constants(tree, siblings):
    """{name as imported: literal} for every `from .<sibling> import NAME` whose NAME is a one-string
    constant of that sibling (`siblings` is {module name: its `_module_string_constants`}).

    ONE HOP, deliberately: the sibling's constants are read without following ITS imports, so a
    chain two modules long stays unreadable and surfaces as an offender rather than resolving to
    a guess. A name imported under an alias is known by the alias, which is the name the module
    then writes with.
    """
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not node.module or node.level != 1:
            continue
        constants = siblings.get(node.module.split(".")[0], {})
        for alias in node.names:
            if alias.name in constants:
                found[alias.asname or alias.name] = constants[alias.name]
    return found


def _status_writes(tree, constants=None):
    """(function name, value node or None) for every expression that can SET an ITEM's `status`.
    `constants` is the module's readable string constants; the module's own literals when the
    caller passes none, the package-resolved map (`_imported_string_constants`) when it does.

    THE READER IS FAIL-CLOSED IN BOTH DIRECTIONS, and it was not. It first read only
    `x["status"] = ...`, so `x.update({"status": "APPROVED"})` walked past it (mutation-measured
    green). Widening it to three syntaxes fixed that case and left the SHAPE of the defect: an
    unbounded VALUE was an offender while an unreadable FORM was silence -- so `i |= {...}`, a
    computed key, and `i.update(changes)` (which is in the running kernel) reported nothing.

    Now a form this reader cannot bound yields `(where, None)`, exactly like a value it cannot
    bound. What it reads:
      * a subscript assignment whose key can be READ -- a string literal, or a module constant
        bound to exactly one string (`_module_string_constants`) -> the value node. Any receiver:
        the key is visible, so the value is the only open question.
      * `.update({...})` / `dict(..., status=...)` naming the key -> the value node.
      * on a PERSISTED receiver only (`_persisted_names`): a subscript assignment with a computed
        key, an `.update(<not a dict literal>)`, and an augmented `|=` -> None.
    A sixth spelling would still be missed, which is why the test below parses a sample of each
    and fails when one stops being recognised: a reader that quietly narrows is the failure mode.
    """
    holder = {}
    for node in ast.walk(tree):
        if isinstance(node, _DEFINITION_NODES):
            for inner in ast.walk(node):
                holder[inner] = node.name
    persisted = {name: _persisted_names(tree, name) for name in set(holder.values())}
    constants = _module_string_constants(tree) if constants is None else constants
    found = []

    def persisted_receiver(node, where):
        return isinstance(node, ast.Name) and node.id in persisted.get(where, set())

    def written_key(slice_node):
        if isinstance(slice_node, ast.Constant):
            return slice_node.value
        if isinstance(slice_node, ast.Name) and slice_node.id in constants:
            return constants[slice_node.id]
        return _UNREADABLE_KEY

    for node in ast.walk(tree):
        where = holder.get(node, "<module>")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Subscript):
                    continue
                key = written_key(target.slice)
                if key is not _UNREADABLE_KEY:
                    if key == "status":
                        found.append((where, node.value))
                elif persisted_receiver(target.value, where):
                    found.append((where, None))      # a computed key may be "status"
        elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.BitOr):
            if persisted_receiver(node.target, where):
                found.append((where, None))          # `item |= {...}` merges an unread mapping
        elif isinstance(node, ast.Call):
            named = (node.func.attr if isinstance(node.func, ast.Attribute)
                     else getattr(node.func, "id", ""))
            if named not in ("update", "dict"):
                continue
            for keyword in node.keywords:
                if keyword.arg == "status":
                    found.append((where, keyword.value))
            for argument in node.args:
                if isinstance(argument, ast.Dict):
                    for key, value in zip(argument.keys, argument.values):
                        if isinstance(key, ast.Constant) and key.value == "status":
                            found.append((where, value))
                elif (named == "update" and isinstance(node.func, ast.Attribute)
                        and persisted_receiver(node.func.value, where)):
                    found.append((where, None))      # merges a mapping this reader cannot read
    return found


def _collections_with_the_key(tree):
    """Module-level names bound to a literal collection that contains "status"."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, (ast.Tuple, ast.List, ast.Set)):
            continue
        if any(isinstance(element, ast.Constant) and element.value == "status"
               for element in node.value.elts):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def _refuses_the_key(tree, function_name, _seen=None):
    """Does this function REFUSE a `status` in its input before it writes anything?

    The one sanctioned answer to an unreadable form, and it is a property rather than a name: a
    function that raises after testing its input against a collection containing "status" cannot
    write one however opaquely it merges. Two shapes of that test are read, because the kernel
    uses both -- a literal tuple in the comparison (`_update_item_locked`) and a module constant
    iterated over (`capture`, over `_KERNEL_SET`) -- and the constant is RESOLVED rather than
    named, so a renamed constant keeps working and an emptied one stops.

    ...AND A GUARD MAY BE DELEGATED, which is the addition of 2026-08-04 and it is a widening of
    the READER, not of what counts as a guard. `state.capture` used to spell the refusal inline;
    the migration needed the same checks before it PLANS a write, so they moved into
    `capture_preflight` and `capture` now calls it as its first statement. Nothing about the
    running protection changed -- a `status` in a capture body still raises before anything is
    merged -- but a per-function reader saw `capture` merging an opaque mapping with no guard in
    its own body and reported it. Following ONE call into a sibling of the same module keeps the
    question honest: the refusal still has to exist in the running source and still has to be
    reachable from the writer. `_seen` is the recursion guard; a mutual pair proves nothing and
    resolves to False rather than to a loop.

    ...AND IT HAS TO RUN BEFORE THE WRITE, which that widening did not require and which is the
    whole claim being made. A guard is counted only when it is `_certainly_evaluated` -- on every
    path through the body -- and only when it stands EARLIER than `_first_store_call`, the first
    expression of the same body that hands a mapping to the store. Both directions were measured
    against the real `kernel/state.py` and both were accepted before this: the guard moved behind
    `_write_yaml_atomic`, and the guard parked in an `if False:`. A body with no store call at all
    persists nothing, so the ordering requirement is vacuous there rather than a refusal.
    """
    holders = _collections_with_the_key(tree)
    _seen = set() if _seen is None else _seen
    if function_name in _seen:
        return False
    _seen = _seen | {function_name}

    def tests_the_key(node):
        """Does this expression test something against a collection containing "status"?"""
        for inner in ast.walk(node):
            sources = []
            if isinstance(inner, ast.Compare):
                sources = list(inner.comparators)
            elif isinstance(inner, ast.comprehension):
                sources = [inner.iter]
            for source in sources:
                if isinstance(source, ast.Name) and source.id in holders:
                    return True
                if isinstance(source, (ast.Tuple, ast.List, ast.Set)) and any(
                        isinstance(element, ast.Constant) and element.value == "status"
                        for element in source.elts):
                    return True
        return False

    for node in ast.walk(tree):
        if not (isinstance(node, _DEFINITION_NODES) and node.name == function_name):
            continue
        # THE RAISE HAS TO HANG ON THE TEST, which the first version did not require: it asked for
        # a `raise` SOMEWHERE and a membership test SOMEWHERE, so an unrelated
        # `raise ValueError("empty")` beside an unrelated comprehension over the constant made an
        # opaque writer look guarded -- measured, and it suppressed a real offender. Now the `if`
        # itself has to be the guard: either its condition tests the key, or its condition names a
        # local that was computed from such a test, and its body has to raise.
        assigned = {target.id: statement.value
                    for statement in ast.walk(node) if isinstance(statement, ast.Assign)
                    for target in statement.targets if isinstance(target, ast.Name)}
        limit = _first_store_call(node)
        certain = _certainly_evaluated(node)

        def in_time(candidate):
            return limit is None or _position(candidate) < limit

        for branch in certain:
            if not isinstance(branch, ast.If) or not in_time(branch):
                continue
            if not any(isinstance(inner, ast.Raise) for inner in ast.walk(branch)):
                continue
            if tests_the_key(branch.test):
                return True
            for inner in ast.walk(branch.test):
                if (isinstance(inner, ast.Name) and inner.id in assigned
                        and tests_the_key(assigned[inner.id])):
                    return True
        # ...or the guard is one call away, in a sibling of this same module. Only a call whose
        # own definition is HERE counts, so the refusal being read is one this tree really
        # contains; an imported name resolves to nothing and stays an offender.
        defined = {inner.name for inner in ast.walk(tree) if isinstance(inner, _DEFINITION_NODES)}
        for inner in certain:
            if not isinstance(inner, ast.Call) or not in_time(inner):
                continue
            called = (inner.func.attr if isinstance(inner.func, ast.Attribute)
                      else getattr(inner.func, "id", None))
            if called in defined and _refuses_the_key(tree, called, _seen):
                return True
        return False
    return False


def test_the_reader_that_finds_direct_status_writes_sees_every_shape_it_claims_to():
    """The reader below is only worth its floor if it does not silently narrow.

    Each sample is one syntax Python offers for setting the key, and each has to be FOUND with its
    value bounded. The subscript-only version of this reader passed the whole suite while
    `task.update({"status": "APPROVED"})` was invisible to it -- so the reader gets its own test,
    ahead of the check that depends on it.
    """
    bounded = {
        "subscript": 'def f(i):\n    i["status"] = "APPROVED"\n',
        # a module constant as the key is as readable as the quoted string, and the kernel writes
        # its own fields that way (`approvals.APPROVED_CONTENT_HASH_FIELD`) — so it must be READ,
        # not counted as an unbounded computed key. Both directions matter and both are here: this
        # one resolves to `status`, and the `constant_key_elsewhere` sample below resolves to a
        # different field and is therefore not a status write at all.
        "constant_key": 'K = "status"\ndef f(i):\n    i[K] = "APPROVED"\n',
        # a module constant as the VALUE is as readable as the quoted string, and the kernel writes
        # one that way (`dispatch.create_lease` -> `task["status"] = LEASE_MINTED_STATUS`): it must
        # RESOLVE, not surface as a value this reader cannot bound.
        "constant_value": 'V = "APPROVED"\ndef f(i):\n    i["status"] = V\n',
        "update_dict": 'def f(i):\n    i.update({"status": "APPROVED"})\n',
        "update_keyword": 'def f(i):\n    i.update(status="APPROVED")\n',
        "dict_keyword": 'def f(i):\n    j = dict(i, status="APPROVED")\n',
    }
    for name, source in bounded.items():
        tree = ast.parse(source)
        writes = _status_writes(tree)
        assert len(writes) == 1, "%s: the reader found %d writes" % (name, len(writes))
        assert _possible_statuses(writes[0][1], _module_string_constants(tree)) == {"APPROVED"}, name
    # ...and the forms it CANNOT bound have to surface as unbounded rather than as nothing: the
    # asymmetry between "value I cannot read" (offender) and "form I cannot read" (silence) is
    # what let `i.update(changes)`, `i |= {...}` and a computed key past this reader entirely.
    # ...on a PERSISTED receiver, which is the subject filter: the same shapes on a hashlib
    # digest or a field-contract dict are not this check's business (see `_persisted_names`).
    persist = '    s._write_yaml_atomic(p, i)\n'
    unbounded = {
        "update_variable": 'def f(i, c, s, p):\n    i.update(c)\n' + persist,
        "aug_or": 'def f(i, c, s, p):\n    i |= c\n' + persist,
        "computed_key": 'def f(i, k, s, p):\n    i[k] = "APPROVED"\n' + persist,
    }
    for name, source in unbounded.items():
        writes = _status_writes(ast.parse(source))
        assert len(writes) == 1, "%s: the reader found %d writes" % (name, len(writes))
        assert _possible_statuses(writes[0][1]) is None, name
    assert not _status_writes(ast.parse('def f(i):\n    i["title"] = "APPROVED"\n'))
    # a constant key that names ANOTHER field is not a status write...
    assert not _status_writes(ast.parse(
        'K = "approved_hash"\ndef f(i):\n    i[K] = "x"\n')), "constant_key_elsewhere"
    # ...and a name the module rebinds is not readable at all, so it stays an unbounded write on a
    # persisted receiver rather than resolving to whichever binding this reader happened to see
    rebound = ('K = "approved_hash"\nK = "status"\n'
               'def f(i, s, p):\n    i[K] = "x"\n' + persist)
    assert _status_writes(ast.parse(rebound)) == [("f", None)], "rebound module constant"
    # A CONSTANT IMPORTED FROM A SIBLING, and an alias of it, read as the literal they stand for
    # (`dispatch.RUNG_KEY = TSK_RUNG_FIELD`, DEC-0091) -- in both directions: an alias of the
    # status key IS a status write, an alias of another field is not, and an imported name this
    # module REBINDS is unreadable again. One hop only: a name the sibling itself imports is not
    # resolved (`chained`), so it surfaces as unbounded rather than as a guess.
    declaring = ast.parse('FIELD = "status"\nOTHER = "approved_hash"\nFAR = "status"\n')
    siblings = {"contract": _module_string_constants(declaring),
                "hop": _module_string_constants(ast.parse("from .contract import FAR\n"))}
    aliasing = ast.parse('from .contract import FIELD, OTHER\nKEY = FIELD\nELSE = OTHER\n'
                         'def f(i):\n    i[KEY] = "APPROVED"\n'
                         'def g(i):\n    i[ELSE] = "APPROVED"\n'
                         'def h(i):\n    i[FIELD] = "APPROVED"\n')
    resolved = _module_string_constants(aliasing, _imported_string_constants(aliasing, siblings))
    assert resolved == {"FIELD": "status", "OTHER": "approved_hash", "KEY": "status",
                        "ELSE": "approved_hash"}, resolved
    assert sorted(where for where, _value in _status_writes(aliasing, resolved)) == ["f", "h"]
    rebinds = ast.parse('from .contract import FIELD\nFIELD = "title"\n'
                        'def f(i, s, p):\n    i[FIELD] = "x"\n' + persist)
    rebinds_map = _module_string_constants(rebinds, _imported_string_constants(rebinds, siblings))
    assert "FIELD" not in rebinds_map and _status_writes(rebinds, rebinds_map) == [("f", None)]
    chained = ast.parse('from .hop import FAR\ndef f(i, s, p):\n    i[FAR] = "x"\n' + persist)
    chained_map = _module_string_constants(chained, _imported_string_constants(chained, siblings))
    assert "FAR" not in chained_map and _status_writes(chained, chained_map) == [("f", None)]
    # the guard that makes an unreadable merge provably safe, and its absence
    guarded = ('def g(c, i):\n'
               '    bad = [k for k in c if k in ("id", "status")]\n'
               '    if bad:\n        raise ValueError(bad)\n'
               '    i.update(c)\n')
    assert _refuses_the_key(ast.parse(guarded), "g")
    # ...and through a module constant, which is how `capture` spells the same guard
    via_constant = ('KEYS = ("id", "status")\n'
                    'def g(c, i):\n'
                    '    bad = [k for k in KEYS if k in c]\n'
                    '    if bad:\n        raise ValueError(bad)\n'
                    '    i.update(c)\n')
    assert _refuses_the_key(ast.parse(via_constant), "g")
    # ...and an unrelated raise beside an unrelated membership test is NOT a guard: that shape
    # made an opaque writer look protected while nothing connected the two.
    unrelated = ('KEYS = ("id", "status")\n'
                 'def g(c, i):\n'
                 '    if not c:\n        raise ValueError("empty")\n'
                 '    noise = [k for k in KEYS]\n'
                 '    i.update(c)\n')
    assert not _refuses_the_key(ast.parse(unrelated), "g")
    assert not _refuses_the_key(ast.parse('def g(c, i):\n    i.update(c)\n'), "g")


def _capture_mutant(mutate):
    """The REAL `kernel/state.py`, with one change made to `capture`, re-parsed.

    Mutated through the AST and round-tripped with `ast.unparse` rather than by editing text: the
    reader below compares POSITIONS, so a mutant whose nodes kept their original line numbers
    would answer a question about the file on disk instead of about itself.
    """
    with open(os.path.join(TEAM_KITS, "kernel", "state.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, _DEFINITION_NODES) and node.name == "capture")
    # WHICH statement is the guard is asked of the body's shape, not counted: it is the one
    # top-level statement of `capture` that is a bare call. Taking `body[0]` moved the DOCSTRING
    # instead, and both mutants then stayed green for a reason that had nothing to do with the
    # reader -- measured, and it is why this assertion is here rather than a comment.
    calls = [index for index, statement in enumerate(function.body)
             if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)]
    assert len(calls) == 1, "`capture` no longer delegates through exactly one bare call"
    mutate(function, calls[0])
    return ast.parse(ast.unparse(tree))


def test_the_guard_reader_requires_the_refusal_to_run_and_to_run_first():
    """B7: `capture` merges a mapping this reader cannot bound, and only a RUNNING guard excuses it.

    The excuse used to be "some qualifying call exists somewhere in the body", which an unordered
    `ast.walk` answers and which is not the property. Both counter-examples are built out of the
    kernel that ships, so this measures the real `capture`/`capture_preflight` pair rather than a
    sample written to agree with the reader:

      * the guard call moved to AFTER `_write_yaml_atomic` -- the body then writes the item first
        and refuses afterwards, which refuses nothing;
      * the guard call parked in an `if False:` -- present in the source, never executed.

    Each mutant must still be SEEN as an unbounded write (otherwise the reader would be silent for
    a different reason and this test would prove nothing), and must be refused as unguarded. The
    unmutated kernel is the positive control on both branches of the reader: `capture` through the
    delegated call, `_update_item_locked` through its own inline `if ... raise`.
    """
    with open(os.path.join(TEAM_KITS, "kernel", "state.py"), encoding="utf-8") as handle:
        original = ast.parse(handle.read())
    assert ("capture", None) in _status_writes(original), (
        "`capture` no longer merges an unbounded mapping, so this test measures nothing")
    assert _refuses_the_key(original, "capture")
    assert _refuses_the_key(original, "_update_item_locked")

    def delay(function, where):
        """Move the guard call to just before the `with` block's last statement."""
        guard = function.body.pop(where)
        block = next(node for node in function.body if isinstance(node, ast.With))
        block.body.insert(len(block.body) - 1, guard)

    def never_run(function, where):
        function.body[where] = ast.If(test=ast.Constant(value=False),
                                      body=[function.body[where]], orelse=[])

    for name, mutate in (("guard after the write", delay),
                         ("guard behind `if False:`", never_run)):
        mutant = _capture_mutant(mutate)
        assert ("capture", None) in _status_writes(mutant), name
        assert not _refuses_the_key(mutant, "capture"), (
            "%s is accepted as a guard, so a writer with no running refusal passes" % name)


def test_the_store_has_exactly_one_writer_for_this_derivation_to_rest_on():
    """`_store_calls` is a closure back from ONE function, so that premise is measured, not assumed.

    THREE HALVES, and the first one is the premise that used to be measured too narrowly. It asked
    for the attribute `safe_dump`, which is one function of one library: a second writer spelled
    `yaml.dump`, `json.dump`, `Path(...).write_text` or `handle.write(...)` was invisible to it, so
    the premise was true of a NAME while the module could have grown a route around it.
    `_persisting_primitives` asks the property instead -- does this function call something that
    serialises or writes, or open a path in a mode that is not read-only -- and the probe below
    puts each of those four spellings in front of it, so a reader that narrows again fails here
    rather than staying silent about a route.

    The closure itself is measured on shapes whose answer is known: it has to be TRANSITIVE (a
    caller of a caller of the writer is a route), it has to see an `async def` the same as a `def`
    -- a coroutine reaching the writer was invisible while `called_by` collected `ast.FunctionDef`
    alone -- and it has to leave everything else out. A `_store_calls` that returned its starting
    point plus one level would pass the whole suite while `capture` -- which reaches the writer
    through `_regenerate_index_locked` as well -- looked like a leaf.
    """
    with open(os.path.join(TEAM_KITS, "kernel", "state.py"), encoding="utf-8") as handle:
        source = handle.read()
    kernel = ast.parse(source)
    writing = _persisting_primitives(kernel)
    assert set(writing) == {_THE_WRITER, _THE_SERIALISER}, (
        "kernel/state.py puts data on disk from %s; `_store_calls` derives every route into the "
        "store from %r alone (with %r the serialiser in front of it), so any other writer is a "
        "route it cannot see" % (sorted(writing), _THE_WRITER, _THE_SERIALISER))
    assert _THE_SERIALISER in _store_calls(), (
        "%r no longer reaches %r, so a mapping can now be put on disk on a route the closure does "
        "not follow" % (_THE_SERIALISER, _THE_WRITER))

    # THE READER'S OWN BOTH-ENDED PROBE: spellings of a write, which must all be seen, and shapes
    # that only READ, which must not be -- a rule that flags reading too would be satisfied by
    # flagging everything and would say nothing about the premise. `h` is the mode this reader
    # cannot resolve, and it is here because the docstring claimed it counted while the code
    # skipped it; `f` is the neighbouring case that must stay out, since `open` with no mode at
    # all IS reading.
    probe = ast.parse(
        "def a(p, d):\n    yaml.dump(d, open(p, 'w'))\n"
        "def b(p, d):\n    json.dump(d, p)\n"
        "def c(p, d):\n    Path(p).write_text(d)\n"
        "async def e(p, d):\n    handle = open(p, mode='a')\n    handle.write(d)\n"
        "def f(p):\n    return yaml.safe_load(open(p, encoding='utf-8'))\n"
        "def g(p):\n    return open(p, 'rb').read()\n"
        "def h(p, m):\n    return open(p, m)\n"
        "def i(p, m):\n    return open(p, mode=m)\n")
    assert set(_persisting_primitives(probe)) == {"a", "b", "c", "e", "h", "i"}, (
        _persisting_primitives(probe))

    # THE RESIDUAL, MEASURED RATHER THAN DESCRIBED. A primitive that moves, copies or removes a
    # path puts data on disk and this reader does not see it. That is a documented gap in the
    # premise, not a property of `kernel/state.py` -- which reaches `os.replace` only from inside
    # the byte writer -- and it is asserted here so that the paragraph in
    # `_persisting_primitives` cannot quietly stop matching the code in either direction.
    residual = ast.parse(
        "def j(a, b):\n    os.replace(a, b)\n"
        "def k(a, b):\n    shutil.copyfile(a, b)\n"
        "def m(a, b):\n    os.rename(a, b)\n")
    assert not _persisting_primitives(residual), (
        "the move/copy primitives are visible to this reader now -- the residual named in "
        "`_persisting_primitives` is closed and its paragraph is the thing that is now false")

    sample = ast.parse(
        "def %s(p, d):\n    pass\n"
        "def near(self, d):\n    self.%s('p', d)\n"
        "async def far(self, d):\n    self.near(d)\n"
        "def unrelated(self, d):\n    self.parse_id(d)\n" % (_THE_WRITER, _THE_WRITER))
    assert _store_calls(sample) == {_THE_WRITER, "near", "far"}, _store_calls(sample)
    # ...and on the shipped kernel the route THIS round added is in it. Named because it is the
    # route the tuple this replaces did not know: a writer with its own field contract (DEC-0004)
    # is exactly the one a reader must not lose sight of.
    assert "capture_migrated_archive" in _STORE_CALLS, sorted(_STORE_CALLS)


def test_every_construct_that_can_skip_a_child_is_classified():
    """The unlisted-construct end of `_CONDITIONALLY_EVALUATED`'s tripwire.

    `_unconditional_children` reads anything it does not recognise as fully evaluated, so a grammar
    node that CAN skip a child and is in neither list is a hole that opens silently. The sweep is
    over `ast` itself -- every node type with a branch-shaped field -- so a construct a future
    Python adds arrives here unclassified and fails, instead of being read as unconditional by a
    reader written before it existed.
    """
    branching = {name for name in dir(ast)
                 if isinstance(getattr(ast, name), type)
                 and issubclass(getattr(ast, name), ast.AST)
                 and set(getattr(getattr(ast, name), "_fields", ()))
                 & {"body", "orelse", "handlers", "finalbody", "cases", "generators"}}
    classified = {node.__name__ for node in _CONDITIONALLY_EVALUATED + _UNCONDITIONAL_BODIES}
    assert not branching - classified, (
        "these AST nodes carry a branch and neither list says whether it is entered on every "
        "path: %s" % sorted(branching - classified))
    assert not set(_CONDITIONALLY_EVALUATED) & set(_UNCONDITIONAL_BODIES)


_SKIPPABLE_GUARD_PLACES = {
    # `and`/`or` short-circuit, and the first of these is the `if False:` mutant of the round
    # before in expression form
    "and": "    False and g(c)\n",
    "or": "    True or g(c)\n",
    "conditional expression": "    g(c) if False else None\n",
    "comprehension element": "    [g(c) for _x in ()]\n",
    "lambda body": "    (lambda: g(c))\n",
    "loop body": "    for _x in ():\n        g(c)\n",
    "while body": "    while False:\n        g(c)\n",
    "match case": "    match 1:\n        case 2:\n            g(c)\n",
    "swallowed try body": "    try:\n        g(c)\n    except Exception:\n        pass\n",
    "except handler": "    try:\n        pass\n    except Exception:\n        g(c)\n",
    "nested definition": "    def h():\n        g(c)\n",
    "if branch": "    if False:\n        g(c)\n",
    # `ast.Assert._fields` carries no suite-shaped name, so the grammar sweep never saw this one
    "assert message": "    assert True, g(c)\n",
}

_ALWAYS_GUARD_PLACES = {
    "plain statement": "    g(c)\n",
    "with body": "    with open('x'):\n        g(c)\n",
    "try body with no handler": "    try:\n        g(c)\n    finally:\n        pass\n",
    "try body under a re-raising handler":
        "    try:\n        g(c)\n    except Exception:\n        raise\n",
    "else under a re-raising handler":
        "    try:\n        pass\n    except Exception:\n        raise\n    else:\n        g(c)\n",
    "finally": "    try:\n        pass\n    except Exception:\n        pass\n"
               "    finally:\n        g(c)\n",
    "first operand of and": "    g(c) and False\n",
    "test of a conditional expression": "    None if g(c) else None\n",
    "iterable of a loop": "    for _x in [g(c)]:\n        pass\n",
    "match subject": "    match g(c):\n        case _:\n            pass\n",
    "assert test": "    assert g(c) or True\n",
}


def _guard_stops_the_write(where):
    """Does a REFUSAL at `where` actually stop the write? -- measured by executing the shape.

    THE OBSERVABLE IS THE WRITE, not whether the call was evaluated, and the difference is a whole
    entry of the table: in `try: g(c) except Exception: pass` the guard IS evaluated and its
    refusal is then swallowed, so execution walks on to the write with nothing refused. What the
    reader claims about a place is exactly this -- a guard here refuses -- so this is what gets
    measured.

    The two tables above are the corpus the reader is judged against, and a corpus whose labels are
    typed by hand is a second belief rather than a second opinion: `assert True, g(c)` was believed
    to run by the reader AND would have been believed by whoever wrote the table. Here Python
    answers: the same source `_guarded_source` builds is compiled and run with a guard that raises,
    and the answer is whether `_write_yaml_atomic` was reached.

    `open` is stubbed because one shape uses a `with`, and the shape under test is the `with`, not
    the file system. The raising guard is installed AFTER the exec, so it replaces the `g` the
    source defines in the same namespace `f` resolves its globals from.
    """
    written = []

    def refuse(_c):
        raise ValueError("refused")

    class _Store:
        def _write_yaml_atomic(self, path, data):
            written.append(path)

    namespace = {"open": lambda *args, **kwargs: contextlib.nullcontext()}
    exec(compile(_guarded_source(where), "<probe>", "exec"), namespace)   # noqa: S102 -- the probe
    namespace["g"] = refuse
    try:
        namespace["f"]({"title": "x"}, {}, _Store(), "p")
    except ValueError:
        pass
    return not written


def test_python_itself_decides_which_of_these_places_refuses_the_write():
    """The corpus's labels are a MEASUREMENT, so the reader is judged against the interpreter.

    WHAT THIS TEST IS AND WHAT IT IS NOT, because the neighbouring claim is easy to make here and
    would be untrue: this does NOT go red when `_unconditional_children` is wrong -- it never looks
    at the reader. It goes red when a LABEL in the two tables is wrong, which is the half nothing
    measured before. The reader is judged one test up
    (`test_a_guard_in_a_part_that_may_be_skipped_is_not_a_guard`), and that one is what turns red
    when `ast.Assert` is taken back out of `_unconditional_children` -- measured 2026-08-05:
    "a refusal in the assert message is accepted, so a writer with no running guard passes".
    The chain only holds with both links: the label is Python's answer, and the reader must match
    the label.
    """
    for name, where in _SKIPPABLE_GUARD_PLACES.items():
        assert not _guard_stops_the_write(where), (
            "%r is in the skippable table, but a refusal there really does stop the write" % name)
    for name, where in _ALWAYS_GUARD_PLACES.items():
        assert _guard_stops_the_write(where), (
            "%r is in the always-evaluated table, but a refusal there does not stop the write"
            % name)
    assert not set(_SKIPPABLE_GUARD_PLACES) & set(_ALWAYS_GUARD_PLACES)


def _guarded_source(where):
    """A writer whose refusal sits at `where` -- the real delegated-guard shape, one call deep."""
    return ('def g(c):\n'
            '    if [k for k in ("id", "status") if k in c]:\n'
            '        raise ValueError(c)\n'
            'def f(c, i, s, p):\n'
            + where +
            '    i.update(c)\n'
            '    s._write_yaml_atomic(p, i)\n')


def test_a_guard_in_a_part_that_may_be_skipped_is_not_a_guard():
    """The other end of the tripwire, and the shape R-1 was about.

    Every entry is the SAME writer -- an opaque merge into a persisted mapping -- with the same
    real refusal moved into a part of one construct that Python may not evaluate. Measured against
    the reader that shipped before this: `False and self.capture_preflight(...)`, `True or ...`,
    `... if False else None`, a `match` with no matching case and a `try` whose handler swallows
    the refusal were ALL accepted as a running guard, because everything that was not a statement
    kind the reader knew about went through `ast.walk`.

    The counter-direction is the same table one entry down: a guard in a part that IS evaluated has
    to keep counting, or this check would be satisfied by refusing everything -- which is how a
    check nobody can keep green stops protecting anything.
    """
    for name, where in _SKIPPABLE_GUARD_PLACES.items():
        tree = ast.parse(_guarded_source(where))
        assert _status_writes(tree) == [("f", None)], name
        assert not _refuses_the_key(tree, "f"), (
            "a refusal in the %s is accepted, so a writer with no running guard passes" % name)
    for name, where in _ALWAYS_GUARD_PLACES.items():
        tree = ast.parse(_guarded_source(where))
        assert _status_writes(tree) == [("f", None)], name
        assert _refuses_the_key(tree, "f"), (
            "a refusal in the %s is refused, so the reader now rejects guards that do run" % name)


def _approval_bound_statuses():
    """{status: {item types that cannot reach it without a USER APPROVAL}}.

    THE OFFENDER RULE for the check below, and it is REACHABILITY rather than the approval edge's
    own target -- the correction of 2026-08-04, in the reader as well as in the kernel. A status
    further down the same chain stands behind that approval just as much: with the targets read as
    a set, a direct writer producing `VERIFIED` for a `BUG` (three chain steps behind a scope
    approval) was not an offender at all, and that is exactly the value the migration's archive
    path handed back before the same fix landed there.

    Walked with `approvals.required_approval_kinds`, which is the function `state.transition`
    itself asks whether an edge needs an APR. So this measures the gate the kernel runs, not the
    table behind it -- and it is deliberately not the same derivation as
    `state.migration_writable_statuses`, whose answer is one of the things being judged here.
    """
    from kernel.approvals import required_approval_kinds
    bound = {}
    for item_type, automaton in backlog_types.AUTOMATA.items():
        reached, frontier = {automaton.initial}, [automaton.initial]
        while frontier:
            current = frontier.pop()
            for source, target in automaton.allowed:
                if source != current or target in reached:
                    continue
                if required_approval_kinds(item_type, source, target):
                    continue
                reached.add(target)
                frontier.append(target)
        for status in automaton.states - reached:
            bound.setdefault(status, set()).add(item_type)
    return bound


def test_a_revision_card_shows_every_spot_and_is_never_a_count():
    """FR-0067's own condition: a card that says "n Einträge geändert" is not an approval.

    THE BOUND IS ON THE NUMBER OF SPOTS, NEVER ON THEIR CONTENT. So the three assertions are one
    rule read three ways: under the bound every spot stands in the question verbatim; over it the
    builder REFUSES with the count instead of shortening the list; and a revision that replaces
    and deletes nothing is sent to the route whose question promises more.

    ALL THREE CHANNELS ARE MEASURED, additions included, because that is where the promise broke:
    a revision that also grew a list printed "instruments: 3 Einträge hinzu" beside the sentence
    saying every spot stands there "niemals als Anzahl" (measured 2026-09-02). The additive route
    may count -- its own card says a list's entries are in the file -- and this one may not.

    The deletions are asserted to be readable as deletions in the card, because that is the
    "louder" half of the FR -- a replaced value can still be looked up in the document afterwards,
    a deleted one exists nowhere.
    """
    spots = ["language: ERSETZT, bisher de", "language: neu en",
             "counterparties: GELÖSCHT -- bisher []",
             "instruments: Eintrag hinzu bratsche"]
    manifest = approvals.document_revision_subject_manifest(
        "master_data.yaml", "staging/TSK-0001/master_data.yaml", "aaaa", "bbbb",
        spots[:2], [spots[2]], [spots[3]], "Steuerberater gewechselt")
    request = {"kind": "document_revision", "item": None, "revision": None,
               "subject_manifest": manifest, "subject_manifest_hash": "0" * 64,
               "request_id": "REQ-1", "mint_code": "1234"}
    question = approvals.build_question(request)["question"]
    for spot in spots:
        assert spot in question, question
    assert question.index("GELÖSCHT WIRD") < question.index("ERSETZT WIRD"), question

    too_many = ["stelle_%d: ERSETZT -- bisher a -- neu b" % index
                for index in range(approvals.MAX_PROPOSAL_CHANGES + 1)]
    with pytest.raises(ApprovalError) as refused:
        approvals.document_revision_subject_manifest(
            "master_data.yaml", "staging/TSK-0001/master_data.yaml", "aaaa", "bbbb",
            too_many, [], [], "zu viel auf einmal")
    assert str(len(too_many)) in str(refused.value) and "split it into steps" in str(refused.value)

    with pytest.raises(ApprovalError) as additive:
        approvals.document_revision_subject_manifest(
            "master_data.yaml", "staging/TSK-0001/master_data.yaml", "aaaa", "bbbb",
            [], [], ["categories.expense: 1 Eintrag hinzu"], "nur eine Ergänzung")
    assert "REPLACES or DELETES" in str(additive.value)


def test_no_direct_status_write_can_produce_a_status_an_approval_commits():
    """Every `x["status"] = ...` in the kernel, and what it is allowed to be.

    The kernel used to claim `transition` was its only status writer while `approvals.mint` and
    several dispatch and state functions wrote one directly. Rather than repeat a claim, this
    reads the running source: `_status_writes` finds every expression outside `_transition_locked`
    that can set the key (three syntaxes, self-tested above), `_possible_statuses` BOUNDS what each
    can produce from the kernel's own maps, and an expression nobody can bound is itself a failure
    -- that was exactly the old mint's shape.

    So a new direct writer is not forbidden; a direct writer that could produce a status the type
    only reaches through a user approval is, and so is one nobody can bound. WHICH statuses those
    are is `_approval_bound_statuses` and it is a walk, not the approval targets read as a set: the
    set reading made this check blind to every status further down the chain, which is how the
    archive path's write set handing back `BUG VERIFIED` passed it. (That set is
    `state.migration_writable_statuses`; the name this sentence used to carry,
    `migration_writable_terminals`, has not existed since the same round -- a dead name in a
    docstring is a pointer a reader cannot follow.)
    """
    destinations = _approval_bound_statuses()
    kernel_dir = os.path.join(TEAM_KITS, "kernel")
    offenders, writers = [], []
    trees = {}
    for name in sorted(os.listdir(kernel_dir)):
        if name.endswith(".py"):
            with open(os.path.join(kernel_dir, name), encoding="utf-8") as handle:
                trees[name] = ast.parse(handle.read())
    # every module's own one-string constants first, so an import of one resolves one hop away
    siblings = {name[:-3]: _module_string_constants(tree) for name, tree in trees.items()}
    for name, tree in trees.items():
        module_constants = _module_string_constants(
            tree, _imported_string_constants(tree, siblings))
        for function, value_node in _status_writes(tree, module_constants):
            where = "%s:%s" % (name, function)
            if where == "state.py:_transition_locked":
                continue
            writers.append(where)
            produced = _possible_statuses(value_node, module_constants)
            if produced is None:
                if _refuses_the_key(tree, function):
                    continue      # it raises on a `status` in its input before it merges anything
                offenders.append(
                    "%s writes a status this reader cannot bound -- bound it (add the shape to "
                    "`_possible_statuses`, with the kernel map it reads its values from), refuse "
                    "the key first, or route the write through the automaton" % where)
                continue
            for bounded in sorted(produced, key=str):
                # A PAIR says which type the value belongs to (a kernel function that takes the
                # item type); a bare string could be any type's, so every type carrying that
                # status is asked. See `_possible_statuses` for what the pairing rests on.
                if isinstance(bounded, tuple):
                    owners, value = {bounded[0]}, bounded[1]
                else:
                    value = bounded
                    owners = {item_type for item_type, automaton
                              in backlog_types.AUTOMATA.items() if value in automaton.states}
                clash = owners & destinations.get(value, set())
                if clash:
                    offenders.append("%s can write %r directly, which %s reaches only through an "
                                     "edge a user approval commits" % (where, value, sorted(clash)))
    # ...and the rule has to have teeth: with an empty `destinations` the loop above is a no-op and
    # this test would pass over any kernel at all.
    assert destinations, "no status of any shipped type stands behind an approval -- the check "\
                         "above then measures nothing"
    # A FLOOR THAT IS NOT A MAGIC NUMBER: the reader must have seen the two modules that really do
    # write statuses. The COUNT is deliberately not asserted -- a docstring said four while the
    # source had seven, and pinning the number here would only re-create that lie one layer down.
    assert {where.split(":")[0] for where in writers} >= {"state.py", "dispatch.py"}, writers
    assert not offenders, offenders


# -- BUG-0040: the criteria an APPROVED AMENDMENT of the root mints -------------

CR_FIELDS = {
    "title": "automatic loyalty discount",
    "target_revision": 1,
    "change_description": "a percentage discount line on every invoice",
    "acceptance_criteria": [{"id": "AC-11", "text": "a discount may be entered per invoice"}],
}


def _root_with_amendment(state, approved=True, target=None, **cr_overrides):
    """A root, and a CR amending it -- the pilot-3 shape (PR-0001 with six approved CRs)."""
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    cr = state.capture("CR", dict(CR_FIELDS, target_pr=target or pr["id"], **cr_overrides))
    if approved:
        approve_scope(state, cr["id"])          # (CR, scope) walks DRAFT -> APPROVED
    return pr, state.read_item(cr["id"])


def test_a_task_may_reference_the_criteria_an_approved_amendment_of_its_root_minted(state):
    """THE FIELD CHAIN OF BUG-0040, replayed in the shape the pilot project actually had.

    That item carries the observation and names the audit chain: approved change requests minted
    criteria, and the dispatch gate called them nonexistent. `derives_from` is the ROOT here, as
    the pilot's task had it, and that is the point -- an approved amendment changes the ROOT's
    contract, so a task serving it derives from the root and names no change request at all.
    """
    pr, cr = _root_with_amendment(state)
    assert cr["status"] == "APPROVED" and cr["approval_ref"]
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_an_unapproved_amendments_criteria_do_not_count(state):
    """The direction that must NOT widen through the amendment hop: a DRAFT amendment is a
    proposal, and the refusal names the item and the reason, because the criterion is plainly
    readable in the CR file and the difference is otherwise invisible.

    This test alone does NOT establish that an unapproved amendment lends nothing -- the task here
    derives from the root. The way round it is the neighbouring test, which names the CR in
    `derives_from`."""
    pr, cr = _root_with_amendment(state, approved=False)
    assert cr["status"] == "DRAFT"
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "exist nowhere: AC-11" in str(exc.value)
    assert cr["id"] in str(exc.value) and "DRAFT" in str(exc.value)


def test_an_unapproved_amendment_named_in_derives_from_lends_nothing(state):
    """THE WAY AROUND THE APPROVAL TERM, measured 2026-08-15 and closed.

    The amendment hop refuses a DRAFT CR. The `derives_from` hop beside it asked only that the
    origin RESOLVE -- no status, no approval -- so naming the very same CR one field over lent
    `AC-11` and the spawn PASSED. Two hops into one universe are only as strict as the looser one,
    and this is what makes the amendment path's whole approval term reachable rather than
    decorative: an amendment's criteria now enter through hop 2 or not at all.
    """
    pr, cr = _root_with_amendment(state, approved=False)
    assert cr["status"] == "DRAFT"
    header = _dispatchable(state, pr["id"], derives_from=cr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "exist nowhere: AC-11" in str(exc.value)


def test_a_bugfix_task_may_reference_a_triaged_bugs_fix_criteria(state):
    """THE COUNTER-DIRECTION TO THAT EXCLUSION, and the reason it is per-type and not blanket.

    A `BUG` is not an amendment: it names no revision of the root, its Fix-Kriterien are its own,
    and it reaches its `APPROVED` status only through a mint that a kit-less repo cannot run at all
    (H39). The kits' bugfix flow cuts tasks against a TRIAGED bug's criteria, so a status or
    approval term on the `derives_from` hop would make that flow undispatchable -- which is why the
    exclusion reads `AMENDMENT_TYPES` rather than "anything with an approvable status".
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    bug = state.capture("BUG", {"title": "checkout 500s", "related_pr": pr["id"],
                                "observed": "500", "expected": "200", "repro": "click",
                                "severity": "high",
                                "acceptance_criteria": [{"id": "AC-FIX-1", "text": "no 500"}]})
    state.transition(bug["id"], "TRIAGED")
    triaged = state.read_item(bug["id"])
    assert triaged["status"] == "TRIAGED" and not triaged["approval_ref"], (
        "premise: the bug carries no approval at all, and must still lend its criteria")
    header = _dispatchable(state, pr["id"], type="bugfix", derives_from=bug["id"],
                           acceptance_refs=["AC-FIX-1"])
    assert dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])


def test_a_criterion_smuggled_into_a_field_the_approval_does_not_sign_does_not_widen(state):
    """THE ONE LINE THAT STOPS AN UNSIGNED CRITERIA CHANNEL, given its own red test.

    `_criteria_ids` reads TWO fields; `approvals._SCOPE_FIELDS` signs only one of them. Measured
    2026-08-15 on an APPROVED CR: adding `success_criteria: [{id: AC-77}]` out of band leaves the
    scope manifest hash MATCHING, so `assert_apr_in_force` raises nothing and the criterion is
    visible to the collector. `_approval_covers_criteria`'s per-FIELD comparison is the only thing
    between that and a dispatchable criterion nobody signed -- replaced by a per-item truthiness
    test it passes, and every other test of this round stays green.

    The signed criterion of the same item keeps working, which is what tells a refusal of the
    channel apart from a refusal of the whole amendment.
    """
    pr, cr = _root_with_amendment(state)
    edited = state.read_item(cr["id"])
    edited["success_criteria"] = [{"id": "AC-77", "text": "through an unsigned field"}]
    state._write_yaml_atomic(state.active_path(cr["id"]), edited)
    live = approvals.subject_manifest_hash(
        approvals.item_subject_manifest(state.read_item(cr["id"]), "scope"))
    apr = approvals.read_apr(state, cr["approval_ref"])
    assert live == apr["subject_manifest_hash"], (
        "premise of this test: the smuggled field is OUTSIDE what the scope approval hashes, so "
        "the content check cannot be what refuses it")
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-77"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "does not carry the criteria" in str(exc.value), str(exc.value)
    assert cr["id"] in str(exc.value)


def test_a_rejected_amendments_criteria_do_not_count(state):
    """A rejection does not clear `approval_ref`, so "it once had an approval" is not the question.

    `approvals.approved_statuses` is -- the statuses an item stands in BECAUSE a user approved it
    and HAS NOT LEFT AGAIN. Without that term a CR the user turned down would keep lending its
    criteria to tasks for as long as it sat in the active directory.
    """
    pr, cr = _root_with_amendment(state)
    state.transition(cr["id"], "REJECTED")
    rejected = state.read_item(cr["id"])
    assert rejected["status"] == "REJECTED" and rejected["approval_ref"], (
        "premise of this test: the approval reference survives the rejection")
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "REJECTED" in str(exc.value)


def test_an_applied_amendments_criteria_stop_counting(state):
    """THE RESIDUE OF BUG-0040, asserted as behaviour instead of promised in a comment.

    `APPLIED` is a terminal no approval targets, so `approved_statuses` leaves it out for the same
    reason it leaves `RETIRED` out for PROC -- and once the item is archived nothing reads it at
    all. The consequence is real and named: a task cut LATER against a criterion an applied CR
    minted meets the pilot's refusal again. Widening the derivation to cover it is a decision, and
    this test is what makes that decision visible instead of letting the edge drift.
    """
    pr, cr = _root_with_amendment(state)
    state.transition(cr["id"], "APPLIED")
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "exist nowhere: AC-11" in str(exc.value) and "APPLIED" in str(exc.value)
    state.archive(cr["id"])
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert cr["id"] not in str(exc.value), (
        "an archived amendment is not read at all, so it cannot be named as the reason")


def test_an_amendment_edited_past_the_kernel_stops_widening(state):
    """WHAT MAKES THE WIDENING SAFE, measured rather than argued: the approval is the authority.

    A criterion added to an APPROVED amendment out of band -- revision not bumped, so no status
    machinery sees it -- breaks the scope manifest's content hash, and `assert_apr_in_force` then
    answers for this reader exactly as it answers for the root's own approval.

    WHAT THAT ESTABLISHES IS THE CONTENT, and only the content: `acceptance_criteria` is inside
    what a scope approval signs, so no criterion can be added to a live approval's item. It says
    nothing about MEMBERSHIP -- `target_pr` is not hashed, so a hand-edited binding re-aims signed
    criteria at another root and this check cannot see it (named where the derivation lives). Two
    neighbours cover the rest of the field surface: the criteria field the manifest does NOT sign,
    and the approval kind that signs nothing at all.
    """
    pr, cr = _root_with_amendment(state)
    edited = state.read_item(cr["id"])
    edited["acceptance_criteria"] = list(edited["acceptance_criteria"]) + [
        {"id": "AC-99", "text": "smuggled in past the kernel"}]
    state._write_yaml_atomic(state.active_path(cr["id"]), edited)
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-99"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "content hash" in str(exc.value) and cr["id"] in str(exc.value)


def test_an_approval_that_does_not_sign_the_criteria_does_not_widen(state):
    """The interaction this guarded against no longer arises through `mint` (`approvals.presents`
    keeps a hanging kind out of `approval_ref` since PR-0011 AC-8), so the reachable shape is now
    a reference written PAST the kernel: an already-APPROVED amendment whose `approval_ref` is
    pointed at a routine approval by hand leaves `status: APPROVED` beside a reference whose kind
    hashes nothing at all. Reading the KIND's own subject manifest -- rather than trusting the
    status, or naming `scope` -- is what keeps that from switching the content check off for this
    amendment. The routine mint itself is measured to leave the field alone on the way.
    """
    pr, cr = _root_with_amendment(state)
    routine = approvals.create_pending_request(
        state, "routine", cr["id"],
        manifest={"item": cr["id"], approvals.ROUTINE_ROLE_FIELD: "backend-developer",
                  "scope": ["src/**"], "trigger": "weekly", "cadence": "weekly"},
        approval_expires=time.time() + 3600)
    mint_via_hook(state, routine)
    minted = _latest_apr(state)
    assert state.read_item(cr["id"])["approval_ref"] == cr["approval_ref"], (
        "the routine mint moved the amendment's approval_ref (PR-0011 AC-8)")
    forged = state.read_item(cr["id"])
    forged["approval_ref"] = minted["id"]
    state._write_yaml_atomic(state.active_path(cr["id"]), forged)
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "does not carry the criteria" in str(exc.value)


def test_an_approved_amendment_of_another_root_does_not_widen_this_one(state):
    """The universe is derived PER ROOT. A CR approved against a different requirement is as
    approved as any other, and its criteria still belong to that other contract -- so the binding
    field, not the approval, is what decides which universe it joins."""
    other = state.capture("PR", dict(PR_FIELDS, title="unrelated"))
    approve_scope(state, other["id"])
    pr, cr = _root_with_amendment(state, target=other["id"])
    assert cr["status"] == "APPROVED"
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    assert "exist nowhere: AC-11" in str(exc.value)
    assert cr["id"] not in str(exc.value), (
        "an amendment of another root explains nothing about this refusal and must not be named")


def test_a_criterion_that_exists_nowhere_still_refuses_and_the_universe_is_listed_honestly(state):
    """The counter-direction to the whole item: widening what dispatches must not empty the check.

    The message has to be TRUE in three ways -- the criteria the approved amendment really added
    are listed as known; nothing is blamed for a reference no amendment ever offered; and the
    excluded amendment that IS in the store stays unnamed, because its criteria could not have been
    the missing one. That last part is the filter, and it needs its own excluded item to measure:
    with only an approved CR present, a reader that named every exclusion and a reader that named
    the relevant ones agree, and the difference this assertion is about is invisible.
    """
    pr, cr = _root_with_amendment(state)
    unrelated = state.capture("CR", dict(CR_FIELDS, target_pr=pr["id"], title="unrelated draft",
                                         acceptance_criteria=[{"id": "AC-55", "text": "elsewhere"}]))
    assert unrelated["status"] == "DRAFT"        # excluded, and offers no reference asked for here
    header = _dispatchable(state, pr["id"], derives_from=pr["id"],
                           acceptance_refs=["AC-1", "AC-nowhere"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    message = str(exc.value)
    assert "exist nowhere: AC-nowhere" in message and "AC-nowhere" not in message.split("known:")[1]
    assert "known: AC-1, AC-11" in message, message
    assert unrelated["id"] not in message, (
        "%s offers AC-55, which nobody asked for -- naming it buries the reason under the backlog"
        % unrelated["id"])
    assert "do not count" not in message, (
        "no amendment offers AC-nowhere, so naming one would dress a typo up as an approval problem")


def test_the_refusal_names_the_excluded_amendment_that_could_explain_it(state):
    """...and the same filter from its other side, so it cannot be satisfied by naming NOBODY.

    Two excluded amendments in one store, one of which offers the reference the task actually
    names. The refusal has to name that one and leave the other out; a filter that always answered
    "none" would pass the neighbouring test and fail here.
    """
    pr, cr = _root_with_amendment(state, approved=False)          # offers AC-11, DRAFT
    unrelated = state.capture("CR", dict(CR_FIELDS, target_pr=pr["id"], title="unrelated draft",
                                         acceptance_criteria=[{"id": "AC-55", "text": "elsewhere"}]))
    header = _dispatchable(state, pr["id"], derives_from=pr["id"], acceptance_refs=["AC-11"])
    with pytest.raises(DispatchError) as exc:
        dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])
    message = str(exc.value)
    assert cr["id"] in message and "DRAFT" in message, message
    assert unrelated["id"] not in message, message


# ---------------- session-break continuation (DEC-0044 / BUG-0042) ----------------
#
# The defect these measure: a running background dispatch survives NO session end. Pilot 3 lost
# three specialists at session breaks, and the state they left behind said they were still running.

SESSION_A = "sess-aaaa-1111"          # the session that asked for the child
SESSION_B = "sess-bbbb-2222"          # the one that starts afterwards


def _dispatched(state, session_id=SESSION_A, started=True):
    """A task carried through the REAL dispatch lifecycle, as `session_id` asked for it.

    Through `validate_dispatch(claim=True)`/`spawn_outcome` rather than by writing a lease, for the
    reason `conftest.drive_task_to` gives: a fixture that hand-wrote the record under test would
    measure the fixture. This is exactly the call gate_dispatch makes on PreToolUse and PostToolUse.
    """
    _pr, task = make_ready_task(state)
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True,
                               prompt_id="prompt-1", session_id=session_id)
    if started:
        dispatch.spawn_outcome(state, task["id"], ok=True, session_id=session_id)
    return task


def test_the_no_progress_status_is_derived_from_the_automatons_edge_set(monkeypatch):
    """`no_progress_status` reads the TSK automaton; ambiguity is refused, never guessed.

    The derivation is re-done here from `AUTOMATA` itself rather than compared against the two
    values the shipped automaton happens to produce -- a test that asserted "LEASED to READY,
    IN_PROGRESS to FAILED" would be the table the function exists not to be. The second half feeds
    an automaton with TWO no-progress edges out of LEASED: the answer must be None, because a sweep
    that guessed there would move a task along an edge nobody chose.
    """
    auto = backlog_types.AUTOMATA["TSK"]
    for status in dispatch.LEASE_BEARING_STATUSES:
        candidates = {dst for src, dst in auto.allowed if src == status}
        candidates -= set(auto.terminals)
        candidates -= set(dispatch.LEASE_BEARING_STATUSES)
        if status in auto.chain and auto.chain.index(status) + 1 < len(auto.chain):
            candidates.discard(auto.chain[auto.chain.index(status) + 1])
        assert len(candidates) == 1, (status, candidates)
        assert dispatch.no_progress_status(status) == candidates.pop()
    ambiguous = backlog_types._Automaton(
        chain=("READY", "LEASED"), terminals=(), terminal_from={},
        extra_edges=(("LEASED", "READY"), ("LEASED", "PAUSED")), extra_states=("PAUSED",))
    monkeypatch.setitem(backlog_types.AUTOMATA, "TSK", ambiguous)
    assert dispatch.no_progress_status("LEASED") is None


def test_a_dispatch_of_another_session_is_swept_and_one_of_this_session_is_not(state):
    """DEC-0044 half (1) and its counter-direction in one measurement.

    Two dispatches, one asked for by SESSION_A and one by SESSION_B; the sweep runs as SESSION_B.
    RED without the sweep: both stay IN_PROGRESS with a lease, which is the pilot state. RED in the
    other direction if the sweep judged anything but the asking session -- a mid-session
    SessionStart (a compaction) would then report this session's own running child as gone.
    """
    theirs = _dispatched(state, SESSION_A)
    ours = _dispatched(state, SESSION_B)
    swept, left = dispatch.sweep_orphaned_dispatches(state, SESSION_B)
    assert [row["task_id"] for row in swept] == [theirs["id"]]
    assert [row["moved_to"] for row in swept] == ["FAILED"]
    assert left == []
    assert state.read_item(theirs["id"])["status"] == "FAILED"
    assert state.read_item(ours["id"])["status"] == "IN_PROGRESS"


def test_a_swept_orphan_keeps_no_lease_and_no_agent_binding(state):
    """What the sweep leaves behind: nothing that still claims to run.

    Named in `sweep_orphaned_dispatches`, whose docstring rests on it -- the transition drops the
    lease (`release_lease_for_status_locked`), so `task_for_agent` can no longer resolve the dead
    child's writes onto the task, and `live_leases` no longer reports it as running.
    """
    task = _dispatched(state, SESSION_A)
    dispatch.bind_agent(state, task["id"], "agent-xyz")
    assert dispatch.task_for_agent(state, "agent-xyz")["id"] == task["id"]
    dispatch.sweep_orphaned_dispatches(state, SESSION_B)
    assert dispatch.task_for_agent(state, "agent-xyz") is None
    assert dispatch.live_leases(state) == []
    assert not dispatch.lease_in_force(state, task["id"])


def test_a_dispatch_whose_lease_the_ttl_already_dropped_is_still_decidable(state):
    """The pilot's worst state: IN_PROGRESS, no lease, nothing reporting it.

    `sweep_expired_leases` drops the lease and leaves IN_PROGRESS standing on purpose (a child may
    outlive its lease), so the LEASE's record of who asked is gone by the time a successor looks.
    RED without the task-side copy `spawn_outcome` writes: the dispatch is undecidable, the sweep
    leaves it, and the task can never be leased again.
    """
    task = _dispatched(state, SESSION_A)
    os.remove(os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml"))
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"
    swept, left = dispatch.sweep_orphaned_dispatches(state, SESSION_B)
    assert [row["task_id"] for row in swept] == [task["id"]] and left == []
    assert state.read_item(task["id"])["status"] == "FAILED"


def test_a_dispatch_with_no_recorded_session_is_reported_and_not_swept(state):
    """Fail-safe direction: what cannot be decided is NAMED, never guessed at.

    A lease claimed without a session id -- state written before this record existed, or a hook
    payload without the key -- must not be swept: every dispatch would look foreign to every
    session, and the sweep would end runs it knows nothing about.
    """
    _pr, task = make_ready_task(state)
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True)
    dispatch.spawn_outcome(state, task["id"], ok=True)
    swept, left = dispatch.sweep_orphaned_dispatches(state, SESSION_B)
    assert swept == []
    assert [row["task_id"] for row in left] == [task["id"]]
    assert "no dispatching session is recorded" in left[0]["why"]
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"


def test_the_expired_lease_sweep_does_not_claim_a_release_it_did_not_make(state):
    """The sweep says what it DID: an IN_PROGRESS task keeps its status, and is not called released.

    Measured before this: `sweep-leases` printed "released to READY: TSK-0001" for a task that
    stayed IN_PROGRESS, because the id was collected whatever `_release_lease_locked` had done. The
    two lists are what makes the sentence true; the second one is the state only a session start
    can judge.
    """
    leased = _dispatched(state, SESSION_A, started=False)
    running = _dispatched(state, SESSION_A)
    for task_id in (leased["id"], running["id"]):
        path = os.path.join(state.root, "tasks", "leases", task_id + ".lease.yaml")
        lease = state._read_yaml(path)
        lease["created_epoch"] = 0.0
        state._write_yaml_atomic(path, lease)
    to_ready, lease_only = dispatch.sweep_expired_leases(state)
    assert to_ready == [leased["id"]] and lease_only == [running["id"]]
    assert state.read_item(leased["id"])["status"] == "READY"
    assert state.read_item(running["id"])["status"] == "IN_PROGRESS"


def _checkpoint(state, tmp_path, task, artifact="src/x.py", body=None):
    """Record a checkpoint the way a specialist does -- through the kernel, over a real file."""
    path = tmp_path / artifact
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("work in progress\n", encoding="utf-8")
    return checkpoints.record(state, task["id"], body or {
        "next_step": "finish the error path",
        "outputs": [{"output_index": 0, "progress": "partial", "artifacts": [artifact],
                     "note": "happy path done"}]})


def test_a_verified_checkpoint_says_what_was_measured_and_no_more(state, tmp_path):
    """The adoptable case, and the scope of what "verified" is allowed to mean.

    A verdict that read as "this work is good" would be the claim DEC-0044 warns about wearing a
    green light, so the summary has to name what was NOT measured as well.
    """
    task = _dispatched(state, SESSION_A)
    _checkpoint(state, tmp_path, task)
    verdict = checkpoints.verify(state, task["id"])
    assert verdict.adoptable and verdict.pointer == "staging/%s/checkpoint.yaml" % task["id"]
    assert "expected_outputs are unchanged" in verdict.summary
    assert "NOT measured" in verdict.summary and "whether the work is correct" in verdict.summary


def test_a_checkpoint_is_verified_against_the_tasks_expected_outputs_not_just_its_files(
        state, tmp_path):
    """DEC-0044's named risk: a record that passes file integrity while measuring another contract.

    The task file is rewritten OUTSIDE the kernel, because that is the only route this term can be
    reached by -- `backlog_types.TSK_PLAN_FIELDS` freezes `expected_outputs` for every status past
    DRAFT, so `update_item` refuses the same change (asserted below, or this test would be
    measuring a path production does not have). Nothing about the artefact changes; a verification
    that only hashed files would call this adoptable.
    """
    task = _dispatched(state, SESSION_A)
    _checkpoint(state, tmp_path, task)
    with pytest.raises(Exception):
        state.update_item(task["id"], {"expected_outputs": ["src/somewhere_else.py"]})
    stored = state.read_item(task["id"])
    stored["expected_outputs"] = ["src/somewhere_else.py"]
    state._write_yaml_atomic(state.active_path(task["id"]), stored)
    verdict = checkpoints.verify(state, task["id"])
    assert not verdict.adoptable
    assert any("expected_outputs have changed" in reason for reason in verdict.reasons)
    assert "TREATED AS ABSENT" in verdict.summary


def test_a_checkpoint_whose_artefact_moved_is_treated_as_absent(state, tmp_path):
    """The other half: the contract holds, the tree does not.

    Both directions in one test, because "changed" and "gone" are one answer -- what the record
    measured is not what is there now, so there is nothing to resume from.
    """
    task = _dispatched(state, SESSION_A)
    _checkpoint(state, tmp_path, task)
    (tmp_path / "src" / "x.py").write_text("somebody else's work\n", encoding="utf-8")
    verdict = checkpoints.verify(state, task["id"])
    assert not verdict.adoptable and "src/x.py changed" in " ".join(verdict.reasons)
    os.remove(str(tmp_path / "src" / "x.py"))
    assert "src/x.py is gone" in " ".join(checkpoints.verify(state, task["id"]).reasons)


def test_a_checkpoint_claiming_progress_with_no_artefact_is_refused(state, tmp_path):
    """A claim nothing backs cannot be verified later, so it is refused when it is made."""
    task = _dispatched(state, SESSION_A)
    with pytest.raises(checkpoints.CheckpointError) as exc:
        checkpoints.record(state, task["id"], {"next_step": "x", "outputs": [
            {"output_index": 0, "progress": "partial", "artifacts": [], "note": "trust me"}]})
    assert "names no artefact" in str(exc.value)


def test_a_checkpoint_progress_word_outside_the_vocabulary_is_refused(state, tmp_path):
    """`PROGRESS_STATES` is enforced by the kernel, not merely described in the schema.

    The schema validator checks that an entry HAS its keys, not what the values say
    (`schemas._check_field`, list branch), so without the check in `_measured_outputs` a made-up
    word would travel to the successor as if the harness understood it.
    """
    task = _dispatched(state, SESSION_A)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "x.py").write_text("x\n", encoding="utf-8")
    with pytest.raises(checkpoints.CheckpointError) as exc:
        checkpoints.record(state, task["id"], {"next_step": "x", "outputs": [
            {"output_index": 0, "progress": "nearly", "artifacts": ["src/x.py"]}]})
    assert "progress 'nearly'" in str(exc.value)


def test_a_checkpoint_points_inside_the_tasks_own_contract(state, tmp_path):
    """An entry that addresses an expected output the task does not have is refused."""
    task = _dispatched(state, SESSION_A)
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "x.py").write_text("x\n", encoding="utf-8")
    with pytest.raises(checkpoints.CheckpointError) as exc:
        checkpoints.record(state, task["id"], {"next_step": "x", "outputs": [
            {"output_index": 7, "progress": "partial", "artifacts": ["src/x.py"]}]})
    assert "output_index 7" in str(exc.value)


def test_the_digests_a_checkpoint_is_verified_by_are_the_kernels_and_not_the_callers(
        state, tmp_path):
    """A record whose integrity data the checked party supplied would verify itself."""
    task = _dispatched(state, SESSION_A)
    with pytest.raises(checkpoints.CheckpointError) as exc:
        checkpoints.record(state, task["id"], {
            "next_step": "x", "expected_outputs_digest": "0" * 64,
            "outputs": [{"output_index": 0, "progress": "partial", "artifacts": ["src/x.py"]}]})
    assert "measured by the kernel" in str(exc.value)


def test_a_checkpoint_records_a_dispatch_in_flight_or_nothing(state, tmp_path):
    """Outside a lease-bearing status there is no run for a checkpoint to describe."""
    _pr, task = make_ready_task(state)
    with pytest.raises(checkpoints.CheckpointError) as exc:
        checkpoints.record(state, task["id"], {"next_step": "x", "outputs": [
            {"output_index": 0, "progress": "partial", "artifacts": ["src/x.py"]}]})
    assert "IN FLIGHT" in str(exc.value)


def test_the_retry_envelope_carries_the_checkpoint_only_when_it_verifies(state, tmp_path):
    """Adoption is OFFERED by the dispatch envelope, and only on a verification that passed.

    The whole loop: dispatch, checkpoint, session break, sweep, retry. The header the successor
    receives names the checkpoint when it verifies -- and carries no such key at all when the tree
    has moved under it, which is what "treated as absent" has to look like from the outside.
    """
    task = _dispatched(state, SESSION_A)
    _checkpoint(state, tmp_path, task)
    dispatch.sweep_orphaned_dispatches(state, SESSION_B)
    assert state.read_item(task["id"])["status"] == "FAILED"
    state.transition(task["id"], "READY", approved_retry=True)
    header = dispatch.dispatch_header(dispatch.create_lease(state, task["id"]))
    assert '"checkpoint": "staging/%s/checkpoint.yaml"' % task["id"] in header
    assert dispatch.parse_header(header)["task_id"] == task["id"]

    state.transition(task["id"], "READY")                 # drop the lease, retry once more
    (tmp_path / "src" / "x.py").write_text("moved on\n", encoding="utf-8")
    assert "checkpoint" not in dispatch.dispatch_header(dispatch.create_lease(state, task["id"]))


# ---------------- the five findings of the TSK-0065 verification round ----------------


def test_a_fresh_lease_of_this_session_is_not_judged_by_the_previous_runs_record(state):
    """The retry this session just minted must survive its own next SessionStart (a compaction).

    THE CHAIN, measured in-session before the fix: `spawn_outcome` writes the asking session on the
    TASK and nothing ever clears it, while `create_lease` mints a lease WITHOUT one (it is recorded
    at the CLAIM, one tool call later). A reader that fell back to the task inside that window
    judged the FRESH dispatch by the DEAD run's session -- so a compaction with the very same id
    swept it: LEASED -> READY, lease gone, and the nonce in the prompt being composed dead.
    `dispatching_session_locked` is where the reading order lives.
    """
    task = _dispatched(state, SESSION_A)
    dispatch.sweep_orphaned_dispatches(state, SESSION_B)          # the break: -> FAILED
    assert state.read_item(task["id"])[dispatch.DISPATCHING_SESSION] == SESSION_A
    state.transition(task["id"], "READY", approved_retry=True)
    dispatch.create_lease(state, task["id"])                      # the retry, minted by SESSION_B
    swept, left = dispatch.sweep_orphaned_dispatches(state, SESSION_B)
    assert swept == [], "a compaction swept the retry this very session had just created"
    assert [row["task_id"] for row in left] == [task["id"]]
    assert state.read_item(task["id"])["status"] == "LEASED"
    assert dispatch.lease_in_force(state, task["id"])


def test_while_a_lease_exists_it_is_what_says_which_session_asked(state):
    """The LEASE half of the record, measured on its own -- the task carries nothing here.

    A claim without a spawn outcome: the lease records the asking session, the task does not, and
    the sweep still has to reach a verdict. RED when `_open_bind_window` stops recording -- nothing
    anywhere names the asker, the dispatch becomes undecidable and the sweep leaves a LEASED task
    that no child of any live session is behind. The companion for the task half is
    `test_a_dispatch_whose_lease_the_ttl_already_dropped_is_still_decidable`.
    """
    task = _dispatched(state, SESSION_A, started=False)
    assert dispatch.DISPATCHING_SESSION not in state.read_item(task["id"])
    assert dispatch.dispatching_session_locked(state, task["id"]) == SESSION_A
    swept, left = dispatch.sweep_orphaned_dispatches(state, SESSION_B)
    assert [row["task_id"] for row in swept] == [task["id"]] and left == []
    assert state.read_item(task["id"])["status"] == "READY"        # LEASED has no work behind it


@pytest.mark.parametrize("outside", ["../outside-secret.txt", "../../Windows/win.ini",
                                     "C:\\Windows\\win.ini", "/Windows/win.ini"])
def test_a_checkpoint_artefact_outside_the_project_is_refused_and_never_verified(
        state, tmp_path, outside):
    """An artefact path that leaves the project is refused when written AND when read back.

    Measured rc 0 for all four spellings before this, with the record then VERIFYING cleanly -- so a
    checkpoint could point the successor, whom the constitution tells to read and judge it, at a
    file outside the project. Both sides are tested because the write path is a route and not a
    wall: staging is the one directory a dispatched specialist may write with its own tools, so the
    record can arrive without ever passing `record`.
    """
    task = _dispatched(state, SESSION_A)
    (tmp_path.parent / "outside-secret.txt").write_text("not yours\n", encoding="utf-8")
    with pytest.raises(checkpoints.CheckpointError) as exc:
        checkpoints.record(state, task["id"], {"next_step": "x", "outputs": [
            {"output_index": 0, "progress": "partial", "artifacts": [outside]}]})
    assert "cannot measure under the project root" in str(exc.value)

    _checkpoint(state, tmp_path, task)                 # a legitimate record...
    path = checkpoints.checkpoint_path(state, task["id"])
    stored = state._read_yaml(path)
    stored["outputs"][0]["artifacts"][0]["path"] = outside      # ...aimed out of the tree by hand
    state._write_yaml_atomic(path, stored)
    verdict = checkpoints.verify(state, task["id"])
    assert not verdict.adoptable
    assert "is not inside the project" in " ".join(verdict.reasons)


def test_the_drive_clause_of_a_stored_path_is_one_reader_for_every_host(monkeypatch, tmp_path):
    r"""A word that names a drive is refused wherever the record is READ, not only on Windows.

    The state tree TRAVELS: a filing position and a checkpoint artefact are written on one host and
    read back on another, and all three refusals asked `os.path.splitdrive`, i.e. the reader's own
    path flavour. Measured 2026-08-28 on the hosted ubuntu runner: `C:/Windows/win.ini` was a
    project position and `C:\Windows\win.ini` a contained artefact, while all three docstrings
    promised a drive letter could not pass (BUG-0069). A minted approval for a position the gate
    can never produce is finding F5's failure mode, one host further on.

    TWO HALVES, and the second is the one that makes this red on a WINDOWS host too -- there the
    defective reading gives the same answer as the fixed one, so the answer alone proves nothing:

      * THE ANSWER -- `state.names_a_drive` knows a drive spec on any host;
      * THE ROUTING -- each of the three asks that reader instead of the host. Measured by
        replacing the name each module imported and watching the word arrive there.
    """
    assert names_a_drive("C:/Windows/win.ini") and names_a_drive("C:x")
    assert names_a_drive("//server/share/x")
    assert not names_a_drive("archive/1-Finanzen/x.pdf") and not names_a_drive("")

    asked = []

    def spy(text):
        asked.append(str(text))
        return names_a_drive(text)

    for module in (approvals, checkpoints, staging):
        monkeypatch.setattr(module, "names_a_drive", spy)
    assert not approvals.is_project_position("C:/elsewhere")
    assert checkpoints.contained_artifact(str(tmp_path), "C:\\Windows\\win.ini") is None
    with pytest.raises(staging.StagingError):
        staging.contained_child(str(tmp_path), "C:x", "staging key")
    assert len([word for word in asked if word.startswith("C:")]) == 3, (
        "one of the three refusals decided a drive spec without the shared reader, so it answers "
        "whatever the host it runs on happens to think: %s" % asked)


def test_a_handwritten_checkpoint_that_measures_nothing_is_absent(state, tmp_path):
    """`outputs: []` verified rc 0 before this, with the artefact clause silently dropping out.

    The write path refuses it; `verify` is the step DEC-0044 gates adoption on, and it has to refuse
    it too, because a record that reaches the successor without passing `record` is exactly the case
    the staging directory makes possible.
    """
    task = _dispatched(state, SESSION_A)
    _checkpoint(state, tmp_path, task)
    path = checkpoints.checkpoint_path(state, task["id"])
    stored = state._read_yaml(path)
    stored["outputs"] = []
    state._write_yaml_atomic(path, stored)
    verdict = checkpoints.verify(state, task["id"])
    assert not verdict.adoptable
    assert "names no artefact at all" in " ".join(verdict.reasons)
    assert "TREATED AS ABSENT" in verdict.summary


# -- the dispatch nobody is working on any more (BUG-0058, pilot 4 P4-2) --------

def _with_a_bound_child(state, agent_id="child-1"):
    """A dispatch in the state pilot 4 measured: IN_PROGRESS, live lease, a child bound to it."""
    task = _dispatched(state, SESSION_A)
    dispatch.bind_agent(state, task["id"], agent_id)
    return task


def _another_dispatch(state, agent_id=None, prompt_id="prompt-2"):
    """A SECOND dispatch of the same role under the same root, through the real lifecycle.

    `agent_id=None` leaves it UNBOUND -- the shape whose child no record can identify, which is a
    different thing from a dispatch nobody has spawned against yet.
    """
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement="PR-0001",
                                            allowed_scope=a_scope_of_its_own(state)))
    state.transition(task["id"], "READY")
    lease = dispatch.create_lease(state, task["id"])
    header = dispatch.parse_header(dispatch.dispatch_header(lease))
    dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"], claim=True,
                               prompt_id=prompt_id, session_id=SESSION_A)
    dispatch.spawn_outcome(state, task["id"], ok=True, session_id=SESSION_A)
    if agent_id:
        dispatch.bind_agent(state, task["id"], agent_id)
    return task


def test_a_dispatch_whose_child_ended_is_named_and_a_running_one_is_not(state):
    """The pilot's central finding, both directions (BUG-0058 AC-1).

    RED without the fix: nothing in the kernel distinguishes "IN_PROGRESS with a child on it" from
    "IN_PROGRESS with a child that stopped and handed nothing back", so the lead's only source is
    the status -- which read IN_PROGRESS through all nine waiting turns.

    The counter-direction is the half that makes the finding worth anything: while the child is
    running there is no finding at all, so this cannot be satisfied by naming every dispatch.
    """
    task = _with_a_bound_child(state)
    assert dispatch.idle_dispatches(state) == []

    assert dispatch.record_child_end(state, agent_id="child-1") == task["id"]
    findings = dispatch.idle_dispatches(state)
    assert [row["task_id"] for row in findings] == [task["id"]]
    assert "no result was booked" in " ".join(findings[0]["reasons"])
    assert findings[0]["status"] == "IN_PROGRESS"
    # REPORTED, never moved: what to do about it is the lead's judgement, and the record names the
    # edge the task's own automaton offers instead of taking it
    assert state.read_item(task["id"])["status"] == "IN_PROGRESS"
    assert findings[0]["no_progress_status"] == dispatch.no_progress_status("IN_PROGRESS")


def test_a_child_that_hands_its_result_back_leaves_no_finding(state):
    """The other way a dispatch stops being idle, and the one that must not be reported: a child
    that ended AND booked its result has moved the task out of every lease-bearing status, so the
    term this rests on is the STATUS and not the recorded end."""
    task = _with_a_bound_child(state)
    dispatch.record_child_end(state, agent_id="child-1")
    dispatch.submit_result(state, {"task_id": task["id"], "role": TSK_FIELDS["assigned_role"],
                                   "status_proposal": "SUBMITTED", "summary": "done",
                                   "outputs": ["src/x.py"], "evidence": [],
                                   "scope_touched": ["src/x.py"], "followups": []})
    assert dispatch.idle_dispatches(state) == []


def _age_the_lease(state, task_id, seconds=None):
    """Push a lease's start back so its TTL has passed -- the only thing a test can do about a
    clock. Returns the lease as it now stands on disk."""
    path = os.path.join(state.root, "tasks", "leases", task_id + ".lease.yaml")
    lease = state._read_yaml(path)
    lease["created_epoch"] = time.time() - float(
        seconds if seconds is not None else lease["ttl"] + 1)
    state._write_yaml_atomic(path, lease)
    return lease


def test_a_bound_child_that_outlived_its_lease_is_not_reported_as_idle(state):
    """THE FALSE POSITIVE THAT WAS MEASURED HERE AND ITS CHAIN RAN TO WORK LOSS.

    A running child may legitimately hold IN_PROGRESS past its lease's expiry -- the lifecycle says
    so at `dispatch.LEASE_MINTED_STATUS` -- so "no lease in force" is not a statement about whether
    anybody is working. Reported as idle, the remedy that travels with the finding takes the task
    to FAILED, which drops the lease: `task_for_agent` then resolves nothing, gate layer 3 refuses
    the child's writes and `submit_result` refuses its envelope. The child works on and its result
    can no longer be booked.

    Both halves are asserted, because the second is what the first is FOR: no finding, and the
    dispatch is still intact enough to hand its result back.
    """
    task = _with_a_bound_child(state)
    _age_the_lease(state, task["id"])
    assert not dispatch.lease_in_force(state, task["id"])
    assert dispatch.idle_dispatches(state) == []
    assert dispatch.task_for_agent(state, "child-1")["id"] == task["id"]
    dispatch.submit_result(state, {"task_id": task["id"], "role": TSK_FIELDS["assigned_role"],
                                   "status_proposal": "SUBMITTED", "summary": "late but done",
                                   "outputs": ["src/x.py"], "evidence": [],
                                   "scope_touched": ["src/x.py"], "followups": []})
    assert state.read_item(task["id"])["status"] == "SUBMITTED"


def test_a_window_that_ran_out_with_no_child_bound_is_named_without_any_stop_event(state):
    """The second term, and every one of its three conditions is load-bearing.

    It is a POSITIVE record and not the absence of one: the lease is still there, it names no
    `agent_id`, and its window has passed -- so nothing was ever bound to this dispatch and nothing
    here was ever tracking a run on it. That is decidable without any event, which is what makes it
    the one case a missing `SubagentStop` cannot hide.

    The counter-direction is the missing lease: once the TTL sweep has taken it away, whether a
    child was ever bound is no longer answerable, and a term that produces a refusal has to read
    that as "we cannot say".
    """
    task = _dispatched(state, SESSION_A)
    assert dispatch.idle_dispatches(state) == []
    _age_the_lease(state, task["id"])
    findings = dispatch.idle_dispatches(state)
    assert [row["task_id"] for row in findings] == [task["id"]]
    assert "no child was ever bound to it" in " ".join(findings[0]["reasons"])

    os.remove(os.path.join(state.root, "tasks", "leases", task["id"] + ".lease.yaml"))
    assert dispatch.idle_dispatches(state) == []


def test_an_idle_finding_is_reported_once_and_again_only_when_it_changes(state):
    """The bound that keeps a refusal from repeating itself every turn -- and its counter-half.

    The caller refuses the END OF A TURN, which the assistant answers by continuing, so a finding
    that stayed unreported after being said would refuse the next stop of the same continuation.
    Comparing the REASONS is what makes "again" mean "something happened since" rather than
    "another turn went by".

    The reachable change: a dispatch reported for never having had a child gets one bound late
    (`bind_agent` runs at PostToolUse and asks nothing about the clock), and that child then stops.
    """
    task = _dispatched(state, SESSION_A)
    _age_the_lease(state, task["id"])
    finding = dispatch.idle_dispatches(state)[0]
    assert dispatch.mark_idle_reported(state, finding) is True
    assert dispatch.mark_idle_reported(state, dispatch.idle_dispatches(state)[0]) is False

    dispatch.bind_agent(state, task["id"], "child-late")
    assert dispatch.idle_dispatches(state) == []            # a child on it is not a finding
    assert dispatch.record_child_end(state, agent_id="child-late") == task["id"]
    changed = dispatch.idle_dispatches(state)[0]
    assert changed["why"] != finding["why"]
    assert dispatch.mark_idle_reported(state, changed) is True


def test_a_new_lease_clears_what_the_previous_runs_child_left_behind(state):
    """A retry must not be reported as idle before its own child has even been asked for.

    RED without the clear in `create_lease`: the FAILED -> READY -> LEASED path leaves
    `child_ended` standing from the run that failed, so the next turn-end names the fresh dispatch
    -- and `mark_idle_reported` finds its own previous answer, so the real finding later would be
    swallowed as "already said".
    """
    task = _with_a_bound_child(state)
    dispatch.record_child_end(state, agent_id="child-1")
    dispatch.mark_idle_reported(state, dispatch.idle_dispatches(state)[0])
    state.transition(task["id"], "FAILED")
    state.transition(task["id"], "READY", approved_retry=True)
    dispatch.create_lease(state, task["id"])
    stored = state.read_item(task["id"])
    assert dispatch.CHILD_ENDED not in stored and dispatch.IDLE_REPORTED not in stored
    assert dispatch.idle_dispatches(state) == []


def test_a_child_stop_the_kernel_cannot_attribute_is_refused_rather_than_guessed(state):
    """The platform limit at the OTHER end of `bind_agent_by_role`'s: a stop that carries no
    agent_id can only be matched by ROLE, and two dispatches of one role are two candidates.

    Recording the end against the wrong one would report a specialist that is still working as
    idle and refuse the lead's turn over it. Zero candidates is not an error either way -- every
    subagent stop reaches this, including those of helpers the harness never dispatched.
    """
    first = _with_a_bound_child(state, "child-1")
    second_task = _another_dispatch(state, "child-2")

    with pytest.raises(dispatch.AmbiguousBinding) as refusal:
        dispatch.record_child_end(state, agent_type=TSK_FIELDS["assigned_role"])
    assert first["id"] in str(refusal.value) and second_task["id"] in str(refusal.value)
    assert dispatch.idle_dispatches(state) == []
    assert dispatch.record_child_end(state, agent_id="a-child-of-nobody") is None
    # the id, however, is unambiguous even while both run
    assert dispatch.record_child_end(state, agent_id="child-2") == second_task["id"]
    assert [row["task_id"] for row in dispatch.idle_dispatches(state)] == [second_task["id"]]


def test_the_ambiguous_stop_refusal_names_the_way_out_of_a_zombie_dispatch(state):
    """BUG-0144: a dispatch nobody can finish kept id-less attribution off for its whole role.

    The refusal is right -- guessing writes the end of a running specialist onto the wrong task --
    but the remedy it carried ("dispatch same-role tasks sequentially") is advice for a project
    that has not yet gone wrong, and says nothing to one that already has. There IS a way out and
    it is the mechanism, not a text: a lease is released with the task's STATUS, so moving the dead
    task takes it out of the candidate set and the next stop of that role lands again.

    This test measures that route rather than the sentence: the ambiguity is produced, then the
    corpse is transitioned, then the same stop is recorded and attributed. The sentence is asserted
    only for the two facts a reader needs to walk it -- the candidates' ids and what each lease
    knows about its child -- because a remedy naming neither cannot be followed.
    """
    running = _with_a_bound_child(state, "child-1")
    zombie = _another_dispatch(state, agent_id=None)

    with pytest.raises(dispatch.AmbiguousBinding) as refusal:
        dispatch.record_child_end(state, agent_type=TSK_FIELDS["assigned_role"])
    message = str(refusal.value)
    assert zombie["id"] in message and running["id"] in message, message
    assert "no child bound" in message and "child-1" in message, message
    assert "TASK moves" in message, message

    state.transition(zombie["id"], "FAILED")
    assert dispatch.record_child_end(state, agent_type=TSK_FIELDS["assigned_role"]) == running["id"]
    assert dispatch.CHILD_ENDED in state.read_item(running["id"])


def test_a_stop_with_no_id_is_refused_while_an_unbound_dispatch_of_the_role_could_own_it(state):
    """The misattribution that WAS measured: an unbound child's stop landed on a running dispatch.

    A dispatch whose child the kernel never bound is exactly the one no record can identify, so a
    role-matched stop looks the same whether it came from that child or from the bound one beside
    it. Counting only the bound dispatch left one candidate and the guess was made -- and the
    dispatch it was written onto was still working, which is the false idle report this whole
    mechanism must not produce.

    The counter-direction is in the same measurement: with the unbound dispatch gone from the
    picture (its task off the lease-bearing statuses), the guess is single-owner again and lands.
    """
    running = _with_a_bound_child(state, "child-1")
    unbound = _another_dispatch(state, agent_id=None)

    with pytest.raises(dispatch.AmbiguousBinding) as refusal:
        dispatch.record_child_end(state, agent_type=TSK_FIELDS["assigned_role"])
    assert unbound["id"] in str(refusal.value) and running["id"] in str(refusal.value)
    assert dispatch.CHILD_ENDED not in state.read_item(running["id"])
    assert dispatch.idle_dispatches(state) == []

    state.transition(unbound["id"], "FAILED")
    assert dispatch.record_child_end(state, agent_type=TSK_FIELDS["assigned_role"]) == running["id"]


def test_a_dispatch_whose_end_is_recorded_stops_competing_for_the_next_stop(state):
    """The corpse must not switch the mechanism off for its role.

    A dispatch whose child's end is already recorded cannot be the owner of a NEW stop, and without
    that term it stays a possible owner for as long as the task stands -- so every later
    role-matched stop of that role is refused as ambiguous and nothing is ever recorded again. The
    task is still IN_PROGRESS here (nobody has acted on the finding yet), which is precisely the
    state the lead is in while it reads the refusal.
    """
    first = _with_a_bound_child(state, "child-1")
    dispatch.record_child_end(state, agent_id="child-1")
    assert state.read_item(first["id"])["status"] == "IN_PROGRESS"
    second = _another_dispatch(state, "child-2")

    assert dispatch.record_child_end(state, agent_type=TSK_FIELDS["assigned_role"]) == second["id"]
    assert [row["task_id"] for row in dispatch.idle_dispatches(state)] == sorted(
        [first["id"], second["id"]])


def test_a_long_running_dispatch_still_counts_as_a_possible_owner_of_a_role_matched_stop(state):
    """WHY THE POSSIBLE OWNERS ARE NOT NARROWED BY THE CLOCK, measured against the shape that was
    proposed to fix the corpse above.

    A child may outlive its lease (`dispatch.LEASE_MINTED_STATUS`), so an expired lease says
    nothing about whether its child is the one that just stopped. Drop the expired dispatch from
    the count and this stop -- which may well be that long-running child's -- lands on the FRESH
    dispatch of the same role instead, and reports a specialist that started seconds ago as idle.
    Refusing is the direction that cannot end a live run.
    """
    long_running = _with_a_bound_child(state, "child-old")
    _age_the_lease(state, long_running["id"])
    fresh = _another_dispatch(state, "child-new")

    with pytest.raises(dispatch.AmbiguousBinding) as refusal:
        dispatch.record_child_end(state, agent_type=TSK_FIELDS["assigned_role"])
    assert long_running["id"] in str(refusal.value) and fresh["id"] in str(refusal.value)
    assert dispatch.CHILD_ENDED not in state.read_item(fresh["id"])
    assert dispatch.idle_dispatches(state) == []


def test_the_idle_finding_says_what_the_run_staged(state):
    """The lead cannot answer honestly without knowing whether anything came of the run, and
    staging is the one place a dispatched specialist may write with its own tools (spec II.4). The
    pilot's own observation was this measurement made by hand: no file, empty staging.

    A count and no judgement -- whether what is there carries the work forward is
    `checkpoint-status`'s answer, which is what every message built on this points at.
    """
    task = _with_a_bound_child(state)
    dispatch.record_child_end(state, agent_id="child-1")
    assert "nothing was staged for it" in dispatch.idle_dispatches(state)[0]["staged"]
    staged = staging.staging_dir(state, task["id"])
    os.makedirs(staged, exist_ok=True)
    with open(os.path.join(staged, "notes.md"), "w", encoding="utf-8") as handle:
        handle.write("half a thought\n")
    said = dispatch.idle_dispatches(state)[0]["staged"]
    assert "1 entry" in said and "staging/%s" % task["id"] in said


# -- the plan-level approval (FR-0074) and the provenance of a mint (FR-0083) ---

def _two_goals(state):
    """Two product goals in the status where their scope question is still open."""
    return (state.capture("PR", dict(PR_FIELDS)),
            state.capture("PR", dict(PR_FIELDS, title="Search", goal="find products")))


def _approve_the_plan(state):
    request = approvals.create_pending_request(
        state, approvals.PLAN_KIND,
        manifest=approvals.plan_subject_manifest(approvals.plan_goals(state)))
    mint_via_hook(state, request)
    return request


def test_one_plan_approval_walks_every_goal_and_the_delivery_side_still_asks(state):
    """FR-0074: one answer covers the scope question of the whole confirmed list -- and only that.

    RED WITHOUT THE FIX: with the plan fallback removed from `assert_transition_approved`, the
    first `transition ... APPROVED` refuses ("none is in force"), which is exactly the per-goal
    question the FR is about.

    THE SECOND HALF IS THE COUNTERWEIGHT and is asserted in the same test on purpose: the wider
    approval is only defensible while the DELIVERY side stays per goal, so a change that let the
    plan cover `delivery` too turns this red rather than passing quietly.
    """
    first, second = _two_goals(state)
    _approve_the_plan(state)

    for goal in (first, second):
        walked = state.transition(goal["id"], "APPROVED")
        assert walked["status"] == "APPROVED"
        # the goal PRESENTS the plan approval, which is what the dispatch route reads
        assert walked["approval_ref"] == approvals.live_plan_approval(state, walked)["id"]

    with pytest.raises(ApprovalError) as refusal:
        state.transition(first["id"], "IN_DELIVERY")
    assert "delivery approval commits" in str(refusal.value)


def test_a_plan_can_only_stand_in_for_the_question_a_plan_answers():
    """FR-0074, both ends of `PLAN_COVERED_KIND` -- the constant is neither dead nor too narrow.

    END ONE: the kind it names is a real approval kind that commits an edge, so the stand-in is
    not a word pointing at nothing.

    END TWO, and this is the half a list would never notice: every OTHER item-derived kind must
    name at least one manifest field a PLAN cannot carry -- a field that only exists once work has
    happened. The moment one of them became derivable from planning content alone, the property
    "a plan settles only the scope question" would have stopped being true, and this goes red
    instead of the comment quietly rotting.
    """
    pairs = {kind for (_typ, kind) in approvals.APPROVAL_TRANSITIONS}
    assert approvals.PLAN_COVERED_KIND in pairs

    plan_content = set(approvals._SCOPE_FIELDS) | {"item", "revision"}
    item = dict(PR_FIELDS, id="PR-0001", revision=1)
    for kind in approvals.item_derived_kinds():
        manifest = set(approvals.item_subject_manifest(item, kind))
        if kind == approvals.PLAN_COVERED_KIND:
            assert manifest <= plan_content, kind
        else:
            assert manifest - plan_content, (
                "%s is now derivable from planning content alone, so PLAN_COVERED_KIND is too "
                "narrow -- or its comment is wrong" % kind)


def test_the_plan_covers_every_open_goal_and_only_those(state):
    """FR-0074: the goal list is DERIVED from the store, and a settled goal is not in it.

    RED WITHOUT THE FIX in the second direction: a `plan_goals` that collected every active root
    would put the already-approved goal back into the hash, so an edit of finished work would kill
    the approval covering the unfinished goals.
    """
    first, second = _two_goals(state)
    assert [goal["item"] for goal in approvals.plan_goals(state)] == [first["id"], second["id"]]

    approve_scope(state, first["id"])          # this goal's scope question is answered
    remaining = approvals.plan_goals(state)
    assert [goal["item"] for goal in remaining] == [second["id"]]
    # a task is not a product goal, whatever else it is
    assert all(goal["item"].startswith("PR-") for goal in remaining)


def test_a_plan_stops_covering_a_goal_the_moment_its_scope_moves(state):
    """FR-0074: the plan binds to each goal's OWN scope hash, so a changed goal comes back as a
    question while the untouched ones stay covered.

    RED WITHOUT THE FIX: with the hash comparison dropped from `_assert_the_list_covers`, the
    edited goal walks to APPROVED again on an approval whose subject it no longer matches.
    """
    first, second = _two_goals(state)
    _approve_the_plan(state)
    state.transition(first["id"], "APPROVED")
    state.transition(second["id"], "APPROVED")

    state.update_item(second["id"], {"acceptance_criteria": [{"id": "AC-1", "text": "other"}]})
    moved = state.read_item(second["id"])
    assert moved["status"] == "DRAFT" and moved["approval_ref"] is None
    assert approvals.live_plan_approval(state, moved) is None
    with pytest.raises(ApprovalError):
        state.transition(second["id"], "APPROVED")
    assert approvals.live_plan_approval(state, state.read_item(first["id"])) is not None

    # AND THE EDIT THE REVISION DOES NOT CATCH, which is the one the hash exists for: an IDE
    # writing the item file straight past the kernel leaves the revision where it was. Measured:
    # without the hash comparison in `_assert_the_list_covers` the paragraph above still passes
    # (the revision bump alone closes it), so this is the assertion that reaches that line.
    path = state.active_path(first["id"])
    edited = state._read_yaml(path)
    edited["acceptance_criteria"] = [{"id": "AC-1", "text": "something nobody approved"}]
    state._write_yaml_atomic(path, edited)
    assert approvals.live_plan_approval(state, state.read_item(first["id"])) is None


def test_a_plan_approval_over_no_open_goal_is_refused_before_anyone_is_asked(state):
    """FR-0074: a permission bound to an empty list would cover every goal captured afterwards."""
    with pytest.raises(ApprovalError) as refusal:
        approvals.plan_subject_manifest(approvals.plan_goals(state))
    assert "nothing to approve" in str(refusal.value)


def test_every_approval_kind_is_classified_as_takeable_back_or_not():
    """FR-0083/FR-0074: `IRREVERSIBLE_KINDS` is measured from both ends, being a set of names.

    END ONE -- no member of it has fallen out of `APR_KINDS` (a rule about a kind nobody can ask
    for is a rule that decides nothing). END TWO -- no kind of `APR_KINDS` is unclassified, which
    is the end that matters: a NEW kind is `IRREVERSIBLE_KINDS`-absent by default, i.e. mintable
    by a program, and that has to be a decision somebody took rather than one nobody noticed.
    """
    assert approvals.IRREVERSIBLE_KINDS <= set(approvals.APR_KINDS)
    revisable = set(approvals.APR_KINDS) - approvals.IRREVERSIBLE_KINDS
    # `hole_exception` is revisable, judged 2026-09-04 (FR-0087/DEC-0073): accepting a measured gap
    # changes nothing outside this project -- the item is a record of a decision, the approval is
    # revocable like any other, and a fallen exception (DEC-0069 (3)) is a NEW item with its own
    # measurement. So it is a QUESTION and not an irreversible act, which is DEC-0068 (3)'s own
    # reading for the kinds that are themselves a question.
    # `verification` is revisable, judged 2026-09-11 (PR-0012 AC-1): it closes defects of this
    # project's own store -- archived, never deleted -- and a defect closed wrongly is re-filed as a
    # new item with its own measurement. The count it closes at once is bounded by
    # `approvals.BATCH_LIMIT` and each entry needed a passing Evidence before the question existed.
    assert revisable == {"analysis", "scope", "delivery", "acceptance", "routine",
                         approvals.HOLE_EXCEPTION_KIND, approvals.PLAN_KIND,
                         approvals.VERIFICATION_KIND}, (
        "a new approval kind has to be judged: can this project take the act back out of its own "
        "resources? If not it belongs in IRREVERSIBLE_KINDS; if so, add it to this list with the "
        "reason in the round's protocol.")


def test_a_program_cannot_mint_a_permission_the_project_cannot_take_back(state):
    """FR-0083: the SDK route mints what a project can revisit, and nothing else.

    RED WITHOUT THE FIX: with `_assert_the_route_may_decide_this` removed, the push token is minted
    by a program and `gate_push_token` then reads a live token for a publication nobody authorised.
    """
    from kernel import sdk_approval

    goal = state.capture("PR", dict(PR_FIELDS))
    scope = approvals.create_pending_request(state, "scope", goal["id"])
    apr = sdk_approval.mint_from_can_use_tool(
        state, scope["request_id"], approvals.approve_label(scope["mint_code"]))
    assert approvals.minted_via(apr) == approvals.PROGRAMMATIC_MINT

    push = approvals.create_pending_request(
        state, "push", manifest=approvals.push_subject_manifest("origin", "main", "abc123"),
        approval_expires=time.time() + 600)
    with pytest.raises(ApprovalError) as refusal:
        sdk_approval.mint_from_can_use_tool(
            state, push["request_id"], approvals.approve_label(push["mint_code"]))
    assert "cannot take back" in str(refusal.value)
    assert approvals.live_line_approval(
        state, "push", approvals.push_subject_manifest("origin", "main", "abc123")) is None


def test_the_card_names_the_route_that_minted_the_approval(state):
    """FR-0083: the card is read out of the RECORD, so both routes are told apart afterwards.

    RED WITHOUT THE FIX: without the `minted_via` stamp both cards read the same, which is exactly
    the state the wishlist calls the provenance being only a claim.
    """
    from kernel import sdk_approval

    human_goal = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, human_goal["id"])
    human = approvals.read_apr(state, state.read_item(human_goal["id"])["approval_ref"])

    program_goal = state.capture("PR", dict(PR_FIELDS, title="Search", goal="find products"))
    request = approvals.create_pending_request(state, "scope", program_goal["id"])
    program = sdk_approval.mint_from_can_use_tool(
        state, request["request_id"], approvals.approve_label(request["mint_code"]))

    assert "Menschen" in approvals.approval_card(human)
    assert "PROGRAMM" in approvals.approval_card(program)
    assert approvals.approval_card(program) == sdk_approval.card(program)
    assert approvals.presented_approval_a_program_minted(
        state, state.read_item(program_goal["id"]))["id"] == program["id"]
    assert approvals.presented_approval_a_program_minted(
        state, state.read_item(human_goal["id"])) is None


def _functions_that_decide_on(field, package_dir):
    """Every function in the package that DECIDES on `field` -- `{"module.py:name": [line, ...]}`.

    Judged on the parsed tree, never on the file's text, and "decides" is a property rather than a
    spelling: a function decides when it compares something that carries the field's value. That is
    the field read straight into an `ast.Compare`, and equally a local the function assigned FROM
    the field and compares afterwards -- the second form is why this reader carries a taint step at
    all, measured: without it the one-line revert of `board.open_requests` (assign `expires`, then
    `now > expires`) left this test green, which is a test that cannot fail for the defect it names.

    A read that only DISPLAYS the value is not a decision and is not reported -- the board formats
    the stamp for the card -- and neither is the line that writes it.
    """
    found = {}
    for entry in sorted(os.listdir(package_dir)):
        if not entry.endswith(".py"):
            continue
        source = open(os.path.join(package_dir, entry), encoding="utf-8").read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            carriers = {field}
            for _ in range(len(carriers) + 3):     # assignment chains, until nothing new arrives
                grown = set(carriers)
                for assign in ast.walk(node):
                    if not isinstance(assign, ast.Assign):
                        continue
                    value = ast.get_source_segment(source, assign.value) or ""
                    if not any(c in value for c in carriers):
                        continue
                    for target in assign.targets:
                        if isinstance(target, ast.Name):
                            grown.add(target.id)
                if grown == carriers:
                    break
                carriers = grown
            for compare in ast.walk(node):
                if not isinstance(compare, ast.Compare):
                    continue
                segment = ast.get_source_segment(source, compare) or ""
                names = {n.id for n in ast.walk(compare) if isinstance(n, ast.Name)}
                if field in segment or (names & carriers):
                    found.setdefault("%s:%s" % (entry, node.name), []).append(
                        segment.strip().splitlines()[0])
    return found


def test_every_reader_of_the_expiry_rule_asks_this_one(state):
    """`approvals.has_expired` calls itself the one definition of "can never mint again" -- held.

    TWO HALVES, because either alone has been green through a real defect. The FIRST is a property
    of the parsed package: comparing an approval request's `expires_at_epoch` against a clock is
    something exactly one function does. Until TSK-0120 three others did it in their own words --
    `mint`, `report.generate_session_brief` and, since FR-0075, `board.open_requests` -- and the
    docstring's "two readers, and they may not disagree" was prose nothing measured.

    The SECOND is what that costs, run rather than reasoned: on a stamp NOBODY can read, the
    definition is fail-closed (an unreadable clock never mints), while `mint`'s own spelling
    reached `float("soon")` and left the package as a bare `ValueError` -- a caller that catches
    `ApprovalError`, which is every caller the kits ship, does not catch that one. Measured before
    the fix: `ValueError: could not convert string to float: 'soon'` for a string stamp and
    `TypeError` for `null`, where `pending_request` refused both as expired.
    """
    package = os.path.join(TEAM_KITS, "kernel")
    deciders = _functions_that_decide_on("expires_at_epoch", package)
    assert set(deciders) == {"approvals.py:has_expired"}, deciders

    for stamp in ("'soon'", "null", "[]", "''"):
        pending = os.path.join(state.root, "approvals", "pending")
        os.makedirs(pending, exist_ok=True)
        path = os.path.join(pending, "r1.yaml")
        open(path, "w", encoding="utf-8").write(
            "request_id: r1\nkind: merge\nitem: PR-0001\nmint_code: abc123\n"
            "expires_at_epoch: %s\n" % stamp)
        with pytest.raises(ApprovalError):
            approvals.pending_request(state, "r1")
        with pytest.raises(ApprovalError):
            approvals.mint(state, "r1", "whatever")
        assert approvals.open_requests(state) == []
        os.remove(path)


# -- BUG-0091/DEC-0066, FR-0085/DEC-0072, FR-0087/DEC-0073 ---------------------

def test_a_work_order_under_an_inbox_item_is_refused_at_creation(state):
    """BUG-0091: a wish is not a goal, and a task under one is a DEAD END, not a mislabel.

    MEASURED on the kernel before this refusal existed: `create_task` with an `FR` in both parent
    fields returned rc 0 and a DRAFT order; `approvals.create_pending_request(state, "scope", FR)`
    then refused ("this type carries no user approval") because `FR` is in no row of
    `APPROVAL_TRANSITIONS`; and `create_lease` refused the order with "no user approval authorises
    dispatching". A task's fields are frozen outside DRAFT, so nothing repairs it afterwards --
    which is why this is refused at creation, exactly as a cross-root origin is.

    THE REMEDY NAMES THE TRIAGE ROUTE, because a refusal a role cannot act on is half a refusal.
    """
    wish = state.capture("FR", {"title": "a wish", "request_text": "please"})
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])

    for field in ("product_requirement", "derives_from"):
        fields = dict(TSK_FIELDS, product_requirement=pr["id"], derives_from=pr["id"])
        fields[field] = wish["id"]
        with pytest.raises(DispatchError) as refusal:
            dispatch.create_task(state, fields)
        message = str(refusal.value)
        assert field in message and wish["id"] in message, message
        assert "CONVERTED" in message and "resulting_item" in message, (
            "the refusal does not name the triage route: %s" % message)

    # ...and a task under the GOAL is untouched
    assert dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=pr["id"]))["status"] == "DRAFT"


def test_the_architect_step_is_owed_by_the_kits_delivery_not_the_projects_stock(tmp_path,
                                                                                 monkeypatch):
    """DEC-0074 as DEC-0079 corrected it: the KIT's delivery decides, and a live directory does not.

    MEASURED ON SCAFFOLDED PILOTS (TSK-0126, merge round): an office order under its `PROC` root and
    a research order under its `RQ` root were refused with "no SR in status ACCEPTED hangs from that
    goal", and the remedy named `capture SR` and "the architect" -- neither kit's texts carry either
    word. The first cut asked the PROJECT's stock, and the verifier measured what that costs: the
    office kit's own CLI accepts `capture SR` (rc 0) and creates `system/active`, and a bare `mkdir`
    does the same -- from then on the duty was on again in the very kit the decision exempted.

    THREE CASES, one store, no kit name in the assertions: a kit whose template SHIPS the home, one
    that does not, and -- the case the correction exists for -- the second one with the directory
    made by hand inside the project. The kit names come out of the store this test builds, so the
    subject is the property and not today's catalogue.
    """
    home = tmp_path / "home"
    store = home / ".claude" / "team-kits"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    (store / "with-the-step" / "templates" / "project_memory" / ACTIVE_DIRS["SR"]).mkdir(
        parents=True)
    (store / "without-the-step" / "templates" / "project_memory" / "product" / "active").mkdir(
        parents=True)
    # ...and since DEC-0078 a kit that is KNOWN has to declare its ladder, and a role its pin, or
    # the lease is refused for that -- which is not what this test is about. The shipped dev-team
    # declaration and the store's tiers table stand in, byte for byte (`tools/test_ladder.py`
    # measures them on their own).
    for kit in ("with-the-step", "without-the-step"):
        shutil.copy(os.path.join(TEAM_KITS, "dev-team", dispatch.LADDER_FILE),
                    str(store / kit / dispatch.LADDER_FILE))
    shutil.copy(os.path.join(TEAM_KITS, dispatch.TIERS_FILE), str(store / dispatch.TIERS_FILE))

    def project(kit, name):
        repo = tmp_path / name
        (repo / ".claude" / "agents").mkdir(parents=True)
        with io.open(repo / ".claude" / "team_kit_roles.txt", "w", encoding="utf-8",
                     newline="\n") as handle:
            handle.write("# agents-and-skills:team-kit-roles v1 team=%s count=1\nproject-manager\n"
                         % kit)
        with io.open(repo / ".claude" / "agents" / "backend-developer.md", "w", encoding="utf-8",
                     newline="\n") as handle:
            handle.write("---\nname: backend-developer\nmodel: sonnet\neffort: high\n---\nbody\n")
        root = repo / "project_memory"
        root.mkdir()
        state = ProjectState(str(root))
        pr = state.capture("PR", dict(PR_FIELDS, **{"class": "normal"}))
        approve_scope(state, pr["id"])
        task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                                derives_from=pr["id"]))
        state.transition(task["id"], "READY")
        return state, state.read_item(task["id"]), state.read_item(pr["id"])

    shipped, task, root = project("with-the-step", "asked")
    assert dispatch.architect_step_owed(shipped, task, root), (
        "a kit that ships the home is not asked for the step")
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(shipped, task["id"])
    assert "SR" in str(refusal.value) and "ACCEPTED" in str(refusal.value), refusal.value

    spared, task, root = project("without-the-step", "not-asked")
    assert not dispatch.architect_step_owed(spared, task, root), (
        "a kit that ships no home for the step was asked for it anyway")
    assert dispatch.create_lease(spared, task["id"])["task_id"] == task["id"]

    # THE CORRECTION ITSELF: the directory made by hand inside the project changes nothing.
    (pathlib.Path(spared.root) / ACTIVE_DIRS["SR"]).mkdir(parents=True)
    second = dispatch.create_task(spared, dict(TSK_FIELDS, product_requirement=root["id"],
                                               derives_from=root["id"],
                                               allowed_scope=["frontend/"],
                                               expected_outputs=["frontend/x.tsx"]))
    spared.transition(second["id"], "READY")
    assert not dispatch.architect_step_owed(spared, spared.read_item(second["id"]), root), (
        "a directory created inside the project switched the duty back on (R2-B1)")
    # a SECOND builder under one goal is leased only on a check-scopes record (DEC-0092 (2)); the
    # measurement here is the architect step, so the record is made the way a PM makes it
    from kernel import scopes
    assert scopes.check(spared)[0] == 0
    assert dispatch.create_lease(spared, second["id"])["task_id"] == second["id"]


def test_a_project_that_names_no_kit_is_asked_for_the_architect_step(tmp_path, monkeypatch):
    """The fail-closed direction of DEC-0079 (4), and the reason the whole suite still meets the duty.

    A tree with no scaffold record cannot say which kit it runs, and a kit that is not staged on
    this machine cannot say what it ships. Both are "this reader does not know", and the answer is
    to ASK -- a question costs a step, a skip loses one.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "empty-home"))
    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    pr = state.capture("PR", dict(PR_FIELDS, **{"class": "normal"}))
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=pr["id"]))
    state.transition(task["id"], "READY")
    assert dispatch.architect_step_owed(state, state.read_item(task["id"]),
                                        state.read_item(pr["id"])), (
        "a project whose kit this reader cannot name was excused the step")

    # and the second half of the same branch: a record naming a kit nobody staged
    (tmp_path / ".claude").mkdir()
    with io.open(tmp_path / ".claude" / "team_kit_roles.txt", "w", encoding="utf-8",
                 newline="\n") as handle:
        handle.write("# agents-and-skills:team-kit-roles v1 team=no-such-kit count=1\n"
                     "project-manager\n")
    assert dispatch.architect_step_owed(state, state.read_item(task["id"]),
                                        state.read_item(pr["id"])), (
        "a kit that is not staged on this machine was read as one that ships no step")


def test_a_project_whose_kit_delivery_cannot_be_read_says_so(tmp_path, monkeypatch):
    """DEC-0079 (4): the fail-closed branch ASKS, and the refusal says WHY it had to.

    MEASURED BEFORE THIS EXISTED (merge verify round 3, R3-B1): all three unreadable cases -- a
    record naming a kit the store does not hold, no record at all, and a kit store that is not
    under the running HOME -- printed the ORDINARY refusal, which sends the reader to
    `capture SR` and to "the architect". In an office or research project those are two words the
    kit does not have, and ending exactly that dead end is what DEC-0074 and DEC-0079 were decided
    for. The store path is the RUNNING home's (`presets.staging_root`), so a project on a second
    machine, another account or a CI runner meets this branch without doing anything unusual.

    BOTH SENTENCES ARE ASSERTED, because a refusal that says nothing wrong is not yet one that says
    the right thing: the unreadable project gets the reason and no `capture`, and a project whose
    kit delivery IS readable and owes the step still gets the ordinary remedy.
    """
    home = tmp_path / "home"
    store = home / ".claude" / "team-kits"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    (store / "with-the-step" / "templates" / "project_memory" / ACTIVE_DIRS["SR"]).mkdir(
        parents=True)

    def project(name, kit):
        repo = tmp_path / name
        (repo / ".claude").mkdir(parents=True)
        if kit is not None:
            with io.open(repo / ".claude" / "team_kit_roles.txt", "w", encoding="utf-8",
                         newline="\n") as handle:
                handle.write("# agents-and-skills:team-kit-roles v1 team=%s count=1\n"
                             "project-manager\n" % kit)
        root = repo / "project_memory"
        root.mkdir()
        state = ProjectState(str(root))
        pr = state.capture("PR", dict(PR_FIELDS, **{"class": "normal"}))
        approve_scope(state, pr["id"])
        task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                                derives_from=pr["id"]))
        state.transition(task["id"], "READY")
        return state, task

    for name, kit, expected in (("unstaged", "no-such-kit", "is not in the kit store"),
                                ("recordless", None, "no readable scaffold record")):
        state, task = project(name, kit)
        with pytest.raises(DispatchError) as refusal:
            dispatch.create_lease(state, task["id"])
        message = str(refusal.value)
        assert "could not be read" in message and expected in message, message
        assert "scripts/harness.py capture" not in message, (
            "the fail-closed refusal hands over the ordinary remedy -- capturing an item whose "
            "very existence in this kit is what could not be read: %s" % message)
        assert str(store) in message or ".claude" in message, (
            "the refusal does not name the store it could not read: %s" % message)

    readable, task = project("readable", "with-the-step")
    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(readable, task["id"])
    message = str(refusal.value)
    assert "could not be read" not in message, message
    assert "scripts/harness.py capture" in message and "ACCEPTED" in message, (
        "a project whose kit delivery IS readable lost the ordinary remedy: %s" % message)


def test_a_goal_of_an_unknown_class_is_asked_for_the_architect_step(state):
    """FR-0085/DEC-0072: the EXEMPTION is the closed set, and an unknown class is asked.

    MEASURED before this was written: `class` has no vocabulary anywhere in this kernel -- the
    shipped suite alone captures roots with `feature`, `normal`, `research`, `exploratory` and
    `technical_enabler`, and no schema constrains the value. A rule spelled as "class in (normal,
    large)" would therefore SKIP the duty for every value nobody thought of, which is the failure
    an unrecognised value always is: it does not fail a check, it skips one.

    So this asks with a class no map knows, and the refusal has to name the architect step.
    """
    pr = state.capture("PR", dict(PR_FIELDS, **{"class": "a class nobody declared"}))
    approve_scope(state, pr["id"])
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=pr["id"]))
    state.transition(task["id"], "READY")

    with pytest.raises(DispatchError) as refusal:
        dispatch.create_lease(state, task["id"])
    message = str(refusal.value)
    # THE ASK IS THE MEASUREMENT here, not which of the two sentences it wears: this
    # fixture builds a project with no scaffold record, so since DEC-0079 (4) the refusal is
    # the fail-closed one. What an exempt class produces is NO refusal at all, and that is
    # what this node is about; the two sentences are held against each other in
    # `test_a_project_whose_kit_delivery_cannot_be_read_says_so`.
    assert "could not be read" in message or ("SR" in message and "ACCEPTED" in message), (
        message)
    assert state.read_item(task["id"])["status"] == "READY", "the refused order was moved anyway"

    # ...and the step, taken through the kernel, opens it
    satisfy_the_architect_step(state, state.read_item(task["id"]), state.read_item(pr["id"]))
    assert dispatch.create_lease(state, task["id"])["task_id"] == task["id"]


def test_a_small_goal_is_not_asked_and_neither_is_a_bugfix_order(state):
    """The other end of the same rule -- three cases DEC-0072 settled, each for its own reason.

    `small` is FR-0085's own word for the size that pays nothing. `technical_enabler` carries no
    product content at all (the kernel already lets it omit the user story). And an order deriving
    from a BUG carries its criteria there: FR-0085 says in as many words that it does not want an
    SR for every bugfix task.
    """
    for klass in sorted(dispatch.SR_EXEMPT_CLASSES):
        exempt = state.capture("PR", dict(PR_FIELDS, title="goal %s" % klass,
                                          **{"class": klass}))
        approve_scope(state, exempt["id"])
        # a scope of its own per case: two live leases over one path are refused now (C-2), and
        # this test is about the architect step and not about that rule
        task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=exempt["id"],
                                                derives_from=exempt["id"],
                                                allowed_scope=["src/%s/**" % klass]))
        state.transition(task["id"], "READY")
        assert dispatch.create_lease(state, task["id"]), klass

    asked = state.capture("PR", dict(PR_FIELDS, title="an asked goal"))
    approve_scope(state, asked["id"])
    bug = state.capture("BUG", {"title": "a defect", "related_pr": asked["id"], "observed": "o",
                                "expected": "e", "repro": "r", "severity": "low",
                                "acceptance_criteria": [{"id": "AC-1", "text": "t"}]})
    fix = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=asked["id"],
                                           derives_from=bug["id"], type="bugfix",
                                           allowed_scope=["src/the-fix/**"]))
    state.transition(fix["id"], "READY")
    assert not dispatch.architect_step_owed(state, state.read_item(fix["id"]),
                                            state.read_item(asked["id"]))
    assert dispatch.create_lease(state, fix["id"])["task_id"] == fix["id"]


def test_the_hole_exception_edge_needs_a_user_minted_approval(state):
    """FR-0087/DEC-0073: a status the supervised party can set itself is no acceptance.

    An accepted exception is a USER statement about risk, so the edge into `ACCEPTED_EXCEPTION` is
    bound to a mint -- a kind of its own, because a kind binds exactly one edge and `scope` already
    binds BUG's TRIAGED -> APPROVED. One approval given for a fix must not walk an item into an
    exception instead.

    THE MANIFEST CARRIES WHAT IS BEING ACCEPTED, which is why the acceptance dies when the gap's
    description or its limit is edited past the kernel: both are in the hash.
    """
    goal = state.capture("PR", dict(PR_FIELDS))
    hole = state.capture("BUG", {
        "title": "a measured gap", "related_pr": goal["id"], "observed": "the chain runs",
        "expected": "it should not", "repro": "run it", "severity": "medium",
        "acceptance_criteria": [{"id": "AC-1", "text": "closed or accepted"}],
        "limits": "the role says so, no gate"}, hole=True)
    state.transition(hole["id"], "TRIAGED")

    with pytest.raises(Exception):
        state.transition(hole["id"], "ACCEPTED_EXCEPTION")
    assert state.read_item(hole["id"])["status"] == "TRIAGED"

    kinds = approvals.required_approval_kinds("BUG", "TRIAGED", "ACCEPTED_EXCEPTION")
    assert kinds == frozenset({approvals.HOLE_EXCEPTION_KIND}), kinds
    manifest = approvals.item_subject_manifest(state.read_item(hole["id"]),
                                               approvals.HOLE_EXCEPTION_KIND)
    assert manifest["limits"] == "the role says so, no gate"
    assert manifest["hole_number"] == hole["hole_number"]

    mint_via_hook(state, approvals.create_pending_request(
        state, approvals.HOLE_EXCEPTION_KIND, hole["id"]))
    assert state.read_item(hole["id"])["status"] == "ACCEPTED_EXCEPTION"


def test_an_order_deriving_from_a_proposed_requirement_is_still_asked(state):
    """F1 of the round-1 verification: the exemption was "anything but the root", and that is not
    what it means.

    MEASURED before this was bound to a property: the same task, the same goal, the same PROPOSED
    `SR` -- deriving from the goal it was REFUSED, deriving from the requirement it was GRANTED, and
    `derives_from` at 75a00d1 names an `SR` 29 times against the goal 3 times. The dev-team
    developer skills prescribe the `SR` spelling by name, so in a kit project the duty would never
    have fired.

    BOTH ENDS: a PROPOSED requirement excuses nothing, and the ACCEPTED one satisfies the duty
    without a branch of its own -- it simply IS the accepted architect step the scan looks for.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    requirement = state.capture("SR", {
        "title": "the technical contract", "derives_from": pr["id"],
        "contract": "what the goal needs", "affected_components": ["src"]})
    task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=requirement["id"],
                                            allowed_scope=a_scope_of_its_own(state)))
    state.transition(task["id"], "READY")

    with pytest.raises(DispatchError, match="architect step"):
        dispatch.create_lease(state, task["id"])
    # ...and the same order with the goal AND the requirement named is no way round it either
    both = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                            derives_from=[pr["id"], requirement["id"]],
                                            allowed_scope=a_scope_of_its_own(state)))
    state.transition(both["id"], "READY")
    with pytest.raises(DispatchError, match="architect step"):
        dispatch.create_lease(state, both["id"])

    state.transition(requirement["id"], "ACCEPTED")
    assert dispatch.create_lease(state, task["id"])["task_id"] == task["id"]


def test_only_an_origin_that_carries_criteria_excuses_the_architect_step():
    """The property the exemption is bound to, read off the field contracts rather than a name list.

    `validate_dispatch` resolves `acceptance_refs` against the ORIGIN and looks in
    `dispatch.CRITERIA_FIELDS`; a type declaring none of those fields cannot carry a work order's
    criteria, so an order under it is not "measured elsewhere" and the duty stands. BOTH ENDS, so
    neither a type that gained a criteria field nor one that lost it can pass unnoticed.
    """
    from kernel.backlog_types import _contract_fields

    contract = _contract_fields()
    excusing = {item_type for item_type in contract
                if dispatch._carries_its_own_criteria(item_type)}
    assert excusing == {"PR", "RQ", "BUG", "CR", "EXP"}, sorted(excusing)
    assert dispatch.ARCHITECT_STEP_TYPE not in excusing, (
        "the type the duty is ABOUT would excuse itself, which is what F1 measured")
    for item_type in excusing:
        assert any(field in contract[item_type] for field in dispatch.CRITERIA_FIELDS), item_type


def test_the_remedy_for_an_already_triaged_wish_names_what_it_became(state):
    """A remedy that cannot be executed is half a refusal (the class BUG-0089 records).

    An `FR` that already reached `CONVERTED` has no outgoing edge left, so telling its author to
    `transition` it is an instruction the automaton refuses. Measured in the round-1 verification:
    the same text was printed either way. Now the wish's own `resulting_item` answers.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    wish = state.capture("FR", {"title": "a wish", "request_text": "please"})
    state.transition(wish["id"], "TRIAGED")
    state.update_item(wish["id"], {"triage_result": "converted", "resulting_item": pr["id"]})
    state.transition(wish["id"], "CONVERTED")

    with pytest.raises(DispatchError) as refused:
        dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=wish["id"],
                                         derives_from=wish["id"]))
    message = str(refused.value)
    assert "already been triaged and became %s" % pr["id"] in message, message
    assert "transition %s TRIAGED" % wish["id"] not in message, (
        "the remedy still asks for a transition out of a terminal: %s" % message)

    # ...and an untriaged wish still gets the triage route
    fresh = state.capture("FR", {"title": "another wish", "request_text": "please"})
    with pytest.raises(DispatchError) as untriaged:
        dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=fresh["id"],
                                         derives_from=fresh["id"]))
    assert "CONVERTED" in str(untriaged.value) and "resulting_item" in str(untriaged.value)


def test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it(state):
    """The remainder H155 carries, written as a test so it rots visibly instead of quietly.

    THE CHAIN, and it is the one the round-3 verification measured through the shipped hook rather
    than the one the comment first claimed. `_carries_its_own_criteria` asks the TYPE, so a `BUG`
    with an EMPTY criteria list excuses the architect step. What then measures the order is
    `validate_dispatch`, and the universe it resolves against is `_known_acceptance_ids_locked` --
    the root, the origin AND the approved amendments together. So a reference that exists only on
    the ROOT resolves, and the order is dispatched against the criteria of exactly the goal whose
    architect step is missing.

    THE TWO CASES THAT DO NOT GET THROUGH are asserted here too, because they are what BOUNDS the
    remainder: no reference at all, and a reference that exists nowhere.

    THIS TEST IS WRITTEN TO GO RED. The day the exemption asks the VALUE instead of the type -- or
    the resolution is narrowed to the origin -- the first assertion fails, and H155's second class
    is the paragraph to correct.
    """
    pr = state.capture("PR", dict(PR_FIELDS))
    approve_scope(state, pr["id"])
    hollow = state.capture("BUG", {
        "title": "a defect with no criteria of its own", "related_pr": pr["id"], "observed": "o",
        "expected": "e", "repro": "r", "severity": "low", "acceptance_criteria": []})

    def order(refs, scope):
        task = dispatch.create_task(state, dict(TSK_FIELDS, product_requirement=pr["id"],
                                                derives_from=hollow["id"], type="bugfix",
                                                acceptance_refs=list(refs),
                                                allowed_scope=[scope]))
        state.transition(task["id"], "READY")
        return task

    # the exemption itself: the TYPE excuses, whatever the list holds
    assert not dispatch.architect_step_owed(
        state, state.read_item(order(["AC-1"], "src/probe/**")["id"]), state.read_item(pr["id"]))

    # ...and no ACCEPTED SR exists anywhere in this store
    assert not list(state.iter_active_items("SR"))

    # WHERE THE CRITERIA ARE RESOLVED IS THE SPAWN, not the lease: `create_lease` grants in all
    # three cases and `validate_dispatch` is what refuses two of them. That split is part of the
    # measured chain -- the verifier read it off the shipped hook, which goes through
    # `validate_dispatch` -- and stating it as "the lease refuses" would be a claim the code does
    # not build.
    def spawn(task):
        lease = dispatch.create_lease(state, task["id"])
        header = dispatch.parse_header(dispatch.dispatch_header(lease))
        return dispatch.validate_dispatch(state, header, TSK_FIELDS["assigned_role"])

    # case 1: no reference at all -- the lease is granted, the spawn is refused
    with pytest.raises(DispatchError, match="carries no acceptance_refs"):
        spawn(order([], "src/none/**"))
    # case 2: a reference that exists nowhere -- same
    with pytest.raises(DispatchError, match="exist nowhere"):
        spawn(order(["AC-9"], "src/ghost/**"))
    # case 3: a reference that exists ON THE ROOT -- granted through both. This is the remainder.
    assert spawn(order(["AC-1"], "src/remainder/**")), (
        "H155's second class no longer holds -- correct the entry, this is not a defect in the "
        "test")


# ============================================ PR-0012 AC-1: the BATCH form of a repaired bug's close

def _plant_a_naming_test(state, item_id, names=True):
    """Write a real pytest node beside the state, naming `item_id` in its docstring's first
    paragraph -- or, with `names=False`, naming it nowhere.

    A FILE AND NOT A STRING, because since round 1's F2 `approvals.batch_walk_blockers` RESOLVES
    the nodes an Evidence records: a run command naming a node that exists nowhere measured
    nothing, and a TRIAGED bug with exactly that evidence was walked to VERIFIED and archived by
    one click. The node is resolved against the state root's parent, which is where a project's
    own tests live.
    """
    root = os.path.dirname(state.root)
    folder = os.path.join(root, "tools")
    os.makedirs(folder, exist_ok=True)
    function = "test_names_%s" % str(item_id).replace("-", "_").lower()
    subject = str(item_id) if names else "something else entirely"
    with io.open(os.path.join(folder, "test_planted.py"), "a", encoding="utf-8",
                 newline="\n") as handle:
        handle.write('def %s():\n    """closes %s"""\n    assert True\n\n\n'
                     % (function, subject))
    return "tools/test_planted.py::%s" % function


def _repaired_bug(state, title="a defect", measured=True, node=None):
    """A BUG at TRIAGED with -- unless `measured` says otherwise -- the passing test Evidence that
    names it: exactly the shape TSK-0131's survey measured 98 times over.

    `node` overrides the run command, which is what the F2 rows need: the evidence's run has to
    name a test that NAMES the defect, and the two ways to fail that are a node nothing declares
    and a node whose test is about something else.
    """
    goal = state.capture("PR", dict(PR_FIELDS, title="Kasse"))
    bug = state.capture("BUG", {"title": title, "related_pr": goal["id"], "observed": "o",
                                "expected": "e", "repro": "r", "severity": "low",
                                "acceptance_criteria": [{"id": "AC-1", "text": "t"}]})
    state.transition(bug["id"], "TRIAGED")
    if measured:
        run = node if node is not None else _plant_a_naming_test(state, bug["id"])
        state.capture("EVD", {"kind": "test", "result": "pass", "related": [bug["id"]],
                              "summary": "the regression run", "artifact_refs": ["staging/x/r.log"],
                              "run_command": "python -B -m pytest " + run,
                              "run_scope": "selection"})
    return state.read_item(bug["id"])


def _ask_the_batch(state, bugs):
    return approvals.create_pending_request(
        state, approvals.VERIFICATION_KIND,
        manifest=approvals.verification_subject_manifest(
            approvals.verification_batch(state, [bug["id"] for bug in bugs])))


def _measured_hole(state, title="a measured gap", bound="the role says so, no gate", triage=True):
    """A BUG carrying a `hole_number` and the sentence that says what bounds it -- the AC-4 shape.

    `triage=False` leaves it at OPEN, which is where most of this repository's own hole items that
    were captured by the migration door actually stand.
    """
    goal = state.capture("PR", dict(PR_FIELDS, title="Kasse"))
    fields = {"title": title, "related_pr": goal["id"], "observed": "the chain runs",
              "expected": "it should not", "repro": "r", "severity": "medium",
              "acceptance_criteria": [{"id": "AC-1", "text": "closed or accepted"}]}
    if bound is not None:
        fields[approvals.HOLE_LIMIT_FIELD] = bound
    hole = state.capture("BUG", fields, hole=True)
    if triage:
        state.transition(hole["id"], "TRIAGED")
    return state.read_item(hole["id"])


def _ask_the_exception_batch(state, holes):
    return approvals.create_pending_request(
        state, approvals.HOLE_EXCEPTION_KIND,
        manifest=approvals.hole_exception_subject_manifest(
            approvals.hole_exception_batch(state, [hole["id"] for hole in holes])))


def test_a_batch_of_accepted_exceptions_ends_on_the_off_chain_terminal(state):
    """PR-0012 AC-4: one answer accepts a whole batch of measured gaps, and every listed one ends
    on `ACCEPTED_EXCEPTION` -- the terminal BESIDE the BUG chain -- not on the chain's confirming
    end.

    RED WITHOUT THE `batch_walk_end` BRANCH for an off-chain target: the walk reads the type's
    confirming end and takes a gap the user ACCEPTED to VERIFIED, i.e. writes "measured gone" for
    something nobody measured -- and for a gap standing at OPEN it does not even get that far,
    because `chain.index(end)` has no index for a status beside the chain.

    A GAP AT OPEN IS IN THE BATCH TOO, and that is the second half of the walk: the automaton
    allows this terminal only FROM TRIAGED (`backlog_types`, `terminal_from`), so the walk climbs
    the free edge first. Without the climb the mint refuses mid-walk, after the APR exists.
    """
    triaged = _measured_hole(state, "a gap somebody looked at")
    fresh = _measured_hole(state, "a gap captured by the migration door", triage=False)
    assert state.read_item(fresh["id"])["status"] == "OPEN"
    mint_via_hook(state, _ask_the_exception_batch(state, [triaged, fresh]))
    for hole in (triaged, fresh):
        body = state.read_anywhere(hole["id"])
        body = body[0] if isinstance(body, tuple) else body
        assert body["status"] == approvals.HOLE_EXCEPTION_STATUS, (hole["id"], body["status"])
        assert not os.path.exists(state.active_path(hole["id"])), (
            "%s ended on a terminal and was not archived" % hole["id"])


def test_a_gap_without_a_bound_is_refused_from_the_exception_batch_by_name(state):
    """CLAUDE.md's house rule, at the one place a click could break it: a gap is CLOSED or carries
    an accepted exception that says WHAT BOUNDS IT -- there is no third state, so an item with no
    `limits` sentence is refused BY NAME before the question exists.

    THE BOUND IS THE PROPERTY, NOT A HOLE NUMBER, and the other direction measures exactly that: a
    DEFECT that states a bound -- BUG-0055's and BUG-0056's shape, measured unclosable without a
    spec decision and without a rule a PreToolUse hook can ask -- is acceptable on this route,
    while a numbered hole that states none is not. A refusal keyed on `hole_number` would have
    locked out the two items this order has to put to the user.

    RED WITHOUT the bound refusal in `hole_exception_batch`: the user is asked to sign
    "this stays open" with nothing beside it saying what takes the place of the protection.
    """
    good = _measured_hole(state)
    boundless = _measured_hole(state, "a gap with no bound", bound=None)

    with pytest.raises(approvals.ApprovalError) as without_bound:
        approvals.hole_exception_batch(state, [good["id"], boundless["id"]])
    assert boundless["id"] in str(without_bound.value)
    assert approvals.HOLE_LIMIT_FIELD in str(without_bound.value)
    assert good["id"] not in str(without_bound.value), "the refusal named the healthy entry too"

    # THE OTHER DIRECTION: a defect with NO hole number but WITH a bound is acceptable
    bounded_defect = _repaired_bug(state, "unclosable without a spec decision", measured=False)
    path = state.active_path(bounded_defect["id"])
    body = state._read_yaml(path)
    body[approvals.HOLE_LIMIT_FIELD] = "the wireframe carries its own approval reference instead"
    state._write_yaml_atomic(path, body)
    accepted = approvals.hole_exception_batch(state, [good["id"], bounded_defect["id"]])
    assert {record[approvals.GOAL_ITEM_FIELD] for record in accepted} == {
        good["id"], bounded_defect["id"]}
    assert not state.read_item(bounded_defect["id"]).get(approvals.HOLE_NUMBER_FIELD)


def test_the_exception_option_names_every_listed_hole_and_its_bound(state):
    """The compared carrier: the approving option's description is what `gate_approval` matches
    character for character, so every listed id AND the bound it stands on have to be IN it -- a
    user who reads only the option still reads what each acceptance costs.

    RED WITHOUT `_hole_exception_option_form` registered in `OPTION_FORMS`: the option falls back
    to the generic text and the bounds never reach the person signing them.
    """
    holes = [_measured_hole(state, "gap %d" % n, bound="what limits gap %d is this" % n)
             for n in range(3)]
    question = approvals.build_question(_ask_the_exception_batch(state, holes))
    description = str(question["options"][0]["description"])
    for n, hole in enumerate(holes):
        assert hole["id"] in description, (hole["id"], description)
        assert "what limits gap %d is this" % n in description, description
        assert hole["id"] not in question["question"], question["question"]


def test_a_batch_kind_given_a_positional_id_is_sent_to_the_flag_with_that_id_in_hand(capsys):
    """`hole_exception` took a positional id until PR-0012 AC-4 gave it the list form, so a role
    with the older habit types one -- and the refusal has to carry the id it was given rather than
    tell it that none was named.

    RED WITHOUT the order of the two checks in `cli`'s request-approval branch: the
    "none was named" refusal fires first, so the message says the opposite of what happened and its
    remedy drops the id the caller supplied.

    BOTH DIRECTIONS: with neither id nor list the "none was named" message is the right one, and
    its verb stays neutral -- `verification` closes what it lists, `hole_exception` accepts that it
    stays open and closes nothing.
    """
    from kernel import cli

    code = cli.main(["--root", "nowhere", "request-approval", approvals.HOLE_EXCEPTION_KIND,
                     "BUG-0102"])
    said = capsys.readouterr().err
    assert code != 0, said
    assert "BUG-0102" in said, said
    assert "--batch" in said, said

    code = cli.main(["--root", "nowhere", "request-approval", approvals.HOLE_EXCEPTION_KIND])
    said = capsys.readouterr().err
    assert code != 0 and "none was named" in said, said
    assert "closes the items" not in said, (
        "the verb claims a closing an exception never does: %s" % said)


def test_a_bound_that_is_not_a_sentence_is_refused_before_it_becomes_text(state):
    """The bound is what the user READS, so a value that is not text is refused rather than folded:
    `_one_line` would turn a list into its `str()` and the approving option would carry
    `['a', 'b']` as the thing that limits the gap.

    RED WITHOUT the isinstance check in `hole_exception_batch`: the batch builds, and the option
    the gate compares character for character shows the user a Python repr.

    THE FIELD HAS NO SCHEMA of its own -- `backlog_types` declares the NAME, not the type -- so
    this is asked where the value becomes readable text and nowhere else.
    """
    hole = _measured_hole(state)
    path = state.active_path(hole["id"])
    body = state._read_yaml(path)
    body[approvals.HOLE_LIMIT_FIELD] = ["a list", "of bounds"]
    state._write_yaml_atomic(path, body)
    with pytest.raises(approvals.ApprovalError) as refused:
        approvals.hole_exception_batch(state, [hole["id"]])
    assert hole["id"] in str(refused.value) and "list" in str(refused.value)


def test_the_card_of_a_list_bound_approval_counts_what_it_binds(state):
    """A list-bound approval carries no `item`, and the card read that as "keinen Vorgang" -- the
    opposite of the truth for the one kind whose whole point is that it binds several.

    RED WITHOUT the `listed_items(consumed_request(...))` branch: the card announces a batch of
    gaps as an approval for no item at all, on the surface a user meets right after clicking.

    THE COUNT COMES FROM THE PROVENANCE and not from the caller: the APR file keeps only the
    manifest digest, so what is counted is the list the consumed request carries -- the record a
    later auditor opens.

    THE COUNT IS READ AS A NUMBER AND NOT AS A DIGIT SOMEWHERE (the verifier's G3 of this round):
    `"2" in card` is satisfied by a card that says 12, 20 or 32, so a counter that added a constant
    to the length passed it. The number is matched with no digit on either side, which is the
    property -- and the card's wording stays in `approvals.approval_card`, not copied here.
    """
    holes = [_measured_hole(state, "gap %d" % n) for n in range(2)]
    request = _ask_the_exception_batch(state, holes)
    mint_via_hook(state, request)
    apr = state._read_yaml(os.path.join(state.root, "approvals", "APR-0001.yaml"))
    assert apr.get("item") is None, apr
    card = approvals.approval_card(apr, state)
    assert re.search(r"(?<!\d)%d(?!\d)" % len(holes), card), card
    assert "keinen Vorgang" not in approvals.approval_card(apr, state)
    # ...and without a state it says what it can rather than counting nothing
    assert "keinen Vorgang" in approvals.approval_card(apr)


def test_a_batch_stops_covering_a_hole_whose_bound_moved(state):
    """The sentence that says what bounds a gap is the one thing the acceptance is FOR, so an edit
    to it past the kernel kills the cover -- exactly as an edit to a goal's scope kills a plan's.

    RED WITHOUT `content_question`: a listed hole bound to the per-item SCOPE hash instead of its
    own kind's manifest, because `HOLE_LIMIT_FIELD` is not one of `_SCOPE_FIELDS` -- so the bound
    could be rewritten under a standing acceptance and the mint would close the gap anyway.
    """
    hole = _measured_hole(state)
    request = _ask_the_exception_batch(state, [hole])
    path = state.active_path(hole["id"])
    edited = state._read_yaml(path)
    edited[approvals.HOLE_LIMIT_FIELD] = "nothing bounds it, actually"
    state._write_yaml_atomic(path, edited)
    mint_via_hook(state, request, expect_success=False)
    assert state.read_item(hole["id"])["status"] == "TRIAGED"


def test_the_batch_mint_walks_every_listed_bug_to_verified_and_archives_it(state):
    """PR-0012 AC-1, through the REAL PostToolUse hook: one answer closes the whole batch -- every
    listed defect walks TRIAGED -> APPROVED -> FIXED -> VERIFIED on the Evidence that named it,
    presents the batch approval and leaves `bugs/active/`.

    RED WITHOUT THE FIX: with `_close_what_the_batch_lists` not called from `mint`, the approval is
    minted and every listed bug stands untouched at TRIAGED -- which is DEC-0086's measured cost.
    RED ALSO WITHOUT `state._archive_locked`: the walk reaches VERIFIED and then blocks on the
    kernel lock the mint already holds.
    """
    first, second = _repaired_bug(state), _repaired_bug(state, "another defect")
    request = _ask_the_batch(state, [first, second])
    mint_via_hook(state, request)

    for bug in (first, second):
        with pytest.raises(Exception):
            state.read_item(bug["id"])           # no longer active: archived
        archived = state._read_yaml(state.archive_path(bug["id"], 2026))
        assert archived["status"] == "VERIFIED", archived
        assert str(archived["approval_ref"]).startswith("APR-"), archived
        assert archived["closed_at"], archived


def test_a_bug_without_a_passing_test_evidence_is_refused_from_the_batch_by_name(state):
    """PR-0012 AC-1 / BUG-0090's rule: the batch is refused BEFORE the user is shown a question and
    the refusal names the id that is not measured -- never "some item".

    RED WITHOUT the confirming-Evidence branch of `batch_walk_blockers`: the question is built over
    an unmeasured defect and the mint walks it to VERIFIED with nothing having measured it.
    """
    measured = _repaired_bug(state)
    unmeasured = _repaired_bug(state, "never measured", measured=False)
    with pytest.raises(ApprovalError) as refusal:
        approvals.verification_batch(state, [measured["id"], unmeasured["id"]])
    assert unmeasured["id"] in str(refusal.value) and "no passing" in str(refusal.value)
    assert measured["id"] not in str(refusal.value).split(unmeasured["id"])[1]


@pytest.mark.parametrize("shape", ["a node nothing declares", "a test about something else",
                                   "no node at all"])
def test_a_bug_whose_evidence_does_not_name_it_is_refused_from_the_batch(state, shape):
    """DEC-0100 (3) / round 1 F2: a passing `test` Evidence RELATED to the bug was the whole test,
    and it let a defect be closed on a run that never looked at it.

    MEASURED by the verifier: a TRIAGED bug whose evidence carried
    `--run-command "python -B -m pytest tools/test_x.py::test_y"` -- a node that exists nowhere in
    the tree -- was walked TRIAGED -> APPROVED -> FIXED -> VERIFIED and archived by ONE click. The
    three shapes here are the three ways an evidence can fail to be about its defect, and each
    earns its own sentence because each needs a different repair.

    `naming_tests.coverage_blocker` is the reader, shared with `tools/close_measured_pass.py`, so
    the search that PROPOSES a batch and the check that accepts one cannot disagree.
    """
    if shape == "a node nothing declares":
        bug = _repaired_bug(state, node="tools/test_x.py::test_y")
    elif shape == "no node at all":
        bug = _repaired_bug(state, node="tools/test_planted.py")
    else:
        bug = _repaired_bug(state, measured=False)
        elsewhere = _plant_a_naming_test(state, bug["id"], names=False)
        state.capture("EVD", {"kind": "test", "result": "pass", "related": [bug["id"]],
                              "summary": "a run about a neighbour", "run_scope": "selection",
                              "artifact_refs": ["staging/x/r.log"],
                              "run_command": "python -B -m pytest " + elsewhere})
    with pytest.raises(ApprovalError) as refusal:
        approvals.verification_batch(state, [bug["id"]])
    assert bug["id"] in str(refusal.value), str(refusal.value)
    assert "DEC-0100" in str(refusal.value) or "repeat" in str(refusal.value), str(refusal.value)
    # ...and the item did not move: a refusal at the request is only half of "nothing was closed"
    assert state.read_item(bug["id"])["status"] == "TRIAGED"


def test_the_batch_the_request_refused_cannot_be_minted_either(state):
    """The second half of F2: the refusal has to stand where the WRITES happen, not only where the
    question is built.

    A request built while the evidence still named a real test, then the test taken away -- the
    shape a moving tree has -- is put to the mint, and the mint re-checks coverage before its first
    write (DEC-0100 (3)'s all-or-nothing clause). Without the check in `batch_walk_blockers`, which
    the mint calls too, the click closes the defect on a run nobody can repeat.
    """
    bug = _repaired_bug(state)
    request = _ask_the_batch(state, [state.read_item(bug["id"])])
    os.remove(os.path.join(os.path.dirname(state.root), "tools", "test_planted.py"))
    assert request, "the request was not built, so nothing below measures the second half"
    with pytest.raises(ApprovalError) as refusal:
        approvals.verification_batch(state, [bug["id"]])
    assert bug["id"] in str(refusal.value)
    assert state.read_item(bug["id"])["status"] == "TRIAGED"


def test_a_parent_defect_is_not_closed_by_its_childs_green_run(state):
    """DEC-0100 (3) one level up, and it was live in this repository's own store: `BUG-0082` carries
    `related_pr: BUG-0075`, so the passing run that measured the metacharacter fix answered as
    BUG-0075's CURRENT verdict too -- `report.evidence_covers` accepts an indirect hop by design,
    which is right for "does this body of work ship" and wrong for "is THIS defect repaired".

    Measured while round 1's F2 was being closed: the third batch line of the 31 closable ids was
    refused with "its evidence names <the child's node>, and none of those tests NAMES BUG-0075".
    The refusal was correct and the SELECTION was the defect -- `proofs_naming` now asks for an
    Evidence whose `related` names the item itself.

    The child's run is green here, so nothing in this test is about a failing measurement: what is
    measured is that a green run about a CHILD closes the child and not its parent.
    """
    parent = _repaired_bug(state, "the parent", measured=False)
    child = state.capture("BUG", {"title": "the child", "related_pr": parent["id"],
                                  "observed": "o", "expected": "e", "repro": "r",
                                  "severity": "low",
                                  "acceptance_criteria": [{"id": "AC-1", "text": "t"}]})
    state.transition(child["id"], "TRIAGED")
    node = _plant_a_naming_test(state, child["id"])
    state.capture("EVD", {"kind": "test", "result": "pass", "related": [child["id"]],
                          "summary": "the child's regression run", "run_scope": "selection",
                          "artifact_refs": ["staging/x/r.log"],
                          "run_command": "python -B -m pytest " + node})

    # the control: the CHILD closes on its own run
    assert approvals.verification_batch(state, [child["id"]])[0][approvals.GOAL_ITEM_FIELD] \
        == child["id"]
    # ...and the parent does not, however green the child is
    with pytest.raises(ApprovalError) as refusal:
        approvals.verification_batch(state, [parent["id"]])
    assert parent["id"] in str(refusal.value) and "no passing" in str(refusal.value)


def test_a_bug_past_the_edge_the_batch_commits_is_refused_from_it_by_name(state):
    """PR-0012 AC-1: the batch commits TRIAGED -> APPROVED, so an item already past that status
    would be signed for something it no longer needs.

    RED WITHOUT the chain-position branch of `batch_walk_blockers`: a FIXED bug joins the batch and
    the walk's own slice then closes it anyway, so nothing would ever report it.
    """
    walked = _repaired_bug(state)
    approve(state, walked["id"], "scope")
    state.transition(walked["id"], "FIXED")
    with pytest.raises(ApprovalError) as refusal:
        approvals.verification_batch(state, [walked["id"]])
    assert "already FIXED" in str(refusal.value) and walked["id"] in str(refusal.value)


def test_a_batch_longer_than_the_limit_is_refused_at_the_builder():
    """PR-0012 AC-1: the ids ride in the compared option description, so a list nobody can read
    through is refused where it costs least -- before the question exists.

    RED WITHOUT the `BATCH_LIMIT` branch: a batch of any length builds a question whose approving
    option grows without bound.
    """
    record = {approvals.GOAL_ITEM_FIELD: "BUG-0001", "revision": 1,
              approvals.GOAL_SCOPE_HASH_FIELD: "0" * 64,
              approvals.LISTED_EVIDENCE_FIELD: "EVD-0001"}
    assert approvals.verification_subject_manifest([record] * approvals.BATCH_LIMIT)["bugs"]
    with pytest.raises(ApprovalError) as refusal:
        approvals.verification_subject_manifest([record] * (approvals.BATCH_LIMIT + 1))
    assert str(approvals.BATCH_LIMIT) in str(refusal.value)
    with pytest.raises(ApprovalError):
        approvals.verification_subject_manifest([])


def test_the_batch_option_names_every_listed_bug_and_its_evidence(state):
    """PR-0012 AC-1: the SENTENCE names the count, the APPROVING OPTION carries the list -- and the
    option is the text `gate_approval` compares character for character.

    RED WITHOUT `OPTION_FORMS` in `build_question`: the option repeats the sentence, so the ids and
    their proofs stand in no compared text at all and a relay could drop half the batch unnoticed.
    """
    bugs = [_repaired_bug(state), _repaired_bug(state, "another defect")]
    request = _ask_the_batch(state, bugs)
    question = approvals.build_question(request)
    approving = question["options"][0]["description"]
    for record in request["subject_manifest"]["bugs"]:
        assert record[approvals.GOAL_ITEM_FIELD] in approving, approving
        assert record[approvals.LISTED_EVIDENCE_FIELD] in approving, approving
        assert record[approvals.GOAL_ITEM_FIELD] not in question["question"], question["question"]
    assert str(len(bugs)) in question["question"]


def test_only_a_kind_with_its_own_option_form_reads_differently_in_the_two_places():
    """Both ends of `OPTION_FORMS`: a kind with an entry says MORE in the option than in the
    sentence, and a kind without one says the same in both -- which is what keeps the table from
    silently rewriting a question nobody decided to change.

    RED WITHOUT the `option_form is not None` guard in `build_question`: every kind's option is
    rebuilt from a form, the older questions change text and every live pending request dies.
    """
    assert set(approvals.OPTION_FORMS) <= set(approvals.APR_KINDS)
    # ONE RECORD, UNDER EVERY KEY A LIST-BOUND BUILDER USES, so a second batch kind is measured by
    # this test on the day it arrives instead of reading as "the form renders nothing": the entry
    # is the same signed-item record either way (`listed_items` is what makes it one), and the key
    # is the builder's own manifest parameter. `manifest_parameters` is the reader.
    from kernel.cli import manifest_parameters
    entry = {approvals.GOAL_ITEM_FIELD: "BUG-0009", "revision": 1,
             approvals.GOAL_SCOPE_HASH_FIELD: "0" * 64,
             approvals.LISTED_EVIDENCE_FIELD: "EVD-0009",
             approvals.LISTED_BOUND_FIELD: "what bounds it today"}
    manifest = {key: [entry]
                for kind in approvals.OPTION_FORMS
                for key in manifest_parameters(approvals.LINE_MANIFEST_BUILDERS[kind])}
    assert len(manifest) == len(approvals.OPTION_FORMS), (
        "two option-form kinds share a manifest key, so this probe can no longer tell them apart")
    for kind, form in approvals.OPTION_FORMS.items():
        assert kind in approvals.TARGET_FORMS, (
            "%s renders an option form but no sentence form" % kind)
        assert "BUG-0009" in form(manifest)
        assert "BUG-0009" not in approvals.TARGET_FORMS[kind](manifest)
    for kind in set(approvals.TARGET_FORMS) - set(approvals.OPTION_FORMS):
        request = {"request_id": "ab" * 16, "kind": kind, "item": None, "revision": None,
                   "item_title": "", "mint_code": "c0ffee", "subject_manifest": {},
                   "subject_manifest_hash": "de" * 32}
        question = approvals.build_question(request)
        target = approvals.TARGET_FORMS[kind]({})
        assert target in question["question"] and target in question["options"][0]["description"]


def test_only_a_list_kind_paired_with_a_type_closes_what_it_lists():
    """`batch_closing_types` is the line between the two list-bound kinds, and it is derived: the
    plan approval stands in for a question whose goals keep their own edges and must move nothing,
    the verification approval is paired with BUG and walks every one it lists.

    RED WITHOUT that derivation (a written-out set of closing kinds): the plan branch closes goals
    the day somebody adds the pair, or the verification branch stops closing when the pair moves.
    """
    assert approvals.batch_closing_types(approvals.PLAN_KIND) == frozenset()
    assert approvals.batch_closing_types(approvals.VERIFICATION_KIND) == frozenset({"BUG"})
    assert approvals.batch_walk_end("BUG", approvals.VERIFICATION_KIND) == "VERIFIED"


def test_only_a_manifest_of_signed_item_records_reads_as_a_list():
    """`listed_items` decides list-bound-ness on the RECORD, not on the kind -- an entry counts when
    it carries the id AND the content hash signed for it. Both ends, because a reader that answered
    "yes" too easily would make an ordinary approval bind items it never named.

    RED WITHOUT the hash condition: any list of mappings carrying an `item` key reads as a signed
    list, and `assert_apr_in_force` then asks the list check instead of the item check.
    """
    signed = {"bugs": [{approvals.GOAL_ITEM_FIELD: "BUG-0001",
                        approvals.GOAL_SCOPE_HASH_FIELD: "0" * 64}]}
    assert approvals.listed_items({"subject_manifest": signed}) == ("BUG-0001",)
    for lookalike in ({"tasks": ["TSK-0001"]},
                      {"tasks": [{approvals.GOAL_ITEM_FIELD: "TSK-0001"}]},
                      {"question": "warum", "scope": "nur lesen"},
                      {}):
        assert approvals.listed_items({"subject_manifest": lookalike}) == (), lookalike


def test_a_batch_approval_authorises_only_the_bugs_it_lists(state):
    """The batch stands in for the `scope` mint of every defect it names -- and of no other one.

    RED WITHOUT `_names_the_item`: `assert_transition_approved` compares `apr["item"]`, the batch
    approval is bound to no single item, and the mint's own walk refuses on the first edge.
    RED WITHOUT the list check inside it: the same approval walks a defect it never listed.
    """
    listed = _repaired_bug(state)
    stranger = _repaired_bug(state, "never listed")
    mint_via_hook(state, _ask_the_batch(state, [listed]))
    assert state._read_yaml(state.archive_path(listed["id"], 2026))["status"] == "VERIFIED"
    with pytest.raises(Exception) as refusal:
        state.transition(stranger["id"], "APPROVED")
    assert "none is in force" in str(refusal.value)


def test_a_batch_stops_covering_a_bug_whose_content_moved_after_the_question(state):
    """The same invalidation a per-item approval has, on the list-bound shape: an out-of-band edit
    of the signed content kills the cover before the mint can use it.

    RED WITHOUT the hash comparison in `_assert_the_list_covers`: the edited defect is closed on an
    approval whose subject it no longer matches.
    """
    bug = _repaired_bug(state)
    request = _ask_the_batch(state, [bug])
    path = state.active_path(bug["id"])
    edited = state._read_yaml(path)
    edited["acceptance_criteria"] = [{"id": "AC-1", "text": "something nobody approved"}]
    state._write_yaml_atomic(path, edited)
    mint_via_hook(state, request, expect_success=False)
    assert state.read_item(bug["id"])["status"] == "TRIAGED"


def test_a_batch_mint_leaves_the_index_as_fresh_as_a_per_step_rebuild_would(state):
    """The batch walk suppresses the per-step index rebuild (`state._transition_locked`'s
    `regenerate=False`) because one mint is ONE operation -- measured: a batch of 25 on a
    repo-sized store spent 100 rebuilds inside a single hook call. This is the other end of that
    trade: what the store shows afterwards must be exactly what a per-step rebuild would have left.

    RED WITHOUT A REBUILD AFTER THE WALK -- and it takes removing BOTH of them, the one
    `_close_what_the_batch_lists` does for itself and `mint`'s trailing one, because either alone
    still leaves the index right: the index then still lists both closed defects as active, so every
    rollup, the board and `stock lies upward` read a state the store left behind. Measured that way
    in the round's rig; removing only one is green here on purpose, and the reason the batch keeps
    its own is a different rule (`tools/test_board.py::test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind`).
    """
    first, second = _repaired_bug(state), _repaired_bug(state, "another defect")
    mint_via_hook(state, _ask_the_batch(state, [first, second]))

    index_path = os.path.join(state.root, "generated", "index.yaml")
    # THE STAMP IS NOT PART OF THE SUBJECT and has to come out of the comparison: `generated_at`
    # has SECOND resolution (`state._now_iso`), so two writes that straddle a second boundary
    # differ in it while the content is identical -- and whether they do is the HOST's load, not
    # this walk's doing. Measured 2026-09-12: this node passed solo (52.1 s) and failed inside a
    # six-suite run of 442 s on the same tree, which is the BUG-0262 / H180 class arriving in
    # another test. Everything the walk really owes -- every item row -- is still compared.
    after_the_mint = state._read_yaml(index_path)
    state.generate_index()
    rebuilt = state._read_yaml(index_path)
    assert {key: value for key, value in rebuilt.items() if key != "generated_at"} == {
        key: value for key, value in after_the_mint.items() if key != "generated_at"}
    assert "generated_at" in rebuilt, "the stamp this comparison excludes stopped existing"
    listed = {str(row.get("id")) for row in (after_the_mint.get("items") or [])}
    assert first["id"] not in listed and second["id"] not in listed, sorted(listed)


def test_a_batch_approval_stays_in_force_for_every_id_it_lists_after_the_minting_process_ended(
        state):
    """The mint runs inside ONE hook call, and a provider kills a hook that outruns its budget. What
    that leaves behind is the claim `approvals.BATCH_LIMIT`'s comment makes: the approval the user
    already gave keeps covering every id it lists, so whatever the walk did not reach is finished
    with `transition` and no second question.

    WHAT THIS NODE SHOWS AND WHAT IT DOES NOT: it measures the part a test can reach -- that the
    stored approval is still IN FORCE for a listed item after the minting process is gone, which is
    the condition `assert_transition_approved` puts the recovery on (`assert_apr_in_force` reads the
    revision and the content, never the status). The other half needs a real kill and is a PROCESS
    measurement, recorded in this round's protocol: the hook killed 18 s into a 24 s walk left 4 of
    10 closed, APR-0038 written, and `transition` walked an untouched listed defect APPROVED ->
    FIXED -> VERIFIED at rc 0 -- plus a stale kernel lock that ages out on its TTL.

    RED WITHOUT `_names_the_item`'s list branch: no approval is in force for any listed id once the
    mint is over, and a whole batch is lost to one killed process.
    """
    first, second = _repaired_bug(state), _repaired_bug(state, "the second of the batch")
    request = _ask_the_batch(state, [first, second])
    mint_via_hook(state, request)

    for bug in (first, second):
        closed = state._read_yaml(state.archive_path(bug["id"], 2026))
        assert closed["status"] == "VERIFIED"
        live = approvals.live_list_approval(state, closed, approvals.VERIFICATION_KIND)
        assert live is not None and live["id"] == closed["approval_ref"], (bug["id"], live)


def test_a_batch_that_moved_since_the_question_closes_nothing_at_all(state):
    """The half-closed batch, which is the failure mode a per-item check could not have: the walk
    runs AFTER the APR is written and the request consumed, so a refusal inside it would leave a
    real approval, a spent request and some of the listed defects closed.

    Measured shape: two defects are asked for; between question and click the second one's test
    starts failing (a newer `fail` Evidence supersedes the pass, DEC-0061's newest-per-kind rule),
    which is exactly what the confirming edge refuses on. Nothing may move.

    RED WITHOUT the `batch_walk_blockers` call in `mint`: the first defect is archived VERIFIED, an
    APR exists for it, and the hook reports that no approval was created -- three records
    disagreeing about one answer.
    """
    first, second = _repaired_bug(state), _repaired_bug(state, "regressed since")
    request = _ask_the_batch(state, [first, second])
    state.capture("EVD", {"kind": "test", "result": "fail", "related": [second["id"]],
                          "summary": "it fails again", "artifact_refs": ["staging/x/r.log"],
                          "run_command": "python -B -m pytest tools/test_x.py::test_y",
                          "run_scope": "selection"})
    result = mint_via_hook(state, request, expect_success=False)
    assert "moved since the question" in result.stderr, result.stderr
    for bug in (first, second):
        assert state.read_item(bug["id"])["status"] == "TRIAGED"
        assert state.read_item(bug["id"])["approval_ref"] is None
    assert not [name for name in os.listdir(os.path.join(state.root, "approvals"))
                if name.startswith("APR-")]


def test_a_batch_whose_signed_CONTENT_moved_closes_nothing_and_mints_nothing(state):
    """The sibling of the Evidence case, and the one that was open: a listed defect whose SIGNED
    content is edited between question and click.

    Measured as a process before the fix (verifier round 1, B1): the first defect stood VERIFIED and
    archived, the second at TRIAGED carrying the batch's `approval_ref`, the third untouched, the
    request consumed and the hook saying "no approval was created" -- four records disagreeing about
    one answer. The refusal comes from `_assert_the_list_covers`, which `state._transition_locked`
    reaches only once the walk is already running, i.e. once the APR exists.

    RED WITHOUT the `request is not None` branch of `batch_walk_blockers`: the batch closes HALF.
    """
    first, second, third = (_repaired_bug(state), _repaired_bug(state, "edited after the question"),
                            _repaired_bug(state, "the third"))
    request = _ask_the_batch(state, [first, second, third])
    # THROUGH THE KERNEL, so the revision moves exactly as it does in life
    state.update_item(second["id"], {"acceptance_criteria": [{"id": "AC-1", "text": "other"}]})

    result = mint_via_hook(state, request, expect_success=False)
    assert "moved since the question" in result.stderr, result.stderr
    for bug in (first, second, third):
        assert state.read_item(bug["id"])["approval_ref"] is None, bug["id"]
        assert not os.path.exists(state.archive_path(bug["id"], 2026)), bug["id"]
    assert not [name for name in os.listdir(os.path.join(state.root, "approvals"))
                if name.startswith("APR-")]
    # ...and the question is still answerable, because nothing consumed it
    assert approvals.pending_request(state, request["request_id"])


def test_the_batch_flag_belongs_to_the_kinds_whose_resolver_reads_it():
    """`cli.kinds_reading_argument` derives the flag's owners through the resolver, so the parser
    and the refusal cannot disagree about which kind may carry `--batch`.

    RED WITHOUT the derivation (a written-out set of kinds): the flag is accepted for a kind whose
    manifest key was renamed, and refused for the next batch kind the day it arrives.
    """
    from kernel import cli

    assert cli.kinds_reading_argument(cli.BATCH_ARGUMENT) == frozenset(
        {approvals.VERIFICATION_KIND, approvals.HOLE_EXCEPTION_KIND})
    assert cli.kinds_reading_argument("no-such-argument") == frozenset()

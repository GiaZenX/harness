"""Tests for the state-kernel core operations (HARNESS_V2_SPEC.md II.4, step 1.4a)."""
import os
import sys
import threading

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "team-kits"))

from conftest import drive_task_to, walk_to_status  # noqa: E402 -- the sanctioned chain walkers
from kernel.backlog_types import (  # noqa: E402
    BLOCKED_REASON_FIELD,
    BLOCKED_RESULT,
    DATE_FIELDS,
    EVIDENCE_RESULT_FIELD,
    PARENT_FIELDS,
    REQUIRED_FIELDS,
    V1_STATUS_MAPPING,
    TransitionError,
)
from kernel.state import _CLOSED_VOCABULARY, ProjectState, StateError  # noqa: E402


PR_FIELDS = {
    "title": "Checkout flow",
    "class": "normal",
    "problem": "no checkout",
    "goal": "working checkout",
    "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
    "invariants": [],
    "out_of_scope": ["payments"],
    "priority": "high",
}


@pytest.fixture
def state(tmp_path):
    # the kernel is fail-closed on a missing state dir (spec II.4: empty state
    # blocks; only the installer bootstrap creates it) -- simulate an
    # initialized project here
    root = tmp_path / "project_memory"
    root.mkdir()
    return ProjectState(str(root))


def make_pr(state, **overrides):
    fields = dict(PR_FIELDS)
    fields.update(overrides)
    return state.capture("PR", fields)


# -- capture -------------------------------------------------------------------

def test_capture_assigns_kernel_fields(state):
    item = make_pr(state)
    assert item["id"] == "PR-0001"
    assert item["status"] == "DRAFT"
    assert item["revision"] == 1
    assert item["approval_ref"] is None
    assert item["created"]
    on_disk = yaml.safe_load(open(state.active_path("PR-0001"), encoding="utf-8"))
    assert on_disk == item


def test_capture_sequential_ids(state):
    assert make_pr(state)["id"] == "PR-0001"
    assert make_pr(state)["id"] == "PR-0002"


def test_capture_rejects_missing_required_field(state):
    fields = dict(PR_FIELDS)
    del fields["out_of_scope"]
    with pytest.raises(StateError, match="out_of_scope"):
        state.capture("PR", fields)


def test_capture_rejects_kernel_set_fields(state):
    with pytest.raises(StateError, match="kernel-set"):
        make_pr(state, status="ACCEPTED")


def test_capture_rejects_unknown_type(state):
    with pytest.raises(StateError, match="unknown|does not handle"):
        state.capture("ARC", {"title": "x"})


def test_id_allocation_includes_archive(state):
    """Max-scan spans active AND archive -- archived ids are never reused."""
    item = make_pr(state)
    walk_to_status(state, item, "ACCEPTED")
    state.archive(item["id"])
    assert make_pr(state)["id"] == "PR-0002"


# -- transition ----------------------------------------------------------------

def test_transition_chain_and_illegal_jump(state):
    item = make_pr(state)
    walk_to_status(state, item, "APPROVED")
    with pytest.raises(TransitionError):
        state.transition(item["id"], "ACCEPTED")  # only from DELIVERED


def test_tsk_failed_ready_requires_approved_retry(state):
    # the origin has to EXIST: `derives_from` is a gate input (the dispatch gate
    # resolves acceptance_refs against it), so the kernel refuses a phantom id
    pr = state.capture("PR", {
        "title": "Root", "class": "normal", "problem": "p", "goal": "g",
        "acceptance_criteria": [{"id": "AC-1", "text": "works"}], "invariants": [],
        "out_of_scope": [], "priority": "high",
    })
    task = state.capture("TSK", {
        "product_requirement": pr["id"],
        "root_revision": 1,
        "derives_from": pr["id"],
        "type": "implementation",
        "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"],
        "required_inputs": [],
        "allowed_scope": ["src/"],
        "forbidden_scope": ["secrets/"],
        "expected_outputs": ["src/x.py"],
        "dependencies": [],
    })
    # LEASED/IN_PROGRESS come from the real lease lifecycle (DEC-0038): a bare transition into a
    # lease-bearing status is now refused, so the honest walk mints the lease.
    drive_task_to(state, task["id"], "FAILED")
    with pytest.raises(TransitionError, match="approved retry"):
        state.transition(task["id"], "READY")
    state.transition(task["id"], "READY", approved_retry=True)


# -- update + approval invalidation --------------------------------------------

def test_hashed_edit_invalidates_approval(state):
    item = make_pr(state)
    # simulate an approval (approve() lands in step 1.4b -- set via kernel file io)
    with state.lock:
        raw = state.read_item(item["id"])
        raw["approval_ref"] = "APR-0001"
        raw["status"] = "APPROVED"
        state._write_yaml_atomic(state.active_path(item["id"]), raw)
    updated = state.update_item(item["id"], {"goal": "DIFFERENT goal"})
    assert updated["revision"] == 2
    assert updated["approval_ref"] is None
    assert updated["status"] == "DRAFT"  # invalidation target for PR


def test_unhashed_edit_keeps_approval(state):
    item = make_pr(state)
    with state.lock:
        raw = state.read_item(item["id"])
        raw["approval_ref"] = "APR-0001"
        raw["status"] = "APPROVED"
        state._write_yaml_atomic(state.active_path(item["id"]), raw)
    updated = state.update_item(item["id"], {"priority": "low"})
    assert updated["revision"] == 1
    assert updated["approval_ref"] == "APR-0001"
    assert updated["status"] == "APPROVED"


def test_hashed_edit_without_approval_keeps_revision(state):
    item = make_pr(state)
    updated = state.update_item(item["id"], {"goal": "new goal"})
    assert updated["revision"] == 1
    assert updated["status"] == "DRAFT"


def test_update_rejects_status_and_id_changes(state):
    item = make_pr(state)
    with pytest.raises(StateError, match="dedicated command"):
        state.update_item(item["id"], {"status": "ACCEPTED"})


def test_dec_capture_starts_valid(state):
    dec = state.capture("DEC", {
        "title": "use SubagentStart binding",
        "context": "S3 spike",
        "decision": "bind lease at SubagentStart",
        "consequences": "no PostToolUse dependency",
        "source": "phase0-disposition", "work": "none",
    })
    assert dec["status"] == "VALID"


def test_inv_capture_starts_unverified(state):
    inv = state.capture("INV", {
        "scope": "frontend",
        "source": "PR-0001",
        "check": {"kind": "test", "ref": "frontend/tests/order.spec"},
        "value": ["CPU", "GPU", "RAM", "STORAGE"],
    })
    assert inv["status"] == "unverified"


def test_an_invariant_is_verified_by_its_check_and_unverified_when_it_stops_resolving(tmp_path):
    """FR-0039: `verified` had no producer at all -- `backlog_types` said so in a comment.

    Measured before this existed: `state.transition("INV-0001", "verified")` raised "unknown item
    type 'INV'", because the type has no automaton, and no other kernel path wrote the field. So
    the vocabulary carried a status nothing could reach.

    BOTH DIRECTIONS IN ONE TEST, because they are one rule: the status is a measurement, so it
    follows the repository. The test file is written, the invariant verifies; the test is renamed
    out from under it, and the same command takes it back. A producer that only ever moved
    forwards would leave a `verified` invariant standing on a check that resolves to nothing.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))
    (tmp_path / "tests").mkdir()
    suite = tmp_path / "tests" / "test_rules.py"
    suite.write_text("def test_no_io_in_the_compounder():\n    pass\n", encoding="utf-8")
    inv = st.capture("INV", {"scope": "compounder/", "source": "PR-0001", "text": "pure, no I/O",
                             "check": {"kind": "test",
                                       "ref": "tests/test_rules.py::test_no_io_in_the_compounder"}})
    assert st.read_item(inv["id"])["status"] == "unverified"

    item, resolved, reason = st.record_invariant_verification(inv["id"])
    assert item["status"] == "verified", reason
    assert resolved is True, reason
    assert st.read_item(inv["id"])["status"] == "verified"

    suite.write_text("def test_something_else():\n    pass\n", encoding="utf-8")
    item, resolved, reason = st.record_invariant_verification(inv["id"])
    assert item["status"] == "unverified"
    assert resolved is False, reason
    assert "does not define" in reason, reason

    with pytest.raises(StateError):
        st.record_invariant_verification("PR-0001")


def test_an_item_may_carry_an_outline_area_but_not_a_third_level(state):
    """FR-0017: the outline is an ATTRIBUTE, on every captured type, and two levels deep.

    Three properties, and the third is the FR's condition rather than a nicety: an outline that
    can grow without limit is the over-fragmentation the user made a precondition of building
    this at all, so the depth is refused where it is written and not reported afterwards.

    The type spread is the second: `area` reaches every type `capture` creates
    (`UNIVERSAL_OPTIONAL_FIELDS`), because grouping is orthogonal to what an item is -- a per-type
    pair would have to be reopened for the next kit's backlog.
    """
    pr = state.capture("PR", dict(PR_FIELDS, area="Frontend/Checkout"))
    assert state.read_item(pr["id"])["area"] == "Frontend/Checkout"
    inv = state.capture("INV", {"scope": "frontend", "source": "PR-0001", "text": "no I/O",
                                "check": {"kind": "test", "ref": "t.py::t"},
                                "area": "Frontend"})
    assert state.read_item(inv["id"])["area"] == "Frontend"

    with pytest.raises(StateError) as refused:
        state.capture("PR", dict(PR_FIELDS, area="Frontend/Checkout/Payment"))
    assert "at most 2" in str(refused.value) and "3 levels deep" in str(refused.value)

    # ...and an item that names no area is untouched by any of it
    plain = state.capture("PR", dict(PR_FIELDS))
    assert "area" not in state.read_item(plain["id"])


def _inv_fields(scope):
    return {"scope": scope, "source": "PR-0001",
            "check": {"kind": "test", "ref": "tests/test_it.py::test_it"},
            "text": "the rule this invariant states"}


@pytest.mark.parametrize("several", [["frontend/", "backend/"], ["frontend/"],
                                     ("frontend/",), {"area": "frontend/"}, b"frontend/"])
def test_a_several_things_inv_scope_is_refused_at_capture_and_on_the_edit_path(state, several):
    """DEC-0043: `INV.scope` governs ONE area, and everything that is not one value is refused LOUDLY.

    BOTH DOORS INTO THE ACTIVE STORE, because a refusal at capture that the edit path undoes is no
    refusal: the same body arrives through `update` (H42's own note is that `capture` was the only
    productive writer, which is what made the silence total).

    THE ONE-ELEMENT LIST IS IN HERE ON PURPOSE and it is the case a count-based check would wave
    through: the readers cannot take a container apart at all, so `['frontend/']` reaches them as
    the text `"['frontend/']"` exactly like a two-element list does.

    SO IS `bytes`, AND IT IS THE CASE THE FIRST CUT OF THIS CONTRACT EXEMPTED beside `str`. Measured
    through the shipped edit path: the value was taken, the readers saw `b'frontend/'`,
    `gate_test_coverage` went rc 2 -> rc 0 and the validator said nothing -- worse than the list
    spelling, which at least the merge gate catches. `holds_one_thing` carries the reason no reader
    of such a field has a byte meaning.

    RED without `state._assert_single_value_fields`: every spelling captures with rc 0 and the
    project's own rule then guards nothing (H42's measured chain, `gate_test_coverage` rc 2 -> rc 0).
    """
    with pytest.raises(StateError, match="holds ONE thing"):
        state.capture("INV", _inv_fields(several))
    inv = state.capture("INV", _inv_fields("frontend/"))
    with pytest.raises(StateError, match="TWO INV items"):
        state.update_item(inv["id"], {"scope": several})
    assert state.read_item(inv["id"])["scope"] == "frontend/"


def test_the_archive_door_still_takes_a_record_the_active_door_refuses(state):
    """The boundary the refusal above deliberately stops at, measured instead of asserted in prose.

    NOT A CASE ANY SHIPPED COMMAND REACHES TODAY, and saying otherwise was this test's own first
    docstring: `V1_STATUS_MAPPING` produces eleven V2 types and `INV` is not one of them
    (`test_the_migration_can_produce_no_inv_so_the_archive_boundary_is_for_the_next_entry`), so no
    migration writes an `INV` anywhere. What this pins is the PLACEMENT for the next
    `SINGLE_VALUE_FIELDS` entry, whose type migration may produce: an archive-bound record is a
    protocol of what happened (DEC-0004), the unresolved ones are archived WITH THEIR REASON rather
    than stopping the run (DEC-0009), and a shape refusal there would stop the run while guarding
    nothing -- no reader of these fields scans the archive.
    """
    body = dict(_inv_fields(["frontend/", "backend/"]))
    body["legacy_fields"] = {"legacy_id": "INV-9", "unresolved": "V1 kept a list of areas here"}
    item = state.capture_migrated_unresolved("INV", body, 2026)
    assert item["scope"] == ["frontend/", "backend/"]
    assert not os.path.exists(state.active_path(item["id"]))


def test_the_migration_can_produce_no_inv_so_the_archive_boundary_is_for_the_next_entry():
    """The half of the placement argument that is a claim about the running tables, not about taste.

    The archive doors are exempt from the shape refusal, and the first version of that argument said
    a migrated `INV` would otherwise die there. No such record exists: a migration writes what
    `V1_STATUS_MAPPING` maps a V1 record to, and no row of it yields `INV`. Asserted from the table
    so the argument turns red the day a V1 row starts producing one -- which is exactly the day the
    exemption stops being theory.
    """
    produced = {v2_type for v2_type, _status, _archive in V1_STATUS_MAPPING.values()}
    assert produced, "the mapping table is empty -- this assertion would then mean nothing"
    assert "INV" not in produced, sorted(produced)


def test_update_rejects_created(state):
    item = make_pr(state)
    with pytest.raises(StateError, match="dedicated command"):
        state.update_item(item["id"], {"created": "1999-01-01T00:00:00"})


def test_hashed_key_with_unchanged_value_keeps_approval(state):
    item = make_pr(state)
    with state.lock:
        raw = state.read_item(item["id"])
        raw["approval_ref"] = "APR-0001"
        raw["status"] = "APPROVED"
        state._write_yaml_atomic(state.active_path(item["id"]), raw)
    updated = state.update_item(item["id"], {"goal": PR_FIELDS["goal"]})  # same value
    assert updated["approval_ref"] == "APR-0001"
    assert updated["revision"] == 1


# -- archive -------------------------------------------------------------------

def test_archive_refuses_non_terminal(state):
    item = make_pr(state)
    with pytest.raises(StateError, match="terminal"):
        state.archive(item["id"])


def test_archive_moves_terminal_item_deterministically(state):
    item = make_pr(state)
    state.transition(item["id"], "REJECTED")
    target = state.archive(item["id"])
    assert not os.path.exists(state.active_path(item["id"]))
    assert os.path.exists(target)
    year = yaml.safe_load(open(target, encoding="utf-8"))["closed_at"][:4]
    assert os.sep + os.path.join("archive", "PR", year, "PR-0001.yaml") in target


def test_archive_non_automaton_item_without_terminal_check(state):
    dec = state.capture("DEC", {
        "title": "t", "context": "c", "decision": "d",
        "consequences": "q", "source": "s", "work": "none",
    })
    target = state.archive(dec["id"])
    assert os.path.exists(target)
    assert not os.path.exists(state.active_path(dec["id"]))


# -- what a migration may write directly (SR-0004 / DEC-0004 bolt 2) -----------

def test_the_statuses_a_migration_may_write_are_the_ones_reachable_without_an_approval(state):
    """The archive path's approval bolt, measured as a WALK rather than as a subtraction.

    `migration_writable_statuses` subtracted the statuses an approval commits as a SET, which left
    every status FURTHER DOWN the same chain writable although it stands behind that approval just
    as much -- `BUG VERIFIED`, `CR APPLIED` and `EXP ANALYZED` on the shipped automata, each of
    them a status the V1 import then wrote into the archive with `approval_ref: null`.

    The expectation is walked here from the type's own edge set, asking
    `approvals.required_approval_kinds` -- the function `state.transition` itself consults -- which
    edges are gated. That is a different derivation from the one under test (which reads
    `APPROVAL_TRANSITIONS` directly), so this is a second opinion rather than a copy. The equality
    carries BOTH directions: a bolt that widened again fails on the left, and one that narrowed --
    dropping `PROC RETIRED`, `TSK CANCELLED`/`VALIDATED`, or the `FR` and `HYP` outcomes, none of
    which any approval touches -- fails on the right.
    """
    from kernel import approvals
    from kernel.backlog_types import AUTOMATA
    from kernel.state import migration_writable_statuses

    for item_type, automaton in AUTOMATA.items():
        reachable, frontier = {automaton.initial}, [automaton.initial]
        while frontier:
            current = frontier.pop()
            for source, target in automaton.allowed:
                if source != current or target in reachable:
                    continue
                if approvals.required_approval_kinds(item_type, source, target):
                    continue
                reachable.add(target)
                frontier.append(target)
        assert migration_writable_statuses(item_type) == reachable, item_type

    # ...and it has to REFUSE something, or the equality above is satisfied by "everything"
    behind = {item_type: automaton.states - migration_writable_statuses(item_type)
              for item_type, automaton in AUTOMATA.items()}
    direct = {(owner, edge[1]) for (owner, _kind), edge in approvals.APPROVAL_TRANSITIONS.items()}
    indirect = sorted((item_type, status) for item_type, states in behind.items()
                      for status in states if (item_type, status) not in direct)
    assert indirect, (
        "no status is refused except the approval edges' own targets, so this is the set "
        "subtraction again under a walk's name")
    # a type with no automaton has no status this kernel can walk to
    assert migration_writable_statuses("DEC") == frozenset()

    # NOT THE NEIGHBOURING GATE QUESTION. `approvals.approved_statuses` answers "which statuses
    # does an item hold BECAUSE it was approved" for the spawn gates, and it subtracts a terminal
    # no approval put there -- so its complement is a DIFFERENT set, and rewriting either into the
    # other would put a tombstone back within the import's reach.
    disagree = sorted(item_type for item_type, automaton in AUTOMATA.items()
                      if automaton.states - approvals.approved_statuses(item_type)
                      != migration_writable_statuses(item_type))
    assert disagree, (
        "the two answers now coincide for every type; one of them has been rewritten into the "
        "other and the reason each exists separately is gone")

    # THE RUNTIME CONTROL, because everything above reads maps: the gated edge really is refused by
    # the kernel with no approval in the store, and an ungated one really is walkable.
    blocked, walkable = make_pr(state), make_pr(state)
    assert "APPROVED" not in migration_writable_statuses("PR")
    with pytest.raises(StateError):
        state.transition(blocked["id"], "APPROVED")
    assert "REJECTED" in migration_writable_statuses("PR")
    state.transition(walkable["id"], "REJECTED")
    assert state.read_item(walkable["id"])["status"] == "REJECTED"


# -- generated index -----------------------------------------------------------

def test_index_marks_corrupt_items_visibly(state):
    make_pr(state)
    broken = os.path.join(state.active_dir("PR"), "PR-0999.yaml")
    with open(broken, "w", encoding="utf-8") as fh:
        fh.write(":: definitely not yaml ::\n\t[")
    state.generate_index()
    index = yaml.safe_load(open(os.path.join(state.root, "generated", "index.yaml"), encoding="utf-8"))
    corrupt_rows = [row for row in index["items"] if row.get("corrupt")]
    assert corrupt_rows and corrupt_rows[0]["id"] == "PR-0999"


def test_index_regenerated_by_every_operation(state):
    item = make_pr(state)
    index_path = os.path.join(state.root, "generated", "index.yaml")
    index = yaml.safe_load(open(index_path, encoding="utf-8"))
    assert [row["id"] for row in index["items"]] == [item["id"]]
    walk_to_status(state, item, "APPROVED")
    index = yaml.safe_load(open(index_path, encoding="utf-8"))
    # ROWS ARE SELECTED BY ID, not by position: walking to APPROVED mints an approval, and an APR
    # is an item type of its own (`ACTIVE_DIRS`), so it takes row 0 in the sorted index.
    rows = {row["id"]: row for row in index["items"]}
    assert rows[item["id"]]["status"] == "APPROVED"
    state.transition(item["id"], "SUPERSEDED")
    state.archive(item["id"])
    index = yaml.safe_load(open(index_path, encoding="utf-8"))
    assert item["id"] not in {row["id"] for row in index["items"]}  # archived items leave active


def test_read_item_names_remedy_for_missing(state):
    # The remedy points at the generated index by NAME and no longer by path: DEC-0024 keeps a
    # place inside the state directory out of every printed remedy, and `index.yaml` was one.
    with pytest.raises(StateError, match="generated index"):
        state.read_item("PR-0099")


# -- concurrency ---------------------------------------------------------------

def test_concurrent_captures_allocate_distinct_ids(tmp_path):
    root = str(tmp_path / "project_memory")
    os.makedirs(root)
    ids, errors = [], []

    def work():
        try:
            local = ProjectState(root)
            for _ in range(3):
                ids.append(local.capture("FR", {"title": "w", "request_text": "x"})["id"])
        except Exception as exc:  # pragma: no cover - diagnostic
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(ids) == 18
    assert len(set(ids)) == 18  # no duplicate ids under contention


# -- Evidence: the two fields a gate decides on (spec II.2) --------------------

def evidence_fields(**overrides):
    fields = {"kind": "test", "related": ["PR-0001"], "result": "pass",
              "summary": "full suite green",
              "artifact_refs": ["staging/TSK-0001/suite.log"]}
    fields.update(overrides)
    return fields


def test_evidence_capture_needs_a_verdict(state):
    """Without `result` the store cannot tell a passing run from a failing one, and the merge
    gate would open on the mere existence of a report."""
    make_pr(state)
    with pytest.raises(StateError, match="result"):
        state.capture("EVD", {k: v for k, v in evidence_fields().items() if k != "result"})


def test_evidence_carries_no_project_status(state):
    """Evidence never has a status of its own (II.2) — it is a record, not a workflow item."""
    make_pr(state)
    item = state.capture("EVD", evidence_fields())
    assert "status" not in item


@pytest.mark.parametrize("field", ["artifact_refs", "related"])
def test_evidence_capture_refuses_a_record_that_points_at_nothing(state, field):
    """The two list fields of an Evidence must NAME something; present-but-empty is not provided.

    `gate_git` opens a merge on this record and its refusal text presents `--artifact-ref` as the
    proof — so `python scripts/harness.py evidence --kind test --result pass --related PR-0001 --summary "looks
    fine"` used to be enough to open a merge on nothing but the word of whoever typed it
    (measured). `related` is the same shape one field over: an evidence bound to no item is filed
    under its own id and judges no delivery at all, while looking exactly like a verdict.

    Both directions are asserted: the counter-case at the end is what keeps this from being
    satisfiable by refusing every Evidence.
    """
    make_pr(state)
    with pytest.raises(StateError, match="must name something"):
        state.capture("EVD", evidence_fields(**{field: []}))
    assert state.capture("EVD", evidence_fields())["id"] == "EVD-0001"


@pytest.mark.parametrize("field,value", [("result", "passed"), ("kind", "smoke")])
def test_evidence_vocabulary_is_closed_at_capture(state, field, value):
    """A value outside the vocabulary would not FAIL the merge gate, it would skip it: an unknown
    result is not a fail, an unknown kind is not QA."""
    make_pr(state)
    with pytest.raises(StateError, match="unknown EVD"):
        state.capture("EVD", evidence_fields(**{field: value}))


@pytest.mark.parametrize("changes", [
    {"result": "pass"},            # the verdict itself: a FAIL turned into a PASS in place
    {"related": ["PR-0002"]},      # the binding: this verdict now covers a different item
    {"summary": "actually fine"},  # the prose the reader is left with
    {"result": "passed"},          # even a value the vocabulary would refuse anyway
])
def test_no_field_of_an_evidence_can_be_edited(state, changes):
    """A record is superseded, never corrected — the whole item, not just the two gate inputs.

    Measured before the refusal existed: `update_item(evd, {"result": "pass"})` reopened a merge
    `gate_git` had closed and `{"related": [...]}` moved a failing verdict onto another item, in
    both cases without a new item and without a trace in the store. That is what makes the gate's
    own sentence ("retired by recording the re-run, never by editing it") true rather than a
    wish, and it is why the rule is the TYPE's, not a list of protected fields: any field of a
    record that changes makes the record's claim false.
    """
    make_pr(state)
    state.capture("PR", dict(PR_FIELDS, title="Second"))
    item = state.capture("EVD", evidence_fields(result="fail"))
    with pytest.raises(StateError, match="record of something that already happened"):
        state.update_item(item["id"], changes)
    assert state.read_item(item["id"])["result"] == "fail"


def test_an_edit_cannot_rebind_a_task_to_an_origin_that_does_not_exist(state):
    """The reference check runs on the edit path for the reason the vocabulary check does.

    `derives_from` is frozen once a task leaves DRAFT (TSK_PLAN_FIELDS), so the window this closes
    is a DRAFT task: refusing a phantom origin at capture and then accepting it from an edit is
    not refusing it at all, and the dispatch gate resolves `acceptance_refs` against exactly that
    field.
    """
    pr = make_pr(state)
    task = state.capture("TSK", {
        "product_requirement": pr["id"], "root_revision": 1, "derives_from": [pr["id"]],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["src/**"],
        "forbidden_scope": [], "expected_outputs": ["src/x.py"], "dependencies": []})
    with pytest.raises(StateError, match="derives_from PR-0099 does not exist"):
        state.update_item(task["id"], {"derives_from": ["PR-0099"]})
    with pytest.raises(StateError, match="not an item id"):
        state.update_item(task["id"], {"derives_from": ["the login epic"]})
    assert state.read_item(task["id"])["derives_from"] == [pr["id"]]


def test_evidence_related_must_name_items_that_exist(state):
    """Evidence bound to a phantom id covers no work while looking exactly like proof."""
    make_pr(state)
    with pytest.raises(StateError, match="related PR-0099 does not exist"):
        state.capture("EVD", evidence_fields(related=["PR-0099"]))
    with pytest.raises(StateError, match="not an item id"):
        state.capture("EVD", evidence_fields(related=["the nightly run"]))


def _contract_payload(item_type, bindings):
    """A payload that satisfies `item_type`'s contract, with its bindings set as given.

    Built from `REQUIRED_FIELDS` so a new field cannot make this test silently stop reaching
    the check it is about, and from `_CLOSED_VOCABULARY` for the fields the kernel judges
    against a fixed vocabulary a few lines earlier -- both read from the kernel rather than
    retyped, so the fixture cannot drift from the contract it is a fixture for.

    THE REQUESTED BINDINGS ARE SET WHETHER OR NOT THE CONTRACT REQUIRES THEM. `REQUIRED_FIELDS`
    cannot mention an optional field, and two of the graph's bindings are optional by spec II.2
    (`PROC.derives_from`, `FR.related_pr`) -- built from the required half alone, this payload
    simply left them out, and the caller's `pytest.raises` then failed with DID NOT RAISE on a
    capture that was never asked to bind anything. The payload has to carry what the caller is
    testing, not only what the type may not omit.
    """
    payload = {}
    for field in REQUIRED_FIELDS[item_type]:
        allowed = _CLOSED_VOCABULARY.get((item_type, field))
        payload[field] = sorted(allowed[0])[0] if allowed else bindings.get(field, "x")
    for field, value in bindings.items():
        payload.setdefault(field, value)
    # ...AND THE CONDITIONAL HALF OF THE SAME CONTRACT: a value out of a closed vocabulary can owe
    # a companion field, and picking the alphabetically first member is how this fixture met one.
    # `BLOCKED_RESULT` owes the sentence saying what stopped the run (FR-0082,
    # `state.capture_preflight`), so the payload carries it -- otherwise this test stops at that
    # refusal and never reaches the binding check it is about. Both names come from the kernel,
    # like everything else here.
    if payload.get(EVIDENCE_RESULT_FIELD) == BLOCKED_RESULT:
        payload[BLOCKED_REASON_FIELD] = "the run did not happen in this fixture"
    # ...and a field the contract declares as a DATE has to BE one (DEC-0064), or every capture
    # here stops at that refusal instead of the one the caller is testing. Read from `DATE_FIELDS`,
    # like the vocabulary above, so a second date field arrives satisfied rather than as the next
    # surprise.
    for field in DATE_FIELDS.get(item_type, ()):
        if field in payload:
            payload[field] = "2026-10-01"
    return payload


def test_a_binding_a_field_contract_declares_is_checked_for_every_type_that_has_one(state):
    """The write-path check reads `PARENT_FIELDS`, so it cannot fall behind the graph.

    It used to carry its own two-name list (`TSK.derives_from`, `EVD.related`) while the
    reference graph in `report` carried a second one, and the two drifted apart around `SR`:
    its REQUIRED `derives_from` was in neither, so an `SR` could be captured against a phantom
    parent AND the Evidence judging it then resolved to no root.

    Asserted over the whole map rather than over the types that carry a binding today, because
    "a type nobody added to the list" is precisely the defect. Both refusals are asserted --
    a free-text binding and one that parses but names nothing -- and the counter-assertion is
    the same payload with every binding pointed at a real item: it captures, so the refusals
    above cannot be this fixture failing some other part of the contract.

    The types this write path never sees are excluded BY CAPTURE'S OWN CONDITION -- `capture`
    refuses everything outside `REQUIRED_FIELDS` (ARC/WFR/DSN come from the freeze path, which
    validates against their schemas instead) -- and the exclusion is measured rather than
    assumed: each one is offered to `capture` and has to be refused for that reason. A skip
    list would otherwise be the place a type quietly stops being checked.
    """
    root = make_pr(state)
    for item_type in sorted(set(PARENT_FIELDS) - set(REQUIRED_FIELDS)):
        with pytest.raises(StateError, match="capture does not handle type"):
            state.capture(item_type, {})
    for item_type, fields in sorted(PARENT_FIELDS.items()):
        if item_type not in REQUIRED_FIELDS:
            continue
        for field in fields:
            others = {other: root["id"] for other in fields if other != field}
            with pytest.raises(StateError, match="%s PR-0099 does not exist" % field):
                state.capture(item_type,
                              _contract_payload(item_type, dict(others, **{field: "PR-0099"})))
            with pytest.raises(StateError, match="not an item id"):
                state.capture(item_type,
                              _contract_payload(item_type,
                                                dict(others, **{field: "the login epic"})))
        captured = state.capture(item_type,
                                 _contract_payload(item_type, {f: root["id"] for f in fields}))
        assert captured["id"].startswith(item_type + "-"), item_type


def test_read_anywhere_follows_an_item_into_the_archive(state):
    """The walk the merge gate needs: a task is archived at VALIDATED, before the merge it
    cleared, so a reader that stops at active/ loses the binding at the finish line."""
    pr = make_pr(state)
    state.transition(pr["id"], "REJECTED")
    state.archive(pr["id"])
    item, archived = state.read_anywhere(pr["id"])
    assert archived and item["id"] == pr["id"]
    assert state.read_anywhere("PR-0099") == (None, False)
    assert state.read_anywhere("not an id") == (None, False)


def test_a_write_that_fails_leaves_no_temp_file_in_the_item_directory(state):
    """R-g: `_write_yaml_atomic` opened `<ID>.yaml.tmp-<pid>` and left it there when the dump raised.

    The leftover is not inert. It sits in `procedures/active/` (measured there), it is read by
    `migrate.state_fingerprint` -- so a plan digest becomes a statement about a file nobody wrote
    on purpose -- and by every directory reader in `report`. `os.replace` still provides the
    atomicity; this is about the FAILING write leaving the directory as it found it.

    Driven with a payload `yaml.safe_dump` cannot represent, because that is a failure the dump
    itself raises after the temp file is already open -- the shape the defect needs.
    """
    make_pr(state)
    directory = state.active_dir("PR")
    before = sorted(os.listdir(directory))
    with pytest.raises(Exception):
        state.capture("DEC", {"title": object(), "context": "c", "decision": "d",
                              "consequences": "q", "source": "s", "work": "none"})
    for item_dir in (directory, state.active_dir("DEC")):
        if not os.path.isdir(item_dir):
            continue
        leftovers = [name for name in os.listdir(item_dir) if ".tmp-" in name]
        assert not leftovers, leftovers
    assert sorted(os.listdir(directory)) == before


# -- what the archive path's second bolt really is (SR-0002 divergence, R-a, R-i) ------------------


def _archive_bound_rows():
    """[(v1 type, v1 status, v2 type, v2 status)] for every row spec II.10 marks as FINISHED."""
    from kernel.backlog_types import V1_STATUS_MAPPING
    return sorted((v1_type, v1_status, v2_type, v2_status)
                  for (v1_type, v1_status), (v2_type, v2_status, finished)
                  in V1_STATUS_MAPPING.items() if finished)


def test_the_archive_paths_second_bolt_is_not_the_terminal_check_sr_0002_asks_for():
    """The divergence `capture_migrated_archive` REPORTS, measured in both directions.

    SR-0002 says the exemption holds "nur bei Endzustaenden" and SR-0004 "dessen abgebildeter
    Status ein Endzustand seines Automaten ist". The code checks something else -- the V1 table's
    `archive_candidate` plus approval reachability -- and this measures that the two rules really
    are different rather than two wordings of one, so the divergence the docstring reports is a
    fact about the shipped tables and not a caution.

    BOTH DIRECTIONS have to be non-empty or "different" would be an overstatement:
      * the code ACCEPTS rows whose mapped status is no terminal (`TSK DONE` is the row SR-0004's
        own measurement is about: 418 field records stand there);
      * the code REFUSES rows whose mapped status IS a terminal (`PR ACCEPTED`, behind the
        acceptance approval).

    RED as a report if the code is ever changed to the terminal check without the SRs and the
    docstring moving with it: the first list empties and this says so.
    """
    from kernel.backlog_types import AUTOMATA
    from kernel.state import migration_archives

    accepted_non_terminal, refused_terminal = [], []
    for v1_type, v1_status, v2_type, v2_status in _archive_bound_rows():
        automaton = AUTOMATA.get(v2_type)
        if automaton is None:
            continue
        terminal = v2_status in automaton.terminals
        if migration_archives(v2_type, v1_type, v1_status) and not terminal:
            accepted_non_terminal.append((v1_type, v1_status, v2_status))
        if not migration_archives(v2_type, v1_type, v1_status) and terminal:
            refused_terminal.append((v1_type, v1_status, v2_status))
    assert ("TSK", "DONE", "DONE") in accepted_non_terminal, accepted_non_terminal
    assert refused_terminal, (
        "no archive-bound row with a terminal status is refused, so the two rules cannot be told "
        "apart on the shipped tables and the reported divergence would be an overstatement")
    # ...and it is the RUNNING rule, not only the table: the writer's own judge answers for a
    # status that is not a terminal of its automaton.
    from kernel.state import migration_archive_status
    assert migration_archive_status("TSK", "TSK", "DONE") == "DONE"
    assert "DONE" not in AUTOMATA["TSK"].terminals


def test_which_archive_bound_rows_rest_on_an_absent_approval_edge():
    """R-a: the archive path reads an ABSENT approval edge as permission -- the hole, measured.

    `migration_writable_statuses` asks `approvals.APPROVAL_TRANSITIONS` which edges a user approval
    commits. A type with no row there has no gated edge, so every status of it is writable -- and a
    missing row means two different things that nothing in this harness can tell apart: "decided,
    no approval is needed here" and "the approval kind was never built".
    `approvals.required_approval_kinds` records `SR PROPOSED -> ACCEPTED` as "Reported, not
    bridged", i.e. the second; so a V1 `SR DONE` record is archived at `ACCEPTED` with
    `approval_ref: null`, which is the same shape as the `CR APPLIED` defect that walk was written
    against, produced by an absence rather than by a subtraction.

    This is a TRIPWIRE over the hole, not a fix: it derives today's set from the running maps and
    fails in both directions. Adding an `("SR", <kind>)` row -- the fix -- takes `SR` out of the
    set and turns it red; adding an archive-bound row for another type with no approval kind puts
    one in and turns it red. Of the four types below, `TSK` is a documented decision (no kind's
    manifest describes a task's progress) and `SR` is the reported gap; `FR` and `HYP` are in
    neither statement, which is itself part of what this records.
    """
    from kernel import approvals
    from kernel.state import migration_archives, migration_writable_statuses

    unguarded = {item_type for (item_type, _kind) in approvals.APPROVAL_TRANSITIONS}
    resting = sorted({(v1_type, v1_status, v2_type) for v1_type, v1_status, v2_type, _v2s
                      in _archive_bound_rows()
                      if migration_archives(v2_type, v1_type, v1_status)
                      and v2_type not in unguarded})
    assert {v2_type for _t, _s, v2_type in resting} == {"SR", "TSK", "FR", "HYP"}, resting
    assert ("SR", "DONE", "SR") in resting, resting
    # the shape the hole produces, read off the kernel's own maps rather than described
    assert "ACCEPTED" in migration_writable_statuses("SR")
    assert not approvals.required_approval_kinds("SR", "PROPOSED", "ACCEPTED")


def _task_at(state, status):
    """A fresh TSK walked to `status` along its own edges -- the origin really exists.

    Through `drive_task_to`, so the walk past LEASED/IN_PROGRESS goes through the real lease
    lifecycle rather than the bare transition DEC-0038 now refuses.
    """
    pr = make_pr(state)
    task = state.capture("TSK", {
        "product_requirement": pr["id"], "root_revision": 1, "derives_from": pr["id"],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["src/"],
        "forbidden_scope": ["secrets/"], "expected_outputs": ["src/x.py"], "dependencies": [],
    })
    return drive_task_to(state, task["id"], status)["id"]


def test_the_migration_write_set_reads_three_of_the_four_edge_guards(state):
    """R-i: which of `_transition_locked`'s four guards the write set reads, measured one by one.

    THE RETRY GUARD IS READ, and measuring that needs an automaton in which the retry edge is the
    ONLY way to its target -- on the shipped task automaton `READY` is reachable from `DRAFT` too,
    so the set does not change and a set comparison would prove nothing. RED without
    `RETRY_APPROVAL_EDGE` being read by the walk: `READY` comes back writable although the only
    edge into it is the one `transition` refuses without an approved retry.

    THE CONFIRMING-EVIDENCE GUARD IS NOT READ, and what that costs today is nothing -- which is a
    different sentence from "it is guarded" and is the one that is true. `CONFIRMING_EVIDENCE`
    covers `BUG` alone, its confirming edge ends at `VERIFIED`, and `VERIFIED` already sits behind
    the `BUG` scope approval, so the approval bolt excludes it first. This measures exactly that:
    for every type the evidence rule really enforces, the confirming target is out of the write
    set for SOME reason. Add a type to `CONFIRMING_EVIDENCE` whose confirming target is reachable
    and this goes red -- which is the moment the unread guard turns into a status that escapes.
    """
    from kernel import approvals
    from kernel import state as state_module
    from kernel.backlog_types import AUTOMATA, _Automaton, confirming_edge
    from kernel.state import CONFIRMING_EVIDENCE, RETRY_APPROVAL_EDGE, migration_writable_statuses

    owner, source, target = RETRY_APPROVAL_EDGE
    only_through_the_retry = _Automaton(
        chain=("DRAFT", source), terminals=("CANCELLED",),
        terminal_from={"CANCELLED": ("DRAFT", source)},
        extra_edges=((source, target),), extra_states=(target,))
    import pytest as _pytest
    monkey = _pytest.MonkeyPatch()
    try:
        monkey.setattr(state_module, "AUTOMATA", dict(AUTOMATA, **{owner: only_through_the_retry}))
        reachable = migration_writable_statuses(owner)
    finally:
        monkey.undo()
    assert target not in reachable, (
        "%s is writable although the only edge into it is %s, which `transition` refuses without "
        "an approved retry" % (target, " -> ".join(RETRY_APPROVAL_EDGE[1:])))
    assert {"DRAFT", source, "CANCELLED"} == set(reachable), reachable

    # THE FOURTH GUARD: not read, and today it does not have to be. What is measured is the
    # CONSEQUENCE, not the reading -- a confirming target that the write set can reach would be a
    # status the import writes while claiming a confirmation nobody recorded.
    assert CONFIRMING_EVIDENCE, "no type demands confirming evidence, so this measures nothing"
    for item_type in CONFIRMING_EVIDENCE:
        edge = confirming_edge(item_type)
        assert edge is not None, item_type
        assert edge[1] not in migration_writable_statuses(item_type), (
            "%s %s is writable by the import although reaching it needs the %r Evidence "
            "`CONFIRMING_EVIDENCE` demands, and this walk does not read that guard -- so the "
            "import would write a confirmation nobody recorded"
            % (item_type, edge[1], CONFIRMING_EVIDENCE[item_type]))
    # ...and the reason it is out is the APPROVAL bolt, which is what makes the sentence above a
    # measurement of coincidence rather than of coverage.
    for item_type in CONFIRMING_EVIDENCE:
        assert any(owner == item_type for (owner, _kind) in approvals.APPROVAL_TRANSITIONS), (
            "%s has no approval edge either, so nothing excludes its confirming target and the "
            "unread guard has become a hole" % item_type)

    # THE TWO READERS LOOK AT THE SAME EDGE, and that is measured off the RUNNING transition path
    # rather than asserted about the constant: every edge out of `FAILED` is attempted on a fresh
    # task, and the one the kernel refuses for a missing retry approval has to be exactly the one
    # the walk above treated as gated. Point the datum somewhere else and both ends move together
    # or this fails.
    refused_for_retry = set()
    for _from, _to in sorted(AUTOMATA[owner].allowed):
        if _from != source:
            continue
        task = _task_at(state, source)
        try:
            state.transition(task, _to)
        except TransitionError as exc:
            if "approved retry" in str(exc):
                refused_for_retry.add((_from, _to))
    assert refused_for_retry == {(source, target)}, refused_for_retry


# -- the honesty sentence of a blocked verdict (FR-0082) and a walkable remedy (BUG-0089) -------

EVD_FIELDS = {
    "kind": "test",
    "related": ["PR-0001"],
    "summary": "the e2e suite",
    "artifact_refs": ["staging/TSK-0001/run.log"],
}


def test_a_blocked_evidence_owes_its_sentence_and_the_sentence_owes_its_verdict(state):
    """FR-0082, both directions of one pair.

    FORWARD: a `blocked` with no sentence is refused, because without it the store holds a red
    verdict a later reader cannot tell from a checked one -- the exact failure the wishlist section
    names ("sonst liest der naechste `blocked` als geprueste Tatsache", section 7).

    BACKWARD, and this is the half that keeps the field honest rather than decorative: the sentence
    under any other result is refused too, because a record that says what stopped the run while
    also reporting the run as done says two things.

    RED WITHOUT THE FIX: with the pair check removed from `capture_preflight` the first capture
    succeeds and the store holds a `blocked` explaining nothing.
    """
    from kernel.backlog_types import BLOCKED_REASON_FIELD, BLOCKED_RESULT

    state.capture("PR", dict(PR_FIELDS))       # the item the Evidence is about has to exist
    with pytest.raises(StateError) as refusal:
        state.capture("EVD", dict(EVD_FIELDS, result=BLOCKED_RESULT))
    assert BLOCKED_REASON_FIELD in str(refusal.value)

    with pytest.raises(StateError):
        state.capture("EVD", dict(EVD_FIELDS, result="pass",
                                  **{BLOCKED_REASON_FIELD: "no browser"}))

    recorded = state.capture("EVD", dict(EVD_FIELDS, result=BLOCKED_RESULT,
                                         **{BLOCKED_REASON_FIELD: "no Chromium on this runner"}))
    assert recorded[BLOCKED_REASON_FIELD] == "no Chromium on this runner"
    # ...and a whitespace-only sentence is no sentence
    with pytest.raises(StateError):
        state.capture("EVD", dict(EVD_FIELDS, result=BLOCKED_RESULT,
                                  **{BLOCKED_REASON_FIELD: "   "}))


def test_a_frozen_field_refusal_names_only_walkable_transitions(state):
    """BUG-0089: the remedy of a frozen work-order field is read off AUTOMATA at refusal time.

    THE PLANTED STATE IS THE MEASURED ONE: a `TSK` in READY, whose automaton has no edge into DRAFT
    from anywhere -- so the remedy must not name DRAFT as somewhere to transition to. Measured
    2026-09-02 on TSK-0107: the refusal said "transition the task back to DRAFT", and `transition
    TSK-0107 DRAFT` then answered "illegal transition TSK: READY -> DRAFT".

    RED WITHOUT THE FIX: the old refusal text contains the string this asserts against.

    THE OTHER END -- that the derivation really READS the table rather than being a rule against
    one word -- is `_replanning_remedy` fed a status the same automaton CAN leave towards its
    initial one, which the shipped `TSK` automaton has no example of; the route function's own
    both-ends test covers it per automaton
    (`tools/test_backlog_types.py::test_the_replanning_route_names_only_edges_the_automaton_has`).
    """
    from kernel.backlog_types import AUTOMATA
    from kernel.state import _replanning_remedy

    task = _ready_task(state)
    with pytest.raises(StateError) as refusal:
        state.update_item(task["id"], {"expected_outputs": ["something else"]})
    remedy = str(refusal.value).split("Remedy:", 1)[1]
    assert "DRAFT" not in remedy, remedy
    for target in ("CANCELLED",):
        assert target in remedy
    assert ("READY", "DRAFT") not in AUTOMATA["TSK"].allowed

    # a status with neither route left says so instead of inventing one
    assert "cannot be re-planned from here" in _replanning_remedy(
        "TSK-0001", "TSK", "VALIDATED", "DRAFT")


def test_the_update_path_reads_a_date_field_exactly_as_capture_does(state):
    """The edit verb is a writer too, so it owes the same date rule (rework 2).

    MEASURED BEFORE THE FIX, through the shipped CLI as a process: `update MST-0001
    {"due": "Weihnachten"}` was rc 0 and stored; `{"due": "20261225"}` put a second spelling of a
    day beside the `2026-12-25` the store already held; `{"due": null}` put back exactly the value
    the capture path had just been taught to refuse. One rule with two doors is no rule.

    RED WITHOUT THE FIX on every line below. `_dates_in` is ONE function called by both verbs, so
    this cannot drift back into two readings.

    THE LAST ASSERTION IS THE POINT OF NORMALISING IN THE EDIT PATH RATHER THAN ONLY REFUSING
    THERE: re-spelling the day the item already carries is not a change, so it must not bump a
    revision or invalidate anything.
    """
    make_pr(state)
    milestone = state.capture("MST", dict(MST_FIELDS, due="2026-12-25"))
    for unreadable in ("Weihnachten", None, "2026-13-01", ""):
        with pytest.raises(StateError, match="not a calendar date"):
            state.update_item(milestone["id"], {"due": unreadable})
        assert state.read_item(milestone["id"])["due"] == "2026-12-25", (
            "a refused update must leave the record alone")

    from datetime import date as _date
    try:
        _date.fromisoformat("20261225")
    except ValueError:
        return                      # this interpreter does not read the compact form -- see H147
    before = state.read_item(milestone["id"])
    updated = state.update_item(milestone["id"], {"due": "20261225"})
    assert updated["due"] == "2026-12-25"
    assert state.read_item(milestone["id"])["due"] == "2026-12-25"
    assert updated["revision"] == before["revision"], (
        "re-spelling the same day is not a change, so nothing may move")


def _ready_task(state):
    """A TSK in READY, walked the sanctioned way (root approval, then the chain edge)."""
    from conftest import approve
    from kernel import dispatch

    root = state.capture("PR", dict(PR_FIELDS))
    approve(state, root["id"], "scope")
    task = dispatch.create_task(state, {
        "product_requirement": root["id"], "derives_from": root["id"],
        "type": "implementation", "assigned_role": "backend-developer",
        "acceptance_refs": ["AC-1"], "required_inputs": [], "allowed_scope": ["src/"],
        "forbidden_scope": ["secrets/"], "expected_outputs": ["src/x.py"], "dependencies": []})
    state.transition(task["id"], "READY")
    return task


# -- the milestone type at the write path (DEC-0064) --------------------------------------------

MST_FIELDS = {"title": "Release 2026.10", "due": "2026-10-01", "derives_from": ["PR-0001"]}


def test_every_type_with_an_automaton_is_captured_with_its_initial_status(state):
    """`capture` stamps the initial status for EVERY type that has an automaton -- derived, not listed.

    THE DEFECT THIS HOLDS, measured before the fix: `state._AUTOMATON_TYPES` was a hand-written
    tuple of ten names that happened to equal `AUTOMATA`'s keys. Adding an eleventh type (`MST`)
    left the item with no `status` key at all -- `capture` wrote it, `archive` then read it as
    non-terminal, and nothing raised anywhere. RED WITHOUT THE FIX on the `MST` row below.

    Over the whole map rather than over the new type, because "a type nobody added to the tuple" is
    exactly the defect; the payload of each type is built from its own contract, so a type added to
    `AUTOMATA` without a capture contract is skipped for a REASON the assertion names.
    """
    from kernel.backlog_types import AUTOMATA, initial_status

    make_pr(state)                       # the parent every binding below resolves against
    for item_type in sorted(AUTOMATA):
        if item_type not in REQUIRED_FIELDS:
            continue                     # not a capturable type -- the freeze path owns those
        payload = _contract_payload(item_type, {})
        for field in PARENT_FIELDS.get(item_type, ()):
            payload[field] = "PR-0001"
        captured = state.capture(item_type, payload)
        assert captured["status"] == initial_status(item_type), item_type


def test_a_date_field_that_is_not_a_date_is_refused_at_capture(state):
    """DEC-0064 (3): `due` is read by `date.fromisoformat` or the capture is refused.

    RED WITHOUT THE FIX: with the `DATE_FIELDS` loop removed from `capture_preflight`, `due:
    "Oktober"` is stored, and every view of that milestone then shows "no date" for a record
    nothing can repair -- an item is practically immutable.

    THE COUNTER-ASSERTION IS THE SECOND HALF: a real ISO date captures, so this cannot pass by the
    type being unusable.
    """
    make_pr(state)
    # `None` among them, and it is the one the first cut let through: the required-field loop only
    # refuses an ABSENT key, so `due: None` was stored on a type nothing can edit afterwards, and
    # every view of that milestone then reads "no date" for good.
    for unreadable in ("Oktober", "2026-13-01", "2026-10-01T00:00", "", None):
        with pytest.raises(StateError, match="not a calendar date"):
            state.capture("MST", dict(MST_FIELDS, due=unreadable))
    milestone = state.capture("MST", dict(MST_FIELDS))
    assert milestone["status"] == "PLANNED" and milestone["due"] == "2026-10-01"
    # ...AND ONE DAY HAS ONE SPELLING IN THE STORE. `date.fromisoformat` accepts more than one
    # form, so without the normalisation two milestones of the same day sort against each other
    # lexically for every reader that orders by `due`.
    # ASKED OF THE INTERPRETER FIRST, because WHICH forms it accepts has widened across versions
    # (`20261001` is refused on 3.10 and read on 3.11+) -- that half is not ours and is named as
    # `H147`. Where the form is refused there is nothing to normalise and the capture is refused,
    # which is the other assertion above.
    from datetime import date as _date
    try:
        _date.fromisoformat("20261001")
    except ValueError:
        return
    compact = state.capture("MST", dict(MST_FIELDS, due="20261001"))
    assert compact["due"] == "2026-10-01"
    assert state.read_item(compact["id"])["due"] == "2026-10-01"
    # ...and the two ways of not reaching it are open while it is ahead, and closed once it is not
    state.transition(milestone["id"], "REACHED")
    with pytest.raises(TransitionError):
        state.transition(milestone["id"], "MISSED")


# -- BUG-0090/DEC-0071 and FR-0087/DEC-0073 ------------------------------------

def test_a_declared_regression_run_confirms_the_bug_it_names(tmp_path):
    """BUG-0090, measured against the running kernel and not against a docstring.

    THE DEFECT: `state._assert_confirmed` routed through the DELIVERY reading of the evidence
    store, which drops every passing Evidence that declares `run_scope: selection` (DEC-0061 (b),
    written for the merge). So a BUG at FIXED with an honest regression record was refused with
    "there is none", while the SAME run recorded WITHOUT the declaration walked -- the record that
    said more about itself was the one punished, and the refusal's own remedy asks for exactly the
    run it dropped.

    BOTH HALVES ARE ASSERTED HERE, because the fix is a split and not a removal: the edge walks on
    the declared selection, and the merge reading of the very same record is unchanged.
    """
    from kernel import report

    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    goal = state.capture("PR", dict(PR_FIELDS))
    bug = state.capture("BUG", {"title": "a defect", "related_pr": goal["id"], "observed": "o",
                                "expected": "e", "repro": "r", "severity": "low",
                                "acceptance_criteria": [{"id": "AC-1", "text": "t"}]})
    walk_to_status(state, bug, "FIXED")
    state.capture("EVD", {"kind": "test", "result": "pass", "related": [bug["id"]],
                          "summary": "the regression run", "artifact_refs": ["staging/x/run.log"],
                          "run_command": "python -m pytest tools/test_x.py -k the_defect",
                          "run_scope": "selection"})

    assert report.qa_verdicts(state, bug["id"]) == {}, (
        "the merge reading changed -- a passing selection must still open nothing")
    assert state.transition(bug["id"], "VERIFIED")["status"] == "VERIFIED"


def test_the_kernel_hands_out_the_hole_number_and_never_the_caller(tmp_path):
    """FR-0087 (b): ids by the kernel, never reserved by hand.

    The defect this ends was measured in generation 3: the lead handed H numbers out per stream by
    message, and one stream's verifier found two of them in no frozen item at all. So a caller says
    THAT an item is a hole and the kernel says WHICH number -- a body carrying the field is refused
    the way a body carrying `status` is, and the allocation is a max-scan over the store, so a
    closed hole's number is never handed out twice.
    """
    from kernel.backlog_types import HOLE_NUMBER_FIELD

    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    state.capture("PR", dict(PR_FIELDS))
    body = {"title": "a gap", "related_pr": "PR-0001", "observed": "measured", "expected": "closed",
            "repro": "run it", "severity": "low",
            "acceptance_criteria": [{"id": "AC-1", "text": "closed"}]}

    assert state.next_hole_number() == "H1"
    first = state.capture("BUG", dict(body), hole=True)
    second = state.capture("BUG", dict(body, title="another gap"), hole=True)
    assert (first[HOLE_NUMBER_FIELD], second[HOLE_NUMBER_FIELD]) == ("H1", "H2")

    plain = state.capture("BUG", dict(body, title="an ordinary defect"))
    assert HOLE_NUMBER_FIELD not in plain, "an ordinary defect was stamped as a hole"

    with pytest.raises(StateError, match=HOLE_NUMBER_FIELD):
        state.capture("BUG", dict(body, **{HOLE_NUMBER_FIELD: "H99"}))

    # ...and an archived hole keeps its number out of circulation
    state.transition(first["id"], "TRIAGED")
    state.transition(first["id"], "REJECTED")
    state.archive(first["id"])
    assert state.next_hole_number() == "H3"


def test_the_migration_door_writes_a_hole_and_refuses_everything_else(tmp_path):
    """DEC-0073 (3a): the door, and the four bolts on it.

    It exists because `migration_writable_statuses("BUG")` does not reach VERIFIED -- the scope
    approval stands in front of it -- so the closed half of the hole list could otherwise only be
    migrated with one user-minted approval and one test Evidence per entry.

    WHAT IT WIDENS is written down as `H154` with its limit and is not asserted away here; what is
    asserted is that it is BOUNDED: only a body carrying a hole number, only a status the automaton
    has, terminal into the archive and non-terminal into `active/`, the status-dependent duty
    enforced, and an existing number returned rather than overwritten.
    """
    from kernel.backlog_types import HOLE_LIMIT_FIELD, HOLE_NUMBER_FIELD
    from kernel.lock import ext_path

    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    state.capture("PR", dict(PR_FIELDS))
    body = {"title": "a closed gap", "related_pr": "PR-0001", "observed": "measured",
            "severity": "low", HOLE_NUMBER_FIELD: "H1"}

    closed = state.capture_migrated_hole(dict(body), "VERIFIED")
    assert closed["status"] == "VERIFIED"
    assert os.path.isfile(state.archive_path(closed["id"], int(closed["created"][:4]))), (
        "a terminal hole was not written into the archive")
    assert not os.path.exists(ext_path(state.active_path(closed["id"])))

    open_hole = state.capture_migrated_hole(
        dict(body, title="an open gap", **{HOLE_NUMBER_FIELD: "H2",
                                           HOLE_LIMIT_FIELD: "the lead reads it"}), "TRIAGED")
    assert os.path.isfile(ext_path(state.active_path(open_hole["id"]))), (
        "an OPEN hole was hidden in the archive, where no validator judges it")

    # a body with no hole number is not this door's business at all
    with pytest.raises(StateError, match="holes only"):
        state.capture_migrated_hole({"title": "x", "related_pr": "PR-0001"}, "TRIAGED")
    # ...nor is a status the automaton does not have
    with pytest.raises(StateError, match="no status of BUG"):
        state.capture_migrated_hole(dict(body, **{HOLE_NUMBER_FIELD: "H3"}), "SHIPPED")
    # ...and an accepted exception owes what limits instead
    with pytest.raises(StateError, match="takes the place of the protection"):
        state.capture_migrated_hole(dict(body, **{HOLE_NUMBER_FIELD: "H4"}), "ACCEPTED_EXCEPTION")

    # a number already in the store is returned, never written a second time
    again = state.capture_migrated_hole(dict(body, title="a different text"), "VERIFIED")
    assert again["id"] == closed["id"] and again["title"] == closed["title"]
    assert state.next_hole_number() == "H3"


def test_only_the_type_a_hole_is_can_be_captured_as_one(tmp_path):
    """The derivation behind the refusal, held at both ends.

    `backlog_types.hole_type()` reads the contract -- exactly one type declares the hole number
    field, because that is what "this type can carry one" means -- and `state.capture` refuses
    every other type from that one answer. A list here would be the second spelling the round-2
    verification found in the CLI.
    """
    import kernel.backlog_types as bt
    from kernel.backlog_types import HOLE_NUMBER_FIELD, hole_type

    # THE CONTRACT IS BOTH HALVES, and this guard reads the same one the derivation reads. It used
    # to read `OPTIONAL_FIELDS` alone, which is exactly the half `hole_type()` was corrected FROM --
    # so reverting the derivation left every suite green and the correction was measured by nothing
    # (round-4 verification, N3').
    carriers = [item_type for item_type, fields in bt._contract_fields().items()
                if HOLE_NUMBER_FIELD in fields]
    assert carriers == [hole_type()], carriers

    # ...and the case that separates the two halves: a SECOND type declaring the field as REQUIRED.
    # Read off the optional half alone this is invisible; read off the contract it is a store whose
    # "what is a hole" has two answers, and the derivation has to say so rather than pick one.
    patched = dict(bt.REQUIRED_FIELDS)
    patched["PROC"] = tuple(patched["PROC"]) + (HOLE_NUMBER_FIELD,)
    original = bt.REQUIRED_FIELDS
    bt.REQUIRED_FIELDS = patched
    try:
        with pytest.raises(AssertionError, match="no single answer"):
            hole_type()
    finally:
        bt.REQUIRED_FIELDS = original
    assert hole_type() == "BUG", "the patch leaked out of its own block"

    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    state.capture("PR", dict(PR_FIELDS))
    for other in sorted(set(REQUIRED_FIELDS) - {hole_type()}):
        with pytest.raises(StateError, match="a hole is a %s" % hole_type()):
            state.assert_capturable_as_hole(other)
    assert state.assert_capturable_as_hole(hole_type()) is None

    # ...and the refusal really stands between a caller and the store
    with pytest.raises(StateError, match="a hole is a"):
        state.capture("FR", {"title": "a wish", "request_text": "please"}, hole=True)
    assert state.next_hole_number() == "H1", "a refused capture still moved the counter"


# -- BUG-0023: an order that expects nothing is refused at both entrances --------------------------

def _order_body(root_id, expected_outputs):
    return {"product_requirement": root_id, "derives_from": root_id, "type": "implementation",
            "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"],
            "required_inputs": [], "allowed_scope": ["src/"], "forbidden_scope": [],
            "expected_outputs": expected_outputs, "dependencies": []}


def test_a_work_order_that_expects_nothing_is_refused_at_both_entrances(state, capsys):
    """BUG-0023: `create-task` and `capture TSK` end in one door, and that door names the field.

    RED before the fix (measured in a copy outside the repo with `NONEMPTY_FIELDS` carrying no
    TSK entry): all three entrances below created a DRAFT order with `expected_outputs: []`. The
    two producers are asked through the running code -- `dispatch.create_task` (what `create-task`
    and `capture TSK` both call) and `state.capture` (what everything else reaches) -- and the CLI
    line once more, because the refusal has to arrive on the surface a role types.

    EVERY SHAPE OF "NAMES NOTHING", not the empty container alone. The first cut asked `not value`,
    which is a question about the CONTAINER, and the verifier measured what walked through it:
    `--expected-output ""` was rc 0 with a DRAFT order created, and `[""]`, `[None]`, `["   "]` and
    `[[]]` were all accepted by `dispatch.create_task` while `[]` was refused. The property is the
    one the refusal always claimed -- at least one entry that carries text -- and it lives in ONE
    predicate (`backlog_types.names_something`) that this door and the validator both ask.

    AND THE OTHER DIRECTION, because a predicate that refuses everything would pass every line
    above: a scalar that says something is legal (`field_elements`, BUG-0015), and so is a list
    whose first entry is blank and whose second is not.
    """
    from kernel import cli, dispatch
    pr = make_pr(state)
    for hollow in ([], [""], [None], ["   "], [[]], "", "   ", None, ["", None, "  "]):
        with pytest.raises(StateError, match="expected_outputs") as refused:
            dispatch.create_task(state, _order_body(pr["id"], hollow))
        assert "--expected-output" in str(refused.value), (hollow, str(refused.value))
        with pytest.raises(StateError, match="expected_outputs"):
            state.capture("TSK", dict(_order_body(pr["id"], hollow), root_revision=1))
    assert cli.main(["--root", state.root, "create-task", "--product-requirement", pr["id"],
                     "--derives-from", pr["id"], "--type", "implementation",
                     "--assigned-role", "backend-developer", "--acceptance-ref", "AC-1",
                     "--allowed-scope", "src/"]) == 1
    assert "expected_outputs" in capsys.readouterr().err
    # ...and the same line WITH a blank value, which is the one word that reached the store
    assert cli.main(["--root", state.root, "create-task", "--product-requirement", pr["id"],
                     "--derives-from", pr["id"], "--type", "implementation",
                     "--assigned-role", "backend-developer", "--acceptance-ref", "AC-1",
                     "--allowed-scope", "src/", "--expected-output", ""]) == 1
    assert "expected_outputs" in capsys.readouterr().err
    assert not [stem for stem, _path in state.iter_active_items("TSK")], (
        "a refused order still reached the store")

    created = dispatch.create_task(state, _order_body(pr["id"], ["src/x.py"]))
    assert created["status"] == "DRAFT" and created["expected_outputs"] == ["src/x.py"]
    scalar = dispatch.create_task(state, _order_body(pr["id"], "src/y.py"))
    assert scalar["expected_outputs"] == "src/y.py", "a scalar that says something was refused"
    mixed = dispatch.create_task(state, _order_body(pr["id"], ["", "src/z.py"]))
    assert mixed["expected_outputs"] == ["", "src/z.py"], "one real entry is enough"

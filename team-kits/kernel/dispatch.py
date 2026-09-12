"""Dispatch leases + result submission (HARNESS_V2_SPEC.md II.4) -- step 1.4b.

READY -> short-lived lease (nonce + TTL) -> `HARNESS_DISPATCH` header ->
PreToolUse validates the lease and CLAIMS it for one dispatch (hook, phase 2) ->
SubagentStart binds the child's agent_id to the lease -> spawn outcome moves the
task (success: IN_PROGRESS, failure: straight back to READY) -> an orphaned lease
falls back to READY after TTL. The gate parses ONLY the header, never prose.

A claim that produces NO child is undone by the clock, not by an event:
`spent_claim_reason` says what makes a claim still stand and
`reconcile_unstarted_dispatches` returns the task to READY once it does not.
Measured 2026-08-02: the provider delivers no hook event for a permission
refusal at all, so a rollback that needs one is a rollback that may never run.

submit_result validates the <=4 KB result envelope against its schema and
moves IN_PROGRESS -> SUBMITTED; the envelope is stored beside the task.
"""
from __future__ import annotations

import json
import operator
import os
import re
import time
import uuid

from .approvals import (
    ROOT_DISPATCH_KINDS,
    ROUTINE_ROLE_FIELD,
    ApprovalError,
    approved_statuses,
    assert_apr_in_force,
    consumed_request,
    item_subject_manifest,
    proven_expiry,
    read_apr,
)
from .backlog_types import (
    ACTIVE_DIRS,
    AMENDMENT_TYPES,
    AUTOMATA,
    PARENT_FIELDS,
    TRIAGE_RESULT_LINK,
    TSK_EFFORT_FIELD,
    TSK_RUNG_FIELD,
    UI_TASK_TYPES,
    field_elements,
    is_inbox_type,
    parse_id,
)
from . import references
from .lock import ext_path
from .schemas import validate
from .state import ProjectState, StateError, _now_iso

HEADER_PREFIX = "HARNESS_DISPATCH "
DEFAULT_LEASE_TTL = 15 * 60.0
# How long a validated dispatch waits for its SubagentStart to claim it (see
# mark_awaiting_bind); generous enough for a slow spawn, short enough that a
# failed spawn does not leave a claimable slot lying around.
#
# It bounds the CLAIM as well, and that is one window rather than two on purpose:
# "the child may still arrive" and "the claim still stands" are the same
# question. See `spent_claim_reason` and `reconcile_unstarted_dispatches` -- past
# this window a dispatch that produced no child is not evidence of anything, and
# the task goes back to READY without any hook event having to say so.
BIND_WINDOW = 120.0
# where an `APR.kind: analysis` lists the tasks it covers (spec II.2 Buendelung:
# "EINE analysis- oder scope-APR darf MEHRERE im subject_manifest GELISTETE
# Analyse-Tasks decken"). Named here because the manifest is otherwise free-form
# for analysis, and a gate cannot check a key nobody agreed on.
ANALYSIS_TASKS_KEY = "tasks"
# The item fields that OFFER criterion ids (spec II.2: PR/RQ/CR/BUG carry
# `acceptance_criteria`, EXP carries `success_criteria`). One tuple, because two
# readers ask about it in opposite directions -- `_criteria_ids` collects the ids
# out of them, `_approval_covers_criteria` asks whether an approval's manifest
# signed them -- and a second spelling would let the second reader vouch for a
# field the first one reads.
CRITERIA_FIELDS = ("acceptance_criteria", "success_criteria")

# WHICH PROVIDER TOOLS RUN A COMMAND LINE. Provider knowledge, so nothing here can
# derive it; it lives in the kernel because the party that has to ACT on it is the
# kernel (`hand_back_path` below) and a kit hook cannot be imported from here. The
# gate that routes on the same fact keeps its own tuple
# (`gate_write_scope.SHELL_TOOLS`) rather than importing this one, because that
# routing must survive a project whose kernel is unreachable; the two ends and the
# kit's own `settings.json` matcher are measured against each other by
# `tools/test_role_contracts.py::test_the_command_running_tools_are_one_fact_in_three_places`.
COMMAND_TOOLS = ("Bash", "PowerShell")

# WHO BOOKS A SPECIALIST'S RESULT IN. Two values, and which one applies to a role is
# a fact about that role's installed definition, never a list: a role whose `tools:`
# frontmatter names none of `COMMAND_TOOLS` cannot run the entry point at all, so
# `submit-result` is not a step it can take. Measured in pilot 3 (BUG-0048) three
# times: the roles reported the demand as a gap instead of working around it, which
# is the honest outcome of a contract that asks for something the toolset withholds.
# The value rides in the lease and then in the dispatch header, so the role is told
# its path at the one moment the dispatch is composed.
HAND_BACK_KEY = "hand_back"
HAND_BACK_SELF = "self"
HAND_BACK_LEAD = "lead"
# The reference skills a dispatch names (FR-0071). Like `checkpoint` and `hand_back` this is a
# POINTER carried in the header and NOT one of the three keys `parse_header` decides on, so it
# grants nothing; `kernel.references` computes it from the task.
REFERENCES_KEY = "references"

# -- the model ladder (DEC-0034 rules 1-5, DEC-0047, DEC-0076, DEC-0077, DEC-0078) ---------------
# The declaration a kit ships beside its constitution, and the store file the rung vocabulary and
# its aliases live in. Both are read out of the KIT STORE through the same reading as the architect
# step (`_the_kit_delivery_of_the_architect_step`): the scaffold record names the kit, the store
# says what that kit ships. The derivation is `ladder_for_order`.
LADDER_FILE = "ladder.yaml"
TIERS_FILE = "model_tiers.yaml"
# What the derivation writes: the two values on the lease and in the header, and the whole
# derivation beside them on the lease so a reader can see WHY (DEC-0077 (5)). THE SAME TWO NAMES ON
# A TASK ARE THE PM'S ASK (DEC-0091 (1), `backlog_types.TSK_RUNG_FIELD`): an input of
# `ladder_for_order`, never its answer -- which is why the answer reaches the task under the three
# `LEASE_*_FIELD` names below and not under these.
RUNG_KEY = TSK_RUNG_FIELD
EFFORT_KEY = TSK_EFFORT_FIELD
LADDER_KEY = "ladder"
# What the lease derived, copied onto the TASK so it outlives the lease (a lease is removed when
# the order ends, a task is archived): the session brief reads them per order (PR-0010 AC-6) and
# `report.lease_distribution` reads them across orders (DEC-0092 (4)). The role class rides along
# because "builders per goal" is a count of BUILD-class orders, and the class is otherwise only on
# the lease.
LEASE_RUNG_FIELD = "lease_rung"
LEASE_EFFORT_FIELD = "lease_effort"
LEASE_CLASS_FIELD = "lease_class"
# The effort vocabulary, ordered low -> high (DEC-0091 (3)). One ordering, because DEC-0091 (2)
# takes the HIGHER of two efforts and a declaration's effort or an order's ask outside this tuple
# could not be compared -- so both are refused against it (`_valid_ladder`, `create_task`).
EFFORT_LEVELS = ("low", "medium", "high", "xhigh")
# The class name under which a kit's ladder lists its builders. DEC-0092 (2) refuses a second
# concurrent lease of THIS class under one goal without a check-scopes record, so a declaration
# has to name it (`_valid_ladder`) or the rule would silently never fire for that kit.
BUILD_CLASS = "build"
# What a SECOND builder's lease carries: {the other running builder: the check-scopes record that
# measured the pair disjoint}. Absent on every ordinary lease, so "one builder" and "a second one
# admitted on evidence" are two different envelopes (PR-0011 AC-1).
MEASURED_DISJOINT_KEY = "measured_disjoint"
# The two words a class or an exception in the declaration may use instead of a rung name: the
# kit's top rung, or the role's own pin.
CLASS_TOP = "top"
CLASS_PIN = "pin"
# The goal class that switches the effort pair to its `large` value (DEC-0077 (1)). The field is
# the root's `class`; which values exist is the schema's business, this names the one the rule reads.
LARGE_CLASS = "large"
# DEC-0034 rule 2, counted on the task: how many runs of this order ended in FAILED -- see
# `count_failed_run_locked` for what counts and where it is counted.
FAILED_RUNS = "failed_runs"
# DEC-0096 (2), the SECOND escalation threshold beside `failed_runs_per_rung`: how many of the
# failed runs inside one rung's cycle are spent raising the EFFORT on that rung before the rung
# itself climbs. A config value and not a constant for the reason DEC-0077 (2) made the first one
# a config value -- a pilot moves it without a kernel change.
EFFORT_STEPS_KEY = "effort_steps_before_rung"


class DispatchError(StateError):
    """Dispatch-gate violation -- fail-closed, message carries the remedy."""


class NoPendingDispatch(DispatchError):
    """A subagent started without a dispatch awaiting it (spec II.4 gate 1/2)."""


class AmbiguousBinding(DispatchError):
    """Several same-role dispatches await binding; guessing is not allowed."""


def _lease_path(state: ProjectState, task_id: str) -> str:
    return os.path.join(state.root, "tasks", "leases", task_id + ".lease.yaml")


def _envelope_path(state: ProjectState, task_id: str) -> str:
    return os.path.join(state.root, "tasks", "results", task_id + ".envelope.yaml")


def create_task(state: ProjectState, fields: dict) -> dict:
    """Create a TSK: the kernel denormalizes root_revision from the CURRENT
    root item -- callers never guess it (spec II.2)."""
    if "root_revision" in fields:
        raise DispatchError(
            "root_revision is kernel-set from the root item. Remedy: drop it."
        )
    root_id = fields.get("product_requirement")
    if not root_id:
        raise DispatchError(
            "TSK needs product_requirement (the PR/RQ root id). Remedy: set it."
        )
    _assert_the_origins_are_not_inbox_items(state, fields)
    _assert_the_order_tiers_are_placeable(state, fields)
    with state.lock:
        root = state.read_item(root_id)
        _assert_origins_belong_to_root_locked(state, root, fields)
        task_fields = dict(fields)
        task_fields["root_revision"] = root.get("revision")
    # TOCTOU note: capture below takes a SECOND lock hold -- a root-revision
    # change in between is caught fail-closed by create_lease's revision check
    return state.capture("TSK", task_fields)


def order_tiers(task: dict) -> tuple:
    """(rung, effort) the PM asked for on this order -- each a string or None (DEC-0091 (1))."""
    rung = task.get(RUNG_KEY)
    effort = task.get(EFFORT_KEY)
    return (str(rung) if rung not in (None, "") else None,
            str(effort) if effort not in (None, "") else None)


def rung_vocabulary(state: ProjectState) -> tuple:
    """(rungs low -> high, where they come from) -- what an order's rung ask is placed against.

    THE KIT'S LADDER where there is one (DEC-0091 (3): "outside the kit's ladder vocabulary"), and
    for a project no kit scaffolded -- the shape this repository itself runs in -- the reference
    vocabulary of the tiers table beside the kernel package, which is the one every ladder's names
    are taken from (DEC-0076). A project with neither has nothing to place a rung against and the
    ask is refused rather than stored for a reader that will never come.
    `tools/test_light_kit.py::test_a_kit_less_project_places_an_order_rung_against_the_reference_vocabulary`
    """
    found = ladder_declaration(state)
    if found is not None:
        kit, ladder = found
        return tuple(ladder["rungs"]), "%s of kit %r" % (LADDER_FILE, kit)
    table = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), TIERS_FILE)
    if not os.path.isfile(table):
        raise DispatchError(
            "no scaffold record names a kit for this project and no %s lies beside the kernel "
            "package (%s), so there is no rung vocabulary to place an order's `%s` against -- "
            "refused rather than stored unread (DEC-0091 (3)). Remedy: drop the field, or run the "
            "kernel from a tree that carries the tiers table."
            % (TIERS_FILE, os.path.dirname(table).replace(os.sep, "/"), RUNG_KEY))
    return _reference_rungs(table), table.replace(os.sep, "/")


def _reference_rungs(table: str) -> tuple:
    """The reference platform's rung names out of the tiers table, LOW TO HIGH.

    THE REFERENCE ROW IS FOUND BY ITS PROPERTY, not by a provider name: it is the one row whose
    rung names pass through as the model ids (`fable: fable`, the table's own words: "rung names
    ARE the model ids"), because that is what makes its names the vocabulary every other row
    translates. The one key of a row that is not a rung names the provider's effort field, and it
    is told apart the same way -- its value is a field name, not the key itself.
    `tools/test_light_kit.py::test_the_reference_row_is_found_by_its_property_and_not_by_a_name`
    drives a synthetic table where the pass-through row sits under another provider's name.

    THE ORDER IS THE TABLE'S OWN `rungs:` LINE and not the row's key order: a mapping's order says
    nothing (the shipped row happens to read high -> low, mid-goal check B4), and a caller that
    indexes this tuple the way `ladder_for_order` indexes a kit's rungs would climb downwards. Both
    ends are held against each other: the line has to name exactly the pass-through row's rungs.
    """
    data = _read_yaml_mapping(table, TIERS_FILE)
    tiers = data.get("tiers") or {}
    rows = {}
    for provider, row in (tiers.items() if isinstance(tiers, dict) else ()):
        if not isinstance(row, dict):
            continue
        rungs = tuple(str(name) for name, value in row.items() if str(name) == str(value))
        if rungs and len(rungs) == len(row) - 1:
            rows[str(provider)] = rungs
    if len(rows) != 1:
        raise DispatchError(
            "%s names %d pass-through rows under `tiers:` (%s) and the reference vocabulary is the "
            "ONE row whose rung names are the model ids -- no rung vocabulary can be read from it. "
            "Remedy: repair the table." % (table, len(rows), ", ".join(sorted(rows)) or "none"))
    ordered = data.get("rungs")
    reference = next(iter(rows.values()))
    if (not isinstance(ordered, list) or len(set(map(str, ordered))) != len(ordered)
            or set(map(str, ordered)) != set(reference)):
        raise DispatchError(
            "%s carries no `rungs:` line naming exactly the reference row's rungs low -> high "
            "(row: %s, line: %r) -- the vocabulary has names but no order, and an order's rung is "
            "compared by position. Remedy: repair the table."
            % (table, ", ".join(reference), ordered))
    return tuple(str(name) for name in ordered)


def _assert_the_order_tiers_are_placeable(state: ProjectState, fields: dict) -> None:
    """An order's `rung` is one of the vocabulary and its `effort` one of `EFFORT_LEVELS`, or the
    order is refused at CREATION (DEC-0091 (3)).

    At creation and not only at the lease, because the field is the PM's judgment written for a
    dispatcher that reads it later: a value the ladder cannot place would sit on a READY order
    until the first `dispatch`, and by then the fields are frozen. The lease asks the same two
    questions again (`ladder_for_order`), so an `update` while DRAFT cannot slip past either.
    `tools/test_light_kit.py::test_an_order_rung_outside_the_ladder_and_an_effort_outside_the_vocabulary_are_refused`
    """
    rung, effort = order_tiers(fields)
    if effort is not None and effort not in EFFORT_LEVELS:
        raise DispatchError(
            "`%s: %s` is not an effort this kernel can order -- the vocabulary is %s, low to high "
            "(DEC-0091 (3)). Remedy: name one of them, or drop the field and the goal's effort "
            "applies." % (EFFORT_KEY, effort, "|".join(EFFORT_LEVELS)))
    if rung is not None:
        rungs, source = rung_vocabulary(state)
        if rung not in rungs:
            raise DispatchError(
                "`%s: %s` is not a rung of %s (%s) -- an order's rung is the PM's ask on the "
                "kit's own ladder, never a model name of its own (DEC-0091 (3), DEC-0076). "
                "Remedy: name one of the rungs, or drop the field and the role's class decides."
                % (RUNG_KEY, rung, source, ", ".join(rungs)))


def _triage_remedy(state: ProjectState, origin: str, item_type: str) -> str:
    """The way out, read off the wish's OWN state rather than composed once for every case.

    A wish that has already been triaged has nothing left to transition -- its terminals have no
    outgoing edge -- and telling its author to walk one is a remedy that cannot be executed, which
    is the class `backlog_types.replanning_route` exists for one level up. So a wish that already
    names the item it became is answered with THAT item, and only an untriaged one is answered with
    the triage.
    `tools/test_approvals_dispatch.py::test_the_remedy_for_an_already_triaged_wish_names_what_it_became`
    """
    terminals, result_field = TRIAGE_RESULT_LINK[item_type]
    try:
        wish, _archived = _read_item_any(state, origin)
    except Exception:  # noqa: BLE001 -- an unreadable wish is the validator's finding
        wish = None
    became = str((wish or {}).get(result_field) or "")
    if became:
        return ("%s has already been triaged and became %s -- create the task under %s."
                % (origin, became, became))
    return ("triage the wish -- `transition %s TRIAGED`, then %s with `%s` = the goal it became "
            "-- and create the task under that goal."
            % (origin, " or ".join("`transition %s %s`" % (origin, status)
                                   for status in sorted(terminals)), result_field))


def _assert_the_origins_are_not_inbox_items(state: ProjectState, fields: dict) -> None:
    """A work order hangs from a GOAL, never from a wish that has not been triaged (BUG-0091).

    WHAT AN INBOX TYPE IS, is `backlog_types.is_inbox_type` and not a type name here: a type whose
    lifecycle can end by naming the item it BECAME is a waiting room, and the item it becomes is
    what work hangs from. The same contract gives `report._check_fr_result_link` its duty.

    REFUSED AT CREATION, for the reason `_assert_origins_belong_to_root_locked` gives one frame
    down and with a sharper measurement behind it: this is not a mislabel, it is a DEAD END.
    Measured on 75a00d1 in a state directory outside the repo -- `create_task` with an `FR` in both
    fields returns rc 0 and a DRAFT order; `approvals.create_pending_request(state, "scope", FR)`
    then refuses ("this type carries no user approval"), because `FR` is in no row of
    `APPROVAL_TRANSITIONS`; and `create_lease` refuses the order with "no user approval authorises
    dispatching". The order's fields are frozen outside DRAFT, so nothing can repair it afterwards.
    21 of this repository's 120 work orders are in that state (DEC-0066 keeps them: they are
    history, and `report.tasks_under_an_inbox_item` is what counts a relapse).

    BOTH PARENT FIELDS, read through `backlog_types.PARENT_FIELDS`, because the binding a work
    order has to its origin is what that map IS -- naming the two here would be a second list of
    the fields the tree already walks.
    """
    for field in PARENT_FIELDS.get("TSK", ()):
        for one in field_elements(fields.get(field)):
            try:
                item_type, _ = parse_id(str(one))
            except ValueError:
                continue          # an unparseable reference is `capture`'s refusal, not this one's
            if not is_inbox_type(item_type):
                continue
            terminals, result_field = TRIAGE_RESULT_LINK[item_type]
            raise DispatchError(
                "%s %s is an inbox item, not a goal -- a work order under an untriaged wish is "
                "refused at creation (BUG-0091, DEC-0066). Nothing could dispatch it either: %s "
                "is in no row of the approval table, so no user approval exists for it and "
                "`create_lease` refuses every task under one. Remedy: %s"
                % (field, one, item_type, _triage_remedy(state, one, item_type)))


def _assert_origins_belong_to_root_locked(state: ProjectState, root: dict, fields: dict) -> None:
    """A TSK's `derives_from` must hang from the SAME root -- refused at CREATION.

    THE DEAD END THIS ENDS, measured 2026-08-02 in a scaffolded project: `create-task
    --product-requirement PR-0001 --derives-from BUG-0001` where BUG-0001 hangs from PR-0002 was
    accepted with rc 0; `validate` then reported it as an ERROR, `gate_memory_complete` blocked
    the merge on that error, and neither remedy named a way out. `transition TSK-0001 CANCELLED`
    does NOT clear the finding (a cancelled item is still an active item -- measured: the error
    survives and gains an "awaiting archive" warning); only `archive` removes it. And the
    alternative both remedies offer -- "fix product_requirement or derives_from" -- is not
    executable at all: an item's fields are frozen outside DRAFT and no command rewrites them.
    An item that cannot be created wrong needs no remedy for having been.

    ONE definition of "does this origin belong to that root", and it is the VALIDATOR'S:
    `report.origin_root_conflict` over `backlog_types.PARENT_FIELDS`. Imported here rather than
    re-walked -- a second implementation of that walk is precisely the drift `_parents_of` was
    rebuilt to end, and the two answers have to agree or this refuses what `validate` accepts.
    The refusal below therefore quotes that function's sentence rather than composing its own.

    SEVERITY IS KEPT IN STEP with the validator on purpose: `_check_task_origins` calls the
    cross-root case an ERROR and the archived/terminal origin a WARNING, so only the first is
    refused. Refusing a warning here would make a task the validator tolerates uncreatable.
    """
    # deferred: `report` imports `state` and `approvals`, never `dispatch`, so this is a leaf
    # import rather than a cycle -- and by the time a task is created, both halves are loaded
    from .report import origin_root_conflict

    for origin in field_elements(fields.get("derives_from")):
        origin = str(origin or "")
        conflict = origin_root_conflict(state, origin, root["id"])
        if conflict:
            raise DispatchError(
                "derives_from %s -- refused at creation (spec II.8). The dispatch gate resolves "
                "acceptance_refs against the ORIGIN, so this task would be judged against another "
                "root's criteria, and `python scripts/harness.py validate` reports it as an error "
                "that blocks every merge. Remedy: create the task under the root the origin really "
                "hangs from, or name an origin that hangs from %s -- the fields of an existing "
                "task are frozen outside DRAFT, which is why this is refused now rather than "
                "reported later."
                % (conflict, root["id"])
            )


# THE TREE A LEASE WAS GRANTED FOR (stream D's C-3). Until this field a lease named a task and
# nothing else, so no reader could say which checkout an order was being worked in -- the
# "one tree per order" rule of the parallel-streams procedure was carried by the lead's memory and
# by nothing in the state. It is written on EVERY lease, so "no worktree" and "the tree the state
# lives in" are not the same envelope; the caller may name another one, which is the case the rule
# exists for -- a stream working in its own checkout against the shared state directory.
# `tools/test_parallel_streams.py::test_the_lease_carries_the_tree_it_was_granted_for`
WORKTREE_FIELD = "worktree"


def _lease_worktree(state: ProjectState, worktree=None) -> str:
    """The checkout this lease is granted for -- the caller's, or the tree the state directory is in.

    DERIVED AND NEVER EMPTY: a default of "wherever the state lives" is the true answer for every
    project that runs in one tree, and it is the one the kernel can compute rather than be told.

    A NAMED TREE HAS TO EXIST, and that is the whole check. A path nobody can stand in records a
    dispatch nobody can perform, and the field exists to be READ -- by a lead asking which checkout
    an order is in. What is deliberately NOT checked, said rather than implied: whether the path is
    a git checkout, whether it is the tree this state directory belongs to, and whether another
    lease already names it. The last one is not a defect -- several orders in ONE tree is the
    ordinary case, and what keeps them apart is the scope rule above, not the tree. The remainder
    is carried with its measurement as `H156` in `docs/POST_V2_WISHLIST.md`.
    `tools/test_parallel_streams.py::test_a_worktree_nobody_can_stand_in_is_refused`
    """
    if worktree is None:
        return os.path.abspath(os.path.dirname(os.path.abspath(state.root)))
    named = os.path.abspath(str(worktree))
    if not os.path.isdir(named):
        raise DispatchError(
            "no directory at %r, so a lease naming it would record a dispatch nobody can perform. "
            "Remedy: name the checkout the specialist really works in, or leave the flag out -- "
            "the tree the state directory lives in is then recorded." % str(worktree))
    return named


def _assert_no_running_lease_owns_the_same_file_locked(state: ProjectState, task_id: str) -> None:
    """No second lease over a file a RUNNING one already owns (stream D's C-2).

    THE PREDICATE IS `kernel.scopes`, imported and asked rather than restated: it folds both sides
    through the shipped `gate_write_scope._norm` and asks that gate's own `_matches`, so what this
    refuses is what the specialists really meet. A second spelling here would refuse pairs the gate
    grants and grant pairs it refuses. The seam both orders declare (`scopes.SEAM_FIELD`) is
    subtracted by `scopes.overlaps` before the verdict, and a declaration that leaves one order
    owning nothing of its own is not subtracted at all -- both rules live there, once.

    ONLY AGAINST LEASES THAT ARE STILL RUNNING, and the reason is what a lease IS: an expired one
    grants nothing, and `sweep_expired_leases` is what removes it. Comparing against a lease whose
    TTL has run out would refuse work on the strength of a claim nobody holds.

    IT COSTS NOTHING WHEN NOTHING ELSE RUNS: the whole check -- the gate import, the `git ls-files`
    of `scopes.tracked_files` -- sits behind the early return below, so the ordinary single-stream
    dispatch does not pay for it.

    WHAT IT DOES NOT REACH is `scopes`' own limit and not a second one, and one of the two it used
    to inherit is gone: since BUG-0218 the witness half also works on the PAIR, so a region no
    single-entry filling reached -- `a/*x` against `a/y*` -- is refused here too, with no file in
    the tree. What remains inherited is a seam narrower than the overlap (BUG-0226), which is a
    DECLARATION both orders made and the merge round applies.

    AND ONLY AGAINST LEASES, which is the division of labour and not a gap (BUG-0238): two READY
    orders that never run at the same time share no lease and collide only in the merge. That is
    what `check-scopes` is for -- it walks the OPEN orders (`scopes.open_orders` reads
    `is_terminal`, not the lease state) and DEC-0070 (1) makes running it before a cut the rule.
    `tools/test_parallel_streams.py::test_the_second_lease_is_refused_when_the_scopes_overlap`
    `tools/test_parallel_streams.py::test_the_lease_refusal_reaches_a_region_no_single_witness_reaches`
    """
    running = sorted({str(lease["task_id"]) for lease in running_leases(state, except_task=task_id)})
    if not running:
        return
    from . import scopes

    matches, gate = scopes.matcher()
    orders = scopes.open_orders(state, set(running) | {task_id})
    files = scopes.tracked_files(os.path.dirname(os.path.abspath(state.root)))
    for pair in scopes.overlaps(matches, orders, files):
        if task_id not in (pair["a"], pair["b"]):
            continue
        shared = pair["files"] + pair["witnesses"]
        if not shared:
            continue
        other = pair["b"] if pair["a"] == task_id else pair["a"]
        raise DispatchError(
            "%s and %s -- which holds a running lease -- both own %s (and %d more), so a second "
            "dispatch would put two specialists on one file. Refused (DEC-0062 (1), stream D C-2); "
            "the path predicate is the shipped %s, the same one gate layer 3 enforces "
            "`allowed_scope` with. Remedy: wait for %s to finish (`python scripts/harness.py "
            "sweep-leases` says how long it has left), move the shared paths out of one of the two "
            "`allowed_scope`s, or declare them in `%s` on BOTH orders if they are shared on purpose."
            % (task_id, other, ", ".join(shared[:scopes.PATHS_SHOWN]),
               max(0, len(shared) - scopes.PATHS_SHOWN), gate, other, scopes.SEAM_FIELD)
        )


def running_leases(state: ProjectState, except_task: str = None) -> list:
    """Every lease whose TTL has not run out, oldest first -- the claims somebody still holds.

    One reading for the two rules that ask it (`_assert_no_running_lease_owns_the_same_file_locked`
    and `_assert_a_second_builder_was_measured_locked`), so "running" cannot mean two things; an
    expired lease grants nothing and `sweep_expired_leases` is what removes it.
    """
    now = time.time()
    return [lease for lease in _iter_leases(state)
            if float(lease.get("created_epoch") or 0) + float(lease.get("ttl") or 0) > now
            and str(lease["task_id"]) != except_task]


def concurrent_builders(state: ProjectState, task: dict, root: dict, ladder: dict) -> list:
    """The ids of the BUILD-class orders under this order's goal that hold a running lease --
    the orders a second builder would run BESIDE (DEC-0092 (2)); empty for anything that is not a
    build order itself.

    The class is read off the OTHER lease's own ladder answer, the record that granted it, rather
    than derived again here; a kit-less project has no class on either side and the rule does not
    reach it, which `tools/test_light_kit.py::test_a_kit_less_project_is_outside_the_second_builder_rule`
    says rather than this sentence.
    """
    if ladder.get("role_class") != BUILD_CLASS:
        return []
    beside = []
    for lease in running_leases(state, except_task=str(task.get("id"))):
        answer = lease.get(LADDER_KEY)
        if not isinstance(answer, dict) or answer.get("role_class") != BUILD_CLASS:
            continue
        try:
            other = state.read_item(str(lease["task_id"]))
        except StateError:
            continue
        if str(other.get("product_requirement") or "") == str(root.get("id")):
            beside.append(str(other["id"]))
    return sorted(beside)


def _assert_a_second_builder_was_measured_locked(state: ProjectState, task: dict, root: dict,
                                                 ladder: dict) -> dict:
    """A second concurrent BUILD lease under one goal needs a check-scopes record that measured the
    two orders' file sets disjoint -- DEC-0087 (2) as a gate, not a sentence (DEC-0092 (2)).
    Returns {other order id: the covering record, state-relative} -- what `create_lease` writes on
    the lease as the evidence it was granted on (`MEASURED_DISJOINT_KEY`); empty when this is not
    a second builder.

    WHAT THIS ADDS TO THE OVERLAP CHECK ABOVE, and why both stand: the overlap check refuses two
    orders that DO share a file, computed live at the lease. This one refuses two builders whose
    disjointness nobody MEASURED before the cut -- somebody has to have run `check-scopes` over the
    pair, and the record that run leaves (`kernel.scopes.check`) is what is asked for. WHO ran it
    is not read and cannot be: `check-scopes` is not one of the ordering commands
    `gate_write_scope` reserves for the lead, so any role may leave the record, and what the gate
    holds is that a measurement exists, not that the PM made it. A record covers an order only
    while the order's scope is what the record measured (`scopes.covering_record` compares
    digests) and only while it is the NEWEST measurement of the pair, so a DRAFT order re-scoped
    after the check, or a later run that found the pair overlapping, leaves it unmeasured again.
    Nothing here reads a justification, because no gate reads free text (DEC-0092 (1)); the record
    is a measurement or it is nothing.

    ONLY UNDER ONE GOAL and ONLY FOR THE BUILD CLASS, both DEC-0092's words: two builders under two
    goals are the parallel form DEC-0087 (2) names, and a QA or design order beside a builder is
    not a second builder.
    `tools/test_light_kit.py::test_a_second_build_lease_under_one_goal_needs_a_check_scopes_record`
    `tools/test_light_kit.py::test_a_record_stops_covering_an_order_whose_scope_moved_since`
    `tools/test_light_kit.py::test_a_second_lease_of_another_class_or_under_another_goal_needs_no_record`
    """
    beside = concurrent_builders(state, task, root, ladder)
    if not beside:
        return {}
    from . import scopes

    covered, unmeasured = {}, []
    for other in beside:
        record = scopes.covering_record(state, str(task["id"]), other)
        if record is None:
            unmeasured.append(other)
        else:
            covered[other] = os.path.relpath(record["path"], state.root).replace(os.sep, "/")
    if not unmeasured:
        return covered
    raise DispatchError(
        "%s would be a SECOND builder under %s beside %s, and no check-scopes record measured "
        "its file set disjoint from %s -- refused (DEC-0092 (2), DEC-0087 (2): a second builder "
        "only on two measured-disjoint file sets). Remedy: run `python scripts/harness.py "
        "check-scopes` (it writes the record this reads, for the orders as they stand now), read "
        "its verdict, and dispatch again; or wait for %s to finish, or give the slice to that "
        "order. A record stops covering an order whose scope changed since the check."
        % (task["id"], root.get("id"), ", ".join(beside), ", ".join(unmeasured),
           ", ".join(unmeasured)))


def create_lease(state: ProjectState, task_id: str, ttl: float = DEFAULT_LEASE_TTL,
                 worktree: str = None) -> dict:
    """READY -> LEASED with a nonce lease. Validates root approval + revision."""
    with state.lock:
        task = state.read_item(task_id)
        if task.get("status") != "READY":
            raise DispatchError(
                "%s is %s, not READY -- no lease (spec II.4). Remedy: bring the "
                "task to READY via its lifecycle first."
                % (task_id, task.get("status"))
            )
        root = state.read_item(task["product_requirement"])
        _assert_dispatch_authorised_locked(state, task, root)
        _assert_the_architect_step_happened_locked(state, task, root)
        if root.get("revision") != task.get("root_revision"):
            raise DispatchError(
                "task %s was planned against root revision %s but %s is now at "
                "revision %s -- tasks of an invalidated root revision are not "
                "leasable (spec II.2). Remedy: re-approve and re-plan the task."
                % (task_id, task.get("root_revision"), root["id"], root.get("revision"))
            )
        blocked = task.get("blocked_by")
        if blocked:
            raise DispatchError(
                "%s is blocked by %s. Remedy: resolve the blocker first."
                % (task_id, blocked)
            )
        _assert_dependencies_met_locked(state, task)
        _assert_no_running_lease_owns_the_same_file_locked(state, task_id)
        lease_path = _lease_path(state, task_id)
        if os.path.exists(lease_path):
            # THE WAIT IS NAMED, and so is the command that ends it. This said "wait for the lease
            # to resolve or time out" and nothing else -- no duration, no command -- so a role that
            # hit it after a denied spawn had a fifteen-minute stall it could not measure and no
            # instruction it could act on. The remaining seconds are read off the lease that is
            # actually there.
            held = _read_lease(state, task_id)
            left = float(held["created_epoch"]) + float(held["ttl"]) - time.time()
            raise DispatchError(
                "a lease for %s already exists -- parallel second claim blocked (spec II.4). It "
                "expires in %d s%s. Remedy: wait, then `python scripts/harness.py sweep-leases`, "
                "which returns every EXPIRED lease's task to READY and reports what is still "
                "running; a lease this task no longer needs is also dropped by any transition off "
                "%s."
                % (task_id, max(0, int(left)),
                   " (already expired -- the sweep releases it now)" if left <= 0 else "",
                   "/".join(LEASE_BEARING_STATUSES))
            )
        lease = {
            "task_id": task_id,
            "nonce": uuid.uuid4().hex,
            "root_revision": task["root_revision"],
            "created": _now_iso(),
            "created_epoch": time.time(),
            "ttl": float(ttl),
            "agent_id": None,
            WORKTREE_FIELD: _lease_worktree(state, worktree),
        }
        # THE ADOPTION OFFER IS MADE HERE, at the one moment a dispatch is composed, so that what
        # the specialist receives says whether there is anything to resume -- and says it ONLY when
        # the verification passed (DEC-0044: an unverified checkpoint is treated as absent). The
        # key is absent otherwise, so "no offer" and "a failing offer" are the same envelope.
        # `checkpoint_verdict` is the caller's route to the REASONS, which belong in front of a
        # human rather than in the header.
        verdict = checkpoint_verdict(state, task_id, _locked=True)
        if verdict.adoptable:
            lease["checkpoint"] = verdict.pointer
        # ...AND THE HAND-BACK PATH, decided here for the same reason: this is the one moment a
        # dispatch is composed, and the role's own definition is what decides it (BUG-0048).
        # Absent when the definition cannot be read -- see `hand_back_path`.
        path = hand_back_path(agents_dir(os.path.dirname(state.root)),
                              task.get("assigned_role"))
        if path:
            lease[HAND_BACK_KEY] = path
        # ...AND THE REFERENCE SKILLS THIS TASK NAMES (FR-0071), derived here for the third time
        # for the same reason: this is the one moment a dispatch is composed, and the TASK is what
        # decides -- its `assigned_role` and its `type`, both frozen plan fields. The alternative
        # was leaving the pick to the role, which is the habitual-pick failure the item names.
        # Absent when nothing matches, so "this kit ships no reference skills" and "none applies to
        # this task" are the same envelope, and the key grants nothing either way.
        reference_skills = references.for_task(
            references.skills_dir(os.path.dirname(state.root)),
            task.get("assigned_role"), task.get("type"))
        if reference_skills:
            lease[REFERENCES_KEY] = reference_skills
        # ...AND THE RUNG AND EFFORT (DEC-0077 (2)), derived here for the fourth time for the same
        # reason: this is the one moment a dispatch is composed, and the STATE decides -- the kit's
        # declaration, the role's pin, the goal's class and how many runs of this order have failed.
        # The failed run is counted first, on the task this lease is for, so a retry climbs
        # (DEC-0034 rule 2). A refusal out of `ladder_for_order` leaves the count unwritten: the
        # task is written once, below, and only when the lease is.
        ladder = ladder_for_order(state, task, root, count_failed_run_locked(task))
        lease[LADDER_KEY] = ladder
        if RUNG_KEY in ladder:
            lease[RUNG_KEY] = task[LEASE_RUNG_FIELD] = ladder[RUNG_KEY]
            lease[EFFORT_KEY] = task[LEASE_EFFORT_FIELD] = ladder[EFFORT_KEY]
            task[LEASE_CLASS_FIELD] = ladder["role_class"]
        else:
            for field in (LEASE_RUNG_FIELD, LEASE_EFFORT_FIELD, LEASE_CLASS_FIELD):
                task.pop(field, None)
        # ...AND A SECOND BUILDER UNDER THIS GOAL HAS TO HAVE BEEN MEASURED (DEC-0092 (2)), asked
        # last and before the write, so a refusal here leaves neither a lease nor a count behind;
        # the record it was admitted on stands on the lease (PR-0011 AC-1: "evidence ... on the
        # lease"), absent for the ordinary single builder.
        covered = _assert_a_second_builder_was_measured_locked(state, task, root, ladder)
        if covered:
            lease[MEASURED_DISJOINT_KEY] = covered
        state._write_yaml_atomic(lease_path, lease)
        task["status"] = LEASE_MINTED_STATUS
        task["leased_at"] = _now_iso()
        # A NEW LEASE IS A NEW DISPATCH, so what the PREVIOUS run's child did stops being evidence
        # about this task here. Left standing, the records would report a retry as idle before its
        # child has even been asked for -- see `idle_dispatches` and `CHILD_ENDED`.
        task.pop(CHILD_ENDED, None)
        task.pop(IDLE_REPORTED, None)
        state._write_yaml_atomic(state.active_path(task_id), task)
        state._regenerate_index_locked()
        return lease


def checkpoint_verdict(state: ProjectState, task_id: str, _locked: bool = False):
    """What `kernel.checkpoints` says about this task's checkpoint -- deferred so the two stay leaves.

    `checkpoints` imports `LEASE_BEARING_STATUSES` from here, so a module-level import in this
    direction would be a cycle. The same shape as `_assert_origins_belong_to_root_locked`'s import
    of `report`, and for the same reason.
    """
    from .checkpoints import verify

    return verify(state, task_id, _locked=_locked)


def agents_dir(repo_root: str) -> str:
    """Where the INSTALLED role definitions live, asked of the installer that puts them there.

    `presets.AGENTS_DIR` is the path the kit installer writes into, so a kit that moved its
    role definitions would move this reader with it. Deferred import for the reason
    `checkpoint_verdict` gives: `presets` pulls in `subprocess`/`shutil` for the installer it
    drives, and a lease does not need them.
    """
    from .presets import AGENTS_DIR

    return os.path.join(repo_root, AGENTS_DIR)


def _role_frontmatter(definitions: str, role: str):
    """The YAML frontmatter of `role`'s definition in `definitions`, or None when it cannot be read.

    ONE reader for the two questions asked of an installed role definition -- which tools it grants
    (`role_tools`) and which model it pins (`role_pin`) -- so the two cannot answer differently
    about what a readable definition is. None means the question could not be asked: an
    uninstalled kit, a role name nobody ships, a definition without frontmatter.
    """
    import yaml

    path = os.path.join(definitions, str(role or "") + ".md")
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        # THE NEIGHBOUR OF THE SAME DEFECT, fixed in the same shape. Here the file is one the
        # installer writes, so no measured chain reaches it -- `kernel.references._frontmatter`
        # carries the one that was measured, and this is the identical line rather than a second
        # answer to "what does this reader do with a file it cannot decode".
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    try:
        front = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return None
    return front if isinstance(front, dict) else None


def role_pin(definitions: str, role: str):
    """The `model:` a role's installed definition pins, or None when it cannot be read or pins none.

    The pin is the role's BASE on the ladder (DEC-0077 (1): the rung hangs on the role pin and the
    kit endpoint). In an installed project the scaffold has already rewritten a tier alias to the
    concrete name; in a kit's own source tree the alias still stands, and `ladder_for_order`
    resolves it through the store's `model_tiers.yaml` rather than through a map kept here.
    """
    front = _role_frontmatter(definitions, role)
    if front is None:
        return None
    pin = front.get("model")
    return None if pin in (None, "") else str(pin)


def role_tools(definitions: str, role: str):
    """The tools `role`'s definition grants, or None when it cannot be read.

    `definitions` is the DIRECTORY the role definitions live in -- `agents_dir(repo_root)` in an
    installed project, `<kit>/agents` for the shipped source, which is how the suite judges a kit
    before anybody installs it.

    None is NOT "no tools": it means the question could not be asked -- an uninstalled kit, a
    role name nobody ships, a definition without frontmatter. Every caller has to distinguish
    the two, because "this role has no shell" is a statement about a contract and "I could not
    look" is a statement about this process.
    """
    front = _role_frontmatter(definitions, role)
    if front is None:
        return None
    granted = front.get("tools")
    if granted is None:
        return None
    if isinstance(granted, str):
        granted = [part.strip() for part in granted.split(",")]
    if not isinstance(granted, list):
        return None
    return [str(one).strip() for one in granted if str(one).strip()]


def hand_back_path(definitions: str, role: str):
    """`HAND_BACK_SELF`, `HAND_BACK_LEAD`, or None when the role definition cannot be read.

    THE PROPERTY, not a list of role names: a role can book its own result in exactly when its
    installed definition grants a tool that runs a command line (`COMMAND_TOOLS`), because
    `submit-result` IS a command line. A role added tomorrow is judged by its own frontmatter on
    the day it ships, and one that gains or loses a shell changes path without anybody editing a
    contract.

    None keeps the dispatch silent rather than guessing. The constitution states the path for
    every role anyway (the hand-back is the final message; the lead books it in), so an absent
    key withholds an ADDITIONAL permission and never grants one.
    """
    granted = role_tools(definitions, role)
    if granted is None:
        return None
    runnable = {tool.lower() for tool in COMMAND_TOOLS}
    return (HAND_BACK_SELF if any(tool.lower() in runnable for tool in granted)
            else HAND_BACK_LEAD)


def dispatch_header(lease: dict) -> str:
    """The ONLY thing the gate parses -- never free prompt prose (spec II.4).

    `checkpoint` rides ALONG when `create_lease` verified one, because the header is the part of the
    envelope that reaches the specialist verbatim; `parse_header` names the three keys the gate
    decides on and this is not one of them, so it grants nothing. It is a POINTER the specialist
    re-verifies for itself (`python scripts/harness.py checkpoint-status <TSK-ID>`) -- the tree can
    move between the lease and the spawn, and a pointer inside a model-composed prompt is not
    evidence of anything on its own.
    """
    body = {
        "task_id": lease["task_id"],
        "root_revision": lease["root_revision"],
        "lease": lease["nonce"],
    }
    if lease.get("checkpoint"):
        body["checkpoint"] = lease["checkpoint"]
    # WHO BOOKS THIS RESULT IN, in the one part of the prompt that reaches the specialist
    # verbatim. Like `checkpoint` it grants nothing -- `parse_header` names the three keys the
    # gate decides on and this is not one of them -- it TELLS the role which of the two paths
    # the constitution describes is the one its own toolset can walk (BUG-0048).
    if lease.get(HAND_BACK_KEY):
        body[HAND_BACK_KEY] = lease[HAND_BACK_KEY]
    # ...AND WHICH REFERENCE SKILLS THIS ORDER NAMES (FR-0071). Same standing as the two above: a
    # pointer, in the one part of the prompt that reaches the specialist verbatim, so that the
    # choice is in the ORDER rather than in the role's habits. The role still has to open them --
    # a name in a header is not a loaded file.
    # NOT a local called `named`: `test_backlog_types._key_read_aliases` follows one binding by NAME
    # and is scope-blind, so a second `named` in this module inherits this one's key and the
    # unrelated `"; ".join(named)` at the bottom of the file is reported as an unguarded read of a
    # reference-list field (measured, red).
    reference_skills = lease.get(REFERENCES_KEY)
    if reference_skills:
        body[REFERENCES_KEY] = reference_skills
    # ...AND THE RUNG AND EFFORT THIS ORDER RUNS ON (DEC-0077 (5)), so the lead sees them where it
    # copies the header from and the specialist sees what it was dispatched on. The same standing
    # as the three above: `parse_header` does not read them, and what `validate_dispatch` compares
    # is the LEASE, so an edited header changes nothing about the answer.
    for key in (RUNG_KEY, EFFORT_KEY):
        if lease.get(key):
            body[key] = lease[key]
    return HEADER_PREFIX + json.dumps(body, sort_keys=True)


def parse_header(prompt: str) -> dict:
    """Extract the HARNESS_DISPATCH header from a spawn prompt, fail-closed."""
    for line in (prompt or "").splitlines():
        line = line.strip()
        if line.startswith(HEADER_PREFIX):
            try:
                data = json.loads(line[len(HEADER_PREFIX):])
                return {
                    "task_id": data["task_id"],
                    "root_revision": data["root_revision"],
                    "lease": data["lease"],
                }
            except (ValueError, KeyError, TypeError):
                raise DispatchError(
                    "malformed HARNESS_DISPATCH header. Remedy: emit the header "
                    "exactly as returned by dispatch_header()."
                ) from None
    raise DispatchError(
        "no HARNESS_DISPATCH header in the spawn prompt -- dispatch blocked "
        "(the gate parses ONLY the header, spec II.4). Remedy: create a lease "
        "and prepend dispatch_header()."
    )


def validate_lease(state: ProjectState, header: dict) -> dict:
    """PreToolUse-side check: lease exists, nonce matches, not expired."""
    with state.lock:
        return _validate_lease_locked(state, header)


def _validate_lease_locked(state: ProjectState, header: dict) -> dict:
    """validate_lease body for callers already holding the lock (not reentrant)."""
    lease = _read_lease(state, header["task_id"])
    if lease["nonce"] != header["lease"]:
        raise DispatchError(
            "lease nonce mismatch for %s -- stale or foreign header. "
            "Remedy: create a fresh lease." % header["task_id"]
        )
    if _expired(lease):
        # THE ONE RELEASE SITE THAT DID NOT REGENERATE, of the four this function has siblings in
        # (`reconcile_unstarted_dispatches`, `spawn_outcome`, `sweep_expired_leases` all do). The
        # release resets the task to READY on disk, so without this the index -- and the board over
        # it -- kept saying LEASED for a task nobody holds any more (TSK-0071 verifier finding B2).
        # Only on the EXPIRY branch, which already writes the item; a validation that passes stays
        # a pure read.
        _release_lease_locked(state, header["task_id"], to_ready=True)
        state._regenerate_index_locked()
        raise DispatchError(
            "lease for %s expired (ttl %ss) -- task returned to READY. "
            "Remedy: create a fresh lease." % (header["task_id"], lease["ttl"])
        )
    if header["root_revision"] != lease["root_revision"]:
        raise DispatchError(
            "header root_revision %s != lease root_revision %s. Remedy: "
            "emit the header exactly as returned by dispatch_header()."
            % (header["root_revision"], lease["root_revision"])
        )
    return lease


def spent_claim_reason(lease: dict):
    """Why this lease may not be claimed (again), or None -- ONE definition of a spent claim.

    WHEN A CLAIM MAY COME INTO EXISTENCE, stated as a property rather than as a
    flag: a claim is the record that a child was ASKED FOR. It may stand only
    while that ask can still produce a child, or while one exists. Nothing else
    about it is evidence of anything.

    Two terms, and both are things that were OBSERVED rather than assumed:
      * `agent_id` -- a child is bound to this lease. It exists; a second claim
        would be a second child under one grant.
      * an ask that is still in flight -- the bind window opened when the claim
        was made has not closed yet, so the child may still arrive.

    TWO HERE, FOUR IN `reconcile_unstarted_dispatches`, and they are not one list
    counted twice -- the two functions answer opposite questions. This one asks
    "may this lease be claimed (again) NOW", and needs only the reasons a claim
    still stands. The other asks "may this lease be GIVEN BACK", which is a
    stronger question: it adds that a claim was ever made (an undispatched lease
    is nobody's failure) and that the task is still LEASED (an outcome already
    recorded must not be undone). Anyone quoting a number should say which of the
    two functions it belongs to.

    WHAT WAS HERE BEFORE AND WHY IT WAS A DEAD END, measured 2026-08-02 in a real
    headless session: the term was `dispatched_at`, an eternal flag written at
    PreToolUse. Every PreToolUse hook of one event runs to completion even when a
    sibling exits 2, so the flag was written for a spawn another gate was
    refusing at the same moment; the retry was then refused for the remaining
    ~900 s of DEFAULT_LEASE_TTL. The rollback that was supposed to undo it hung
    on a `PermissionDenied` hook event, which fired in NONE of twelve measured
    sessions. A consumption whose undo depends on an event nobody has seen is a
    consumption without a way out, so the undo is now the clock plus
    `reconcile_unstarted_dispatches`, which needs no event at all.

    THE RESIDUAL, named rather than implied: two spawns of the SAME header issued
    inside one parallel batch both land inside the open window, so the second is
    refused -- that half holds. Two spawns MORE than BIND_WINDOW apart where the
    first really did start but neither `SubagentStart` nor `PostToolUse` was ever
    delivered would both be allowed. Such a first child is UNBOUND (nothing set
    `agent_id`), and gate layer 3 refuses every write from an unbound agent, so
    what is lost there is tokens, not scope.
    """
    if lease.get("agent_id"):
        return ("a child (%s) is already bound to the lease for %s"
                % (lease["agent_id"], lease["task_id"]))
    left = _window_open_until(lease) - time.time()
    if lease.get("dispatched_at") and left > 0:
        return ("the lease for %s was dispatched at %s and is still awaiting its child "
                "(%d s left)" % (lease["task_id"], lease["dispatched_at"], int(left)))
    return None


def reconcile_unstarted_dispatches(state: ProjectState) -> list:
    """Every claim that never produced a child -> the task back to READY. Returns the ids.

    THE WAY BACK FOR A SPENT LEASE, and it depends on no hook event whatsoever --
    which is the whole point. Spec II.4 wants "Fehlschlag -> sofort zurueck auf
    READY"; the events that could say "this spawn failed" are the provider's to
    deliver, and a real run showed the harness cannot rely on getting them:
    `PostToolUseFailure` does fire, a permission refusal fires NOTHING, and
    `PermissionDenied` -- which the rollback was registered on -- was never seen.
    So the condition here is the ABSENCE of evidence after the window in which
    evidence could still arrive, which is decidable locally:

        dispatched, no bound child, bind window closed, task still LEASED.

    Every one of the four is load-bearing. Without `dispatched` this would sweep
    a lease its owner has not spawned against yet. Without the `agent_id` check
    it would free a task whose child is running. Without the closed window it
    would race the child that is just starting. Without `LEASED` it would undo an
    outcome one of the post-spawn events already recorded.

    FOUR HERE, TWO IN `spent_claim_reason`: giving a lease back is a stronger
    claim than refusing to re-issue it, so it takes two conditions more. See that
    docstring for the pairing.

    Cost is BIND_WINDOW rather than DEFAULT_LEASE_TTL: 120 s instead of 900 s,
    and `sweep_expired_leases` remains the backstop for everything else (a bound
    child that never finished, a lease nobody dispatched).
    """
    released = []
    with state.lock:
        now = time.time()
        for lease in _iter_leases(state):
            if lease.get("agent_id") or not lease.get("dispatched_at"):
                continue
            if _window_open_until(lease) >= now:
                continue
            task_id = str(lease["task_id"])
            try:
                task = state.read_item(task_id)
            except StateError:
                continue
            if task.get("status") != "LEASED":
                continue
            _release_lease_locked(state, task_id, to_ready=True)
            released.append(task_id)
        if released:
            state._regenerate_index_locked()
    return released


# The value `validate_dispatch` takes for `spawn_model` when the caller has NO spawn payload at all
# (the entry point, the suite's library calls): then the rung is not held against a model nobody
# named. A spawn that names no model passes `None`, which is a different answer -- see
# `spawn_model_refusal`.
NOT_A_SPAWN = object()


def spawn_model_refusal(lease: dict, requested):
    """None, or the sentence that refuses a spawn whose model is not the lease's rung (DEC-0077 (2)).

    MEASURED 2026-09-05, both halves (project_memory/staging/TSK-0130/stream-protocol.md, AC-6):
    the Agent tool's `tool_input` carries `model` when the lead passes it, and a child pinned
    `sonnet` spawned with `model: opus` ran on opus. So the RUNG axis is enforceable at the spawn,
    and this is where. The tool has no `effort` parameter (the same measurement), so that axis is
    derived, written and shown -- never held; BUG-0251 carries what that costs.

    THREE CASES: no rung on the lease (a kit-less project) -> nothing to hold; no `model` on the
    spawn -> fine exactly when the rung IS the role's own pin, because the pin is what the child
    runs on then; a `model` on the spawn -> it has to be the rung, spelled as the rung is (the
    alias the platform reads, which is the same vocabulary the frontmatter pin uses).
    `tools/test_ladder.py::test_a_spawn_below_the_lease_rung_is_refused_and_one_that_names_it_passes`
    """
    ladder = lease.get(LADDER_KEY)
    if not isinstance(ladder, dict) or RUNG_KEY not in ladder:
        return None
    rung = ladder[RUNG_KEY]
    if requested is None:
        if ladder.get("base") == rung:
            return None
        return ("the lease for %s says rung %s but the spawn names no model, so the child would run "
                "on the role's own pin (%s) -- the climb the state derived would not happen "
                "(DEC-0077 (2), DEC-0034). Remedy: pass `model: %s` on the Agent call; the header "
                "carries the value."
                % (lease.get("task_id"), rung, ladder.get("pin"), rung))
    if str(requested) != rung:
        return ("the spawn names model %r but the lease for %s says rung %s -- dispatch blocked "
                "(DEC-0077 (2): the rung is derived from the state, not chosen at the spawn). "
                "Remedy: pass `model: %s`, or leave the parameter out when the rung is the role's "
                "own pin." % (requested, lease.get("task_id"), rung, rung))
    return None


def validate_dispatch(state: ProjectState, header: dict, subagent_type: str,
                      claim: bool = False, prompt_id: str = None,
                      session_id: str = None, spawn_model=NOT_A_SPAWN) -> dict:
    """The full gate-layer-2 check (spec II.4), re-run at SPAWN time.

    `create_lease` checked the same ground when the lease was made, but that was
    a separate moment: an out-of-band edit, a revoked approval or a newly
    failed dependency between lease and spawn must not get through. Everything
    happens under ONE lock hold so the answer cannot change while it is
    computed.

    Checks, in the order spec II.4 lists them: task exists and holds a valid
    READY-lease, role match, root revision, valid APR hash, dependencies met,
    required design_ref/AC references present.

    `claim=True` additionally CONSUMES the lease for one dispatch (spec II.4
    "Ein paralleler zweiter Claim wird blockiert", II.12 "zweiter Claim derselben
    Lease -> Block"). Without it a validated header is a reusable bearer token:
    the nonce travels inside the specialist's own prompt, so the same header
    could spawn N children -- and only the first would ever get bound. Callers
    that merely VERIFY an already-dispatched spawn (the PostToolUse path) pass
    claim=False.

    A claim OPENS THE BIND WINDOW in the SAME write, under the same lock hold,
    and that is not tidiness: `spent_claim_reason` reads that window to decide
    whether a claim still stands, so a claim recorded in one write and its window
    in the next would leave a moment in which the claim counted for nothing.
    `prompt_id` narrows the window exactly as `mark_awaiting_bind` documents.
    """
    with state.lock:
        task_id = header["task_id"]
        lease = _validate_lease_locked(state, header)
        if claim:
            spent = spent_claim_reason(lease)
            if spent:
                raise DispatchError(
                    "%s -- a second claim on one lease is blocked (spec II.4). "
                    "Remedy: create a fresh lease for a second attempt; the "
                    "specialist carries the nonce in its prompt, so re-using it "
                    "would spawn under a spent claim." % spent
                )
        task = state.read_item(task_id)
        if task.get("status") != "LEASED":
            raise DispatchError(
                "%s is %s but holds a lease -- inconsistent state, dispatch "
                "blocked (fail-closed). Remedy: `python scripts/harness.py doctor` shows the "
                "lease; `python scripts/harness.py sweep-leases` returns the task to READY."
                % (task_id, task.get("status"))
            )
        expected_role = task.get("assigned_role")
        if not subagent_type or str(subagent_type) != str(expected_role):
            raise DispatchError(
                "role mismatch: %s is assigned to %r but the spawn asks for "
                "%r -- dispatch blocked (spec II.4). Remedy: spawn the "
                "assigned role, or re-plan the task."
                % (task_id, expected_role, subagent_type or "<none>")
            )
        root = state.read_item(task["product_requirement"])
        if root.get("revision") != task.get("root_revision"):
            raise DispatchError(
                "task %s was planned against root revision %s but %s is now at "
                "revision %s -- tasks of an invalidated root revision are not "
                "dispatchable (spec II.2). Remedy: re-approve and re-plan."
                % (task_id, task.get("root_revision"), root["id"], root.get("revision"))
            )
        _assert_dispatch_authorised_locked(state, task, root)
        _assert_the_architect_step_happened_locked(state, task, root)
        _assert_the_ladder_answer_holds_locked(state, task, root, lease)
        _assert_dependencies_met_locked(state, task)
        if task.get("blocked_by"):
            raise DispatchError(
                "%s is blocked by %s. Remedy: resolve the blocker first."
                % (task_id, task["blocked_by"])
            )
        # A gate input is only as good as its VALIDATION. Both checks below ask
        # whether the reference RESOLVES, not merely whether it is non-empty:
        # three defects in a row on the design rule (synonym type -> legal
        # re-type -> dangling reference) were all the same mistake one level
        # further out, and "design_ref: TBD" satisfies a truthiness test while
        # pointing at nothing.
        #
        # The two are strict in DIFFERENT scopes, on purpose -- do not "make them
        # consistent". `design_refs` lives on the ROOT and is what the scope
        # approval hashes, so membership there is exactly right. Acceptance
        # criteria legitimately live ONE HOP AWAY: spec II.2 gives BUG its
        # Fix-Kriterien, CR its own acceptance_criteria and EXP its
        # success_criteria, and `derives_from` names which of them a task serves.
        # Resolving AC against the root alone made every bugfix, CR and EXP task
        # undispatchable while passing only the WRONG reference.
        #
        # AND ONE HOP AWAY IS NOT THE WHOLE UNIVERSE EITHER -- BUG-0040. An
        # APPROVED AMENDMENT changes the ROOT's contract, so its criteria reach a
        # task that derives from the root and names no CR at all. The universe is
        # therefore derived rather than walked; `_known_acceptance_ids_locked` is
        # the one place it is built, and `excluded` is what it could not admit.
        refs = [str(ref) for ref in field_elements(task.get("acceptance_refs"))]
        known_ac, excluded = _known_acceptance_ids_locked(state, root, task)
        unknown = [ref for ref in refs if ref not in known_ac]
        if not refs or unknown:
            raise DispatchError(
                "%s %s -- a task nobody can check against the approved criteria "
                "is not dispatchable (spec II.4). Remedy: reference criteria that "
                "exist on %s, on its derives_from item, or on an approved amendment "
                "of %s (known: %s).%s"
                % (task_id,
                   "carries no acceptance_refs" if not refs
                   else "references criteria that exist nowhere: %s" % ", ".join(unknown),
                   root["id"], root["id"], ", ".join(sorted(known_ac)) or "none defined",
                   _amendment_hint(unknown, excluded))
            )
        if str(task.get("type", "")).lower() in UI_TASK_TYPES:
            confirmed = [str(ref) for ref in field_elements(root.get("design_refs"))]
            if confirmed and str(task.get("design_ref") or "") not in confirmed:
                raise DispatchError(
                    "%s is a UI task under %s, which has a confirmed design, but "
                    "its design_ref is %r -- dispatch blocked (spec II.6: the "
                    "active reference must be unambiguous, and II.6a makes "
                    "design_ref the binding implementation reference). Remedy: "
                    "set design_ref to one of the frozen revisions: %s."
                    % (task_id, root["id"], task.get("design_ref"), ", ".join(confirmed))
                )
            # ...and MEMBERSHIP IS NOT RESOLUTION. The paragraph above says both checks "ask
            # whether the reference RESOLVES", and this one did not: `design_refs` lives on the
            # ROOT, is not a binding field (`PARENT_FIELDS`), and is therefore never resolved on
            # any write path -- so `capture PR … "design_refs":["DSN-9999"]` followed by
            # `create-task --design-ref DSN-9999` was a SPAWN ALLOWED against a design that does
            # not exist (measured 2026-07-31, before this).
            #
            # WHAT A `design_ref` IS, read off the producer rather than assumed: `staging.
            # freeze_design` writes a STATE-RELATIVE PATH (`design/revisions/DSN-0001.r01.html`)
            # and `freeze_wireframe` the same shape, because a frozen revision is a FILE, not an
            # item with its own automaton (II.6a: "Zustand = Ort + approval_ref"). A role writing
            # the field by hand reaches for the id instead, which is what the measured hole used.
            # Both are accepted and both must resolve -- a path to a file under the state root, an
            # id through `exists_anywhere` (which already knows a frozen revision lives at
            # `<id>.rNN.yaml`). Anything else resolves to nothing and is refused.
            missing = [ref for ref in confirmed if not _design_ref_resolves(state, ref)]
            if missing:
                raise DispatchError(
                    "%s names design references that exist nowhere: %s -- dispatch blocked "
                    "(spec II.6a: design_ref is the BINDING implementation reference, and a "
                    "reference to nothing binds nothing). Remedy: freeze the design through the "
                    "promotion path, or correct %s's design_refs."
                    % (root["id"], ", ".join(missing), root["id"])
                )
        # THE MODEL THE SPAWN NAMES, held against the rung LAST and before the claim, so a refusal
        # here spends nothing: the lead corrects the Agent call and the same lease serves.
        if spawn_model is not NOT_A_SPAWN:
            refusal = spawn_model_refusal(lease, spawn_model)
            if refusal:
                raise DispatchError(refusal)
        if claim:
            lease["dispatched_at"] = _now_iso()
            _open_bind_window(lease, prompt_id, session_id)
            state._write_yaml_atomic(_lease_path(state, task_id), lease)
        return {"lease": lease, "task": task, "root": root}


def verify_dispatch_identity(state: ProjectState, header: dict, subagent_type: str,
                             require_role: bool = True) -> dict:
    """Is this header really THIS lease's? -- identity only, no authorisation.

    For the post-spawn events. They cannot block, so the only thing they protect
    is their own bookkeeping, and the question they need answered is "does this
    header belong to the lease it names" -- nonce, root revision, assigned role.

    Deliberately NOT `validate_dispatch`: asking "is dispatch still authorised?"
    on an event that cannot prevent anything only breaks the bookkeeping. An
    approval revoked while the child ran would freeze the task LEASED -- no
    rollback on failure, a ghost bind window poisoning the next same-role
    dispatch, and on success a task that never reaches IN_PROGRESS, so
    `submit_result` later refuses the specialist's finished work. Recording an
    outcome takes permission away or leaves it unchanged; it never grants any.

    `require_role` is the asymmetry, and it is deliberate rather than an
    oversight (an earlier cut treated a MISSING role as "no opinion" everywhere,
    which failed open on the one path that GRANTS something):
      * True for the success path, which BINDS an agent_id to a task and thereby
        hands gate layer 3 a write permission. A payload variant without
        `subagent_type` must not collect that binding unchecked.
      * False for the failure paths, which only return the task to READY. That
        takes permission away, so refusing it over a missing field would strand
        the task until the TTL sweep for no safety gain.
    """
    with state.lock:
        lease = _validate_lease_locked(state, header)
        task = state.read_item(header["task_id"])
        expected_role = task.get("assigned_role")
        role_missing = not subagent_type
        if (role_missing and require_role) or (
                not role_missing and str(subagent_type) != str(expected_role)):
            raise DispatchError(
                "role %s: %s is assigned to %r but the spawn declared %r -- "
                "refusing to record an outcome for it."
                % ("missing" if role_missing else "mismatch",
                   header["task_id"], expected_role, subagent_type or "<none>")
            )
        return {"lease": lease, "task": task}


def mark_awaiting_bind(state: ProjectState, task_id: str, prompt_id: str = None,
                       session_id: str = None) -> dict:
    """Record that a validated dispatch is waiting for its SubagentStart.

    Why this exists: the SubagentStart payload carries `agent_id` and
    `agent_type` but NO key back to the tool call (no tool_use_id, no prompt --
    verified against the S3 spike payloads and the hooks reference). So the lease
    has to be claimable by role for a short window. See `bind_agent_by_role` for
    what happens when the window holds more than one candidate.

    `prompt_id` narrows it as far as the platform allows: both PreToolUse and
    SubagentStart carry the id of the user prompt being processed, so a stale
    window left by an earlier turn can neither collide with, nor be stolen by, a
    child from a later one. It cannot separate two same-role dispatches inside
    ONE turn -- that is the residual ambiguity, and it is refused, not guessed.

    `validate_dispatch(claim=True)` opens the same window in its own write; both
    go through `_open_bind_window` so there is one description of what an open
    window is, and `spent_claim_reason` reads that same description back.
    """
    with state.lock:
        lease = _read_lease(state, task_id)
        _open_bind_window(lease, prompt_id, session_id)
        state._write_yaml_atomic(_lease_path(state, task_id), lease)
        return lease


def _open_bind_window(lease: dict, prompt_id: str = None, session_id: str = None) -> dict:
    """Mark a lease as awaiting its child for BIND_WINDOW seconds (caller writes).

    THE ASKING SESSION IS RECORDED HERE because this is the moment a child is ASKED FOR, and
    `DISPATCHING_SESSION` explains what the record is for. A caller that has no session id (an
    in-process test, a CLI) leaves the existing record standing rather than blanking it: a claim
    re-opened without the id must not turn a decidable dispatch into an undecidable one.
    """
    lease["awaiting_bind_until"] = time.time() + BIND_WINDOW
    lease["awaiting_bind_prompt"] = prompt_id
    if session_id:
        lease[DISPATCHING_SESSION] = str(session_id)
    return lease


def clear_awaiting_bind(state: ProjectState, task_id: str) -> None:
    """Close the bind window (the spawn failed or was denied, so no child comes).

    Without this a denied spawn leaves a claimable slot for BIND_WINDOW seconds,
    and the next strictly SEQUENTIAL same-role dispatch collides with the ghost
    -- reported as "dispatch same-role tasks sequentially" to a user who already
    was.
    """
    with state.lock:
        try:
            lease = _read_lease(state, task_id)
        except DispatchError:
            return
        lease.pop("awaiting_bind_until", None)
        lease.pop("awaiting_bind_prompt", None)
        state._write_yaml_atomic(_lease_path(state, task_id), lease)


def bind_agent_by_role(state: ProjectState, agent_id: str, agent_type: str,
                       prompt_id: str = None) -> dict:
    """SubagentStart: claim the one lease awaiting a child of this role.

    Returns the bound lease, or raises AmbiguousBinding when the window holds
    several candidates for the same role. That case is refused rather than
    guessed: binding the wrong agent_id would attribute one specialist's writes
    to another specialist's allowed_scope, which is worse than a visible
    refusal -- it would be a silent hole in gate layer 3 (spec II.4).
    """
    if not agent_id:
        # consuming the window for a payload with no agent_id would leave the
        # REAL child permanently unbound, i.e. unable to write anything
        raise NoPendingDispatch(
            "SubagentStart carried no agent_id -- nothing to bind, leaving the "
            "window open for the real child."
        )
    with state.lock:
        now = time.time()
        candidates = []
        for lease in _iter_leases(state):
            if lease.get("agent_id") or _window_open_until(lease) < now:
                continue
            if _expired(lease):
                continue  # the bind window can outlive the lease itself
            if prompt_id and lease.get("awaiting_bind_prompt") not in (None, prompt_id):
                continue
            try:
                task = state.read_item(lease["task_id"])
            except StateError:
                continue
            if str(task.get("assigned_role")) == str(agent_type):
                candidates.append(lease)
        if not candidates:
            raise NoPendingDispatch(
                "no dispatch awaiting a %r child -- this subagent was not "
                "started through the dispatch gate." % agent_type
            )
        if len(candidates) > 1:
            raise AmbiguousBinding(
                "%d concurrent dispatches await a %r child (%s) and the platform "
                "gives SubagentStart no key to tell them apart -- refusing to "
                "guess, because a wrong binding would silently run one "
                "specialist under another's allowed_scope. Remedy: dispatch "
                "tasks of the SAME role sequentially; different roles in "
                "parallel are unaffected."
                % (len(candidates), agent_type,
                   ", ".join(sorted(c["task_id"] for c in candidates)))
            )
        lease = candidates[0]
        lease["agent_id"] = agent_id
        lease.pop("awaiting_bind_until", None)
        lease.pop("awaiting_bind_prompt", None)
        state._write_yaml_atomic(_lease_path(state, lease["task_id"]), lease)
        return lease


def bind_agent(state: ProjectState, task_id: str, agent_id: str) -> dict:
    """Bind a known task to a known agent_id -- the UNAMBIGUOUS binding point.

    Used from PostToolUse(Agent), where `tool_input.prompt` (and therefore the
    dispatch header) and `tool_response.agentId` arrive together, so no
    role-matching guess is involved. It fires at child COMPLETION, which is too
    late to gate the child's own writes -- hence the role-claim above for the
    live window, and this as the authoritative record afterwards (spike S3
    names both binding points).
    """
    with state.lock:
        lease = _read_lease(state, task_id)
        lease["agent_id"] = agent_id
        lease.pop("awaiting_bind_until", None)
        state._write_yaml_atomic(_lease_path(state, task_id), lease)
        return lease


def task_for_agent(state: ProjectState, agent_id: str):
    """The task an agent_id is bound to, or None -- gate layer 3 asks this."""
    if not agent_id:
        return None
    for lease in _iter_leases(state):
        if lease.get("agent_id") == agent_id:
            try:
                return state.read_item(lease["task_id"])
            except StateError:
                return None
    return None


def spawn_outcome(state: ProjectState, task_id: str, ok: bool, session_id: str = None) -> dict:
    """PostToolUse on the spawn: success -> IN_PROGRESS, failure -> READY.

    THE SESSION IS RECORDED ON THE TASK AS WELL, and not only on the lease, because the lease is
    the record that goes away first: `sweep_expired_leases` drops it after the TTL while leaving an
    IN_PROGRESS task standing (see `LEASE_MINTED_STATUS`), and that is precisely the state BUG-0042
    measured -- "IN_PROGRESS with no live agent behind them". With the asker recorded only on the
    lease, that task would be undecidable for `orphaned_dispatches` forever.
    """
    with state.lock:
        task = state.read_item(task_id)
        if ok:
            if task.get("status") == "LEASED":
                task["status"] = "IN_PROGRESS"
                task["started"] = _now_iso()
                if session_id:
                    task[DISPATCHING_SESSION] = str(session_id)
                state._write_yaml_atomic(state.active_path(task_id), task)
        else:
            _release_lease_locked(state, task_id, to_ready=True)
            task = state.read_item(task_id)
        state._regenerate_index_locked()
        return task


def sweep_expired_leases(state: ProjectState):
    """(returned to READY, lease dropped only) for every expired lease (spec II.4: no task hangs).

    TWO LISTS AND NOT ONE, because for one of the two the sweep did LESS than it says. Measured
    2026-08-15 in a scaffolded project against the previous single list: an IN_PROGRESS task whose
    lease expired was printed as "released to READY: TSK-0001" while it stayed IN_PROGRESS --
    `_release_lease_locked` resets only `LEASE_MINTED_STATUS`, deliberately (a child can outlive its
    lease, see that constant). The task was then unleasable, unreported by `validate` and unnamed by
    the next sweep: the "IN_PROGRESS with no live agent behind them" dead end of BUG-0042, wearing a
    sentence that said the opposite. Every caller has to carry both halves; what to DO about the
    second one is a question only a new session can answer (`sweep_orphaned_dispatches`).
    """
    to_ready, lease_only = [], []
    with state.lock:
        lease_dir = os.path.join(state.root, "tasks", "leases")
        if not os.path.isdir(lease_dir):
            return to_ready, lease_only
        for name in sorted(os.listdir(lease_dir)):
            if not name.endswith(".lease.yaml"):
                continue
            task_id = name[: -len(".lease.yaml")]
            try:
                lease = _read_lease(state, task_id)
            except DispatchError:
                continue
            if _expired(lease):
                reset = _release_lease_locked(state, task_id, to_ready=True)
                (to_ready if reset else lease_only).append(task_id)
        if to_ready or lease_only:
            state._regenerate_index_locked()
    return to_ready, lease_only


def live_leases(state: ProjectState) -> list:
    """[(task_id, seconds_left)] for every lease a sweep did NOT release, sorted.

    WHY THE SWEEP HAS TO SAY THIS. `sweep-leases` printed the released ids and nothing else, so a
    role holding a task blocked by "a lease for TSK-0007 already exists -- parallel second claim
    blocked" ran it, read `released to READY: -`, and had no way to learn whether the wait was
    five seconds or fifteen minutes. Silence there is what turns a bounded wait into a stall.
    """
    remaining = []
    with state.lock:
        for lease in _iter_leases(state):
            left = float(lease["created_epoch"]) + float(lease["ttl"]) - time.time()
            if left > 0:
                remaining.append((str(lease["task_id"]), left))
    return sorted(remaining)


# The single status a lease MINTS, and the one whose loss RESETS the task: `create_lease` produces
# it and `_release_lease_locked` returns a task in it to READY once the lease is gone. That
# one-to-one -- LEASED at rest <=> a live lease -- is what DEC-0038/BUG-0010 rests on: it is why a
# bare transition may not reach it (`assert_lease_backed_transition_locked`) and why a task FOUND in
# it without a live lease is an anomaly to REPORT rather than a running child to leave be
# (`leased_without_live_lease`). IN_PROGRESS is deliberately NOT this status: a running child can
# hold IN_PROGRESS past its lease's expiry -- `sweep_expired_leases` drops the lease but leaves the
# status (`_release_lease_locked` resets only LEASED) -- so IN_PROGRESS without a lease is expected,
# not corrupt. One spelling, referenced by `create_lease` and `_release_lease_locked`.
LEASE_MINTED_STATUS = "LEASED"

# The statuses a lease SERVES, and therefore the only ones it may outlive its creation into.
# `create_lease` puts a task in the first and `spawn_outcome` moves it to the second while keeping
# the lease, because `task_for_agent` resolves a running child's writes through it; `submit_result`
# removes it. Any OTHER status means no child is coming and none is running, so a lease left behind
# there blocks the next claim for its whole TTL with nothing on the other end.
# `test_the_lease_bearing_statuses_are_the_ones_the_lifecycle_produces` drives create_lease,
# spawn_outcome and submit_result and reads the statuses off the running code, so this tuple cannot
# quietly stop describing the lifecycle. It is ALSO the set a bare transition may not enter without
# a live lease (DEC-0038): a lease-served status can only be reached honestly through the lease.
LEASE_BEARING_STATUSES = (LEASE_MINTED_STATUS, "IN_PROGRESS")


def lease_in_force(state: ProjectState, task_id: str) -> bool:
    """True when a live (unexpired) lease file exists for this task -- the record a lease-bearing
    status rests on (DEC-0038). Caller holds the lock; a missing, corrupt or expired lease is not
    in force. Reuses `_read_lease`/`_expired` so "in force" has one definition."""
    if not os.path.exists(_lease_path(state, task_id)):
        return False
    try:
        lease = _read_lease(state, task_id)
    except DispatchError:
        return False
    return not _expired(lease)


def assert_lease_backed_transition_locked(state: ProjectState, item_id: str, to_status: str) -> None:
    """Refuse a DIRECT transition INTO a lease-bearing status when no live lease backs it.

    DEC-0038/BUG-0010: a lease-bearing status is ESTABLISHED by a real dispatch lease, never by a
    bare `transition`. `create_lease` (READY -> LEASED) and `spawn_outcome` (LEASED -> IN_PROGRESS)
    write those statuses DIRECTLY and never come through `state.transition`, so this refuses ONLY
    the parallel non-dispatch path -- the dispatch lifecycle is untouched (`create_lease` still
    reaches LEASED). The property is `LEASE_BEARING_STATUSES`, so a lifecycle that started keeping a
    lease into a further status would carry this guard with it rather than leaving a new hole.

    Caller holds the lock. No item-type test is needed: a lease-bearing status name lives only in
    the TSK automaton, so `assert_transition` has already refused it for any other type, and the
    membership test below simply returns for every status but LEASED/IN_PROGRESS.
    """
    if to_status not in LEASE_BEARING_STATUSES:
        return
    if lease_in_force(state, item_id):
        return
    raise DispatchError(
        "%s cannot be moved to %s by a direct transition: a lease-bearing status is established by "
        "a real dispatch lease, not by a status write (DEC-0038/BUG-0010). LEASED with no lease is "
        "untrue bookkeeping -- a later `sweep-leases` finds no lease to reconcile. Remedy: lease the "
        "task through the dispatch path (`python scripts/harness.py dispatch %s`), which mints the "
        "lease and moves it to LEASED." % (item_id, to_status, item_id))


def leased_without_live_lease(state: ProjectState) -> list:
    """Active tasks that read LEASED but hold no live lease -- REPORTED, never silently reset.

    After DEC-0038 a bare transition can no longer mint LEASED, so a LEASED task with no live lease
    is old state or a removed/corrupt lease. `sweep-leases` NAMES it (with the id) instead of
    throwing it back to READY: a silent reset would erase the only sign the bookkeeping was ever
    wrong, and a status the automaton calls LEASED whose lease is gone is a fact a human should see
    (BUG-0010 AC-3). Only `LEASE_MINTED_STATUS`, not the whole lease-bearing set -- an IN_PROGRESS
    task legitimately outlives its lease (see that constant), so flagging it would be noise.
    """
    flagged = []
    with state.lock:
        for stem, _path in state.iter_active_items("TSK"):
            try:
                task = state.read_item(stem)
            except StateError:
                continue
            if task.get("status") == LEASE_MINTED_STATUS and not lease_in_force(state, stem):
                flagged.append(stem)
    return sorted(flagged)


# -- session ownership: the one locally decidable form of "no agent is behind this" -------------

# WHERE THE ASK IS RECORDED. A subagent is a child of the session that asked for it and cannot
# outlive that session, so "the session that asked for this child is not the session asking now" is
# the only form of DEC-0044's "a lease whose agent the session cannot see" this kernel can decide
# without looking at a process it has no handle on. The provider hands every hook payload a
# `session_id` (measured key list in `tools/provider_observations.json`, agent_identity), which is
# what makes the term readable at all.
#
# ONE field name on TWO records, because one of them is dropped first: the LEASE carries it from the
# claim (`_open_bind_window`), the TASK from the successful spawn (`spawn_outcome`) -- and
# `sweep_expired_leases` deletes the lease after the TTL while leaving an IN_PROGRESS task standing,
# which is exactly the state BUG-0042 measured. `dispatching_session_locked` is the single reader.
DISPATCHING_SESSION = "dispatch_session"


def dispatching_session_locked(state: ProjectState, task_id: str, task: dict = None):
    """Which session asked for THIS task's current dispatch, or None when nothing recorded it.

    THE LEASE IS THE LIVE RECORD, and while one EXISTS it is the only one asked -- even when it is
    still empty. The task's copy answers only where there is no lease at all, which is precisely the
    state it was written for (`sweep_expired_leases` drops the lease and leaves IN_PROGRESS
    standing).

    THE DEFECT THAT MADE THAT ORDER A RULE INSTEAD OF A PREFERENCE, measured 2026-08-15: a fallback
    that ran whenever the lease carried no session read the LAST run's value out of the task, and
    `create_lease` mints a lease with no session (it is recorded at the CLAIM, one tool call later).
    In that window a retry dispatched by THIS session was judged foreign: a mid-session SessionStart
    -- a compaction, same id -- swept the fresh dispatch back to READY and killed the nonce sitting
    in the prompt that was being composed. `test_approvals_dispatch
    .test_a_fresh_lease_of_this_session_is_not_judged_by_the_previous_runs_record` is that chain.

    None is NOT "nobody" -- it is "undecidable here", and every caller has to treat it that way (see
    `orphaned_dispatches`). A corrupt lease answers None for the same reason.
    """
    if os.path.exists(_lease_path(state, task_id)):
        try:
            recorded = _read_lease(state, task_id).get(DISPATCHING_SESSION)
        except DispatchError:
            return None
        return str(recorded) if recorded else None
    try:
        recorded = (task if task is not None else state.read_item(task_id)).get(
            DISPATCHING_SESSION)
    except StateError:
        return None
    return str(recorded) if recorded else None


def no_progress_status(from_status: str):
    """The status the TSK automaton offers for a run that produced NOTHING, or None when it is not
    the single obvious one.

    DERIVED FROM THE EDGE SET, not a table of two rows, because a table is a claim that the
    lifecycle has exactly these two lease-bearing statuses forever. Three subtractions, each of
    which says what such a status may NOT be:
      * a TERMINAL -- a run that produced nothing did not end the task's life,
      * the CHAIN SUCCESSOR -- that edge means the run DID produce something,
      * a LEASE-BEARING status -- landing in one would re-assert the very thing being swept away.
    What the shipped automaton leaves is LEASED -> READY (the lease-timeout back-edge) and
    IN_PROGRESS -> FAILED (the run that did not deliver, which is also the edge the pilot's PM
    walked by hand -- BUG-0042). Ambiguity is refused rather than guessed: with no single answer
    left, the caller REPORTS the dispatch instead of moving it.
    `test_approvals_dispatch.test_the_no_progress_status_is_derived_from_the_automatons_edge_set`
    holds both halves.
    """
    auto = AUTOMATA["TSK"]
    if from_status not in auto.states:
        return None
    candidates = {dst for src, dst in auto.allowed if src == from_status}
    candidates -= set(auto.terminals)
    candidates -= set(LEASE_BEARING_STATUSES)
    if from_status in auto.chain and auto.chain.index(from_status) + 1 < len(auto.chain):
        candidates.discard(auto.chain[auto.chain.index(from_status) + 1])
    return candidates.pop() if len(candidates) == 1 else None


def orphaned_dispatches(state: ProjectState, session_id: str):
    """(orphaned, undecidable) for every task sitting in a lease-bearing status.

    ORPHANED means the ask is recorded and it names a session other than `session_id` -- no child of
    it can be running here, so the status is a claim nothing backs. UNDECIDABLE means the record this
    task's CURRENT dispatch answers with (`dispatching_session_locked`) names no session at all:
    state written before this record existed, a lease just minted and not yet claimed, a lease
    removed out of band. The honest answer there is "this cannot be judged", and the caller says so
    rather than sweeping on a guess. A dispatch this very session asked for is neither, which is what
    keeps a mid-session SessionStart (a compaction) from reporting a live child of its own as gone --
    and that holds for the retry it minted seconds ago only because of the reading order the reader's
    own docstring measures.

    WHAT THIS DOES NOT MEASURE, named because the answer would otherwise read stronger than it is:
    a session id that is not ours proves the ask came from ELSEWHERE, not that the asker is over.
    Two Claude Code sessions in one repo at the same time are therefore the case where "orphaned" is
    true by this definition and wrong in fact; `sweep_orphaned_dispatches` is what decides what may
    be done about that, and it is deliberately narrower than this function. The second boundary is
    the id itself: it is the provider's, and what this term needs of it -- that a session KEEPS it
    while its children live -- is not among the things `tools/provider_observations.json` records as
    measured. A provider that issued a fresh id to a continuing session would look, from here,
    exactly like a session that ended.
    """
    orphaned, undecidable = [], []
    with state.lock:
        for stem, _path in state.iter_active_items("TSK"):
            try:
                task = state.read_item(stem)
            except StateError:
                continue
            status = task.get("status")
            if status not in LEASE_BEARING_STATUSES:
                continue
            asked_by = dispatching_session_locked(state, stem, task)
            record = {"task_id": stem, "status": status, "asked_by": asked_by,
                      "lease_in_force": lease_in_force(state, stem)}
            if asked_by is None:
                undecidable.append(record)
            elif asked_by != str(session_id or ""):
                orphaned.append(record)
    by_id = operator.itemgetter("task_id")          # one sort key, two lists
    return sorted(orphaned, key=by_id), sorted(undecidable, key=by_id)


def sweep_orphaned_dispatches(state: ProjectState, session_id: str):
    """(swept, left) -- return every orphaned dispatch to an honest status at session start.

    DEC-0044 half (1): nothing pretends to run. The status moves through `state.transition`, i.e.
    along an edge the TSK automaton names (`no_progress_status`), so the sweep cannot write a status
    the lifecycle does not offer, and the transition drops the lease on its way out
    (`release_lease_for_status_locked`). An IN_PROGRESS dispatch therefore lands in FAILED and its
    retry is the user's approved one (`state.RETRY_APPROVAL_EDGE`) -- which is the moment DEC-0044
    puts the checkpoint verdict in front of a human.

    `left` carries every dispatch this did NOT move, with the reason, and it is not a leftover: the
    undecidable ones and any whose transition the automaton refuses have to reach the session as
    facts, or the sweep's silence would read as "there was nothing".

    THE RESIDUE THIS DOES NOT CLOSE, measured against the shipped surface rather than assumed: a
    SECOND live session in the same repo owns dispatches this session cannot see either, and they
    are indistinguishable here from those of a session that ended. What bounds the damage is that
    the sweep only ever moves a task to a status a human then has to act on -- READY (re-leasable)
    or FAILED (whose way back needs the user's approved retry) -- and never touches an agent binding
    that is still resolvable: `task_for_agent` reads the LEASE, and by the time this has run the
    lease is gone, so a still-running foreign child is refused by gate layer 3 exactly as it already
    is today once its lease expires (`test_approvals_dispatch
    .test_a_swept_orphan_keeps_no_lease_and_no_agent_binding`).
    """
    orphaned, undecidable = orphaned_dispatches(state, session_id)
    swept, left = [], list(undecidable)
    for record in orphaned:
        target = no_progress_status(record["status"])
        if target is None:
            left.append(dict(record, why="the TSK automaton offers no single no-progress edge out "
                                         "of %s -- refusing to guess one" % record["status"]))
            continue
        try:
            state.transition(record["task_id"], target)
        except StateError as exc:
            left.append(dict(record, why="the transition to %s was refused (%s)" % (target, exc)))
            continue
        swept.append(dict(record, moved_to=target))
    for record in left:
        record.setdefault("why", "no dispatching session is recorded for it, so whether a child was "
                                 "ever asked for by another session cannot be decided here")
    return swept, left


# -- the dispatch nobody is working on any more (BUG-0058) --------------------------------------

# WHERE THE END OF A CHILD IS RECORDED, and it is the TASK for the reason DISPATCHING_SESSION also
# rides on it: the lease is the record that goes away FIRST (`sweep_expired_leases` drops it while
# leaving an IN_PROGRESS task standing), while this fact is read at the end of a LATER turn --
# arbitrarily long after the child stopped. `create_lease` clears it, because a new lease is a new
# dispatch and the previous run's child says nothing about this one.
CHILD_ENDED = "child_ended"

# WHAT THE LEAD WAS LAST TOLD about this dispatch: the sentence itself, not a counter and not a
# digest. `idle_dispatches` composes it and `mark_idle_reported` compares against it, so the
# surfacing speaks at most once per FINDING rather than once per turn -- and again the moment the
# finding changes. Kept readable in the item on purpose: a task file that says what was surfaced
# needs no second store to explain a refusal somebody met an hour ago. ONE STRING and not the list
# of reasons, because a list on an item is a shape other readers have a rule about
# (`backlog_types.REFERENCE_LIST_FIELDS`, and BUG-0038 is what a scalar read as a sequence costs);
# what is stored here holds prose and no references, so it stays a scalar.
IDLE_REPORTED = "idle_reported"


def _lease_bearing_dispatches_locked(state: ProjectState):
    """(task_id, task, lease) for every lease whose task still stands in a lease-bearing status.

    The caller holds the lock. Everything that asks "which dispatch does this belong to" starts
    here and narrows from it, so the narrowing terms stay visible at their own call site instead of
    being baked into the walk.
    """
    for lease in _iter_leases(state):
        task_id = str(lease["task_id"])
        try:
            task = state.read_item(task_id)
        except StateError:
            continue
        if task.get("status") in LEASE_BEARING_STATUSES:
            yield task_id, task, lease


def _dispatches_a_stop_could_belong_to(state: ProjectState):
    """The dispatches whose child could be the one that just stopped. The caller holds the lock.

    ONE narrowing, and it is the only thing that can be said with certainty about a stop: a
    dispatch whose child's end is ALREADY RECORDED cannot be the owner of a NEW one. Everything
    else stays in -- an UNBOUND dispatch belongs here because its child is precisely the one no
    record can identify, and an EXPIRED lease belongs here because a child may outlive its lease
    (`LEASE_MINTED_STATUS`), so its window running out says nothing about whether its child is the
    one that stopped.

    Both were measured rather than reasoned into place. Without the recorded-end term the corpse of
    pilot 4 stays a possible owner for every later stop of the same role forever, and the ambiguity
    refusal in `record_child_end` then turns the whole mechanism off for that role
    (`test_a_dispatch_whose_end_is_recorded_stops_competing_for_the_next_stop`). With an EXPIRY
    term added on top -- the shape a review proposed against exactly that poison -- a stop of a
    long-running child lands on the fresh same-role dispatch beside it, which is the misattribution
    this whole function exists to avoid
    (`test_a_long_running_dispatch_still_counts_as_a_possible_owner_of_a_role_matched_stop`).
    """
    for task_id, task, lease in _lease_bearing_dispatches_locked(state):
        if not task.get(CHILD_ENDED):
            yield task_id, task, lease


def record_child_end(state: ProjectState, agent_id: str = None, agent_type: str = None):
    """Record that a dispatch's child has STOPPED; returns the task id, or None when this stop
    belongs to no dispatch this kernel can name.

    WHY IT IS WRITTEN DOWN AT ALL: the end of a child is an EVENT, and the party that has to know
    about it -- the lead, at the end of one of its own later turns -- is not the party the event is
    delivered to. Without a record, "is anything still working on this task?" is a question no
    reader can answer, which is the state pilot 4 measured (BUG-0058; see `idle_dispatches`).

    TWO ATTRIBUTIONS, AND THEY ARE NOT THE SAME KIND OF ANSWER:
      * `agent_id` is an IDENTITY. The lease that names it IS this child's dispatch; nothing is
        matched and nothing is guessed.
      * the ROLE is a GUESS, taken only when the payload carries no id, and it is made ONLY when
        exactly one dispatch of that role could be the owner at all -- counting every one this
        kernel cannot rule out (`_dispatches_a_stop_could_belong_to`), the UNBOUND ones included.
        An unbound dispatch's child is exactly the one no record can identify, so leaving it out of
        the count is what wrote the stop of an unbound child onto a RUNNING same-role dispatch
        beside it -- measured, and the counter-direction is
        `test_a_stop_with_no_id_is_refused_while_an_unbound_dispatch_of_the_role_could_own_it`.
        Where the single possible owner is itself unbound, there is nothing to record: no record
        ties that child to that dispatch, and writing one would be the same guess in one step.

    Zero candidates is None and not an error: every subagent stop reaches this, including those of
    helpers the harness never dispatched, and including a second stop of a child whose end is
    already recorded.

    WHAT IT CANNOT SEE: a child whose lease is already GONE (the TTL sweep drops it while the task
    stays IN_PROGRESS) has no `agent_id` mapping left, so its end is unattributable here -- and
    `idle_dispatches` does not carry that case either, since a running child is indistinguishable
    from a dead one once every record of it is gone. It is a hole with a name, not a covered case.
    """
    with state.lock:
        possible = list(_dispatches_a_stop_could_belong_to(state))
        if agent_id:
            candidates = [row for row in possible
                          if str(row[2].get("agent_id")) == str(agent_id)]
        elif agent_type:
            owners = [row for row in possible
                      if str(row[1].get("assigned_role")) == str(agent_type)]
            if len(owners) > 1:
                raise AmbiguousBinding(
                    "%d dispatches of the role %r could own this stop (%s) and it carries no "
                    "agent_id -- refusing to guess which of them ended, because recording the end "
                    "against the wrong task reports a specialist that is still working as idle. "
                    "Remedy: dispatch tasks of the SAME role sequentially; different roles in "
                    "parallel are unaffected. AND IF ONE OF THEM IS A CORPSE (BUG-0144): a "
                    "dispatch whose run is over for good stops competing as soon as its TASK "
                    "moves -- the lease is released with the status -- so transition the finished "
                    "one and the next stop of this role is attributed again. Each candidate with "
                    "what its lease knows about its child: %s"
                    % (len(owners), agent_type, ", ".join(sorted(row[0] for row in owners)),
                       ", ".join("%s (%s)" % (row[0], row[2].get("agent_id") or "no child bound")
                                 for row in sorted(owners, key=lambda one: one[0]))))
            candidates = [row for row in owners if row[2].get("agent_id")]
        else:
            candidates = []
        if not candidates:
            return None
        task_id, task, _lease = candidates[0]
        task[CHILD_ENDED] = _now_iso()
        state._write_yaml_atomic(state.active_path(task_id), task)
        state._regenerate_index_locked()      # see `mark_idle_reported` -- a task is a board card
        return task_id


def _window_ran_out_with_no_child(state: ProjectState, task_id: str) -> bool:
    """Is there a lease for this task that names no child and whose window has passed?

    The caller holds the lock. All three terms are read off the ONE record that can carry them, and
    a MISSING lease answers False on purpose: once the TTL sweep has taken the lease away, whether
    a child was ever bound is not a question this kernel can still answer, and False is what "we
    cannot say" has to mean for a term that produces a refusal.
    """
    if not os.path.exists(_lease_path(state, task_id)):
        return False
    try:
        lease = _read_lease(state, task_id)
    except DispatchError:
        return False
    return not lease.get("agent_id") and _expired(lease)


def staged_progress(state: ProjectState, task_id: str) -> str:
    """One sentence about what this dispatch has PUT ON DISK, measured rather than assumed.

    The top level of the task's staging directory, which is the one place a dispatched specialist
    may write with its own tools (spec II.4) -- so "nothing there" is the same observation the
    pilot made by hand about the run that produced no file. A COUNT and no judgement: whether what
    is there carries the work forward is what `checkpoint-status` answers, and every message built
    on this points at that command instead of pretending to have asked it.
    """
    directory = os.path.join(state.staging_root(), task_id)
    where = os.path.relpath(directory, state.root).replace(os.sep, "/")
    try:
        entries = os.listdir(ext_path(directory))
    except OSError:
        return "nothing was staged for it (%s does not exist)" % where
    if not entries:
        return "nothing was staged for it (%s is empty)" % where
    return "%d entr%s under %s" % (len(entries), "y" if len(entries) == 1 else "ies", where)


def idle_dispatches(state: ProjectState) -> list:
    """Every dispatch this kernel has a RECORD saying no child is on it, with what it staged.

    THE FAILURE THIS MAKES VISIBLE, measured in pilot 4 half 2 (BUG-0058, P4-2 in
    docs/pilot/2026-08-22-pilot-4-befunde.md): a dispatched specialist made two tool calls,
    produced no file and stopped; the lead then answered NINE consecutive user turns with waiting
    phrases and made not one follow-up call, while the task sat in IN_PROGRESS with a live lease
    and an empty staging directory. Nothing asked whether anything was still behind that status.

    WHAT A FINDING IS -- a POSITIVE record, never the absence of one, and the difference is the
    whole correction this function has behind it:
      * its child's end is recorded (`CHILD_ENDED`, written at that child's SubagentStop), or
      * NOTHING WAS EVER BOUND to it and its dispatch window has run out: the lease is still there,
        it names no `agent_id`, and its TTL has passed. Nobody was ever tracking a run on it.
    A task in a lease-bearing status that matches neither is silent here.

    THE TERM THAT IS DELIBERATELY ABSENT, because it was WRONG and its chain ran to work loss: "no
    lease in force" on its own. A running child may legitimately outlive its lease -- that is a
    documented property of this lifecycle, stated at `LEASE_MINTED_STATUS` -- so that term reported
    specialists that were still working; measured, and the remedy it carried (take the task to the
    no-progress status) would have unbound a live child and made its `submit-result` refusable.
    `test_a_bound_child_that_outlived_its_lease_is_not_reported_as_idle` is the counter-direction,
    and it goes red the moment the term comes back.

    A finding is REPORTED, never moved: what to do about it is the lead's judgement (book a
    handed-back envelope, adopt a checkpoint, or take the task onto the automaton's no-progress
    edge), and a kernel that decided it would be guessing at work it cannot see. `no_progress_status`
    rides along so the reader that prints this does not have to name a status the automaton might
    not offer.

    WHAT THIS DOES NOT SEE, and both are holes with names rather than covered cases: a BOUND child
    whose SubagentStop never arrives is indistinguishable here from one that is still working, for
    as long as the task stands; and once the TTL sweep has removed the lease of such a task, no
    record of it is left at all. What this DOES report about a run nobody stopped is the unbound
    case above -- and an unbound child, if one is running, is one gate layer 3 refuses every write
    from, so what is reported there is a dispatch that can produce nothing either way.
    """
    findings = []
    with state.lock:
        for stem, _path in state.iter_active_items("TSK"):
            try:
                task = state.read_item(stem)
            except StateError:
                continue
            status = task.get("status")
            if status not in LEASE_BEARING_STATUSES:
                continue
            reasons = []
            ended = task.get(CHILD_ENDED)
            if ended:
                reasons.append("its child stopped at %s and no result was booked" % ended)
            if _window_ran_out_with_no_child(state, stem):
                reasons.append("no child was ever bound to it and its dispatch window of %d s has "
                               "run out, so nothing here was ever tracking a run on it"
                               % DEFAULT_LEASE_TTL)
            if not reasons:
                continue
            findings.append({"task_id": stem,
                             "status": status,
                             "assigned_role": task.get("assigned_role"),
                             "reasons": reasons,
                             # THE FINDING AS ONE SENTENCE, composed once: `mark_idle_reported`
                             # compares this against what was last said and the reader that prints
                             # it prints this, so "the same finding" cannot come to mean two
                             # things -- which is what deciding it twice would eventually buy.
                             "why": "; ".join(reasons),
                             "no_progress_status": no_progress_status(status),
                             "staged": staged_progress(state, stem)})
    return sorted(findings, key=operator.itemgetter("task_id"))


def mark_idle_reported(state: ProjectState, finding: dict) -> bool:
    """Record that the lead was told THIS finding; True when it had not been told this one before.

    THE BOUND ON A REFUSAL THAT WOULD OTHERWISE REPEAT ITSELF. The caller refuses the end of a turn
    (`gate_dispatch.handle_stop`), and the assistant answers a refused stop by CONTINUING -- so a
    condition that survives being reported would refuse the next stop of the same continuation, and
    the one after that. What is compared is the REASONS: unchanged means the lead has already been
    handed this exact fact and a second refusal adds nothing; changed means something happened
    since -- a child bound late to a dispatch that had already been reported as never having had
    one, and then stopping, is the reachable case
    (`test_an_idle_finding_is_reported_once_and_again_only_when_it_changes`).

    This is the kernel-side bound and it is deliberately not the only one -- the caller also stands
    down for a stop the provider marks as one a stop hook already blocked. Two bounds because the
    second is the provider's word and this one is the harness's own; only this one is measured
    here, which is why no text in the kits promises that the refusal arrives, only that it does not
    repeat.
    """
    task_id = finding["task_id"]
    said = finding["why"]
    with state.lock:
        try:
            task = state.read_item(task_id)
        except StateError:
            return False
        if str(task.get(IDLE_REPORTED) or "") == said:
            return False
        task[IDLE_REPORTED] = said
        state._write_yaml_atomic(state.active_path(task_id), task)
        # THE RECORD LANDS ON THE TASK, and a task is a card on the board, so an unregenerated
        # write leaves the board showing the item as it was before it. The rule and its two
        # measured defects are in
        # `test_board.test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind`.
        state._regenerate_index_locked()
        return True


def release_lease_for_status_locked(state: ProjectState, task_id: str, status: str) -> bool:
    """Drop a lease the task's new status no longer serves; True when one was dropped.

    THE DEAD END THIS ENDS, measured 2026-08-02: `transition TSK-0001 READY` off LEASED (an
    explicit back-edge in the TSK automaton, spec II.2 Querregeln) moved the status and left the
    lease file in place. The task then read READY while `create_lease` refused it with "a lease for
    TSK-0001 already exists", `validate` reported nothing at all, and the only exit was to wait out
    the TTL. `transition ... CANCELLED` from LEASED or IN_PROGRESS left the same wreckage on a task
    nobody would ever sweep.

    Called from `state._transition_locked`, i.e. from EVERY transition, so the rule is a property
    of the status rather than of the four callers that happen to move a task today.
    """
    # No item-type test: a lease is keyed by task id, so a non-task simply has no lease file and
    # the existence check below answers for it. One condition instead of two spellings of one.
    if status in LEASE_BEARING_STATUSES:
        return False
    if not os.path.exists(_lease_path(state, task_id)):
        return False
    _remove_lease(state, task_id)
    return True


def submit_result(state: ProjectState, envelope: dict) -> dict:
    """Validate the <=4 KB envelope, store it, move IN_PROGRESS -> SUBMITTED."""
    validate(envelope, "result_envelope")
    task_id = envelope["task_id"]
    with state.lock:
        task = state.read_item(task_id)
        if task.get("status") != "IN_PROGRESS":
            raise DispatchError(
                "%s is %s -- submit-result needs IN_PROGRESS. Remedy: check "
                "the task lifecycle." % (task_id, task.get("status"))
            )
        state._write_yaml_atomic(_envelope_path(state, task_id), envelope)
        task["status"] = "SUBMITTED" if envelope["status_proposal"] == "SUBMITTED" else "FAILED"
        task["completed"] = _now_iso()
        state._write_yaml_atomic(state.active_path(task_id), task)
        _remove_lease(state, task_id)
        state._regenerate_index_locked()
        return task


# -- internals -----------------------------------------------------------------

def _iter_leases(state: ProjectState):
    """Every readable lease; the caller holds the lock. Corrupt files are skipped
    here on purpose -- callers that must FAIL on one read it by task id."""
    lease_dir = os.path.join(state.root, "tasks", "leases")
    if not os.path.isdir(lease_dir):
        return
    for name in sorted(os.listdir(lease_dir)):
        if not name.endswith(".lease.yaml"):
            continue
        try:
            lease = state._read_yaml(os.path.join(lease_dir, name))
        except Exception:
            continue
        if isinstance(lease, dict) and lease.get("task_id"):
            yield lease


def _criteria_ids(item: dict) -> set:
    """The criterion ids an item offers: `acceptance_criteria` (PR/RQ/CR/BUG) or
    `success_criteria` (EXP, spec II.2). Entries may be `{id, text}` mappings or
    plain strings -- both shapes appear in real items, and a strict resolution
    check that only understood one of them would block the other.

    The FIELD itself is normalised through `backlog_types.field_elements` for the same reason
    (BUG-0015): a scalar `acceptance_criteria: AC-1` split into four one-letter criterion ids,
    and against a scalar `acceptance_refs` that split the same way the dispatch check passed on
    criteria nobody wrote."""
    ids = set()
    for field in CRITERIA_FIELDS:
        for entry in field_elements(item.get(field)):
            if isinstance(entry, dict) and entry.get("id"):
                ids.add(str(entry["id"]))
            elif isinstance(entry, str) and entry.strip():
                ids.add(entry)
    return ids


def _binds_to(item_type: str, item: dict, target_id: str) -> bool:
    """Does this item hang DIRECTLY from `target_id`, through a field its own contract binds with?

    A predicate over `backlog_types.PARENT_FIELDS`, which is where the fact "these field names
    carry a binding" is decided; `report._parent_bindings` is the other reader of that same map,
    for the walk that needs the pairs rather than a yes/no. Direct rather than transitive on
    purpose -- an amendment names its target itself, and the narrower question is the safe one for
    a check that WIDENS what dispatches.
    """
    return any(str(one) == target_id
               for field in PARENT_FIELDS.get(item_type, ())
               for one in field_elements(item.get(field)))


def _approval_covers_criteria(item: dict, kind: str) -> bool:
    """Does an approval of this KIND hash the very criteria we are about to trust?

    THE QUESTION THIS ANSWERS, and why it is not "is the kind `scope`": `assert_apr_in_force`
    verifies a content hash only for the item-derived kinds, and even among those only the SCOPE
    manifest carries `acceptance_criteria` (`approvals._SCOPE_FIELDS`; the acceptance and delivery
    manifests name delivered commits and task lists instead). An `analysis` or `routine` approval
    is not item-derived at all and `item_subject_manifest` refuses to build one.

    So the reachable hole this closes is a real interaction and not a hypothetical: `mint` writes
    `approval_ref` for EVERY item-bound approval (see `_covering_routine_apr`, which documents the
    same overwrite for roots), so a routine approval minted on an already-APPROVED amendment leaves
    `status: APPROVED` standing beside an `approval_ref` whose kind hashes nothing -- and an
    out-of-band edit of the criteria would then widen the universe unchallenged. Asking the
    MANIFEST instead of naming a kind means a kind added to `APPROVAL_TRANSITIONS` later is judged
    by what it actually covers.

    THE RETURN LINE IS THE WHOLE PROTECTION FOR ONE FIELD, so it is named rather than left to be
    inferred: `success_criteria` is read by `_criteria_ids` and is NOT in `approvals._SCOPE_FIELDS`.
    Measured 2026-08-15 -- an out-of-band `success_criteria: [{id: AC-77}]` added to an APPROVED CR
    leaves the scope hash MATCHING (so `assert_apr_in_force` says nothing), and this comparison is
    the only thing between that and a dispatchable criterion nobody signed. It is per FIELD and not
    per item for exactly that reason. `test_approvals_dispatch
    .test_a_criterion_smuggled_into_a_field_the_approval_does_not_sign_does_not_widen` is its red
    test; the line has no other one.
    """
    try:
        manifest = item_subject_manifest(item, kind)
    except ApprovalError:
        return False  # not item-derived -- it signs no content of this item at all
    return all(field in manifest for field in CRITERIA_FIELDS if field in item)


def _amendment_criteria_locked(state: ProjectState, root: dict):
    """(criterion ids, {amendment id: why it does not count}) for the amendments of one root.

    THE DERIVATION: an amendment's criteria are part of the root's contract when the USER approved
    that amendment's content -- the same authority the root's own criteria rest on, which
    `_assert_dispatch_authorised_locked` has already demanded one frame up. Four terms, each read
    from the store that owns it:
      * it IS an amendment -- `backlog_types.AMENDMENT_TYPES`, the types that name the revision
        they amend;
      * it amends THIS root -- `_binds_to`, over the reference graph's own binding fields;
      * it still STANDS in a status a user's approval put it in -- `approvals.approved_statuses`,
        derived from the type's automaton, which is what keeps a REJECTED amendment out (its
        `approval_ref` survives the rejection) and an APPLIED one too;
      * its approval is IN FORCE and SIGNS THE CRITERIA -- `assert_apr_in_force` plus
        `_approval_covers_criteria`.
    Nothing here enumerates a type, a status or a kind, so the day a kit ships a second amendment
    type it arrives already resolved -- the property is held from both ends by
    `test_backlog_types.test_an_amendment_is_the_type_that_names_the_revision_it_amends`.

    WHAT THE SIGNATURE COVERS, AND WHAT IT DOES NOT -- said plainly, because "the user approved it"
    is true of the CONTENT and not of the MEMBERSHIP. The scope manifest hashes the criteria
    (`approvals._SCOPE_FIELDS`, which concedes the same narrowness at its own definition), and it
    does NOT hash `target_pr` -- so which root an amendment belongs to is not part of what anybody
    signed. Through the kernel that is closed: an edit of `target_pr` is a `HASHED_FIELDS` change,
    which bumps the revision and drops the approval. PAST the kernel it is open: a hand-edited
    `target_pr` re-aims a still-valid approval's criteria into another root's universe, and this
    reader cannot tell. Widening the manifest would kill every live approval, so it is a spec
    decision with a migration and not something to slip in here. Authorisation is untouched either
    way -- that comes from the ROOT's own approval, one frame up.

    WHERE THIS DERIVATION STOPS, and it is a residue rather than a safe edge: an amendment that
    reached its terminal `APPLIED` contributes nothing, and once archived it is not even read --
    so a LATER task against a criterion that CR minted is refused again, BUG-0040 one lifecycle
    step further on. Not widened here because `approved_statuses` answers `{APPROVED}` for CR by
    the same argument that keeps `RETIRED` out for PROC, and overriding a derivation with a special
    case is the shape this whole item is fixing. The behaviour is asserted, not promised, by
    `test_approvals_dispatch.test_an_applied_amendments_criteria_stop_counting`, so widening it
    later is a decision somebody has to take rather than a silent drift.

    The second element is what makes the refusal honest: an amendment whose criteria do NOT count
    is invisible in the item files (they read `AC-11` plainly), so the reason travels with the
    refusal instead of leaving the user to compare hashes by hand -- the failure BUG-0039 is about.
    """
    known, excluded = set(), {}
    for item_type in sorted(AMENDMENT_TYPES):
        for _stem, path in state.iter_active_items(item_type):
            try:
                item = state._read_yaml(path)
            except Exception as exc:  # noqa: BLE001 -- an unreadable amendment approves nothing
                # criteria None: unreadable means we cannot say WHICH criteria were lost, so this
                # one is named in every refusal rather than only in the ones it could explain
                excluded[os.path.basename(path)] = (None, "unreadable (%r)" % (exc,))
                continue
            if not isinstance(item, dict) or not item.get("id"):
                continue
            if not _binds_to(item_type, item, root["id"]):
                continue
            reason = _amendment_refusal(state, item, item_type)
            if reason is None:
                known |= _criteria_ids(item)
            else:
                excluded[str(item["id"])] = (_criteria_ids(item), reason)
    return known, excluded


def _amendment_hint(unknown, excluded: dict) -> str:
    """The half of the refusal that names WHY a criterion the user can READ is not in the universe.

    Only the amendments that could explain THIS refusal -- one that offers an unrecognised
    reference, or one nobody could read. Naming every excluded amendment would bury the one that
    matters under the rest of the backlog, and a reference no amendment offers is exactly the
    "exists nowhere" case this must not dress up as an approval problem.

    Without it the user meets the pilot's own confusion one level deeper: `CR-0001.yaml` says
    `AC-11` in plain sight while the gate says it exists nowhere, and the difference is a hash
    nobody can see. BUG-0039 is that failure mode in the approval texts.
    """
    if not unknown:
        return ""   # the refusal is "no acceptance_refs at all" -- no amendment explains that
    named = []
    for item_id, (criteria, reason) in sorted(excluded.items()):
        if criteria is None or criteria & set(unknown):
            named.append("%s (%s)" % (item_id, reason))
    if not named:
        return ""
    return (" Amendments of the root that could hold a missing reference, and why their criteria "
            "do not count: %s." % "; ".join(named))


def _amendment_refusal(state: ProjectState, item: dict, item_type: str):
    """Why this amendment of the root contributes no criteria, or None when it does."""
    status = item.get("status")
    if status not in approved_statuses(item_type):
        return "status %r is not a status a user's approval put it in" % status
    apr_ref = item.get("approval_ref")
    if not apr_ref:
        return "it carries no approval_ref"
    try:
        apr = read_apr(state, apr_ref)
        assert_apr_in_force(state, apr, item)
    except Exception as exc:  # noqa: BLE001 -- see below
        # BROAD ON PURPOSE, and the direction is what makes it safe: every answer this branch can
        # give NARROWS the universe, so an unforeseen failure costs a refusal a reader can see and
        # never a criterion a reader cannot. `read_apr` translates a missing file, but a corrupt
        # approval YAML or an unreadable consumed request arrives as neither StateError nor
        # ApprovalError -- and reaching the hook as an internal error would report "the harness is
        # broken" about an amendment that simply does not vouch for anything.
        return str(exc) or repr(exc)
    if not _approval_covers_criteria(item, apr.get("kind")):
        return ("its approval %s is of kind %r, whose subject manifest does not carry the "
                "criteria -- nothing signed them" % (apr_ref, apr.get("kind")))
    return None


def _known_acceptance_ids_locked(state: ProjectState, root: dict, task: dict):
    """(criterion ids a task may reference, why an amendment's were left out).

    Two hops, and they are strict in DIFFERENT ways because the items behind them differ:

    1. `derives_from`, a required TSK field naming the contract the task actually serves -- a
       bugfix task referencing the PR's AC instead of the BUG's Fix-Kriterien would be referencing
       the wrong contract entirely. This hop asks only that the origin RESOLVES. It carries no
       status and no approval term, and that is a DESIGN CHOICE with a measured reason rather than
       an oversight: a `BUG` cannot reach `APPROVED` in a repo whose approval mint is unreachable
       (H39), while the kits' own bugfix flow cuts tasks against a TRIAGED bug's Fix-Kriterien. A
       status term here would make that flow undispatchable. So the looseness is real and it is
       bounded by what it lends: the criteria of an item the PLANNER named, under a root whose own
       approval already authorised the dispatch one frame up.
       `test_approvals_dispatch.test_a_bugfix_task_may_reference_a_triaged_bugs_fix_criteria`
       holds that direction open.
    2. THE AMENDMENT HOP, which needs no `derives_from` at all, because an approved amendment
       changes the ROOT's contract rather than offering one of its own. BUG-0040 carries the field
       observation and names the audit chain it was measured on: a live project's approved change
       requests minted criteria that this gate then called nonexistent, and the task was cancelled
       for it. Re-cutting that task against ONE of the change requests would have bought its
       criteria and lost the rest, which is why the fix is a derivation over the root rather than a
       second hop.

    AND AN AMENDMENT MAY ONLY ENTER THROUGH HOP 2 -- the `continue` below. Without it hop 1 was the
    way around hop 2's whole point: `derives_from: CR-0001` on a DRAFT, never-approved CR lent
    `AC-11` and the spawn PASSED (measured 2026-08-15), so the amendment path's approval term could
    be walked past by naming the same item one field over. The exclusion reads `AMENDMENT_TYPES`,
    the same derivation hop 2 selects with, so the two halves cannot come apart.
    `test_approvals_dispatch.test_an_unapproved_amendment_named_in_derives_from_lends_nothing`
    is the red side of it.
    """
    known = _criteria_ids(root)
    for origin in field_elements(task.get("derives_from")):
        if not origin or str(origin) == root["id"]:
            continue
        try:
            origin_type, _number = parse_id(str(origin))
        except ValueError:
            continue  # free-text provenance note, not an item reference
        if origin_type in AMENDMENT_TYPES:
            continue  # an amendment's criteria are approval-gated -- hop 2 or nothing
        item, _archived = _read_item_any(state, str(origin))
        if item:
            known |= _criteria_ids(item)
    amended, excluded = _amendment_criteria_locked(state, root)
    return known | amended, excluded


def _assert_dependencies_met_locked(state: ProjectState, task: dict) -> None:
    """spec II.4 gate 2 / II.12 "offene Abhaengigkeit -> Block". A dependency is
    satisfied once its work was accepted (DONE) or QA'd (VALIDATED)."""
    open_deps = []
    for dep_id in field_elements(task.get("dependencies")):
        dep, _archived = _read_item_any(state, dep_id)
        if dep is None:
            open_deps.append("%s (missing)" % dep_id)
        elif dep.get("status") not in ("DONE", "VALIDATED"):
            open_deps.append("%s (%s)" % (dep_id, dep.get("status")))
    if open_deps:
        raise DispatchError(
            "%s has open dependencies: %s -- dispatch blocked (spec II.4). "
            "Remedy: finish the dependencies first."
            % (task["id"], ", ".join(open_deps))
        )


# WHICH GOALS ARE NOT ASKED FOR THE ARCHITECT STEP (FR-0085, DEC-0072). The wish asked for the duty to hang
# off the `class` field a root already carries -- "small: no SR; normal/large: at least one ACCEPTED
# SR". MEASURED before it was built: `class` has NO vocabulary anywhere in this kernel. The shipped
# suite alone captures roots with `feature`, `normal`, `research`, `exploratory` and
# `technical_enabler`, and no schema, no validator and no capture check constrains the value. A rule
# spelled as "class in (normal, large)" would therefore SKIP the duty for every value nobody
# thought of, which is the failure `EVIDENCE_KINDS` names one file away: an unrecognised value does
# not fail a check, it skips one.
#
# So the EXEMPTION is the closed set and everything else is asked, unknown values included. Two
# members, each with its own reason: `small` is FR-0085's own word for the size that pays nothing;
# `technical_enabler` is the class this kernel already treats as carrying no product content
# (`REQUIRED_FIELDS` lets it omit the user story, `report._check_ui_delivery_sequence` lets it run
# alongside), and there is no user-facing design for an architect to derive.
#
# WHAT IT COSTS AND IN WHICH DIRECTION IT FAILS: a typo in a class name asks for an architect round
# that was not owed -- friction, and recoverable by one `capture SR`. The opposite spelling would
# hand out work under a goal nobody designed, which is what the wish is about. The free-text nature
# of the field is carried as a hole with its measurement, not papered over here.
# `tools/test_approvals_dispatch.py::test_a_goal_of_an_unknown_class_is_asked_for_the_architect_step`
SR_EXEMPT_CLASSES = frozenset(("small", "technical_enabler"))
# The status in which a technical requirement has been ACCEPTED rather than merely proposed --
# derived from the type's own chain so a renamed status moves the duty with it, and it is the LAST
# chain status because that is what "accepted" is on a two-step automaton (PROPOSED -> ACCEPTED).
ARCHITECT_STEP_TYPE = "SR"


def _accepted_requirement_status() -> str:
    return AUTOMATA[ARCHITECT_STEP_TYPE].chain[-1]


def _carries_its_own_criteria(item_type: str) -> bool:
    """CAN an item of this type hold the criteria a work order is measured against?

    THE QUESTION IS ABOUT THE TYPE AND NOT ABOUT THE VALUE, and the wording matters because the
    first cut of this sentence said the origin "brings" its criteria while the code asks whether
    its type CAN carry them. Measured 2026-09-05 (round-2 verification, R3): a `BUG` with
    `acceptance_criteria: []` excuses the architect step, and the shipped kit hook lets that spawn
    through with rc 0.

    IT STAYS AT THE TYPE LEVEL, with the reason rather than by default: this predicate answers "is
    this order measured somewhere other than the goal", which is a fact about where its criteria
    LIVE. Whether the list at that place is filled is a different question with a different owner
    and a different MOMENT: `validate_dispatch` -- the spawn, not the lease -- refuses a task that
    names no criterion at all and one whose criteria exist nowhere. Answering it here would put a
    second reader on it, one lifecycle step early.

    WHAT THE TWO TOGETHER DO NOT CATCH, measured through the shipped kit hook as a process rather
    than derived: the universe `validate_dispatch` resolves against is NOT the origin alone. It is
    `_known_acceptance_ids_locked` -- the root, the origin AND the approved amendments -- so a
    reference that exists only on the ROOT resolves. An order whose origin is a `BUG` with an EMPTY
    criteria list and whose `acceptance_refs` name a criterion of the goal is therefore excused from
    the architect step by THIS predicate and then measured against the GOAL's criteria -- the very
    goal whose architect step is missing. Measured through the shipped kit hook as a process, and
    the LEASE is granted in all three: empty criteria + no refs -> spawn rc 2 ("carries no
    acceptance_refs"); empty criteria + a ref that exists nowhere -> spawn rc 2; empty criteria + a
    ref that exists on the root -> spawn rc 0. That last line is the remainder, and it is `H155` in
    `docs/POST_V2_WISHLIST.md`.
    `tools/test_approvals_dispatch.py::test_an_empty_origin_excuses_the_step_while_the_root_criteria_measure_it`

    DERIVED FROM THE FIELD CONTRACT, not from a list of type names: `validate_dispatch` looks for a
    task's criteria in `CRITERIA_FIELDS`, so a type whose contract declares one of those fields is
    a place criteria can live and a type that declares none is not, whatever its name. Measured
    over the shipped contracts that picks out PR, RQ, BUG, CR and EXP and leaves out SR, PROC, HYP,
    MST and TSK -- and the one that matters is `SR`, which is exactly the type the duty below is
    ABOUT.
    `tools/test_approvals_dispatch.py::test_only_an_origin_that_carries_criteria_excuses_the_architect_step`
    """
    from .backlog_types import _contract_fields

    declared = _contract_fields().get(item_type, ())
    return any(field in declared for field in CRITERIA_FIELDS)


def _the_kit_ships_the_architect_step(state: ProjectState) -> bool:
    """Does the KIT this project runs SHIP a home for `ARCHITECT_STEP_TYPE`? (DEC-0074, DEC-0079)

    THE DUTY BELONGS TO A KIT THAT HAS THE STEP, and until DEC-0074 it was asked of every project
    the shared kernel serves. Measured on scaffolded pilots outside the repo (TSK-0126): an office
    work order under its `PROC` root and a research work order under its `RQ` root both hit
    "no SR in status ACCEPTED hangs from that goal", and the remedy sent them to `capture SR` and to
    "the architect" -- two words that appear in neither kit's constitution, skills or phase model.
    The office kit's texts do not contain the string `SR` at all.

    WHAT IS READ, AND WHY IT IS THE KIT'S DELIVERY AND NOT THE PROJECT'S STOCK -- this is DEC-0079,
    and it is the correction of a first cut that asked `os.path.isdir(state.root / ...)`. Measured
    as processes on scaffolded pilots (merge verify round 2, R2-B1): the office kit's OWN command
    line accepts `capture SR` with rc 0, which creates `system/active`, and a bare `mkdir` does the
    same -- and from that moment every order under a `PROC` was refused at the lease AND at the
    spawn. A rule a project can switch on by accident is not the rule the user decided. So the
    subject is what the KIT DELIVERS: the scaffold's own ownership record says which kit installed
    this project (`presets.installation`), the kit store says what that kit ships
    (`presets.kit_dir`), and the question is whether its `templates/project_memory` carries
    `ACTIVE_DIRS[ARCHITECT_STEP_TYPE]`. Of the three shipped kits only dev-team's does. A kit that
    GAINS the type falls under the duty the day its template ships that home, and one that loses it
    falls out -- with no line here to edit. An enumeration of kit names was option (C) of DEC-0074
    and was rejected for the reason CLAUDE.md gives: the next kit without the type walks into it
    again.

    IT FAILS CLOSED. A tree with no scaffold record and a kit that is not staged on this machine
    are both "this reader cannot say", and then the duty is ASKED -- the direction that costs a
    question rather than the one that skips a step. That is also why the whole test suite, whose
    state directories are built key by key and carry no kit record, keeps meeting the duty.

    THE OTHER HALF (DEC-0079 (1b)) IS THE RULE THAT WAS ALREADY THERE: an origin that BRINGS the
    criteria excuses the step (`_carries_its_own_criteria`), which is what leaves a research order
    deriving from an `EXP` unasked even where the home exists.

    `tools/test_approvals_dispatch.py::test_the_architect_step_is_owed_by_the_kits_delivery_not_the_projects_stock`
    """
    return _the_kit_delivery_of_the_architect_step(state)[0]


def _the_kit_delivery_of_the_architect_step(state: ProjectState):
    """(owed, why_it_could_not_be_read) -- one reader, two callers, one answer.

    THE SECOND HALF IS THE REFUSAL'S, and it is why this returns a reason instead of a bool.
    `DEC-0079` (4) says the fail-closed direction is "stated in the remedy"; measured on scaffolded
    pilots (merge verify round 3, R3-B1) the refusal printed the ORDINARY sentence in all three
    unreadable cases, so an office project whose kit store this process cannot reach was sent to
    `capture SR` and to "the architect" -- the two words H163 exists because that kit does not have.

    WHERE THE STORE PATH COMES FROM, said rather than implied: `presets.staging_root()`, which is
    the RUNNING home directory. The scaffold record names the kit, not a path, so a project moved
    to a machine, an account or a runner whose home carries no kit store is exactly the case this
    branch answers -- and there the honest answer is "this could not be read", not "derive an SR".

    `tools/test_approvals_dispatch.py::test_a_project_whose_kit_delivery_cannot_be_read_says_so`
    """
    from . import presets

    repo = os.path.dirname(os.path.abspath(state.root))
    try:
        kit = presets.installation(repo)["kit"]
    except Exception:  # noqa: BLE001 -- an absent or broken record is an answer, not a crash
        return True, ("this project carries no readable scaffold record (%s), so which kit it runs "
                      "-- and therefore whether that kit has an architect step at all -- could not "
                      "be read" % presets.ROLES_MANIFEST.replace(os.sep, "/"))
    try:
        directory = presets.kit_dir(kit)
    except Exception:  # noqa: BLE001 -- the kit is not in the store this process can reach
        return True, ("the kit %r this project records is not in the kit store this process can "
                      "reach (%s), so what that kit DELIVERS could not be read"
                      % (kit, presets.staging_root()))
    template = os.path.join(directory, "templates", "project_memory")
    if not os.path.isdir(template):
        return True, ("the kit %r in the store at %s ships no templates/project_memory, so what it "
                      "delivers could not be read" % (kit, directory))
    return os.path.isdir(
        os.path.join(template, *ACTIVE_DIRS[ARCHITECT_STEP_TYPE].split("/"))), None


def presets_staging_root() -> str:
    """The kit store this process reads, for a refusal that has to name it."""
    from . import presets

    return presets.staging_root()


def architect_step_owed(state: ProjectState, task: dict, root: dict) -> bool:
    """Does this work order still owe the architect step? -- the predicate, asked in two places.

    THE REFUSAL BELOW AND THE SUITE'S OWN DISPATCH FIXTURE (`tools/conftest.drive_task_to`) ask
    THIS, so a fixture that walks a task to a lease satisfies the rule the way it already mints an
    approval on a gated edge -- rather than re-deciding for itself what the rule is. A second
    spelling in the fixture would let the suite walk past a duty production cannot walk past, which
    is the one thing a fixture must never be able to do.

    WHAT EXCUSES AN ORDER, as a property and no longer as "anything but the root". The first cut of
    this returned False for EVERY origin other than the root, and the verifier measured what that
    came to: a task deriving from a `PROPOSED` SR under the same goal was granted a lease while the
    identical task deriving from the goal was refused, and `derives_from` at 75a00d1 names an SR 29
    times against the goal 3 times -- the dev-team developer skills PRESCRIBE the SR spelling
    ("Your `TSK` -- `derives_from` names the SR"), so in a kit project the duty would never have
    fired at all.

    The exemption is now bound to what it MEANS: an origin excuses the architect step when its
    type is a place a work order's criteria can LIVE (`_carries_its_own_criteria`) -- a defect, a
    change request, an experiment. Such an order is measured against that item and is the case FR-0085 rules out ("not
    wanted: an SR for every bugfix task"). An `SR` origin carries no criteria field, so it excuses
    nothing by itself; it satisfies the duty exactly when it IS the accepted architect step, which
    the scan below already answers -- one rule, no second branch for the type the rule is about.
    """
    owed, _why = _the_kit_delivery_of_the_architect_step(state)
    if not owed:
        return False        # DEC-0074/DEC-0079: the kit ships no home for the step, so no duty
    if str(root.get("class") or "") in SR_EXEMPT_CLASSES:
        return False
    for origin in field_elements(task.get("derives_from")):
        origin = str(origin)
        if origin == str(root.get("id")):
            continue
        try:
            origin_type, _ = parse_id(origin)
        except ValueError:
            continue      # an unparseable origin is refused at creation, not weighed here
        if _carries_its_own_criteria(origin_type):
            return False
    from .report import origin_root_conflict

    accepted = _accepted_requirement_status()
    for stem, path in state.iter_active_items(ARCHITECT_STEP_TYPE):
        try:
            item = state._read_yaml(path)
        except Exception:  # noqa: BLE001 -- an unreadable item is the validator's finding
            continue
        if not isinstance(item, dict) or item.get("status") != accepted:
            continue
        if not origin_root_conflict(state, str(item.get("id") or stem), root["id"]):
            return False
    return True


def _assert_the_architect_step_happened_locked(state: ProjectState, task: dict, root: dict) -> None:
    """No work order under a goal that has no ACCEPTED technical requirement (FR-0085).

    THE MEASUREMENT THAT ASKED FOR IT: the constitutions name the chain FR -> PR -> SR -> TSK and
    the PM skill hands an approved goal to the architect, while the kernel knew nothing about it --
    measured in a state directory outside the repo, a `normal`, a `large` AND a `small` goal each
    got a lease with zero SR items in the project. How lopsided the ratio of requirements to work
    orders is in a given store is a measurement of the round that asks, not a count this comment
    can keep.

    WHERE IT ASKS: at the LEASE, because that is where a dispatch is minted. `validate_dispatch`
    asks again at the spawn, the way it re-asks the approval, the dependencies and the blocker, so
    a lease that predates this rule does not carry a spawn past it.

    WHOM IT ASKS: every order under the goal EXCEPT one whose origin brings its own criteria --
    the property is `_carries_its_own_criteria` and the argument is there. An order deriving from a
    technical requirement is asked like any other, and is answered by that requirement being
    ACCEPTED. A goal of an exempt class is never asked -- see `SR_EXEMPT_CLASSES` for which, and
    why the exemption rather than the duty is the closed set.

    WHAT COUNTS AS THE STEP HAVING HAPPENED: an `SR` in the accepted status of its own automaton
    that hangs from this root, read through the same reference walk the validator uses
    (`report.origin_root_conflict` over `backlog_types.PARENT_FIELDS`) -- a second spelling of
    "hangs from" would refuse what `validate` calls fine.
    """
    if not architect_step_owed(state, task, root):
        return
    unreadable = _the_kit_delivery_of_the_architect_step(state)[1]
    if unreadable:
        # ITS OWN SENTENCE, because the ordinary one would be FALSE here: this order is asked not
        # because its goal lacks a design step but because this reader could not find out whether
        # the kit HAS one. Sending a kit without `SR` to `capture SR` is the dead end DEC-0074 and
        # DEC-0079 were decided to end (merge verify round 3, R3-B1).
        raise DispatchError(
            "%s hangs from %s, and whether this project's kit runs an architect step at all could "
            "not be read: %s. The duty is therefore ASKED rather than skipped, which is the "
            "fail-closed direction of DEC-0079 (4) -- a question costs a step, a wrong skip loses "
            "one. Remedy: make the kit's own delivery readable again -- restore the scaffold "
            "record, or put the kit back in the store this process reads (%s); the kit store is "
            "the RUNNING home directory's, so a project moved to another machine or account needs "
            "its kit staged there. Do NOT capture a technical requirement to get past this: "
            "whether this kit has that item type at all is exactly what could not be read."
            % (task["id"], root["id"], unreadable, presets_staging_root()))
    accepted = _accepted_requirement_status()
    raise DispatchError(
        "%s hangs from %s (class %r), and no %s in status %s hangs from that goal -- the architect "
        "step has not happened, so this work order would be built against a goal nobody designed "
        "(FR-0085). Remedy: have the architect derive the technical requirement -- `python "
        "scripts/harness.py capture %s` with `derives_from: %s`, then `transition <id> %s` -- or, "
        "if this goal really needs none, capture it in a class the duty does not ask (%s)."
        % (task["id"], root["id"], root.get("class"), ARCHITECT_STEP_TYPE, accepted,
           ARCHITECT_STEP_TYPE, root["id"], accepted, ", ".join(sorted(SR_EXEMPT_CLASSES)))
    )


# -- the model ladder: rung and effort derived from the state ------------------------------------

def kit_installation(state: ProjectState):
    """(kit, kit_dir) for the kit this project runs, None when NO scaffold record exists at all.

    THE SAME READING AS THE ARCHITECT STEP (`_the_kit_delivery_of_the_architect_step`, DEC-0079):
    the scaffold's ownership record names the kit, the kit store says what that kit ships. The
    difference is what the three unreadable cases mean for a ladder, and it is drawn at the FILE:
      * no record file at all -> None. No kit installed this project; the kernel is being driven
        directly, as this repository drives its own state and as every suite fixture does. There
        is no declaration to read and the kernel invents none (DEC-0078 (4) forbids a default).
      * a record file that is present but unreadable, or a kit the store this process reads does
        not hold -> REFUSED. A project that WAS scaffolded has a ladder somewhere; not finding it is
        the fail-closed direction of DEC-0079 (4), stated in the remedy.
    `tools/test_ladder.py::test_a_project_without_a_scaffold_record_gets_no_rung_and_no_refusal`
    `tools/test_ladder.py::test_a_record_that_is_present_but_unreadable_is_refused_not_ignored`
    """
    from . import presets

    repo = os.path.dirname(os.path.abspath(state.root))
    if not os.path.exists(os.path.join(repo, presets.ROLES_MANIFEST)):
        return None
    try:
        kit = presets.installation(repo)["kit"]
    except Exception as exc:  # noqa: BLE001 -- the record's own refusal, in the dispatch vocabulary
        raise DispatchError(
            "this project's scaffold record (%s) is present but cannot be read, so which kit's "
            "ladder applies to this order could not be decided -- dispatch blocked (DEC-0079 (4): "
            "unreadable means asked, not skipped). The record's own reason: %s"
            % (presets.ROLES_MANIFEST.replace(os.sep, "/"), exc)) from None
    try:
        directory = presets.kit_dir(kit)
    except Exception as exc:  # noqa: BLE001 -- the store's own refusal, same vocabulary
        raise DispatchError(
            "the kit %r this project records is not in the kit store this process reads (%s), so "
            "its ladder declaration could not be read -- dispatch blocked (DEC-0079 (4)). The kit "
            "store is the RUNNING home directory's, so a project moved to another machine or "
            "account needs its kit staged there. The store's own reason: %s"
            % (kit, presets.staging_root(), exc)) from None
    return kit, directory


def _read_yaml_mapping(path: str, what: str) -> dict:
    """A YAML mapping off disk, or a DispatchError naming what could not be read."""
    import yaml

    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DispatchError("%s could not be read (%s: %s) -- dispatch blocked rather than guessed "
                            "at. Remedy: repair the file in the kit store and restage the kit."
                            % (what, exc.__class__.__name__, exc)) from None
    if not isinstance(data, dict):
        raise DispatchError("%s is not a YAML mapping -- dispatch blocked rather than guessed at. "
                            "Remedy: repair the file in the kit store and restage the kit." % what)
    return data


# The keys a per-role exception may carry (DEC-0078 (3): "named exceptions"): a different endpoint
# for that role, a fixed effort that replaces the pair, a fixed start that replaces class and pin.
EXCEPTION_KEYS = frozenset((CLASS_TOP, EFFORT_KEY, RUNG_KEY))

# A CLASS START IS A PAIR, and a bare rung is the pair whose ends coincide (DEC-0097 (1)): the
# `default` is where an order of that class starts when it asks for nothing, the `floor` is how far
# down an ask may take it. Both spellings ship today -- dev and research write the pair for their
# `build`, office writes the scalar everywhere -- and
# `tools/test_ladder.py::test_both_class_spellings_ship_and_the_scalar_still_means_default_equals_floor`
# holds both ends. NOT A BUILD-CLASS RULE: any class may declare a band, and a class whose two ends
# coincide simply has none, which is why nothing below branches on the class name.
CLASS_PAIR_KEYS = frozenset(("default", "floor"))


def _valid_ladder(kit: str, raw: dict) -> dict:
    """The declaration with every field checked, or a refusal naming the field (DEC-0078 (4)).

    Checked at the LEASE and not once at install, because the store is the running home
    directory's and a kit restaged in between is exactly the case that would otherwise carry a
    broken declaration into a dispatch. A refusal names the field so the remedy is a line, not a
    search. `tools/test_ladder.py::test_a_malformed_declaration_names_the_field_it_refuses` walks
    one mutation per rule below.
    """
    def refuse(why):
        raise DispatchError(
            "%s of kit %r %s -- dispatch blocked rather than guessed at (DEC-0078 (4): the kernel "
            "carries no ladder of its own to fall back on). Remedy: correct the declaration in the "
            "kit store and restage the kit." % (LADDER_FILE, kit, why))

    rungs = raw.get("rungs")
    if (not isinstance(rungs, list) or not rungs
            or not all(isinstance(rung, str) and rung for rung in rungs)
            or len(set(rungs)) != len(rungs)):
        refuse("needs `rungs:` as a non-empty list of distinct names, low to high")
    top = raw.get(CLASS_TOP)
    if top not in rungs:
        refuse("names a `top:` (%r) that is not one of its rungs" % (top,))
    effort = raw.get(EFFORT_KEY)
    if (not isinstance(effort, dict)
            or not all(isinstance(effort.get(key), str) and effort.get(key)
                       for key in ("default", LARGE_CLASS))):
        refuse("needs `effort:` with a `default` and a `%s` value" % LARGE_CLASS)
    for key in ("default", LARGE_CLASS):
        if effort[key] not in EFFORT_LEVELS:
            refuse("gives `effort.%s` the value %r, which is not one of %s -- an order's effort ask "
                   "is compared against it (DEC-0091 (2)) and a value outside the ordering cannot "
                   "be" % (key, effort[key], "|".join(EFFORT_LEVELS)))
    escalation = raw.get("escalation") if isinstance(raw.get("escalation"), dict) else {}
    per_rung = escalation.get("failed_runs_per_rung")
    if isinstance(per_rung, bool) or not isinstance(per_rung, int) or per_rung < 1:
        refuse("needs `escalation.failed_runs_per_rung:` as a whole number of at least 1 "
               "(DEC-0034 rule 2)")
    effort_steps = escalation.get(EFFORT_STEPS_KEY)
    if isinstance(effort_steps, bool) or not isinstance(effort_steps, int) or effort_steps < 0:
        refuse("needs `escalation.%s:` as a whole number of at least 0 -- of the failed runs "
               "inside one rung's cycle, how many raise the EFFORT before the rung itself climbs "
               "(DEC-0096 (2)). A kit that declares 0 escalates on the rung axis alone, the way "
               "every kit did before DEC-0096" % EFFORT_STEPS_KEY)
    classes = raw.get("classes")
    if not isinstance(classes, dict) or not classes:
        refuse("needs `classes:` -- the rung each role class starts on (DEC-0034 rules 1/4/5)")
    defaults, floors = {}, {}
    for name, start in classes.items():
        pair = dict(start) if isinstance(start, dict) else {key: start for key in CLASS_PAIR_KEYS}
        if set(pair) != CLASS_PAIR_KEYS:
            refuse("gives class %r a start with the key(s) %s -- the two-value form carries exactly "
                   "`default` and `floor` (DEC-0097 (1)), and a bare rung is the pair whose ends "
                   "coincide" % (name, ", ".join(sorted(map(str, pair))) or "none"))
        for key in sorted(CLASS_PAIR_KEYS):
            if pair[key] not in (CLASS_TOP, CLASS_PIN) and pair[key] not in rungs:
                refuse("gives class %r the %s %r, which is neither `%s`, `%s` nor one of its rungs"
                       % (name, key, pair[key], CLASS_TOP, CLASS_PIN))
        # COMPARED ONLY WHERE BOTH ENDS ARE RUNG NAMES: `pin` is per role and `top` moves with a
        # per-role exception, so neither can be placed on the rung order here. Where they cannot,
        # `ladder_for_order` clamps instead of trusting the file -- the derived default is taken
        # as `max(floor, default)`, so an inverted pair loses its band rather than inverting it.
        if (pair["default"] in rungs and pair["floor"] in rungs
                and rungs.index(pair["default"]) < rungs.index(pair["floor"])):
            refuse("gives class %r the default %r BELOW its floor %r -- the default is where an "
                   "order of that class starts unasked and the floor is how far an ask may take it "
                   "down (DEC-0097 (1)), so this pair names a band that points the wrong way"
                   % (name, pair["default"], pair["floor"]))
        defaults[str(name)] = str(pair["default"])
        floors[str(name)] = str(pair["floor"])
    if BUILD_CLASS not in classes:
        refuse("declares no `%s` class -- DEC-0092 (2) refuses a second concurrent lease of that "
               "class under one goal without a check-scopes record, and a kit that names its "
               "builders otherwise would never be asked" % BUILD_CLASS)
    roles = raw.get("roles")
    if not isinstance(roles, dict) or not roles:
        refuse("needs `roles:` -- every spawnable role of the kit and its class")
    for role, name in roles.items():
        if name not in classes:
            refuse("gives role %r the class %r, which `classes:` does not declare" % (role, name))
    exceptions = raw.get("exceptions")
    exceptions = {} if exceptions is None else exceptions
    if not isinstance(exceptions, dict):
        refuse("needs `exceptions:` as a mapping of role -> rule (or an empty mapping)")
    for role, rule in exceptions.items():
        if role not in roles:
            refuse("excepts role %r, which `roles:` does not list" % (role,))
        if not isinstance(rule, dict) or not rule or set(rule) - EXCEPTION_KEYS:
            refuse("excepts role %r with keys other than %s"
                   % (role, ", ".join(sorted(EXCEPTION_KEYS))))
        for key in (CLASS_TOP, RUNG_KEY):
            if key in rule and rule[key] not in rungs:
                refuse("excepts role %r with a `%s` (%r) that is not one of its rungs"
                       % (role, key, rule[key]))
        if EFFORT_KEY in rule and rule[EFFORT_KEY] not in EFFORT_LEVELS:
            refuse("excepts role %r with an `%s` (%r) that is not one of %s"
                   % (role, EFFORT_KEY, rule[EFFORT_KEY], "|".join(EFFORT_LEVELS)))
    return {
        "rungs": [str(rung) for rung in rungs],
        CLASS_TOP: str(top),
        EFFORT_KEY: {"default": str(effort["default"]), LARGE_CLASS: str(effort[LARGE_CLASS])},
        "failed_runs_per_rung": int(per_rung),
        EFFORT_STEPS_KEY: int(effort_steps),
        # TWO KEYS AND NOT ONE MAPPING OF PAIRS, produced by the single normalisation above so they
        # cannot disagree: `classes` keeps answering the question every reader before DEC-0097 asked
        # of it -- the rung a class STARTS on -- and `class_floors` answers the one DEC-0097 added.
        # Fusing them into pairs would have changed the meaning of `classes[...]` under three
        # readers outside this file that ask only the first question.
        "classes": defaults,
        "class_floors": floors,
        "roles": {str(role): str(name) for role, name in roles.items()},
        "exceptions": {str(role): dict(rule) for role, rule in exceptions.items()},
    }


def ladder_declaration(state: ProjectState):
    """(kit, validated declaration) for the kit this project runs, or None for a kit-less project.

    A kit that is known and ships no `ladder.yaml` is REFUSED here with the sentence DEC-0078 (4)
    asks for; the kit-less case is `kit_installation`'s None and is answered by the caller.
    `tools/test_ladder.py::test_a_kit_without_a_ladder_declaration_is_refused_at_dispatch`
    """
    found = kit_installation(state)
    if found is None:
        return None
    kit, directory = found
    path = os.path.join(directory, LADDER_FILE)
    if not os.path.isfile(path):
        raise DispatchError(
            "kit %r declares no model ladder: there is no %s in its store copy at %s. Every kit "
            "declares its own ladder -- rungs, endpoints, effort pair, named exceptions -- and the "
            "kernel carries none of its own, so no order of this kit is dispatched until it does "
            "(DEC-0078 (4)). Remedy: ship %s beside the kit's constitution (dev-team's is the "
            "shape), restage the kit, then dispatch again." % (kit, LADDER_FILE, directory, LADDER_FILE))
    return kit, _valid_ladder(kit, _read_yaml_mapping(path, "%s of kit %r" % (LADDER_FILE, kit)))


def _store_aliases(kit_directory: str) -> dict:
    """alias -> rung name out of the store's `model_tiers.yaml` (the store is the kit's parent).

    Read only when a pin is not already a rung name -- an installed project's frontmatter is
    alias-free after the scaffold's rewrite, a kit's own source tree is not.
    """
    data = _read_yaml_mapping(os.path.join(os.path.dirname(kit_directory), TIERS_FILE),
                              "%s in the kit store" % TIERS_FILE)
    aliases = data.get("aliases")
    return ({str(alias): str(rung) for alias, rung in aliases.items()}
            if isinstance(aliases, dict) else {})


def count_failed_run_locked(task: dict) -> int:
    """`FAILED_RUNS` of this order after counting the run that ended before this lease.

    Mutates `task` and returns the count; the caller holds the lock and writes the task with the
    lease. WHAT COUNTS AS A FAILED RUN is derived from the automaton and not recorded where FAILED
    is written: a task that is READY again while carrying a `started` stamp has been through
    FAILED since, because the TSK automaton offers IN_PROGRESS no way back to READY except through
    FAILED -- `tools/test_ladder.py::test_every_way_from_a_started_run_back_to_ready_passes_failed`
    derives that from `AUTOMATA` so a changed edge set turns it red. Counting here rather than at
    the write is what makes the count independent of WHO wrote FAILED (`submit_result`, the orphan
    sweep, or a `transition` by hand -- three writers, one reader).

    THE STAMP IS CONSUMED, not remembered: a new lease is a new dispatch (the same reason
    `create_lease` drops `CHILD_ENDED`), `spawn_outcome` stamps the next run's own start, and a
    lease that produced no child (LEASED -> READY) leaves no stamp behind to count. A first cut
    remembered the stamp it had counted and compared the next one against it -- and `_now_iso` has
    seconds, so two runs inside one second read as one and the second FAILED did not climb
    (measured red in `test_an_exception_moves_one_roles_top_and_the_climb_stops_there`). Nothing in
    the kernel or the kits reads `started` back (grep 2026-09-05); the moment the run began stays
    on the lease's `dispatched_at` and in the audit trail.
    `tools/test_ladder.py::test_a_lease_that_produced_no_child_counts_no_failed_run`
    """
    count = int(task.get(FAILED_RUNS) or 0)
    if task.pop("started", None):
        count += 1
    task[FAILED_RUNS] = count
    return count


# A TEST IS A THING THAT IS RUN AND YIELDS A VERDICT, and that is the property the three readers
# below encode -- NOT "the word `test` occurs". The first version of this reader searched for the
# bare word and granted the cheap rung to `docs/test-plan.md` and to the criterion "no test needed
# for this rename" (both measured against the shipped dev declaration, verifier round 1, B1). A
# document whose NAME contains the word is not a test, and a sentence that DENIES one is not an
# acceptance.
# WHAT THE THREE READERS DO NOT READ, said rather than implied: a test named without the word (a
# compound -- `unittest.py`, and the German `Regressionstest` too, because no rule here could tell
# that tail from the one in `latest`; a suite called `checks/`), a verdict word outside
# `_VERDICT_WORDS`, and whether the named file exists or passes. Each of those REFUSES the ask and
# leaves the order on the more expensive default, which is the direction this reader fails in on
# purpose -- B1 was the other one. The compound row is measured, not claimed:
# `tools/test_ladder.py::test_the_acceptance_reader_reads_a_test_and_not_the_word`. That last one is the same trade as before: this reader
# decides a RUNG, not a merge, and the verifier checks the slice either way.
_WORD_TEST_RX = re.compile(r"(?<![a-z0-9])tests?(?![a-z0-9])", re.IGNORECASE)
# A TEST MODULE'S OWN NAME: the separator after (or before) the word is what every runner's
# convention has in common, and it is exactly what a document title does not have --
# `test-plan.md` and `testimonials.md` fail it, `test_x.py`, `x_test.go`, `x.test.ts`, `x_spec.rb`
# pass it.
_TEST_MODULE_RX = re.compile(r"\A(?:test[_.].+|.+[_.]test|.+[_.]spec)\.[a-z0-9]+\Z", re.IGNORECASE)
# A RUNNER OR A NODE ID -- a test named as something one EXECUTES.
_RUNNER_RX = re.compile(r"(?<![a-z0-9])(?:pytest|::test_|npm test|go test|cargo test)", re.IGNORECASE)
# THE VERDICT A TEST YIELDS, in the two languages the kits are written in. An enumeration, and the
# only one here -- held at BOTH ends by
# `tools/test_ladder.py::test_the_acceptance_reader_needs_a_verdict_word_and_every_listed_one_earns_its_place`:
# every entry must be the sole reason one sentence counts, and no entry may be one the sentence
# would pass without.
_VERDICT_WORDS = ("red", "green", "rot", "gruen", "grün", "fail", "fails", "failing", "passes",
                  "passing", "faellt", "fällt", "schlaegt fehl", "schlägt fehl")
_VERDICT_RX = re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z0-9])"
                         % "|".join(word.replace(" ", r"\s+") for word in _VERDICT_WORDS),
                         re.IGNORECASE)
# A SENTENCE THAT DENIES, AND THE TWO GRAMMATICAL CLASSES ARE READ DIFFERENTLY -- BUG-0278. A
# CLAUSAL negator denies the clause it stands in, so "kein Test wird rot" and "tests are not
# required here" are refusals whatever else the sentence says. A PREPOSITIONAL one denies only its
# own COMPLEMENT, which is why one list would not do: read as clausal, `ohne` refused this
# repository's own red-first formula -- "ein Test wird rot, ohne den Fix" -- while its English twin
# was granted, because `without` was in neither list.
#
# A VOCABULARY AND NOT A PATTERN, so the tripwire below can walk it: an entry ending in `*` stands
# for the word AND its inflections (`kein*` is keine/keinen/keiner), which is the one spelling
# convention here. The list is held at BOTH ends by
# `tools/test_ladder.py::test_every_listed_denial_word_is_the_reason_its_sentence_is_refused` --
# every entry is the SOLE reason one sentence is refused, and no entry is carried by a neighbour.
# It is an enumeration that fails in the DANGEROUS direction when it is short: a missing word makes
# a sentence that denies a test read as one that promises one, and that GRANTS the cheap rung.
# Round 1 of this item's verification measured exactly that gap -- `never` and `none` were listed
# and their German twins `nie`/`niemals`/`nirgend*` were not, so "Ein Test wird niemals rot" bought
# the cheap rung.
_CLAUSAL_DENIERS = ("no", "not", "never", "none", "nothing", "neither", "nor",
                    "nicht", "nie", "niemals", "kein*", "nirgend*", "weder")
_PREPOSITIONAL_DENIERS = ("ohne", "without")
# THE CORRELATIVE NEGATION, which both languages build the same way: `neither ... nor`,
# `weder ... noch`. Round 2 of this item's verification measured the construction granting the
# cheap rung; round 3 measured each HALF doing the same on its own -- "Neither of the tests goes
# red after the rename" and "No fix ships; nor does a test go red", where the sentence split at `;`
# hands `nor` its own clause. So the OPENING half of every pair is an ordinary negation and stands
# in `_CLAUSAL_DENIERS` above -- `neither` and `weder` never appear outside one. The CLOSING half
# is not symmetric across the two languages and is not derivable: English `nor` denies on its own
# and is listed; German `noch` does NOT -- "noch ein Test wird rot" promises a second test -- and
# is deliberately absent. This table is what keeps the construction from being half covered: its
# tripwire asserts every OPENING half is a listed denier, and carries one measured row per pair for
# the closing half, which is the one thing a word list cannot decide about itself.
# `tools/test_ladder.py::test_every_listed_denial_word_is_the_reason_its_sentence_is_refused`
# WHAT IT COSTS, on the cheap side and measured: "neither here nor there the test goes red" is an
# idiom that denies nothing, and it is refused -- an unnecessary expensive rung, never a grant.
_CORRELATIVE_DENIERS = (("neither", "nor"), ("weder", "noch"))


def _word_alternation(words) -> str:
    """The alternation of a denial vocabulary: a trailing `*` becomes "and its inflections"."""
    return "|".join(word[:-1] + r"\w*" if word.endswith("*") else word for word in words)


_DENIES_RX = re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % _word_alternation(_CLAUSAL_DENIERS),
                        re.IGNORECASE)
_PREPOSITION_DENIES_RX = re.compile(
    r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % _word_alternation(_PREPOSITIONAL_DENIERS), re.IGNORECASE)
# WHERE A CLAUSE ENDS, for the complement above: the punctuation a writer separates clauses with.
_CLAUSE_END_RX = re.compile(r"[,;:.!?]")
# WHERE A PREPOSITION'S COMPLEMENT ENDS, and it is a DEFINITION rather than a width. A preposition
# governs exactly ONE noun phrase, and a noun phrase is opened by its determiner -- so the
# complement runs to the clause end or to the NEXT determiner, whichever comes first, with the
# determiner that opens the complement itself skipped. Nothing here has to find the finite verb,
# which is what the two rejected readings both tried to approximate.
#
# WHAT WAS REJECTED AND WHY, both measured on this item: reading the complement to the END OF THE
# CLAUSE made the FRONTED form swallow its main clause ("Without the fix a test goes red." was
# refused, round 1 of the verification); reading it as a WIDTH of three words flipped to the
# DANGEROUS side from the fourth word on -- "The result goes red without any new regression test"
# was granted although it denies a test (round 2). A width is the wrong shape for a phrase whose
# length is free; the determiner is what really ends one.
#
# A NOUN PHRASE MAY CONTAIN A SECOND ONE, and that is where the determiner rule needed its own
# answer (round 3 of this item's verification measured the class, which is bigger than the German
# genitive the first note named): both languages postmodify a noun with another noun phrase --
# German by the GENITIVE ("ohne die Hilfe eines Tests"), English by `of` ("without the help of a
# test") -- and the complement has to run through it, or a denial reads as a promise. So a
# determiner does NOT end the complement when it is an unambiguous genitive form or stands
# directly after `of`.
#
# THE PRICE OF THAT, dangerous direction FIRST: the AMBIGUOUS German genitive articles are not
# read as genitives -- `der` and `einer` are also nominative and dative, and nothing here can tell
# which -- so "ohne die Hilfe einer Probe, die rot wird" ends its complement early and can still
# buy the cheap rung. Unambiguous forms (`des`, `eines`, `dessen`, `deren`) are covered. The other
# direction is cheap and stated second: a determiner MISSING from the list below only lengthens a
# complement, which can cost an unnecessary refusal and the expensive rung, never a grant.
#
# THE LIST IS A CLOSED GRAMMATICAL CLASS, not a vocabulary of content words: the articles and
# quantifiers of the two languages the kits are written in. `kein*`/`no` are deniers already and
# are not repeated here.
#
# A TRAILING `-` TAKES THE GERMAN DECLENSION AND NOT ANY TAIL, which is a NARROWER convention than
# the deniers' `*` on purpose: with `\w*` the entry `ein` swallowed the adjective `einzigen`, so
# "ohne einen einzigen neuen Test" ended its complement before the test word and granted the cheap
# rung -- measured while building this. A determiner's tail is one of five endings, and that set is
# the definition.
# `tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`
_DECLENSION = "(?:e|en|em|er|es)?"
_DETERMINERS = ("the", "a", "an", "any", "some", "each", "every", "this", "that", "these", "those",
                "der", "die", "das", "den", "dem", "des", "ein-", "jed-", "dies-", "jen-", "all-")
_DETERMINER_RX = re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % "|".join(
    word[:-1] + _DECLENSION if word.endswith("-") else word for word in _DETERMINERS),
    re.IGNORECASE)
# A GERMAN COMPOUND'S HEAD IS ITS LAST ELEMENT, so `Regressionstest` and `Unittest` ARE the test
# word -- invisible to `_WORD_TEST_RX`, which asks for a word boundary an agglutinating language
# does not put there. Two conditions keep the English tail-collisions out, and both are measured
# rather than guessed: the compound is a NOUN (capitalised, as every German noun is), and its stem
# is at least `_COMPOUND_STEM_MIN` characters -- `pro`test, `con`test, `la`test all carry 2-3.
# WHAT STILL GETS THROUGH, said rather than left to be found: a capitalised English superlative at
# the start of a sentence ("Greatest ...") carries a 4-character stem and would be read as the test
# word; it needs a verdict word in the same sentence to matter, and the direction it fails in is
# the cheap rung, which is why it is named here instead of chased with a word list.
# `tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`
_COMPOUND_STEM_MIN = 4
_COMPOUND_TEST_RX = re.compile(
    r"(?<![A-Za-z0-9])[A-ZÄÖÜ][a-zäöüß]{%d,}tests?(?![a-z0-9])" % (_COMPOUND_STEM_MIN - 1))


def _path_names_a_test(word: str) -> bool:
    """Is this PATH a test artefact -- a component that is a test tray, or a test module's name.

    The word is split on both separators, because an order writes either. A document under a
    `docs/` tray keeps its name: `docs/test-plan.md` is a plan ABOUT tests and buys nothing.
    """
    parts = [part for part in re.split(r"[\\/]+", word.strip().strip("\"'`")) if part]
    if not parts:
        return False
    if any(_WORD_TEST_RX.fullmatch(part) for part in parts[:-1]):
        return True
    return bool(_TEST_MODULE_RX.match(parts[-1]))


def _mentions_a_test(text: str) -> bool:
    """Does this span name a test at all -- as a runner, as a path, or as the word?

    The one reader both the positive question and the denial question below use, so "what counts
    as naming a test" cannot drift between them.
    """
    if _RUNNER_RX.search(text):
        return True
    if any(_path_names_a_test(word) for word in text.split()):
        return True
    return bool(_WORD_TEST_RX.search(text) or _COMPOUND_TEST_RX.search(text))


def _denies_a_test(sentence: str) -> bool:
    """Does this sentence refuse a test -- clausally, or by a preposition over its own complement?

    See `_DENIES_RX` for why the two classes are read differently (BUG-0278).
    """
    if _DENIES_RX.search(sentence):
        return True
    for first, second in _CORRELATIVE_DENIERS:
        opened = re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % first, sentence, re.IGNORECASE)
        if opened and re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % second,
                                sentence[opened.end():], re.IGNORECASE):
            return True
    for negator in _PREPOSITION_DENIES_RX.finditer(sentence):
        rest = sentence[negator.end():]
        clause_end = _CLAUSE_END_RX.search(rest)
        within_clause = rest[:clause_end.start()] if clause_end else rest
        if _mentions_a_test(_complement_of(within_clause)):
            return True
    return False


# A DETERMINER THAT OPENS A POSTMODIFIER rather than the next phrase -- see the note above. The
# English `of` stands before it; the German genitive is IN it, and only the unambiguous forms count.
_POSTMODIFIER_RX = re.compile(r"(?:\bof\s+$)", re.IGNORECASE)
_GENITIVE_DETERMINERS = ("des", "eines", "dessen", "deren")


def _complement_of(within_clause: str) -> str:
    """The ONE noun phrase a preposition governs -- see `_DETERMINERS` for why it ends there.

    The determiner that OPENS the complement is skipped, because that one belongs to it; the next
    one begins the phrase after it, and that is where this stops -- UNLESS that next one opens a
    postmodifier of the same phrase (an `of`-phrase or a genitive), in which case the complement
    runs on through it.
    `tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin`
    """
    text = within_clause.lstrip()
    opener = _DETERMINER_RX.match(text)
    rest = text[opener.end():] if opener else text
    cut = 0
    while True:
        following = _DETERMINER_RX.search(rest, cut)
        if following is None:
            return rest
        word = following.group(0).lower()
        before = rest[:following.start()]
        if word in _GENITIVE_DETERMINERS or _POSTMODIFIER_RX.search(before):
            cut = following.end()       # a postmodifier of the same phrase -- keep going
            continue
        return rest[:following.start()]


def _sentence_names_a_test(sentence: str) -> bool:
    """Does THIS sentence name a test as an artefact or as an action, and not deny one."""
    if _denies_a_test(sentence):
        return False
    if _RUNNER_RX.search(sentence):
        return True
    if any(_path_names_a_test(word) for word in sentence.split()):
        return True
    return bool((_WORD_TEST_RX.search(sentence) or _COMPOUND_TEST_RX.search(sentence))
                and _VERDICT_RX.search(sentence))


def acceptance_is_test_shaped(task: dict, root: dict) -> bool:
    """Does this order's acceptance name a TEST -- the condition DEC-0097 (2) puts on an ask below
    the class default.

    TWO FEEDS, ONE PROPERTY: the order's `expected_outputs` must name a test ARTEFACT (a path in a
    test tray or a test module's own name), and an acceptance criterion this order refers to must
    carry a SENTENCE that names a test as an artefact, as a runner, or as an action with a verdict
    -- and does not deny one. The reason for the condition is FR-0091 precision 2 and Anthropic's
    own threshold ("if you could describe the diff in one sentence"): a slice small enough for the
    cheap rung can be handed a pass/fail oracle, and one that can only be described in prose cannot.
    `tools/test_ladder.py::test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance`
    """
    for output in field_elements(task.get("expected_outputs")):
        if _path_names_a_test(str(output)):
            return True
    wanted = {str(ref) for ref in field_elements(task.get("acceptance_refs"))}
    for criterion in field_elements(root.get("acceptance_criteria")):
        if not isinstance(criterion, dict) or str(criterion.get("id")) not in wanted:
            continue
        flat = re.sub(r"\s+", " ", str(criterion.get("text") or ""))
        if any(_sentence_names_a_test(sentence)
               for sentence in re.split(r"(?<=[.!?;])\s+", flat)):
            return True
    return False


def ladder_for_order(state: ProjectState, task: dict, root: dict, failed_runs: int) -> dict:
    """The rung and effort THIS order runs on, from the kit's declaration and the state (DEC-0077).

    TWO AXES, derived and never chosen by hand:
      * the RUNG hangs on the role's pin and the kit's endpoints (DEC-0077 (1), DEC-0047): the
        role's class decides the rung it STARTS on -- `top` for planning and architecture (DEC-0034
        rule 1), a named floor for design and QA (rules 4/5), the class's own rung for the build
        (DEC-0095 (1)) -- and a class floor never LOWERS a pin; after that every
        `failed_runs_per_rung` failed runs of this order
        climb one rung (rule 2), capped at the role's top. THE TOP DOES CAP DOWNWARDS, and that is
        the one place a pin can be lowered: a kit whose `top` (or whose per-role `top` exception)
        lies BELOW a role's pin dispatches that role on the top, not on its pin. No shipped kit
        does that today and the answer is not silent -- the lease's `why` names both, and
        `tools/test_ladder.py::test_a_top_below_a_pin_lowers_it_and_the_answer_says_so` reads it --
        but a hand-written `model_map` reaches the case, so it is written here rather than
        discovered. Rule 3 (the fall back after the risky
        phase, a CR lifting the architecture back up for that CR) needs no state of its own: the
        rung is derived per ORDER at every lease and stored nowhere else, and an architecture-class
        order under a CR starts on the top rung like any other.
      * the EFFORT hangs on the goal: the pair's `large` value when the root's `class` is
        `LARGE_CLASS`, its `default` otherwise, unless the role's exception fixes one (the office
        filing floor, DEC-0047).
      * THE ORDER'S ASK IS THE THIRD INPUT (DEC-0091 (2), DEC-0097 (2)): the rung is the higher of
        the class DEFAULT and the order's `rung`, the effort the higher of the goal's and the
        order's `effort`; the climb starts where the order starts, `top` and the kit's highest
        declared effort still cap --
        `tools/test_light_kit.py::test_an_order_rung_lifts_the_start_and_the_climb_begins_there`,
        `::test_an_order_effort_lifts_the_goals_effort_and_the_kits_highest_effort_caps_it`. An ask
        BELOW the default is granted down to the class FLOOR, and only when the order's acceptance
        names a test (`acceptance_is_test_shaped`); below the floor nothing is granted. Both
        refusals stand in the `why` --
        `tools/test_ladder.py::test_an_ask_below_the_default_is_granted_only_for_a_test_shaped_acceptance`.
      * THE TWO AXES ESCALATE IN ORDER, effort before rung (DEC-0096): the failed runs inside one
        rung's cycle raise the effort first, and only the threshold itself raises the rung -- the
        block at the end of this function carries the derivation and the reason.
    A kit-less project (no scaffold record) gets `{"absent": why}` and the role runs on its own
    pin; every other failure to read is a refusal, never a guess (DEC-0078 (4)).
    `tools/test_ladder.py` holds one red-first test per rule named above.
    """
    found = ladder_declaration(state)
    if found is None:
        from .presets import ROLES_MANIFEST

        return {"absent": "no scaffold record (%s) names a kit for this project, so there is no "
                          "ladder declaration to read; the role runs on its own pin"
                          % ROLES_MANIFEST.replace(os.sep, "/")}
    kit, ladder = found
    role = str(task.get("assigned_role") or "")
    role_class = ladder["roles"].get(role)
    if role_class is None:
        raise DispatchError(
            "role %r has no class in %s of kit %r, so the rung it starts on cannot be derived -- "
            "dispatch blocked (DEC-0034 rules 1/4/5 hang on the class; DEC-0078 (4)). Remedy: list "
            "the role under `roles:` in the kit's declaration with one of its classes (%s) and "
            "restage the kit." % (role, LADDER_FILE, kit, ", ".join(sorted(ladder["classes"]))))
    definitions = agents_dir(os.path.dirname(os.path.abspath(state.root)))
    pin = role_pin(definitions, role)
    if pin is None:
        raise DispatchError(
            "the installed definition of role %r (%s) could not be read or pins no `model:`, so the "
            "rung cannot be derived from it -- dispatch blocked (DEC-0077 (1): the rung hangs on "
            "the role pin). Remedy: restore the role file the scaffold installs, or re-run the "
            "scaffold." % (role, os.path.join(definitions, role + ".md").replace(os.sep, "/")))
    rungs = ladder["rungs"]
    base = pin if pin in rungs else _store_aliases(os.path.dirname(os.path.join(
        kit_installation(state)[1], LADDER_FILE))).get(pin)
    if base not in rungs:
        raise DispatchError(
            "role %r pins %r, which is neither a rung of kit %r's ladder (%s) nor an alias %s "
            "resolves to one -- dispatch blocked (DEC-0076: three rungs, named by the reference "
            "vocabulary). Remedy: pin the role to one of the rungs or to an alias of one."
            % (role, pin, kit, ", ".join(rungs), TIERS_FILE))
    exception = ladder["exceptions"].get(role, {})
    top = str(exception.get(CLASS_TOP, ladder[CLASS_TOP]))
    if RUNG_KEY in exception:
        floor = default_rung = str(exception[RUNG_KEY])
        floor_why = "the exception sets the floor"
    else:
        # THE CLASS DECLARES A BAND (DEC-0097 (1)): its `floor` is how far down an ask may take
        # this order, its `default` where the order starts without one. `pin` and `top` resolve per
        # ROLE, which is why the resolution happens here and not in the validator. Both ends are
        # clamped rather than trusted: the floor never lowers the role's pin (the rule DEC-0034
        # rule 4/5 always had), and the default never falls below the floor that came out of it.
        rule = ladder["classes"][role_class]
        rule_floor = ladder["class_floors"][role_class]
        def resolve(name):
            return top if name == CLASS_TOP else base if name == CLASS_PIN else name

        floor = rungs[max(rungs.index(base), rungs.index(resolve(rule_floor)))]
        default_rung = rungs[max(rungs.index(floor), rungs.index(resolve(rule)))]
        # THE RESOLVED RUNG AND NOT THE FILE'S WORD (verifier round 1, N-b): `pin` and `top` are
        # per role, and the clamp above is exactly where the declaration and the answer part
        # company -- a `why` echoing `pin` would name a rung this order is not starting on.
        floor_why = "class %s starts on %s" % (role_class, default_rung)
        if rule != default_rung:
            floor_why += " (declared %s)" % rule
        if default_rung != floor:
            floor_why += " with the floor at %s" % floor
    # THE ORDER'S ASK LIFTS THE START (DEC-0091 (2)), AND LOWERS IT ONLY INSIDE THE CLASS'S BAND
    # (DEC-0097 (2)): the climb of rule 2 then begins where the order starts, and `top` caps it as
    # it caps every climb -- an ask above the role's top is not refused (it is inside the
    # vocabulary) but it is not granted either, and the `why` says which of the two it was. An ask
    # BELOW the class default is granted down to the class floor when the order's acceptance is
    # TEST-SHAPED, and otherwise left ungranted with the reason in the `why`: that is the band that
    # keeps the cheap rung reachable for a mechanical slice and unreachable for a description
    # (FR-0091 precision 2). Below the floor nothing is granted at all, whatever the acceptance
    # says -- the floor is the rule DEC-0091 (2) always had.
    order_rung, order_effort = order_tiers(task)
    if order_rung is not None and order_rung not in rungs:
        raise DispatchError(
            "%s asks for `%s: %s`, which is not a rung of kit %r's ladder (%s) -- dispatch blocked "
            "(DEC-0091 (3)). Remedy: correct the order while it is DRAFT, or drop the field."
            % (task.get("id"), RUNG_KEY, order_rung, kit, ", ".join(rungs)))
    if order_effort is not None and order_effort not in EFFORT_LEVELS:
        raise DispatchError(
            "%s asks for `%s: %s`, which is not one of %s -- dispatch blocked (DEC-0091 (3)). "
            "Remedy: correct the order while it is DRAFT, or drop the field."
            % (task.get("id"), EFFORT_KEY, order_effort, "|".join(EFFORT_LEVELS)))
    start, start_why = default_rung, floor_why
    if order_rung is None:
        pass
    elif rungs.index(order_rung) > rungs.index(default_rung):
        start = order_rung
        start_why += ", the order asks %s" % order_rung
    elif rungs.index(order_rung) == rungs.index(default_rung):
        start_why += ", the order's ask %s is not above it" % order_rung
    elif rungs.index(order_rung) < rungs.index(floor):
        start_why += (", the order asks %s below the floor %s; refused: a floor is not a band"
                      % (order_rung, floor))
    elif acceptance_is_test_shaped(task, root):
        start = order_rung
        start_why += (", the order asks %s below the default %s; allowed: the acceptance names a test"
                      % (order_rung, default_rung))
    else:
        start_why += (", the order asks %s below the default %s; refused: the acceptance names no "
                      "test, only a description" % (order_rung, default_rung))
    per_rung = ladder["failed_runs_per_rung"]
    chosen = rungs[min(rungs.index(start) + int(failed_runs) // per_rung, rungs.index(top))]
    # THE RUNG STEPS THAT WERE GRANTED, not the ones the threshold derived -- `top` caps the climb,
    # and everything below that reads this count (the effort cycle, the shown sentence) has to read
    # the granted one or it credits the order with a climb it did not get.
    granted_rungs = rungs.index(chosen) - rungs.index(start)
    goal_class = str(root.get("class") or "")
    if EFFORT_KEY in exception:
        effort, effort_why = str(exception[EFFORT_KEY]), "the exception fixes it"
    elif goal_class == LARGE_CLASS:
        effort, effort_why = ladder[EFFORT_KEY][LARGE_CLASS], "the goal's class is %s" % LARGE_CLASS
    else:
        effort, effort_why = ladder[EFFORT_KEY]["default"], (
            "the goal's class is %s" % goal_class if goal_class else "the goal carries no class")
    # THE ORDER'S EFFORT ASK LIFTS THE GOAL'S THE SAME WAY, and the kit's own pair is its ceiling:
    # the higher value a declaration names is the highest effort that kit runs at all (office:
    # `high`, DEC-0078 (2) -- "xhigh is not an office effort"), so an ask above it lands on the
    # ceiling with the `why` saying so, exactly as a rung ask above `top` does. A ROLE'S EFFORT
    # EXCEPTION IS FLOOR AND CEILING AT ONCE: the office filing pair runs `low` because its work is
    # reading under double control (DEC-0047), and an order that asked `high` for it would buy
    # nothing the pair is there for -- measured lifted at the mid-goal check (B2) and closed here;
    # `tools/test_ladder.py::test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs`
    # carries the ask case. The rung exception, by contrast, is a floor the ask may lift
    # (`floor_why` above), because a rung fixed by exception is a start, not a reason to stay low.
    ceiling = max(ladder[EFFORT_KEY].values(), key=EFFORT_LEVELS.index)
    if EFFORT_KEY in exception:
        ceiling = str(exception[EFFORT_KEY])
    if order_effort is not None and EFFORT_LEVELS.index(order_effort) > EFFORT_LEVELS.index(effort):
        if EFFORT_LEVELS.index(order_effort) > EFFORT_LEVELS.index(ceiling):
            effort, effort_why = ceiling, (
                "the order asks %s, but the exception fixes %s (DEC-0047)" % (order_effort, ceiling)
                if EFFORT_KEY in exception else
                "the order asks %s, capped at the kit's highest effort %s" % (order_effort, ceiling))
        else:
            effort, effort_why = order_effort, "the order asks %s" % order_effort
    # DEC-0096: THE TWO AXES ESCALATE IN ORDER -- effort first, rung after, and the declaration's
    # two thresholds say how. `failed_runs_per_rung` failed runs buy one RUNG step (above); of the
    # failed runs inside the current rung's cycle, the first `effort_steps_before_rung` buy one
    # EFFORT step each. The count is the failed runs MINUS the ones already paid out as GRANTED
    # rung steps, so it resets with every granted step -- that reset is the "effort back at the
    # kit's default" of DEC-0096 (1) and it needs no state of its own. AT THE TOP RUNG NOTHING IS
    # GRANTED ANY MORE, so the count keeps growing and the effort stays where the threshold put it
    # -- its ceiling on every shipped kit, and in general `min(default + effort_steps_before_rung,
    # ceiling)` -- instead of falling back: an order that has run out of ladder never gets a weaker
    # pair than the run before it. Keyed on the derived cycle (`failed_runs % per_rung`) it did
    # exactly that --
    # measured by the verifier of round 1: dev FAIL 5 fable/xhigh, FAIL 6 fable/high.
    # A declaration of 0 steps derives exactly what the kernel derived before DEC-0096, and where
    # no cap bites the two spellings agree (`granted_rungs * per_rung == failed_runs // per_rung *
    # per_rung`), which is why the change is invisible below the top rung.
    # `tools/test_ladder.py::test_a_failed_run_raises_the_effort_before_it_raises_the_rung`
    # THE CEILING IS THE KIT'S OWN PAIR, not a third number: the higher value a kit declares is the
    # highest effort it runs at all (DEC-0078 (2)), and a role whose exception FIXES an effort has
    # that value as its ceiling -- so the escalation buys nothing where the kit declared no
    # headroom. All three kits ship a pair with exactly ONE step of headroom today, which is why
    # DEC-0096 (1) narrates FAIL 2 as "the raised effort" rather than as a second step.
    on_this_rung = int(failed_runs) - granted_rungs * per_rung
    here = EFFORT_LEVELS.index(effort)
    raised = min(here + min(on_this_rung, ladder[EFFORT_STEPS_KEY]), EFFORT_LEVELS.index(ceiling))
    effort_steps = max(raised - here, 0)          # the escalation RAISES the effort or leaves it
    if effort_steps:
        effort, effort_why = EFFORT_LEVELS[raised], (
            "%s, raised %d step(s) by %d failed run(s) on this rung"
            % (effort_why, effort_steps, on_this_rung))
    # The derivation as ONE sentence for the two readers that show it (DEC-0096 (4)): the lease's
    # `why` and the spawn gate's checkpoint line (c). It states the two steps and the two
    # thresholds they came from, so a PM reading "FAIL 2: rung +0" can see WHY the rung stood still.
    # BOTH NUMBERS ARE THE STEPS GRANTED, not the steps derived: `top` caps the rung climb and the
    # kit's pair caps the effort, so a derived "+2" that the cap swallowed would be a claim about a
    # model the order is not running on. Where the two differ, the cap is beside it in the `why`
    # and on the checkpoint's (c) line ("top %s"), which is what a reader needs to tell a ladder
    # that stood still from one that was held.
    escalation_line = ("FAIL %d: rung +%d, effort +%d -- this kit spends the first %d failed "
                       "run(s) of every %d on the effort axis (DEC-0096)"
                       % (int(failed_runs), granted_rungs, effort_steps,
                          ladder[EFFORT_STEPS_KEY], per_rung))
    return {
        RUNG_KEY: chosen,
        EFFORT_KEY: effort,
        "kit": kit,
        "role_class": role_class,
        "pin": pin,
        "base": base,
        "floor": floor,
        "default": default_rung,
        "start": start,
        "order": {RUNG_KEY: order_rung, EFFORT_KEY: order_effort},
        "failed_runs": int(failed_runs),
        "escalation": escalation_line,
        CLASS_TOP: top,
        "goal_class": goal_class or None,
        "why": "%s: pin %s, %s, %s, top %s; effort %s: %s"
               % (chosen, pin, start_why, escalation_line, top, effort, effort_why),
    }


def ladder_line(lease: dict) -> str:
    """The lease's ladder answer as one line for a human -- the `dispatch` command's stderr."""
    ladder = lease.get(LADDER_KEY)
    if not isinstance(ladder, dict):
        return "ladder: no answer on this lease (minted before the rule; a new lease carries one)"
    if "absent" in ladder:
        return "ladder: no rung -- %s" % ladder["absent"]
    return "ladder: rung %s, effort %s (%s)" % (ladder[RUNG_KEY], ladder[EFFORT_KEY], ladder["why"])


# The question the checkpoint ends with. The PM answers it to itself and not in a field
# (DEC-0092 (1)): a required "why" is boilerplate nobody can check and trains the habit it is meant
# to break, so the four lines above it are FACTS and this is the only sentence that asks anything.
CHECKPOINT_QUESTION = (
    "Does the rung fit the slice, and is one builder still the right count? If the last run FAILED, "
    "which axis: \"confidently wrong no matter how much context you give it\" -> a larger model; "
    "\"skipped a file, not running the tests, or bailing on a refactor partway through\" -> more "
    "effort (Anthropic's two escalation signals, FR-0091 precision 1). "
    "(DEC-0092 (3): a mirror with numbers -- nothing here blocks.)")


def reflection_checkpoint(state: ProjectState, task: dict, root: dict, lease: dict) -> list:
    """The four fact lines the spawn gate hands the PM before a BUILDER starts (DEC-0092 (3)).

    (a) the goal's measured file sets, (b) the order's size signals, (c) the rung and effort about
    to be leased with the class's default and floor, the order's ask and the FAIL-count derivation
    beside them (DEC-0096 (4), DEC-0097 (3)), (d) the distribution of the last N leases --
    and the one question. Everything here is READ off the state; nothing is judged and nothing is
    refused, which is why the gate that prints it does so after `validate_dispatch` has already
    said yes (`gate_dispatch.handle_pre_tool_use`). The kit-less case has no ladder answer and
    therefore no builder to mirror; the caller decides that off the lease's class, not here.
    `tools/test_light_kit.py::test_the_shipped_spawn_gate_prints_the_four_line_checkpoint_and_never_blocks_on_it`
    """
    from . import report, scopes

    ladder = lease.get(LADDER_KEY) or {}
    sets = scopes.goal_partition(state, str(root.get("id")))
    orders_open = sum(len(group) for group in sets)
    # BOUNDED LIKE THE CHECK'S OWN PRINTOUT (`scopes.PATHS_SHOWN`): the line goes into the model's
    # context on every builder spawn, so above that many sets only a count is printed, and above
    # that many open orders the groups are not spelled at all (measured 324 chars at 25 orders,
    # mid-goal check B6). The partition is computed NOW, not read from a record -- which is why
    # the line says so: a PM reading "N disjoint sets" must not take the second lease for granted.
    shown = scopes.PATHS_SHOWN
    if len(sets) > 1:
        if orders_open > shown:
            groups = "not listed above %d open orders" % shown
        else:
            groups = "; ".join(" + ".join(group) for group in sets[:shown])
            if len(sets) > shown:
                groups += "; ... and %d more sets" % (len(sets) - shown)
        sets_line = ("this goal splits into %d disjoint sets among %d open order(s) (computed now; "
                     "a second builder still needs a check-scopes record): %s"
                     % (len(sets), orders_open, groups))
    else:
        sets_line = ("this goal is one set: %d open order(s) share files or there is only one -- "
                     "a second builder here has no disjoint slice to take" % orders_open)
    order = ladder.get("order") or {}
    lines = [
        "(a) %s" % sets_line,
        "(b) this order: %d allowed-scope entr%s, %d expected output(s), goal class %s"
        % (len(field_elements(task.get("allowed_scope"))),
           "y" if len(field_elements(task.get("allowed_scope"))) == 1 else "ies",
           len(field_elements(task.get("expected_outputs"))), ladder.get("goal_class") or "none"),
        # DEFAULT AND FLOOR SIDE BY SIDE (DEC-0097 (3)): the PM reading this has to see the band an
        # ask can move in, not just the one rung the order would otherwise start on -- the two
        # coincide for every class but the build in dev and research, and a line that showed only
        # one of them would read the same in both cases. THE BAND IS NAMED ONLY WHERE THERE IS ONE
        # (verifier round 1): a class whose ends coincide has nothing to ask down to, and a line
        # offering it one would be a claim the dispatcher refuses.
        "(c) about to lease: rung %s, effort %s -- the ladder for %s starts on %s by default%s "
        "(pin %s, class %s), top %s; the order asked rung %s / effort %s; %s"
        % (lease.get(RUNG_KEY), lease.get(EFFORT_KEY), task.get("assigned_role"),
           ladder.get("default"),
           (" and may be asked down to %s when the order's acceptance NAMES A TEST"
            % ladder.get("floor")) if ladder.get("floor") != ladder.get("default")
           else ", with no band below it",
           ladder.get("pin"), ladder.get("role_class"), ladder.get(CLASS_TOP),
           order.get(RUNG_KEY) or "nothing", order.get(EFFORT_KEY) or "nothing",
           ladder.get("escalation") or "no escalation answer on this lease"),
        "(d) %s" % report.lease_distribution(state)["line"],
        CHECKPOINT_QUESTION,
    ]
    return lines


def _assert_the_ladder_answer_holds_locked(state: ProjectState, task: dict, root: dict,
                                           lease: dict) -> None:
    """The rung and effort the lease carries are what the state says NOW (DEC-0077 (2)).

    Re-derived at the SPAWN the way the approval, the architect step and the dependencies are, so a
    declaration restaged, a role re-pinned or a goal re-classed between lease and spawn does not
    carry a stale answer into the child. The failed-run count is the task's, already counted at the
    lease; nothing is counted here. A lease minted before this rule carries no answer at all and is
    refused for the same reason: a new lease costs a command, a stale answer costs the rung.
    `tools/test_ladder.py::test_an_answer_that_moved_between_lease_and_spawn_is_refused`
    """
    now = ladder_for_order(state, task, root, int(task.get(FAILED_RUNS) or 0))
    was = lease.get(LADDER_KEY)
    if not isinstance(was, dict):
        raise DispatchError(
            "the lease for %s carries no ladder answer (minted before the rule), so what the child "
            "would run on cannot be compared with what the state says -- dispatch blocked. Remedy: "
            "`python scripts/harness.py sweep-leases` once it has expired, or wait it out, then "
            "dispatch again; the new lease carries the answer." % task["id"])
    if (was.get(RUNG_KEY), was.get(EFFORT_KEY), "absent" in was) != (
            now.get(RUNG_KEY), now.get(EFFORT_KEY), "absent" in now):
        raise DispatchError(
            "the ladder's answer for %s moved between lease and spawn: the lease says %s, the "
            "state now says %s -- dispatch blocked (DEC-0077 (2): rung and effort are derived from "
            "the state at the spawn, never carried over). Remedy: wait out or sweep the lease and "
            "dispatch again; the new lease carries the current answer."
            % (task["id"], ladder_line({LADDER_KEY: was}), ladder_line({LADDER_KEY: now})))


def _assert_dispatch_authorised_locked(state: ProjectState, task: dict, root: dict) -> None:
    """No subagent without a user approval (spec II.2 Risikoklassen) -- via one
    of the THREE legitimate routes, never neither.

    1. DELIVERY route: the root item carries a current scope or delivery
       approval, and the task rides on it. ONLY those two kinds (see
       ROOT_DISPATCH_KINDS): an analysis or routine approval minted against the
       root would otherwise authorise unlimited IMPLEMENTATION work under a
       still-DRAFT root -- and because their manifests are not item-derived, no
       content hash could catch an out-of-band edit either, silently switching
       off gate layer 4 for that root.
    2. ANALYSIS route: an `APR.kind: analysis` LISTS this task. Spec II.2
       (Buendelung, user decision 2026-07-24) lets one analysis approval cover
       several listed tasks, and such an approval is usually not item-bound at
       all -- so the root may legitimately have no approval_ref while the task
       is still fully approved.
    3. ROUTINE route: an `APR.kind: routine` on this root covers this task's
       ROLE and the task claims no writable scope (see `_covering_routine_apr`).
       Spec II.1 makes the auditor "eine VERPFLICHTENDE Routine ... legitimiert
       durch eine widerrufbare `APR.kind: routine`-Freigabe" and II.10a demands
       that an expired or revoked one block that dispatch fail-closed. Until
       this route existed the kernel had no reader for the kind at all, so the
       expiry branch it demands was dead code on this path and the auditor rode
       an `analysis` approval whose manifest has to list every single run
       (measured 2026-07-26, re-measured 2026-07-31, disposition line 100).

    THE TWO TASK ROUTES ARE NOT BOUND ALIKE, and the difference decides what happens
    when the ROOT's own approval has stopped granting anything: the routine route
    refuses a task that claims a writable scope, the analysis route binds a listed
    task and nothing else. So the read-only fall-through below is conditional on the
    TASK, never on which route might catch it -- see the `except` branch.
    """
    refusals = []
    apr_ref = root.get("approval_ref")
    if apr_ref:
        try:
            apr = _read_root_apr(state, apr_ref)
            if apr.get("kind") in ROOT_DISPATCH_KINDS:
                _assert_root_approval_locked(state, root)
                return
        except DispatchError as exc:
            # A ROOT WHOSE APPROVAL NO LONGER GRANTS ANYTHING MAY STILL BE READ, NEVER WRITTEN.
            # That is the whole condition, and getting it wrong once is why it is stated as a
            # rule rather than as a route: refusing outright made the audit unreachable in
            # exactly the situation an audit exists for (scope approval REVOKED, or the root
            # edited past the kernel), while falling through UNCONDITIONALLY -- what the first
            # cut of this did -- handed the same amnesty to implementation work. `analysis` is
            # what made that measurable: `_covering_analysis_apr` binds a LISTED TASK and nothing
            # else, so any task some analysis approval lists walked past both tripwires
            # `assert_apr_in_force` exists for. Measured 2026-07-31: root edited out of band
            # (revision unchanged, content hash broken) -> IMPLEMENTATION dispatch ALLOWED; root
            # approval revoked -> ALLOWED. The revocation is the worse of the two, because a user
            # deliberately withdrew it.
            # So the fall-through is conditional on the TASK claiming no writable scope -- the
            # same `_claims_writable_scope` the routine route binds to. A writable task gets the
            # root's own refusal, verbatim and unaggregated, exactly as before.
            if _claims_writable_scope(task):
                raise
            refusals.append("the approval %s presents (%s): %s" % (root["id"], apr_ref, exc))
        # an approval of a non-dispatching kind raises nothing and is NOT an error on the item --
        # it simply does not authorise a spawn, so fall through to the task routes
    if _covering_analysis_apr(state, task["id"]) is not None:
        return
    covering, routine_refusals = _covering_routine_apr(state, task, root)
    if covering is not None:
        return
    refusals += routine_refusals
    raise DispatchError(
        "no user approval authorises dispatching %s under %s -- blocked (spec II.2: no "
        "subagent without a user approval). Remedy: obtain the scope approval for %s, or "
        "an analysis approval that LISTS %s in its subject manifest, or -- for a recurring "
        "read-only run -- a routine approval on %s naming role %r (spec II.10a).%s"
        % (task["id"], root["id"], root["id"], task["id"], root["id"],
           task.get("assigned_role"),
           (" The approvals that name %s and why none of them covers it: %s"
            % (root["id"], "; ".join(refusals))) if refusals else "")
    )


def _read_root_apr(state: ProjectState, apr_ref: str) -> dict:
    """The APR a root presents, refused in the DISPATCH vocabulary when it cannot be read.

    `read_apr` raises `ApprovalError`, which is not a `DispatchError` -- and the hook classifies
    anything else as an internal error, so a MISSING approval file reached the user as "the
    harness is broken, run the doctor" instead of "this root's approval is gone". The same
    argument `_assert_root_approval_locked` makes for its own re-raise; it lived one call too far
    in, so the one failure that skipped that function skipped the translation too, and with it the
    read-only fall-through that every other reason for "grants nothing" gets.
    """
    try:
        return read_apr(state, apr_ref)
    except ApprovalError as exc:
        raise DispatchError("dispatch blocked (spec II.4): %s" % exc) from None


def _covering_analysis_apr(state: ProjectState, task_id: str):
    """A valid, PROVEN analysis approval listing this task, or None.

    The task list is read from the approval's CONSUMED REQUEST, never from the
    approval file: the request is the part only `mint` can produce, so reading
    coverage there means a hand-written APR-0001.yaml listing whatever tasks it
    likes authorises nothing (spec II.12).
    """
    approvals_dir = os.path.join(state.root, "approvals")
    if not os.path.isdir(approvals_dir):
        return None
    for name in sorted(os.listdir(approvals_dir)):
        if not (name.startswith("APR-") and name.endswith(".yaml")):
            continue
        try:
            apr = state._read_yaml(os.path.join(approvals_dir, name))
        except Exception:
            continue
        if not isinstance(apr, dict) or apr.get("kind") != "analysis" or apr.get("revoked"):
            continue
        try:
            request = consumed_request(state, apr)
            expires = proven_expiry(request)
        except (DispatchError, ApprovalError):
            continue  # unprovable, revoked or unreadable covers nothing (fail-closed)
        if expires is not None and expires < time.time():
            continue
        listed = (request.get("subject_manifest") or {}).get(ANALYSIS_TASKS_KEY) or []
        if task_id in [str(entry) for entry in listed]:
            return apr
    return None


def _claims_writable_scope(task: dict) -> bool:
    """Does this task's work order CLAIM the right to write outside the state directory?

    `allowed_scope` is the claim, and this asks only about the claim. Truthy rather than a length
    test on purpose: a single unusable entry (`[""]`, `["."]`) is a claim to something, and
    `gate_write_scope._scope_entries` refuses those loudly rather than reading them as
    "everything", so a task carrying one is not read-only here either.

    WHAT REFUSING SUCH A TASK BUYS, AND WHERE IT STOPS -- measured 2026-07-31, because the first
    version of this docstring claimed the whole of it and the harness builds half:
      * a work order with an empty `allowed_scope` is refused every write outside the state
        directory BY THE WRITE TOOLS: `gate_write_scope.handle_file_write` reads the bound task
        and blocks Edit/Write/MultiEdit/NotebookEdit (measured rc 2). Inside the state directory
        it never consults the field -- the specialist keeps its own `staging/<task-id>/`, which is
        the one exception the auditor role is written around.
      * THE SHELL PATH CHECKS NO TASK SCOPE AT ALL. `gate_write_scope.handle_shell` never resolves
        the bound task; it decides on whether the command line names the state directory or the
        enforcement layer. Measured with a bound auditor whose `allowed_scope` is empty, against
        all eight registered `Bash|PowerShell` PreToolUse hooks: `echo pwned > src/x.py`,
        `rm -rf src` and `git commit -am wip` all rc 0. The auditor carries `Bash`.
    So what this route enforces is the WORK ORDER, not a sandbox: a routine approval cannot
    authorise a task that is planned to write, and it does not stop a spawned agent from writing
    through a shell. Gate layer 3 for the shell is an open hole of `gate_write_scope`, older than
    this route and shared by every bound specialist; it is pinned as such in
    `tools/test_hooks_v2.py` under the `state_write_protection.shell` capability, so
    `python scripts/harness.py doctor` reports that capability `unverified` rather than green.
    """
    return bool(task.get("allowed_scope"))


def _covering_routine_apr(state: ProjectState, task: dict, root: dict):
    """(approval, refusals): a `routine` approval that authorises THIS dispatch, plus why the
    others did not.

    WHAT A ROUTINE BINDS, and therefore what this checks -- spec II.2 makes it "gebunden an
    Rolle, Read-only-Scope, Trigger, Ablaufdatum und jederzeit widerrufbar", II.10a hashes all
    of those plus the Takt:
      * the ROOT it was minted for, and everything `assert_apr_in_force` means by "in force":
        revoked, unprovable (`consumed_request`), foreign, or past its expiry. The expiry is
        re-read on EVERY dispatch, from the hash-covered manifest of the minted request, so a
        lease taken before the clock ran out does not carry the spawn past it -- `create_lease`
        and `validate_dispatch` both come through here.
      * the ROLE. A route that did not bind it would let one signature spawn any specialist.
      * READ-ONLY, via `_claims_writable_scope`. This is what keeps the route from being the
        blanket permission `ROOT_DISPATCH_KINDS` deliberately withholds: a routine can authorise
        a recurring audit, and it can never authorise implementation work under the same root.
    Read out of the CONSUMED REQUEST, never the approval file, for the reason the analysis route
    is: the request is the part only `mint` can produce, so a hand-written `APR-0001.yaml`
    claiming any role it likes authorises nothing (spec II.12).

    WHAT IT DOES NOT CHECK, named because the manifest carries it and a reader would otherwise
    assume the kernel acts on it: `trigger` and `cadence` say WHEN the routine may run, and
    nothing in this kernel records when it last did -- II.10a's `last_completed`/`next_due` have
    no producer. `scope` says where the run may READ, and there is no read gate at any layer. All
    three are inside the hashed manifest, so they cannot be moved without breaking the approval;
    they are simply not enforced, and the auditor's role text says so in the same words.

    AND WHAT MINTING ONE NO LONGER COSTS (PR-0011 AC-8): until generation 6 `mint` wrote
    `approval_ref` for every item-bound approval, so a routine minted for a root that carried a
    scope or delivery approval took the reference with it and every builder under that root
    stopped dispatching until the scope question was asked again. `approvals.presents` now keeps
    a hanging kind out of that field -- this route reads the approvals directory, never
    `approval_ref`, so nothing here needed the field. A store where the older mint left that
    state behind is what `report._check_dispatch_approval_presented` still warns about.
    """
    refusals = []
    approvals_dir = os.path.join(state.root, "approvals")
    if not os.path.isdir(approvals_dir):
        return None, refusals
    for name in sorted(os.listdir(approvals_dir)):
        if not (name.startswith("APR-") and name.endswith(".yaml")):
            continue
        try:
            apr = state._read_yaml(os.path.join(approvals_dir, name))
        except Exception:  # noqa: BLE001 -- an unreadable approval authorises nothing
            continue
        if not isinstance(apr, dict) or apr.get("kind") != "routine":
            continue
        if str(apr.get("item") or "") != root["id"]:
            continue
        apr_id = apr.get("id") or name[:-5]
        try:
            request = assert_apr_in_force(state, apr, root)
        except ApprovalError as exc:
            refusals.append("%s: %s" % (apr_id, exc))
            continue
        manifest = request.get("subject_manifest") or {}
        role = str(manifest.get(ROUTINE_ROLE_FIELD) or "")
        if role != str(task.get("assigned_role") or ""):
            refusals.append(
                "%s covers role %r, not %r" % (apr_id, role or "<none>", task.get("assigned_role")))
            continue
        if _claims_writable_scope(task):
            refusals.append(
                "%s is a READ-ONLY routine (spec II.2), but %s claims allowed_scope %s"
                % (apr_id, task["id"], task.get("allowed_scope")))
            continue
        return apr, refusals
    return None, refusals


def _assert_root_approval_locked(state: ProjectState, root: dict) -> None:
    """Root carries a CURRENT approval that is still in force.

    Which APR that is, is this function's own question: `approval_ref` names the approval the root
    presents, and the dispatch route rides on THAT one (its kind decided the route two frames up).
    Whether it still grants anything is `approvals.assert_apr_in_force`, shared with the status
    automaton -- revoked, unprovable, foreign, expired, or invalidated by an out-of-band edit are
    the same five answers whoever asks, and the copy that used to live here is how a shared fact
    becomes two facts.

    ApprovalError is NOT a DispatchError, and the hook classifies anything else as an internal
    error -- so a provable-policy refusal would reach the user as "the harness is broken, run the
    doctor" instead of "this approval is not proven". Re-raised in the dispatch vocabulary here,
    with the consequence this caller adds and the shared check deliberately does not carry.
    """
    apr_ref = root.get("approval_ref")
    if not apr_ref:
        raise DispatchError(
            "root %s has no current approval -- dispatch blocked (fail-closed). "
            "Remedy: obtain the scope/delivery approval." % root["id"]
        )
    apr = read_apr(state, apr_ref)
    try:
        assert_apr_in_force(state, apr, root)
    except ApprovalError as exc:
        raise DispatchError("dispatch blocked (spec II.4): %s" % exc) from None


def _design_ref_resolves(state: ProjectState, reference: str) -> bool:
    """Does this `design_refs` entry name a FROZEN DESIGN that exists? (see validate_dispatch)

    "EXISTS" IS NOT ENOUGH, and the first cut of this function proved it. It asked
    `os.path.exists(state.root/<entry>)`, which is true of `README.md`, of `generated/index.yaml`,
    of `.`, of `..` and of `../.claude/settings.json` -- measured 2026-07-31 end to end over the
    shipped surface: `capture PR … "design_refs":["../.claude/settings.json"]`, a UI task naming
    that ref, scope approval, lease, and the spawn was ALLOWED. The II.6 rule was still satisfiable
    by a self-written reference; only the shape had changed from a phantom id to any path at all.
    Its own docstring claimed the opposite ("an entry that escapes the state root simply does not
    resolve"), which is the comment shape this kit refuses.

    TWO FORMS, AND THE ID FORM IS ASKED FIRST -- which is the correction to the first version of
    this function, where it was DEAD CODE. A bare `DSN-0001` is also a relative path under the
    state root, so it entered the path branch, was not a file, and came back False: the branch
    below could only ever be reached by a reference that lands on or outside the root, and none of
    those parses as an id. Measured after a real `freeze_design`: `exists_anywhere('DSN-0001')`
    True, `_design_ref_resolves('DSN-0001')` False -- so the docstring's promise was wrong AND a
    `design_refs` entry in id form locked every legitimate UI dispatch. Replacing the whole branch
    with `return False` changed no test, which is why the test below now carries a REAL frozen id
    in the accepted list rather than only a phantom in the refused one.

    THE PATH FORM, three conditions, each closing one measured case:
      * CONTAINMENT -- `realpath`, not `normpath`. `normpath` is textual, and `os.path.isfile`
        follows links: measured with `mklink /J project_memory/design/revisions/out .claude`, the
        entry `design/revisions/out/settings.json` resolved True while its real path lay outside
        the state root entirely. This repo has paid for a symlink-blind path comparison once
        already (`hashing._bundle_files`); resolving both sides is the same fix in one word.
      * IT MUST BE A FILE. A frozen revision is a file (II.6a: "Zustand = Ort"), so `staging`,
        `.` and every other directory stop here.
      * IT MUST LIE WHERE THE PRODUCER PUTS ONE (`staging.frozen_design_dirs`).
    """
    from .staging import frozen_design_dirs

    reference = str(reference or "").strip()
    if not reference:
        return False
    try:
        parse_id(reference)
    except ValueError:
        pass
    else:
        return state.exists_anywhere(reference)
    root = os.path.realpath(state.root)
    target = os.path.realpath(os.path.join(state.root, reference.replace("/", os.sep)))
    if target == root or not target.startswith(root + os.sep):
        return False
    relative = os.path.relpath(target, root).replace(os.sep, "/")
    return os.path.isfile(target) and any(
        relative.startswith(directory + "/") for directory in frozen_design_dirs())


def _read_item_any(state: ProjectState, item_id: str):
    """Return (item, archived); the caller holds the lock.

    Delegates to `ProjectState.read_anywhere` -- this was the original home of
    that walk, and the merge gate needed the same one. Two readers of one storage
    layout is the defect this repo keeps finding, so the walk moved to the state
    object and this name stays as the local spelling.
    """
    return state.read_anywhere(item_id)


def _read_lease(state: ProjectState, task_id: str) -> dict:
    try:
        return state._read_yaml(_lease_path(state, task_id))
    except FileNotFoundError:
        raise DispatchError(
            "no lease for %s -- dispatch blocked (spec II.4). Remedy: create "
            "a lease from READY first." % task_id
        ) from None
    except Exception as exc:
        raise DispatchError(
            "corrupt lease file for %s (%s) -- dispatch blocked (fail-closed). "
            "Remedy: `python scripts/harness.py doctor` inspects leases; removing the corrupt "
            "lease returns the task to READY on the next sweep."
            % (task_id, exc.__class__.__name__)
        ) from None


def _expired(lease: dict) -> bool:
    return time.time() > float(lease["created_epoch"]) + float(lease["ttl"])


def _window_open_until(lease: dict) -> float:
    """The bind window's end, or 0 when there is none / it is unreadable.

    Defensive on purpose: `_iter_leases` skips leases that do not PARSE, so a
    parseable lease with a junk value here is the remaining gap -- and a claim
    path that raises ValueError on it turns a diagnosable state into an
    internal-error block with a traceback instead of a remedy.
    """
    try:
        return float(lease.get("awaiting_bind_until") or 0)
    except (TypeError, ValueError):
        return 0.0


def _remove_lease(state: ProjectState, task_id: str) -> None:
    try:
        os.remove(_lease_path(state, task_id))
    except FileNotFoundError:
        pass


def _release_lease_locked(state: ProjectState, task_id: str, to_ready: bool) -> bool:
    """Drop the lease; True when the TASK's status was reset too, False when only the lease went.

    The return value is what keeps `sweep_expired_leases` honest -- see the two lists there.
    """
    _remove_lease(state, task_id)
    task = state.read_item(task_id)
    if to_ready and task.get("status") == LEASE_MINTED_STATUS:
        task["status"] = "READY"
        state._write_yaml_atomic(state.active_path(task_id), task)
        return True
    return False

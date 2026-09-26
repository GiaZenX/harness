"""Session brief, state validator and doctor (HARNESS_V2_SPEC.md II.4/II.5) -- 1.4c.

- generate_session_brief: a new session works from generated/session_brief.yaml
  plus active items ALONE -- never from transcripts (II.5). Content contract =
  kernel/schemas/session_brief.yaml, validated before writing.
- validate_state: the fail-closed layer-4 validator -- full field duties
  (incl. status-dependent ones), the reference graph, approval integrity with
  the D/4 content-hash check (out-of-band edits invalidate approvals visibly),
  staging orphans, id uniqueness, budgets, lease/request hygiene. Returns
  findings; gates block on any severity=error finding.
- doctor: read-only activation/diagnosis report (II.4) -- never writes state.
- closed_by_delivery / delivered_but_open / delivery_closure_rollup: what a delivery has already
  closed, DERIVED from the Evidence records rather than read off the status field (DEC-0051), the
  part of that answer the status field has not caught up with, and that part as rows. Printed
  BESIDE the findings by `validate` and carried in `doctor`'s payload -- never as a finding.

Language convention (II.10a parity rule "Deutsch zum User / Englisch in
Artefakten"): code, comments and identifiers are English; USER-FACING strings
(next_step texts, the approval question in approvals.py) are German.

Deferred validator duties (documented, not findings): INV check-test existence/
collectability -> pytest/CI integration (phase 2, B.2-10); cross-BRANCH id
uniqueness -> gate layer 5 / CI at merge; routine/analysis APR expiry ->
dispatch TODO (II.10a).
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time

from .approvals import (
    APPROVAL_HOOK,
    APPROVAL_MINT_EVENT,
    APPROVAL_QUESTION_EVENT,
    APPROVAL_QUESTION_TOOL,
    APPROVED_CONTENT_HASH_FIELD,
    ROOT_DISPATCH_KINDS,
    ApprovalError,
    approved_content_hash,
    approved_statuses,
    assert_apr_in_force,
    consumed_request,
    has_expired,
    required_approval_kinds,
)
from .backlog_types import (
    AREA_FIELD,
    AREA_SEPARATOR,
    ACTIVE_DIRS,
    AUTOMATA,
    BLOCKED_REASON_FIELD,
    DEC_SUPERSEDES_FIELD,
    DEC_WORK_FIELD,
    DEC_WORK_NONE,
    HASHED_FIELDS,
    NON_AUTOMATON_STATUSES,
    NONEMPTY_FIELDS,
    area_segments,
    names_something,
    work_is_none,
    PARENT_FIELDS,
    PARTIAL_RUN_SCOPE,
    PASSING_RESULT,
    QA_EVIDENCE_KINDS,
    REFERENCE_LIST_FIELDS,
    ROOT_TYPE_BY_KIT,
    RUN_SCOPES,
    STATUS_DEPENDENT_FIELDS,
    TRIAGE_RESULT_LINK,
    confirming_edge,
    field_elements,
    GOAL_CLASS_FIELD,
    goal_classes_without,
    is_inbox_type,
    required_fields_of,
    parse_id,
    single_value_offences,
)
from .dispatch import (
    BUILD_CLASS,
    EFFORT_KEY,
    FAILED_RUNS,
    LEASE_CLASS_FIELD,
    LEASE_EFFORT_FIELD,
    LEASE_PROVIDER_FIELD,
    LEASE_PROVIDERS_FIELD,
    LEASE_RUNG_FIELD,
    RUNG_KEY,
)
from .hashing import HASH_SCHEMA_VERSION, hook_bundle_hash
from .lock import LOCK_SCHEMA_VERSION, PORTABLE_PATH_MAX_CHARS, ext_path
from .schemas import validate
from .state import CONFIRMING_EVIDENCE, STAGING_DIRNAME, ProjectState, _now_iso

# THE GOAL CLASSES THAT CARRY NO PRODUCT CONTENT (DEC-0103). Two checks below skip a duty for such
# a goal -- the user story it owes, and its place in the delivery sequence a user has to see -- and
# both used to spell `technical_enabler` themselves. Asked of the vocabulary as a COMPLEMENT, so a
# class the vocabulary does not know (a goal stored before DEC-0103, a value from another tool) is
# in neither set and keeps being asked: a skipped duty is the one direction these checks may not
# fail in.
# `tools/test_report.py::test_a_goal_whose_class_the_vocabulary_does_not_know_still_owes_its_user_story`
PRODUCTLESS_CLASSES = goal_classes_without("carries_product_content")

ITEM_MAX_BYTES = 12 * 1024   # spec II.5: active item <= 200 lines / 12 KB
ITEM_MAX_LINES = 200

# WHAT THE DOCUMENT SCAN BELOW WILL SPEND, and why a reader with no bound is a gate with no
# verdict. `validate_state` is not only a command a person types: the dev and research kits'
# `gate_memory_complete` calls it on the PreToolUse path in front of `git merge`/`git push`, and a
# hook that outlives the host's budget is KILLED, which the provider reads as "carry on". So an
# unbounded reader on that path is a gate that a large enough file switches off -- the same
# inversion `guard_guidelines` and `gate_test_coverage` carry their caps for, and this scan
# shipped without one.
#
# WHICH PARSER PAYS FOR IT, because the previous version of this note named the wrong one and its
# curve was too cheap by the difference. `migrate._read_document` calls `yaml.safe_load`, which is
# `yaml.SafeLoader` -- the PURE PYTHON loader. `CSafeLoader` exists on this host and
# `yaml.__with_libyaml__` is True, and neither of those is on this path: nothing here asks for the
# C loader, so a note reading "PyYAML with libyaml" described a reader nobody runs.
#
# Re-measured on the loader it does use (2026-08-07, one office-shaped `filing_log.yaml` of dated
# entries, `_check_no_v1_records_outside_the_archive` timed directly, best of three):
# 1 MB 1.85 s · 2 MB 2.90 s · 4 MB 6.36 s · 8 MB 18.01 s. The per-MB cost is NOT constant -- it
# runs from ~1.9 s/MB to ~2.3 s/MB across that span -- and the FIRST reading of each size, before
# the cache was warm, was 1.7x to 2.7x higher again (2.9 to 4.2 s/MB), which is the reading a hook
# gets on a machine that has not just read the file.
# So the whole-scan value below is ~18 s warm and ~31 s cold: not twelve, and a third to a half of
# the 60 s a PreToolUse hook has for EVERYTHING, `validate_state`'s other duties and the
# interpreter start included. It is a bound, and it is not a comfortable one.
#
# TWO CAPS, because neither bounds the other: a per-DOCUMENT cap says nothing about a thousand
# documents, and a whole-SCAN cap says nothing about the first file being 200 MB. They are the
# same two values the hook-layer readers of a store carry, so that one project has ONE answer to
# "how much may a blocking reader spend";
# `test_hooks.test_every_blocking_store_reader_carries_the_same_two_caps` is what holds them
# equal rather than this sentence, and it is where the other readers are named.
#
# WHAT IS SKIPPED IS REPORTED, never passed over -- for EVERY way of skipping, which is the
# correction of 2026-08-07 and is a property of the loop rather than a list of causes: see
# `_check_no_v1_records_outside_the_archive`. The three measured halves are in `test_migrate` --
# `test_a_document_too_large_to_search_is_reported_as_unsearched_and_not_read`,
# `test_the_whole_scan_budget_names_the_documents_it_did_not_reach` and
# `test_an_unparsable_document_is_unsearched_and_still_refuses_the_merge`.
DOCUMENT_MAX_BYTES = 2_000_000
DOCUMENT_SCAN_MAX_BYTES = 8_000_000

# The next step per root status. Three of the four are "obtain an approval", and that is not
# editorial: those three edges are the ones `approvals.APPROVAL_TRANSITIONS` says an approval
# COMMITS, so `state.transition` refuses them without one and the mint walks them itself. A line
# here that said "transition it" would be telling the lead to run a command the kernel refuses.
_NEXT_STEP = {
    "DRAFT": "Scope-Freigabe einholen",
    "APPROVED": "Tasks anlegen; Delivery-Freigabe einholen (der Mint setzt IN_DELIVERY)",
    "IN_DELIVERY": "Tasks abarbeiten",
    "DELIVERED": "Abnahme einholen",
}


def _finding(severity: str, item: str, message: str, remedy: str) -> dict:
    return {"severity": severity, "item": item, "message": message, "remedy": remedy}


def _iter_active(state: ProjectState):
    """(type, stem, item, path, read error) for every ACTIVE item, over every type.

    WHICH FILES ARE ITEMS is `ProjectState.iter_active_items` and no longer this function's own
    answer. It was, with the rule "every `*.yaml` in the directory is an item", and that rule
    contradicted `state._frozen_revision_path` for the types the kernel stores per revision: a
    second `freeze_wireframe` wrote `WFR-0001.r02.yaml` beside `WFR-0001.r01.yaml`, this loop
    yielded two items carrying one id, `validate_state` reported `WFR-0001 duplicate id` and
    `gate_memory_complete` refused every merge in the project until a frozen, immutable artefact
    was deleted by hand (measured 2026-07-28, disposition row 6.5).
    """
    for item_type in sorted(ACTIVE_DIRS):
        for stem, path in state.iter_active_items(item_type):
            try:
                item = state._read_yaml(path)
                yield item_type, stem, item, path, None
            except Exception as exc:
                yield item_type, stem, None, path, exc


# -- session brief -------------------------------------------------------------

# The newest STANDING decisions ride into the next session with the brief (BUG-0005). Without them a
# new session begins blind to the last call the previous one made, and the PM reaches for the raw
# transcript to recover it (BUG-0019) -- the exact loss the brief exists to prevent. "Standing" is
# `_holding_decisions`' answer (in force AND not superseded), so a replaced decision never rides
# along. Count- and text-bounded rather than unbounded, because the brief carries a byte budget
# (`kernel/schemas/session_brief.yaml` max_serialized_bytes) that a growing decision log would break;
# the full text stays in the DEC item, this is a pointer with a summary.
_BRIEF_MAX_DECISIONS = 5
_BRIEF_DECISION_MAX_CHARS = 400


def _clip(text: object, limit: int) -> str:
    """`text` as a string, never longer than `limit` characters (a trailing ellipsis marks a cut)."""
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _id_number(item_id: object) -> int:
    """The numeric part of an item id, 0 when it is not a parseable id (for a stable tiebreak)."""
    try:
        _type, number = parse_id(str(item_id))
    except ValueError:
        return 0
    return number


def _brief_decision_rows(dec_items: dict) -> list:
    """The newest STANDING decisions as {id, title, decision}, newest first, count- and text-bounded.

    `dec_items` is {id: DEC item} for the active DEC items. WHICH of them hold is `_holding_decisions`
    (the one definition, shared with `standing_decisions`); WHICH come first is `created` then the id
    number (the same monotonic tiebreak `_delivery_evidence` uses, so same-second captures still
    order); HOW MANY and HOW LONG is bounded so the section cannot push the brief past its byte
    budget -- the DEC item keeps the full text, this carries a clipped summary.
    """
    holding = _holding_decisions(dec_items)
    ordered = sorted(
        (dec_items[dec_id] for dec_id in holding),
        key=lambda it: (str(it.get("created") or ""), _id_number(it.get("id"))),
        reverse=True,
    )
    return [{"id": it.get("id"),
             "title": _clip(it.get("title"), _BRIEF_DECISION_MAX_CHARS),
             "decision": _clip(it.get("decision"), _BRIEF_DECISION_MAX_CHARS)}
            for it in ordered[:_BRIEF_MAX_DECISIONS]]


# HOW MANY LEASES THE DISTRIBUTION LOOKS BACK OVER (DEC-0092 (3)(d) and (4)): the "last N" of both
# the spawn gate's checkpoint and the brief's line, one number so the two mirrors show the same
# habit. Ten is one generation's worth of orders in this repository's own history (gen 4: four
# streams + merge, gen 5: three + merge) -- long enough for "always one" or "always three" to show,
# short enough that a changed habit shows within a generation.
DISTRIBUTION_WINDOW = 10


def _leased_orders(state: ProjectState) -> list:
    """Every work order a lease wrote its answer on -- active and archived -- newest lease first.

    The answer is `dispatch.LEASE_RUNG_FIELD` and its two siblings, copied onto the task at the
    lease precisely so this reading survives the lease's removal and the task's archiving. Sorted
    by `leased_at`, which the lease stamps in the kernel's ISO form, so a lexical sort is a time
    sort.
    """
    rows = []
    for item_type, _stem, item, _path, exc in _iter_active(state):
        if item_type == "TSK" and not exc and isinstance(item, dict) and item.get(LEASE_RUNG_FIELD):
            rows.append(item)
    for item_type, item in _iter_archived_items(state):
        if item_type == "TSK" and item.get(LEASE_RUNG_FIELD):
            rows.append(item)
    rows.sort(key=lambda item: (str(item.get("leased_at") or ""), str(item.get("id") or "")),
              reverse=True)
    return rows


def _handed_back(item: dict) -> bool:
    """Was this order HANDED BACK -- a chain status after IN_PROGRESS (SUBMITTED and on), asked of
    the automaton. Not "passed": SUBMITTED is a result envelope, and DONE/VALIDATED are the
    verdicts that may follow it; this reader counts the runs until the hand-back."""
    chain = AUTOMATA["TSK"].chain
    status = str(item.get("status") or "")
    return status in chain and chain.index(status) > chain.index("IN_PROGRESS")


def lease_distribution(state: ProjectState, window: int = DISTRIBUTION_WINDOW) -> dict:
    """The last `window` ORDERS of this project, by their latest lease, as the habit they show
    (DEC-0092 (4)).

    ORDERS AND NOT LEASES, said because the two differ exactly where the habit shows: an order
    re-dispatched after a FAILED run is one order with several leases, and `leased_at` on the item
    is the latest of them -- so this counts orders, and the runs each needed are a column of their
    own. THREE COUNTS AND ONE LINE: how many BUILD-class orders each goal in the window received
    (`builders_per_goal`: {"1": goals with one builder, "2": ...}), which rungs and EFFORTS the
    latest leases landed on (`rungs`, `efforts`), and how many RUNS an order on each rung and on
    each effort needed until it was HANDED BACK (`runs_to_hand_back_per_rung` and
    `..._per_effort`: mean of `failed_runs` + 1 over the orders that reached
    SUBMITTED or later -- handed back is not passed, and the verdict is nobody's here).

    BOTH AXES AND NOT THE RUNG ALONE (DEC-0097 (4)): the ladder escalates on two axes and DEC-0096
    spends the effort steps FIRST, so a reading that counts only rungs cannot say whether the
    cheaper axis bought anything -- which is the one question the user is paying this counter to
    answer (FR-0091 section 3, "was nur wir selbst messen koennen"). The pair is deliberately NOT
    counted as one key ("opus/high"): the window is ten orders, and a joint key splits that into
    cells too small to mean anything. Derived
    from the task items alone, so it costs no new instrument (DEC-0092's context) and reads the
    same in a project with no lease yet, where the line says so instead of showing zeros as a
    habit. WHAT "RUNS" COUNTS: dispatches of the order -- one plus the FAILED runs
    `dispatch.count_failed_run_locked` counted -- and not the verifier's rounds, which no state
    field records.
    `tools/test_report.py::test_the_session_brief_carries_the_lease_distribution_line`

    WHOSE RUNG (BUG-0308 / H221): `rungs`/`efforts` and their two means count the lease's top-level
    answer, which is the REFERENCE platform's (`counted_provider` names it: the providers the orders
    recorded, or "the reference platform" for orders leased before they recorded one). Every
    provider a lease also answered for is counted under its own name in `by_provider` -- rungs,
    efforts and runs to hand-back per rung -- so a Codex project's climbed order shows its Codex rung.
    `tools/test_ladder.py::test_the_lease_distribution_names_the_provider_whose_rung_it_counts_bug_0308`
    """
    recent = _leased_orders(state)[:window]
    builders = {}
    # ONE LOOP PER AXIS-VALUE, keyed by the field the lease wrote, so a third axis would be a row
    # here and not a second block of counting.
    seen = {LEASE_RUNG_FIELD: {}, LEASE_EFFORT_FIELD: {}}
    runs = {LEASE_RUNG_FIELD: {}, LEASE_EFFORT_FIELD: {}}
    counted, by_provider = set(), {}
    for item in recent:
        counted.add(str(item.get(LEASE_PROVIDER_FIELD) or "the reference platform"))
        answers = item.get(LEASE_PROVIDERS_FIELD)
        for provider, answer in (answers.items() if isinstance(answers, dict) else ()):
            if not isinstance(answer, dict):
                continue
            row = by_provider.setdefault(str(provider), {"rungs": {}, "efforts": {}, "runs": {}})
            for key, bucket in ((RUNG_KEY, "rungs"), (EFFORT_KEY, "efforts")):
                value = str(answer.get(key))
                row[bucket][value] = row[bucket].get(value, 0) + 1
            if _handed_back(item):
                row["runs"].setdefault(str(answer.get(RUNG_KEY)), []).append(
                    int(item.get(FAILED_RUNS) or 0) + 1)
        if item.get(LEASE_CLASS_FIELD) == BUILD_CLASS:
            root = str(item.get("product_requirement") or "?")
            builders[root] = builders.get(root, 0) + 1
        for field in (LEASE_RUNG_FIELD, LEASE_EFFORT_FIELD):
            value = str(item.get(field))
            seen[field][value] = seen[field].get(value, 0) + 1
            if _handed_back(item):
                runs[field].setdefault(value, []).append(int(item.get(FAILED_RUNS) or 0) + 1)
    per_goal = {}
    for count in builders.values():
        per_goal[str(count)] = per_goal.get(str(count), 0) + 1
    means = {field: {value: round(sum(counts) / len(counts), 1)
                     for value, counts in runs[field].items()}
             for field in runs}
    providers = {provider: {"rungs": row["rungs"], "efforts": row["efforts"],
                            "runs_to_hand_back_per_rung": {
                                value: round(sum(counts) / len(counts), 1)
                                for value, counts in row["runs"].items()}}
                 for provider, row in sorted(by_provider.items())}

    def spelled(counted):
        return ", ".join("%s x %d" % (value, n) for value, n in sorted(counted.items()))

    def averaged(counted):
        return ", ".join("%s %s" % (value, mean)
                         for value, mean in sorted(counted.items())) or "none handed back yet"

    if not recent:
        line = "no lease recorded in this project yet -- no habit to show"
    else:
        line = ("last %d order(s) by their latest lease: %d goal(s) with builders; builders per goal "
                "%s; rungs %s; efforts %s; runs to hand-back per rung %s; per effort %s"
                % (len(recent), len(builders),
                   ", ".join("%s builder(s) x %d goal(s)" % (n, goals)
                             for n, goals in sorted(per_goal.items())) or "none",
                   spelled(seen[LEASE_RUNG_FIELD]), spelled(seen[LEASE_EFFORT_FIELD]),
                   averaged(means[LEASE_RUNG_FIELD]), averaged(means[LEASE_EFFORT_FIELD])))
        line += "; rungs and efforts counted as answered for %s" % ", ".join(sorted(counted))
        others = [provider for provider in providers if provider not in counted]
        if others:
            line += "; per provider: " + "; ".join(
                "%s rungs %s, runs to hand-back per rung %s" % (
                    provider, spelled(providers[provider]["rungs"]),
                    averaged(providers[provider]["runs_to_hand_back_per_rung"]))
                for provider in others)
    return {"window": int(window), "orders": len(recent), "goals_with_builders": len(builders),
            "counted_provider": sorted(counted), "by_provider": providers,
            "builders_per_goal": per_goal, "rungs": seen[LEASE_RUNG_FIELD],
            "efforts": seen[LEASE_EFFORT_FIELD],
            "runs_to_hand_back_per_rung": means[LEASE_RUNG_FIELD],
            "runs_to_hand_back_per_effort": means[LEASE_EFFORT_FIELD], "line": line}


def generate_session_brief(
    state: ProjectState, kit: str, kit_version: str, enforcement_mode: str
) -> str:
    with state.lock:
        roots, tasks, decs = [], [], {}
        qa_runs = {scope: 0 for scope in sorted(RUN_SCOPES)}
        qa_runs["undeclared"] = 0
        for item_type, stem, item, _path, exc in _iter_active(state):
            if exc or not isinstance(item, dict):
                continue
            if item_type in ("PR", "RQ"):
                roots.append({
                    "id": item.get("id", stem),
                    "title": item.get("title", ""),
                    "status": item.get("status", ""),
                    "next_step": _NEXT_STEP.get(item.get("status"), "-"),
                })
            elif item_type == "TSK":
                row = {
                    "id": item.get("id", stem),
                    "status": item.get("status", ""),
                    "assigned_role": item.get("assigned_role", ""),
                }
                if item.get("blocked_by"):
                    row["blocked_by"] = item["blocked_by"]
                # The rung and the effort the dispatcher derived are written on the task by the
                # lease (`dispatch.create_lease`, the three `LEASE_*_FIELD`s), and the brief is
                # where a lead meets them (DEC-0077 (5), PR-0010 AC-6); the PM's own ASK per order
                # (DEC-0091, `RUNG_KEY` / `EFFORT_KEY` on the task) rides beside them so the two
                # can be told apart in one row. A task never dispatched carries no lease answer,
                # and its row says nothing rather than a default. Measured missing 2026-09-06 and
                # filed as BUG-0249 because the stream that built the lease was forbidden this file;
                # `tools/test_report.py::test_the_session_brief_shows_the_rung_and_effort_a_lease_wrote_on_the_task`.
                for key in (RUNG_KEY, EFFORT_KEY, LEASE_RUNG_FIELD, LEASE_EFFORT_FIELD,
                            LEASE_PROVIDERS_FIELD):
                    if item.get(key):
                        row[key] = item[key]
                tasks.append(row)
            elif item_type == "DEC":
                decs[item.get("id", stem)] = item
            elif item_type == "EVD" and item.get("kind") in QA_EVIDENCE_KINDS:
                # THE COUNT NOBODY COULD GIVE (BUG-0190). "How often did the suite run, and over
                # how much of it" was prose in a role text, and the reason given for leaving it
                # there was that an `EVD` is immutable -- which is true of the RECORD and says
                # nothing about a ROLLUP. Every record already declares its scope (`RUN_SCOPES`),
                # so the number is a derivation over what is in the store, exactly like every
                # other rollup this module makes. Counted in the walk the brief already does.
                # An `EVD` that declares NO scope is its own bucket rather than folded into
                # `full`: that silence is BUG-0192, and a rollup that hid it would be the second
                # place where an undeclared run counts as a whole one.
                qa_runs[str(item.get("run_scope") or "undeclared")] += 1
        pending, expired_requests = [], 0
        pending_dir = os.path.join(state.root, "approvals", "pending")
        if os.path.isdir(ext_path(pending_dir)):
            for name in sorted(os.listdir(ext_path(pending_dir))):
                if not name.endswith(".yaml"):
                    continue
                try:
                    request = state._read_yaml(os.path.join(pending_dir, name))
                except Exception:
                    continue
                if has_expired(request):
                    # an expired request can never mint -- never show it as
                    # open (Fable-Check 9/NIT-8), only count it. WHY THE RULE IS ASKED AND NOT
                    # SPELLED: this used to compare the clock itself, and so did the board once
                    # FR-0075 gave it the same question -- three spellings of one rule, `H126`.
                    expired_requests += 1
                    continue
                pending.append({
                    "request_id": request["request_id"],
                    "kind": request["kind"],
                    "item": request.get("item") or request["kind"],
                })
        staging = []
        staging_dir = state.staging_root()
        if os.path.isdir(ext_path(staging_dir)):
            # A STAGING KEY IS A DIRECTORY, and this is the SECOND reader of that -- `validate_state`
            # is the other one, and until now only that one asked. A pointer here is printed with a
            # trailing slash, so every FILE under `staging/` was announced to every session as a
            # directory: `staging/.gitkeep/` in every fresh project, and, since the migration prints
            # instructions that put a file there on purpose, a deposit copy as well.
            staging = ["%s/%s/" % (STAGING_DIRNAME, d)
                       for d in sorted(os.listdir(ext_path(staging_dir)))
                       if os.path.isdir(ext_path(os.path.join(staging_dir, d)))]
        findings = validate_state(state, _locked=True)
        brief = {
            "kit": kit,
            "kit_version": kit_version,
            "enforcement_mode": enforcement_mode,
            "generated_at": _now_iso(),
            "active_roots": roots,
            "active_tasks": tasks,
            "open_approvals": pending,
            "staging_pointers": staging,
            "standing_decisions": _brief_decision_rows(decs),
            # THE DISTRIBUTION LINE (DEC-0092 (4)): the same last-N reading the spawn gate's
            # checkpoint shows the PM, here where the USER meets the brief, so a habit --
            # always one builder, always the top rung -- is a line and not a search.
            "lease_distribution": lease_distribution(state),
            "budget_status": {
                "validator_errors": sum(1 for f in findings if f["severity"] == "error"),
                "validator_warnings": sum(1 for f in findings if f["severity"] == "warning"),
                "expired_requests": expired_requests,
                # `tools/test_report.py::test_the_brief_counts_the_qa_runs_by_the_scope_they_declare`
                "qa_runs": qa_runs,
            },
        }
        validate(brief, "session_brief")
        path = state.generated_path("session_brief.yaml")
        state._write_yaml_atomic(path, brief)
        return path


# -- state validator (gate layer 4) --------------------------------------------

def validate_state(state: ProjectState, _locked: bool = False) -> list:
    """Full fail-closed scan; returns findings (empty = valid).

    `_locked=True` skips taking the kernel lock -- ONLY for callers that
    either already hold it (generate_session_brief) or are explicitly
    read-only-racy by design (doctor). Everyone else uses the default.

    GRAPH-WALKING DUTIES this validator owns (spec II.4 gate 4). They were named
    as open in the phase-2 review of 2026-07-25 and are implemented below; the
    reasoning is kept because it is what makes each one a decision rather than a
    rule someone happened to write:
    * `approvals/consumed/**` must be DIFF-CLEAN against HEAD. A minted request
      is immutable once written, and `approvals/**` is committed (II.2 excludes
      only kit_state.json, generated/** and the lock), so a re-hashed request --
      the one forgery `consumed_request` cannot detect arithmetically, because
      the hash function is public -- shows up as a git diff on a file that must
      never change. That turns the documented residual from "undetectable" into
      "detected at the next validate/merge".
    * `apr["expires"]` must equal `request["subject_manifest"]["expires"]`. The
      APR copy is a derived display value; if the two disagree, a human reads a
      validity the gate correctly refuses.
    * A TSK's `derives_from` must belong to its ROOT's tree -- BUG.related_pr ==
      root, CR.target_pr == root, EXP -> HYP -> RQ == root. The kernel already
      refuses phantom origins at capture, but the dispatch gate resolves
      `acceptance_refs` against the origin, so an origin from an UNRELATED root
      lets a task be judged against borrowed criteria. Authorisation is
      unaffected (that comes only from the root's approval), and the mislabel is
      recorded in a committed file and frozen outside DRAFT -- which is why it
      belongs to this graph-walking layer rather than to the hot path. A task
      deriving from a TERMINAL/archived origin (e.g. a REJECTED bug) is stale and
      should be flagged the same way.
    """
    if not _locked:
        with state.lock:
            return validate_state(state, _locked=True)
    findings = []
    seen_ids = {}
    active_items = {}
    opened_paths = []
    diagram_entries = []
    for item_type, stem, item, path, exc in _iter_active(state):
        rel = os.path.relpath(path, state.root)
        opened_paths.append(path)
        # THE SAME WALK, IN THE SAME ORDER, is what the generated pictures are rendered from, so
        # the rows for them are collected HERE and not by a second walk of the store (BUG-0211;
        # `ProjectState.board_row` carries the measurement that decided it). Before the corrupt
        # branch below, because the renderer has a row for that case too.
        diagram_entries.append((state.board_row(item_type, stem, item),
                                item if isinstance(item, dict) else None))
        if exc or not isinstance(item, dict):
            findings.append(_finding(
                "error", stem, "corrupt item file (%s)" % (exc or "non-mapping"),
                "git restore %s && python scripts/harness.py generate-index" % rel,
            ))
            continue
        item_id = item.get("id", stem)
        active_items[item_id] = (item_type, item)
        if item_id in seen_ids:
            findings.append(_finding(
                "error", item_id, "duplicate id (also at %s)" % seen_ids[item_id],
                "merge/rename one of the two items -- ids are unique (spec II.4 gate 5)",
            ))
        seen_ids[item_id] = rel
        # field duties, over BOTH contract sources (`DECLARED_REQUIRED_FIELDS`): what a stored
        # item must CARRY, not what a caller must hand `capture`. Reading the capture map alone
        # made this loop run zero times for `ARC`, `WFR` and `DSN` -- the three types whose duties
        # live in `kernel/schemas/` -- so a hand-written architecture companion with no
        # `derives_from` was reported by nobody, the finding spec II.8 names outright.
        for field in required_fields_of(item_type, item):
            if field not in item:
                findings.append(_finding(
                    "error", item_id, "missing required field %r" % field,
                    "add the field (spec II.2 Pflichtfelder)",
                ))
        # status validity
        auto = AUTOMATA.get(item_type)
        if auto and item.get("status") not in auto.states:
            findings.append(_finding(
                "error", item_id, "unknown status %r" % item.get("status"),
                "use `python scripts/harness.py transition` with a defined status",
            ))
        elif auto and item.get("status") in auto.terminals:
            # II.2: Geschlossenes verlaesst den aktiven Kontext
            findings.append(_finding(
                "warning", item_id,
                "terminal item (%s) awaiting archive" % item.get("status"),
                "run `python scripts/harness.py archive %s`" % item_id,
            ))
        # status-dependent duties (Fable-Check 7/NIT-1) -- the map, so a new duty is a row in
        # `backlog_types.STATUS_DEPENDENT_FIELDS` and not another branch here
        status = item.get("status")
        owed = STATUS_DEPENDENT_FIELDS.get((item_type, status))
        if owed and not item.get(owed):
            findings.append(_finding(
                "error", item_id, "%s without %s" % (status, owed),
                "record `%s` -- %s owes it in this status and in no other" % (owed, item_type),
            ))
        # THE APPROVAL STAMP, judged for PRESENCE and for TRUTH. Which statuses carry the duty is
        # asked of `approved_statuses` (the automaton plus `APPROVAL_TRANSITIONS`) rather than
        # written out as ("APPROVED", "ACTIVE") -- the pair this line used to carry was a copy of
        # the PROC chain, and a copy of a chain is what goes stale when the chain moves.
        # Spec II.2 lists `approved_hash` for PROC, so the DUTY stays PROC's; the second half is
        # new and is the point of stamping at all: a stamp that no longer matches the content is a
        # worse lie than a missing one, because it reads as proof.
        if item_type == "PROC" and status in approved_statuses(item_type):
            recorded = item.get(APPROVED_CONTENT_HASH_FIELD)
            if not recorded:
                findings.append(_finding(
                    "error", item_id, "%s PROC without approved_hash" % status,
                    "re-run the approval flow -- the mint stamps the hash (spec II.2)",
                ))
            else:
                try:
                    current = approved_content_hash(item_type, item)
                except (TypeError, ValueError) as exc:
                    current, recorded = None, "unhashable content (%s)" % type(exc).__name__
                if current != recorded:
                    findings.append(_finding(
                        "error", item_id,
                        "approved_hash no longer matches the PROC's own %s -- it was edited past "
                        "the kernel after approval"
                        % "/".join(HASHED_FIELDS.get(item_type, ())),
                        "restore the approved content, or re-run the approval flow for the new one",
                    ))
        if (item_type == "PR" and item.get(GOAL_CLASS_FIELD) not in PRODUCTLESS_CLASSES
                and not item.get("user_story")):
            findings.append(_finding(
                "warning", item_id, "user_story missing (class %r)" % item.get(GOAL_CLASS_FIELD),
                "add a user_story or set class %s" % ", ".join(sorted(PRODUCTLESS_CLASSES)),
            ))
        if item_type == "INV" and not (("text" in item) ^ ("value" in item)):
            findings.append(_finding(
                "error", item_id, "INV needs exactly one of text|value",
                "set exactly one of the two",
            ))
        # budgets (spec II.5)
        try:
            size = os.path.getsize(ext_path(path))
            with open(ext_path(path), encoding="utf-8") as fh:
                lines = sum(1 for _ in fh)
            if size > ITEM_MAX_BYTES or lines > ITEM_MAX_LINES:
                findings.append(_finding(
                    "error", item_id,
                    "item exceeds budget (%d bytes / %d lines; max %d/%d)"
                    % (size, lines, ITEM_MAX_BYTES, ITEM_MAX_LINES),
                    "keep the summary in the item and capture the detail as an evidence item of "
                    "its own through the entry point, then reference it (spec II.5)",
                ))
        except OSError:
            pass
    # reference graph + approval integrity (D/4)
    for item_id, (item_type, item) in active_items.items():
        # THE PARENT BINDINGS, taken from `_parents_of` -- the same hop the graph walks, so a
        # binding the merge gate resolves and a binding this validator judges cannot be two
        # different sets. Listed instead, this knew `product_requirement`, `related_pr` and
        # `target_pr`, and `derives_from` was in none of them: an `SR`, `HYP` or `EXP` pointed at
        # an id that exists nowhere was reported by nobody, in the layer whose whole job is the
        # reference graph.
        #
        # ONE binding is judged more strictly, and it is a rule about that field rather than about
        # a type: `product_requirement` must be ACTIVE, because the dispatch gate reads the root of
        # the task it is about to lease. Every other parent may legitimately have been ARCHIVED --
        # a BUG against an accepted PR (Fable-Check 9/#1), Evidence about a task archived the moment
        # it reached VALIDATED.
        for field, ref in _parent_bindings(item_type, item):
            if ref in active_items:
                continue
            if field == "product_requirement":
                findings.append(_finding(
                    "error", item_id, "product_requirement -> %s does not exist (active)" % ref,
                    "fix the reference or restore the item",
                ))
            elif not _in_archive(state, ref):
                findings.append(_finding(
                    "error", item_id,
                    "%s -> %s exists neither active nor archived" % (field, ref),
                    "fix the reference or restore the item",
                ))
        for dep in field_elements(item.get("dependencies")):
            if dep not in active_items and not _in_archive(state, dep):
                findings.append(_finding(
                    "error", item_id, "dependency %s does not exist" % dep,
                    "fix the dependency list",
                ))
        apr_ref = item.get("approval_ref")
        if apr_ref:
            apr_path = os.path.join(state.root, "approvals", apr_ref + ".yaml")
            try:
                apr = state._read_yaml(apr_path)
            except Exception:
                findings.append(_finding(
                    "error", item_id, "approval_ref %s has no APR file" % apr_ref,
                    "manually written approvals never count -- re-run the approval flow",
                ))
                continue
            # WHETHER THE PRESENTED APPROVAL STILL GRANTS ANYTHING IS ONE QUESTION WITH ONE
            # ANSWER, and this used to be a second one. `assert_apr_in_force` is what
            # `assert_transition_approved` and the dispatch route decide on -- revoked, provenance,
            # which item it binds to, the clock, and the content hash for the kinds that carry one
            # -- and this block recomputed two of those five for itself. That copy went wrong the
            # moment a kind arrived whose binding is not one item: a `plan` approval carries
            # `item: None` and `revision: None` by construction (its subject is the goal LIST), so
            # the private comparison read every goal it covers as an out-of-band edit and
            # `gate_memory_complete` closed merge and push on it -- measured as a process, rc 0
            # before the plan approval and rc 2 after it, with a remedy that named a change nobody
            # had made. Asked here, the plan branch is the same branch the transition walked.
            # `tools/test_report.py::test_a_plan_approved_goal_is_not_reported_as_an_out_of_band_edit`
            # and `tools/test_hooks.py::test_a_plan_approval_does_not_close_the_merge_gate`.
            try:
                assert_apr_in_force(state, apr, item)
            except ApprovalError as exc:
                findings.append(_approval_integrity_finding(item_id, exc))
    findings.extend(_check_consumed_requests_diff_clean(state))
    findings.extend(_check_approval_expiry_agrees(state, active_items))
    findings.extend(_check_task_origins(state, active_items))
    findings.extend(_check_tasks_under_an_inbox_item(active_items))
    findings.extend(_check_bug_system_link(state, active_items))
    findings.extend(_check_invariant_checks(state, active_items))
    findings.extend(_check_generated_diagrams(state, diagram_entries))
    findings.extend(_check_board_is_as_fresh_as_the_index(state))
    findings.extend(_check_filing_coverage_was_compared(state))
    findings.extend(_check_every_stored_file_reads(state, opened_paths))
    findings.extend(_check_accepted_tasks_carry_a_verdict(state, active_items))
    findings.extend(_check_confirmations_agree_with_the_verdicts(state, active_items))
    findings.extend(_check_experiment_reports(active_items))
    findings.extend(_check_premise_recheck(state, active_items))
    findings.extend(_check_fr_result_link(state, active_items))
    findings.extend(_check_dec_supersedes(state, active_items))
    findings.extend(_check_decision_carriers(state, active_items))
    findings.extend(_check_reference_list_shape(active_items))
    findings.extend(_check_single_value_fields(active_items))
    findings.extend(_check_nonempty_fields(active_items))
    findings.extend(_check_design_refs_resolve(state, active_items))
    findings.extend(_check_ui_delivery_sequence(active_items))
    findings.extend(_check_dispatch_approval_presented(state, active_items))
    # staging orphans: neither an active task nor an active root item
    staging_dir = state.staging_root()
    if os.path.isdir(ext_path(staging_dir)):
        for entry in sorted(os.listdir(ext_path(staging_dir))):
            # A staging KEY is a directory named after an item. The template ships `staging/.gitkeep`
            # so git can carry the empty directory, and reading that file as a key put a warning into
            # every `python scripts/harness.py validate` and every session brief of every fresh project.
            if not os.path.isdir(ext_path(os.path.join(staging_dir, entry))):
                continue
            opened_paths.append(os.path.join(staging_dir, entry))
            if entry in active_items:
                continue
            # AND AN ACTIVE RECORD POINTING INTO IT IS NOT AN ORPHAN EITHER (BUG-0032). An
            # Evidence's `artifact_refs` is where its raw proof lives -- the record IS the pointer,
            # and "remove it" would destroy what the record stands for. Measured in this store: the
            # generation-6 streams wrote `staging/<task-id>/protocol.md` into their evidence, so
            # every one of those task directories was reported as orphaned the moment the task
            # closed. Asked of the REFERENCES the store carries, not of the directory's name.
            holders = _items_pointing_into_staging(active_items, entry)
            if holders:
                continue
            findings.append(_finding(
                "warning", "staging/%s" % entry,
                "orphaned staging dir (no active task or root item, and no active record points "
                "into it)",
                "promote, archive or remove via the kernel staging lifecycle",
            ))
    # lease hygiene
    lease_dir = os.path.join(state.root, "tasks", "leases")
    if os.path.isdir(ext_path(lease_dir)):
        for name in sorted(os.listdir(ext_path(lease_dir))):
            if not name.endswith(".lease.yaml"):
                continue
            opened_paths.append(os.path.join(lease_dir, name))
            task_id = name[: -len(".lease.yaml")]
            if task_id not in active_items:
                findings.append(_finding(
                    "warning", task_id, "lease without active task",
                    "remove the lease (doctor) -- sweep cannot resolve it",
                ))
    # stale-break remnants (lock module leftovers)
    for name in os.listdir(ext_path(state.root)):
        if name.startswith(".kernel.lock.stale-"):
            findings.append(_finding(
                "warning", name, "stale-break remnant lockfile",
                "safe to delete after inspection (doctor)",
            ))
    findings.extend(_check_no_v1_records_outside_the_archive(state))
    findings.extend(_check_portable_path_budget(opened_paths))
    return findings


def _check_portable_path_budget(paths) -> list:
    """Spec II.4's other half (FR-0037): warn while the tree is still openable by everything else.

    The kernel itself is not the endangered reader -- every state file operation goes through
    `lock.ext_path` -- so the finding is a WARNING and says whose problem it is: git, an editor
    and a sync client open the same files without that prefix.

    ONE FINDING, NOT ONE PER FILE. Depth is a property of the tree: in a project that has this
    problem at all, nearly every item has it, and a per-item warning would push every other
    finding out of the report to repeat a single fact.

    WHAT IT MEASURES IS WHAT THE SCAN ALREADY OPENED -- active items, staging keys, leases -- so
    it adds no second walk to a validator that holds the kernel lock. A file deeper inside a
    staging directory is therefore NOT seen; both halves are measured by
    `tools/test_report.py::test_a_state_tree_past_the_portable_path_limit_is_warned_once`.
    """
    lengths = sorted(((len(os.path.abspath(p)), p) for p in paths), reverse=True)
    over = [(n, p) for n, p in lengths if n > PORTABLE_PATH_MAX_CHARS]
    if not over:
        return []
    longest, where = over[0]
    return [_finding(
        "warning", os.path.basename(where),
        "%d state path(s) are longer than %d characters (longest: %d) -- the kernel opens them "
        "through extended-length paths, git, editors and sync clients do not"
        % (len(over), PORTABLE_PATH_MAX_CHARS, longest),
        "move the project closer to the drive root, or shorten the directory names above it",
    )]


# -- a soft duplicate hint at capture (FR-0018) --------------------------------

# THE SCORE ABOVE WHICH TWO ITEMS OF ONE TYPE ARE WORTH LOOKING AT, and the only number this
# hint has. It sits in the middle of a MEASURED EMPTY BAND rather than at a value anyone liked:
# every same-type pair of this repository's own store was scored (2026-09-02, with the tokenizer
# above and not with a second one), and so was the case the FR is about -- the same requirement
# written a second time, keeping part of its wording. The honest pairs stop well below this line
# and the re-requests start well above it, with nothing in between; the distributions, the store
# and its size are in the TSK-0106 protocol, where a number that describes one round belongs.
# `test_report.test_the_duplicate_hint_stays_quiet_on_ordinary_neighbours` is where the band stays
# measured: it carries one pair BELOW this line and one ABOVE it, so a threshold low enough to nag
# and one high enough to go quiet each turn it red. That claim was untrue for one round -- the
# fixtures grew and the pairs drifted out of the band while the sentence stayed.
DUPLICATE_HINT_SIMILARITY = 0.45
# Three, because the hint is read at the moment an item is created and a list one cannot take in
# at a glance is one nobody reads. `similar_items` returns them ranked, so a fourth near-match is
# never the one that mattered most.
DUPLICATE_HINT_LIMIT = 3
# HOW MUCH AN ITEM HAS TO SAY BEFORE IT IS COMPARED AT ALL, and this number sits in a band as wide
# as the other one is narrow. A ratio over a handful of words is decided by a single shared one:
# two unrelated bugs reading "404 -> 200" and "500 -> 200" share `200` and their severity and score
# 0.5 -- over the threshold, on nothing. Measured on the same store (2026-09-02): the SMALLEST real
# item carries 49 content words and the smallest union of any honest pair is 93, while the noise
# cases live at four to eight. Below this line the hint says nothing rather than something it
# cannot mean. `test_report.test_the_duplicate_hint_says_nothing_about_items_too_small_to_compare`
# holds both edges.
DUPLICATE_HINT_MIN_WORDS = 20
# A WORD IS A RUN OF LETTERS IN ANY SCRIPT, and that is a rule rather than an alphabet. `[a-z]`
# is an enumeration of one language's letters: it cut `Prüfung der Größe` into `der` and `fung`
# and read `ÄÖÜ` as nothing at all -- so two unrelated German items scored 0.625 on their
# leftovers, over any threshold this hint could carry. Digits are kept only in runs of three
# (a year, an amount); shorter ones are list indices and item numbers.
_HINT_WORD = re.compile(r"[^\W\d_]{3,}|\d{3,}", re.UNICODE)


def _content_words(item: dict, fields) -> set:
    """The words an item's OWN CONTENT is made of, flattened out of nested fields.

    WHICH FIELDS ARE THE CONTENT is not decided here: `HASHED_FIELDS` already answers it for the
    kernel, because those are the fields whose change invalidates an approval -- the substance of
    the item as this project has already defined it. A type the kernel has no such definition for
    gets no hint rather than a guess over whatever strings it happens to carry, and both ends of
    that are measured in
    `test_report.test_the_duplicate_hint_covers_every_type_whose_content_the_kernel_defines`.

    Words shorter than three characters are dropped: they are articles and ids' separators, and
    they made every pair of items look alike.
    """
    parts = []

    def flatten(value):
        if isinstance(value, dict):
            for one in value.values():
                flatten(one)
        elif isinstance(value, (list, tuple)):
            for one in value:
                flatten(one)
        elif value is not None:
            parts.append(str(value))

    flatten(item.get("title"))
    for field in fields:
        flatten(item.get(field))
    return set(_HINT_WORD.findall(" ".join(parts).lower()))


def similar_items(state: ProjectState, item_type: str, fields: dict,
                  exclude: str = None) -> list:
    """The active items of the SAME type whose content overlaps `fields` -- ranked, never a block.

    A SOFT HINT AND NOTHING MORE (FR-0018). The user's own reasoning is the design: requirements
    resemble each other, so a hard refusal would fire on honest work far more often than on a
    real duplicate, and the role chain catches most true duplicates anyway. What was missing was
    the one moment a machine can help at no cost -- the moment of writing a second copy.

    SAME TYPE ONLY, which is the rule and not a shortcut: a BUG and the SR it was found against
    share most of their vocabulary and are never each other's duplicate.

    Overlap is the Jaccard ratio of the two content word sets -- symmetric, insensitive to how
    long the items are, and free of any per-field weighting nobody could justify. It is a hint;
    the ranking is what it owes, not a similarity anyone should quote.

    "NEVER A BLOCK" IS A CLAIM AND THEREFORE A TEST:
    `tools/test_staging_cli.py::test_capture_names_the_neighbours_it_found_and_captures_the_item_anyway`
    runs the real capture and reads the exit code, the id on stdout and the hint on stderr.
    """
    contract = HASHED_FIELDS.get(item_type)
    if not contract:
        return []
    mine = _content_words(fields, contract)
    if len(mine) < DUPLICATE_HINT_MIN_WORDS:
        return []
    scored = []
    for stem, path in state.iter_active_items(item_type):
        try:
            other = state._read_yaml(path)
        except Exception:
            continue                     # an unreadable item is the validator's finding, not this
        if not isinstance(other, dict):
            continue
        other_id = str(other.get("id") or stem)
        if exclude and other_id == exclude:
            continue
        theirs = _content_words(other, contract)
        if len(theirs) < DUPLICATE_HINT_MIN_WORDS:
            continue
        score = len(mine & theirs) / float(len(mine | theirs))
        if score >= DUPLICATE_HINT_SIMILARITY:
            scored.append({"id": other_id, "title": other.get("title"), "score": round(score, 3)})
    scored.sort(key=lambda row: (-row["score"], row["id"]))
    return scored[:DUPLICATE_HINT_LIMIT]


# -- an invariant's check, resolved (FR-0039) ----------------------------------

# HOW A CHECK NAMES ITS TEST. `INV.check` is a mapping whose `ref` is a test node id -- the path of
# the file, then the names inside it, separated by this. It is the shape the kits' own invariants
# are written in and the shape a role pastes out of a test runner; the kernel does not invent a
# second one.
INVARIANT_REF_SEPARATOR = "::"


def _marker_chain(node) -> list:
    """The dotted name a decorator (or a `pytestmark` value) is written as, outermost last.

    `pytest.mark.skip` and `pytest.mark.skip(reason=...)` are the same marker to this reader: the
    call wrapper is unwrapped, so what is compared is the NAME and never the spelling.
    """
    target = node.func if isinstance(node, ast.Call) else node
    parts = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return list(reversed(parts))


def _marker_verdict(node):
    """(verdict, why) for ONE marker, or None when this marker says nothing about execution.

    THE RULE IS ABOUT WHO DECIDES, not about a list of marker names. `skip` is decided by the
    source and the answer is `False`. `skipif` is decided by the RUNNER when it evaluates the
    condition, so the source cannot answer and the verdict is the module's third answer, `None`.
    A `parametrize` with no cases generates no test at all, which the source does decide.
    Only markers written under `mark` count -- a decorator of the project's own that happens to
    end in the same word is not a pytest marker, and reading it as one would refuse a check that
    runs perfectly well.
    `tools/test_report.py::test_a_check_whose_test_is_skipped_resolves_to_nothing_it_can_run`
    """
    chain = _marker_chain(node)
    if "mark" not in chain[:-1]:
        return None
    marker = chain[-1]
    if marker == "skip":
        return False, "carries a `skip` marker"
    if marker == "skipif":
        return None, ("carries a `skipif` marker whose condition the runner evaluates, which this "
                      "kernel does not")
    if marker == "parametrize" and isinstance(node, ast.Call) and len(node.args) >= 2:
        cases = node.args[1]
        if isinstance(cases, (ast.List, ast.Tuple, ast.Set)) and not cases.elts:
            return False, "is parametrised with an empty case list, so no test is generated"
    return None


def _unrunnable_tests(tree) -> dict:
    """{test name: (verdict, why)} for every definition this file tells the runner not to execute.

    The companion of the name scan in `invariant_check_resolution`: the name says the definition
    is there, this says whether it would RUN. A module-level `pytestmark` is read too, because it
    carries the same declaration for every test in the file.
    `tools/test_report.py::test_a_check_whose_test_is_skipped_resolves_to_nothing_it_can_run`
    """
    module_wide = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark"
                   for target in node.targets):
            continue
        values = (node.value.elts if isinstance(node.value, (ast.List, ast.Tuple))
                  else [node.value])
        for value in values:
            module_wide = _marker_verdict(value) or module_wide
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        verdict = module_wide
        for decorator in getattr(node, "decorator_list", []):
            verdict = _marker_verdict(decorator) or verdict
        if verdict is not None:
            found[node.name] = verdict
    return found


def invariant_check_resolution(state: ProjectState, item: dict, parsed_names: dict = None):
    """(resolved, reason) for one INV's `check` -- does it point at a test that EXISTS?

    THE FIELD `verified` HAD NO PRODUCER (spec II.12, FR-0039). `backlog_types` conceded it in a
    comment: an invariant becomes verified once its check test exists and is collectable, and
    nothing in this kernel established that -- so `verified` was a word in a vocabulary and every
    invariant of every project stood at `unverified` for ever.

    COLLECTABLE IS DECIDED BY PARSING, NOT BY RUNNING. What a test run costs and which runner a
    project uses is a fact about the project (the same argument `RUN_SCOPES` carries for a run's
    scope); what the kernel can answer on its own is whether the file exists and whether the name
    the ref ends in is DEFINED in it. That is the half II.12 makes the merge depend on, and it is
    the half a role can be wrong about by accident -- a renamed test, a deleted file.

    THREE ANSWERS AND NOT TWO, and the third is what keeps this from being an unclearable block.
    True is "the test is there"; False is "it is not, and that is decidable" -- a check with no
    ref, a file that is not there, a Python file that does not define the name. None is "this
    kernel cannot tell": a test file in a language it does not parse. A kernel three kits share
    would otherwise block every merge of every project whose tests are not Python, for ever, with
    no command that could clear it -- and a rule nobody can satisfy is worked around, not met.
    `H110` in `docs/POST_V2_WISHLIST.md` carries that limit with its measurement.

    AND A DEFINITION THE RUNNER IS TOLD NOT TO EXECUTE IS NOT A CHECK (BUG-0193). The same parse
    that finds the name reads what stands ON it: a `skip` marker, or a parametrisation with no
    cases, means the test is there and never runs, and that is `False` with its own sentence. A
    `skipif` is the third answer instead, because its condition is evaluated by the runner and the
    source does not decide it. What stays out of reach is what is not in the file at all -- a
    marker the project's own configuration deselects -- and the reason is the same one this
    function gives everywhere: the runner's configuration is a fact about the project.
    `_unrunnable_tests` is where that reading lives.

    The path is read relative to the PROJECT root -- the directory the state tree sits in, which is
    where a role runs the test runner from. Every outcome gets its own sentence, because the
    remedies differ.

    `parsed_names` IS A CACHE FOR ONE SCAN AND NOTHING MORE. Invariants of one project point at the
    same few test files, and this runs inside `validate_state`, which a MERGE GATE waits for: 30
    invariants against one 0.5 MB test file cost 6.1-6.9 s per scan measured without it, and the
    kits register no timeout for that gate -- a hook killed by the provider reads as "carry on",
    i.e. as a pass. A caller that passes no cache parses per item, which is right for the single
    reads (`state.record_invariant_verification`), where a stale answer would be worse than a
    parse. `tools/test_report.py::test_one_scan_parses_each_test_file_once` holds it.
    """
    check = item.get("check")
    if not isinstance(check, dict):
        return False, "check is not a mapping with a `ref` -- there is nothing to resolve"
    refs = field_elements(check.get("ref"))
    if len(refs) != 1 or not str(refs[0]).strip():
        return False, "check names no single `ref` to resolve"
    ref = str(refs[0]).strip()
    head, sep, tail = ref.partition(INVARIANT_REF_SEPARATOR)
    if not sep or not tail.strip():
        return False, ("check ref %r names no test inside a file -- the shape is "
                       "<path>%s<test name>" % (ref, INVARIANT_REF_SEPARATOR))
    name = tail.split(INVARIANT_REF_SEPARATOR)[-1].strip()
    # A parametrised node id carries its case in brackets; the DEFINITION is the name before it.
    name = name.split("[")[0].strip()
    path = os.path.join(os.path.dirname(os.path.abspath(state.root)), *head.split("/"))
    if not os.path.isfile(ext_path(path)):
        return False, "check ref %r names %s, which does not exist" % (ref, head)
    key = os.path.abspath(path)
    cached = parsed_names.get(key) if parsed_names is not None else None
    if cached is None:
        try:
            with open(ext_path(path), encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
        except (OSError, SyntaxError, ValueError) as exc:
            cached = type(exc).__name__
        else:
            cached = ({node.name for node in ast.walk(tree)
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))},
                      _unrunnable_tests(tree))
        if parsed_names is not None:
            parsed_names[key] = cached
    if isinstance(cached, str):
        return None, ("check ref %r names %s, which this kernel cannot read as a test file (%s) -- "
                      "it resolves a check by PARSING it, and that reaches Python. Whether this "
                      "test exists is a question for the project's own runner" % (ref, head, cached))
    defined, unrunnable = cached
    if name not in defined:
        return False, "check ref %r names %s, which %s does not define" % (ref, name, head)
    verdict, why = unrunnable.get(name, (True, None))
    if verdict is not True:
        return verdict, ("check ref %r names %s, which %s defines and %s -- a definition the "
                         "runner does not execute checks nothing" % (ref, name, head, why))
    return True, "%s defines %s" % (head, name)


def _items_pointing_into_staging(active_items: dict, key: str) -> list:
    """The active items whose `artifact_refs` name a path under `staging/<key>/` -- BUG-0032.

    ONE FIELD AND NOT EVERY STRING IN THE STORE: `artifact_refs` is the field whose whole purpose
    is to point at a file outside the item ("evidence references its artefacts, never inlines
    them", `evidence --artifact-ref`), so it is the field that can hold a staging directory alive.
    A mention in prose is not a reference and is deliberately not read -- that would make any item
    that discussed a directory keep it.

    The comparison is on the KEY, i.e. the first segment after `staging/`, because that is what a
    staging directory IS; a reference to a file deeper inside holds the directory just as much.
    `tools/test_report.py::test_a_staging_dir_an_active_record_points_into_is_not_an_orphan`
    """
    prefix = "%s/%s/" % (STAGING_DIRNAME, key)
    holders = []
    for item_id, (_item_type, item) in sorted(active_items.items()):
        for reference in field_elements(item.get("artifact_refs")):
            spelled = str(reference).replace("\\", "/").lstrip("./")
            if spelled.startswith(prefix):
                holders.append(item_id)
                break
    return holders


def _check_every_stored_file_reads(state: ProjectState, opened_paths: list) -> list:
    """BUG-0236, second residue: an ARCHIVED item with broken YAML was silent in every reader.

    The active walk above reports a corrupt item file, and it never reaches the archive -- while
    `state._iter_every_stored_item`, which does, skips what it cannot read because it is asked for
    items. Measured on H156 with its YAML destroyed: all three hole checkers exited 0.

    ONLY THE FILES THE ACTIVE WALK DID NOT OPEN, so one broken item is one finding: the walk that
    already reported it passes its paths in.
    """
    already = {os.path.abspath(path) for path in opened_paths}
    findings = []
    for path, why in state.unreadable_stored_files():
        if os.path.abspath(path) in already:
            continue
        findings.append(_finding(
            "error", os.path.splitext(os.path.basename(path))[0],
            "stored file %s does not read (%s) -- every reader over the store skips it in silence"
            % (os.path.relpath(path, state.root).replace(os.sep, "/"), why),
            "repair the YAML (it is under git: `git diff` shows what happened to it) or remove the "
            "file; a record nothing can read is a record nothing counts"))
    # THE OTHER HALF OF THAT WALK'S BOUND. It refuses to OPEN a stored file over
    # `DOCUMENT_MAX_BYTES` -- this validator runs on a hook path with a time budget -- and a skip
    # nobody reports is the silence the walk above exists against.
    #
    # ONLY FOR AN ITEM FILE, and the line that decides is `parse_id` rather than a directory list:
    # an over-sized DOCUMENT is already reported by the bounded document scan in this same
    # validator, by path and with this same remedy, so a second finding about it would be one file
    # told to a reader twice. What that scan does NOT reach is an ITEM file -- an archived record
    # nothing else opens -- and that is the one this reports.
    for path, size in state.oversized_stored_files():
        if os.path.abspath(path) in already:
            continue
        try:
            parse_id(os.path.splitext(os.path.basename(path))[0])
        except ValueError:
            continue
        findings.append(_finding(
            "error", os.path.splitext(os.path.basename(path))[0],
            "stored file %s was NOT READ: it is %d bytes and this validator opens at most %d bytes "
            "of one stored file, so whether it holds a record is unknown -- unknown is not empty"
            % (os.path.relpath(path, state.root).replace(os.sep, "/"), size, DOCUMENT_MAX_BYTES),
            "split the file or take it out of the state directory (an editor or shell outside the "
            "session -- an export of this size is a business record, not project state), then run "
            "`python scripts/harness.py validate` again"))
    return findings


def _check_filing_coverage_was_compared(state: ProjectState) -> list:
    """BUG-0152: an interview nobody walked read exactly like a plan that covers everything.

    `filing.uncovered_document_sources` answers "which sources have no rule", and it answers the
    empty list both when every source is covered and when there was nothing to compare at all. The
    third answer lives in `filing.coverage_not_compared`; this is what says it out loud, so the
    silence stops being a pass. A WARNING: the plan may be perfectly good, and what is missing is
    an ANSWER about it -- `gate_filing` is what fails closed on a plan with no rules.

    A project with no profile is not judged at all: the file belongs to the office kit.
    """
    from . import filing                  # lazy: `filing` imports `approvals`, which imports this
    try:
        reason = filing.coverage_not_compared(state)
    except Exception as exc:              # noqa: BLE001 -- a validator never fails on its reader
        reason = "the filing profile could not be read (%s: %s)" % (type(exc).__name__, exc)
    if not reason:
        return []
    return [_finding(
        "warning", "filing", "the filing plan's coverage was not compared: %s" % reason,
        "walk the onboarding interview with the user and record what the business receives in "
        "`business_profile.yaml` -- until then nothing here can say whether the plan covers it")]


def _check_board_is_as_fresh_as_the_index(state: ProjectState) -> list:
    """BUG-0140: a board that could not be rewritten froze the DISPLAY and said so once, on stderr.

    `state._write_board` is fail-soft on purpose -- a file the operating system will not let it
    replace (the page open in a viewer is the measured case) must not fail the state write itself.
    It prints one line at the moment it happens, and the session that reads the page an hour later
    saw nothing. This is the standing line the item names as its closing direction.

    MTIME AND NOT THE TIMESTAMP INSIDE THE PAGE, because the two files are written in one call from
    one clock reading: the index goes first, the board second, so a board OLDER than the index is
    exactly a write that did not happen. Reading the stamp out of the rendered HTML would be a
    second reader of a format `kernel.board` owns.
    A board that is not there at all is not judged -- a store nobody has written has no stale page.
    `tools/test_report.py::test_a_board_that_could_not_be_rewritten_is_reported_as_older_than_the_index`
    """
    from . import board                   # lazy: `board` imports this module's neighbours
    index = ext_path(state.generated_path("index.yaml"))
    page = ext_path(state.generated_path(board.FILENAME))
    if not (os.path.isfile(index) and os.path.isfile(page)):
        return []
    if os.path.getmtime(page) >= os.path.getmtime(index):
        return []
    return [_finding(
        "warning", "generated",
        "%s is older than %s -- the last state write could not replace the page, so what it shows "
        "is not what the store holds" % (board.FILENAME, "index.yaml"),
        # NO PATH INSIDE THE STATE DIRECTORY IN A REMEDY (DEC-0024): a name a reader takes from a
        # remedy is one they picked, and it can already be taken. The index is named by its role.
        "close whatever holds the file open (a viewer locks it on this platform) and run any "
        "kernel command that writes state; until one succeeds, the generated index beside it is "
        "the current record and this page is not")]


def _check_generated_diagrams(state: ProjectState, entries: list) -> list:
    """BUG-0211: a hand edit to a generated diagram was seen by nobody until it was overwritten.

    A WARNING AND NOT AN ERROR, and the two verdicts are warnings for different reasons. A HAND
    EDIT is work somebody is about to lose at the next state write, and the remedy is to save it
    elsewhere -- nothing about the state is wrong, so blocking a merge on it would punish the
    wrong thing. A STALE picture is nobody's mistake and repairs itself at the next write; it is
    reported because between the two writes a reader is looking at a plan that is not the store's.
    A file that is not on disk is not judged at all -- see `plan_diagram.verdicts`.

    `foreign` is deliberately silent: it is the answer for a name this renderer does not produce,
    and `verdicts` only ever asks about the names it does.
    """
    from . import plan_diagram          # lazy: the renderer imports nothing of this module's
    findings = []
    try:
        judged = plan_diagram.verdicts(state.generated_path(""), entries)
    except Exception as exc:            # noqa: BLE001 -- a validator never fails on its own reader
        return [_finding("warning", "generated", "the generated diagrams could not be judged "
                                                 "(%s: %s)" % (type(exc).__name__, exc),
                         "run any kernel write to rebuild them, then validate again")]
    for name, verdict, reason in judged:
        if verdict == "hand-edited":
            findings.append(_finding(
                "warning", "generated", "%s was edited by hand (%s)" % (name, reason),
                # No path inside the state directory in a remedy (DEC-0024) -- see the board check.
                "the next state write regenerates it -- save the edit outside the state directory "
                "now, or change the items the picture is rendered from"))
        elif verdict == "stale":
            findings.append(_finding(
                "warning", "generated", "%s is older than the state it shows (%s)" % (name, reason),
                "run any kernel command that writes state; the picture is rebuilt with the index"))
    return findings


def _check_invariant_checks(state: ProjectState, active_items: dict) -> list:
    """II.12/FR-0039: an invariant whose check resolves to no test does not govern anything.

    AN ERROR AND THEREFORE A MERGE BLOCKER, which is the point of the FR rather than a side
    effect: `gate_memory_complete.state_errors` blocks a push on this validator's errors, so the
    rule "an unverifiable invariant stops the merge" needed no hook of its own. An invariant is
    what a project's guards read to decide which code they govern -- one that points at nothing
    is a rule with no evidence that anyone still keeps it.

    THE OTHER TWO DIRECTIONS ARE WARNINGS, and each for its own reason. A check that DOES resolve
    while the item still reads `unverified` is bookkeeping nobody has run yet, and the remedy is a
    command rather than a repair. A check this kernel cannot READ -- a test file in another
    language -- is not a finding about the project at all but about the reader, and as an error it
    would block every merge of every project whose tests are not Python with nothing to clear it
    (`H110`).
    """
    findings = []
    verified = NON_AUTOMATON_STATUSES["INV"][1]
    parsed_names: dict = {}          # one parse per FILE for this scan -- see the resolution
    for item_id, (item_type, item) in sorted(active_items.items()):
        if item_type != "INV":
            continue
        resolved, reason = invariant_check_resolution(state, item, parsed_names)
        if resolved is None:
            findings.append(_finding(
                "warning", item_id, "%s" % reason,
                "keep the check pointing at the test a person can run; nothing here can confirm "
                "it, and no merge is blocked on an answer this kernel cannot give",
            ))
        elif not resolved:
            findings.append(_finding(
                "error", item_id, "%s -- an invariant nothing can check does not govern" % reason,
                "write the test the check names, or point the check at one that exists; then run "
                "`python scripts/harness.py verify-invariants`",
            ))
        elif item.get("status") != verified:
            findings.append(_finding(
                "warning", item_id, "check resolves (%s) but the item still reads %r"
                % (reason, item.get("status")),
                "run `python scripts/harness.py verify-invariants` -- the kernel records the "
                "status, no one writes it by hand",
            ))
    return findings


def standing_areas(state: ProjectState) -> dict:
    """The backlog's outline as it stands: {"Document/Heading": [item id, ...]}.

    FR-0017's protection against over-fragmentation, and the whole of it. The FR's rule is about a
    MOMENT -- "a new heading only when a requirement really fits none of the existing ones" -- so
    what a machine can add is the outline itself, at that moment (`kernel.cli`, on capture). There
    is no count and no threshold: nothing separates a thousand headings from nine hundred honest
    ones except whether the writer saw what was already there.

    Every active item is asked, whatever its type, because `AREA_FIELD` is on every captured
    type's contract -- an outline that showed only two types' entries would recommend an area that
    a third type already fills. That the contract really reaches every one of them is measured by
    `tools/test_backlog_types.py::test_every_captured_type_declares_the_outline_field_and_none_declares_it_twice`,
    not by this sentence.
    """
    outline: dict = {}
    for _item_type, stem, item, _path, exc in _iter_active(state):
        if exc or not isinstance(item, dict):
            continue
        segments = area_segments(item.get(AREA_FIELD))
        if segments:
            outline.setdefault(AREA_SEPARATOR.join(segments), []).append(
                str(item.get("id") or stem))
    return {key: sorted(ids) for key, ids in sorted(outline.items())}


def _check_no_v1_records_outside_the_archive(state: ProjectState) -> list:
    """SR-0001, enforced for good: no kit document may keep a V1 BACKLOG record.

    WHY IT IS ENFORCED HERE AND NOT ONLY AT MIGRATION TIME. The migration is the step that ends
    the double, and nothing afterwards stops a project from putting the monolith back -- restoring
    it from git, or copying an old kit template in. Then the same thing exists twice in one
    project and no reader can tell which copy is the state; SR-0001 asks for exactly this
    permanent bolt ("damit ein Projekt nicht heimlich zurueckkippt").

    THE RECOGNISER IS `migrate`'s OWN, not a second one. A V1 record is what `migrate.scan_document`
    finds and `migrate` calls a backlog record: a self-identifying `<TYP>-nnnn` mapping that
    carries a `status`, whose type some V1 or V2 contract knows. Reading it with a rule of this
    module's own is how the dry run and the validator would come to disagree about the same file
    -- and the dry run PROMISES this condition in advance
    (`migrate._documents_still_holding_records`).

    WHAT IS OUT OF SCOPE, and both exclusions fall out of one predicate rather than being named:
    the scan is over KIT DOCUMENTS (`layout.is_project_document`), so `archive/` and `legacy/` are
    outside it because both are kernel-written areas, and so is every item file the kernel wrote.
    A dev project's `acceptance_reports.yaml` keys its criteria `AC-<n>` with a `status` and is NOT
    flagged, because `AC` is a backlog type to nobody -- the same carve-out the migration makes,
    asked of the same function, which is also where that example's field reading is recorded.

    A DOCUMENT THAT PRODUCED NO VERDICT IS A FINDING, WHATEVER STOPPED IT, and that is a property
    of the loop below rather than a list of causes it knows: the only way to reach the record
    search is a document that was inside both budgets AND parsed, and every other path builds the
    same "NOT SEARCHED" finding out of its own reason. This scan is the only thing between a V1
    monolith copied back in and a project carrying the same records twice, so "could not look" may
    not leave the same silence as "looked and found none".

    ...AND A DIRECTORY THAT PRODUCED NO FILES AT ALL IS THE SAME SENTENCE ONE STOREY LOWER. The
    loop's completeness rests on the walk in `migrate.search_coverage`, and a walk is silent about a
    directory it cannot open: measured 2026-08-08 with one subdirectory of the state denied read
    access to the running user, this check made no finding and the shipped merge gate answered rc 0
    over a `PROC-0001` sitting in it. `UNLISTABLE` is now a verdict of the coverage and the first
    thing this function turns into an error.

    IT WAS A LIST OF CAUSES FOR ONE ROUND, and the half it did not list is what the shape costs.
    The two budgets were reported and an UNPARSABLE document was skipped in silence -- measured
    2026-08-07 against the shipped `gate_memory_complete` as a process, in a scaffolded project
    with a valid root item: a document holding one V1 record blocked `git merge` (rc 2); the same
    document with one unparsable line added, the record still in it in plain text, rc 0. SR-0001's
    bolt was switched off by a syntax error, and the dry run -- which reports such a file under
    UNREADABLE and refuses the run -- contradicted this validator about the same file.
    Both ends of that are measured in
    `test_migrate.test_an_unparsable_document_is_unsearched_and_still_refuses_the_merge`.

    ...AND THE RUN-UP TO THE LOOP WAS THE SAME SHAPE ONE STEP EARLIER: which files reach it was
    decided here, in three conditions of this function's own, while the import decided the same
    question differently. Measured 2026-08-07 with one `PROC-0001` laid down in seven places of one
    state: three were reported by both readers and four fell into three different combinations of
    "the dry run names it", "this scan names it" and "neither does". The run-up is now
    `migrate.search_coverage`, which gives every file under the state root exactly one verdict, and
    the two readers take the SEARCHED set and the unsearched reasons from it -- so a file they
    could classify differently no longer exists. WHAT AN UNSEARCHED FILE COSTS HERE is the one
    thing this function decides on its own: a file outside the record search's reach is reported as
    coverage (`record_scan_coverage`) and is NOT a finding, because no gate can block a project out
    of a `.md` file it ships itself -- so a V1 store renamed to `tasks.yaml.bak` inside the state
    directory is named and does not stop a merge. That is a hole and it is carried as one, not as a
    claim here.

    WHAT IT WILL SPEND IS BOUNDED AND WHAT THE BOUND COSTS IS REPORTED -- see `DOCUMENT_MAX_BYTES`
    for the measurement and for why an unbounded reader on the merge gate's path is a gate a large
    enough file switches off. The documents are taken in sorted order, so which of them the
    whole-scan budget reaches is a fact about the project rather than about the walk.
    """
    from . import migrate                   # lazy: `migrate` imports this module at its own import
    findings = []
    coverage = migrate.search_coverage(state)
    # A SUBTREE NOBODY COULD LIST IS THE ONE COVERAGE ANSWER THAT IS A FINDING, and it is the only
    # one of them that says this scan's own reach is unknown rather than bounded. An unsearched FILE
    # is named and blocks nothing on purpose (see below); a directory the walk could not open hides
    # an unknown number of files, so "did not look" is not even countable there. Both readers of the
    # coverage refuse on it -- the dry run puts it in `unreadable`.
    for where, why in migrate.unlistable_notes(coverage):
        # THE STEP IS THE MIGRATION'S OWN and is not spelled a second time here (DEC-0024, second
        # clause). The alternative that stood here until round 9 -- "or take it out of the state
        # directory" -- is the one `migrate.THE_ONLY_UNLISTABLE_STEP` had just been stripped of, on
        # the same class of directory: this row is produced for ANY walk error (`L28`), the
        # canonical ones included, so a reader who followed it could carry off the directory the
        # root item lives in. Two printers offering two answers for one condition is how the
        # removed one comes back, so there is one answer and one place it is written.
        findings.append(_finding("error", where, why[0].upper() + why[1:],
                                 migrate.THE_ONLY_UNLISTABLE_STEP))
    documents = [rel for rel, verdict, _why in coverage if verdict == migrate.SEARCHED]
    spent = 0
    _bounded = (
        "take the file out of the state directory (an editor or shell outside the "
        "session -- a log or an export of this size is a business record, not project "
        "state) or split it, then run `python scripts/harness.py validate` again")
    for rel in sorted(documents):
        path = ext_path(os.path.join(state.root, *rel.split("/")))
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        # (why this document produced no verdict, what to do about it) -- see the docstring: the
        # ONLY way past this block is a document that was read AND parsed, so no reason to skip
        # one can be added later without also passing through here.
        unsearched = None
        if size > DOCUMENT_MAX_BYTES:
            unsearched = ("it is %d bytes and this scan reads at most %d bytes of one document"
                          % (size, DOCUMENT_MAX_BYTES), _bounded)
        elif spent + size > DOCUMENT_SCAN_MAX_BYTES:
            unsearched = ("the %d bytes this scan may read in total were already spent on the "
                          "documents before it (this one adds %d)"
                          % (DOCUMENT_SCAN_MAX_BYTES, size), _bounded)
        else:
            spent += size
            payload, problem = migrate._read_document(state, rel)
            if problem:
                unsearched = (
                    "it %s -- the records in it, if any, are still there in plain text" % problem,
                    "repair the file (an editor or shell outside the session; save it as UTF-8 -- "
                    "a YAML document declares any other encoding by a BOM, and a Windows editor "
                    "writing ANSI back is one of the ways a document gets here), or take it out "
                    "of the state directory; `python scripts/harness.py migrate --dry-run` names "
                    "it under UNREADABLE and refuses the run for the same reason")
        if unsearched:
            why, remedy = unsearched
            findings.append(_finding(
                # THE CAUSE LEADS, and the check it took down follows. This message used to open
                # with "NOT SEARCHED for V1 backlog records", so a `project_config.yaml` with one
                # bad line answered a merge with a sentence about a V1 backlog nobody in the
                # project had ever heard of -- the failed CHECK named instead of the reason it
                # failed. The refusal is right either way; what a reader can act on is not.
                "error", rel,
                "%s. It was therefore NOT SEARCHED for V1 backlog records, and whether it holds "
                "any is unknown -- unknown is not empty. (This validator is also read by gates on "
                "a hook path with a time budget, where a reader that outruns it is a check that "
                "answers nothing at all, so it is bounded rather than thorough.)"
                % (why[0].upper() + why[1:]),
                remedy,
            ))
            continue
        held = [key for _ordinal, key, record in migrate.scan_document(payload)
                if migrate._declares_status(record)
                and migrate._is_backlog_type(migrate.V1_ID_RE.match(key).group(1))]
        if held:
            findings.append(_finding(
                "error", rel,
                "holds %d V1 backlog record(s) (%s...) -- the same thing exists twice in this "
                "project and nothing says which copy is the state"
                % (len(held), ", ".join(sorted(held)[:3])),
                "run `python scripts/harness.py migrate --dry-run`: a document whose records "
                "all became items is moved into the kernel's legacy area by the import "
                "(SR-0005), and the dry run names every record that still needs an answer "
                "first",
            ))
    return findings


def record_scan_coverage(state: ProjectState) -> dict:
    """What the SR-0001 record scan CAN look at and what it cannot -- coverage, not findings.

    WHY IT IS NOT A FINDING. Every project ships files this scan does not read -- `README.md`,
    `product/masterplan.md`, and in the research kit a whole `reports/assets/` tree. A finding
    about them would be permanent, unclearable and (as an error) a merge no project could ever
    pass; as a warning it would be an alarm about a state nobody can leave. So the difference
    between "looked and found none" and "did not look" is carried where it is true -- in the
    coverage this returns, which `python scripts/harness.py validate` prints under its findings and
    `python scripts/harness.py doctor` carries in its payload, per file and with the reason the
    import's own dry run prints for the same file.

    WHAT THAT LEAVES OPEN, said here rather than implied: nothing BLOCKS on it. A V1 store renamed
    to `tasks.yaml.bak`, or moved under `staging/` or under a dotted directory, is named by both
    readers and stops no merge (`L19` in `docs/POST_V2_WISHLIST.md`), and one dropped into a
    kernel-written area is not even named (`L20` there).

    WHAT IS DELIBERATELY NOT IN HERE is the coverage's UNLISTABLE verdict: a directory the walk
    could not open is an error finding of `_check_no_v1_records_outside_the_archive`, not coverage,
    because it says the coverage itself is short.

    DEPOSIT COPIES ARE COUNTED, NOT LISTED (BUG-0028). A file this command's own remedy told a reader
    to make lands under `staging/` with the deposit mark; one appears per applied remedy, so it is
    reported as a `deposits` count rather than one `not_searched` line each, which grew this section
    without bound as a project followed the report (synaipse: 26 -> 62).
    """
    from . import migrate                   # lazy: `migrate` imports this module at its own import
    coverage = migrate.search_coverage(state)
    return {"searched": [rel for rel, verdict, _why in coverage if verdict == migrate.SEARCHED],
            "not_searched": [{"path": rel, "why": why}
                             for rel, why in migrate.unsearched_notes(coverage)],
            # THE DEPOSIT COPIES, COUNTED AND NOT LISTED AMONG `not_searched` (BUG-0028). A deposit
            # is a copy this command's own remedy made; one appears per applied remedy, so counting
            # them keeps this coverage from growing a line every time a project follows the report.
            "deposits": [rel for rel, _why in migrate.deposit_notes(coverage)]}



def _approval_integrity_finding(item_id: str, exc) -> dict:
    """One `ApprovalError` as a validator finding, message and remedy kept apart.

    THE SENTENCE IS THE KERNEL'S, not a second wording of it: every branch of
    `assert_apr_in_force` writes a fact and then its own `Remedy:`, and the branch that refused is
    the only place that knows which of the five it was. Splitting on that word is what lets this
    surface keep its two columns without inventing a third text -- and a branch that ever carries
    no remedy gets the honest fallback rather than an empty column.
    """
    message = str(exc)
    fact, marker, remedy = message.partition("Remedy:")
    return _finding(
        "error", item_id, fact.strip().rstrip(".") if marker else message,
        remedy.strip() if marker else
        "re-run the approval flow for the current content; a hand-written approval never counts")

def _check_dispatch_approval_presented(state: ProjectState, active_items: dict) -> list:
    """WARN when a root presents a non-dispatching approval while a dispatching one is in force.

    Until generation 6 `mint` wrote `approval_ref` for every item-bound approval, and the dispatch
    gate's ROOT route reads that one field -- "the approval the root presents". So minting a
    `routine` or `analysis` approval for a root that already carried a valid scope or delivery
    approval MOVED the reference, and every implementation task under that root stopped
    dispatching. `approvals.presents` closed that door (PR-0011 AC-8): a hanging kind no longer
    lands in the field. This check stays for the stores the older mint wrote, and for a field
    written past the kernel.

    Measured 2026-07-31, and the reason this exists: nothing reported the state at all. The
    project only learned of it at the next spawn, as a refusal -- and because a `routine` is
    time-boxed and recurring by construction, it recurred at EVERY renewal, on a root that had long
    been APPROVED, where "mint them in the right order" was no advice at all.

    A WARNING, not an error: the state is legal, the remedy is a user action (re-run the scope
    approval), and a gate that blocked the merge here would block it for a permission the project
    may not need this cycle. Terminal items are skipped -- they dispatch nothing, and they already
    carry their own "awaiting archive" warning.

    THE STORE IS READ ONCE, and that is not tidiness. The first cut re-listed and re-parsed the
    whole approvals directory INSIDE the item loop, with `assert_apr_in_force` -- which reads the
    consumed request and recomputes its hash -- in the inner branch. `validate_state` runs from
    `gate_memory_complete` on a MERGE OR PUSH line, and the shape this very round creates is the bad
    one: a routine approval is per root and is re-minted WEEKLY, so the store grows linearly while
    those roots permanently present a non-dispatching approval. Measured over 400 approvals and
    300 items: 1 affected item 0.20 s, 5 -> 1.34 s, 20 -> 5.33 s, 50 -> 13.23 s, 300 -> 87.97 s --
    a minute and a half of a frozen session in front of every merge and every push, growing
    with the store, and a store a few times that size outgrows the window the calling hook is
    killed at (the kits' `_compat.HOOK_DEADLINE_SECONDS`), which is where a slow validator becomes
    an unrun one.

    WHEN THAT PATH REALLY RUNS, recorded HERE and nowhere else because it was wrong in FOUR
    docstrings of this module at once (2026-08-31): the hook process starts on every Bash and
    PowerShell call, and it leaves again -- rc 0, silent -- unless the line wants a merge or a push
    (`gate_memory_complete.main`, whose own applicability check is `_compat.wants_push_or_merge`).
    Measured through that hook as a process against a project holding one finding: `ls -la` rc 0
    silent, `git commit -m x` rc 0 silent, `git push origin main` rc 2, `git merge feat/x` rc 2. The
    "every Bash call" wording overstated the cost by the whole ratio between those two sets, and it
    was the sentence every other docstring here had copied. The budget note under `ITEM_MAX_LINES`
    said it correctly the whole time; the others now point at this paragraph rather than retelling
    it (SR-0008).

    One pass over the directory into `{item id: [approval, ...]}` makes it
    O(approvals + items) with the same verdicts.
    """
    findings = []
    approvals_dir = os.path.join(state.root, "approvals")
    if not os.path.isdir(ext_path(approvals_dir)):
        return findings
    by_item, presented_by_ref = {}, {}
    for name in sorted(os.listdir(ext_path(approvals_dir))):
        if not (name.startswith("APR-") and name.endswith(".yaml")):
            continue
        try:
            apr = state._read_yaml(os.path.join(approvals_dir, name))
        except Exception:  # noqa: BLE001 -- an unreadable approval grants nothing
            continue
        if not isinstance(apr, dict):
            continue
        presented_by_ref[name[:-5]] = apr
        if apr.get("kind") in ROOT_DISPATCH_KINDS and apr.get("item"):
            by_item.setdefault(str(apr["item"]), []).append((name[:-5], apr))
    for item_id, (item_type, item) in sorted(active_items.items()):
        apr_ref = item.get("approval_ref")
        auto = AUTOMATA.get(item_type)
        if not apr_ref or (auto and item.get("status") in auto.terminals):
            continue
        # a missing APR file is the neighbouring finding's business, not this one's
        presented = presented_by_ref.get(str(apr_ref))
        if presented is None or presented.get("kind") in ROOT_DISPATCH_KINDS:
            continue
        for name, apr in by_item.get(item_id, ()):
            try:
                assert_apr_in_force(state, apr, item)
            except ApprovalError:
                continue
            findings.append(_finding(
                "warning", item_id,
                "presents %s approval %s, while %s approval %s is still in force -- the dispatch "
                "gate's root route reads approval_ref, so tasks under this item are refused"
                % (presented.get("kind"), apr_ref, apr.get("kind"), apr.get("id") or name),
                "re-run the %s approval flow for %s to make it the presented one again; the "
                "routine/analysis approval keeps working through its own route"
                % (apr.get("kind"), item_id),
            ))
            break
    return findings


def _check_consumed_requests_diff_clean(state: ProjectState) -> list:
    """`approvals/consumed/**` must be diff-clean against HEAD.

    A minted request is immutable once written, and `approvals/**` is committed
    (II.2 excludes only kit_state.json, generated/** and the lock). Re-hashing a
    request is the ONE forgery `consumed_request` cannot detect arithmetically --
    the hash function is public, so a consistent rewrite verifies. It cannot hide
    from git, though: the file must never change after it is written, so any diff
    on it is the forgery, and the documented residual turns from "undetectable"
    into "detected at the next validate or merge".

    A repo without git, or a file not yet committed, yields nothing: this rule can
    only speak about files git is tracking.
    """
    consumed = os.path.join(state.root, "approvals", "consumed")
    if not os.path.isdir(ext_path(consumed)):
        return []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--", "approvals/consumed"],
            cwd=state.root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    findings = []
    for line in (result.stdout or "").splitlines():
        rel = line.strip()
        if rel:
            findings.append(_finding(
                "error", rel,
                "a consumed approval request was MODIFIED after it was minted",
                "a minted request is immutable -- `git restore %s`. A re-hashed "
                "request verifies arithmetically (the hash function is public), so "
                "this diff is the only place the tampering shows." % rel,
            ))
    return findings


def _check_approval_expiry_agrees(state: ProjectState, active_items: dict) -> list:
    """`apr["expires"]` must equal `request["subject_manifest"]["expires"]`.

    The APR copy is a derived DISPLAY value; the gate reads expiry only from the
    hash-covered manifest. If the two disagree, a human reads a validity the gate
    correctly refuses -- or, worse, believes an approval is still live.
    """
    findings = []
    for item_id, (_item_type, item) in sorted(active_items.items()):
        apr_ref = item.get("approval_ref")
        if not apr_ref:
            continue
        try:
            apr = state._read_yaml(os.path.join(state.root, "approvals", apr_ref + ".yaml"))
            request = consumed_request(state, apr)
        except Exception:
            # NOT "reported above", which is what this line used to claim: the loop above only
            # reports a MISSING APR file. An approval whose consumed request is gone (revoked, or
            # never written) makes `consumed_request` raise here and the item is skipped silently
            # -- measured 2026-07-31: `0 error(s), 1 warning(s)`. It is the mirror of the other
            # unreported pair (a valid APR whose item lost its `approval_ref`, see
            # `approvals.mint`): the store can disagree with itself in both directions and this
            # validator names neither. Fail-closed downstream -- every AUTHORISATION path
            # re-derives provenance and refuses -- so what is missing is the REPORT, not the
            # protection. Closing it is a validator change of its own.
            continue
        proven = (request.get("subject_manifest") or {}).get("expires")
        shown = apr.get("expires")
        if shown != proven:
            findings.append(_finding(
                "error", item_id,
                "approval %s shows expires=%r while its hash-covered request says %r"
                % (apr_ref, shown, proven),
                "the gate reads the REQUEST, so the displayed value is the wrong one -- "
                "re-run the approval flow rather than editing either file",
            ))
    return findings


def _parent_bindings(item_type: str, item: dict):
    """(field, id) for every item this one hangs from -- ONE hop up the reference graph.

    WHICH FIELDS bind is `backlog_types.PARENT_FIELDS`, derived there from the field
    contracts -- BOTH of them, the capture-time one and the frozen types' schemas. Nothing
    here may know a list of types: `_parents_of` was one (TSK/BUG/CR/HYP/EXP), and `SR` --
    required to carry `derives_from` since the lockstep, and the natural subject of a review
    -- was missing from it. Evidence recorded against an `SR` therefore resolved to no root,
    and the merge gate answered the role that had judged the work with "nothing judges this
    work". `ARC`, `WFR` and `DSN` then repeated it for the architect and the designer, whose
    contracts live in `kernel/schemas/` rather than in `REQUIRED_FIELDS`.

    A binding field holds one id or a list of them; both spellings are normalised through
    `backlog_types.field_elements`, so a type whose contract lets it hang from several items
    needs no second code path. A TSK is that type today: `product_requirement` is the root it
    serves and `derives_from` the item whose criteria it was cut from (a BUG or CR under that
    root), and both are legitimate ways for the work to belong to the root.

    The FIELD is yielded alongside the id because the validator's message names it and one
    binding is judged more strictly than the rest -- see `validate_state`.
    """
    for field in PARENT_FIELDS.get(item_type, ()):
        for one in field_elements(item.get(field)):
            if one:
                yield field, str(one)


def _parents_of(item_type: str, item: dict) -> list:
    """The ids of `_parent_bindings`, for the walk that only needs to know where to go next."""
    return [ref for _field, ref in _parent_bindings(item_type, item)]


def _item_of(state: ProjectState, item_id: str):
    """(type, item) for an id resolvable anywhere in the store, or (None, None)."""
    try:
        item_type, _number = parse_id(item_id)
    except ValueError:
        return None, None
    item, _archived = state.read_anywhere(item_id)
    if not isinstance(item, dict):
        return None, None
    return item_type, item


def _reaches_on_every_path(state: ProjectState, item_id: str, target_id: str,
                           seen: frozenset) -> bool:
    """Does EVERY ancestry path out of `item_id` end at `target_id`? (transitive, cycle-safe)

    The `all` is the whole point and is the difference to `_hangs_from`, which asks the same
    question with `any` and answers a different one: `_hangs_from` says the item can be REACHED
    from the target (enough to bind an Evidence to a root), this says the item belongs to that
    target and to no other (what an origin comparison needs). An item that hangs from two roots
    satisfies the first and not the second.

    Every way of not arriving is False, so the caller's refusal is the default: a cycle, an
    unresolvable id, and an item with no binding field at all (which hangs from nothing and
    therefore not from the target either).

    WHERE THE `all` ACTUALLY DECIDES is one level further in than it looks, and that is why it
    needs a test of its own: `origin_root_conflict` already walks the origin's OWN parents one by
    one, so an origin with two parents is caught there whatever this function does. The `all`
    starts deciding at the GRANDparent -- an origin with a single parent that itself hangs from two
    roots -- and with `any` in its place, seven modules stayed green (645 passed, measured
    2026-09-02). `test_report.test_an_origin_whose_only_parent_hangs_from_two_roots_is_refused` is
    that case, and
    `test_report.test_an_origin_that_reaches_the_root_through_only_one_of_its_parents_is_refused`
    measures the level above it. `_check_task_origins` and
    `dispatch._assert_origins_belong_to_root_locked` are the two callers, through
    `origin_root_conflict`.
    """
    if item_id == target_id:
        return True
    if item_id in seen:
        return False
    item_type, item = _item_of(state, item_id)
    if item is None:
        return False
    parents = _parents_of(item_type, item)
    return bool(parents) and all(
        _reaches_on_every_path(state, parent, target_id, seen | {item_id})
        for parent in parents)


def _ancestry_tops(state: ProjectState, item_id: str, seen: frozenset) -> frozenset:
    """The ids at the TOP of every ancestry path out of `item_id` -- what it really hangs from.

    Named for the refusal message rather than for a check: a role that is told its origin does
    not belong to the task's root needs to be told which root it does belong to, and after the
    walk became transitive that is no longer the immediate parent. An id that resolves to
    nothing is a top of its own, so the message names the reference the store cannot follow
    instead of falling silent about it.
    """
    if item_id in seen:
        return frozenset()
    item_type, item = _item_of(state, item_id)
    if item is None:
        return frozenset((item_id,))
    parents = _parents_of(item_type, item)
    if not parents:
        return frozenset((item_id,))
    tops = frozenset()
    for parent in parents:
        tops |= _ancestry_tops(state, parent, seen | {item_id})
    return tops or frozenset((item_id,))


def origin_root_conflict(state: ProjectState, origin_id: str, root_id: str):
    """Why a task's `derives_from` does not belong to its root -- or None when it does.

    ONE definition for the two places that ask it: `dispatch._assert_origins_belong_to_root_locked`
    refuses at creation and `_check_task_origins` reports on a stored item, and when those two
    disagree the kernel refuses what its own validator accepts.

    TRANSITIVE, because the chain a kit documents may be deeper than one hop. Its predecessor
    `_root_of` returned the single immediate parent, so an `EXP` under a `HYP` under an `RQ` had
    root `HYP-0001` here and root `RQ-0001` at the merge gate -- the research kit's own
    `RQ -> HYP -> EXP -> TSK` was uncreatable (BUG-0083). The dev chain never met it: there every
    task origin sits one level under the root.

    AMBIGUITY FAILS CLOSED, which is the other half and the older defect: `_root_of` answered
    "several parents" with None and both callers read None as "skip the comparison", so an origin
    with two parents was accepted under ANY root -- measured with an `EXP` under `RQ-0001` and a
    task under `RQ-0002` (BUG-0086). Here an origin belongs to the root when every one of its
    parents reaches it on every path; a mixed parentage is refused with the parent that leaves the
    root named, and the two cases carry different sentences because the remedies differ.

    Silent on an id that resolves to nothing: a phantom origin is refused at capture
    (`state._assert_origins_resolve`) and reported by the reference checks, and answering it here
    too would put the same defect in front of the role twice under two different names.
    """
    origin_id = str(origin_id or "")
    if not origin_id or origin_id == root_id or not root_id:
        return None
    _origin_type, origin = _item_of(state, origin_id)
    if origin is None:
        return None
    parents = _parents_of(_origin_type, origin)
    if not parents:
        return ("%s names no parent binding at all, so it is a root of its own and not part of "
                "the root %s of the item that names it" % (origin_id, root_id))
    astray = [parent for parent in parents
              if not _reaches_on_every_path(state, parent, root_id, frozenset((origin_id,)))]
    if not astray:
        return None
    tops = frozenset()
    for parent in astray:
        tops |= _ancestry_tops(state, parent, frozenset((origin_id,)))
    elsewhere = "/".join(sorted(tops))
    # WHICH OF THE TWO SENTENCES IS TRUE is one question: does the root stand at the end of ANY
    # path out of this origin? If it does, some paths reach it and some do not -- that is the
    # ambiguity, at whatever depth it sits. If it does not, the origin belongs somewhere else.
    #
    # Counting the straying parents alone answered that wrong one level in and said both things at
    # once -- "EXP-0001 belongs to RQ-0001/RQ-0002, not to RQ-0001" -- for an origin whose single
    # parent hangs from this root AND another: every parent strays (so the count read "foreign
    # root") while the root is among the tops. Reading `tops` ALONE gets the level above it wrong
    # in the mirror image: with two parents, one of which reaches the root, the strays' tops do
    # not contain it. Both readings together are the question above, and both levels are measured
    # (`test_report.test_an_origin_that_reaches_the_root_through_only_one_of_its_parents_is_refused`
    # and `test_report.test_an_origin_whose_only_parent_hangs_from_two_roots_is_refused`).
    if len(astray) == len(parents) and root_id not in tops:
        return ("%s belongs to %s, not to %s -- the root of the item that names it"
                % (origin_id, elsewhere, root_id))
    # The ambiguity may sit at the origin (two parents, one of them elsewhere) or ABOVE it (one
    # parent that itself hangs from two roots), so the sentence names the PATH and not a count.
    return ("%s reaches root %s on only some of its ancestry paths: %s leads to %s -- an ambiguous "
            "origin is refused rather than resolved to whichever path is read first"
            % (origin_id, root_id, ", ".join(astray), elsewhere))


def _hangs_from(state: ProjectState, item_id: str, target_id: str, seen: set) -> bool:
    """Does `item_id` belong to `target_id`'s tree? (transitive, cycle-safe)

    The walk goes through `read_anywhere` rather than the active map on purpose: a task is
    archived the moment it reaches VALIDATED, which is BEFORE the merge it was validated
    for. Resolving only active items would therefore lose exactly the binding a merge gate
    needs, and lose it at the one moment the work is finished.
    """
    if item_id == target_id:
        return True
    if item_id in seen:
        return False
    seen.add(item_id)
    try:
        item_type, _ = parse_id(item_id)
    except ValueError:
        return False
    item, _archived = state.read_anywhere(item_id)
    if not isinstance(item, dict):
        return False
    return any(_hangs_from(state, parent, target_id, seen)
               for parent in _parents_of(item_type, item))


def evidence_covers(state: ProjectState, evidence: dict, target_id: str) -> bool:
    """Was this Evidence recorded about `target_id`?

    Bound DIRECTLY when `related` names the item, and INDIRECTLY when it names something
    that hangs from it -- QA judges a task, and the task belongs to a root. The indirect
    hop is what replaces the V1 merge gate's file-level fallback, and it is strictly
    narrower: V1 accepted any passing entry in a file whose TEXT mentioned the target
    anywhere, including in a comment.
    """
    # NOT `field_elements`, and left that way on purpose (BUG-0015 round): `or []` drops a FALSY
    # non-empty value where `field_elements` would keep it (`0` -> `[]` here, `[0]` there). No id
    # is falsy, so the two agree on every value this field can hold; folding it would be a
    # behaviour change made for tidiness in a round that was fixing a defect. Same two lines below
    # in `qa_verdicts_by_subject`.
    related = evidence.get("related") or []
    related = list(related) if isinstance(related, (list, tuple)) else [related]
    return any(_hangs_from(state, str(ref), target_id, set()) for ref in related)


# THE TWO QUESTIONS ONE EVIDENCE STORE IS ASKED, and the only thing that separates them is what a
# PASSING run has to have covered to answer.
#
# `DELIVERY_QUESTION` -- "does this body of work ship?". Its subject is everything that hangs from
# the item, so the absence a pass has to show is unbounded, and a run that declares itself a
# selection cannot show it.
# `CONFIRMATION_QUESTION` -- "is the ONE defect this item names measured gone?". Its subject is that
# defect, and the run that answers it is a regression run: a selection BY NATURE. The shipped
# refusal at `state._assert_confirmed` asks for exactly that run.
#
# A NAMED QUESTION AND NOT A SECOND READER (PR-0005 invariant: two readers of one store are one
# derivation, never two spellings). The scan, the coverage walk and the newest-per-kind rule stay
# in one place below; only the pass-side filter is bound to the question, because only the question
# decides what a pass had to cover. DECISION: DEC-0071, beside DEC-0061; the defect is BUG-0090,
# measured on the shipped kernel -- an honestly declared regression run refused the very edge whose
# refusal text demands it, while the same run recorded WITHOUT the declaration walked.
DELIVERY_QUESTION = "delivery"
CONFIRMATION_QUESTION = "confirmation"
EVIDENCE_QUESTIONS = (DELIVERY_QUESTION, CONFIRMATION_QUESTION)


def _delivery_evidence(state: ProjectState, question: str = DELIVERY_QUESTION):
    """Every ACTIVE Evidence of a delivery-judging kind, as (item, ordering key).

    The one scan both verdict functions below share, so "which files are verdicts and in
    what order do they supersede each other" is answered once.

    WHICH files count -- `QA_EVIDENCE_KINDS`, i.e. the kinds that judge a delivery. An
    `audit` Evidence judges the project (II.10a), so it can neither open nor close the
    merge of one item.

    AND A PASS FROM A PARTIAL RUN DOES NOT ANSWER THE DELIVERY QUESTION (FR-0040; the decision this
    embodies is DEC-0061). An Evidence may declare what its run
    covered (`backlog_types.RUN_SCOPES`); one that declares `PARTIAL_RUN_SCOPE` and passed is
    dropped for `DELIVERY_QUESTION`, so the merge falls back to the newest FULL verdict or to none
    at all. The
    asymmetry is the argument and not a half-measure: a run over part of the work can show a
    defect, so a `fail` from a selection stays a fail and still closes the gate; it cannot show
    the absence of one, so its pass opens nothing. Until this line, `EVIDENCE_RESULTS`' own
    vocabulary comment as it then stood, and `gate_git`'s refusal text, both told the reader that a
    partial run is not merge evidence while nothing anywhere read a scope.

    FOR `CONFIRMATION_QUESTION` THE SAME RECORD COUNTS, and the argument is the same asymmetry read
    on its other side: the absence that question asks about is bounded by ONE named item, while a
    delivery's is not. HOW WIDE THAT BOUND REALLY IS, said rather than implied: `evidence_covers`
    is untouched, so a record naming something that HANGS FROM the item -- the task under the bug --
    confirms it too. That is the same reach the delivery question has always had, and it is the one
    DEC-0071 describes; it is not "the one item the caller names", and writing that here would be a
    narrower promise than the code keeps. See the two constants above for the questions and
    BUG-0090 for the measurement that separated them.
    `tools/test_report.py::test_a_selection_that_passes_confirms_the_item_it_names_and_ships_nothing`
    holds both ends of the split.

    WHAT IT DOES NOT REACH, said because the field is optional: a record that declares NO scope
    is treated exactly as before. The declaration cannot be made mandatory on this type without
    turning every Evidence a project already holds into a validator error that no command can
    repair -- an `EVD` is immutable -- so the duty belongs to the surface that records new ones,
    which is a contract decision and not this function's. `docs/POST_V2_WISHLIST.md` H108 carries
    it with its measurement.
    `tools/test_report.py::test_a_pass_from_a_partial_run_is_not_merge_evidence_and_a_fail_still_is`

    ARCHIVED evidence is deliberately not read: spec II.2 says closed things leave the
    active context, so archiving a superseded verdict is how it is retired -- visibly,
    through a kernel operation recorded in git, rather than by editing a file.

    The ordering key is `created` and then the id NUMBER (monotonic under the kernel's
    max-scan allocation, so it settles same-second ties).

    Lock-free by design. Every read here is a single item file, and this runs on the same
    tool call as `gate_memory_complete`, which already takes the lock for `validate_state`
    -- a second acquisition on that event is the interaction that turns a slow validate
    into a blocked push (see the note in that gate).
    """
    if question not in EVIDENCE_QUESTIONS:
        raise ValueError(
            "unknown evidence question %r -- the store answers %s. Remedy: ask one of them; a "
            "third question is a contract decision, not a call-site argument."
            % (question, ", ".join(EVIDENCE_QUESTIONS)))
    # through `iter_active_items` like every other "what is active" reader. `EVD` is not stored
    # per revision today, so this changes nothing measurable -- it is here because a private
    # listing of an active directory is the shape that produced disposition row 6.5, and this was
    # the last one inside the kernel.
    for stem, path in state.iter_active_items("EVD"):
        try:
            evidence = state._read_yaml(path)
            _type, number = parse_id(str((evidence or {}).get("id") or stem))
        except Exception:  # noqa: BLE001 -- a corrupt/misnamed file is no verdict; the
            continue       # state validator is what reports it as a finding
        if not isinstance(evidence, dict):
            continue
        if evidence.get("kind") not in QA_EVIDENCE_KINDS:
            continue
        if (question == DELIVERY_QUESTION
                and evidence.get("run_scope") == PARTIAL_RUN_SCOPE
                and evidence.get("result") == PASSING_RESULT):
            continue
        yield evidence, (str(evidence.get("created") or ""), number)


def _newest_per_kind(records) -> dict:
    """{kind: {id, result, created, blocked_reason}} keeping the newest record of each kind.

    A kind's newest evidence is its CURRENT verdict: a re-run supersedes its predecessor,
    and a FAIL recorded after a PASS is a regression that must close the gate again --
    which "any pass wins" could not express.

    THE BLOCKING SENTENCE TRAVELS WITH THE VERDICT (FR-0082), and it is carried here rather than
    re-read by the caller for the reason this function exists at all: the merge gate is not allowed
    a second reader of the Evidence store, so anything it has to SAY about a verdict has to arrive
    with it. It is `None` for every result that is not `BLOCKED_RESULT` -- the kernel refuses to
    store the sentence under any other result (`state.capture_preflight`), so the key is empty
    exactly where there is nothing to say.
    """
    verdicts = {}
    for evidence, order in records:
        kind = evidence.get("kind")
        if kind in verdicts and order <= verdicts[kind]["_order"]:
            continue
        verdicts[kind] = {"id": evidence.get("id"), "result": evidence.get("result"),
                          "created": evidence.get("created"),
                          BLOCKED_REASON_FIELD: evidence.get(BLOCKED_REASON_FIELD),
                          "_order": order}
    for entry in verdicts.values():
        del entry["_order"]
    return verdicts


def qa_verdicts(state: ProjectState, target_id: str,
                question: str = DELIVERY_QUESTION) -> dict:
    """The CURRENT QA verdict per Evidence kind FOR ONE item, as {kind: {id, result, created}}.

    `question` says WHICH of the two questions above is being asked and defaults to the delivery
    one, so every caller that had none keeps the reading it had. The only caller that asks the
    other is `state._assert_confirmed`; see the constants for why the two differ at all.

    THE definition the merge gate reads, and the reason it lives here rather than in the
    hook: "has QA passed for this item" is a question about canonical state, and a hook
    that answered it for itself would be a second implementation of the answer the harness
    and CI must give too.

    `target_id` is required. An earlier cut let it be None and meant "the store's newest
    per kind, unbound" -- but that reading collapses the whole project into one verdict,
    so a green run on one item hid an open failure on another. The caller that has no item
    asks `qa_verdicts_by_subject` instead, which keeps the grouping.

    Which evidence counts for this item is `evidence_covers`; which of several counts is
    `_newest_per_kind`; which files are verdicts at all is `_delivery_evidence`.
    """
    return _newest_per_kind(
        (evidence, order) for evidence, order in _delivery_evidence(state, question)
        if evidence_covers(state, evidence, target_id))


def qa_verdicts_by_subject(state: ProjectState, question: str = DELIVERY_QUESTION) -> dict:
    """The current verdict per kind for EVERY item Evidence names: {subject: {kind: entry}}.

    The answer for a caller that could not determine an item -- a merge on a branch named
    after none. Reading the store as one flat newest-per-kind would be the V1 file-level
    false accept rebuilt out of typed items: one item's fresh PASS would be the project's
    verdict while another item's open FAIL sat one file away, unread. Grouping by the item
    each Evidence NAMES keeps every open verdict its own, so "nothing is currently failing"
    can be asked instead of "the last thing that happened was green".

    Grouping is by the `related` ids AS WRITTEN, without the reference-graph walk
    `evidence_covers` does: this function has no target to walk towards, and the walk would
    only merge groups that are already each judged. Evidence naming no item at all is
    grouped under its own id rather than dropped -- it judges only itself, but a `fail`
    pinned to nothing is still a `fail`, and dropping it would make the emptiest record the
    most permissive one.

    `question` is the same switch `qa_verdicts` takes and defaults the same way, so every caller
    that had none keeps the delivery reading; `confirmed_but_open` is the one that asks the other.
    """
    groups = {}
    for evidence, order in _delivery_evidence(state, question):
        # the second of the two `or []` spellings -- see `evidence_covers` for why neither is
        # folded into `backlog_types.field_elements`
        related = evidence.get("related") or []
        related = list(related) if isinstance(related, (list, tuple)) else [related]
        for subject in [str(ref) for ref in related] or [str(evidence.get("id"))]:
            groups.setdefault(subject, []).append((evidence, order))
    return {subject: _newest_per_kind(records) for subject, records in groups.items()}


# -- what a delivery has already closed (DEC-0051) -----------------------------

def _active_map(state: ProjectState) -> dict:
    """{id: (type, item)} over the readable ACTIVE items -- the map `validate_state` hands around.

    ONE spelling for every reader that needs the map without being `validate_state`, because two
    spellings of "what is active" are two answers waiting to differ. An unreadable item file is
    dropped here rather than by each caller: it is a finding of `validate_state` and of nobody else,
    and a caller that invented its own answer for it would be a second verdict on the same file.
    """
    return {str(item.get("id") or stem): (item_type, item)
            for item_type, stem, item, _path, exc in _iter_active(state)
            if not exc and isinstance(item, dict)}


def closed_by_delivery(state: ProjectState, by_subject: dict = None) -> dict:
    """{item id: [EVD id, ...]} -- every item a DELIVERY has already closed, read from the evidence.

    THE OCCASION is `DEC-0051`: a status field is set by hand and a delivery verdict is written by
    the kernel, so the two disagree the moment nobody moves an item, and the store then reads as
    though work that shipped is still open. The decision is to DERIVE the answer from the records
    that already exist rather than to invent a status for it.

    THE DEFINITION, and it is a property rather than a list of ids: an item is closed when the
    CURRENT delivery verdict of every kind that NAMES it says `pass`, and at least one kind does. A
    FAIL recorded after a PASS therefore REOPENS the item, which "any pass wins" could not express:
    `test_report.test_a_later_fail_reopens_what_an_earlier_pass_had_closed`.

    `by_subject` is the grouping a caller has already paid for (`qa_verdicts_by_subject`), passed in
    for the reason `delivered_but_open` takes `active_items`: `contradicted_confirmations` asks this
    question and the failing half of it in one breath, so the pair costs one scan of the Evidence
    directory rather than two. That matters on the one path where `validate_state` is not a command
    somebody typed -- the merge/push line, recorded at `_check_dispatch_approval_presented` -- and
    it is the same moment `_delivery_evidence` names as the one where extra work over that
    directory turns a slow validate into a blocked push.

    WHAT IS SHARED WITH THE MERGE GATE AND WHAT IS NOT -- exactly, because the wider claim stood
    here for one round and is measurably false. SHARED: which files are delivery verdicts
    (`_delivery_evidence`) and which of several supersedes (`_newest_per_kind`). NOT SHARED: the
    SUBJECT. This groups by the ids an Evidence WRITES (`qa_verdicts_by_subject`, one pass, no
    walk), while `gate_git` asks `qa_verdicts` -> `evidence_covers` -> `_hangs_from`, which walks
    the reference graph transitively. The two therefore reach different sets, deliberately: the
    walk travels from a task's verdict up to BOTH items the task hangs from, the root it is filed
    under included, so putting this derivation on it would close a whole product requirement
    because one of its tasks passed. That is the right reading for "may this merge proceed" and the
    wrong one for "is this item done".
    `test_report.test_a_task_verdict_does_not_close_the_item_the_task_hangs_from` measures the
    difference from both ends, so neither reading can quietly become the other; what the gap costs
    in a real store is counted once, in `docs/reviews/2026-08-25-tsk0085-measurements.md`, and not
    a second time here.

    WHICH SUBJECTS IT ANSWERS FOR -- those whose type has an automaton, i.e. whose story has an end
    to reach. That one condition also drops the record types (`EVD`, the frozen companions) and with
    them the evidence that names no item at all, which `qa_verdicts_by_subject` files under its own
    id; a second condition for that case would be a second place to keep in step.

    AN ARCHIVED VERDICT COUNTS FOR NOTHING, so archiving one RE-OPENS what it had closed.
    `_delivery_evidence` reads active Evidence only -- spec II.2's way of retiring a superseded
    verdict visibly -- and this inherits it, which is right for a superseded verdict and surprising
    for a housekeeping archive of an old but still-current one.
    `test_report.test_archiving_a_verdict_reopens_the_item_it_had_closed` holds that half so it
    stays a known property rather than a discovery.

    WHAT IT PROVES AND WHAT IT DOES NOT, measured rather than hedged. It proves that a passing
    delivery verdict NAMED the item -- not that everything the item asks for has been built. The
    measured case is `FR-0004` in this repository's own store (2026-08-25): `EVD-0041` passes and
    names it, while the delivery it records closed that request in part by its own commit headline.
    So for a wish a project delivers in parts this reads as closed one part early, and a reader who
    needs the whole answer reads the item against the built code -- which is what
    `docs/reviews/2026-08-25-tsk0085-measurements.md` did, per item, for the store behind that
    measurement.
    """
    closed = {}
    if by_subject is None:
        by_subject = qa_verdicts_by_subject(state)
    for subject, verdicts in by_subject.items():
        try:
            subject_type, _number = parse_id(subject)
        except ValueError:
            continue
        if subject_type not in AUTOMATA:
            continue
        results = {(entry or {}).get("result") for entry in verdicts.values()}
        if results == {PASSING_RESULT}:
            closed[subject] = sorted(str((entry or {}).get("id")) for entry in verdicts.values())
    return closed


def delivered_but_open(state: ProjectState, active_items: dict = None) -> dict:
    """{item id: [EVD id, ...]} for the items `closed_by_delivery` names whose STATUS still reads open.

    The difference between the two answers IS the bookkeeping debt `FR-0058` measured: an item the
    evidence has closed and the status has not. `active_items` is the map `validate_state` has
    already built ({id: (type, item)}); a caller with none passes nothing and this reads the store
    itself through `_active_map`, exactly as `accepted_without_a_verdict` does.

    A TERMINAL item is not in this answer -- it is closed in both readings, and the "awaiting
    archive" warning of `validate_state` is already about it.
    """
    if active_items is None:
        active_items = _active_map(state)
    open_items = {}
    for item_id, evidence_ids in closed_by_delivery(state).items():
        entry = active_items.get(item_id)
        if entry is None:
            continue
        item_type, item = entry
        auto = AUTOMATA.get(item_type)
        if auto is None or item.get("status") in (auto.terminals or ()):
            continue
        open_items[item_id] = evidence_ids
    return open_items


def contradicted_confirmations(state: ProjectState, active_items: dict = None) -> dict:
    """{item id: [EVD id, ...]} -- items whose STATUS says CONFIRMED while a verdict says it failed.

    THE CROSS-CHECK ON `closed_by_delivery`, and DEC-0051 stage 2 is the occasion. Stage 1 made
    "delivered" a DERIVATION over the Evidence, which left two answers about one item standing
    beside each other: the status field and the derivation. `delivered_but_open` reports one
    direction of a disagreement -- the evidence closed it, the status did not follow -- as coverage,
    because a project can be unable to clear it. This is the other direction, and it is a FINDING,
    because it is never a reachability gap: an item can only stand here if somebody walked it to the
    end of its chain while the store already held, or later gained, a failing verdict about it.

    THE THREE TERMS ARE ALL DERIVED, none of them listed:
      * WHICH STATUS MEANS CONFIRMED is `backlog_types.confirming_edge`, the same reader
        `state._assert_confirmed` and `accepted_without_a_verdict` use -- the terminal a type can
        only reach by walking its whole chain. A type that has none (an `FR`, which ends its chain
        off a terminal and whose three ways out are a judgement no automaton makes) is not asked.
        This is deliberately NOT "the item is in some terminal": `REJECTED`, `DUPLICATE`,
        `CANCELLED` and `SUPERSEDED` mean the work was DROPPED, and a failing verdict beside a
        dropped item agrees with the record instead of contradicting it.
      * WHAT COUNTS AS THE VERDICT is `closed_by_delivery`'s own definition, asked of the same
        grouping in the same breath -- so the cross-check cannot come to read the evidence
        differently from the derivation it is checking.
      * SILENCE IS NOT A CONTRADICTION. An item nothing has ever judged is not in this answer, and
        that is the one place a rule could have been invented here: `state.CONFIRMING_EVIDENCE`
        guards this edge for `BUG` alone and says in its own comment that the other confirming
        edges are policy the roles follow, not a rule the kernel enforces. Demanding a verdict for
        every confirmed item would be the kernel making that policy up.

    NOT ON THE HOT PATH UNLESS IT HAS TO BE: the Evidence directory is scanned only when some
    active item actually stands in a confirming terminal, which is rare -- a confirmed item is
    normally archived. In a store without one this costs a dictionary walk and no file read.

    Both ends are measured: `test_report.test_a_failing_verdict_contradicts_a_confirmed_item` and
    `test_report.test_a_terminal_that_does_not_mean_confirmed_is_no_contradiction`.
    """
    if active_items is None:
        active_items = _active_map(state)
    confirmed = {}
    for item_id, (item_type, item) in active_items.items():
        edge = confirming_edge(item_type)
        if edge is not None and item.get("status") == edge[1]:
            confirmed[item_id] = item_type
    if not confirmed:
        return {}
    by_subject = qa_verdicts_by_subject(state)
    closed = closed_by_delivery(state, by_subject)
    contradicted = {}
    for item_id in sorted(confirmed):
        verdicts = by_subject.get(item_id)
        if not verdicts or item_id in closed:
            continue
        contradicted[item_id] = sorted(
            str((entry or {}).get("id")) for entry in verdicts.values()
            if (entry or {}).get("result") != PASSING_RESULT)
    return contradicted


def _check_confirmations_agree_with_the_verdicts(state: ProjectState, active_items: dict) -> list:
    """The finding `contradicted_confirmations` produces -- see it for the derivation."""
    return [
        _finding(
            "error", item_id,
            "%s while the current delivery verdict(s) %s say the work did NOT hold -- the status "
            "claims a confirmation the records contradict"
            % (active_items[item_id][1].get("status"), ", ".join(failing)),
            "decide which of the two is true and make the store say it: record the re-run that "
            "passes (`python scripts/harness.py evidence --kind <kind> --result pass --related %s "
            "--summary ... --artifact-ref <staged proof> --run-command \"<the line you ran>\" "
            "--run-scope <full|selection>`), or archive the verdict that no longer applies -- "
            "never by editing the Evidence, which is immutable" % item_id,
        )
        for item_id, failing in sorted(contradicted_confirmations(state, active_items).items())
    ]


def _guarded_edge(item_type: str, source: str, target: str) -> dict:
    """One edge with everything that stands in front of it: {from, to, approvals, evidence}.

    `approvals` are the kinds whose mint walks the edge (`approvals.required_approval_kinds`),
    `evidence` the Evidence kind the edge demands (`state.CONFIRMING_EVIDENCE` on the type's
    `backlog_types.confirming_edge`) or None. Both are read from the maps `state._transition_locked`
    itself consults, so a route printed to a reader and a route the kernel allows cannot become two
    answers.
    """
    return {
        "from": source,
        "to": target,
        "approvals": tuple(sorted(required_approval_kinds(item_type, source, target))),
        "evidence": (CONFIRMING_EVIDENCE.get(item_type)
                     if (source, target) == confirming_edge(item_type) else None),
    }


def closing_route(item_type: str, status: str) -> dict:
    """How this type gets from `status` to a CLOSED status, and what guards every step of it.

    {"steps": [edge, ...], "choices": [edge, ...]} -- `steps` walks the type's own chain from
    `status` to the end of it, `choices` are the terminal edges leaving that last chain status when
    the chain does not already end in a terminal. Both entries are `_guarded_edge`.

    THE TWO SHAPES ARE THE AUTOMATON'S, not a case distinction made here: `BUG` and `TSK` end their
    chain in the terminal that means CONFIRMED, so they have no choice left to make; `FR` ends its
    chain at `TRIAGED` and the three ways out of it -- what the wish BECAME -- are a judgement no
    automaton makes, so they are offered rather than picked. Which of them a delivered wish takes,
    and what that terminal then owes, is `_check_fr_result_link`'s question, not this one's.

    WHY A READER NEEDS IT AT ALL: it is what makes an unreachable close VISIBLE instead of
    surprising. `H39` is the measured case -- a repaired BUG passes a minted `scope` approval AND a
    passing `test` Evidence before `VERIFIED`, so where neither can be produced the derivation above
    is what says the work is done and the status field cannot. Both guards are measured in
    `test_report.test_the_closing_route_of_a_bug_names_both_guards_between_it_and_verified`, and the
    offered end of an `FR` in
    `test_report.test_the_closing_route_of_a_request_offers_the_terminals_it_may_become`.
    """
    auto = AUTOMATA.get(item_type)
    if auto is None or status not in auto.chain:
        return {"steps": [], "choices": []}
    chain = list(auto.chain)
    steps = [_guarded_edge(item_type, source, target)
             for source, target in zip(chain[chain.index(status):], chain[chain.index(status) + 1:])]
    last = chain[-1]
    choices = ([] if last in auto.terminals else
               [_guarded_edge(item_type, last, terminal)
                for terminal in sorted(auto.terminals)
                if (last, terminal) in auto.allowed])
    return {"steps": steps, "choices": choices}


def _needs(edge: dict) -> str:
    """" (needs ...)" for one `_guarded_edge`, or "" when nothing stands in front of it.

    THE APPROVAL KINDS ARE ALTERNATIVES AND THE EVIDENCE IS NOT, so there is one "or" inside and
    one "and" between. `required_approval_kinds` answers "which kinds COMMIT this edge" and any one
    of them walks it, while a confirming Evidence is demanded on top of whichever was given. Until
    a second kind existed for any edge both read the same and one join word said both -- the day
    `BUG TRIAGED -> APPROVED` took `scope` OR `verification` (PR-0012 AC-1) that line started
    telling every reader of the rollup to obtain two approvals where one walks.
    `tools/test_report.py::test_the_route_says_or_between_approval_kinds_and_and_before_the_evidence`
    """
    needed = []
    if edge["approvals"]:
        needed.append(" or ".join("a %r approval" % kind for kind in edge["approvals"]))
    if edge["evidence"]:
        needed.append("a passing %r Evidence" % edge["evidence"])
    return " (needs %s)" % " and ".join(needed) if needed else ""


def _route_sentence(item_type: str, status: str) -> str:
    """`closing_route` as one line a person can act on.

    A status the type's chain does not carry (a side state, or a terminal) yields "" -- there is no
    walk to describe from there, and a sentence invented for that case would be the one claim this
    module cannot derive.
    """
    route = closing_route(item_type, status)
    if not (route["steps"] or route["choices"]):
        return ""
    parts = [status] + ["%s%s" % (edge["to"], _needs(edge)) for edge in route["steps"]]
    sentence = " -> ".join(parts)
    if route["choices"]:
        sentence += " -> one of %s" % ", ".join(
            "%s%s" % (edge["to"], _needs(edge)) for edge in route["choices"])
    return sentence


def delivery_closure_rollup(state: ProjectState) -> list:
    """`delivered_but_open` as rows a reader can act on: {item, type, status, evidence, route}.

    COVERAGE, NOT A FINDING, and the reason is the same one `record_scan_coverage` carries one
    screen up -- with one addition that is specific to this answer and is the whole argument for
    the shape. A finding is something a project can CLEAR. Here it is measurably not: a repaired
    `BUG` reaches `VERIFIED` only through a minted approval and a passing `test` Evidence
    (`closing_route`), so a project that cannot mint carries the row for good. As an error that
    would block every merge it can never pass; as a warning it would be an alarm about a state
    nobody can leave, which is how a validator stops being read. So this is printed BESIDE the
    findings, with no severity and no exit code, by `kernel.cli`'s `validate` and in `doctor`'s
    payload -- the same two surfaces the record-scan coverage uses.
    `test_report.test_the_delivery_rollup_is_printed_beside_the_findings_and_is_none_of_them`
    holds it out of the findings; `H39` is the gap it reports around.

    NOT ON THE HOOK PATH, deliberately. `validate_state` runs from `gate_memory_complete` on a
    merge or push line in the dev and research kits (`_check_dispatch_approval_presented` records
    when that path runs and what it costs), and this is one more pass over the Evidence directory
    -- so it hangs off the two commands a person types, and neither the gate path nor a merge pays
    anything for it.
    """
    active_items = _active_map(state)
    rows = []
    for item_id, evidence_ids in sorted(delivered_but_open(state, active_items).items()):
        item_type, item = active_items[item_id]
        rows.append({
            "item": item_id,
            "type": item_type,
            "status": item.get("status"),
            "evidence": evidence_ids,
            "route": _route_sentence(item_type, item.get("status")),
        })
    return rows


# -- the stock that lies upward (FR-0058, PR-0008 AC-3) --------------------------------------

def _test_nodes_the_tree_no_longer_defines(state: ProjectState, run_command, parsed_names: dict):
    """The `<file>::<test>` words of a recorded run whose test the project's tree does not define.

    THE SAME READER `invariant_check_resolution` uses, fed one word at a time as if it were a
    check ref -- so what counts as "defined" has one definition in this module. A word this
    kernel cannot read (a non-Python file) is not reported: that is the reader's limit, not a
    stale record.
    """
    stale = []
    for word in str(run_command or "").split():
        if INVARIANT_REF_SEPARATOR not in word:
            continue
        resolved, _reason = invariant_check_resolution(
            state, {"check": {"ref": word.strip("\"'")}}, parsed_names)
        if resolved is False:
            stale.append(word)
    return stale


def confirmed_but_open(state: ProjectState, active_items: dict = None) -> dict:
    """{item id: {kind, evidence, run_command, unresolved}} -- items whose CONFIRMING Evidence
    passes while their status still reads open.

    THE SECOND QUESTION TO THE ONE DERIVATION, and the reason `delivered_but_open` is not enough:
    that one asks the DELIVERY question -- every kind that names the item passes, a declared
    selection dropped -- while the run that closes a defect is a regression run, a selection by
    nature (DEC-0071, `CONFIRMATION_QUESTION`). Measured on this repository's store before this
    existed: the four bugs walked to VERIFIED in generation 3 had exactly such a record (EVD-0079),
    and no line of `validate` could say so about a bug that still read TRIAGED. This is what the
    survey of FR-0058 feeds and what makes 'done' derivable: the store holds the measurement, the
    status has not followed, and the line names both.

    WHICH TYPES ARE ASKED is `state.CONFIRMING_EVIDENCE` -- the types whose confirming edge demands
    an Evidence kind at all -- so a type the kernel does not confirm by evidence cannot be named
    here on a rule this function invented (`contradicted_confirmations` refuses the same
    invention for the same reason).

    WHAT "ABOUT THE ITEM" MEANS, said as `accepted_without_a_verdict` says it: the ids an Evidence
    WRITES (`qa_verdicts_by_subject`), one pass over the store, without the graph walk
    `state._assert_confirmed` takes through `qa_verdicts`. So this is NARROWER than the edge: an
    item named here can walk its edge, while one the edge would accept through a task hanging
    under it is not named here.

    THE TEST TREE IS PARSED, NEVER RUN. A passing record whose `run_command` names a test node the
    tree no longer defines is a measurement nobody can repeat, and the row says so (`unresolved`);
    whether a test still PASSES is a run, and a run is a new Evidence, never a validator line --
    `validate_state` runs on the merge/push line of `gate_memory_complete`, where a test run would
    outlive the hook's window.

    COVERAGE, NOT A FINDING, for `delivery_closure_rollup`'s reason: the route from here to the
    confirmed status needs a mint the project may not be able to run (`closing_route`).
    `test_report.test_a_passing_regression_run_names_the_open_item_as_stock_lying_upward` holds
    the delivery/confirmation split, the terminal exemption and the kind; the parsed-tree half is
    `test_report.test_the_stock_line_says_when_the_recorded_test_no_longer_exists`.
    """
    if active_items is None:
        active_items = _active_map(state)
    by_subject = qa_verdicts_by_subject(state, CONFIRMATION_QUESTION)
    parsed_names: dict = {}
    found = {}
    for item_id, (item_type, item) in sorted(active_items.items()):
        kind = CONFIRMING_EVIDENCE.get(item_type)
        auto = AUTOMATA.get(item_type)
        if not kind or auto is None or item.get("status") in auto.terminals:
            continue
        verdict = (by_subject.get(item_id) or {}).get(kind)
        if not verdict or verdict.get("result") != PASSING_RESULT:
            continue
        try:
            evidence = state.read_item(str(verdict.get("id")))
        except Exception:  # noqa: BLE001 -- an unreadable record is the validator's own finding
            evidence = {}
        run_command = evidence.get("run_command")
        found[item_id] = {
            "kind": kind,
            "evidence": [str(verdict.get("id"))],
            "run_command": run_command,
            "unresolved": _test_nodes_the_tree_no_longer_defines(state, run_command, parsed_names),
        }
    return found


def stock_rollup(state: ProjectState) -> list:
    """`confirmed_but_open` as rows: {item, type, status, kind, evidence, run_command, unresolved, route}.

    Printed beside the findings by `kernel.cli`'s `validate` and carried in `doctor`'s payload,
    exactly as `delivery_closure_rollup` is and for its reason.

    THE ROW IS A DICT DISPLAY, spelled out field by field exactly as that sibling's is, and that is
    not style. `tools/test_approvals_dispatch.py::test_no_direct_status_write_can_produce_a_status_an_approval_commits`
    reads every place in this kernel that BINDS a `status` key on an existing mapping -- a subscript
    assignment, an `.update({...})`, a `dict(..., status=...)` -- and refuses a value it cannot
    bound, because that is the shape the old `mint` wrote an approval-bound status with. Both of the
    first two spellings stood here and turned it red, correctly. A display builds a NEW mapping for a
    report and can persist nothing, which is why the reader does not read one.
    """
    active_items = _active_map(state)
    rows = []
    for item_id, found in sorted(confirmed_but_open(state, active_items).items()):
        item_type, item = active_items[item_id]
        rows.append({
            "item": item_id,
            "type": item_type,
            "status": item.get("status"),
            "kind": found["kind"],
            "evidence": found["evidence"],
            "run_command": found["run_command"],
            "unresolved": found["unresolved"],
            "route": _route_sentence(item_type, item.get("status")),
        })
    return rows


# -- the pointer sweep: a citation that resolves at nothing (FR-0007, PR-0008 AC-7) --------------

# The files the KIT INSTALLER copies to the project ROOT. An enumeration, because the kernel holds
# no other reader for them -- so it carries the tripwire at BOTH ends the house rule asks for:
# `tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`
# scaffolds a pilot per kit and measures that every name here really is written by that scaffold
# (the entry is not dead) AND that reading it really would report citations of the kit's own
# repository against this store (the entry is not needless).
SCAFFOLDED_ROOT_FILES = ("AGENTS.md", "AGENTS.override.md", "CLAUDE.md")

# The DIRECTORIES the installer fills with kit-owned scripts. The first entry is not typed: it is
# the directory the kernel's own `ENTRY_POINT` lies in, asserted below, so a kit that moves its
# entry point moves this with it. The rest is the same unavoidable enumeration as the line above and
# carries the same two-ended tripwire in the same test: every entry is written by at least one kit's
# real scaffold (not dead) and reading it would really report the kit's own citations (not
# needless). SINCE `BUG-0265` THIS IS THE FALLBACK AND NOT THE ANSWER: where the installer wrote
# `.claude/kit_repo_files.json`, `installed_kit_paths` skips the FILES that record names and the
# project's own script beside them is swept again. The enumeration still answers for a project
# installed before that record existed, which is the only place its cost (`H183`) is still paid.
INSTALLER_SCRIPT_DIRS = ("scripts", "tools")

# A citation is a BACKTICK SPAN -- the same thing this kit's source repository reads in its own
# mechanical half (`.claude/hooks/test_gates.py::_points_into_this_file`) and the same shape every
# constitution asks a comment to write its pointer in. What is NOT read is said in `pointer_sweep`.
_CITATION_RX = re.compile(r"`([^`]+)`", re.DOTALL)
# A LINE BREAK inside a span is glued out, with the continuation markers around it -- a long name
# wraps, the next line opens with `#` or `*`, and a name read as two halves resolves at nothing,
# which would make this sweep depend on where an editor happened to break the line. A SPACE that is
# not a line break is NOT glued out, and that half is measured: pasted runner output (`FAILED
# tools/test_board.py::test_x`) inside one span became `FAILEDtools/test_board.py::test_x` and was
# reported as a dead pointer in five review documents -- a span carrying a space is prose ABOUT a
# node, not a citation of one, and the shape below then lets it pass unread.
_CITATION_GLUE_RX = re.compile(r"[ \t#*]*[\r\n]+[ \t#*]*")
# A TEST NODE citation, as a SHAPE the reader must match rather than as a span it hopes is one: a
# path carrying at least one separator, a file name with a suffix, `::`, and a name. Every part of
# that is what `invariant_check_resolution` needs to answer at all -- it resolves the path against
# the project root -- so a span this shape rejects is one the resolver could only guess about.
# MEASURED over this repository before the shape was required: the resolver was handed
# `deselectdoes::not::exist` and `MEMORY.md::$DATA` (example strings inside code, not pointers) and
# a 900-character span glued out of an unbalanced backtick in a test file, and reported all three as
# dead pointers. What the shape costs is named in `pointer_sweep`: a citation by BARE file name is
# not read.
_TEST_NODE_RX = re.compile(r"^[\w.\-/]*/[\w.\-]+\.[A-Za-z0-9]+" + re.escape(INVARIANT_REF_SEPARATOR)
                           + r"[\w.\-]+$")


class PointerSweepUnavailable(RuntimeError):
    """The sweep has no subject -- git could not list the project.

    Its own class rather than an empty list, because "no files" and "no findings" print the same and
    mean the opposite things, and the empty one is the reassuring one.
    """


def _undecorated_citation(span: str) -> str:
    """A citation with the decoration around it taken off -- a DEFINITION, not a list of spellings.

    THE RIGHT END: a character that is neither alphanumeric nor `_` cannot END an item id or a test
    name, so a run of such characters comes off there. THE LEFT END is narrower, and that asymmetry
    is measured rather than tidy: a path may BEGIN with `.` or `/`, so stripping every non-word
    character from the left turned `.claude/hooks/test_gates.py::x` into `claude/hooks/...` and the
    sweep reported its own docstring as a dead pointer. Only the characters that open a decoration
    come off the left. A parametrised node id is cut at the bracket pytest opens the case with,
    because the definition is the name before it.
    """
    span = span.split("[")[0]
    trailing = "".join(sorted({character for character in span
                               if not (character.isalnum() or character == "_")}))
    span = span.rstrip(trailing) if trailing else span
    leading = "".join(sorted({character for character in span
                              if not (character.isalnum() or character in "_./")}))
    return span.lstrip(leading) if leading else span


def installed_kit_paths(repo_root: str) -> set:
    """The repo-relative path PREFIXES a project's own roles did not write -- the kit installed them.

    THREE READERS THE PROJECT ITSELF HOLDS, and not a list of directory names in this module. The
    first cut was such a list -- the kit's home plus three root files -- and it was measured short
    by four trees: a freshly scaffolded project with no line of its own code answered the shipped
    `sweep-pointers` with 39 (dev), 27 (office) and 30 (research) dead pointers, every one of them
    inside `.agents/`, `.codex/`, `scripts/` or office's `tools/`, and none of them anything the
    project may edit (`gate_write_scope` refuses all of them). That is the failure this reader's own
    docstring claimed was excluded.

      * THE ENFORCEMENT LAYER, as the SHIPPED gate defines it: `gate_write_scope._ENFORCEMENT_PATHS`,
        imported through `scopes._hooks_dir()` -- the same import `scopes.matcher()` makes, and for
        the same reason. A second spelling here would answer a different question than the gate the
        roles really meet.
      * THE PROVIDER LAYER, as the PROJECT records it: `.claude/provider_artifacts.json` names every
        `dirs`/`files` entry the generator wrote. A provider layer that gains a directory therefore
        moves this reader without anyone editing it.
      * THE INSTALLER'S OWN RECORD OF WHAT IT PLACED: `.claude/kit_repo_files.json` names every
        file a kit copied OUTSIDE the hook bundle, so the sweep skips those files and reads the
        project's own script in the same directory again (`BUG-0265`/`H183`, AC-1; the writing end
        is `tools/test_hooks.py::test_the_installer_records_which_files_it_places_outside_the_hook_bundle`,
        the reading end `tools/test_pointer_sweep.py::test_a_projects_own_script_is_swept_while_the_kits_copy_beside_it_is_not`).
      * THE INSTALLER'S ROOT FILES, and the SCRIPT DIRECTORIES only where that record is absent:
        `SCAFFOLDED_ROOT_FILES` and `INSTALLER_SCRIPT_DIRS`, the two enumerations with their
        two-ended tripwire.

    A MISSING READER IS NOT SILENCE: a project with no gate beside its kernel and no manifest still
    gets the two enumerations, and the sweep then reports what it reports -- the caller sees the
    findings, not an empty answer. The one case that must never read as "clean" is "no files at
    all", and that is `PointerSweepUnavailable`.

    THE FIRST TWO READERS OVERLAP, and saying otherwise would be the claim this file is about.
    MEASURED on a scaffolded dev pilot (2026-09-06, verifier round 2): dropping the gate alone or the
    manifest alone leaves the sweep at 0 findings on a clean project -- each covers `.agents/` and
    `.codex/` on its own -- and only dropping BOTH brings the 41 back. So neither is individually
    necessary today and no test can show one going red without the other; they are defence in depth,
    and what each buys is a project where the OTHER is absent (a kit that ships no provider layer,
    a project whose gate is missing). The last group, the two enumerations, IS individually
    load-bearing and its tripwire shows it -- for `SCAFFOLDED_ROOT_FILES` in every project, for
    `INSTALLER_SCRIPT_DIRS` only in one installed before the installer wrote its record.
    """
    prefixes = set(SCAFFOLDED_ROOT_FILES)
    # THE SCRIPT DIRECTORIES ONLY WHERE A KIT IS INSTALLED, and the condition is the installer's own
    # artefact: the entry point. Without it there is no scaffold, so `scripts/` and `tools/` are
    # whatever the project put there -- which is the case of the kit's SOURCE repository, whose
    # `tools/` is its whole test suite. Measured: excluding them unconditionally cost that repo
    # seven of its own findings.
    from .cli import ENTRY_POINT   # local: `cli` imports this module, so the pair is a cycle
    if os.path.isfile(ext_path(os.path.join(repo_root, *ENTRY_POINT.split("/")))):
        shipped = os.path.join(repo_root, ".claude", "kit_repo_files.json")
        try:
            with open(ext_path(shipped), encoding="utf-8-sig") as handle:
                named = {str(one).replace("\\", "/").strip("/")
                         for one in (json.load(handle).get("repo_files") or [])}
        except Exception:  # noqa: BLE001 -- see "A MISSING READER IS NOT SILENCE" above
            named = set()
        # A project installed BEFORE the installer wrote this record has none, and dropping the
        # directories there would un-exclude every kit script at once.
        prefixes |= named or set(INSTALLER_SCRIPT_DIRS)
    try:
        from .scopes import _hooks_dir
        hooks = _hooks_dir()
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        import gate_write_scope
        prefixes |= {str(one).replace("\\", "/").strip("/")
                     for one in gate_write_scope._ENFORCEMENT_PATHS}
    except Exception:  # noqa: BLE001 -- see "A MISSING READER IS NOT SILENCE" above
        pass
    manifest = os.path.join(repo_root, ".claude", "provider_artifacts.json")
    try:
        with open(ext_path(manifest), encoding="utf-8-sig") as handle:
            recorded = json.load(handle)
        for key in ("dirs", "files"):
            prefixes |= {str(one).replace("\\", "/").strip("/")
                         for one in (recorded.get(key) or [])}
    except Exception:  # noqa: BLE001 -- same reason
        pass
    return {one for one in prefixes if one}


def _lies_in_a_kit_tree(repo_root: str, rel: str, cache: dict) -> bool:
    """True where an ANCESTOR directory of this file holds a kit -- so the file is kit material.

    `hashing.is_kit_dir` is the kernel's own answer to "is this a kit", and a directory that HOLDS
    one is a kits root: its whole content is the kit's, shared half included (that is the same
    reading `hashing.kit_hash_inputs` makes of the tree it hashes). Cached per directory, because a
    kits root carries hundreds of files and the predicate goes to the filesystem.
    """
    from .hashing import is_kit_dir
    parts = rel.split("/")[:-1]
    for depth in range(len(parts)):
        directory = "/".join(parts[:depth + 1])
        if directory not in cache:
            absolute = os.path.join(repo_root, *directory.split("/"))
            try:
                children = sorted(os.listdir(ext_path(absolute)))
            except OSError:
                children = []
            cache[directory] = any(
                is_kit_dir(os.path.join(absolute, child)) for child in children)
        if cache[directory]:
            return True
    return False


def _swept_files(repo_root: str, state_root: str, kit_home: str):
    """(relative path, text) for every file of the project GIT tracks that this sweep judges.

    THE SUBJECT IS ASKED OF GIT, not walked off the filesystem: "the project's own code" is exactly
    what the project committed, and a walk would have to decide by hand which dependency tree, build
    output or tool cache is not the project's. `git ls-files` is that decision already made, by the
    running tool rather than by a list here.

    FOUR GROUPS ARE LEFT OUT and each for its own reason, none of them "it is noisy":
      * the canonical STATE tree -- the citations of an ITEM are `validate_state`'s subject, and its
        answers are typed findings about the item rather than about a file;
      * everything the KIT INSTALLED -- its home directory, the enforcement layer as the shipped
        gate defines it, the provider layer as the project's own manifest records it, the root files
        and the script directories. `installed_kit_paths` is that derivation and carries the
        measurement that a list of directory names here was short by four trees. Those files cite
        the items and tests of the kit's SOURCE repository, which this store does not hold and this
        project may not edit -- `gate_write_scope` refuses every write to them, so a finding there
        names nobody who could act on it. Keeping THOSE pointers honest belongs to the kit's own
        repository, where the store answers;
      * a KIT TREE lying in the project itself -- the case of the kit's own source repository, where
        the kits are checked out rather than installed. Decided with the kernel's own predicate
        (`hashing.is_kit_dir`): a directory that HOLDS a kit is a kits root, and everything under it
        is kit material for the same reason `.claude/` is. MEASURED without this rule, over the kit
        source repository: 100 of 118 findings were the placeholder ids of an EXAMPLE project in
        kernel docstrings (`PROC-0001`, `WFR-0001`, `RQ-0001`), which no store is meant to answer;
      * a file that does not decode as UTF-8 -- which is how "text" is decided here, rather than by
        a list of suffixes that is wrong for the next project's language.
    """
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z"], cwd=repo_root, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise PointerSweepUnavailable(
            "git could not list this project's files (%r), so this sweep has no subject and its "
            "silence would mean nothing" % (error,))
    if listed.returncode != 0:
        raise PointerSweepUnavailable(
            "git could not list this project's files (rc %d: %s), so this sweep has no subject and "
            "its silence would mean nothing"
            % (listed.returncode,
               (listed.stderr or b"").decode("utf-8", "replace").strip()[:200]))
    state_rel = os.path.relpath(os.path.abspath(state_root), repo_root).replace(os.sep, "/")
    kit_roots: dict = {}
    installed = installed_kit_paths(repo_root) | {kit_home, state_rel}
    for raw in listed.stdout.split(b"\0"):
        rel = raw.decode("utf-8", "replace").strip()
        if not rel:
            continue
        if any(rel == one or rel.startswith(one + "/") for one in installed):
            continue
        if _lies_in_a_kit_tree(repo_root, rel, kit_roots):
            continue
        try:
            with open(ext_path(os.path.join(repo_root, *rel.split("/"))),
                      encoding="utf-8") as handle:
                yield rel, handle.read()
        except (OSError, UnicodeDecodeError):
            continue


def pointer_sweep(state: ProjectState) -> list:
    """Every citation in the project's OWN files that points at nothing, as findings.

    THE DUTY THIS IS THE MECHANICAL HALF OF (`FR-0007`, and the rule itself in `DEC-0008` /
    `SR-0008`): a comment carries the WHY as a POINTER, and a claim about a PROPERTY becomes a test
    the comment NAMES. Both halves rot the same way -- the test is renamed, the item is re-filed --
    and a pointer that resolves at nothing is worse than none, because it reads as covered. What no
    machine can decide is whether a property claim named a test AT ALL; that half stays with the
    role that writes and the role that reviews, and the constitutions say so in the same breath.

    WHAT IS READ, deliberately narrow: a backtick span carrying `::` is a TEST NODE and is resolved
    against the tree by `invariant_check_resolution` -- the same reader the invariants use, so
    "defined" has ONE definition in this module; a span that is a kernel item ID (`parse_id`
    decides, so the vocabulary is `ACTIVE_DIRS` and not a pattern typed here) is resolved against
    the store, active and archived alike, because an archived item is still a place a reader can go.

    WHAT IS NOT READ, named rather than implied: a test cited by BARE FILE NAME with no directory
    (`_TEST_NODE_RX` demands a separator, because the resolver reads the path from the project root
    and would otherwise have to guess where the file should live); a node id through a class; a test
    file in a language this kernel does not parse (`invariant_check_resolution`'s third answer,
    `H110`); and every span that is neither shape -- a path, a command, a field name. So a green
    sweep says "no pointer of the two readable kinds is dead", never "every claim here is covered".

    WHAT IT CANNOT TELL APART, and the reason this is a REPORT and not a gate: an ILLUSTRATION and a
    POINTER are the same shape. A document that teaches by example (`write it as
    tests/perf/test_pricing.py::test_p95`) and a report about ANOTHER project's store (a pilot log
    naming that pilot's `PROC-0001`) both read as dead pointers here, and no property of the span
    separates them from a citation that rotted. Measured over the kit's own source repository, where
    the majority of the findings turned out to be of exactly those two kinds; the mechanism and that
    measurement are `H175`. So the answer belongs to whoever reads the report -- which is why this
    exits 1 and no hook waits on it.

    `tools/test_pointer_sweep.py::test_a_dead_test_pointer_and_a_dead_item_pointer_are_both_reported`
    holds the two finding classes and the silences beside them.
    """
    from . import presets
    repo_root = os.path.dirname(os.path.abspath(state.root))
    kit_home = presets.KIT_VERSION_FILE.replace(os.sep, "/").split("/")[0]
    parsed_names: dict = {}
    known: dict = {}
    findings = []
    for rel, text in _swept_files(repo_root, state.root, kit_home):
        findings.extend(findings_in_text(state, rel, text, parsed_names, known))
    return findings


def findings_in_text(state: ProjectState, where: str, text: str,
                     parsed_names: dict = None, known: dict = None) -> list:
    """The dead pointers of ONE text -- the loop `pointer_sweep` runs, callable on its own.

    ONE reader, because a second one drifts: the pilot tripwire in
    `tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`
    has to ask "would reading this file really produce a finding", and it asked that with its own
    copy of the loop. A copy answers for itself: narrow `pointer_sweep` and the copy stays wide, so
    the tripwire keeps saying "this entry is needed" about a reader that no longer reads that way.

    `parsed_names` and `known` are the two caches of a whole sweep; a caller with none pays per call,
    which is right for a single file.
    """
    parsed_names = {} if parsed_names is None else parsed_names
    known = {} if known is None else known
    findings = []
    for span in _CITATION_RX.findall(text):
        glued = _undecorated_citation(_CITATION_GLUE_RX.sub("", span))
        if INVARIANT_REF_SEPARATOR in glued:
            if not _TEST_NODE_RX.match(glued):
                continue
            resolved, reason = invariant_check_resolution(
                state, {"check": {"ref": glued}}, parsed_names)
            if resolved is False:
                findings.append(_finding(
                    "error", where,
                    "names the test `%s`, and it does not resolve: %s" % (glued, reason),
                    "point the statement at a test that exists, or drop the claim it carries -- "
                    "a named test that resolves at nothing reads as covered while nothing "
                    "measures it (SR-0008).",
                ))
            continue
        try:
            parse_id(glued)
        except ValueError:
            continue
        if glued not in known:
            known[glued] = state.exists_anywhere(glued)
        if not known[glued]:
            findings.append(_finding(
                "error", where,
                "names the item `%s`, which this store holds neither active nor archived" % glued,
                "name the item that really carries the reason, or write the reason out -- a "
                "pointer nobody can follow is a claim nobody can check (SR-0008).",
            ))
    return findings


def _check_bug_system_link(state: ProjectState, active_items: dict) -> list:
    """FR-0054: the SR a bug names must live under the same root the bug is filed against.

    THE FIELD EXISTS BECAUSE THE OTHER ONE ANSWERS A DIFFERENT QUESTION. `related_pr` is the
    product root the bug belongs to and says nothing about which contract it broke; a bug in the
    software hits a SYSTEM requirement, and the system tree could only ever group bugs under the
    product root.

    JUDGED ON MEMBERSHIP AND NOT ON EXISTENCE, which is the residue the FR names in its own text:
    `related_pr` and `target_pr` are checked for resolvability by the reference loop above and for
    nothing else, so a bug can point at a requirement of a foreign tree and be reported by nobody.
    The new field does not repeat that, and it reuses `origin_root_conflict` rather than walking
    the graph a second time -- the same definition the task origins are judged with, including its
    fail-closed answer for an ambiguous parentage.

    HERE AND NOT AT CAPTURE, for the reason `_check_task_origins` gives one screen up: the walk is
    a graph question, the damage is a mislabel in a committed file, and this layer is where the
    kernel already pays for that walk.
    """
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        if item_type != "BUG":
            continue
        root = item.get("related_pr")
        for ref in field_elements(item.get("related_sr")):
            conflict = origin_root_conflict(state, str(ref), str(root or ""))
            if conflict:
                findings.append(_finding(
                    "error", item_id, "related_sr %s" % conflict,
                    "name a system requirement under %s, or file the bug against the root that "
                    "requirement belongs to" % (root or "this bug's root"),
                ))
    return findings


def _check_task_origins(state: ProjectState, active_items: dict) -> list:
    """A TSK's `derives_from` must belong to its ROOT's tree, and not be stale.

    The kernel refuses phantom origins at capture (cheap, on the hot path), but
    the dispatch gate resolves `acceptance_refs` against the ORIGIN -- so an
    origin from an unrelated root lets a task be judged against borrowed
    criteria. Authorisation is unaffected (that comes only from the root's
    approval) and the mislabel sits in a committed file frozen outside DRAFT,
    which is why it belongs to this graph-walking layer rather than to dispatch.
    """
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        if item_type != "TSK":
            continue
        root = item.get("product_requirement")
        for origin in field_elements(item.get("derives_from")):
            origin = str(origin)
            if origin == root:
                continue
            entry = active_items.get(origin)
            if entry is None:
                if _in_archive(state, origin):
                    findings.append(_finding(
                        "warning", item_id,
                        "derives_from %s is archived -- the task is judged against "
                        "criteria that left the active context" % origin,
                        "re-point the task at a live origin, or archive it too",
                    ))
                continue          # non-existent origins are refused at capture
            origin_type, origin_item = entry
            auto = AUTOMATA.get(origin_type)
            if auto and origin_item.get("status") in (auto.terminals or ()):
                findings.append(_finding(
                    "warning", item_id,
                    "derives_from %s is %s (terminal) -- a task deriving from a closed "
                    "origin is stale" % (origin, origin_item.get("status")),
                    "close the task, or re-point it at the item that supersedes %s" % origin,
                ))
            conflict = origin_root_conflict(state, origin, root) if root else None
            if conflict:
                findings.append(_finding(
                    "error", item_id,
                    "derives_from %s" % conflict,
                    "the dispatch gate resolves acceptance_refs against the origin, so "
                    "this task would be judged against another root's criteria -- fix "
                    "product_requirement or derives_from",
                ))
    return findings


def tasks_under_an_inbox_item(state: ProjectState) -> dict:
    """{task id: the inbox item it hangs from} over the WHOLE store -- active and archived.

    THE RELAPSE DETECTOR BUG-0091 ASKS FOR, and it reads the whole store rather than the active map
    for a measured reason: every such work order this repository holds is ARCHIVED, so a reader of
    the active items alone answers "none" about a practice that is exactly what DEC-0066 was
    written against. How many there are is a measurement of a round and lives in that round's
    report, not in a second copy here -- one written into this comment was wrong about this very
    function within a day, because it counted one parent field and the function reads both.

    WHICH TYPES ARE THE INBOX is `backlog_types.is_inbox_type`, the same contract
    `dispatch._assert_the_origins_are_not_inbox_items` refuses a new one from and
    `_check_fr_result_link` takes its duty from.

    ARCHIVED ORDERS ARE HISTORY AND STAY VALID -- DEC-0066 (4) says so in as many words -- which is
    why this COUNTS rather than judges. It is deliberately NOT what `validate_state` calls: that
    runs on the merge and push line, and an archive walk of every item file there is the shape
    `_delivery_evidence` records as having turned a slow validate into a blocked push. The
    validator's finding below reads the active map it already holds; both read `_inbox_origins_of`,
    so the counter and the finding cannot disagree about what an inbox origin is.
    `tools/test_report.py::test_the_inbox_counter_sees_an_archived_work_order_and_the_validator_only_a_live_one`
    """
    found = {}
    for item_type, _stem, item, _path, exc in _iter_active(state):
        if exc or item_type != "TSK" or not isinstance(item, dict):
            continue
        found.update(_inbox_origins_of(item))
    for item_type, item in _iter_archived_items(state):
        if item_type == "TSK":
            found.update(_inbox_origins_of(item))
    return found


def _inbox_origins_of(task: dict) -> dict:
    """{task id: the first inbox item it names} -- both parent fields, one reading."""
    for field in PARENT_FIELDS.get("TSK", ()):
        for one in field_elements(task.get(field)):
            try:
                item_type, _ = parse_id(str(one))
            except ValueError:
                continue
            if is_inbox_type(item_type):
                return {str(task.get("id")): str(one)}
    return {}


def _iter_archived_items(state: ProjectState):
    """(type, item) for every archived item file the store holds -- the half `_iter_active` misses."""
    archive = ext_path(state.archive_root())
    if not os.path.isdir(archive):
        return
    for base, _dirs, names in os.walk(archive):
        for name in sorted(names):
            stem = os.path.splitext(name)[0]
            try:
                item_type, _ = parse_id(stem)
            except ValueError:
                continue
            try:
                item = state._read_yaml(os.path.join(base, name))
            except Exception:  # noqa: BLE001 -- an unreadable archived file is nobody's finding
                continue
            if isinstance(item, dict):
                yield item_type, item


def _check_tasks_under_an_inbox_item(active_items: dict) -> list:
    """The finding for a LIVE work order hanging from a wish -- see `tasks_under_an_inbox_item`.

    A WARNING AND NOT AN ERROR: DEC-0066 (4) keeps the orders that already exist valid, and
    `dispatch` is what refuses a NEW one, so an error here would block the merge of a repository
    for a history its own decision protects. What it costs is stated rather than assumed -- such an
    order is undispatchable anyway, so the warning names a dead end rather than inventing one.
    """
    origins = {}
    for item_id, (item_type, item) in sorted(active_items.items()):
        if item_type == "TSK":
            origins.update(_inbox_origins_of(item))
    return [
        _finding(
            "warning", task_id,
            "hangs from %s, which is an inbox item and not a root -- a wish is what waits for the "
            "triage that turns it into a goal, and no user approval exists for its type, so this "
            "order cannot be dispatched at all" % origin,
            "triage %s (TRIAGED, then CONVERTED with `%s` = the new goal, or MERGED into an "
            "existing one) and derive the work order from that goal"
            % (origin, TRIAGE_RESULT_LINK[parse_id(origin)[0]][1]),
        )
        for task_id, origin in sorted(origins.items())
    ]


def _root_type_of(item: dict) -> str:
    """The TYPE of the item a task hangs from, read off its id, or "".

    The id rather than a lookup: a root that has been archived is out of `active_items` and would
    read as "no root", which would silence the check for exactly the tasks that ran longest. An id
    carries its type, and `capture` refuses a `product_requirement` that names nothing.
    """
    try:
        return parse_id(str(item.get("product_requirement") or ""))[0]
    except Exception:  # noqa: BLE001 -- a malformed reference is the reference checks' finding
        return ""


def accepted_without_a_verdict(state: ProjectState, active_items: dict = None) -> dict:
    """{task id: [missing kind, ...]} for tasks whose work was accepted with no QA verdict on it.

    `active_items` is the map `validate_state` has already built ({id: (type, item)}); a caller
    that has none passes nothing and this reads the active items itself. Two callers, one answer:
    the validator's finding and the SessionStart briefing (`_kernel.unverified_delivery_briefing`)
    are the same question asked in two places, and answering it twice is how they would drift.

    WHICH STATUS "ACCEPTED" IS, derived and not typed: `confirming_edge("TSK")` is the edge on
    which a task is closed as CONFIRMED, and the status it leaves FROM is the one that means the
    work is finished but not yet confirmed. Rename `DONE` and this moves with it.

    WHY THIS EXISTS -- BUG-0060, and the measurement is the whole argument. The evidence drawer
    was empty after two dev pilots, and the two moments that ask for a verdict are the merge
    (`gate_git`) and the confirming edge itself. Neither was reached: pilot 3 ended with 11 tasks
    at the accepted status and none confirmed, pilot 4's half 2 never got that far, and this
    repository's own 81 archived tasks are CANCELLED to the last one. So the absence was never
    stated anywhere -- a drawer nobody fills looks exactly like a project that owes nothing. This
    is what states it, on the status the runs really reach.

    A WARNING AND NOT AN ERROR, deliberately: standing here is what a task DOES between the
    developer's handback and QA, so this is a debt, not a defect. It blocks nothing on its own --
    the merge is `gate_git`'s question and it asks it for itself.

    ONLY WHERE THE VERDICT IS OWED, and that is derived rather than assumed of every kit. A task
    is asked for one when it hangs from the item type a project of its kit hangs from --
    `backlog_types.ROOT_TYPE_BY_KIT`, whose values are the roots whose kits' shipped texts promise
    the delivery kinds (`gate_git` demands the same three at the merge). A kit absent from that map
    has no such root, and the office kit is the measured case: it creates tasks like any other, and
    the only Evidence any of its roles produces is `kind: audit`, which is no delivery verdict at
    all. Without this term every completed office task would carry a debt nothing in that kit can
    pay -- a warning that can only be ignored, which is how a validator stops being read.

    NARROWER THAN `qa_verdicts`, said rather than implied: `qa_verdicts_by_subject` is one pass
    over the store and groups by the ids an Evidence WRITES, without the reference walk. Evidence
    recorded about something that hangs from the task is therefore not counted here, while
    `qa_verdicts` would count it. The one pass is the reason -- this runs inside `validate_state`,
    which `gate_memory_complete` reaches on a MERGE OR PUSH line (recorded at
    `_check_dispatch_approval_presented`), and a per-task walk over the store is the shape
    `_delivery_evidence` documents as having turned a validate into a blocked push.
    """
    edge = confirming_edge("TSK")
    if edge is None:
        return {}
    accepted_status = edge[0]
    if active_items is None:
        active_items = _active_map(state)
    delivery_roots = set(ROOT_TYPE_BY_KIT.values())
    tasks = sorted(item_id for item_id, (item_type, item) in active_items.items()
                   if item_type == "TSK" and item.get("status") == accepted_status
                   and _root_type_of(item) in delivery_roots)
    if not tasks:
        return {}
    by_subject = qa_verdicts_by_subject(state)
    owed = {}
    for task_id in tasks:
        verdicts = by_subject.get(task_id, {})
        missing = sorted(kind for kind in QA_EVIDENCE_KINDS
                         if (verdicts.get(kind) or {}).get("result") != PASSING_RESULT)
        if missing:
            owed[task_id] = missing
    return owed


def verification_missing_for_goal(state: ProjectState, goal_id: str,
                                  active_items: dict = None) -> list:
    """The QA evidence kinds with no PASSING verdict anywhere under this goal -- the emptiness
    DEC-0113 makes the PM ask the user about before it requests the goal's acceptance (H59).

    THE SUBJECT IS THE GOAL AND EVERYTHING THAT HANGS FROM IT, because a verification run is
    recorded about the TASK it measured and almost never about the goal: asking the goal id alone
    would report "nobody verified" for a goal whose every task carries a passing `test` record.
    `accepted_without_a_verdict` asks the neighbouring question -- one task at a time, for the
    validator's warning; this one asks it once for a goal, for a question a human answers, and
    both read `qa_verdicts_by_subject` so the two cannot come to disagree about what a verdict is.

    WHAT IT CANNOT SEE, said rather than left to be found: an ARCHIVED task's evidence. The
    subjects are the goal plus the ACTIVE items that name it as their root, so a goal whose only
    verified task was archived before the acceptance reads as unverified and the user is asked a
    question they could have been spared. That is the over-asking direction, and the answer to it
    is a sentence in a chat -- while the other direction would be silence about a goal nobody
    measured, which is the whole of H59.
    `tools/test_approvals_dispatch.py::test_a_goal_with_no_verification_run_is_asked_about_once`
    """
    if active_items is None:
        active_items = _active_map(state)
    subjects = {str(goal_id)}
    subjects.update(item_id for item_id, (_type, item) in active_items.items()
                    if str(item.get("product_requirement") or "") == str(goal_id))
    by_subject = qa_verdicts_by_subject(state)
    answered = set()
    for subject in subjects:
        verdicts = by_subject.get(subject) or {}
        answered.update(kind for kind in QA_EVIDENCE_KINDS
                        if (verdicts.get(kind) or {}).get("result") == PASSING_RESULT)
    return sorted(set(QA_EVIDENCE_KINDS) - answered)


def _check_accepted_tasks_carry_a_verdict(state: ProjectState, active_items: dict) -> list:
    """The finding `accepted_without_a_verdict` produces -- see it for the derivation."""
    return [
        _finding(
            "warning", task_id,
            "%s with no passing QA Evidence of kind(s) %s -- the work is booked as finished and "
            "nothing in the project measured it"
            % (active_items[task_id][1].get("status"), ", ".join(missing)),
            "run the quality role and record its run: `python scripts/harness.py evidence --kind "
            "<%s> --result <pass|fail> --related %s --summary ... --artifact-ref <staged proof> "
            "--run-command \"<the line you ran>\" --run-scope <full|selection>`; the same records "
            "are what open the merge and what carry the task to its confirmed status"
            % ("|".join(missing), task_id),
        )
        for task_id, missing in sorted(accepted_without_a_verdict(state, active_items).items())
    ]


def _check_experiment_reports(active_items: dict) -> list:
    """R7 (parity row 84): an EXP that reached ANALYZED without report evidence.

    "Report pro EXP sofort nach PASS; sonst incomplete." Without it the research
    loop can close an experiment whose result exists only in a chat message.
    """
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        if item_type != "EXP" or item.get("status") != "ANALYZED":
            continue
        if not (item.get("evidence_refs") or []):
            findings.append(_finding(
                "error", item_id,
                "ANALYZED without evidence_refs -- an experiment with no report is "
                "incomplete, whatever the conversation said (parity row 84)",
                "attach the report as evidence, or move the EXP back to COMPLETED",
            ))
    return findings


def _check_premise_recheck(state: ProjectState, active_items: dict) -> list:
    """R8 (parity row 87) plus BUG-0004: a decision carrying premise_invalidation_triggers and newer
    scope work that never records a re-check -- and, whenever a re-check IS recorded, that it names a
    real decision.

    THE WARNING is a warning on purpose: whether a trigger actually fired is a judgement no pattern
    can make, and the user's "maximal haerten" decision says heuristics warn, never fail closed.

    THE EXISTENCE CHECK is what makes `premise_rechecks` a capability and not ballast (BUG-0004). The
    field is READ here and WRITTEN through the sanctioned `update` command (`state.update_item`),
    which -- like every kernel edit -- takes the value without knowing what a re-check should name
    (`state` module note: update_item does not reject unknown extra fields). So an architect could
    clear this very warning with an id no decision carries, and nothing measured it. The validator
    closes that: a re-check naming a phantom is a cleared warning resting on nothing, so it is an
    error, exactly as a phantom `derives_from` is. WHICH decision it names is the writer's judgement
    (the same boundary the warning keeps); THAT it names a real item is the writer's contract.
    """
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        if item_type not in ("PR", "RQ", "CR"):
            continue
        for ref in field_elements(item.get("premise_rechecks")):
            ref = str(ref)
            if ref not in active_items and not _in_archive(state, ref):
                findings.append(_finding(
                    "error", item_id,
                    "premise re-check names %s, which no item carries -- a cleared warning "
                    "resting on a phantom decision" % ref,
                    "record the re-check against the DEC id that actually carries the "
                    "invalidation triggers, or drop the entry",
                ))
    triggered = [(i, it) for i, (t, it) in sorted(active_items.items())
                 if t == "DEC" and (it.get("premise_invalidation_triggers") or [])]
    if triggered:
        for item_id, (item_type, item) in sorted(active_items.items()):
            if item_type not in ("PR", "RQ", "CR") or item.get("status") == "DRAFT":
                continue
            checked = {str(ref) for ref in field_elements(item.get("premise_rechecks"))}
            missing = [dec for dec, _ in triggered if dec not in checked]
            if missing:
                findings.append(_finding(
                    "warning", item_id,
                    "no premise re-check recorded against %s, which carries invalidation "
                    "triggers" % ", ".join(missing[:3]),
                    "the architect re-checks direction-setting decisions on every PR/CR; "
                    "record the outcome in `premise_rechecks` (naming the DEC) even when "
                    "nothing changed -- \"not up for renegotiation\" is forbidden",
                ))
    return findings


def _check_fr_result_link(state: ProjectState, active_items: dict) -> list:
    """BUG-0009(a): a feature request that CONVERTED or MERGED names the item it became.

    The FR automaton's `terminal_from` comment reads "a triage OUTCOME", and the V1 mapping calls
    `FR ACCEPTED` "becomes a PRD" -- but WHICH item the request became was nowhere in the state, so
    the trail ended exactly where the interesting question ("what came of this wish") begins.
    `FR.triage_result` was a status-dependent duty from TRIAGED, but it never forced NAMING an item.
    The two outcomes that leave a result (`FR_RESULT_TERMINALS`) now owe `FR_RESULT_FIELD`, and the
    named item must exist; REJECTED points to nothing and is left alone.

    BACKWARD-COMPATIBLE by construction: the duty binds only in those two terminal states, so every
    OPEN/TRIAGED request -- which is every FR in the store today -- owes nothing.

    WHICH TYPES OWE IT is read off `backlog_types.TRIAGE_RESULT_LINK` rather than named here, and
    that is the same map `dispatch` refuses a work order under an inbox item from (BUG-0091). The
    duty and the refusal are then two readings of one contract instead of two spellings of it.
    """
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        outcome = TRIAGE_RESULT_LINK.get(item_type)
        if outcome is None or item.get("status") not in outcome[0]:
            continue
        _result_terminals, result_field = outcome
        result = item.get(result_field)
        if not result:
            findings.append(_finding(
                "error", item_id,
                "%s without %s -- the request became another item, but the state does not say "
                "which" % (item.get("status"), result_field),
                "record the item this request became in `%s`" % result_field,
            ))
            continue
        if str(result) not in active_items and not _in_archive(state, str(result)):
            findings.append(_finding(
                "error", item_id,
                "%s names %s, which no item carries" % (result_field, result),
                "point `%s` at the id of the item this request became" % result_field,
            ))
    return findings


# The DEC status that means "in force". DEC has no automaton, so its vocabulary is the map's, whose
# FIRST value is the initial/holding one (backlog_types names that ordering); anything else -- today
# only `SUPERSEDED`, e.g. a migrated ADR -- means the decision has been retired. Derived rather than
# spelled `"VALID"` here so a renamed status moves the meaning with it.
_DEC_IN_FORCE_STATUS = NON_AUTOMATON_STATUSES["DEC"][0]


def _superseded_decisions(active_items: dict) -> dict:
    """{superseded DEC id -> the active DEC id that replaced it}, from the forward `supersedes` links.

    ONE source of truth: the link lives on the NEWER decision and the "is superseded" answer is
    DERIVED from it, so there is no back-pointer to drift out of step (BUG-0009(b)).
    """
    superseded_by = {}
    for item_id, (item_type, item) in active_items.items():
        if item_type != "DEC":
            continue
        for ref in field_elements(item.get(DEC_SUPERSEDES_FIELD)):
            superseded_by[str(ref)] = item_id
    return superseded_by


def _holding_decisions(dec_items: dict) -> set:
    """The ids in `dec_items` ({id: DEC item}) whose decision still HOLDS.

    The ONE definition of "holds", read by `standing_decisions` and by the session brief. A decision
    holds when it is IN FORCE (`_DEC_IN_FORCE_STATUS`; a `SUPERSEDED` one -- a migrated ADR, say --
    does NOT, and the link is not the only way a decision is retired) AND no other active decision
    names it in `supersedes`. The link half is `_superseded_decisions`, so the forward link stays the
    single source it is everywhere else rather than being re-derived here.

    "NAMES IT IN `supersedes`" is a claim about a FIELD SHAPE too, and it is why `supersedes` is one
    of `backlog_types.REFERENCE_LIST_FIELDS`: written as a bare id it was read as its letters, none
    of which is an item id, so the replaced decision kept counting as holding -- measured, and
    pinned by `test_report.test_a_scalar_supersedes_retires_the_decision_it_names`.
    """
    superseded = _superseded_decisions({d: ("DEC", it) for d, it in dec_items.items()})
    return {d for d, it in dec_items.items()
            if d not in superseded and it.get("status") == _DEC_IN_FORCE_STATUS}


# -- a decision nobody carries (FR-0012, DEC-0083) ------------------------------------------------

_DEC_ID_IN_TEXT_RX = re.compile(r"\bDEC-\d{4}\b")


def _decisions_items_name(state: ProjectState, active_items: dict) -> set:
    """Every DEC id some NON-DECISION item names, anywhere in its fields -- the pointer direction.

    THE CARRIER IS AN ITEM THAT DOES THE WORK, so another decision is not one: a `supersedes` link
    and a decision quoting its predecessor are decisions talking to each other, and the case
    FR-0012 was filed on (`DEC-0034`, VALID for 26 days with nothing built) would have been silenced
    by exactly that. So DEC items are read as subjects here, never as carriers.

    THE WHOLE STORE and not only the active part: a decision carried by an item that has since been
    archived was carried, and reporting it as uncarried would send a reader after work that is done.

    THE FIELDS, not a file: this reads the values of stored items, which is the same subject
    `validate_state` judges everywhere else. A citation in a document under `docs/` is NOT a carrier
    -- that is the difference between an item and prose, and it is the difference FR-0012 is about.
    """
    named = set()
    for item in state._iter_every_stored_item():
        item_id = str(item.get("id") or "")
        if item_id.startswith("DEC-"):
            continue
        for value in item.values():
            for one in field_elements(value):
                named.update(_DEC_ID_IN_TEXT_RX.findall(str(one)))
    for item_id, (item_type, item) in active_items.items():
        if item_type == "DEC":
            continue
        for value in item.values():
            for one in field_elements(value):
                named.update(_DEC_ID_IN_TEXT_RX.findall(str(one)))
    return named


def _check_decision_carriers(state: ProjectState, active_items: dict) -> list:
    """DEC-0083: a decision says which items carry its work, and one nobody carries is named.

    TWO LINES, and they answer two different questions:

      * `work` naming an id NO item carries is an ERROR -- the same contract every other binding
        has, and a pointer nobody can follow is worse than none;
      * a decision IN FORCE that carries no `work` and that no item anywhere names is a WARNING,
        "decision without a carrier". `work: none` silences it, and that silence is the point: a
        naming rule or a verdict commits nobody, and a validator that could not be told so would be
        a validator nobody reads (`delivery_closure_rollup`'s own argument).

    THE MEASURED CASE is `DEC-0034`: a model-escalation ladder that stood VALID for 26 days while
    nothing built it and no item pointed at it, found by the user and by no review round (DEC-0080).
    Both halves catch it -- no field, and no carrier.

    WHAT STAYS HUMAN, and the decision says so itself: a `work: none` on a decision that DOES demand
    work is caught by nobody. That is the same half of `FR-0007` the comment duty leaves to the role
    that writes and the role that reviews.

    `tools/test_report.py::test_a_decision_nobody_carries_is_named_and_none_is_the_silence` holds
    both lines, the silence and the archived-carrier case.
    """
    subjects = {item_id: item for item_id, (item_type, item) in active_items.items()
                if item_type == "DEC"}
    if not subjects:
        return []
    findings = []
    named = None
    for item_id, item in sorted(subjects.items()):
        work = item.get(DEC_WORK_FIELD)
        if work_is_none(work):
            continue        # the ONE silence DEC-0083 (2)(c) names
        if names_something(work):
            for ref in field_elements(work):
                ref = str(ref).strip()
                if not ref:
                    continue    # a blank BESIDE a real id says nothing; the real one is read
                if ref not in active_items and not _in_archive(state, ref):
                    findings.append(_finding(
                        "error", item_id,
                        "%s names %s, which no item carries" % (DEC_WORK_FIELD, ref),
                        "point `%s` at the ids of the items that really build what this decision "
                        "commits, or write `%s: %s` when it commits nobody"
                        % (DEC_WORK_FIELD, DEC_WORK_FIELD, DEC_WORK_NONE),
                    ))
                elif ref.startswith("DEC-"):
                    # A DECISION IS NOT A CARRIER, and the two halves of this check have to agree:
                    # `_decisions_items_name` refuses to read one decision as another's carrier,
                    # because the case FR-0012 was filed on would have been silenced by exactly that.
                    # Measured (verifier round 3, R3-4): `work: ['DEC-0001']` was silent, so the same
                    # DEC-0034 state was reachable one level up.
                    findings.append(_finding(
                        "error", item_id,
                        "%s names %s, and a decision is not a carrier -- somebody has to BUILD what "
                        "this one commits" % (DEC_WORK_FIELD, ref),
                        "name the items that do the work (a `TSK`, a goal), or write `%s: %s` when "
                        "it commits nobody" % (DEC_WORK_FIELD, DEC_WORK_NONE),
                    ))
            continue
        # ...and everything else -- absent, `[]`, `""`, `[""]`, `"   "` -- is the SAME state: the
        # field says nothing. Reading an empty container as an answer was the defect (verifier
        # round 2, N-B2): four spellings silenced this line without ever saying `none`, and `[]` is
        # exactly what a JSON body carries when the author does not have the ids yet.
        if item.get("status") in NON_AUTOMATON_STATUSES.get("DEC", ())[1:]:
            continue        # superseded: it is not in force, so nobody owes it work
        if named is None:
            named = _decisions_items_name(state, active_items)
        if item_id not in named:
            findings.append(_finding(
                "warning", item_id,
                "decision without a carrier -- it names no `%s` and no item in this store names "
                "it, so nothing says whether anybody is building what it decided" % DEC_WORK_FIELD,
                "record the items that carry it (`python scripts/harness.py update %s` with `%s: "
                "[ITEM-nnnn]`), or `%s: %s` when it commits nobody -- a decision that demands work "
                "and has no carrier is the DEC-0034 case (FR-0012, DEC-0083)"
                % (item_id, DEC_WORK_FIELD, DEC_WORK_FIELD, DEC_WORK_NONE),
            ))
    return findings


def _check_dec_supersedes(state: ProjectState, active_items: dict) -> list:
    """BUG-0009(b): a decision that supersedes older ones names them, each named id exists and is a
    DEC, and a still-active decision that has been superseded is flagged for archival.

    A DEC has no automaton, so nothing else moves a replaced decision out of the active context -- an
    automaton type gets the "terminal item awaiting archive" warning, and without this a superseded
    decision would linger indefinitely reading as though it still holds. The existence/type check is
    the link's contract (a decision supersedes a decision, not a bug or a task); the warning is the
    DEC analogue of the terminal-awaiting-archive warning the automaton types already get.
    """
    findings = []
    superseded_by = _superseded_decisions(active_items)
    for item_id, (item_type, item) in sorted(active_items.items()):
        if item_type != "DEC":
            continue
        for ref in field_elements(item.get(DEC_SUPERSEDES_FIELD)):
            ref = str(ref)
            entry = active_items.get(ref)
            if entry is None and not _in_archive(state, ref):
                findings.append(_finding(
                    "error", item_id,
                    "%s names %s, which no item carries" % (DEC_SUPERSEDES_FIELD, ref),
                    "point `%s` at the id of the decision this one replaces" % DEC_SUPERSEDES_FIELD,
                ))
            elif entry is not None and entry[0] != "DEC":
                findings.append(_finding(
                    "error", item_id,
                    "%s names %s, which is a %s, not a decision"
                    % (DEC_SUPERSEDES_FIELD, ref, entry[0]),
                    "a decision supersedes another decision; `%s` takes DEC ids only"
                    % DEC_SUPERSEDES_FIELD,
                ))
    for dec_id, replacer in sorted(superseded_by.items()):
        if active_items.get(dec_id, (None,))[0] == "DEC":
            findings.append(_finding(
                "warning", dec_id,
                "superseded by %s -- a replaced decision awaiting archive" % replacer,
                "run `python scripts/harness.py archive %s`" % dec_id,
            ))
    return findings


def _check_reference_list_shape(active_items: dict) -> list:
    """A `REFERENCE_LIST_FIELDS` field written as a bare value where the state carries a list.

    A WARNING, and the severity is the measurement rather than caution: since BUG-0038 every read
    of these fields A DERIVATION OVER THE KERNEL SOURCES CAN SEE goes through `field_elements`, so a
    scalar resolves as the one reference it spells and no gate decides differently because of it.
    That qualifier is the honest width of the claim, not modesty: what the derivation reaches, and
    what it does not, are in
    `test_backlog_types._item_fields_read_as_sequences`, and the wire itself is
    `test_backlog_types.test_every_kernel_read_of_a_reference_list_field_goes_through_field_elements`.

    NAMING IT IS ALSO ALL THIS CAN DO. `design_refs` is a hashed field (`HASHED_FIELDS`), so
    correcting the shape moves the item's revision through `_update_item_locked`; a validator that
    quietly rewrote the value would be doing that behind whatever approval the item carries -- and
    `project_memory/**` has one writer, which is not this function.

    THE CHECK IS THE SHAPE ONLY. An item already damaged by the BUG-0038 chain carries a LIST -- of
    letters -- and passes here; that half is `_check_design_refs_resolve` and the two existence
    checks the other two fields already had.
    `test_report.test_validate_names_a_scalar_reference_list_field`.
    """
    findings = []
    for item_id, (_item_type, item) in sorted(active_items.items()):
        for field in REFERENCE_LIST_FIELDS:
            value = item.get(field)
            if value is None or value == "" or isinstance(value, (list, tuple)):
                continue
            findings.append(_finding(
                "warning", item_id,
                "%s is a single %s, not a list -- the kernel reads it as ONE reference"
                % (field, type(value).__name__),
                "write it as a list through the kernel edit path "
                "(`python scripts/harness.py update %s`)" % item_id,
            ))
    return findings


def _check_nonempty_fields(active_items: dict) -> list:
    """A `NONEMPTY_FIELDS` field stored empty -- the items that door came too late for (BUG-0023).

    THE SAME MAP AND THE SAME PREDICATE THE CAPTURE DOOR READS (`state.capture_preflight` refuses
    with `backlog_types.names_something`, and so does this), so what a new item is refused for and
    what a stored one is named for cannot become two readings. Both used to ask `not value`, which
    is a question about the CONTAINER: `[""]`, `[None]` and `["   "]` were stored and named by
    nobody. A WARNING and not an error: the stored orders are history, an error would block the
    merge of a repository for items no command can repair once they left DRAFT (`TSK_PLAN_FIELDS`
    freezes the field), and the finding says what such an order costs -- nothing can verify it.
    `test_report.test_validate_names_a_stored_order_that_expects_nothing` holds the door and this
    line to one map and one predicate, over every shape.
    """
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        for field in NONEMPTY_FIELDS.get(item_type, ()):
            if field in item and not names_something(item.get(field)):
                findings.append(_finding(
                    "warning", item_id,
                    "%s names nothing -- a list of blanks says exactly what leaving the field "
                    "out says, and nothing can be measured against it" % field,
                    "re-plan the order with the %s it is measured against (DRAFT: `python "
                    "scripts/harness.py update %s`; past DRAFT the field is frozen and the order "
                    "is cancelled and re-created)" % (field, item_id),
                ))
    return findings


def _check_single_value_fields(active_items: dict) -> list:
    """A `SINGLE_VALUE_FIELDS` field written as several things -- the items the door came too late
    for (DEC-0043).

    AN ERROR, WHILE THE NEIGHBOURING SHAPE CHECK IS A WARNING, and the difference is measured
    rather than felt: a scalar in a reference-list field resolves as the one reference it spells
    and no gate decides differently, whereas H42's chain is a gate that DECIDES DIFFERENTLY --
    `dev-team/hooks/gate_test_coverage.py` refuses a push over an untested governed area under
    `scope: compounder/` and allows the same push under `scope: ["compounder/"]`. An error is also
    what a dev/research project's `gate_memory_complete` reads, so such a project cannot merge
    until the item is corrected: friction in the honest direction, since the rule the item states
    is guarding nothing meanwhile. Both halves of that -- the gate that goes quiet and the merge
    this finding then stops -- are measured as hook processes in
    `test_hooks.test_the_shipped_readers_of_a_single_value_field_still_read_one_value`.

    NAMING IT IS ALL THIS CAN DO, for the reason `_check_reference_list_shape` gives: the state has
    one writer and it is not this function. The remedy is the kernel edit path, which refuses the
    same spelling (`state._assert_single_value_fields`), so the two cannot drift.
    `test_report.test_validate_names_an_inv_scope_spelled_as_several_things`.
    """
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        for field, why, remedy in single_value_offences(item_type, item):
            findings.append(_finding(
                "error", item_id,
                "%s is a %s where the contract is ONE value -- %s, so this rule reaches no reader"
                % (field, type(item[field]).__name__, why),
                "%s. Rewrite it through the kernel edit path "
                "(`python scripts/harness.py update %s`)" % (remedy, item_id),
            ))
    return findings


def _check_design_refs_resolve(state: ProjectState, active_items: dict) -> list:
    """Every `design_refs` entry names a frozen design that EXISTS -- the II.6a question, asked
    where the state is judged rather than only where a spawn is refused.

    WHY THIS CHECK EXISTS. `supersedes` and `premise_rechecks` have carried existence checks since
    BUG-0009(b)/BUG-0004, so a letter-split value at least surfaces as findings naming letters;
    `design_refs` had none, which is why the measured BUG-0038 chain ended in "0 error(s),
    0 warning(s)" over an item holding 34 one-letter entries. Normalising the readers stops the
    damage being CREATED; an item written that way before is reachable only through a check, and
    this is it.

    AND ONE MEMBER OF `REFERENCE_LIST_FIELDS` STILL HAS NO EXISTENCE CHECK: `architecture_refs`,
    which joined that tuple with TSK-0139 when `staging.freeze_architecture` finally gained a writer
    for it (BUG-0054). What it DOES get from joining is the shape check --
    `_check_flattened_reference_fields` walks the tuple, so a scalar written where the state holds
    a list is reported for it exactly as for the other three, which is the BUG-0038 damage class.
    What is missing is only "the frozen revision this entry names is on disk". Not added in that
    round on purpose: a new validator finding changes what `validate` says about every existing
    project, and the field had been producer-less until that hour, so no stored entry can yet be
    stale. Named here rather than left to be discovered.

    Through `dispatch._design_ref_resolves`, the resolver the dispatch gate itself uses, so a
    validator that says "fine" and a gate that refuses the spawn cannot come apart.
    `test_report.test_validate_names_design_refs_that_resolve_to_nothing`.
    """
    from .dispatch import _design_ref_resolves   # lazy: keeps the package's import graph a tree

    findings = []
    for item_id, (_item_type, item) in sorted(active_items.items()):
        missing = [str(ref) for ref in field_elements(item.get("design_refs"))
                   if not _design_ref_resolves(state, str(ref))]
        if missing:
            shown = ", ".join(missing[:3]) + (" ..." if len(missing) > 3 else "")
            findings.append(_finding(
                "error", item_id,
                "design_refs names %d reference(s) that resolve to no frozen design: %s"
                % (len(missing), shown),
                "freeze the design through the promotion path, or correct the entry -- this is the "
                "list the II.6a dispatch tooth resolves on a ROOT item, and a reference to nothing "
                "binds nothing",
            ))
    return findings


def standing_decisions(state: ProjectState):
    """Which active DEC items still hold, and which have been superseded -- answered from the
    `supersedes` links, not from `context` prose (BUG-0009(b)).

    A decision holds when it is IN FORCE and no OTHER active decision names it in `supersedes`; a
    decision another one replaced, or one whose own status is SUPERSEDED (a migrated ADR), does not.
    Returns (standing, superseded_by): `standing` is the set of active DEC ids that still hold
    (`_holding_decisions`), `superseded_by` maps a LINK-superseded active DEC id to the id of the
    decision that replaced it. Read-only; no lock, like the other report queries.
    """
    active_decisions = {}
    for item_type, _stem, item, _path, exc in _iter_active(state):
        if exc or not isinstance(item, dict) or item_type != "DEC":
            continue
        dec_id = item.get("id")
        if dec_id:
            active_decisions[dec_id] = item
    superseded_by = _superseded_decisions({d: ("DEC", it) for d, it in active_decisions.items()})
    standing = _holding_decisions(active_decisions)
    superseded = {d: s for d, s in superseded_by.items() if d in active_decisions}
    return standing, superseded


def _check_ui_delivery_sequence(active_items: dict) -> list:
    """R12 (parity row 107, the 4-slices incident): no SECOND user-visible item
    enters delivery while one is DELIVERED and not yet ACCEPTED.

    The point of the sequence rule is that the user SEES a slice before the next
    is built on its assumptions; four unreviewed slices in flight is how the
    incident happened.
    """
    awaiting = [i for i, (t, it) in sorted(active_items.items())
                if t in ("PR", "RQ") and it.get(GOAL_CLASS_FIELD) not in PRODUCTLESS_CLASSES
                and it.get("status") == "DELIVERED"]
    if not awaiting:
        return []
    findings = []
    for item_id, (item_type, item) in sorted(active_items.items()):
        if (item_type in ("PR", "RQ") and item.get(GOAL_CLASS_FIELD) not in PRODUCTLESS_CLASSES
                and item.get("status") == "IN_DELIVERY"):
            findings.append(_finding(
                "error", item_id,
                "IN_DELIVERY while %s is DELIVERED and not yet ACCEPTED -- a second "
                "user-visible slice is being built on assumptions the user has not "
                "seen confirmed (parity row 107)" % ", ".join(awaiting[:3]),
                "get %s accepted (or explicitly rejected) first" % awaiting[0],
            ))
    return findings


def _in_archive(state: ProjectState, item_id: str) -> bool:
    try:
        item_type, _ = parse_id(item_id)
    except ValueError:
        return False
    base = os.path.join(state.archive_root(), item_type)
    if not os.path.isdir(ext_path(base)):
        return False
    for year in os.listdir(ext_path(base)):
        if os.path.exists(ext_path(os.path.join(base, year, item_id + ".yaml"))):
            return True
    return False


# -- doctor (read-only, never writes state; spec II.4) -------------------------

# The capabilities spec II.8 names, each `verified` or `unverified`, plus the SPLIT the phase-2
# review asked for. `state_write_protection` was one value covering two different mechanisms with
# two different strengths, so a project could read "verified" while every shell command in it
# walked past the file-tool gate.
CAPABILITIES = (
    "spawn_veto",
    "approval_provenance",
    "hook_trust",
    "state_write_protection.file",
    "state_write_protection.shell",
)
# Which ones must be verified for `enforcement: hard`. All of them: II.8 says "NUR wenn alle
# notwendigen Faehigkeiten verifiziert sind", and after the split both halves are necessary --
# they guard the same directory through different doors.
_REQUIRED_FOR_HARD = frozenset(CAPABILITIES)


def _settings_layers(repo_root: str):
    """Every settings layer Claude Code merges, LOWEST precedence first.

    The local file is REAL wiring — Claude Code merges it — and reading only the committed one
    reported a hook as unregistered when it was live. The USER layer (`~/.claude/settings.json`)
    is real too and was missing: it is where `disableAllHooks` is most likely to be set, because a
    user who wants hooks off wants them off everywhere, and a project reading only its own two
    files reported full enforcement while nothing ran.

    Order is precedence order, so a caller that needs "the winning value" can take the LAST layer
    that defines a key. `_hooks_disabled` deliberately does not: see there.
    """
    # `CLAUDE_CONFIG_DIR` is Claude Code's own override for that directory. Honoured because
    # ignoring it would read a file the provider does not, and because a doctor that consults the
    # developer's real home makes its own test suite depend on whose machine it runs on.
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude")
    home = os.path.join(config_dir, "settings.json")
    project = os.path.join(repo_root, ".claude")
    for path in (home, os.path.join(project, "settings.json"),
                 os.path.join(project, "settings.local.json")):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            yield data


def _hooks_disabled(repo_root: str) -> bool:
    """Claude Code's documented global kill switch. Nothing enforces anything when it is set.

    ANY layer setting it counts, rather than the highest-precedence one that mentions it. That is
    deliberately not a merge: the question here is not "what is configured" but "could a hook have
    been suppressed", and answering it wrong in the permissive direction is how a report claims
    enforcement that is not running. A project that re-enables hooks over a user-level kill switch
    is welcome to be reported as `unverified` until someone looks; the reverse mistake is silent.
    """
    return any(layer.get("disableAllHooks") is True for layer in _settings_layers(repo_root))


def _wired_hooks(repo_root: str) -> dict:
    """{hook filename: {event: set of matchers}} — only registrations that could actually FIRE.

    Four things are checked that a first cut ignored, and each of them was a settings shape in
    which NOTHING is enforced while the matrix reported `hard`:

      * the MATCHER. It is a tool-name filter, so `gate_dispatch` registered for `Edit|Write`
        never sees a spawn. Every shipped kit uses per-tool matchers, so a one-token typo silently
        upgraded a project — which is precisely the failure the `.file`/`.shell` split exists to
        prevent, reached through a different door.
      * the hook TYPE. Claude Code supports `command|http|mcp_tool|prompt|agent`; only a
        `command` runs the file this matrix is reasoning about.
      * whether the file EXISTS. A registration pointing at a missing file cannot run.
      * whether the command actually INVOKES it. `echo "see gate_write_scope.py"` mentions it.

    The command must name the hook as an ARGUMENT, not merely contain the string, and the
    invocation must not swallow the exit code (`sh -c "python gate.py; exit 0"` can never block).
    """
    wired = {}
    if _hooks_disabled(repo_root):
        return wired
    hooks_dir = os.path.join(repo_root, ".claude", "hooks")
    for layer in _settings_layers(repo_root):
        # DEFENSIVELY, because this is the tool of last resort: three malformed shapes crashed it
        # outright -- a list-valued `hooks`, a non-string matcher going into a set, an int matcher
        # reaching `re.compile`. Doctor is run precisely when a kit update half-finished or
        # somebody hand-edited the file, so it is the one program that must not die on bad input.
        hooks = layer.get("hooks")
        if not isinstance(hooks, dict):
            continue
        for event, entries in hooks.items():
            for entry in entries if isinstance(entries, list) else []:
                if not isinstance(entry, dict):
                    continue
                matcher = entry.get("matcher")
                if not isinstance(matcher, (str, type(None))):
                    matcher = "<unusable-matcher>"     # hashable, and matches no tool
                for hook in entry.get("hooks") or []:
                    if not isinstance(hook, dict) or hook.get("type", "command") != "command":
                        continue
                    command = str(hook.get("command") or "")
                    if _swallows_exit_code(command):
                        continue
                    for name in _invoked_scripts(command):
                        if not os.path.isfile(os.path.join(hooks_dir, name)):
                            continue
                        wired.setdefault(name, {}).setdefault(event, set()).add(matcher)
    return wired


# A registration whose shell rewrites the gate's exit status enforces nothing: exit 2 is the only
# code Claude Code blocks on, so `python gate.py; exit 0` is a gate that always allows. Separators
# include newline and `&` — a wrapper written across two lines is the same command, and the first
# version of this pattern accepted both as enforcement. `:` is sh's no-op and exits 0 like `true`.
_SWALLOW_RX = re.compile(
    r"(?:[;&\n]|\|\||&&)\s*(?:exit\s+0|true|:)\s*(?:[;&\n\"']|$)")


def _swallows_exit_code(command: str) -> bool:
    """Does this command throw away the gate's exit status?

    Deliberately over-eager, and the direction is the point: a false positive reports a working
    gate as `unverified` and costs someone a look at their settings; a false negative reports a
    gate that can never block as enforcement. It is also quote-BLIND, so `echo "; exit 0"` counts
    — which is the same trade, and the alternative is a shell parser inside a report.
    """
    return bool(_SWALLOW_RX.search(command or ""))


# ONE SHELL WORD that ends in `.py`. The WORD -- not the run of non-blank characters -- is the
# unit, because a shell ends a word at whitespace or at a separator only while no quote is open: a
# quoted span is one word however many spaces it carries. Both cases stand as ONE sub-pattern
# rather than as two readers, and that is what closes the over-warning half of BUG-0173 --
# `python -B "C:/Offline Repos/p/.claude/hooks/gate_approval.py"` yielded nothing here while the
# very same registration minted.
# `tools/test_report.py::test_a_quoted_path_with_a_space_runs_and_a_named_missing_file_does_not`
_SCRIPT_WORD = r"""(?:"([^"\n]*\.py)"|'([^'\n]*\.py)'|([^\s"';|&]+\.py))"""


def _script_basename(raw) -> str:
    """The file name a matched `_SCRIPT_WORD` names -- quoting removed, separators normalised.

    Quoting is removed character-wise, the way a shell removes it, so `"a"/b.py` and `a/b.py` are
    one word to this reader.
    """
    return os.path.basename(_script_word(raw).replace("\\", "/"))


def _script_word(raw) -> str:
    """A matched `_SCRIPT_WORD` with its quoting removed and its path left alone."""
    return str(raw or "").replace('"', "").replace("'", "")


def _first_alternative(groups) -> str:
    """The one alternative of a `_SCRIPT_WORD` that matched; the other two are None by construction."""
    for one in groups:
        if one:
            return one
    return ""


def _invoked_scripts(command: str) -> list:
    """The base NAMES of the `.py` files this command runs -- `_invoked_script_words` decides."""
    return [_script_basename(word) for word in _invoked_script_words(command)]


def _invoked_script_words(command: str) -> list:
    """The `.py` WORDS this command RUNS, as opposed to merely mentions.

    THE WORD AND NOT THE BASE NAME, because two different questions are asked of the same match:
    the base name answers "which gate is this", and only the word answers "which file is this", so
    only the word can be asked whether that file is there (`_runs_no_file`, BUG-0173).

    The script must follow an INTERPRETER (or be the command word itself). Extracting every `.py`
    token counted `echo "see gate_dispatch.py for details"` as a registration of that gate — which
    is the same "it appears, therefore it enforces" reasoning the whole matrix exists to reject.

    A `.py` passed AS AN ARGUMENT to an already-invoked `.py` also runs. That is `_gate.py`, the
    launcher every V2 gate is now registered behind, and without this the whole matrix would read
    zero the moment the launcher shipped: doctor would see `_gate.py` registered and no gate
    anywhere. Written as the general relationship rather than as a special case for one filename —
    the previous version of this function collected findings for exactly as long as it enumerated
    shapes instead of stating what "runs" means.
    """
    words, names = [], []

    def remember(raw):
        base = _script_basename(raw)
        if base and base not in names:
            names.append(base)
            words.append(_script_word(raw))

    for match in re.finditer(
            r"(?:^|[;&|(]|\bsh\s+-c\s+[\"']?)\s*[\"']?"
            r"(?:(?:[^\s\"';|&]*[/\\])?(?:python[0-9.]*|py|pypy[0-9.]*)(?:\.exe)?[\"']?"
            r"(?:\s+-[^\s\"']+)*\s+" + _SCRIPT_WORD +
            r"|" + _SCRIPT_WORD + r")",
            command or "", re.IGNORECASE):
        remember(_first_alternative(match.groups()))
    # ...then follow the launcher chain: `A.py B.py` runs B as well, and `A.py B.py C.py` both.
    #
    # THE SECOND SCRIPT IS MATCHED IN A LOOKAHEAD, so consecutive pairs OVERLAP. Without it
    # `re.finditer` consumed `A.py B.py` whole and resumed after it, so the pair `B.py C.py` was
    # never seen and a three-link chain reported only its first two. That stopped being
    # hypothetical the day the kits registered their spawn gates as ONE chained command — office
    # runs four gates behind the launcher — and it would have read as `gate_dispatch` being
    # unregistered on PreToolUse in doctor's own capability matrix.
    for _pass in range(8):
        grew = False
        for match in re.finditer(
                _SCRIPT_WORD + r"[\"']?\s+(?=" + _SCRIPT_WORD + r")", command or ""):
            first = _script_basename(_first_alternative(match.groups()[:3]))
            second = _first_alternative(match.groups()[3:])
            if first in names and _script_basename(second) not in names:
                remember(second)
                grew = True
        if not grew:
            break
    return words


# THE ONE VARIABLE this reader can resolve without a shell, named ONCE and spelled by derivation:
# the provider substitutes the project directory itself, so its value is known here -- every other
# variable belongs to a shell state this process does not have. The three spellings below are the
# three shells' syntax for the SAME name and not three cases to keep in step.
_PROJECT_DIR_VARIABLE = "CLAUDE_PROJECT_DIR"
_PROJECT_DIR_RX = re.compile(r"\$\{?%s\}?|%%%s%%" % (_PROJECT_DIR_VARIABLE, _PROJECT_DIR_VARIABLE))


def _runs_no_file(command: str, repo_root: str, name: str) -> bool:
    """Does this command start `name` from a path that RESOLVES here and holds no file?

    The under-warning half of BUG-0173: a registration whose path resolves and whose file is not
    there starts nothing, and every reader of this module said it minted. Only a word this
    function can resolve WITHOUT a shell is judged; one that still carries a variable or a tilde
    after the project directory is substituted is left alone, because a wrong "the file is
    missing" suppresses a warning at a project that really mints -- the reassuring direction, and
    the one this module's own docstrings call as wrong as the alarming one.

    `tools/test_report.py::test_a_quoted_path_with_a_space_runs_and_a_named_missing_file_does_not`
    """
    located = []
    for word in _invoked_script_words(command):
        if _script_basename(word) != name:
            continue
        resolved = _PROJECT_DIR_RX.sub(repo_root.replace("\\", "/"), word)
        if "$" in resolved or "%" in resolved or "~" in resolved:
            continue                       # a shell's state decides this one, and we are not it
        located.append(os.path.isfile(os.path.join(repo_root, resolved)))
    return bool(located) and not any(located)


def _matches_tool(matcher, tools) -> bool:
    """Would this matcher fire for any of `tools`?

    `*`/empty means every tool. Otherwise Claude Code treats it as an unanchored regex, which is
    why `Edit|Write` matches `Edit` and nothing else here.
    """
    if matcher in (None, "", "*"):
        return True
    if not isinstance(matcher, str):
        return False          # a non-string matcher cannot fire; see the malformed-settings note
    # Claude Code matches a matcher made only of letters/digits/_/-/space/,/| EXACTLY, with `|` as
    # alternation. Treating every matcher as an unanchored regex made `"dit"` "cover" Edit and
    # `"Ag"` "cover" Agent -- registrations that fire for NOTHING, read as enforcement.
    if re.fullmatch(r"[\w\-, |]+", matcher):
        alternatives = {part.strip() for part in matcher.split("|") if part.strip()}
        return any(tool in alternatives for tool in tools)
    try:
        pattern = re.compile(matcher)
    except (re.error, TypeError):
        return False
    return any(pattern.search(tool) for tool in tools)


def _fires_for(wired: dict, name: str, event: str, tools) -> bool:
    """Is EVERY tool in the class covered by some matcher?

    `any` was the wrong quantifier and it re-created the defect the matcher check was added to
    close: `gate_dispatch` registered for `Task` alone read as a spawn veto while `Agent` spawns
    went unguarded, and `gate_write_scope` registered for `NotebookEdit` alone "protected" Edit,
    Write and MultiEdit. A class is covered when all of it is.
    """
    matchers = wired.get(name, {}).get(event)
    if not matchers:
        return False
    return all(any(_matches_tool(m, (tool,)) for m in matchers) for tool in tools)


def approval_mint_is_wired(repo_root: str) -> bool:
    """Can an ANSWER OF THE USER'S mint anything in this project?

    ITS OWN WALK AND NOT `_wired_hooks`, and that correction is the whole point of this function
    existing separately. `_wired_hooks` answers "could this registration BLOCK", which is the right
    question for the capability matrix and the wrong one here: a mint is a SIDE EFFECT -- the hook
    writes the APR file on its way out -- so it happens whatever the exit status is and wherever the
    file lies. Both differences are reachable and both were measured 2026-08-30 against the shipped
    hook, each with the item ending at `APPROVED`:
      * `python -B "$CLAUDE_PROJECT_DIR/.claude/hooks/gate_approval.py" ; exit 0` --
        `_swallows_exit_code` drops it, and it mints (hook rc 0);
      * the same hook registered from a directory that is not `.claude/hooks/` -- `_wired_hooks`
        requires the file THERE, and it mints.
    Read through `_wired_hooks` this function called both of them "nothing consumes the answer",
    which is an over-claim in the unsafe direction: it tells a role the project is weaker than it is.
    None of the three shipped kits is affected -- all three read True either way, measured.

    SO THE THREE DROPPED CONDITIONS ARE DELIBERATE. What decides is what really starts the hook:
    the kill switch, the event, the matcher, the hook TYPE, and whether the command RUNS the
    approval hook rather than merely naming it (`_invoked_scripts`) -- that list, and nothing more
    generous.

    BOTH DIRECTIONS THIS READER USED TO GET WRONG ARE CLOSED (BUG-0173, and the round that closed
    them is the one this sentence was written in): a quoted absolute path containing a SPACE is one
    word to `_invoked_script_words` and reads `True`, and a path that RESOLVES to a file which is
    not there reads `False` through `_runs_no_file` instead of claiming a mint nothing performs.
    What stays undecided is stated where it is decided: a word carrying a variable other than the
    project directory belongs to a shell state this process does not have, and `_runs_no_file`
    leaves it alone rather than guess -- the cost of each direction differs, an over-warning stalls
    a round that could have proceeded and an under-warning stays silent about one that cannot.

    WHAT IT DOES NOT ANSWER, said because the name invites the wider reading: whether `mint` is
    reachable at all. It is not the same question -- the hook can be run by hand with a payload
    assembled from the readable pending request, which `approvals._assert_minting_caller` records in
    its own docstring and the shipped `known_hole` tests assert. `False` here means "this project
    does not tell the provider to run the minting hook", never "nothing can mint".

    Measured in both directions by `test_report.test_the_mint_is_wired_by_the_registration_and_not
    _by_the_file_lying_there` and `test_report.test_a_registration_that_could_not_block_still_mints`.
    """
    if _hooks_disabled(repo_root):
        return False
    for layer in _settings_layers(repo_root):
        hooks = layer.get("hooks")
        if not isinstance(hooks, dict):
            continue
        entries = hooks.get(APPROVAL_MINT_EVENT)
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            if not _matches_tool(entry.get("matcher"), (APPROVAL_QUESTION_TOOL,)):
                continue
            for hook in entry.get("hooks") or []:
                if not isinstance(hook, dict) or hook.get("type", "command") != "command":
                    continue
                command = str(hook.get("command") or "")
                if APPROVAL_HOOK not in _invoked_scripts(command):
                    continue
                if _runs_no_file(command, repo_root, APPROVAL_HOOK):
                    continue
                return True
    return False


# The providers a project configures whose enforcement registrations `_wired_hooks` does NOT read.
#
# ONE ENTRY TODAY and it is not an enumeration of providers: the pair below says, per provider,
# which MARKER declares it configured and whether this reader opens its registrations at all.
# `_wired_hooks` reads the Claude layers, so `claude` answers True on the second element and every
# other entry answers False -- a provider added to the kits arrives here unmeasured, which is the
# fail-closed direction rule 1 of `capability_matrix` asks for.
# `tools/test_report.py::test_the_spawn_veto_is_not_claimed_for_a_provider_this_report_cannot_read`
PROVIDER_MARKERS = (
    ("claude", os.path.join(".claude", "settings.json"), True),
    ("codex", ".codex", False),
)


def _unmeasured_providers(repo_root: str) -> list:
    """Configured providers whose registrations this report cannot open -- see PROVIDER_MARKERS."""
    return sorted(name for name, marker, measured in PROVIDER_MARKERS
                  if not measured and os.path.exists(os.path.join(repo_root, marker)))


def capability_matrix(state: ProjectState, repo_root: str = None, enumeration=None):
    """(matrix, reasons) — every enforcement capability, and WHY each reads as it does.

    `enumeration` is the `(holes, source)` pair from `_known_hole_capabilities()`. It is
    passed in rather than fetched here so that ONE report describes ONE sidecar: read twice,
    a file that changed in between produced a `capabilities` block and a `known_holes` block
    about different data, with nothing to notice it.

    Two rules govern this function, and the first review of it found nine ways the first cut
    broke them:

    1. NEVER CLAIM MORE THAN IS MEASURED. `verified` means a check ran against this project and
       passed. Anything else -- a value that cannot be determined here, a condition that library
       code cannot establish, a file that is not where this code can see it -- is `unverified`.
       Spec II.8: "nicht Feststellbares bleibt `unverified`."
    2. AN OPEN HOLE OUTRANKS A GREEN CHECK. `tools/conftest.py` defines the `known_hole` marker's
       contract as "the named capability must be reported `unverified` while this test passes".
       A first cut reported such capabilities as `verified` with a `documented_residuals` note and
       called it "not an error" -- but the only residual any user decision covers is a USER who
       deliberately types the mint code, and the shipped `known_hole` tests assert AGENT-side
       forgeries (two authored files mint; rewriting `sys.modules` mints). Those are not residuals
       of a verified capability; they are the capability not being verified.
    """
    repo_root = repo_root or os.path.dirname(state.root)
    wired = _wired_hooks(repo_root)
    reasons = {}

    def verdict(name, ok, why):
        reasons[name] = why
        return "verified" if ok else "unverified"

    spawn = _fires_for(wired, "gate_dispatch.py", "PreToolUse", ("Agent", "Task"))
    # A CAPABILITY IS VERIFIED FOR THE PROJECT, NOT FOR ONE PROVIDER OF IT (BUG-0057).
    # `_wired_hooks` reads the three `.claude` layers and nothing else, so on a `claude+codex`
    # installation it answers about the Claude path alone -- and the line then said `verified`
    # with the reason "gate_dispatch fires on PreToolUse for Agent/Task" while the Codex path has
    # no spawn veto at all (spec II.13 calls that gap mechanically documented). Measured 2026-08-16
    # on a fresh claude+codex install: `capabilities.spawn_veto: verified`, and `spawn_veto` absent
    # from `enforcement_blockers`.
    # DERIVED, not a second provider list: whatever `_unmeasured_providers` finds configured beside
    # the layers this reader can open is a provider it has not measured, so rule 1 of this
    # function's own contract applies -- what cannot be determined stays `unverified`.
    unmeasured = _unmeasured_providers(repo_root)
    matrix = {"spawn_veto": verdict(
        "spawn_veto", spawn and not unmeasured,
        "gate_dispatch fires on PreToolUse for Agent/Task, the only event that can DENY a spawn"
        if spawn and not unmeasured else
        "gate_dispatch fires on PreToolUse for Agent/Task, but this project also configures %s, "
        "whose registrations this report cannot read — so the veto is measured for the Claude "
        "path only and the capability answers for the project (spec II.8/II.13)"
        % "/".join(unmeasured) if spawn else
        "no gate_dispatch registration fires on PreToolUse for Agent/Task — either it is not "
        "registered, its matcher excludes those tools, the file is missing, or hooks are disabled")}

    approval_pre = _fires_for(wired, APPROVAL_HOOK, APPROVAL_QUESTION_EVENT,
                              (APPROVAL_QUESTION_TOOL,))
    approval_post = _fires_for(wired, APPROVAL_HOOK, APPROVAL_MINT_EVENT,
                               (APPROVAL_QUESTION_TOOL,))
    scope_file = _fires_for(wired, "gate_write_scope.py", "PreToolUse",
                            ("Edit", "Write", "MultiEdit", "NotebookEdit"))
    scope_shell = _fires_for(wired, "gate_write_scope.py", "PreToolUse", ("Bash", "PowerShell"))

    matrix["state_write_protection.file"] = verdict(
        "state_write_protection.file", scope_file,
        "gate_write_scope fires on PreToolUse for the file tools" if scope_file else
        "no gate_write_scope registration fires for Edit/Write/MultiEdit")
    matrix["state_write_protection.shell"] = verdict(
        "state_write_protection.shell", scope_shell,
        "gate_write_scope fires on PreToolUse for Bash/PowerShell" if scope_shell else
        "shell writes to the state directory are not analysed — `sed -i`, `cp` and `>` bypass the "
        "file-tool gate entirely")

    # ...and provenance. Condition (ii) -- "mint() is callable ONLY from the PostToolUse hook" --
    # is one library code cannot establish about itself, which `approvals.mint` says in its own
    # docstring. A first cut "checked" it by asking whether `_assert_minting_caller` was a
    # callable attribute; deleting the CALL left that True. So it is reported as unmeasured
    # rather than assumed, and provenance cannot be verified here at all.
    matrix["approval_provenance"] = verdict(
        "approval_provenance", False,
        "the wiring conditions %s, but condition (ii) of the 2026-07-24 decision — that `mint()` "
        "is reachable ONLY from the PostToolUse hook — depends on the project's PERMISSION "
        "posture (whether an agent can run an arbitrary interpreter), which this report cannot "
        "read. Spec II.8: what cannot be determined stays `unverified`, and the mode stays "
        "`audited`."
        % ("hold" if (approval_pre and approval_post and scope_shell) else "do not hold"))

    trusted, trust_why = _hook_bundle_trust(repo_root)
    matrix["hook_trust"] = verdict("hook_trust", trusted, trust_why)

    # THE ENUMERATION WINS. Any capability a shipped `known_hole` test names is not verified,
    # whatever the wiring says -- that is the marker's contract, written before this matrix.
    holes, holes_source = enumeration if enumeration else _known_hole_capabilities()
    if not holes_source:
        # ...and NOT BEING ABLE TO READ IT wins too. This rule is the one that pulls a capability
        # down; if it could not run, then no green verdict below it was fully checked, and rule 1
        # applies. Getting this backwards would have been the worst possible incentive: deleting
        # `known_holes.json` -- one ordinary file removal -- would have SILENCED every hole and
        # turned the report greener than a correct install.
        why = ("the `known_hole` enumeration (kernel/known_holes.json) could not be read, so the "
               "rule that pulls capabilities down for asserted open paths did not run. Nothing "
               "below it can be reported as checked. Remedy: reinstall the kit, or regenerate the "
               "kit. Inside the harness checkout: `python tools/gen_known_holes.py`.")
        for name in matrix:
            if matrix[name] == "verified":
                matrix[name] = "unverified"
                reasons[name] = why
        return matrix, reasons
    for name in holes:
        if name in matrix and matrix[name] == "verified":
            matrix[name] = "unverified"
            reasons[name] = ("%s — but a `known_hole` test asserts an OPEN path for this "
                             "capability, and an asserted hole outranks a green wiring check "
                             "(tools/conftest.py)." % reasons.get(name, ""))
    return matrix, reasons


_UNMEASURABLE_HERE = {
    "approval_provenance":
        "condition (ii) of the 2026-07-24 decision — `mint()` reachable ONLY from the PostToolUse "
        "hook — is a property of the project's PERMISSION posture (can an agent run an arbitrary "
        "interpreter?), which no library can read about itself. It is not a wiring defect and no "
        "wiring change raises it.",
}


def _structural_blockers(matrix, reasons, holes):
    """{capability: why} for the required capabilities NO configuration could raise here.

    The difference this draws is the one a reader of `enforcement: audited` actually needs: a
    project that is misconfigured, versus one where the mode is a property of the harness. Both
    print the same word today, and only the first is worth fixing.

    Two structural sources, kept apart on purpose because they were masking each other:
      * a shipped `known_hole` test ASSERTS an open path (the enumeration; it outranks wiring),
      * a condition library code cannot establish about itself (_UNMEASURABLE_HERE).
    A capability that is merely unwired appears in `enforcement_blockers` and NOT here — that is
    the whole distinction. `holes` is None when the enumeration could not be read, which is itself
    structural: the rule that would pull capabilities down did not run.
    """
    if holes is None:
        return {name: "the `known_hole` enumeration could not be read, so no capability can be "
                      "reported as checked (see installation_errors)."
                for name in sorted(_REQUIRED_FOR_HARD)}
    out = {}
    for name in sorted(_REQUIRED_FOR_HARD):
        why = []
        if name in holes:
            why.append("a shipped `known_hole` test asserts an OPEN path for it, which outranks "
                       "any wiring check (tools/conftest.py); removing that test is the only "
                       "thing that changes this")
        if name in _UNMEASURABLE_HERE:
            why.append(_UNMEASURABLE_HERE[name])
        if why:
            out[name] = " Also: ".join(why)
    return out


def _kit_state_record(repo_root: str):
    """`.claude/kit_state.json` as a mapping, or None when there is nothing readable to use.

    ONE READER. The trust verdict and the raw measurement below ask different questions of this
    file and must not answer from different readings of it. There WAS a second reader,
    `_hook_bundle_trusted`, unreferenced from anywhere and answering the old way — `active` plus any
    recorded hash meant trusted, with no recomputation — so it returned True precisely where
    `_hook_bundle_trust` returns "the bundle changed since it was trusted". A dead duplicate of a
    security decision is a loaded gun for whoever calls the shorter name next; it is gone.
    """
    try:
        with open(os.path.join(repo_root, ".claude", "kit_state.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def bundle_measurement(repo_root: str):
    """(recorded, actual) hex hashes of the installed bundle — either may be None.

    THE OBSERVATION, SEPARATE FROM THE CAPABILITY, and the separation is the whole point. `hook_trust`
    is pulled to `unverified` by a shipped `known_hole` no matter what this pair says — correctly,
    because the recorder is forgeable by anyone who can run scripts. But collapsing the capability
    also collapsed the only machine-readable trace of the comparison: with `gate_dispatch` replaced
    by `sys.exit(0)`, every typed field of the report — capabilities, trust_status, known_holes,
    enforcement, blockers — came out byte-identical to a clean run (measured 2026-07-27; only the
    free-text `capability_reasons["hook_trust"]` still differed, and no consumer parses prose).
    A measurement with two outcomes had become a constant.

    So the honest answer is two answers: the CAPABILITY stays down because the mechanism that
    produces the record cannot be trusted, and the OBSERVATION is published on its own, whatever
    the capability says. Deliberately blind to `disableAllHooks` and to the state machine, which
    are reasons a matching bundle is not in EFFECT — not reasons it stopped matching.
    """
    data = _kit_state_record(repo_root)
    recorded = str((data or {}).get("hook_bundle_hash") or "") or None
    return recorded, _hook_bundle_hash(repo_root)


# The state names spec II.8 gives the update machine (docs/HARNESS_V2_SPEC.md, section II.8 — the
# chain plus the failure state). They are used for ONE thing: telling a name this harness knows
# from a name it does not. What a state COSTS is deliberately not read off this tuple — see
# `_kit_trust_reason`. Both ends of the tuple are measured in tools/test_report.py against the
# spec's own text: a name here that section II.8 does not carry, and a name it carries that is
# missing here. An enumeration whose completeness nothing measured is the defect this repo keeps
# meeting; the only thing that hangs off this one is one clarifying sentence, never the verdict.
SPEC_II8_STATES = ("update_available", "approved", "applying", "hooks_trust_required",
                   "restart_required", "active", "failed_rolled_back")


# WHAT A RECORD MAY PUT INTO THIS REPORT'S PROSE, as two shapes rather than as a filter against
# anything in particular. `.claude/kit_state.json` is data an agent can write with one ordinary
# command (see `_kernel.bundle_trust` on the re-blessing class), and every value echoed from it
# below lands in text a session READS AS INSTRUCTION. A value that does not have the shape its
# field promises is therefore described, never quoted: a name is an identifier, a hash is hex long
# enough for a 12-character prefix to identify it. Anything else — a space, a slash, a backtick, a
# newline, a novel — cannot reach the reader as words. Not a denylist: nothing here knows which
# tokens are dangerous, only which shapes are legitimate.
_NAME_SHAPE = re.compile(r"[A-Za-z0-9_]{1,40}\Z")
_HASH_SHAPE = re.compile(r"[0-9a-fA-F]{12,128}\Z")


def _short_hash(digest) -> str:
    """The first 12 characters of a hex digest — or a description of what was there instead."""
    if digest is None or digest == "":
        return "none"
    text = str(digest)
    if _HASH_SHAPE.match(text):
        return text[:12]
    return "a value that is not a hash (%d characters, not quoted)" % len(text)


def _state_label(state) -> str:
    """The record's `state` field, spelled so a reader can act on it — including when it is junk."""
    if isinstance(state, str) and _NAME_SHAPE.match(state):
        return "state %r" % state
    if state is None:
        return "no `state` field"
    if isinstance(state, str):
        return ("a `state` field that is not a name (%d characters, not quoted)" % len(state))
    return "a `state` field that is not a name (%s)" % type(state).__name__


def _trust_hook_registered(repo_root: str) -> bool:
    """Does THIS project's settings actually start the kits' SessionStart trust hook?

    The flip out of a bare-restart state has a runner or it does not, and the runner is named in
    `settings.json` — which lives OUTSIDE the hashed bundle, so a matching bundle hash says nothing
    about it. Without this, the reason below promised a flip that no session could perform: the
    user restarts, the record does not move, and the report gives no way to see why.

    `_wired_hooks` has already dropped every registration that could not fire (a non-`command`
    type, a missing file, a mention that is not an invocation, a swallowed exit code); SessionStart
    carries no tool matcher, so what is left to ask is whether one exists at all. A kit that
    renamed the hook file would read as "not registered" here and be sent to the scaffold — the
    conservative direction, and the one that ends a restart loop rather than starting one.
    """
    return bool(_wired_hooks(repo_root).get("kit_trust_state.py", {}).get("SessionStart"))


def _kit_trust_reason(data: dict, recorded, actual, registered: bool) -> str:
    """Why `hook_trust` is not verified for this record — with exactly ONE next action.

    Called only where the green condition in `_hook_bundle_trust` did NOT hold, so at least one of
    "the record says `active`" and "the two hashes are present and equal" is false here.
    `registered` is `_trust_hook_registered`'s answer and decides only the bare-restart branch,
    which is the one whose advice depends on a runner existing.

    THE NAME RECORDS A PAST FINDING; THE HASH COMPARISON IS THE FINDING NOW, and this answers from
    the comparison wherever the comparison can answer. Not a preference: the kits'
    `hooks/kit_trust_state.py` decides on the same comparison, so its `transition()` returns
    `active` for ANY non-active state whose recorded hash equals the measured one — `restart_required`
    and `failed_rolled_back` and a name nobody ever defined alike — and `hooks_trust_required` for any
    state whose hash differs (writing nothing where the record already says that). A reason keyed on
    the NAME therefore describes a machine that is not running, and BUG-0036 is what that costs: one
    sentence keyed on `!= "active"` told every such
    project that "a changed bundle needs /hooks confirmation and exactly one new session (spec II.8)",
    including the `restart_required` every fresh scaffold sits in, whose exit is one new session and
    nothing else. That is the `/hooks` rationalization the BUG-0017 arc removed from the entry window.

    `hooks_trust_required` is the one name that keeps its spec-II.8 `/hooks` wording whatever the
    comparison says, and for a reason the comparison cannot supply: the name records that a bundle
    this project never vouched for WAS measured. Putting the changed file back makes the hashes agree
    again; it does not make the change reviewed.
    """
    state = data.get("state")
    label = _state_label(state)
    if not recorded or actual is None:
        # Measured against the shipped hook: with no recorded hash `transition()` returns without
        # writing, so a new session is exactly the advice that changes nothing here.
        return ("the kit trust record carries %s and there is nothing to compare (recorded=%s, "
                "computed=%s). A record without a usable hash is one the SessionStart trust hook "
                "leaves untouched, so no number of new sessions moves it. ONE next action: re-run "
                "the kit's scaffold from the project root — its recorder (write_kit_state.py, "
                "beside the kits) is what writes that field. Nothing was compared here, so this "
                "verdict says nothing about whether the bundle changed."
                % (label, _short_hash(recorded), _short_hash(actual)))
    if recorded != actual:
        return ("the installed hooks hash to %s but the project recorded %s, and the record carries "
                "%s — the bundle changed since it was trusted, so what runs is not what this "
                "project vouched for. Spec II.8: a changed hook hash needs /hooks confirmation and "
                "then exactly one new session. ONE next action: open /hooks and review what changed "
                "in .claude/hooks and .claude/kernel; re-installing the kit is what records a "
                "reviewed bundle."
                % (_short_hash(actual), _short_hash(recorded), label))
    if state == "hooks_trust_required":
        seen = data.get("hook_bundle_hash_seen")
        return ("the installed bundle matches the recorded hash again (%s), but the record still "
                "carries %s: a bundle this project never vouched for was measured (%s) and was "
                "never reviewed. Spec II.8 asks for the /hooks confirmation for that change. ONE "
                "next action: open /hooks and review what had changed — the next session flips this "
                "record to `active` on the matching hash alone, so the review is the only step left "
                "that waits on a person."
                % (_short_hash(actual), label,
                   "seen: %s" % _short_hash(seen) if seen
                   else "the seen hash is not in the record"))
    unknown = ("" if isinstance(state, str) and state in SPEC_II8_STATES else
               " On top of that, the record's state is not one spec II.8 names, so the record "
               "itself is suspect; this verdict rests on the comparison above, not on the name.")
    # THE SENTENCE THIS BRANCH WRITES DOES NOT SPELL THE SLASH-COMMAND, not even to deny it: a
    # reader — human or agent — matches on the token, and the harness repo's own CLAUDE.md records
    # what a marker standing inside a sentence that denied it cost there. That is a property of the
    # LITERAL below and of nothing else; what a record can inject through the values interpolated
    # into it is bounded by `_NAME_SHAPE`/`_HASH_SHAPE` above, which is where that half is measured.
    if not registered:
        # An unregistered trust hook makes "start a new session" advice that cannot work: the flip
        # has no runner, and the record stays where it is however often the user restarts.
        return ("the installed bundle matches the hash the project recorded (%s), and the record "
                "carries %s — but this project's settings register no SessionStart run of the "
                "kits' trust hook, so no new session can move the record and restarting is a loop "
                "with no end. ONE next action: re-run the kit's scaffold from the project root — "
                "it installs the hooks together with the registration that starts them.%s"
                % (_short_hash(actual), label, unknown))
    return ("the installed bundle matches the hash the project recorded (%s), and the record "
            "carries %s — the bundle is the vouched-for one, and the record does not yet say these "
            "hooks RUN. ONE next action, and the whole exit: start ONE new session; the kits' "
            "SessionStart trust hook is registered here and flips the record to `active` by "
            "running, and a hook cannot run unless hooks run — which is the evidence this record "
            "is still missing. Nothing here waits on a review or a confirmation: no changed bundle "
            "was measured.%s"
            % (_short_hash(actual), label, unknown))


def _hook_bundle_trust(repo_root: str):
    """(bool, reason) — does the installed bundle match the hash the project recorded?

    A first cut returned True whenever `kit_state.json` said `active` and carried ANY hash, so a
    project with no hooks directory at all read "the installed hook bundle matches the trusted
    hash". Nothing was matched. Spec II.8 wants a CHANGED hash to force `/hooks` confirmation, so
    the hash has to be recomputed and compared — and since BUG-0036 the same comparison, not the
    state name, is what the REASON is built from as well (`_kit_trust_reason`). The green verdict is
    untouched by that: it still needs `active` plus two present, equal hashes, exactly as before.
    """
    # With the global kill switch on, the bundle's hash may well match — and saying "verified"
    # beside "no hook runs" invites exactly the wrong reading. A capability describes what is in
    # EFFECT, not what is on disk.
    if _hooks_disabled(repo_root):
        return False, ("`disableAllHooks` is set, so no hook runs at all — whatever the bundle "
                       "hashes to is not in effect")
    data = _kit_state_record(repo_root)
    if data is None:
        return False, "no readable .claude/kit_state.json, so there is no recorded hash to compare"
    # ONE condition for the green verdict, and the reason for every way of missing it comes from
    # one place. The four cases used to be four branches, and the state branch answered for three
    # of them at once (BUG-0036); a mismatch under `active` still answered without naming a next
    # action at all. Spec II.8 demands the single next action for the error state; the general form
    # — a kit update shows exactly one next step at any time — is an acceptance criterion of the
    # spec's E2E block ("E2E pro Kit"), not of II.8.
    recorded, actual = bundle_measurement(repo_root)
    if data.get("state") == "active" and recorded and actual and recorded == actual:
        return True, "the installed hook bundle hashes to the value the project recorded (%s)" % (
            _short_hash(actual))
    return False, _kit_trust_reason(data, recorded, actual, _trust_hook_registered(repo_root))


def _hook_bundle_hash(repo_root: str):
    """sha256 over the installed hook bundle — see `hashing.hook_bundle_hash` for THE definition.

    This used to be a second implementation (top-level `*.py`, name+content, no separators) of a
    concept `gen_provider_artifacts` already implemented differently. It therefore never produced
    the value the Codex trust binding recorded, and `hook_trust` compared two measurements of
    different things.
    """
    return hook_bundle_hash(os.path.join(repo_root, ".claude"))


def _mint_is_hook_only() -> bool:
    """Does `approvals.mint` still refuse every caller outside its recognised routes?

    A property of the SHIPPED code, not of configuration: `_assert_minting_caller` is the last
    check inside `mint`, and it is the whole reason a hand-written approval proves nothing.

    THE NAME IS OLDER THAN THE ANSWER: since FR-0083 there are two recognised routes -- the
    approval hook and `kernel.sdk_approval` -- so what this asks is that the check is still there,
    not that the hook is the only caller. It is also why the check this function performs (is the
    attribute callable) is NOT what `capability_matrix` reports provenance on: that verdict is
    `False` with a reason, see `approval_provenance` there.
    """
    try:
        from . import approvals
        return callable(getattr(approvals, "_assert_minting_caller", None))
    except Exception:  # noqa: BLE001
        return False


def installed_identity(state: ProjectState) -> dict:
    """What the INSTALLATION says about itself: kit, version, lead role, provider config.

    THE WIRING SPEC II.4 ASKS FOR, and it did not exist. `doctor` took `kit`/`kit_version` as
    parameters, `cli` passed neither, and `lead_role`/`provider_config` were hard-coded to
    "unknown" behind a comment promising that "phase-2 wiring fills these from the installed kit".
    Measured on a correctly installed office project: all four came back `unknown` while
    `.claude/kit_state.json` held `"kit": "office-team"` and `settings.json` held
    `agent: office-manager` two directories away. Spec II.4 lists these fields and allows
    `unknown` only for what cannot be determined -- these can.

    EVERY VALUE IS READ FROM THE INSTALLATION, never guessed: the kit name from
    `.claude/kit_state.json` (what the scaffold recorded), the version from `.claude/kit_version`
    (what the scaffold stamped), the lead role from `settings.json`'s `agent`, and the provider
    config from which generated artefacts exist. Anything unreadable stays `unknown`, which is the
    honest answer and the one the spec reserves for it.
    """
    claude_dir = os.path.join(os.path.dirname(state.root), ".claude")
    identity = {"kit": "unknown", "kit_version": "unknown", "kit_reason": "",
                "lead_role": "unknown", "provider_config": "unknown"}
    try:
        with open(os.path.join(claude_dir, "kit_state.json"), encoding="utf-8") as handle:
            recorded = json.load(handle)
        if isinstance(recorded, dict) and recorded.get("kit"):
            identity["kit"] = str(recorded["kit"])
    except Exception:
        pass
    try:
        with open(os.path.join(claude_dir, "kit_version"), encoding="utf-8-sig") as handle:
            for line in handle:
                if line.startswith("version:"):
                    identity["kit_version"] = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    try:
        with open(os.path.join(claude_dir, "settings.json"), encoding="utf-8") as handle:
            settings = json.load(handle)
        if isinstance(settings, dict) and settings.get("agent"):
            identity["lead_role"] = str(settings["agent"])
    except Exception:
        pass
    providers = [name for name, marker in (
        ("claude", os.path.join(claude_dir, "settings.json")),
        ("codex", os.path.join(os.path.dirname(state.root), ".codex")),
    ) if os.path.exists(marker)]
    if providers:
        identity["provider_config"] = "+".join(providers)
    if identity["kit"] == "unknown":
        # BUG-0029: WHY it is unknown, so a bare `unknown` beside a known `kit_version` does not read
        # as a defect. The kit NAME is recorded by the scaffold in `.claude/kit_state.json`;
        # `kit_version` is a date stamp plus a content hash (`tools/bump_kit_version.py`) and carries
        # no kit name, so a project that has a version but no `kit_state.json` -- a V1 or freshly
        # migrated project that has not been re-scaffolded -- cannot have its kit named from what is
        # on disk here. This is a determinable gap, not a determinable kit reported as unknown.
        identity["kit_reason"] = (
            "the kit name is recorded by the scaffold in .claude/kit_state.json and this project "
            "carries no readable `kit` there; kit_version names a date and a content hash, not a "
            "kit, so the kit cannot be derived from disk. Re-scaffold the kit, or pass --kit "
            "explicitly to a command that needs it (generate-session-brief).")
    return identity


def doctor(state: ProjectState, kit: str = None, kit_version: str = None) -> dict:
    # ARGUMENTS WIN, THE INSTALLATION FILLS THE REST. The two parameters stay because the
    # SessionStart path knows the kit it is about to record and should not have to read it back;
    # every other caller (`cli`) passes nothing and gets the installed answer instead of `unknown`.
    identity = installed_identity(state)
    report = {
        "generated_at": _now_iso(),
        "root": state.root,
        "kit": kit or identity["kit"],
        "kit_version": kit_version or identity["kit_version"],
        # BUG-0029: when the kit cannot be named, WHY -- a determinable gap, not a determinable kit
        # left as `unknown`. Empty once the kit IS named (an argument, or a recorded kit_state.json).
        "kit_reason": "" if (kit or identity["kit"]) != "unknown" else identity["kit_reason"],
        # defects in the INSTALLATION rather than in the project's state -- kept separate from
        # `validator.errors`, which callers gate on, because a damaged kit is no reason to refuse
        # the user's own well-formed items. Always present, so no consumer has to guess whether an
        # absent key means "clean" or "an older report".
        "installation_errors": [],
        # spec II.4: what the kernel cannot determine is reported as `unknown` -- and these two
        # CAN be determined, from `settings.json` and the generated provider artefacts
        # (`installed_identity`). They were pinned to "unknown" behind a comment promising a
        # wiring that was never built.
        "lead_role": identity["lead_role"],
        "provider_config": identity["provider_config"],
        # filled below from what was actually read -- reporting `unknown` here while
        # `hook_trust` said "the bundle matches the trusted hash" made one report contradict
        # itself in two lines.
        "hook_bundle_hash": None,
        # ...and, as a TYPED field rather than as prose inside a capability reason, the comparison
        # itself: what the project recorded, and whether the installed bundle still hashes to it.
        # `null` is "there was nothing to compare", which is a third answer and not a quiet `false`
        # -- see `bundle_measurement` for why this may not be folded back into `hook_trust`.
        "recorded_hook_bundle_hash": None,
        "bundle_matches_recorded": None,
        "trust_status": None,
        # spec II.4 names Spezialisten among doctor's fields; it was absent entirely, not even
        # as `unknown`.
        "specialists": "unknown",
        # filled below from what is actually WIRED
        "state_version": {
            "lock_schema": LOCK_SCHEMA_VERSION,
            "hash_schema": HASH_SCHEMA_VERSION,
        },
    }
    lock_path = state.lock.lock_path
    if os.path.exists(ext_path(lock_path)):
        try:
            payload = state._read_yaml(lock_path)
            report["lock"] = {
                "held_by_pid": payload.get("pid"),
                "age_seconds": round(max(0.0, time.time() - float(payload.get("acquired_at", 0))), 1),
                "ttl": payload.get("ttl"),
            }
        except Exception:
            report["lock"] = {"state": "unreadable (corrupt lockfile)"}
    else:
        report["lock"] = {"state": "free"}
    leases = []
    lease_dir = os.path.join(state.root, "tasks", "leases")
    if os.path.isdir(ext_path(lease_dir)):
        for name in sorted(os.listdir(ext_path(lease_dir))):
            if name.endswith(".lease.yaml"):
                try:
                    lease = state._read_yaml(os.path.join(lease_dir, name))
                    leases.append({
                        "task_id": lease.get("task_id"),
                        "agent_id": lease.get("agent_id"),
                        "expired": time.time() > float(lease.get("created_epoch", 0)) + float(lease.get("ttl", 0)),
                    })
                except Exception:
                    leases.append({"task_id": name, "state": "corrupt"})
    report["leases"] = leases
    # read-only scan WITHOUT taking the lock: doctor must work while a kernel
    # operation (or a stale holder) holds it -- diagnosis may see mid-write
    # snapshots, which is acceptable for a report that never writes state
    findings = validate_state(state, _locked=True)
    report["validator"] = {
        "errors": [f for f in findings if f["severity"] == "error"],
        "warnings": [f for f in findings if f["severity"] == "warning"],
    }
    # COVERAGE, NOT A VERDICT, and the tool of last resort is where it belongs: which files the
    # SR-0001 record scan could look at is a fact `validator.errors` cannot carry, because a file
    # nobody can make readable may not be an error.
    report["record_scan_coverage"] = record_scan_coverage(state)
    # ...and, for the same reason, what a delivery has already closed while the status field still
    # reads open (DEC-0051): a row whose route needs a mint the project cannot run is not something
    # `validator.warnings` may carry, because nothing a project does would clear it.
    report["delivery_closure"] = delivery_closure_rollup(state)
    report["stock_lies_upward"] = stock_rollup(state)
    repo_root = os.path.dirname(state.root)
    holes, holes_source = _known_hole_capabilities()
    matrix, reasons = capability_matrix(state, repo_root, (holes, holes_source))
    recorded_bundle, actual_bundle = bundle_measurement(repo_root)
    report["hook_bundle_hash"] = actual_bundle or "unknown"
    report["recorded_hook_bundle_hash"] = recorded_bundle
    report["bundle_matches_recorded"] = (
        None if recorded_bundle is None or actual_bundle is None
        else recorded_bundle == actual_bundle)
    if report["bundle_matches_recorded"] is False:
        # An INSTALLATION defect, not a state defect, so it goes where a damaged kit goes and not
        # into `validator.errors` that callers gate on. It has to be raised somewhere typed: the
        # capability it belongs to is held at `unverified` by a `known_hole` in every case, so
        # without this line the difference between a clean project and one whose enforcement code
        # was rewritten after it was trusted appears in no field a consumer can branch on.
        report["installation_errors"].append(_finding(
            "error", ".claude/kit_state.json",
            "the installed enforcement bundle hashes to %s but this project recorded %s — it "
            "changed after trust was recorded, and every gate now runs code the project never "
            "confirmed." % (actual_bundle[:12], recorded_bundle[:12]),
            "review the difference in /hooks, then ask the user to re-run the team scaffold, "
            "which reinstalls the kit's own files and records the bundle it installed. A session "
            "cannot run it itself: `gate_write_scope` refuses a write-capable command line that "
            "names the enforcement layer, and starting a script is one."))
    report["trust_status"] = matrix.get("hook_trust", "unknown")
    # THE WALLS. A typed field rather than prose, because "which files can block this project and
    # who is allowed to write them" is something a dashboard and a session brief both branch on;
    # see `gated_documents` for what it does and does not claim.
    report["gated_documents"] = gated_documents(state, repo_root)
    report["specialists"] = _installed_specialists(repo_root)
    report["hooks_disabled"] = _hooks_disabled(repo_root)
    report["capabilities"] = matrix
    report["capability_reasons"] = reasons
    # spec II.8: `hard` only when every necessary capability is verified, otherwise `audited`.
    # The SPLIT must never RAISE the mode -- before it, `state_write_protection` was one value,
    # and splitting a single "verified" into two would have been a way to keep the verdict while
    # only half the door was locked. Both halves are required, so the split can only ever lower.
    unmet = sorted(name for name in _REQUIRED_FOR_HARD if matrix.get(name) != "verified")
    report["enforcement"] = "hard" if not unmet else "audited"
    report["enforcement_blockers"] = unmet
    # ...and, separately, THE CEILING: the best mode this installation could reach if every
    # wiring problem were fixed. Without it the report answers "are you `hard`?" and never "could
    # you be?", and a reader chasing `enforcement: audited` cannot tell a misconfigured project
    # from one where no configuration would help. Both are `audited`; only one is worth an
    # afternoon.
    #
    # The distinction is also what keeps three overlapping reasons from masking each other. Every
    # required capability here is currently held down by TWO independent mechanisms, and a review
    # showed the consequence: reverting `approval_provenance` to the naive wiring check it started
    # as — the round-1 defect — passed the entire suite, because the enumeration pulled it down
    # anyway. Naming the structural reason on its own line makes the overlap visible instead of
    # convenient, and `test_each_mechanism_holds_the_ceiling_on_its_own` kills each mutant apart.
    ceiling_reasons = _structural_blockers(matrix, reasons, holes if holes_source else None)
    report["enforcement_ceiling"] = "audited" if ceiling_reasons else "hard"
    report["enforcement_ceiling_reasons"] = ceiling_reasons
    # ...and the KNOWN HOLES the shipped suite enumerates, cross-checked against the matrix.
    #
    #   known_holes == null -- the enumeration could not be READ. `[]` would say the opposite
    #     ("looked, found none"), and the difference decides whether the matrix above means
    #     anything. Kept as two fields rather than one sentinel value so a consumer that only
    #     iterates the list cannot mistake "could not look" for "nothing to see".
    #   unknown_hole_capabilities -- a marker naming a capability that does not exist. That is a
    #     real defect: the enumeration and the matrix have drifted, and the cross-check for that
    #     capability can never fire again. It happened immediately: splitting
    #     `state_write_protection` left two markers pointing at a name the matrix no longer has.
    #
    # There is deliberately no `documented_residuals`. It existed while a verified capability
    # could carry an asserted hole beside it; rule 2 ended that, so the field could only ever be
    # empty -- and an always-empty "no residuals" line reads as reassurance.
    report["environment_notes"] = _environment_notes(repo_root)
    report["known_holes"] = sorted(holes) if holes_source else None
    report["known_holes_source"] = holes_source
    # WHICH kernel answered. Two now legitimately exist on one machine — `<repo>/.claude/kernel`
    # installed by the scaffold and `~/.claude/team-kits/kernel` from the installer — and the
    # capability matrix measures the PROJECT'S bundle while this enumeration comes from whichever
    # package is executing. A doctor run from the global staging over a project with a stale
    # `.claude/kernel` describes two different kernels in one report and says so nowhere.
    report["kernel_path"] = os.path.dirname(os.path.abspath(__file__))
    project_kernel = os.path.join(repo_root, ".claude", "kernel")
    foreign = False
    if os.path.isdir(project_kernel):
        try:
            foreign = not os.path.samefile(project_kernel, report["kernel_path"])
        except OSError:
            foreign = True
    if foreign:
        report["environment_notes"].append(
            "this report was produced by the kernel at %s, but the project installed its own at "
            "%s — the capability matrix measures the project's bundle while the `known_hole` "
            "enumeration comes from the running package. Remedy: run `python scripts/harness.py doctor` from the "
            "project's kernel, or re-run the scaffold so the two agree."
            % (report["kernel_path"], project_kernel))
    report["unknown_hole_capabilities"] = sorted(
        name for name in holes if name not in matrix)
    if report["unknown_hole_capabilities"]:
        # Called a real defect two comments up, and it has to BE one: a marker naming a
        # capability the matrix does not have is a cross-check that can never fire again,
        # and it was QUIETER than a missing sidecar until this finding existed.
        report["installation_errors"].append(_finding(
            "error", "kernel/known_holes.json",
            "the enumeration names %s, which is not a capability this doctor knows — the cross-check for it can never fire, so whatever hole that test asserts is invisible here."
            % ", ".join(report["unknown_hole_capabilities"]),
            "rename the marker to a capability in `report.CAPABILITIES`, or add the capability."))
    if not holes_source:
        # Loud, and deliberately NOT in `validator.errors`. That list is findings about the
        # PROJECT'S STATE, which callers gate on; a damaged installation is not a reason to refuse
        # the user's own well-formed items. It is a reason to distrust the matrix above — which is
        # what this field says, in the one place a reader cannot page past.
        report["installation_errors"].append(_finding(
            "error", "kernel/known_holes.json",
            "the `known_hole` enumeration is missing or unreadable, so doctor cannot report any "
            "capability as verified — the whole matrix above is `unverified` for that reason "
            "alone, and the mode is `audited`.",
            "reinstall the kit (a project has no `tools/`; inside the harness checkout, "
            "`python tools/gen_known_holes.py` regenerates it)."))
    index_path = state.generated_path("index.yaml")
    report["index_present"] = os.path.exists(ext_path(index_path))
    return report


def _environment_notes(repo_root: str) -> list:
    """Environment facts that WEAKEN a capability without falsifying it.

    Both of these came out of phase-2 reviews and belong here rather than in a gate:

      * Python < 3.11 has no `-P`, so the office ledger validator runs with the script directory
        on `sys.path` and a `scripts/csv.py` could shadow a stdlib module it imports. The gate
        omits the flag rather than pretending; the honest place to say so is this report.
      * an interpreter INSIDE the repo (`.venv/`) is one an agent can write. A gate cannot check
        that meaningfully -- it would execute on the very interpreter it distrusts -- so it is
        reported instead of guarded, which is where a reviewer put it.
    """
    notes = []
    if sys.version_info < (3, 11):
        notes.append(
            "python %d.%d has no `-P`: the ledger validator runs with its script directory on "
            "sys.path, so a file placed in `scripts/` can shadow a stdlib module it imports. "
            "Remedy: run the project on 3.11+." % sys.version_info[:2])
    # The matrix describes ONE provider surface: `.claude/settings.json` and the layers Claude
    # Code merges. A project that also runs Codex enforces through `.codex/hooks.json`, generated
    # from the same source but a separate file with its own event set and its own trust binding.
    # Reporting a single matrix over a two-provider project is not wrong so much as narrower than
    # it looks, and spec II.8 asks for the mode of the INSTALLATION. Named here rather than
    # silently, until the matrix reads both surfaces.
    codex = os.path.join(repo_root, ".codex", "hooks.json")
    if os.path.isfile(codex):
        notes.append(
            "this project also has a Codex surface (.codex/hooks.json) and the capability matrix "
            "above describes the CLAUDE one only — a gate can be registered for one provider and "
            "not the other. Remedy: re-run the scaffold, which generates both from the same "
            "settings, and read the Codex bundle-trust line in /hooks separately.")
    try:
        executable = os.path.realpath(sys.executable)
        inside = os.path.realpath(repo_root)
        if executable.startswith(inside + os.sep):
            notes.append(
                "the interpreter running the hooks lives INSIDE the repo (%s), and an agent can "
                "write there. No gate can check this credibly -- it would run on the interpreter "
                "it distrusts. Remedy: run the harness on an interpreter outside the project."
                % os.path.relpath(executable, inside))
    except (OSError, ValueError):
        pass
    return notes


# The log `_kernel.block` appends one JSON object per refusal to, relative to the STATE root --
# the same file `gate_memory_complete.repeat_count` reads for its escalation counter. Reading the
# recorder's own output is the only way this report can say anything about what a gate DID.
_AUDIT_LOG = os.path.join(".audit", "hook_events.jsonl")


def _recorded_refusals(state: ProjectState) -> dict:
    """{hook name: how often it recorded a block} -- read from the state's own audit log."""
    counts = {}
    try:
        with open(ext_path(os.path.join(state.root, _AUDIT_LOG)),
                  encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:      # a truncated last line is not a data point
                    continue
                if isinstance(entry, dict) and entry.get("event") == "block":
                    hook = str(entry.get("hook") or "")
                    counts[hook] = counts.get(hook, 0) + 1
    except OSError:
        pass
    return counts


def gated_documents(state: ProjectState, repo_root: str) -> list:
    """The WALLS this installation stands on -- one entry per gated, writer-less kit document.

    WHY DOCTOR SAYS THIS AT ALL. A project can stand in a state where a registered gate refuses
    every merge (or every filing) over the content of a file that no `harness.py` command can
    write and no tool write reaches. Measured 2026-08-03, before this function existed: `grep -c
    "masterplan\\|filing_plan\\|project_config" kernel/report.py` was 0, so the tool whose job is
    to report the state was silent about the one state a session cannot work its way out of.

    WHAT IS CLAIMED, and it is exactly what `layout.gated_documents` derived: this file has no
    kernel writer, and a registered refusal-capable hook of THIS installation addresses it. Plus
    one measurement of what that hook DID -- the blocks it recorded in the project's own audit log.

    WHAT IS DELIBERATELY NOT CLAIMED: whether the document is still unfilled. That is the gate's
    own condition (`gate_filing.rules`, `gate_memory_complete.config_unfilled` + its template
    marker), and re-deriving it here would be a second implementation of a rule that already runs
    -- the shape that keeps producing the next defect in this repo. The gate is asked for its own
    verdict where asking it is safe, which is the hook side: `_kernel.unfilled_gated_documents`,
    read at SessionStart by `session_status`. Doctor cannot import a kit hook without installing
    `_kernel`'s exit-2 excepthook into its own process, and doctor is the tool of last resort.
    """
    from . import layout                # lazy: keeps the package's import graph a tree

    try:
        walls = layout.gated_documents(repo_root, state.root)
    except Exception:  # noqa: BLE001 -- a report that cannot derive this still owes the rest
        return []
    refusals = _recorded_refusals(state)
    entries = []
    for rel, who in sorted(walls.items()):
        # ASKED, NOT ASSERTED. This field was the constant `None` for a round after `add-filing-rule`
        # shipped, beside a note that said no command writes such a file -- so the one tool whose job
        # is to report the state reported a dead end the harness had already left (BUG-0041's shape,
        # for the very document FR-0049 step 5 serves). `layout.partial_writers` is the same
        # derivation `gate_write_scope` and the SessionStart briefing ask, so all three move together.
        # WITH THE STATE ROOT, because a writer that owns no single named file can only answer per
        # PROJECT: `apply-proposal` writes a document it can compare and refuses one it cannot, and
        # that is a fact about the file on disk. Asked without it, such a route is left out, and a
        # report that hid a route the harness has is this field's own measured defect.
        writers = list(layout.partial_writers(rel, state.root))
        entries.append({
            "path": rel,
            "gate": who["hook"],
            "kernel_writer": writers or None,
            # per GATE, not per document: one refusal can name several of them, and the audit log
            # records the hook, not the finding. Named that way so no consumer reads it as "this
            # file was refused N times".
            "gate_refusals_recorded": refusals.get(who["audit_name"], 0),
            "note": (
                "%s is registered, can refuse an operation, and addresses this file. The kernel "
                "has no path builder that can name it, so no `python scripts/harness.py` command "
                "creates it: the session that can do that is the one running BEFORE the kit is "
                "installed. %s Whether it is currently unfilled is that gate's own verdict and is "
                "not re-derived here -- the SessionStart briefing asks the gate for it."
                % (who["audit_name"],
                   "Nothing WRITES it either, so filling it is the user's, in an editor outside "
                   "the session." if not writers else
                   "WHAT CAN BE WRITTEN INTO IT: %s -- each on a user-minted approval; anything "
                   "those commands do not cover is the user's, in an editor outside the session."
                   % ", ".join("`python scripts/harness.py %s` writes %s"
                               % (entry["command"], entry["field"]) for entry in writers))),
        })
    return entries


def _installed_specialists(repo_root: str) -> list:
    """The specialist agents actually installed — spec II.4 names them among doctor's fields."""
    agents = os.path.join(repo_root, ".claude", "agents")
    try:
        return sorted(n[:-3] for n in os.listdir(agents) if n.endswith(".md"))
    except OSError:
        return []


def _known_hole_capabilities():
    """(capabilities, source) — what a shipped `known_hole` test says is NOT closed.

    `source` is "sidecar" when the generated enumeration was read, and None when it could not be.
    THAT DISTINCTION IS THE POINT. A first cut regex-scanned the harness's own test files, which
    do not exist in a scaffolded project — so it returned `[]` there, and `[]` reads as an
    affirmative "no known holes" rather than "could not look". Since the enumeration is what
    forces a capability down (rule 2 in `capability_matrix`), being unable to read it silently
    switched the governing rule off in every environment except the one the tests run in, and one
    unchanged project got different verdicts depending on where the kernel package sat.

    The sidecar (`kernel/known_holes.json`, generated by `tools/gen_known_holes.py` from pytest's
    own marker collection) travels with the kernel.

    IT IS CHECKED AGAINST A DIGEST HELD IN CODE. Without it the two tampers had opposite prices:
    DELETING the file cost every capability (the branch above), while writing
    `{"capabilities": {}}` over it silenced every asserted hole for free and turned
    `state_write_protection.shell` green — the cheapest edit was the profitable one.

    WHAT THE DIGEST DOES AND DOES NOT BUY, stated precisely because the first version of this
    comment overclaimed it. It raises the price of a SILENT edit from one file to two, and it
    catches every accidental deviation: a stale sidecar after a new marker, a BOM from a Windows
    redirect, a truncated write, a hand-fix someone meant to regenerate. It does NOT stop someone
    who edits both files: they sit in one directory behind one guard. The cost that does not
    depend on the attacker's diligence comes from elsewhere — both files are inside
    `hashing.BUNDLE_SUBTREES`, so any edit changes the enforcement bundle's hash and drops
    `hook_trust` to `unverified` at the next session start. In the harness checkout, where
    `team-kits/kernel` sits under no `.claude`, even that does not apply; there the pin is CI.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_holes.json")
    try:
        with open(path, encoding="utf-8") as handle:
            payload = handle.read()
    except OSError:
        return [], None
    try:
        from .known_holes_digest import KNOWN_HOLES_SHA256
    except Exception:  # noqa: BLE001
        # NOT just ImportError. A module truncated mid-write raises SyntaxError, and that is the
        # very "half-finished kit update" this whole layer exists for -- uncaught it propagated
        # out of doctor() and produced a traceback and ZERO report, exactly when the report is
        # the thing someone needs.
        return [], None
    if hashlib.sha256(payload.encode("utf-8")).hexdigest() != KNOWN_HOLES_SHA256:
        return [], None
    try:
        data = json.loads(payload)
    except ValueError:
        return [], None
    capabilities = data.get("capabilities") if isinstance(data, dict) else None
    if not isinstance(capabilities, dict):
        return [], None
    return sorted(capabilities), "sidecar"

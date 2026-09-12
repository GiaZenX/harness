#!/usr/bin/env python3
"""
Shared helper: THE RECURRING AUDIT RUN, as a duty rather than as an automation (FR-0038).

One file, mirrored byte-identical in all three kits -- which is the mirror rule of this repo and
is held by `tools/test_hooks.py::test_shared_kit_files_identical` at both ends, not by this
sentence. It is here for the reason `_audit.py` next to it is: what it answers is not an office
question. Every kit ships a `project-auditor`, every kit's
`notify_agent_events` writes the run record this module reads, and every kit therefore owes the
same reminder — so a copy that lived in one kit would have left the other two with a
role nobody is ever reminded to run. THE CADENCE ITSELF IS NOT CLAIMED FOR ANY OTHER FILE HERE:
it stands in `audit_period_id` below and nowhere else, and that no role text and no constitution
states it a second time is `tools/test_parallel_streams.py::
test_no_text_that_describes_the_audited_role_states_the_cadence_the_code_owns`. Until 2026-09-12
this paragraph stated a rhythm for all three constitutions that none of them states (`BUG-0220`); a
sentence about another file that nothing reads is exactly the claim that rots, and `tools/test_parallel_streams.py::
test_the_shipped_routine_module_claims_no_cadence_for_a_text_it_does_not_own` now reads this one. Measured before the move: FR-0038 was delivered in 1 of 3 kits
while nothing about it was office-specific (`tools/test_routine_feed.py::
test_the_routine_notice_appears_and_clears_in_every_kit_that_ships_it`).

THE HOOK REPORTS, THE PM SPAWNS. Nothing here starts a model process and nothing here may: a
process a hook starts is an execution layer outside what the provider reads as the enforcement
layer, which is the whole of `DEC-0028`. So this module names a run that is owed and stops, and
`tools/test_routine_feed.py::test_the_routine_module_starts_no_process_at_all` reads that off the
parse tree.

THE RUN RECORD IS DERIVED, NOT WRITTEN A SECOND TIME. `notify_agent_events` already appends every
subagent stop to the kit's own event log; `last_run` reads it. What that buys is that no new hook
has to be registered; what it costs is written down as `H112` in `docs/POST_V2_WISHLIST.md` and is
not repeated here — a rotated log reads as "never ran" (the safe direction), and a run that GAVE UP
counts as a run (the unsafe one).

TWO CALLERS, ON PURPOSE. A kit with a duty register calls `routine_duties` as one feed among
several, so the manager meets one paragraph instead of five notices; a kit without one calls
`notice`, which is the same answer as a sentence. Both directions are measured, and that the office
briefing names the run exactly ONCE is its own assertion
(`tools/test_routine_feed.py::test_the_office_briefing_names_the_routine_exactly_once`).
"""
import datetime
import json
import os
import sys


# NO BYTECODE FROM A HOOK RUN, for the reason `_gate.py` states at length: this file lives in the
# hashed enforcement bundle, so caching it would change the bundle by being run.
sys.dont_write_bytecode = True

# THE SIBLING THIS MODULE REACHES IS ITS OWN NEIGHBOUR (`_audit`), and it puts its directory in
# front itself rather than relying on the hook that imported it. Without it the module is importable
# only from inside a hook process, and every measurement of it would have to be a measurement of the
# caller.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE_DIRNAME = "project_memory"

# THE ROLE THIS KIT'S RECURRING AUDIT RUNS AS. It is named here rather than derived: this notice
# fires BEFORE any routine approval exists in a fresh project (the first session start owes the
# first run), so a module that read the role off an approval would have nothing to read exactly
# when it has to speak. Since PR-0011 AC-8 the entry point can produce the approval
# (`request-approval routine <ROOT> --role ... --expires-in-days ...`); this constant is what
# the notice proposes that line with.
# `tools/test_routine_feed.py::test_the_audited_role_is_a_role_every_kit_ships` keeps this name from
# pointing at an agent that no longer exists, in all three kits at once.
# THE OTHER DIRECTION IS UNCOVERED and stays that way here: a SECOND auditing role appearing beside
# this one would go unnoticed, because "is this role an auditor" is not a property any shipped file
# carries — it is prose in a role text. Deriving it would mean inventing that property.
AUDIT_ROLE = "project-auditor"
# The event `notify_agent_events` writes when a subagent finishes, and the field it puts the role in.
# Spelled here because that hook builds its JSON inline rather than through `_audit.record_event`;
# `tools/test_routine_feed.py::test_the_routine_reads_the_run_record_the_shipped_hook_really_writes`
# runs that hook as a process, once per kit, and reads the result back through this module, so a
# rename there turns red instead of making this feed silently blind.
RUN_EVENT = "subagent_stop"
RUN_EVENT_FIELD = "event"
RUN_ROLE_FIELD = "reason"
RUN_TIME_FIELD = "ts"
RUN_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


def duty(what, due, source):
    """One dated obligation, in the shape every feed of every kit reports.

    It lives here rather than beside the office register because this module is the one both kinds
    of caller share, and a second definition of the same three keys is how the two wordings of the
    old hand-written nags drifted apart.
    """
    return {"what": what, "due": due, "source": source}


def audit_period_id(day):
    """The period one audit run covers, as the id a run is compared against (FR-0038).

    An ISO week: the auditor's cadence is weekly, so "has it run in this period" is exactly "is
    there a run carrying this week id" — which is the double-run guard FR-0038 asks for, without
    date arithmetic a run late on a Sunday would fall out of. Both directions of that guard are
    `tools/test_routine_feed.py::test_a_run_in_an_earlier_week_leaves_the_routine_due`, and the
    boundary itself is
    `tools/test_routine_feed.py::test_the_routine_is_due_again_on_the_monday_after_a_run`.
    """
    year, week, _weekday = day.isocalendar()[:3]
    return "%04d-W%02d" % (year, week)


def last_run(root, role):
    """(timestamp, unreadable-reason) of the last time a subagent of `role` finished HERE.

    The record is exactly as durable as the event log: `_audit` rotates it at `ROTATE_BYTES`, so a
    run older than the live generation reads as NO run and the routine is reported due. Nagging is
    the safe direction for a reminder that proposes, and
    `tools/test_routine_feed.py::test_a_rotated_event_log_makes_the_routine_read_as_due_rather_than_as_run`
    measures it.
    """
    import _audit  # noqa: PLC0415 — lazy, so this module imports standalone
    path = os.path.join(root, STATE_DIRNAME, ".audit", _audit.LOG_NAME)
    if not os.path.isfile(path):
        return None, None
    try:
        if os.path.getsize(path) > _audit.ROTATE_BYTES:
            return None, ("%s is larger than the size it rotates at, so it was not read here"
                          % os.path.relpath(path, root).replace(os.sep, "/"))
        newest = None
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict):
                    continue
                if record.get(RUN_EVENT_FIELD) != RUN_EVENT:
                    continue
                if str(record.get(RUN_ROLE_FIELD) or "").strip() != role:
                    continue
                try:
                    when = datetime.datetime.strptime(
                        str(record.get(RUN_TIME_FIELD) or ""), RUN_TIME_FORMAT)
                except ValueError:
                    continue
                if newest is None or when > newest:
                    newest = when
        return newest, None
    except OSError as exc:
        return None, ("the event log could not be read here (%s), so when the %s last ran is unknown"
                      % (exc.__class__.__name__, role))


def routine_duties(root, today):
    """(duties, unreadable) — the recurring audit run, in the shape a duty register consumes.

    Off in a directory that is not a project at all: without a state directory there is no project
    to audit and no log to read, and a reminder in an arbitrary folder would be noise
    (`tools/test_routine_feed.py::test_a_directory_that_is_not_a_project_gets_no_routine_notice`).
    """
    duties, unreadable = [], []
    if not os.path.isdir(os.path.join(root, STATE_DIRNAME)):
        return duties, unreadable
    when, reason = last_run(root, AUDIT_ROLE)
    if reason:
        unreadable.append(reason)
    period = audit_period_id(today)
    if when is not None and audit_period_id(when.date()) == period:
        return duties, unreadable
    due = today - datetime.timedelta(days=today.isocalendar()[2] - 1)
    duties.append(duty(
        "the %s has not run in %s (last run in this project's event log: %s) — propose it to the "
        "user and spawn it yourself on its READ-ONLY route: `python scripts/harness.py "
        "request-approval routine <ROOT_ID> --role %s --scope <read scope> --trigger <when> "
        "--cadence <how often> --expires-in-days <n>` (relay the question verbatim; the user answers, "
        "once per term), then `create-task --type analysis --assigned-role %s --read-only ...`, "
        "`transition <TSK> READY`, `dispatch <TSK>`; the report lands as items through the kernel. "
        "No hook starts a run"
        % (AUDIT_ROLE, period,
           when.strftime(RUN_TIME_FORMAT) if when is not None else "none", AUDIT_ROLE, AUDIT_ROLE),
        due, "%s/.audit run records" % STATE_DIRNAME))
    return duties, unreadable


def notice(root, today=None):
    """The session-start sentence for a kit that has no duty register, or "" when nothing is owed.

    Same answer as `routine_duties`, worded for a caller that prints it directly. A kit WITH a
    register must not call this as well — it would name the same run twice, which is what
    `tools/test_routine_feed.py::test_the_office_briefing_names_the_routine_exactly_once` pins.
    """
    today = today or datetime.date.today()
    duties, unreadable = routine_duties(root, today)
    parts = []
    if duties:
        parts.append(
            "ROUTINE DUE (%s): %s. This notice PROPOSES — no hook starts a run, and the decision is "
            "the user's." % (duties[0]["due"].isoformat(), duties[0]["what"]))
    if unreadable:
        parts.append(
            "ROUTINE RECORD INCOMPLETE: %s. Do not read the absence of a reminder as a run that "
            "happened." % "; ".join(unreadable))
    return " ".join(parts)

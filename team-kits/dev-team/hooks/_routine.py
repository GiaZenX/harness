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
not repeated here — a rotated log reads as "never ran", which is the safe direction. The UNSAFE
direction that stood beside it — a stop that gave up on its output contract counting as a run —
is closed: `last_run` pairs each stop with the give-up record `gate_subagent_output` writes for the
same stop (BUG-0196,
`tools/test_routine_feed.py::test_a_run_that_gave_up_on_its_output_contract_is_not_a_run`).

TWO CALLERS, ON PURPOSE. A kit with a duty register calls `routine_duties` as one feed among
several, so the manager meets one paragraph instead of five notices; a kit without one calls
`notice`, which is the same answer as a sentence. Both directions are measured, and that the office
briefing names the run exactly ONCE is its own assertion
(`tools/test_routine_feed.py::test_the_office_briefing_names_the_routine_exactly_once`).
"""
import datetime
import json
import math
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
# THE RECORD THAT SAYS A STOP DELIVERED NOTHING. `gate_subagent_output` writes it on the same
# SubagentStop the event above records, and it opens its reason with the agent type -- which is why
# one reader answers "which role is this record about" for both kinds (`_role_of`). Until BUG-0196
# this module read only the stop, so a run that gave up on its output contract counted as a run and
# suppressed the weekly reminder for a report nobody ever received: the unsafe direction of the two
# `H112` names. `tools/test_routine_feed.py::test_a_run_that_gave_up_on_its_output_contract_is_not_a_run`
# runs both shipped hooks as processes and reads the answer back through here.
GAVE_UP_EVENT = "gave_up"


def duty(what, due, source, period=""):
    """One dated obligation, in the shape every feed of every kit reports.

    It lives here rather than beside the office register because this module is the one both kinds
    of caller share, and a second definition of the same four keys is how the two wordings of the
    old hand-written nags drifted apart.

    `period` IS WHAT MAKES THIS DUTY THIS ONE within its feed and source, and it is the third fact
    the done record is keyed on (`kernel.duties.duty_key`, BUG-0197 / H113): a filing period, the
    oldest expired archive year, an invoice number. It has to stay the SAME FROM DAY TO DAY -- a
    part that moves with the clock ("5 days overdue") would give the duty a new key every morning
    and make every done record dead by noon. A feed that passes none gets `""`, and its duties are
    then keyed on feed+source alone: that is correct for a feed with ONE duty per source and wrong
    for one with many, which is why every shipped feed passes one.
    `tools/test_office_duties.py::test_every_shipped_feed_gives_its_duties_a_key_that_survives_a_day`
    """
    return {"what": what, "due": due, "source": source, "period": period}


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


def _role_of(record):
    """The role a log record is about, for BOTH kinds this module reads.

    `notify_agent_events` puts the bare agent type in `reason`; `gate_subagent_output` opens its
    give-up reason with the same agent type and a colon. One reader, so the two cannot come to
    disagree about which role a record belongs to.
    """
    return str(record.get(RUN_ROLE_FIELD) or "").split(":")[0].strip()


def last_run(root, role):
    """(timestamp, unreadable-reason) of the last time a subagent of `role` finished HERE DELIVERING.

    The record is exactly as durable as the event log: `_audit` rotates it at `ROTATE_BYTES`, so a
    run older than the live generation reads as NO run and the routine is reported due. Nagging is
    the safe direction for a reminder that proposes, and
    `tools/test_routine_feed.py::test_a_rotated_event_log_makes_the_routine_read_as_due_rather_than_as_run`
    measures it.

    A STOP THAT GAVE UP IS NOT A RUN (BUG-0196). The two records belong to the SAME SubagentStop and
    are written by two hooks of one matcher group, so WHICH of them lands first is the provider's
    business and not a fact this reader may rest on. What pairs them is therefore position and not
    time: a give-up applies to the stop of its role that has no other stop of that role between them
    -- in either direction. A stop is counted only once the next stop of that role arrives or the
    log ends, because until then its give-up may still be on its way.
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
        open_stop = None        # a stop of this role whose give-up could still follow
        unpaired_give_up = False  # a give-up that arrived before its own stop record
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict):
                    continue
                if _role_of(record) != role:
                    continue
                event = record.get(RUN_EVENT_FIELD)
                if event == GAVE_UP_EVENT:
                    if open_stop is None:
                        unpaired_give_up = True
                    open_stop = None
                    continue
                if event != RUN_EVENT:
                    continue
                try:
                    when = datetime.datetime.strptime(
                        str(record.get(RUN_TIME_FIELD) or ""), RUN_TIME_FORMAT)
                except ValueError:
                    continue
                if open_stop is not None and (newest is None or open_stop > newest):
                    newest = open_stop
                if unpaired_give_up:
                    unpaired_give_up = False
                    open_stop = None
                else:
                    open_stop = when
        if open_stop is not None and (newest is None or open_stop > newest):
            newest = open_stop
        return newest, None
    except OSError as exc:
        return None, ("the event log could not be read here (%s), so when the %s last ran is unknown"
                      % (exc.__class__.__name__, role))


def delivery_occasions(root, since):
    """[(item id, status)] — records that reached the END of their own chain after `since`.

    THE OCCASION HALF OF `FR-0084` (`BUG-0240`/`H158`), as a DEFINITION and not a status list. The
    auditing skill names four occasions for the retrospective step, and exactly ONE of them is a
    fact about the store: something was delivered or released. That is "the record stands at the
    end of its own automaton" — a TERMINAL state, or the status a CONFIRMING edge leads from, which
    is the kernel's own name for "the work is finished and not yet confirmed"
    (`backlog_types.confirming_edge`). Both halves come from the automaton, so a type whose chain
    grows a status is covered without an edit here. The other three occasions — a phase ended, a
    finding class repeated, a Decision's premise moved — are not facts a file carries, and the
    skill says so where the role reads it.

    THE WALK STATS FIRST and parses only what changed after `since`, so an ordinary session start
    reads no item at all and does not even import the kernel. `since` is second-resolution (it
    comes out of the event log), so a file's time is rounded UP before it is compared: a record
    written in the same second as the run counts as an occasion. That is the nagging direction, and
    it is the one to be wrong in.

    WHAT IT ANSWERS WITH SILENCE, named rather than left to be found: no run recorded yet (the
    period arm already makes the run due), and a kernel this project cannot import — then this
    module reports what it reported before occasions existed, never a reassuring "nothing happened".

    THE KERNEL LOCK IS NOT TAKEN, deliberately: this runs inside a SessionStart hook, the answer is
    a reminder and not a decision, and an item caught half-written raises — which is handled one
    item at a time as "not an occasion". Taking the lock here would put a session start behind
    whatever else holds it, to make a nag one record more accurate.
    """
    if since is None:
        return []
    state_root = os.path.join(root, STATE_DIRNAME)
    cutoff = since.timestamp()
    changed = []
    for base, _dirs, names in os.walk(state_root):
        for name in names:
            if not name.endswith(".yaml"):
                continue
            path = os.path.join(base, name)
            try:
                stamped = math.ceil(os.path.getmtime(path))
            except OSError:
                continue
            if stamped > cutoff:
                changed.append(name[:-len(".yaml")])
    if not changed:
        return []
    try:
        import _kernel
        backlog = _kernel.kernel_module("backlog_types", root)
        state = _kernel.open_state(root)
    except BaseException:  # noqa: BLE001 -- see "WHAT IT ANSWERS WITH SILENCE" above
        return []
    occasions = []
    for item_id in sorted(set(changed)):
        kind = item_id.split("-")[0]
        automaton = backlog.AUTOMATA.get(kind)
        if automaton is None:
            continue
        endings = set(automaton.terminals)
        edge = backlog.confirming_edge(kind)
        if edge is not None:
            endings.add(edge[0])
        try:
            # READ ANYWHERE, not just active/. Archiving is its OWN step (`kernel.state.archive`,
            # the entry point's `archive` command) and not something a transition does by itself --
            # but it is the step a finished record takes, and after it the file is no longer under
            # `active/` while the walk above still finds it. A reader that only knows `active/`
            # therefore misses exactly the records this function exists for, and the fourth state of
            # `tools/test_review_procedure.py::test_a_delivery_since_the_last_run_makes_the_audit_due_and_names_it`
            # is that case.
            found, _archived = state.read_anywhere(item_id)
            status = str((found or {}).get("status") or "")
        except BaseException:  # noqa: BLE001 -- an unreadable item is not an occasion
            continue
        if status in endings:
            occasions.append((item_id, status))
    return occasions


def routine_duties(root, today):
    """(duties, unreadable) — the recurring audit run, in the shape a duty register consumes.

    Off in a directory that is not a project at all: without a state directory there is no project
    to audit and no log to read, and a reminder in an arbitrary folder would be noise
    (`tools/test_routine_feed.py::test_a_directory_that_is_not_a_project_gets_no_routine_notice`).

    TWO THINGS MAKE THE RUN DUE, and the second is `BUG-0240`/`H158`: the turn of the PERIOD, and
    an OCCASION standing since the last run (`delivery_occasions`). A run in this period clears the
    duty only while no occasion followed it, and where one did the duty NAMES it — a retrospective
    step whose trigger nothing watches is what the seam was.
    `tools/test_review_procedure.py::test_a_delivery_since_the_last_run_makes_the_audit_due_and_names_it`
    holds both directions.
    """
    duties, unreadable = [], []
    if not os.path.isdir(os.path.join(root, STATE_DIRNAME)):
        return duties, unreadable
    when, reason = last_run(root, AUDIT_ROLE)
    if reason:
        unreadable.append(reason)
    period = audit_period_id(today)
    occasions = delivery_occasions(root, when)
    if when is not None and audit_period_id(when.date()) == period and not occasions:
        return duties, unreadable
    due = today - datetime.timedelta(days=today.isocalendar()[2] - 1)
    if occasions:
        duties.append(duty(
            "the %s owes a run on an OCCASION: %s reached the end of its own chain since the last "
            "run (last run in this project's event log: %s) — the retrospective step asks for a "
            "delivery, so propose the run to the user and spawn it on its READ-ONLY route, the "
            "same one the period-driven run takes"
            % (AUDIT_ROLE,
               ", ".join("%s (%s)" % (one, status) for one, status in occasions[:5]),
               when.strftime(RUN_TIME_FORMAT) if when is not None else "none"),
            due, "%s/ item records" % STATE_DIRNAME,
            # THE PERIOD OF AN OCCASION-DRIVEN RUN IS THE WEEK IT IS OWED IN, not the list of
            # occasions: that list grows as more items reach the end of their chain, and a key that
            # moved with it would resurrect the duty the moment a second item finished.
            "occasion %s" % period))
        return duties, unreadable
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
        due, "%s/.audit run records" % STATE_DIRNAME, period))
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

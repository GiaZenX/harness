"""The recurring audit run, measured in EVERY kit that ships it (FR-0038, `DEC-0028`, TSK-0112).

FR-0038 was built in the office kit and nowhere else, while nothing about it was an office question:
all three kits ship a `project-auditor`, the cadence is one ISO week in all three
(`_routine.audit_period_id`, mirrored), and the
hook that writes the run record (`notify_agent_events.py`) is byte-identical in all three. The feed
now lives in a mirrored `_routine.py`, and this suite is what holds it to that -- every assertion
below runs over the THREE kits rather than over one, so a kit that stops carrying the feed fails
here instead of going quietly silent.

Everything is measured against the SHIPPED files: the module as it lies in each kit's `hooks/`, and
the whole `session_status.py` as a PROCESS with JSON on stdin, over a project built under `tmp_path`
outside this repo.
"""
import ast
import datetime
import json
import os
import subprocess
import sys

import pytest

import conftest
from conftest import load_kit_module

ROOT = conftest.ROOT
TEAM_KITS = conftest.TEAM_KITS
KITS = ("dev-team", "office-team", "research-team")
# A newline, spelled once: this module writes small fixture files and an escape inside a long
# assertion string is where a hand edit loses a quote.
NL = chr(10)


def hooks_of(kit):
    return os.path.join(TEAM_KITS, kit, "hooks")


def routine_module(kit):
    return load_kit_module("%s_routine" % kit.replace("-", "_"),
                           os.path.join(hooks_of(kit), "_routine.py"))


def project(tmp_path, events=()):
    """A project directory with the one thing the feed needs: a state directory, and optionally the
    event log entries a finished subagent leaves behind."""
    os.makedirs(str(tmp_path / "project_memory"), exist_ok=True)
    if events:
        path = tmp_path / "project_memory" / ".audit" / "hook_events.jsonl"
        os.makedirs(os.path.dirname(str(path)), exist_ok=True)
        with open(str(path), "w", encoding="utf-8") as handle:
            handle.write("".join(json.dumps(one) + "\n" for one in events))
    return tmp_path


def event(role, when):
    return {"ts": when.strftime("%Y-%m-%dT%H:%M:%S"), "hook": "notify_agent_events",
            "event": "subagent_stop", "reason": role}


def said(kit, tmp_path, hook=None):
    """What the SHIPPED SessionStart hook of `kit` really injects for this project."""
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path), HARNESS_KERNEL_PATH=TEAM_KITS)
    environment.pop("TEAM_KIT_PROVIDER", None)
    result = subprocess.run(
        [sys.executable, "-B", hook or os.path.join(hooks_of(kit), "session_status.py")],
        input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "SessionStart",
                          "session_id": "measurement"}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=environment, timeout=180)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


# ------------------------------------------------------------- the chain, once per kit, as a process

@pytest.mark.parametrize("kit", KITS)
def test_the_routine_notice_appears_and_clears_in_every_kit_that_ships_it(kit, tmp_path):
    """THE WHOLE CHAIN OF FR-0038 IN ONE MEASUREMENT, per kit, through the shipped hooks only.

    A project that has never run its auditor is told so at session start; the kit's OWN
    `notify_agent_events.py` is then run as a process with a real SubagentStop payload, and the next
    session start no longer says it. Both directions in one run, because either alone is satisfiable
    by a constant: a hook that always nagged and one that never did would each pass half of this.
    """
    routine = routine_module(kit)
    project(tmp_path)
    before = said(kit, tmp_path)
    assert routine.AUDIT_ROLE in before, (
        "%s says nothing about the audit run it has never had:\n%s" % (kit, before[:600]))

    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    recorded = subprocess.run(
        [sys.executable, "-B", os.path.join(hooks_of(kit), "notify_agent_events.py")],
        input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "SubagentStop",
                          "agent_type": routine.AUDIT_ROLE, "session_id": "s"}),
        capture_output=True, text=True, env=environment, timeout=60)
    assert recorded.returncode == 0, recorded.stderr

    when, reason = routine.last_run(str(tmp_path), routine.AUDIT_ROLE)
    assert reason is None and when is not None, (
        "the run record the kit's own hook just wrote was not read back: %s" % ((when, reason),))
    after = said(kit, tmp_path)
    assert routine.AUDIT_ROLE not in after, (
        "%s still asks for a run that just happened:\n%s" % (kit, after[:600]))


@pytest.mark.parametrize("kit", KITS)
def test_the_routine_reads_the_run_record_the_shipped_hook_really_writes(kit, tmp_path):
    """The record is DERIVED from another hook's event log, so the shape has to be measured and not
    fixed: a hand-written fixture would keep passing through a rename of the event name or of the
    field the role lands in, and this feed would go blind while its own test stayed green."""
    routine = routine_module(kit)
    project(tmp_path)
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    result = subprocess.run(
        [sys.executable, "-B", os.path.join(hooks_of(kit), "notify_agent_events.py")],
        input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "SubagentStop",
                          "agent_type": routine.AUDIT_ROLE, "session_id": "s"}),
        capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode == 0, result.stderr
    assert not routine.routine_duties(str(tmp_path), datetime.date.today())[0], (
        "a run in the current period must clear the duty -- that is the double-run guard")


@pytest.mark.parametrize("kit", KITS)
def test_a_run_that_gave_up_on_its_output_contract_is_not_a_run(kit, tmp_path):
    """BUG-0196: a stop that delivered nothing must not answer for a report nobody received.

    The record this feed reads is DERIVED from the event log, and until now it read only the stop.
    A subagent that hits `gate_subagent_output`'s give-up branch produces exactly that stop -- so
    the weekly reminder went silent for a run whose whole output was a refusal. Both shipped hooks
    are run as PROCESSES here, so a rename of either record turns this red instead of making the
    feed quietly blind, and the answer is read back through the module under test.

    THE OTHER DIRECTION IN THE SAME RUN: the next stop, with the output contract honoured, does
    clear the duty. A reader that counted no stop at all would pass the first half alone.
    """
    routine = routine_module(kit)
    project(tmp_path)
    # `gate_subagent_output` judges only an agent this project really installs.
    agents = tmp_path / ".claude" / "agents"
    os.makedirs(str(agents), exist_ok=True)
    with open(str(agents / (routine.AUDIT_ROLE + ".md")), "w", encoding="utf-8") as handle:
        handle.write("---" + NL + "name: " + routine.AUDIT_ROLE + NL + "---" + NL)
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    log = tmp_path / "project_memory" / ".audit" / "hook_events.jsonl"

    def stop(message):
        payload = {"cwd": str(tmp_path), "hook_event_name": "SubagentStop",
                   "agent_type": routine.AUDIT_ROLE, "session_id": "s",
                   "last_assistant_message": message, "stop_hook_active": True}
        for hook in ("notify_agent_events.py", "gate_subagent_output.py"):
            done = subprocess.run([sys.executable, "-B", os.path.join(hooks_of(kit), hook)],
                                  input=json.dumps(payload), capture_output=True, text=True,
                                  env=environment, timeout=60)
            assert done.returncode == 0, (hook, done.stdout, done.stderr)
        return open(str(log), encoding="utf-8").read()

    written = stop("ich habe aufgegeben")
    assert routine.GAVE_UP_EVENT in written, (
        "the shipped gate wrote no give-up record for this stop: " + written)
    when, reason = routine.last_run(str(tmp_path), routine.AUDIT_ROLE)
    assert reason is None and when is None, (
        "a stop that gave up was read as a run: %s -- %s" % ((when, reason), written))
    assert routine.routine_duties(str(tmp_path), datetime.date.today())[0], (
        "the reminder went silent for a run that delivered nothing")

    written = stop("summary: der Bericht steht")
    assert routine.last_run(str(tmp_path), routine.AUDIT_ROLE)[0] is not None, (
        "a stop that honoured the contract was not counted: " + written)
    assert not routine.routine_duties(str(tmp_path), datetime.date.today())[0]


@pytest.mark.parametrize("kit", KITS)
def test_a_run_in_an_earlier_week_leaves_the_routine_due(kit, tmp_path):
    """The period id decides, and it is an ISO week: last week's run does not answer for this one.
    Both directions, so "always due" and "never due" each fail here."""
    routine = routine_module(kit)
    today = datetime.date.today()
    project(tmp_path, events=[event(routine.AUDIT_ROLE,
                                    datetime.datetime.now() - datetime.timedelta(days=8))])
    due, _unreadable = routine.routine_duties(str(tmp_path), today)
    assert len(due) == 1 and routine.AUDIT_ROLE in due[0]["what"], due
    project(tmp_path, events=[event(routine.AUDIT_ROLE, datetime.datetime.now())])
    assert not routine.routine_duties(str(tmp_path), today)[0]


@pytest.mark.parametrize("kit", KITS)
def test_the_routine_is_due_again_on_the_monday_after_a_run(kit, tmp_path):
    """The boundary is the WEEK and not seven days: a run late on Sunday answers for that week and
    for no part of the next one."""
    routine = routine_module(kit)
    sunday = datetime.datetime(2026, 5, 3, 23, 0, 0)          # ISO 2026-W18, day 7
    project(tmp_path, events=[event(routine.AUDIT_ROLE, sunday)])
    assert not routine.routine_duties(str(tmp_path), sunday.date())[0]
    assert routine.routine_duties(str(tmp_path),
                                  (sunday + datetime.timedelta(days=1)).date())[0]


@pytest.mark.parametrize("kit", KITS)
def test_a_rotated_event_log_makes_the_routine_read_as_due_rather_than_as_run(kit, tmp_path):
    """THE COST OF DERIVING THE RECORD, measured instead of promised (`H112`). `_audit` rotates the
    log at `ROTATE_BYTES`, so a run older than the live generation is not there to be read, and the
    feed then reports the routine DUE -- nagging is the safe direction for a reminder that only
    proposes, and this pins that it fails that way rather than reporting a run it cannot see."""
    routine = routine_module(kit)
    audit = load_kit_module("%s_audit" % kit.replace("-", "_"),
                            os.path.join(hooks_of(kit), "_audit.py"))
    project(tmp_path, events=[event(routine.AUDIT_ROLE, datetime.datetime.now())])
    with open(str(tmp_path / "project_memory" / ".audit" / audit.LOG_NAME), "a",
              encoding="utf-8") as handle:
        handle.write("#" * (audit.ROTATE_BYTES + 1) + "\n")
    when, reason = routine.last_run(str(tmp_path), routine.AUDIT_ROLE)
    assert when is None and reason, (when, reason)
    assert routine.routine_duties(str(tmp_path), datetime.date.today())[0]


@pytest.mark.parametrize("kit", KITS)
def test_a_directory_that_is_not_a_project_gets_no_routine_notice(kit, tmp_path):
    """The floor under every assertion above: without a state directory there is no project to
    audit, so a feed that always spoke would fail here rather than look like a working one."""
    routine = routine_module(kit)
    assert routine.routine_duties(str(tmp_path), datetime.date.today()) == ([], [])
    assert routine.notice(str(tmp_path)) == ""


# ------------------------------------------------------------------ what the module may not do

@pytest.mark.parametrize("kit", KITS)
def test_the_routine_module_starts_no_process_at_all(kit):
    """`DEC-0028` as a property of the code that runs, read off the parse tree.

    A hook may prepare a run, report it, refuse -- it may not START one, because a process a hook
    starts is an execution layer outside what the provider reads as the enforcement layer.
    """
    with open(os.path.join(hooks_of(kit), "_routine.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    imported = {alias.name.split(".")[0]
                for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names}
    imported |= {(node.module or "").split(".")[0]
                 for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imported & {"subprocess", "multiprocessing", "asyncio"}, imported
    called = {getattr(node.func, "attr", getattr(node.func, "id", None))
              for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not called & {"system", "popen", "Popen", "spawnl", "spawnv", "execv", "fork", "run"}, \
        called


@pytest.mark.parametrize("kit", KITS)
def test_the_audited_role_is_a_role_every_kit_ships(kit):
    """`_routine.AUDIT_ROLE` is a name and not a derivation, because the carrier the constitutions
    point at (an `APR.kind: routine`) has no producer in any kit (`H111`). This keeps the name from
    pointing at an agent that no longer exists -- and, since the module is mirrored, it has to hold
    in every kit at once, which is the half a test CAN hold."""
    routine = routine_module(kit)
    definition = os.path.join(TEAM_KITS, kit, "agents", routine.AUDIT_ROLE + ".md")
    assert os.path.isfile(definition), definition


def test_no_routine_approval_can_be_minted_in_any_kit_today():
    """The measurement `_routine.AUDIT_ROLE`'s comment rests on, so the comment cannot rot quietly.
    If a route to a routine approval ever appears, this goes red and the role and the cadence should
    be read off the approval instead of named in the module."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    assert "routine" in approvals.APR_KINDS
    assert "routine" not in approvals.item_derived_kinds(), (
        "a routine approval can now be built from an item id -- the feed should derive its role and "
        "cadence from it instead of naming them")


# ------------------------------------------------------------------ the two callers, and only two

def test_the_office_briefing_names_the_routine_exactly_once(tmp_path):
    """The office kit reaches this feed THROUGH its duty register, which is why its `session_status`
    does not call `notice` as well. Naming the same run twice in one briefing is the failure this
    pins -- it is the exact shape the register was built to end (two paragraphs, two wordings)."""
    routine = routine_module("office-team")
    project(tmp_path)
    briefing = said("office-team", tmp_path)
    # the RUN is named once -- counted by the due sentence, not by the role's name: since PR-0011
    # AC-8 the one notice spells the auditor's route out, and that line names the role again in
    # `--role` and `--assigned-role`
    owed = "%s has not run in" % routine.AUDIT_ROLE
    assert briefing.count(owed) == 1, (
        "the office briefing names the audit run %d times:\n%s" % (briefing.count(owed), briefing))
    assert routine.AUDIT_ROLE in briefing


def test_every_kit_briefing_reaches_the_shared_module():
    """The wiring itself, off the parse tree of each shipped `session_status.py`: the office one
    reaches it through `_duties` (whose `FEEDS` names it), the other two import it directly.

    Asked as "does this hook reach the module", not "does it contain a word": a kit that dropped the
    call would leave a role nobody is ever reminded to run, which is the state TSK-0112 corrected.
    """
    for kit in KITS:
        names = set()
        for name in ("session_status.py", "_duties.py"):
            path = os.path.join(hooks_of(kit), name)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names |= {alias.name for alias in node.names}
                elif isinstance(node, ast.ImportFrom):
                    names.add(node.module or "")
        assert "_routine" in names, (
            "%s's session briefing reaches the shared routine feed through nothing -- its "
            "project-auditor is never named as due" % kit)


@pytest.mark.parametrize("kit", ("dev-team", "research-team"))
def test_a_missing_routine_module_is_a_line_in_the_briefing_rather_than_silence(kit, tmp_path):
    """The failure mode a fail-soft `except` creates, measured on a COPY of a shipped hook.

    Take `_routine.py` away and the notice simply stopped appearing, which reads as "nothing is due"
    -- the same wrong reading the kit-merge notice one surface over refuses to allow.

    ONCE PER KIT THAT CALLS THE MODULE DIRECTLY, and that is not symmetry for its own sake: the
    two briefings are separate files (`session_status.py` is kit-specific), so each carries its
    own copy of the fallback and each can lose it on its own. Measured on the dev kit alone,
    this test was a pointer the research hook cites and that did not answer for it. The office
    kit reaches the module through its register, so its half of the same argument is
    `tools/test_office_duties.py::test_a_missing_duty_register_is_a_line_in_the_briefing_rather_than_silence`.
    """
    import shutil
    hooks = str(tmp_path / "hooks")
    shutil.copytree(hooks_of(kit), hooks)
    os.remove(os.path.join(hooks, "_routine.py"))
    project(tmp_path)
    briefing = said(kit, tmp_path, hook=os.path.join(hooks, "session_status.py"))
    assert "ROUTINE CHECK UNAVAILABLE" in briefing, (
        "%s: the routine feed could not be loaded and the briefing says nothing about it:\n%s"
        % (kit, briefing))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))

"""The office kit's DUTY REGISTER, measured against the shipped hook (FR-0034, FR-0038).

Everything here runs the office `_duties` module, or the whole `session_status.py` PROCESS, against
a project built under `tmp_path` — outside this repo. A test that asserted on the module's docstring
would measure the docstring; what a session receives is a program's output.
"""
import ast
import datetime
import json
import os
import subprocess
import sys
import time

import pytest

import conftest
from conftest import load_kit_module

ROOT = conftest.ROOT
TEAM_KITS = conftest.TEAM_KITS
OFFICE_HOOKS = os.path.join(TEAM_KITS, "office-team", "hooks")
OFFICE_SCRIPTS = os.path.join(TEAM_KITS, "office-team", "templates", "repo", "scripts")
SESSION_STATUS = os.path.join(OFFICE_HOOKS, "session_status.py")

LEDGER_HEADER = ("id,doc_date,payment_date,direction,doc_type,counterparty,invoice_no,net,"
                 "vat_rate,gross,vat_treatment,category,source,reverses,note\n")


def duties_module():
    return load_kit_module("office_duties", os.path.join(OFFICE_HOOKS, "_duties.py"))


def write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8") as handle:
        handle.write(text)


def project(tmp_path, profile="", plan="", register="", ledger="", events=(), years=()):
    """A project with only the records a measurement needs — `project_memory/` always, because the
    routine feed is off in a directory that is not a project at all."""
    os.makedirs(str(tmp_path / "project_memory"), exist_ok=True)
    if profile:
        write(tmp_path / "project_memory" / "business_profile.yaml", profile)
    if plan:
        write(tmp_path / "project_memory" / "filing_plan.yaml", plan)
    if register:
        write(tmp_path / "project_memory" / "compliance_register.yaml", register)
    if ledger:
        write(tmp_path / "ledger" / ("%d.csv" % datetime.date.today().year),
              LEDGER_HEADER + ledger)
    if events:
        write(tmp_path / "project_memory" / ".audit" / "hook_events.jsonl",
              "".join(json.dumps(one) + "\n" for one in events))
    for relative in years:
        os.makedirs(str(tmp_path / relative), exist_ok=True)
    return tmp_path


def register_of(tmp_path, today=None):
    return duties_module().register(str(tmp_path), today or datetime.date.today())


def feed_of(name, tmp_path, today=None):
    """One feed, by itself. A feed test that went through `register` would be measuring every other
    feed's answer as well — and the routine feed answers in EVERY project, so "no duty" would be
    unreachable for the negative controls below."""
    return getattr(duties_module(), name)(str(tmp_path), today or datetime.date.today())


def said(tmp_path, extra_env=None, hook=None):
    """What the SHIPPED SessionStart hook really injects for this project — a process, JSON on
    stdin. `HARNESS_KERNEL_PATH` because the kernel-backed parts of the hook resolve the kernel
    relative to the project, and a `tmp_path` project has no `.claude/kernel`.

    `hook` names a COPY of the shipped hook for the one measurement that has to take a neighbour
    away from it; every other caller runs the file this kit ships.
    """
    environment = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path),
                       HARNESS_KERNEL_PATH=TEAM_KITS)
    environment.pop("TEAM_KIT_PROVIDER", None)
    environment.update(extra_env or {})
    result = subprocess.run(
        [sys.executable, "-B", hook or SESSION_STATUS],
        input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "SessionStart",
                          "session_id": "measurement"}),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=environment, timeout=120)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


MONTHLY_PROFILE = """
tax:
  fiscal_year: "calendar"
  filings:
    - what: "Umsatzsteuer-Voranmeldung"
      period_months: 1
      due_days_after_period: 10
      legal_basis: "para 18 Abs. 1 UStG"
"""


# ------------------------------------------------------------------ FR-0034: the tax rhythm

def test_the_register_reads_the_business_time_zone_and_names_one_it_cannot_resolve(tmp_path):
    """BUG-0208: whose day a deadline is due on was the machine's, and nothing declared it.

    `_duties` read `datetime.date.today()`, so two machines in two zones answered the same question
    with two different dates and neither of them was the BUSINESS's. `business.timezone` in the
    profile is that declaration. The two zones below are 25 hours apart (UTC+14 and UTC-11), so
    their dates differ at every instant -- a pair chosen for that, not for the place.

    THE THIRD ANSWER IS THE ONE THAT MUST NOT BE SILENT: a zone this machine cannot resolve falls
    back to the machine's date AND says so, and the sentence has to reach the briefing a session
    really receives -- a fallback nobody is told about is the quiet wrong answer this register
    exists to avoid.

    What this does NOT measure, because there is nothing to measure: the register is computed once
    per SessionStart, so a session running past midnight keeps its answer. That half of H124 has no
    second occasion to be read at.
    """
    zoneinfo = pytest.importorskip("zoneinfo")
    duties = duties_module()

    def with_zone(name, zone):
        return project(tmp_path / name, profile="business:\n  name: Probe\n  timezone: %s\n" % zone)

    east = with_zone("east", "Pacific/Kiritimati")     # UTC+14
    west = with_zone("west", "Pacific/Niue")           # UTC-11
    east_day, east_problem = duties.business_today(str(east))
    west_day, west_problem = duties.business_today(str(west))
    assert east_problem is None and west_problem is None, (east_problem, west_problem)
    assert east_day == datetime.datetime.now(zoneinfo.ZoneInfo("Pacific/Kiritimati")).date()
    assert west_day == datetime.datetime.now(zoneinfo.ZoneInfo("Pacific/Niue")).date()
    assert east_day != west_day, (
        "two projects 25 hours apart were given the same day -- the zone is not being read")

    silent = project(tmp_path / "silent", profile="business:\n  name: Probe\n")
    assert duties.business_today(str(silent)) == (datetime.date.today(), None)

    broken = with_zone("broken", "Mars/Olympus_Mons")
    day, problem = duties.business_today(str(broken))
    assert day == datetime.date.today(), "an unresolvable zone must not invent a date"
    assert problem and "Mars/Olympus_Mons" in problem, problem
    assert "Mars/Olympus_Mons" in duties.briefing(str(broken)), (
        "the fallback was silent in the paragraph the session receives")


def test_the_session_start_hook_names_the_tax_deadline_the_profile_declares(tmp_path):
    """End to end, as the manager receives it: the rhythm is the USER's declaration and the hook
    prints the period that just closed with the date it is due and the basis it rests on.

    A kit that knew what a Umsatzsteuer-Voranmeldung is would be wrong for the first business with
    another filing; what it knows is a period length and a lag.
    """
    project(tmp_path, profile=MONTHLY_PROFILE)
    briefing = said(tmp_path)
    assert "Umsatzsteuer-Voranmeldung" in briefing
    assert "para 18 Abs. 1 UStG" in briefing, "the legal basis must travel into the notice"

    today = datetime.date.today()
    closed = (today.replace(day=1) - datetime.timedelta(days=1))
    assert "%04d-%02d" % (closed.year, closed.month) in briefing, (
        "the register must name the period that CLOSED, not the running one:\n%s" % briefing)


def test_a_shifted_fiscal_year_is_reported_as_unread_rather_than_placed_in_the_calendar_year(
        tmp_path):
    """A business whose year does not start in January is legitimate and unread here. Silence would
    be the dangerous answer — the manager would take an empty register for a quiet quarter."""
    project(tmp_path, profile=MONTHLY_PROFILE.replace('"calendar"', '"july"'))
    duties, unreadable = feed_of("filing_duties", tmp_path)
    assert not [one for one in duties if "Voranmeldung" in one["what"]]
    assert any("fiscal_year" in one for one in unreadable), unreadable


def test_a_filing_entry_whose_period_does_not_divide_the_year_is_reported_rather_than_skipped(
        tmp_path):
    """Five months is not a period of the calendar year, so no due date follows from it. The entry
    is named as unreadable: a silently dropped filing is the one a business would never notice."""
    project(tmp_path, profile=MONTHLY_PROFILE.replace("period_months: 1", "period_months: 5"))
    duties, unreadable = feed_of("filing_duties", tmp_path)
    assert not duties
    assert any("period_months" in one for one in unreadable), unreadable


@pytest.mark.parametrize("months,lag,expected_days_back", [(1, 10, 0), (3, 10, 0), (12, 30, 0)])
def test_a_declared_period_produces_a_due_date_after_the_period_it_closes(
        tmp_path, months, lag, expected_days_back):
    """The arithmetic itself, over the three rhythms a German business actually runs on: whatever
    the period, the due date is AFTER the end of the period that has closed and no earlier."""
    del expected_days_back
    project(tmp_path, profile=MONTHLY_PROFILE
            .replace("period_months: 1", "period_months: %d" % months)
            .replace("due_days_after_period: 10", "due_days_after_period: %d" % lag))
    today = datetime.date.today()
    duties, unreadable = feed_of("filing_duties", tmp_path, today)
    assert not unreadable, unreadable
    assert len(duties) == 1, duties
    due = duties[0]["due"]
    assert due <= today + datetime.timedelta(days=lag), (
        "the period the register picked has not closed yet: %s" % duties[0])
    assert due > today - datetime.timedelta(days=months * 31 + lag), (
        "the register reached back further than one period: %s" % duties[0])


# ------------------------------------------------------------------ FR-0034: retention

PLAN = """
rules:
  - id: FP-001
    path_template: "archive/finance/incoming/<year>/"
    retention: "%s"
"""


def test_a_year_past_its_retention_is_named_and_one_inside_it_is_not(tmp_path):
    """Both directions in one measurement, because either alone is satisfiable by a constant: the
    old year appears, the recent one does not, and the reader is holding the SPAN against the year
    rather than reporting every folder it finds."""
    today = datetime.date.today()
    old, recent = today.year - 12, today.year - 2
    project(tmp_path, plan=PLAN % "8y (para 147 AO)",
            years=["archive/finance/incoming/%d" % old,
                   "archive/finance/incoming/%d" % recent])
    duties, unreadable = feed_of("retention_duties", tmp_path, today)
    assert not unreadable, unreadable
    named = " | ".join(one["what"] for one in duties)
    assert str(old) in named and str(recent) not in named, named


def test_a_retention_this_reader_cannot_parse_is_reported_rather_than_read_as_met(tmp_path):
    """The other half of the span reader: "while the product is active" is a legitimate retention
    and not a number of years. Treating it as satisfied would be a watcher that reports nothing and
    claims to be watching."""
    today = datetime.date.today()
    project(tmp_path, plan=PLAN % "while the product is active",
            years=["archive/finance/incoming/%d" % (today.year - 40)])
    duties, unreadable = feed_of("retention_duties", tmp_path, today)
    assert not duties
    assert any("FP-001" in one for one in unreadable), unreadable


def test_a_path_template_that_climbs_out_of_the_project_is_not_walked(tmp_path):
    """A filing rule is user text and nothing decides what it may SAY — `gate_filing` decides where a
    document may be filed. So a rule whose path climbs would point a session-start `listdir` at a
    directory outside the business; the feed reads no place it cannot place inside the project."""
    outside = tmp_path.parent / ("outside-%s" % tmp_path.name)
    os.makedirs(str(outside / "1990"), exist_ok=True)
    project(tmp_path, plan="""
rules:
  - id: FP-ESCAPE
    path_template: "../%s/<year>/"
    retention: "1y"
""" % outside.name)
    duties, unreadable = feed_of("retention_duties", tmp_path)
    assert not duties and not unreadable, (duties, unreadable)


def test_a_rule_whose_archive_is_not_year_partitioned_produces_no_retention_duty(tmp_path):
    """The named limit, pinned so it stays a limit and does not quietly become a false positive:
    the reader walks YEAR folders, and a flat drawer has none."""
    project(tmp_path, plan="""
rules:
  - id: FP-002
    path_template: "archive/products/datasheets/"
    retention: "3y"
""", years=["archive/products/datasheets/acme"])
    duties, unreadable = feed_of("retention_duties", tmp_path)
    assert not duties and not unreadable, (duties, unreadable)


# ------------------------------------------------------------------ FR-0034: dunning candidates

TERMS_PROFILE = "receivables:\n  payment_terms_days: 14\n"


def _row(doc_type, paid="", invoice="R-1", direction="income", days_old=200):
    issued = (datetime.date.today() - datetime.timedelta(days=days_old)).isoformat()
    return ("L1,%s,%s,%s,%s,ACME,%s,100.00,19,119.00,standard,sales,archive/a.pdf,,\n"
            % (issued, paid, direction, doc_type, invoice))


def test_an_unpaid_invoice_is_a_dunning_candidate_and_an_unpaid_credit_note_is_not(tmp_path):
    """The definition that separates the two: a credit note REDUCES what its own direction totals,
    so an unpaid one is not money anybody owes. Without this the register would tell a business to
    chase its own refunds."""
    project(tmp_path, profile=TERMS_PROFILE,
            ledger=_row("invoice", invoice="R-OPEN") + _row("credit_note", invoice="R-CREDIT")
            + _row("invoice", paid=datetime.date.today().isoformat(), invoice="R-PAID")
            + _row("invoice", invoice="R-FRESH", days_old=2))
    duties, unreadable = feed_of("receivable_duties", tmp_path)
    assert not unreadable, unreadable
    named = " | ".join(one["what"] for one in duties)
    assert "R-OPEN" in named, named
    for quiet in ("R-CREDIT", "R-PAID", "R-FRESH"):
        assert quiet not in named, "%s must not be dunned: %s" % (quiet, named)


def test_an_open_invoice_from_an_earlier_year_is_still_a_candidate(tmp_path):
    """The feed opens every ledger year this project keeps, not a window of the last two. An invoice
    nobody paid three years ago is exactly the one a business wants named, and a window would have
    hidden it while the feed looked like a watcher."""
    old = datetime.date.today().year - 3
    project(tmp_path, profile=TERMS_PROFILE, ledger=_row("invoice", invoice="R-RECENT"))
    for year in range(old, datetime.date.today().year):
        write(tmp_path / "ledger" / ("%d.csv" % year), LEDGER_HEADER
              + ("L9,%d-02-01,,income,invoice,ACME,R-%d,100.00,19,119.00,standard,sales,"
                 "archive/a.pdf,,\n" % (year, year)))
    duties, unreadable = feed_of("receivable_duties", tmp_path)
    assert not unreadable, unreadable
    named = " | ".join(one["what"] for one in duties)
    assert "R-%d" % old in named, ("the oldest open invoice fell out of the window: %s" % named)
    assert "R-RECENT" in named, named


def test_the_receivable_feed_and_the_shipped_ledger_agree_on_what_reduces_a_total():
    """THE TRIPWIRE ON THE ONE ENUMERATION THIS FEED CARRIES, in both directions.

    `_duties.REDUCING_DOC_TYPES` is a reader's copy of `ledger_add.NEGATIVE_DOC_TYPES`, and the two
    are read off the modules here rather than compared by eye: a reducing doc type added to the
    ledger and not here would be dunned as a receivable, and one named here that the ledger does
    not know is a rule about nothing.
    """
    ledger = load_kit_module("office_ledger_add", os.path.join(OFFICE_SCRIPTS, "ledger_add.py"))
    duties = duties_module()
    assert set(duties.REDUCING_DOC_TYPES) == set(ledger.NEGATIVE_DOC_TYPES), (
        duties.REDUCING_DOC_TYPES, ledger.NEGATIVE_DOC_TYPES)
    assert duties.RECEIVABLE_DIRECTION in ledger.DIRECTIONS, duties.RECEIVABLE_DIRECTION
    for column in (duties.LEDGER_DIRECTION, duties.LEDGER_DOC_TYPE, duties.LEDGER_DOC_DATE,
                   duties.LEDGER_PAYMENT_DATE):
        assert column in ledger.COLUMNS, column


def test_the_receivable_feed_opens_the_years_its_own_bound_names(tmp_path):
    """`_duties.MAX_LEDGER_YEARS` measured from the constant, both directions in one run.

    The test above pins that the window is not two years wide; this pins that there IS a window and
    where it ends, so neither "read one year" nor "read every year on disk" survives. A business
    with more ledger years than the bound is told nothing about the ones beyond it — which is the
    honest cost of bounding a session start, and it is measured here rather than assumed.
    """
    duties = duties_module()
    today = datetime.date.today()
    oldest = today.year - duties.MAX_LEDGER_YEARS      # one year deeper than the feed opens
    project(tmp_path, profile=TERMS_PROFILE)
    for year in range(oldest, today.year + 1):
        write(tmp_path / "ledger" / ("%d.csv" % year), LEDGER_HEADER
              + ("L9,%d-02-01,,income,invoice,ACME,R-%d,100.00,19,119.00,standard,sales,"
                 "archive/a.pdf,,\n" % (year, year)))
    found, unreadable = feed_of("receivable_duties", tmp_path, today)
    assert not unreadable, unreadable
    named = " | ".join(one["what"] for one in found)
    assert "R-%d" % (oldest + 1) in named, (
        "the year just inside the bound is not read, so the window is narrower than the constant "
        "says: %s" % named)
    assert "R-%d" % oldest not in named, (
        "a year beyond the bound was opened, so the constant bounds nothing: %s" % named)


def test_without_payment_terms_the_ledger_produces_no_dunning_candidate(tmp_path):
    """The kit invents no dunning policy. With the field unset the feed is OFF — a reminder about
    somebody else's money rests on what the owner agreed with them, not on a default of 14 or 30."""
    project(tmp_path, profile="business:\n  name: \"x\"\n", ledger=_row("invoice"))
    duties, unreadable = feed_of("receivable_duties", tmp_path)
    assert not duties and not unreadable, (duties, unreadable)


# ------------------------------------------------------------------ FR-0038: the audit routine

def routine_module():
    """The SHARED routine feed, which is where FR-0038 lives since TSK-0112. The office
    register is one of its two callers; the feed itself is measured per kit in
    `tools/test_routine_feed.py`, so what is asked here is only what the REGISTER does with
    it."""
    return load_kit_module("office_routine", os.path.join(OFFICE_HOOKS, "_routine.py"))


def _event(role, when):
    return {"ts": when.strftime("%Y-%m-%dT%H:%M:%S"), "hook": "notify_agent_events",
            "event": "subagent_stop", "reason": role}


def test_the_duty_register_starts_no_process_at_all():
    """`DEC-0028` as a property of the code that runs, read off the parse tree.

    A hook may prepare a run, report it, refuse — it may not START one, because a process a hook
    starts is an execution layer outside what the provider reads as the enforcement layer. The
    register names a run that is owed; a `subprocess` call here would be that boundary crossed.
    """
    with open(os.path.join(OFFICE_HOOKS, "_duties.py"), encoding="utf-8") as handle:
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


# ------------------------------------------------------------------ the register as a whole

def test_the_duty_register_writes_nothing_into_the_project_it_reads(tmp_path):
    """It PROPOSES. Measured as the property rather than asserted in prose: the whole tree is
    hashed before and after, and nothing under it may move."""
    project(tmp_path, profile=MONTHLY_PROFILE + TERMS_PROFILE, plan=PLAN % "8y",
            register="register:\n  - id: CR-1\n    review_by: \"2001-01-01\"\n",
            ledger=_row("invoice"),
            years=["archive/finance/incoming/%d" % (datetime.date.today().year - 40)])

    def snapshot():
        seen = {}
        for base, dirs, names in os.walk(str(tmp_path)):
            dirs[:] = [one for one in dirs if one != "__pycache__"]
            for name in names:
                path = os.path.join(base, name)
                seen[path] = (os.path.getsize(path), open(path, "rb").read())
        return seen

    before = snapshot()
    duties, _unreadable = register_of(tmp_path)
    assert duties, "the control is worthless if the register found nothing to report"
    assert snapshot() == before, "the register changed the project it was reading"


def test_the_review_dates_the_compliance_notice_used_to_carry_are_still_named(tmp_path):
    """The nag `session_status` used to print on its own became a FEED of the register. This is the
    regression guard on that move: an entry past its review date must still reach the manager, and
    one that is not due must still stay quiet."""
    project(tmp_path, register="""
register:
  - id: CR-STALE
    review_by: "2001-01-01"
  - id: CR-FRESH
    review_by: "2099-01-01"
""")
    briefing = said(tmp_path)
    assert "CR-STALE" in briefing, briefing
    assert "CR-FRESH" not in briefing, briefing


def test_an_unreadable_source_is_named_rather_than_read_as_an_empty_register(tmp_path):
    """An empty register and an unreadable one are different answers. A manager who reads a short
    list as a quiet business stops looking, so the register says which source it could not read —
    the same distinction the kit's session briefing already draws for the kit-merge backlog."""
    project(tmp_path, profile="business: [this is not a mapping\n")
    briefing = said(tmp_path)
    assert "INCOMPLETE" in briefing and "business_profile.yaml" in briefing, briefing


def test_an_empty_state_document_is_not_reported_as_unparseable(tmp_path):
    """A file with nothing in it HAS no fields — that is an answer, not a failure. Reporting it as
    unreadable would send the manager looking for a broken file every session of a fresh project,
    and a warning that fires on the normal case is one nobody reads any more."""
    project(tmp_path, profile="# only a comment\n", plan="# only a comment\n",
            register="# only a comment\n")
    for feed in ("filing_duties", "retention_duties", "review_duties"):
        duties, unreadable = feed_of(feed, tmp_path)
        assert not duties and not unreadable, (feed, duties, unreadable)


def test_a_project_that_owes_nothing_gets_no_paragraph(tmp_path):
    """The floor under every assertion above: with nothing due the register says NOTHING, so a
    briefing that always printed the block would fail here rather than look like a working one."""
    duties = duties_module()
    project(tmp_path, events=[_event(routine_module().AUDIT_ROLE, datetime.datetime.now())])
    assert duties.briefing(str(tmp_path)) == ""


# ------------------------------------------------------------------ the time budget

def _session_status_git_budget():
    """(seconds per git call, number of git calls in `main`) read off the SHIPPED hook's parse tree.

    The number lives once, in the hook, as the `timeout=` of the call its `git()` helper makes —
    reading it here rather than restating it is what keeps the sum below from becoming a second
    copy of a constant that belongs to another file (`_bookings.TOTAL_BUDGET` carries the same
    argument for the ledger chain).
    """
    with open(SESSION_STATUS, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    helper = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == "git")
    timeouts = [keyword.value.value for node in ast.walk(helper)
                if isinstance(node, ast.Call)
                for keyword in node.keywords
                if keyword.arg == "timeout" and isinstance(keyword.value, ast.Constant)]
    assert len(timeouts) == 1, "the git helper no longer names exactly one timeout: %s" % timeouts
    main = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = [node for node in ast.walk(main)
             if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "git"]
    assert calls, "the hook no longer calls git in main — this reader measures nothing"
    return timeouts[0], len(calls)


def test_the_session_start_budgets_together_fit_inside_the_hook_deadline():
    """THE SUM IS THE BOUND, because these budgets are spent SEQUENTIALLY IN ONE PROCESS.

    `session_status` is registered on its own, with no `timeout`, so what bounds it is the deadline
    the hooks give themselves. Checking `_duties.TOTAL_BUDGET` against that alone is not the
    property: the hook already gives its git reads a budget of their own, and the host sees the sum.
    Every number is read off the module or the parse tree, so raising either turns this red instead
    of leaving a comment that stopped being true.
    """
    duties = duties_module()
    compat = load_kit_module("office_compat", os.path.join(OFFICE_HOOKS, "_compat.py"))
    per_call, calls = _session_status_git_budget()
    together = duties.TOTAL_BUDGET + per_call * calls
    assert together < compat.HOOK_DEADLINE_SECONDS, (
        "the session-start hook gives itself %g s (%g for the register + %d git reads of %g) "
        "against a %g s deadline: the host kills it mid-briefing and the manager wakes up blind"
        % (together, duties.TOTAL_BUDGET, calls, per_call, compat.HOOK_DEADLINE_SECONDS))
    assert duties.TOTAL_BUDGET > 0, "a budget of 0 satisfies the line above and measures nothing"


def test_a_session_start_over_a_maximal_register_stays_inside_the_hook_deadline(tmp_path):
    """The arithmetic above is one half; this is the other — the shipped hook, as a process, over a
    project sized at what the register's own caps allow.

    THE EXPENSIVE DIRECTION IS THE QUIET ONE, and getting that backwards would have made this
    measurement look reassuring while measuring almost nothing. Every feed returns as soon as it has
    `MAX_PER_FEED` duties, so a ledger full of dunning candidates is read for a few hundred rows and
    stops. A ledger nobody owes anything on has no exit: it is read to the last row of the last year
    the bound allows. So the years below carry PAID rows, and only the oldest — the one read last —
    carries the unpaid ones.
    """
    duties = duties_module()
    compat = load_kit_module("office_compat", os.path.join(OFFICE_HOOKS, "_compat.py"))
    rules, years = [], []
    for index in range(duties.MAX_PER_FEED):
        path = "archive/bulk/%03d" % index
        rules.append('  - id: FP-%03d\n    path_template: "%s/<year>/"\n    retention: "1y"\n'
                     % (index, path))
        for year in range(1990, 2000):
            years.append("%s/%d" % (path, year))
    paid = "".join(_row("invoice", paid=datetime.date.today().isoformat(),
                        invoice="R-P%05d" % index) for index in range(4000))
    project(tmp_path, profile=MONTHLY_PROFILE + TERMS_PROFILE,
            plan="rules:\n" + "".join(rules), ledger=paid, years=years,
            register="register:\n" + "".join(
                '  - id: CR-%d\n    review_by: "2001-01-01"\n' % index for index in range(200)))
    # Every ledger year the feed may open, sized off `MAX_LEDGER_YEARS` so raising the bound raises
    # this measurement with it.
    this_year = datetime.date.today().year
    oldest = this_year - duties.MAX_LEDGER_YEARS + 1
    for year in range(oldest, this_year):
        write(tmp_path / "ledger" / ("%d.csv" % year), LEDGER_HEADER
              + (paid if year > oldest else "".join(
                  _row("invoice", invoice="R-%05d" % index) for index in range(4000))))
    started = time.time()
    briefing = said(tmp_path)
    elapsed = time.time() - started
    assert "DUE / OVERDUE" in briefing, briefing[:400]
    assert elapsed < compat.HOOK_DEADLINE_SECONDS, (
        "%.1f s for one session start — the host kills the hook and the manager gets no briefing "
        "at all" % elapsed)
    # ...and the project really was the size this test claims: a walk that stopped at the newest
    # ledger would pass the clock above while measuring one file. The oldest year the bound allows
    # is the LAST one read, so its invoices are the proof that all of them were.
    found, _unreadable = feed_of("receivable_duties", tmp_path)
    assert found, "no dunning candidate at all — the deepest ledger year was never opened"


# ------------------------------------------------------ what the briefing NAMES, and what it drops

def test_a_decade_of_archive_years_does_not_push_the_due_tax_deadline_out_of_the_briefing(tmp_path):
    """THE MEASUREMENT THE MODULE DOCSTRING RESTS ON, and it was red when it was written.

    A business that has filed by year since 2005 under ONE retention rule is an ordinary business,
    not an edge case. Before this, that archive produced one duty per year folder, every one of them
    long past its date; the briefing names the nearest-due first and has room for `MAX_NAMED`, so
    thirteen folders from the 2000s took every slot and the ONE deadline that costs money if it is
    missed — the tax filing due in days — was not in the paragraph the manager reads.

    WHAT THIS TEST MEASURES IS THE RESULT, IN THE MANAGER'S WORDS, and not either half of the fix.
    Measured: with only `_named_fairly` reverted this stays GREEN, and with only the per-rule
    aggregation reverted it stays GREEN too; it went red on the tree where BOTH were missing. Each
    half has its own holder --
    `tools/test_office_duties.py::test_a_rule_with_many_years_past_retention_is_one_duty_that_names_the_oldest_and_the_count`
    and `tools/test_office_duties.py::test_no_feed_can_take_every_slot_of_the_briefing_from_another`
    -- so the coverage is disjunctive: this test is NOT a regression net for either half on its own,
    and removing one half together with its holder would leave all three green.
    """
    today = datetime.date.today()
    oldest = today.year - 21
    project(tmp_path, profile=MONTHLY_PROFILE, plan=PLAN % "8y (para 147 AO)",
            years=["archive/finance/incoming/%d" % year
                   for year in range(oldest, today.year - 8)])
    briefing = said(tmp_path)
    assert "Umsatzsteuer-Voranmeldung" in briefing, (
        "a decade of archive folders pushed the one deadline with a date on it out of the "
        "briefing:\n%s" % briefing)
    assert str(oldest) in briefing, (
        "the archive that IS past its retention is not named either — the paragraph now drops "
        "everything:\n%s" % briefing)


def test_a_rule_with_many_years_past_retention_is_one_duty_that_names_the_oldest_and_the_count(
        tmp_path):
    """One RULE is one obligation: review this drawer. Thirteen year folders under it are thirteen
    reasons, not thirteen duties — and a register that returned them separately would report the
    same review over and over while claiming to report the current obligation only.

    The count and the oldest year both travel into the duty, because dropping them would trade the
    over-report for an under-report: the user has to be able to see how much is waiting.
    """
    today = datetime.date.today()
    oldest, newest_past = today.year - 21, today.year - 9
    project(tmp_path, plan=PLAN % "8y",
            years=["archive/finance/incoming/%d" % year
                   for year in range(oldest, newest_past + 1)]
            + ["archive/finance/incoming/%d" % (today.year - 1)])
    duties, unreadable = feed_of("retention_duties", tmp_path, today)
    assert not unreadable, unreadable
    assert len(duties) == 1, ("one rule must produce one review duty, not one per year: %s"
                              % [one["what"] for one in duties])
    what = duties[0]["what"]
    assert str(oldest) in what, what
    assert str(newest_past - oldest + 1) in what, (
        "the number of year folders waiting is not in the duty, so collapsing them hid it: %s"
        % what)
    assert str(today.year - 1) not in what, ("a year INSIDE its retention was counted: %s" % what)
    assert duties[0]["due"] == datetime.date(oldest + 8, 12, 31), duties[0]["due"]


def test_no_feed_can_take_every_slot_of_the_briefing_from_another(tmp_path):
    """The property that keeps one loud source from silencing another, as a property.

    Every feed here has more duties than the paragraph has slots. A selection that simply took the
    nearest-due `MAX_NAMED` would print one feed and drop the other four — which is what it did.
    Each feed that found something must be represented, and the arithmetic that makes that possible
    (`MAX_NAMED` is at least as large as the number of feeds) is asserted rather than assumed, so
    adding a sixth feed without room for it turns this red.
    """
    duties = duties_module()
    today = datetime.date.today()
    assert duties.MAX_NAMED >= len(duties.FEEDS), (
        "the briefing has fewer slots than the register has feeds, so one feed cannot be named "
        "at all: %d slots, %d feeds" % (duties.MAX_NAMED, len(duties.FEEDS)))
    plan = "rules:\n" + "".join(
        '  - id: FP-%03d\n    path_template: "archive/bulk%03d/<year>/"\n    retention: "1y"\n'
        % (index, index) for index in range(duties.MAX_NAMED + 2))
    project(tmp_path,
            profile=MONTHLY_PROFILE + TERMS_PROFILE,
            plan=plan,
            ledger="".join(_row("invoice", invoice="R-%03d" % index)
                           for index in range(duties.MAX_NAMED + 2)),
            register="register:\n" + "".join(
                '  - id: CR-%03d\n    review_by: "2001-01-01"\n' % index
                for index in range(duties.MAX_NAMED + 2)),
            years=["archive/bulk%03d/1990" % index for index in range(duties.MAX_NAMED + 2)])
    found, _unreadable = duties.register(str(tmp_path), today)
    producing = {one["feed"] for one in found}
    assert len(producing) == len(duties.FEEDS), (
        "the fixture does not make every feed speak, so this measures less than it claims: %s"
        % sorted(producing))
    paragraph = duties.briefing(str(tmp_path), today)
    silent = sorted(name for name in producing
                    if not any(one["what"] in paragraph
                               for one in found if one["feed"] == name))
    assert not silent, (
        "these feeds found something and none of it reached the paragraph:\n%s\n%s"
        % (silent, paragraph))


def test_a_filing_plan_that_names_a_place_outside_the_project_is_not_walked(tmp_path):
    """A filing rule is USER TEXT and nothing decides what it may say, so the directory a session
    start lists has to be one this project owns.

    Answered by RESOLVING and not by reading the spelling — reading the spelling was measured wrong
    in both halves at once: a drive letter in the first path component was refused and one in a
    later component was not, and `os.path.join` lets the later one win, so `a/b/D:/<year>/` pointed
    the walk at the current directory of another drive. Every class of "not in this project" is a
    case here, and the last one is the control: an ordinary rule must still resolve.
    """
    duties = duties_module()
    root = str(tmp_path)
    for template in ("../secrets/<year>/", "a/b/D:/<year>/", "docs/C:/Users/<year>/",
                     "C:/Windows/<year>/", "/etc/<year>/", "//server/share/<year>/",
                     "docs/../../<year>/"):
        placed = duties._project_directory(root, template)
        assert placed is None or _inside(root, placed), (
            "%r was placed at %r, which is not inside the project" % (template, placed))
    ordinary = duties._project_directory(root, "archive/finance/<year>/")
    assert ordinary and _inside(root, ordinary), (
        "an ordinary rule no longer resolves, so the assertions above hold over nothing: %r"
        % ordinary)


def _the_filesystem_puts_this_on_the_root(root, prefix):
    """Does THIS platform's filesystem put `<root>/<prefix>` on `root` itself? None = cannot ask.

    ASKED OF THE FILESYSTEM, never of `os.path.abspath`, and that is the whole point of the detour:
    `abspath` is the primitive `_duties._same_place` answers with, so an expectation derived from it
    would agree with the code under test by construction and no mutation of the guard could go red.
    A directory is really made and `os.path.samefile` decides -- the operating system's own answer
    to "are these two names one place".

    Measured 2026-09-04 with `....`: on Windows the directory is the parent (trailing dots are
    dropped before the call ever reaches the filesystem, `samefile` True, the parent stays empty),
    on Linux it is a real child named `....` (`samefile` False, the parent lists it).
    """
    probe = os.path.join(root, "place-probe")
    os.makedirs(probe, exist_ok=True)
    target = os.path.join(probe, *prefix.split("/")) if prefix else probe
    try:
        os.makedirs(target, exist_ok=True)
        return os.path.samefile(target, probe)
    except OSError:
        return None


def test_a_filing_plan_that_resolves_to_the_project_ROOT_is_not_walked(tmp_path):
    """The other half of containment, and the half a string comparison got wrong.

    Being INSIDE the project is not enough: the project root itself is not an archive. A template
    that resolves back to the root points the walk at every directory the project has, and every
    four-digit one of them is read as an archive year -- so an ordinary `2026/` working folder
    becomes a retention duty nobody can act on. No escape, but a register that reports what it never
    watched is a register a business stops reading.

    MEASURED: `....//<year>/` resolved to the root WITH A TRAILING SEPARATOR, and the guard compared
    raw strings, so `candidate == base` was False and the walk went ahead. Both ends here -- the
    resolver refuses it, and the feed over a project that really has such a folder stays quiet.

    THAT PAIR IS A WINDOWS STATEMENT, and saying so is the point rather than a caveat: the guard's
    ROOT branch is only REACHABLE where a spelling survives `_literal_prefix` and still lands on the
    root, and on POSIX there is none -- `./<year>/` and `<year>/` come back with an empty prefix and
    `_project_directory` returns before the guard, while `....` names a real child there. So on
    POSIX the first end is vacuous and the second is empty too (no `<root>/....` is ever created).
    Removing `candidate == base` from `_duties._project_directory` reddens this node on Windows and
    leaves it green on Linux -- measured in the first verification round of TSK-0125.

    WHICH SPELLING LANDS ON THE ROOT IS THE PLATFORM'S ANSWER, NOT THIS TABLE'S, and asserting the
    table's was a red on ubuntu-latest that no local run reproduced (BUG-0069, run 33717432166):
    `....` is a root spelling only where trailing dots are dropped from a path component, which is
    Windows and not POSIX -- there it names a real child, and refusing it as "the root" would be the
    guard over-reaching. So each spelling is asked of the filesystem first, and BOTH answers are
    assertions: a spelling that lands on the root must be refused, one that does not must resolve.
    """
    duties = duties_module()
    root = str(tmp_path)
    # each spelling with the literal prefix `_literal_prefix` takes out of it -- written here rather
    # than read from the module, so the platform question stays independent of the code under test
    for template, prefix in (("....//<year>/", "...."), ("./<year>/", "."), ("<year>/", "")):
        placed = duties._project_directory(root, template)
        on_the_root = _the_filesystem_puts_this_on_the_root(root, prefix)
        if on_the_root is None:
            continue          # this platform will not make the directory -- nothing to hold it to
        if on_the_root:
            assert placed is None, (
                "%r was placed at the project root, whose every four-digit folder then reads as an "
                "archive year" % template)
        else:
            assert placed is not None, (
                "%r names a real directory on this platform, not the project root, so refusing it "
                "as the root takes a legitimate filing rule away" % template)
    project(tmp_path, plan="""
rules:
  - id: FP-ROOT
    path_template: "....//<year>/"
    retention: "1y"
""", years=["2010"])
    found, unreadable = feed_of("retention_duties", tmp_path)
    assert not found and not unreadable, (found, unreadable)


def test_the_place_reader_folds_case_exactly_where_the_platform_does():
    """`_same_place`'s case half, which was carried by the platform and by no test (TSK-0114).

    The docstring of `_same_place` names two differences it flattens. One of them -- the trailing
    separator -- is already inside `os.path.abspath`, so at its call site it changes nothing; the
    other is the case fold, and every case of its named sibling test spells root and template
    alike, so nothing went red if `normcase` disappeared.

    ASKED OF THE PLATFORM AND NOT OF A NAME: whether two spellings that differ only in case are ONE
    place is the platform's answer, so this asserts the reader gives the same answer the platform
    does -- true on a case-folding file system and true on one that does not fold, without either
    being written here as a case.
    """
    duties = duties_module()
    upper, lower = os.path.join("ARCHIVE", "2026"), os.path.join("archive", "2026")
    folds = os.path.normcase(upper) == os.path.normcase(lower)
    assert (duties._same_place(upper) == duties._same_place(lower)) is folds, (
        "the reader and the platform disagree about whether %r and %r are one place" % (upper, lower))


def _inside(root, path):
    root, path = os.path.abspath(root), os.path.abspath(path)
    try:
        return os.path.normcase(os.path.commonpath([root, path])) == os.path.normcase(root)
    except ValueError:
        return False


# ------------------------------------------------------------------ the day a duty falls due

def test_a_duty_is_overdue_the_day_AFTER_its_date_and_not_on_it(tmp_path):
    """The boundary `is_overdue` draws, measured on the day itself. A filing due today is due, not
    late; counting it as late tells a business it missed a deadline it still has hours for."""
    del tmp_path
    duties = duties_module()
    today = datetime.date.today()
    assert not duties.is_overdue({"due": today}, today)
    assert duties.is_overdue({"due": today - datetime.timedelta(days=1)}, today)
    assert not duties.is_overdue({"due": today + datetime.timedelta(days=1)}, today)


def test_the_tax_feed_treats_the_last_day_of_a_period_as_inside_it(tmp_path):
    """On the 31st the month has not closed. Reading it as closed would name a period the business
    is still trading in and give it a due date computed from a period that is not over."""
    project(tmp_path, profile=MONTHLY_PROFILE)
    last_day = datetime.date(2026, 1, 31)
    duties, unreadable = feed_of("filing_duties", tmp_path, last_day)
    assert not unreadable, unreadable
    assert len(duties) == 1, duties
    assert "2025-12" in duties[0]["what"], (
        "January is not closed on 31 January: %s" % duties[0]["what"])
    duties, _unreadable = feed_of("filing_duties", tmp_path, datetime.date(2026, 2, 1))
    assert "2026-01" in duties[0]["what"], duties[0]["what"]


def test_a_retention_year_falls_due_the_day_AFTER_its_last_31_december(tmp_path):
    """The statutory clock runs to the END of the last year, so on 31 December of that year the
    documents are still inside their retention. One day either side of that date, in one run."""
    project(tmp_path, plan=PLAN % "8y", years=["archive/finance/incoming/2010"])
    on_the_day = datetime.date(2018, 12, 31)
    duties, _unreadable = feed_of("retention_duties", tmp_path, on_the_day)
    assert not duties, ("2010 + 8y is still inside its retention ON 31.12.2018: %s" % duties)
    duties, _unreadable = feed_of("retention_duties", tmp_path,
                                  on_the_day + datetime.timedelta(days=1))
    assert len(duties) == 1, duties


def test_an_invoice_becomes_a_dunning_candidate_the_day_AFTER_its_terms_run_out(tmp_path):
    """Payment terms of 14 days mean the customer has all 14. Dunning on day 14 is dunning a
    customer who is not late — the one direction of this feed that reaches a third party."""
    issued = datetime.date(2026, 3, 1)
    project(tmp_path, profile=TERMS_PROFILE,
            ledger=("L1,%s,,income,invoice,ACME,R-1,100.00,19,119.00,standard,sales,,,\n"
                    % issued.isoformat()))
    duties, _unreadable = feed_of("receivable_duties", tmp_path,
                                  issued + datetime.timedelta(days=14))
    assert not duties, ("dunned on the last day of its own terms: %s" % duties)
    duties, _unreadable = feed_of("receivable_duties", tmp_path,
                                  issued + datetime.timedelta(days=15))
    assert len(duties) == 1, duties


def test_a_review_date_falls_due_the_day_AFTER_it(tmp_path):
    """A Wiedervorlage set for today is today's work, not overdue work."""
    project(tmp_path, register='register:\n  - id: CR-1\n    review_by: "2026-05-06"\n')
    on_the_day = datetime.date(2026, 5, 6)
    assert not feed_of("review_duties", tmp_path, on_the_day)[0]
    assert feed_of("review_duties", tmp_path, on_the_day + datetime.timedelta(days=1))[0]


# ------------------------------------------- the register is unreachable, not silent (P10)

def test_a_missing_duty_register_is_a_line_in_the_briefing_rather_than_silence(tmp_path):
    """The failure mode a fail-soft `except` creates, measured on a COPY of the shipped hook.

    Take `_duties.py` away and the paragraph simply stopped appearing: a manager reads a briefing
    with no deadlines in it as a business with no deadlines. The same distinction this hook already
    draws one surface over for the kit-merge backlog -- an unreadable source is named.
    """
    import shutil
    hooks = str(tmp_path / "hooks")
    shutil.copytree(OFFICE_HOOKS, hooks)
    os.remove(os.path.join(hooks, "_duties.py"))
    briefing = said(tmp_path, hook=os.path.join(hooks, "session_status.py"))
    assert "DUTY REGISTER UNAVAILABLE" in briefing, (
        "the deadline register could not be loaded and the briefing says nothing about it:\n%s"
        % briefing)


# --------------------------------------------- what the filing-plan TEMPLATE hands a fresh project

FILING_PLAN_TEMPLATE = os.path.join(TEAM_KITS, "office-team", "templates", "project_memory",
                                    "filing_plan.yaml")


def shipped_filing_rules():
    """Every rule the shipped filing plan puts in front of a user: the live list plus the example
    block, which is commented out and is exactly what a fresh project copies.

    The example block is UN-COMMENTED AND PARSED rather than scanned line by line: what the user
    pastes is YAML, so the subject of a measurement about it is the value PyYAML makes of it. The
    block is the run of comment lines that follows the `rules:` key, which is a position in the
    file and not a pattern somebody has to keep matching.
    """
    yaml = pytest.importorskip("yaml")
    with open(FILING_PLAN_TEMPLATE, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    live = yaml.safe_load("\n".join(lines)) or {}
    start = next(index for index, line in enumerate(lines) if line.startswith("rules:")) + 1
    block = []
    for line in lines[start:]:
        if not line.startswith("#"):
            break
        block.append(line[1:])
    examples = yaml.safe_load("\n".join(block))
    assert isinstance(examples, list) and examples, (
        "the example rules under `rules:` in %s do not parse as YAML once the comment marker is "
        "taken off, so what a user pastes is not a rule at all" % FILING_PLAN_TEMPLATE)
    return list(live.get("rules") or []) + [one for one in examples if isinstance(one, dict)]


def test_every_retention_the_filing_plan_template_ships_is_readable_or_deliberately_empty():
    """A template value the register cannot read makes the register say so — at EVERY session start
    of every project that followed the template.

    Measured before this was fixed: the two rules the template tells a plan it always needs
    (`FP-900`, `FP-901`) carried prose spans, so a project that copied the block was met with
    "DEADLINE REGISTER INCOMPLETE" for as long as it existed — a warning that fires on the normal
    case is one nobody reads any more.

    Both ends: a rule may carry `null` to say "no span this watcher can count", and at least one
    example must still carry a readable span, or the template stops teaching the form and this test
    holds over nothing.
    """
    duties = duties_module()
    rules = shipped_filing_rules()
    assert len(rules) >= 4, "only %d rules read out of the template" % len(rules)
    unreadable, readable = [], 0
    for rule in rules:
        assert "retention" in rule, (
            "filing rule %s ships without a `retention` key at all, so a plan copied from this "
            "template has a drawer nothing watches" % rule.get("id"))
        value = rule.get("retention")
        if not value:
            continue
        if duties._retention_years(value) is None:
            unreadable.append((rule.get("id"), value))
        else:
            readable += 1
    assert not unreadable, (
        "the shipped filing plan hands a fresh project retention values `_duties._retention_years` "
        "cannot turn into a span, so its session start reports the register as INCOMPLETE forever. "
        "Write a countable span, or `null` with the reason beside it: %s" % unreadable)
    assert readable, (
        "no example carries a readable span any more — the template no longer teaches the form the "
        "watcher reads, and the assertion above is satisfied by emptiness")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))


def test_the_kernel_and_the_duty_register_read_a_retention_the_same_way():
    """ONE definition, two copies that cannot be merged -- so the agreement is measured (F6).

    `kernel.filing.retention_span` refuses a retention at the WRITE and `_duties._retention_years`
    watches it at every SESSION START. They have to be the same reading: a kernel that accepted
    what the register cannot count would put an unwatched rule in the plan -- reported as unwatched
    at every session start, forever -- and a kernel stricter than the register would refuse a rule
    the register would happily watch.

    WHY TWO COPIES AND NOT ONE, in both directions, because only one of them was written here until
    TSK-0120: the kernel may not import a kit hook, and the register may not require the kernel. The
    second half is the load-bearing one and it is measured -- with `$HARNESS_KERNEL_PATH` pointing
    at a directory that holds no kernel, `_duties.retention_duties` still answers while
    `_kernel.kernel_module("filing")` raises `KernelUnavailable`. Moving the register onto
    `kernel.filing.retention_span` (stream B's seam S6) would buy one definition at the price of a
    session-start register that goes silent whenever the kernel cannot be imported, which is the one
    moment a project most needs to hear its deadlines. So the copies stay and this holds them.

    THE DEFINITIONS ARE COMPARED, NOT SAMPLES, and that is verifier finding M2 of rework 1. A fixed
    list of examples measured only the words somebody happened to think of: adding `|jahren` to
    either reader, or `|monate` to the kernel's, left this test green while the two answers had
    already parted -- which is the exact drift F6 exists to prevent. So the compiled patterns
    themselves have to be the same object's worth of text, and the CORPUS is generated from the unit
    words BOTH patterns carry, so a unit added to one is a case the other is asked about.
    """
    import sys as _sys

    _sys.path.insert(0, TEAM_KITS)
    from kernel import filing

    register = duties_module()
    theirs, ours = register._SPAN_RX, filing._RETENTION_SPAN_RX
    assert (theirs.pattern, theirs.flags) == (ours.pattern, ours.flags), (
        "the two retention readers are no longer one definition:\n  register %r\n  kernel   %r"
        % (theirs.pattern, ours.pattern))

    units = sorted(_units_of(theirs.pattern) | _units_of(ours.pattern))
    assert len(units) > 3, units
    generated = ["8%s" % unit for unit in units] + ["10 %s" % unit for unit in units]
    shapes = ["8y (\u00a7 147 AO; mit der Steuerberatung best\u00e4tigen)", "30", "keine Frist",
              "solange das Produkt aktiv ist", "Version 1.8y", "P8Y", "", "   ", None, 8, True]
    disagreed = [one for one in generated + shapes
                 if register._retention_years(one) != filing.retention_span(one)]
    assert not disagreed, ["%r: register %r, kernel %r"
                           % (one, register._retention_years(one), filing.retention_span(one))
                           for one in disagreed]
    # ...and the corpus really exercises both answers, so an agreement on "None for everything"
    # cannot pass for one.
    spans = [filing.retention_span(one) for one in generated + shapes]
    assert any(one is not None for one in spans) and any(one is None for one in spans), spans


def _units_of(pattern):
    """The unit words a retention pattern accepts -- its own alternation, read off the pattern.

    Read rather than repeated, so the corpus above grows with whichever reader grows. The group
    this looks for is the one carrying alternatives; the digit group beside it carries none.
    """
    import re as _re

    found = set()
    for group in _re.findall(r"\(([^()]*\|[^()]*)\)", pattern):
        found.update(part for part in group.split("|") if part.isalpha())
    return found

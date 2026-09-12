#!/usr/bin/env python3
"""
Shared helper: the office project's DUTY REGISTER — what this business owes on a date, DERIVED from
the records it already keeps (FR-0034, FR-0038).

NOTHING HERE ACTS, and that is the shape of the feature rather than a caution: every feed answers
one question — "what dated obligation does this record imply" — and the caller prints the answer.
The user decides. For the routine feed — which lives in the shared `_routine` and is the one feed
this register does not own — that boundary is `DEC-0028` (a hook reports, the PM spawns); for the
rest it is the kit's approval-before-action line. No feed writes, files, pays, deletes or
dispatches, and `test_the_duty_register_writes_nothing_into_the_project_it_reads` measures it.

WHY ONE REGISTER AND NOT FIVE NOTICES: `session_status` already carried two hand-written nags of
this shape (the quarterly report, the compliance register) with two wordings, two failure behaviours
and no shared bound. A duty is `{what, due, source}`, so a new feed is a function here rather than
another paragraph over there, and one budget covers all of them.

A FEED THAT CANNOT READ ITS SOURCE SAYS SO instead of returning nothing. An empty register and an
unreadable one are not the same answer. The kit already draws that line one surface over, with the
reason written out: `session_status.main`'s "KIT MERGE BACKLOG UNREADABLE" notice.

THE HONEST LIMIT OF THE WHOLE REGISTER, once, here, so no feed repeats it: this kit records that
something is OWED, never that it was DONE. There is no submission record for a tax filing, no
payment record beyond the ledger's own column, no "handled" flag anywhere (`H113`). Two consequences
are built rather than promised, and each is measured:

  * NO FEED REACHES BACK OVER ITS OWN HISTORY. The tax feed names the period that just closed and
    not the ones before it; the retention feed names ONE review per RULE, however many year folders
    under it have run out. Before that second half existed, an archive kept by year since 2005 was
    thirteen duties under one rule
    (`tools/test_office_duties.py::test_a_rule_with_many_years_past_retention_is_one_duty_that_names_the_oldest_and_the_count`).
  * WHAT A FEED CAN STILL REPORT MANY OF is many DISTINCT open items — one unpaid invoice each, one
    review date each — so the paragraph `briefing` prints takes its slots one feed at a time
    (`_named_fairly`). A single loud source cannot push another feed's one duty out of what the
    manager reads, and that is where the defect was: thirteen archive folders from the 2000s took
    every slot from the tax deadline due that week
    (`tools/test_office_duties.py::test_no_feed_can_take_every_slot_of_the_briefing_from_another`).

A register that nagged about every period since the business started would be switched off in a
week, and then it protects nothing.
"""
import csv
import datetime
import os
import re
import sys
import time


# NO BYTECODE FROM A HOOK RUN, for the reason `_gate.py` states at length: this file lives in the
# hashed enforcement bundle, so caching it would change the bundle by being run.
sys.dont_write_bytecode = True

# THE SIBLINGS THIS MODULE REACHES ARE ITS OWN NEIGHBOURS (`_kernel`, `_routine`), and it puts its
# directory in front itself rather than relying on the hook that imported it — `_bookings` and
# `_filing` carry the same line. Without it the module is importable only from inside a hook
# process, and every measurement of it would have to be a measurement of the caller.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _routine     # the fifth feed, shared with the two kits that have no register (TSK-0112)


# THE CAP FOR THE WHOLE REGISTER, and it is this module's own promise: its caller is `session_status`,
# a SessionStart hook whose registration names no `timeout`, so what bounds it is the deadline the
# hooks give themselves (`_compat.HOOK_DEADLINE_SECONDS`) — and being killed there costs the session
# its ENTIRE briefing, not just this paragraph. The arithmetic is not spelled here, for the reason
# `_bookings.TOTAL_BUDGET` gives: `tools/test_office_duties.py::
# test_the_session_start_budgets_together_fit_inside_the_hook_deadline` reads this constant, the
# hook's git budget and the deadline off the modules, so raising either past the sum turns red.
# WHAT IT IS AGAINST: the ledger walk is linear in the ledger and the archive walk is one `listdir`
# per filing rule, so the worst case is a large ledger plus many rules — measured as the shipped
# hook process by `test_a_session_start_over_a_maximal_register_stays_inside_the_hook_deadline`.
TOTAL_BUDGET = 8

STATE_DIRNAME = "project_memory"
PROFILE = "business_profile.yaml"
FILING_PLAN = "filing_plan.yaml"
COMPLIANCE_REGISTER = "compliance_register.yaml"
LEDGER_DIR = "ledger"
ARCHIVE_DIR = "archive"

# How many duties one feed may put into the register, and how many the briefing NAMES. The first is
# a memory bound (an archive with a thousand year folders is a legal state); the second is what a
# session-start paragraph can carry without becoming the wall of text nobody reads.
MAX_PER_FEED = 200
MAX_NAMED = 6
# How many ledger YEARS the receivable feed opens, newest first. A COST bound and not a statement
# about how long an unpaid invoice stays worth chasing (`_ledger_files` carries that argument): the
# feed reads every year it opens row by row, so what this caps is the file count of one session
# start. WHAT IS PINNED IS THE FEED'S OBEDIENCE TO THE BOUND AND NOT THE NUMBER:
# `tools/test_office_duties.py::test_the_receivable_feed_opens_the_years_its_own_bound_names`
# sizes its ledger off this constant, so it turns red when the SLICE stops matching the constant and
# stays green when the number itself is raised or lowered. Changing the number is therefore a
# decision about cost that no test contradicts, which is why the argument for it stands here.
MAX_LEDGER_YEARS = 12


# The ledger's own columns, and the doc types that REDUCE the total of their own direction. Both
# belong to `scripts/ledger_add.py`; this is the reader's copy, and
# `test_the_receivable_feed_and_the_shipped_ledger_agree_on_what_reduces_a_total` compares it against
# the shipped script both ways — a reducing type added there, or one named here the ledger does not
# know, turns it red. Without that pairing an unpaid credit note would be dunned as a receivable.
LEDGER_DIRECTION = "direction"
LEDGER_DOC_TYPE = "doc_type"
LEDGER_DOC_DATE = "doc_date"
LEDGER_PAYMENT_DATE = "payment_date"
RECEIVABLE_DIRECTION = "income"
REDUCING_DOC_TYPES = ("reversal", "credit_note", "refund")

# A DIRECTORY NAME THAT DENOTES A CALENDAR YEAR — the property the retention feed walks on, rather
# than a list of the placeholder spellings a `path_template` may use for it (`<year>`, `<Jahr>`, …).
# A plan written in German and one written in English are then read the same way.
_YEAR_NAME_RX = re.compile(r"\A(\d{4})\Z")
# A RETENTION SPAN, read off the free text a rule carries (`"8y (§ 147 AO; …)"`). The unit words are
# the unavoidable half — a natural-language vocabulary — and the tripwire for it is the other branch:
# a retention this reader cannot turn into a span is REPORTED as unreadable, never treated as met
# (`test_a_retention_this_reader_cannot_parse_is_reported_rather_than_read_as_met`).
_SPAN_RX = re.compile(r"(?<![\w.])(\d{1,3})\s*(y|yr|yrs|year|years|j|jahr|jahre)(?![\w])", re.I)
_MONTHS_IN_A_YEAR = 12
# The one fiscal year this register can place a period in. A shifted fiscal year is a legitimate
# business and an unread source here, so it is named as unreadable rather than computed wrongly.
CALENDAR_FISCAL_YEAR = "calendar"


def _state_dir(root):
    import _kernel  # noqa: PLC0415 — the bridge is imported lazily, as in `_bookings._state_dir`
    return _kernel.state_dir(root)


def _read_yaml(path):
    """The document at `path`, `{}` when there is no file, `None` when there is one and it will not
    read. The three-way answer is the point: `None` is what a feed turns into an `unreadable` line."""
    if not os.path.isfile(path):
        return {}
    try:
        import yaml  # type: ignore[import-untyped]  # noqa: PLC0415
        with open(path, encoding="utf-8-sig") as handle:
            document = yaml.safe_load(handle)
    except BaseException:  # noqa: BLE001 — any failure here means "unknown", never "nothing"
        return None
    if document is None:
        return {}      # a file with nothing in it HAS no fields; that is an answer, not a failure
    return document if isinstance(document, dict) else None


# THE SHAPE OF A DUTY LIVES IN THE SHARED MODULE, so the register and the kit-independent
# routine notice cannot drift into two versions of the same three keys.
_duty = _routine.duty


def business_today(root):
    """(date, unreadable-line) — today in the BUSINESS's own time zone (BUG-0208).

    Until this existed the register read `datetime.date.today()`, so the answer belonged to whatever
    machine the session ran on: two machines in two zones answered the same question with two
    different dates, and nothing declared whose day was meant. `business.timezone` in the profile is
    that declaration, and it is the user's own field like every other source this register reads.

    THREE ANSWERS, and the third is the one that must not be silent: no declaration -> this
    machine's zone (the usual case, and the profile's comment says so); a resolvable IANA name ->
    that zone's date; a name this machine cannot resolve -> this machine's date PLUS a line for
    `unreadable`, because a deadline computed against a clock nobody asked for is exactly the
    quiet wrong answer the register exists to avoid.

    WHAT THIS DOES NOT MOVE, said here rather than left to be found: the register is computed once,
    at SessionStart, so a session that runs past midnight keeps the answer it started with. That is
    a property of the event and not of this reader -- there is no second occasion to read the clock
    at.
    """
    profile = _read_yaml(os.path.join(_state_dir(root), PROFILE))
    section = (profile or {}).get("business") if isinstance(profile, dict) else None
    zone = str((section or {}).get("timezone") or "").strip() if isinstance(section, dict) else ""
    if not zone:
        return datetime.date.today(), None
    try:
        from zoneinfo import ZoneInfo  # noqa: PLC0415 — stdlib since 3.9; the kit runs on 3.8 too
        return datetime.datetime.now(ZoneInfo(zone)).date(), None
    except BaseException as exc:  # noqa: BLE001 — an unresolvable zone is a reported fact
        return datetime.date.today(), (
            "%s declares business.timezone %r, which this machine cannot resolve (%s), so every "
            "date in this register is this machine's own" % (PROFILE, zone, exc.__class__.__name__))


def is_overdue(duty, today):
    return duty["due"] is not None and duty["due"] < today


def _end_of_month(year, month):
    if month == _MONTHS_IN_A_YEAR:
        return datetime.date(year, 12, 31)
    return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)


def _period_label(year, first_month, last_month):
    if first_month == last_month:
        return "%d-%02d" % (year, first_month)
    return "%d-%02d..%02d" % (year, first_month, last_month)


def _positive_int(value):
    number = _whole_number(value)
    return number if number is not None and number > 0 else None


def _whole_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def filing_duties(root, today):
    """What the business owes the tax office for the period that JUST CLOSED (FR-0034).

    Derived from `business_profile.yaml` -> `tax.filings`, which is the user's own declaration: a
    filing is a PERIOD LENGTH plus a LAG, and nothing here knows what a Umsatzsteuer-Voranmeldung is.
    That is deliberate — a kit that hard-coded German filing kinds would be wrong for the first
    business with a different one, and the deadline it printed would be a claim the kit cannot back.
    The legal basis is a field of the entry and travels with it into the notice, which is what
    `tools/test_office_duties.py::test_the_session_start_hook_names_the_tax_deadline_the_profile_declares`
    reads out of the shipped hook's own output.

    Only the last COMPLETED period, for the reason the module docstring gives: nothing records that a
    filing was submitted, so a feed that walked back through the year would nag about periods that
    were filed months ago.
    """
    duties, unreadable = [], []
    profile = _read_yaml(os.path.join(_state_dir(root), PROFILE))
    if profile is None:
        unreadable.append("%s exists and does not parse, so no tax deadline is derived from it"
                          % PROFILE)
        return duties, unreadable
    tax = profile.get("tax") if isinstance(profile.get("tax"), dict) else {}
    fiscal = str(tax.get("fiscal_year") or CALENDAR_FISCAL_YEAR).strip().lower()
    entries = tax.get("filings") or []
    if not isinstance(entries, list):
        unreadable.append("%s -> tax.filings is not a list, so no tax deadline is derived" % PROFILE)
        return duties, unreadable
    if entries and fiscal != CALENDAR_FISCAL_YEAR:
        unreadable.append(
            "%s -> tax.fiscal_year is %r; this register places periods in the CALENDAR year only, so "
            "it derives no tax deadline for this business" % (PROFILE, fiscal))
        return duties, unreadable
    for entry in entries[:MAX_PER_FEED]:
        if not isinstance(entry, dict):
            continue
        what = str(entry.get("what") or "").strip()
        months = _positive_int(entry.get("period_months"))
        lag = _whole_number(entry.get("due_days_after_period"))
        if not what or months is None or lag is None or _MONTHS_IN_A_YEAR % months:
            unreadable.append(
                "%s -> tax.filings entry %r needs a name, a `period_months` that divides the "
                "calendar year and a `due_days_after_period`; this one does not, so nothing here "
                "says when it is due" % (PROFILE, (what or str(entry))[:120]))
            continue
        year, closed = today.year, None
        for _ in range(2):
            for index in range(_MONTHS_IN_A_YEAR // months - 1, -1, -1):
                first, last = index * months + 1, (index + 1) * months
                if _end_of_month(year, last) < today:
                    closed = (year, first, last)
                    break
            if closed:
                break
            year -= 1
        if not closed:
            continue
        year, first, last = closed
        due = _end_of_month(year, last) + datetime.timedelta(days=lag)
        basis = str(entry.get("legal_basis") or "").strip()
        duties.append(_duty(
            "%s for %s%s" % (what, _period_label(year, first, last),
                             " (%s)" % basis if basis else ""),
            due, "%s tax.filings" % PROFILE))
    return duties, unreadable


def _literal_prefix(path_template):
    """The part of a `path_template` that is a real path — everything before its first placeholder.

    `gate_filing` reads the placeholders; this feed only needs the directory the rule's documents
    live under, and that is the literal head. A template with no placeholder is entirely literal.
    """
    text = str(path_template or "").replace("\\", "/")
    head = text.split("<", 1)[0]
    parts = [part for part in head.split("/") if part and part != "."]
    # A TEMPLATE THAT CLIMBS OR STARTS AT A ROOT NAMES NO PLACE IN THIS PROJECT. `gate_filing`
    # decides where a document may be FILED; nothing decides what a rule may SAY. This is the
    # SYNTACTIC half and it is not the guarantee — `_project_directory` below decides containment by
    # resolving, because reading the spelling was measured wrong in both directions at once.
    if any(part == ".." for part in parts) or os.path.isabs(head):
        return ""
    return "/".join(parts)


def _same_place(path):
    """`path` in the one spelling this module compares by: absolute, normalised, case-folded.

    TWO PATHS THAT NAME THE SAME PLACE MUST COMPARE EQUAL, and that is the whole reason this exists
    rather than a bare `==` on `abspath`: the platform decides whether case is part of a name, and
    where it is not, a rule spelled `Archive/` and a root spelled `archive/` are ONE place. That
    difference made the root guard in `_project_directory` answer about strings instead of about
    places (`tools/test_office_duties.py::test_a_filing_plan_that_resolves_to_the_project_ROOT_is_not_walked`),
    and the fold itself is measured against the platform's own answer in
    `tools/test_office_duties.py::test_the_place_reader_folds_case_exactly_where_the_platform_does`.
    `normpath` is already inside `abspath`, so here it adds nothing and stands for a caller that
    hands in a path this module did not build.
    """
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _project_directory(root, path_template):
    """The real directory a rule's documents lie under, or `None` when it is not in this project.

    CONTAINMENT IS ANSWERED BY RESOLVING, never by inspecting the spelling, and that is the whole
    point of this function: the spelling reader before it refused a drive letter in the FIRST path
    component and let one in a later component through, while `os.path.join` lets the later one win
    — `a/b/D:/<year>/` resolved to `D:` and a session start listed the current directory of another
    drive. Every class of "not in this project" is a case of
    `tools/test_office_duties.py::test_a_filing_plan_that_names_a_place_outside_the_project_is_not_walked`,
    including the control that an ordinary rule still resolves; the project ROOT is its own case in
    `tools/test_office_duties.py::test_a_filing_plan_that_resolves_to_the_project_ROOT_is_not_walked`.
    """
    prefix = _literal_prefix(path_template)
    if not prefix:
        return None
    directory = os.path.abspath(os.path.join(root, *prefix.split("/")))
    base, candidate = _same_place(root), _same_place(directory)
    try:
        common = _same_place(os.path.commonpath([base, candidate]))
    except ValueError:      # two different drives have no common path at all
        return None
    # INSIDE THE PROJECT **AND NOT THE PROJECT ITSELF**. The second half is not tidiness: the root is
    # not an archive, so a template that resolves back to it turns every four-digit directory the
    # project has into an archive year. Comparing raw strings missed it -- `....//<year>/` resolves
    # to the root WITH a trailing separator, which is the same place and a different string.
    if common != base or candidate == base:
        return None
    return directory


def _retention_years(text):
    match = _SPAN_RX.search(str(text or ""))
    return int(match.group(1)) if match else None


def retention_duties(root, today):
    """Archive years whose rule's retention has run out (FR-0034, F2 of `docs/office-kit-from-field.md`).

    `filing_plan.yaml` carries `retention` per rule and until now nobody watched it. What is watched
    here is the pair (rule, year folder): a folder whose name denotes a calendar year, directly under
    the rule's literal path, is the unit German filing actually uses. The due date is the 31st of
    December `retention` years after that year, because the statutory clock starts at the END of the
    calendar year the last entry belongs to (§ 147 Abs. 4 AO) — an honesty note that also stands in
    the template the rules come from, and the template is where a user can correct it.

    ONE RULE IS ONE DUTY — review this drawer — and the year folders under it are its reasons, not
    duties of their own. A business that has filed by year since 2005 is an ordinary business, and
    reporting thirteen of them separately was the register accumulating a past it claimed not to
    accumulate; the oldest year and the COUNT travel into the duty instead, so collapsing them
    trades no over-report for an under-report.

    WHAT IT DOES NOT SEE, so no caller has to guess: a rule whose archive is not partitioned by year
    produces no duty at all (`test_a_rule_whose_archive_is_not_year_partitioned_produces_no_retention_duty`),
    and NOTHING here deletes — the duty is to REVIEW. What the kit's own wall (`guard_fs_tripwire`)
    does and does not stop is written at that guard's own head, and it is not repeated here.
    """
    duties, unreadable = [], []
    plan = _read_yaml(os.path.join(_state_dir(root), FILING_PLAN))
    if plan is None:
        unreadable.append("%s exists and does not parse, so no retention is watched" % FILING_PLAN)
        return duties, unreadable
    rules = plan.get("rules") or []
    if not isinstance(rules, list):
        return duties, unreadable
    for rule in rules[:MAX_PER_FEED]:
        if not isinstance(rule, dict):
            continue
        retention = rule.get("retention")
        rule_id = str(rule.get("id") or rule.get("path_template") or "?")
        if not retention:
            continue
        span = _retention_years(retention)
        if span is None:
            unreadable.append(
                "filing rule %s keeps its documents for %r and this reader cannot turn that into a "
                "number of years, so its retention is watched by nothing" % (rule_id, retention))
            continue
        prefix = _literal_prefix(rule.get("path_template"))
        directory = _project_directory(root, rule.get("path_template"))
        if directory is None or not os.path.isdir(directory):
            continue
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            unreadable.append("filing rule %s points at %s, which could not be listed here"
                              % (rule_id, prefix))
            continue
        expired = []
        for name in names:
            match = _YEAR_NAME_RX.match(name)
            if not match or not os.path.isdir(os.path.join(directory, name)):
                continue
            year = int(match.group(1))
            if year + span > datetime.MAXYEAR:
                continue     # a folder named far in the future has no reachable retention date
            if datetime.date(year + span, 12, 31) >= today:
                continue
            expired.append(year)
        if not expired:
            continue
        oldest = min(expired)
        duties.append(_duty(
            "%d year folder(s) under %s/ are past their retention (%s), the oldest being %d — "
            "review them with the user; nothing here deletes"
            % (len(expired), prefix, retention, oldest),
            datetime.date(oldest + span, 12, 31), "%s rule %s" % (FILING_PLAN, rule_id)))
        if len(duties) >= MAX_PER_FEED:
            return duties, unreadable
    return duties, unreadable


def _ledger_files(root):
    """The ledger years this project keeps, newest first, bounded by `MAX_LEDGER_YEARS`.

    EVERY year rather than the current two: an invoice nobody paid three years ago is exactly the one
    a business wants named, and a window of two would have hidden it while looking like a watcher
    (`tools/test_office_duties.py::test_an_open_invoice_from_an_earlier_year_is_still_a_candidate`).
    The bound is what keeps a session start from walking a decade of ledgers, and where it falls is
    `tools/test_office_duties.py::test_the_receivable_feed_opens_the_years_its_own_bound_names`.
    """
    directory = os.path.join(root, LEDGER_DIR)
    if not os.path.isdir(directory):
        return []
    years = sorted((name for name in os.listdir(directory)
                    if name.endswith(".csv") and _YEAR_NAME_RX.match(name[:-len(".csv")])),
                   reverse=True)
    return [os.path.join(directory, name) for name in years[:MAX_LEDGER_YEARS]]


def _iso_date(text):
    try:
        return datetime.datetime.strptime(str(text or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def receivable_duties(root, today):
    """Invoices the business has not been paid for, past its OWN payment terms (FR-0034).

    The terms come from `business_profile.yaml` -> `receivables.payment_terms_days`, so the kit
    invents no dunning policy: with the field unset there is no duty
    (`tools/test_office_duties.py::test_without_payment_terms_the_ledger_produces_no_dunning_candidate`)
    rather than one on an assumed 14 or 30 days.

    A receivable is an income row whose doc type does not REDUCE its own direction and whose
    `payment_date` is empty — the ledger's own vocabulary, held against the shipped script by
    `test_the_receivable_feed_and_the_shipped_ledger_agree_on_what_reduces_a_total`.
    """
    duties, unreadable = [], []
    profile = _read_yaml(os.path.join(_state_dir(root), PROFILE))
    if profile is None:
        return duties, unreadable      # `filing_duties` reports the same file; twice is noise
    section = profile.get("receivables") if isinstance(profile.get("receivables"), dict) else {}
    terms = _positive_int(section.get("payment_terms_days"))
    if terms is None:
        return duties, unreadable
    for path in _ledger_files(root):
        try:
            with open(path, encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if str(row.get(LEDGER_PAYMENT_DATE) or "").strip():
                        continue
                    if str(row.get(LEDGER_DIRECTION) or "").strip() != RECEIVABLE_DIRECTION:
                        continue
                    if str(row.get(LEDGER_DOC_TYPE) or "").strip() in REDUCING_DOC_TYPES:
                        continue
                    issued = _iso_date(row.get(LEDGER_DOC_DATE))
                    if issued is None:
                        continue
                    due = issued + datetime.timedelta(days=terms)
                    if due >= today:
                        continue
                    duties.append(_duty(
                        "invoice %s to %s is unpaid %d day(s) past your %d-day terms"
                        % (str(row.get("invoice_no") or row.get("id") or "?"),
                           str(row.get("counterparty") or "?"), (today - due).days, terms),
                        due, os.path.relpath(path, root).replace(os.sep, "/")))
                    if len(duties) >= MAX_PER_FEED:
                        return duties, unreadable
        except OSError:
            unreadable.append("%s could not be read, so its open invoices are not counted"
                              % os.path.relpath(path, root).replace(os.sep, "/"))
    return duties, unreadable


def review_duties(root, today):
    """Wiedervorlagen: the dated re-looks this project's own records ask for (FR-0034).

    Today that is `compliance_register.yaml` -> `review_by`, which `session_status` used to count in a
    notice of its own. It is a feed here instead, so that one surface names everything that is due
    rather than two paragraphs naming half each; nothing was lost in the move, and
    `tools/test_office_duties.py::test_the_review_dates_the_compliance_notice_used_to_carry_are_still_named`
    is the regression guard on that.
    """
    duties, unreadable = [], []
    document = _read_yaml(os.path.join(_state_dir(root), COMPLIANCE_REGISTER))
    if document is None:
        unreadable.append("%s exists and does not parse, so its review dates are watched by nothing"
                          % COMPLIANCE_REGISTER)
        return duties, unreadable
    for entry in (document.get("register") or [])[:MAX_PER_FEED]:
        if not isinstance(entry, dict):
            continue
        due = _iso_date(entry.get("review_by"))
        if due is None or due >= today:
            continue
        duties.append(_duty(
            "compliance entry %s is past its review date"
            % str(entry.get("id") or entry.get("topic") or entry.get("title") or "?"),
            due, COMPLIANCE_REGISTER))
    return duties, unreadable


# THE FIVE SOURCES OF A DUTY. The fifth is not an office question and does not live here: the
# feed is the shared `_routine` module, and this register is one of its two callers (the other
# is the session briefing of a kit that has no register). `TSK-0112` cut it out, and the claim
# that made it worth cutting is measured over all three kits rather than stated here:
# `tools/test_routine_feed.py::test_the_audited_role_is_a_role_every_kit_ships` and
# `tools/test_routine_feed.py::test_the_routine_notice_appears_and_clears_in_every_kit_that_ships_it`.
FEEDS = (filing_duties, retention_duties, receivable_duties, review_duties,
         _routine.routine_duties)


def register(root, today=None, budget=None):
    """(duties, unreadable) for the whole project — every feed, inside one budget.

    The budget is checked BETWEEN feeds, so a feed that has started always finishes: a half-run feed
    would report half a register as if it were all of it, and that is the one answer this module may
    not give. A feed left unrun is named in `unreadable` instead.

    Every duty carries the `feed` that found it, which is what lets `_named_fairly` share the
    briefing's slots out by source rather than by date.
    """
    duties, unreadable = [], []
    if today is None:
        today, zone_problem = business_today(root)
        if zone_problem:
            unreadable.append(zone_problem)
    deadline = time.monotonic() + (TOTAL_BUDGET if budget is None else budget)
    for feed in FEEDS:
        if time.monotonic() > deadline:
            unreadable.append(
                "the %g s this register gives itself ran out before %s ran, so what it asks for is "
                "not in this list" % (TOTAL_BUDGET, feed.__name__))
            continue
        try:
            found, problems = feed(root, today)
        except BaseException as exc:  # noqa: BLE001 — a briefing must never refuse a session
            found = []
            problems = ["%s could not be derived here (%s)"
                        % (feed.__name__, exc.__class__.__name__)]
        for one in found:
            one["feed"] = feed.__name__
        duties += found
        unreadable += problems
    duties.sort(key=lambda one: (one["due"] or datetime.date.max, one["what"]))
    return duties, unreadable


def _named_fairly(duties, limit):
    """At most `limit` of `duties`, taken one FEED at a time and nearest-due first within each.

    THE SLOTS ARE SHARED BY SOURCE, NOT BY DATE, and that is the whole of it: a business can have
    one duty that costs money this week and fifty that have been waiting since 2013, and a paragraph
    filled strictly by date is a paragraph about 2013. `MAX_NAMED >= len(FEEDS)` is what makes every
    speaking feed reachable, and
    `tools/test_office_duties.py::test_no_feed_can_take_every_slot_of_the_briefing_from_another`
    asserts that arithmetic rather than trusting it.
    """
    # Grouped by the key the duty carries, so a duty that reached here without one keeps a queue of
    # its own instead of dropping out of the paragraph.
    queues = []
    for key in list(dict.fromkeys([feed.__name__ for feed in FEEDS]
                                  + [one.get("feed") for one in duties])):
        queue = [one for one in duties if one.get("feed") == key]
        if queue:
            queues.append(queue)
    chosen, depth = [], 0
    while len(chosen) < limit and any(len(queue) > depth for queue in queues):
        for queue in queues:
            if len(chosen) >= limit:
                break
            if len(queue) > depth:
                chosen.append(queue[depth])
        depth += 1
    return sorted(chosen, key=lambda one: (one["due"] or datetime.date.max, one["what"]))


def briefing(root, today=None):
    """The one session-start paragraph, or "" when this project owes nothing it can see.

    It PROPOSES. The sentence says so, because the surface a reminder appears on is where an agent
    decides whether it may act — and every other feed of this kit that names a deadline is an
    approval-before-action surface too.
    """
    # THE CLOCK IS READ ONCE per briefing and handed down: two reads could fall on either side of a
    # midnight, and then the paragraph would call a duty overdue that its own list dates tomorrow.
    zone_problem = None
    if today is None:
        today, zone_problem = business_today(root)
    duties, unreadable = register(root, today)
    if zone_problem:
        unreadable.insert(0, zone_problem)
    if not duties and not unreadable:
        return ""
    parts = []
    if duties:
        overdue = [one for one in duties if is_overdue(one, today)]
        named = _named_fairly(duties, MAX_NAMED)
        parts.append(
            "DUE / OVERDUE (%d, %d of them past their date): %s%s. This register PROPOSES — it "
            "files nothing, pays nothing, deletes nothing and spawns nothing — and it records no "
            "'done': every entry stands until its own source changes (a period closes, a payment "
            "date is entered, a folder is emptied, a run happens). Put what matters to the user in "
            "your FIRST paragraph and let them decide."
            % (len(duties), len(overdue),
               "; ".join("%s [by %s, %s]" % (one["what"], one["due"].isoformat(), one["source"])
                         if one["due"] else "%s [%s]" % (one["what"], one["source"])
                         for one in named),
               " …" if len(duties) > len(named) else ""))
    if unreadable:
        parts.append(
            "DEADLINE REGISTER INCOMPLETE: %s. Do not read a short list as a quiet business — tell "
            "the user which source could not be read." % "; ".join(unreadable[:MAX_NAMED]))
    return " ".join(parts)

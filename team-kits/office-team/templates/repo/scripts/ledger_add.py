#!/usr/bin/env python3
"""
ledger_add.py — the validated write path into the ledger, and its validator.

An LLM editing a CSV of money data is the wrong tool, so this script validates every row and
refuses bad data. It is the PREFERRED write path, not the only one: user decision I.3/1 removed
the append-only rule (and `guard_ledger_direct` with it) because refusing every hand edit did not
make the data trustworthy — it made fixing a typo cost a reversal entry. Direct Edit/Write on
ledger/*.csv is therefore ALLOWED and always validation-required: `gate_ledger_valid` re-validates
the whole file afterwards and marks the ledger broken if it no longer holds (spec II.9).

Corrections are still best expressed as reversal entries (--doc-type reversal --reverses <id>) —
that keeps the history readable — but a correction by edit is legitimate, and git history plus the
Evidence trail is what makes it auditable. This is GoBD-INSPIRED bookkeeping, NOT certified
revision-safe archiving; the reports say so too.

ONE VALIDATION CORE: `validate_row` + `validate_cross` are used by BOTH the append path and
`--validate`, so the two cannot drift into disagreeing about what a valid ledger is. Everything
they accept must also be parseable by `euer_report.py`, which reads the CSV with a bare `float()`
— that is why comma decimals are refused here even though Python would parse them.

Usage (bookkeeper):
  python scripts/ledger_add.py --year 2026 --direction expense --doc-type invoice \
    --doc-date 2026-07-01 --payment-date 2026-07-03 --counterparty "Muster GmbH" \
    --invoice-no RE-2026-114 --net 100.00 --vat-rate 19 --gross 119.00 \
    --vat-treatment standard --category shipping --source "archive/finance/.../file.pdf"
  # unpaid: --open instead of --payment-date;  reversal: --doc-type reversal --reverses <id>

Exit 0 = appended. Exit 1 = refused (reason on stderr) — fix the DATA.
  python scripts/ledger_add.py --validate ledger/2026.csv   # whole-file check; clears the block
  python scripts/ledger_add.py --import rows.csv --year 2026  # validate MERGED, then save atomically

SAVING IS ATOMIC AND VALIDATES THE RESULT, not the increment (disposition row 310). A plain
append writes into the live file: if the process dies mid-write the ledger keeps half a row, and
`--validate` then reports a broken file that no edit caused. Every write here builds the complete
new content, validates THAT, and only then replaces the file in one `os.replace`.
"""
import argparse
import csv
import datetime
import io
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLUMNS = ["id", "doc_date", "payment_date", "direction", "doc_type", "counterparty",
           "invoice_no", "net", "vat_rate", "gross", "vat_treatment", "category", "source",
           "reverses", "note"]
DIRECTIONS = ("income", "expense")
DOC_TYPES = ("invoice", "credit_note", "refund", "fee", "reversal", "other")
VAT_TREATMENTS = ("standard", "reverse_charge", "kleinunternehmer", "oss", "exempt")
# Doc types that REDUCE the total of their own direction. Must stay identical to
# `euer_report.py`'s list -- that script signs these -1, and a validator that does not know the
# consumer's arithmetic cannot tell a correct ledger from one that reports double.
NEGATIVE_DOC_TYPES = ("reversal", "credit_note", "refund")
# The reversal graph rules apply to `reversal` only: a credit note stands on its own document and
# does not have to name a target.


def refuse(msg):
    """Exit 1 with the reason. Raises SystemExit, so a `finally: unlock(...)` still runs."""
    sys.stderr.write("[ledger_add] REFUSED: %s\n" % msg)
    sys.exit(1)


def read_amount(raw):
    """(value, error). DOT decimals only, and finite.

    `float()` happily returns `nan` and `inf` for the strings "nan"/"inf", and both then propagate
    silently: `nan` compares False against every threshold, so the arithmetic check passes, and the
    EÜR totals print as `nan` in a document that goes to a tax office. A comma decimal is refused
    for a different reason -- `euer_report.py` parses with a bare `float()`, so "1234,56" would
    pass validation here and crash the report; a validator must not accept what the consumer
    cannot read.
    """
    text = str(raw if raw is not None else "").strip()
    if not text:
        return None, "is empty"
    if "," in text:
        return None, ("%r uses a comma decimal separator — write 1234.56; the reports parse the "
                      "CSV with float() and would fail on this row" % text)
    try:
        value = float(text)
    except ValueError:
        return None, "%r is not a number" % text
    if not math.isfinite(value):
        return None, "%r is not a finite amount" % text
    if value < 0:
        return None, ("%r is negative — direction/doc_type carry the sign (use "
                      "credit_note/reversal)" % text)
    return round(value, 2), None


def validate_row(row, where):
    """Every rule that judges ONE row, in one place.

    Both callers use it: `--validate` per line, and the append path on the row it is about to
    write. Two separate implementations is what this replaced, and they had already drifted --
    the append path required a reversal to name its target while the file check did not, so a
    ledger that `--validate` called clean could not have been produced by the script.
    """
    findings = []
    for field, required in (("doc_date", True), ("payment_date", False)):
        value = (row.get(field) or "").strip()
        if not value:
            if required:
                findings.append("%s: %s is required" % (where, field))
            continue
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            findings.append("%s: %s %r is not a YYYY-MM-DD date" % (where, field, value))

    for field, allowed in (("direction", DIRECTIONS), ("doc_type", DOC_TYPES),
                           ("vat_treatment", VAT_TREATMENTS)):
        if (row.get(field) or "") not in allowed:
            findings.append("%s: %s %r is not one of %s"
                            % (where, field, row.get(field), "/".join(allowed)))
    for field in ("counterparty", "category", "source"):
        if not (row.get(field) or "").strip():
            findings.append("%s: %s is required" % (where, field))

    amounts = {}
    for field in ("net", "gross", "vat_rate"):
        value, error = read_amount(row.get(field))
        if error:
            findings.append("%s: %s %s" % (where, field, error))
        else:
            amounts[field] = value
    if len(amounts) == 3:
        net, gross, rate = amounts["net"], amounts["gross"], amounts["vat_rate"]
        expected = round(net * (1 + rate / 100.0), 2)
        if abs(expected - gross) > 0.011:
            findings.append("%s: net %.2f * (1 + %.2f%%) = %.2f != gross %.2f — re-read the "
                            "document; a value you cannot read is UNCLEAR, never guessed"
                            % (where, net, rate, expected, gross))
        if row.get("vat_treatment") in ("reverse_charge", "kleinunternehmer", "exempt"):
            if rate != 0:
                findings.append("%s: vat_rate must be 0 for %s (the treatment field carries the "
                                "tax logic)" % (where, row.get("vat_treatment")))
            if abs(net - gross) > 0.011:
                findings.append("%s: net must equal gross for %s (no VAT in the amount)"
                                % (where, row.get("vat_treatment")))

    target = (row.get("reverses") or "").strip()
    if row.get("doc_type") == "reversal" and not target:
        findings.append("%s: a reversal entry must name the entry it reverses (`reverses`)" % where)
    if target and row.get("doc_type") != "reversal":
        findings.append("%s: sets `reverses` but is not a reversal" % where)
    if target and target == (row.get("id") or "").strip():
        findings.append("%s: reverses itself" % where)
    return findings


# A ledger file is `<4-digit-year>.csv` — what `euer_report.py` actually reads (`ledger/%d.csv`).
# Globbing `*.csv` made every other CSV in the directory an ID SOURCE that the report never sees:
# a `scratch.csv` holding a row with the reversed id let a reversal of a booking-that-is-not-there
# validate clean, and the quarter then reported a NEGATIVE total. A human's `2026 - Kopie.csv` does
# the same by accident, which is why the non-numeric basename is refused rather than skipped.
YEAR_FILE_RX = re.compile(r"^[0-9]{4}\.csv$", re.IGNORECASE)

_SIBLING_CACHE = {}


def sibling_index(year):
    """{id: row} across the OTHER year files, built once per process.

    Re-reading and re-parsing every sibling for every unresolved target was quadratic: 12 files x
    4 300 rows with 300 dangling targets took 56s for ONE `--validate`, and the gate multiplied
    that by the file count until the host killed the hook — which is a non-blocking error, so the
    commit went through. Even the honest case paid it: 12 x 2 000 rows with 40 real cross-year
    stornos cost 17s per commit and 6.5s per append.

    `os.listdir`, not `glob`: a project path containing `[` made `glob` return zero files, so a
    legitimate year-boundary storno was reported as "exists in no ledger file" and the repo was
    permanently blocked by a message pointing at a data error that did not exist.
    """
    key = str(year)
    if key in _SIBLING_CACHE:
        return _SIBLING_CACHE[key]
    index, reversed_elsewhere, homes = {}, {}, {}
    directory = os.path.join(ROOT, "ledger")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        names = []
    for name in names:
        if not YEAR_FILE_RX.match(name) or os.path.splitext(name)[0] == key:
            continue
        rows, error = read_ledger(os.path.join(directory, name))
        if error:
            continue
        for row in rows:
            rid = (row.get("id") or "").strip()
            if not rid:
                continue
            homes.setdefault(rid, set()).add(name)
            if rid in index:
                # AMBIGUOUS, and silently so before: the index kept whichever file sorted first
                # and reported nothing, so a reversal bound to that row. With `L2025-0001` in both
                # 2025.csv (119,00) and 2026.csv (1190,00), a 2027 reversal of 119,00 validated
                # clean against the 2025 row while the 1190,00 booking stayed on the books
                # uncancelled — and the direction/gross check confirmed the row the operator did
                # not mean. Ids are the ledger's only cross-file reference; two rows cannot share
                # one, so the entry is poisoned and nothing may bind to it.
                index[rid] = None
                continue
            index[rid] = row
            target = (row.get("reverses") or "").strip()
            if target and row.get("doc_type") == "reversal":
                reversed_elsewhere.setdefault(target, "%s (%s)" % (name, rid or "no id"))
    duplicates = {rid: sorted(files) for rid, files in homes.items() if len(files) > 1}
    _SIBLING_CACHE[key] = (index, reversed_elsewhere, duplicates, homes)
    return _SIBLING_CACHE[key]


def _reversal_matches(where, row, target_row, target):
    """A reversal must cancel what it names — same direction, same gross.

    The graph rules alone said nothing about CONTENT: an expense of 119,00 could be reversed by an
    `income` row of 1190,00, both individually valid, and the quarter then reported -1190,00 EUR
    income. Same failure class as a reversal-of-a-reversal, through a different door.
    """
    findings = []
    if target_row.get("doc_type") == "reversal":
        findings.append("%s: reverses %s, which is itself a reversal — the reports subtract every "
                        "reversal, so this would book the amount negative" % (where, target))
        return findings
    if (row.get("direction") or "") != (target_row.get("direction") or ""):
        findings.append("%s: reverses %s but is %r while %s is %r — a reversal cancels an entry, "
                        "so it sits on the same side"
                        % (where, target, row.get("direction"), target, target_row.get("direction")))
    mine, _ = read_amount(row.get("gross"))
    theirs, _ = read_amount(target_row.get("gross"))
    if mine is not None and theirs is not None and abs(mine - theirs) > 0.011:
        findings.append("%s: reverses %s (%.2f) but is %.2f — a reversal cancels the FULL amount; "
                        "for a partial correction book a credit_note"
                        % (where, target, theirs, mine))
    return findings


def is_malformed(row):
    """Does this row's SHAPE disagree with the header? -- one spelling, two readers.

    `csv.DictReader` files the overflow of a too-long row under the `None` key and pads a too-short
    one with a `None` value, so both shapes are one question. Both the per-row report and
    `validate_cross` ask it here rather than each for itself: the second reader is the one that used
    to sort such a row's column names and raise `TypeError` instead of leaving the finding to the
    first (`tools/test_hooks_v2.py::test_a_malformed_existing_row_stops_the_write`).
    """
    return None in row or None in row.values()


def validate_cross(rows, year=""):
    """Every rule that needs the OTHER rows: identity, the year, duplicates, the reversal graph.

    `rows` is a list of (line_label, row). The reversal graph is checked as a GRAPH because
    `euer_report.py` sums a reversal with sign -1: a reversal OF a reversal subtracts twice, so a
    booked-then-reversed 119 EUR expense reported as -119 EUR, and two reversals of one original
    do the same. Nothing else in the pipeline would notice -- the report has no reason to suspect
    its input, and a negative expense total looks like a data-entry mistake, not a rule gap.

    A ROW WHOSE SHAPE IS BROKEN IS NOT A SUBJECT HERE, and that is not tidiness: csv files the
    OVERFLOW of an unquoted comma under the `None` key, and the duplicate reading sorts the row's
    own column names -- so one hand-edited line with a stray comma raised
    `TypeError: '<' not supported between 'NoneType' and 'str'` out of the middle of a validation
    that had already produced the right finding one line earlier (measured 2026-09-12 on the append
    path: a traceback instead of "wrong number of columns"). The caller reports those rows through
    `is_malformed`; comparing them with each other says nothing on top of that.
    """
    rows = [(where, row) for where, row in rows if not is_malformed(row)]
    findings, seen_ids, invoices = [], {}, {}
    by_id = {}
    for where, row in rows:
        rid = (row.get("id") or "").strip()
        if not rid:
            findings.append("%s: missing id" % where)
        elif rid in seen_ids:
            findings.append("%s: duplicate id, first seen at %s" % (where, seen_ids[rid]))
        else:
            seen_ids[rid] = where
            by_id[rid] = row

        effective = ((row.get("payment_date") or "").strip()
                     or (row.get("doc_date") or "").strip())[:4]
        if year and str(year).isdigit() and effective and effective != str(year):
            findings.append("%s: %s year %s does not belong in ledger/%s.csv — book it into "
                            "ledger/%s.csv; year-boundary invoices are routine and an entry in the "
                            "wrong file silently vanishes from EVERY report"
                            % (where, "payment" if (row.get("payment_date") or "").strip()
                               else "document", effective, year, effective))

    # ...INCLUDING reversals booked in another year's file. `cancelled` was per file while the
    # cross-file lookup was not, so `2026.csv` and `2027.csv` could each reverse the same 2025
    # booking: all three files validated clean and the reports subtracted the amount twice. That is
    # exactly what the same-file rule refuses, walked around through the door B12 opened.
    index, reversed_elsewhere, duplicates, homes = sibling_index(year)
    for rid, files in sorted(duplicates.items()):
        findings.append("id %s exists in more than one ledger file (%s) — ids are the only "
                        "cross-file reference the books have, so a reversal cannot say which row "
                        "it cancels" % (rid, ", ".join(files)))
    # ...and the same id appearing BOTH here and in a sibling file
    for rid in sorted(seen_ids):
        if rid in index and rid not in duplicates:
            # NAME the other file: across a decade of year files, "another ledger file" is a
            # manual search, and `homes` already holds the answer.
            others = ", ".join(sorted(homes.get(rid) or [])) or "another ledger file"
            findings.append("id %s also exists in %s — renumber one of them" % (rid, others))
    cancelled = {}
    for where, row in rows:
        target = (row.get("reverses") or "").strip()
        if not target or row.get("doc_type") != "reversal":
            continue
        if target in reversed_elsewhere:
            findings.append("%s: %s is already reversed in %s — a second reversal subtracts the "
                            "amount twice" % (where, target, reversed_elsewhere[target]))
        if target not in seen_ids:
            # A year-boundary storno is routine: an invoice paid 2025-12-22 and reversed
            # 2026-01-17 belongs in 2026.csv by the payment-year rule, while its target lives in
            # 2025.csv. Demanding "same file" made that entry impossible to book in EITHER file,
            # and the only remaining construct was a credit note -- which is a different document
            # with different legal meaning.
            elsewhere = index.get(target)
            if elsewhere is None:      # absent, or present in two files and therefore ambiguous
                findings.append("%s: reverses %s, which exists in no ledger file" % (where, target))
            else:
                findings.extend(_reversal_matches(where, row, elsewhere, target))
            continue
        findings.extend(_reversal_matches(where, row, by_id[target], target))
        if target in cancelled:
            findings.append("%s: %s is already reversed at %s — a second reversal subtracts the "
                            "amount twice" % (where, target, cancelled[target]))
        else:
            cancelled[target] = where

    for where, row in rows:
        invoice = (row.get("invoice_no") or "").strip()
        if not invoice or row.get("doc_type") == "reversal":
            continue
        gross, _ = read_amount(row.get("gross"))
        key = (row.get("counterparty"), invoice, gross)
        invoices.setdefault(key, []).append((where, (row.get("id") or "").strip()))
    for key, hits in invoices.items():
        live = [(where, rid) for where, rid in hits if rid not in cancelled]
        if len(live) > 1:
            findings.append("duplicate invoice %s / %s booked %d times (%s) — a correction needs a "
                            "reversal, not a second booking"
                            % (key[0], key[1], len(live), ", ".join(w for w, _ in live)))

    # ...AND THE SAME BOOKING WITHOUT AN INVOICE NUMBER (`BUG-0182`). The rule above needs
    # `invoice_no`, which a receipt, a fee or a bank charge often does not have -- so two rows that
    # differ in NOTHING BUT THEIR ID were a double booking of one voucher that every layer let
    # through: `gate_second_booking` pairs its readings on `source`, so both rows were covered by
    # ONE reading pair, and this validator asked only about ids and invoice numbers.
    #
    # THE KEY IS THE WHOLE ROW MINUS THE ID, and that is the definition rather than a choice of
    # columns: the id is allocated at write time and is the one field two bookings of one voucher
    # cannot share, so everything else agreeing IS the duplicate. A business that really books one
    # voucher twice (two identical positions) makes them distinguishable -- the `note` column is
    # there for that -- and the finding says so.
    same = {}
    for where, row in rows:
        rid = (row.get("id") or "").strip()
        if row.get("doc_type") == "reversal" or rid in cancelled:
            continue
        key = tuple(sorted((name, str(value)) for name, value in row.items() if name != "id"))
        same.setdefault(key, []).append(where)
    for key, places in sorted(same.items()):
        if len(places) > 1:
            findings.append("the same booking stands %d times and differs only in its id (%s) — "
                            "one voucher booked twice. If both are real, tell them apart in `note`; "
                            "if one is a mistake, a correction needs a reversal, not a deletion"
                            % (len(places), ", ".join(places)))
    return findings


def read_ledger(path):
    """(rows, error). The one reader — `--validate`, append and `--import` must see one file."""
    if not os.path.isfile(path):
        return [], None
    try:
        with open(path, "rb") as raw:
            if raw.read(3).startswith(b"\xef\xbb\xbf"):
                return None, ("%s starts with a UTF-8 BOM — save it as UTF-8 without BOM; the "
                              "reports read the header literally and would not find the `id` "
                              "column" % path)
        with open(path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != COLUMNS:
                return None, ("header does not match the schema (expected: %s)"
                              % ", ".join(COLUMNS))
            return list(reader), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, "%s cannot be read (%s)" % (path, type(exc).__name__)


def save_atomically(path, rows):
    """Write the WHOLE ledger, then swap it in with one rename.

    Appending in place is not atomic: a crash, a full disk or a killed process leaves a partial
    final row, and the next `--validate` reports a corrupt ledger that nobody edited. Building the
    complete content in a sibling temp file and calling `os.replace` means the ledger is either
    the old file or the new one — never half of either. The temp file is a SIBLING because
    `os.replace` is only atomic within one filesystem.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in COLUMNS})
    tmp = os.path.join(directory, ".%s.tmp-%d" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(buf.getvalue())
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        refuse("could not save %s (%s) — the ledger is unchanged" % (path, exc))


def next_id(year, rows):
    """The first free `L<year>-nnnn`, by SCANNING the ids present.

    `len(rows) + 1` looked equivalent and was not: delete one mistaken row -- legal since I.3/1 --
    and the counter starts re-issuing an id that is still in the file. The ledger stays valid, and
    both write paths then refuse forever with "duplicate id", offering no remedy but the hand edit
    this script exists to avoid.
    """
    used = set()
    for row in rows:
        rid = (row.get("id") or "").strip()
        if rid.startswith("L%d-" % year) and rid[len("L%d-" % year):].isdigit():
            used.add(int(rid[len("L%d-" % year):]))
    number = 1
    while number in used:
        number += 1
    return "L%d-%04d" % (year, number)


def lock(path):
    """A cross-process lock around the read-modify-write, per spec II.4.

    Without it, two concurrent appends both read N rows, both write N+1, and one entry is LOST --
    silently, because the surviving file is perfectly valid. Measured: five parallel runs, five
    "appended" messages, four rows. The pre-atomic `open(path, "a")` at least produced a duplicate
    id that `--validate` would have caught; making the save atomic without a lock traded a visible
    failure for an invisible one.
    """
    target = path + ".lock"
    deadline = time.time() + 10
    while True:
        try:
            handle = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(handle, str(os.getpid()).encode("ascii"))
            os.close(handle)
            return target
        except FileExistsError:
            # A lock older than 60s is a crashed run, not a live one. Breaking it by RENAMING
            # first: `getmtime` then `os.remove` are two calls, so a second waiter could delete a
            # lock a first waiter had already replaced. The rename fails for whoever loses, and
            # only the winner removes the file it now owns.
            try:
                if time.time() - os.path.getmtime(target) > 60:
                    stale = target + ".stale-%d" % os.getpid()
                    os.rename(target, stale)
                    os.remove(stale)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                refuse("another ledger write has held %s for 10s; if no other run is active, "
                       "delete that file" % target)
            time.sleep(0.05)
        except OSError as exc:
            refuse("could not take the ledger lock (%s)" % exc)


def unlock(target):
    try:
        os.remove(target)
    except OSError:
        pass


def label_rows(rows):
    return [("line %d (%s)" % (number, (row.get("id") or "").strip() or "no id"), row)
            for number, row in enumerate(rows, start=2)]


# THE CHART OF ACCOUNTS (FR-0081): a project document, read at the WRITE and not in `--validate`.
# The account is not a column of the row -- it is derived from the category through
# `project_memory/chart_of_accounts.yaml` and re-derived by `euer_report.py`, so the ledger schema
# is unchanged and an old ledger stays valid the day a framework is switched on. What the switch
# changes is the booking: with a framework named, a category no account of it maps to is refused
# HERE, with the accounts named, instead of landing in the report's "ohne Konto" group.
CHART_REL = os.path.join("project_memory", "chart_of_accounts.yaml")


def account_for(category):
    """(account, label, framework) the ACTIVE chart maps `category` to; None while no chart is active.

    Refuses -- does not guess -- a category that maps to no account or to two of the active
    framework: `tools/test_office_package.py::test_a_booking_names_its_account_and_a_category_the_chart_does_not_map_is_refused`.
    """
    path = os.path.join(ROOT, CHART_REL)
    if not os.path.isfile(path):
        return None
    try:
        import yaml
    except ImportError as exc:
        refuse("%s exists but PyYAML is missing (%s): pip install -r requirements-office.txt"
               % (CHART_REL, exc))
    try:
        with open(path, encoding="utf-8") as handle:
            chart = yaml.safe_load(handle) or {}
    except Exception as exc:            # noqa: BLE001 -- any parse failure is one refusal
        refuse("%s cannot be read (%s); a booking cannot name its account" % (CHART_REL, exc))
    active = chart.get("active") if isinstance(chart, dict) else None
    if not active:
        return None
    entries = (chart.get("accounts") or {}).get(active)
    if not isinstance(entries, list):
        refuse("%s names `active: %s` but carries no `accounts.%s` list" % (CHART_REL, active, active))
    hits = [entry for entry in entries if isinstance(entry, dict)
            and category in [str(one) for one in (entry.get("categories") or [])]]
    if len(hits) != 1:
        refuse("category %r maps to %d account(s) of %s (%s) -- one is needed. Remedy: map it in "
               "%s through `apply-proposal` (a new account or a category added to one), never "
               "by hand." % (category, len(hits), active,
                             ", ".join(str(hit.get("account")) for hit in hits) or "none",
                             CHART_REL.replace(os.sep, "/")))
    return str(hits[0].get("account")), str(hits[0].get("label_de") or ""), str(active)


def new_problems(existing, incoming, year):
    """What the INCOMING rows break that was not already broken.

    Pre-existing damage must not be attributed to the entry being added: an operator booking an
    unrelated invoice would be shown findings about somebody else's row from March and would have
    no way to proceed.
    """
    problems = []
    for index, row in enumerate(existing):
        # A malformed EXISTING row must stop the write. `save_atomically` rewrites every row
        # through `row.get(column, "")`, so an unquoted comma in a note (csv puts the overflow
        # under the None key) was silently TRUNCATED and a short row silently padded -- the append
        # exited 0 saying "appended" while destroying a field it never mentioned. Hand edits are
        # legal now, so malformed rows are an expected input, not a corrupt-file corner case.
        if None in row or None in row.values():
            problems.append("line %d (%s): wrong number of columns — this row must be repaired "
                            "before anything can be written, or saving would rewrite and truncate "
                            "it" % (index + 2, (row.get("id") or "").strip() or "no id"))
    for index, row in enumerate(incoming):
        where = "new entry %d (%s)" % (index + 1, (row.get("id") or "").strip() or "no id")
        problems += validate_row(row, where)
    before = set(validate_cross(label_rows(existing), year))
    merged = label_rows(existing) + [
        ("new entry %d (%s)" % (i + 1, (r.get("id") or "").strip() or "no id"), r)
        for i, r in enumerate(incoming)]
    problems += [f for f in validate_cross(merged, year) if f not in before]
    return problems


def validate_file(path):
    """Full validation of a ledger CSV. Returns a list of findings (empty = valid).

    The whole-file counterpart of the append path, and the SAME code: user decision I.3/1 allows
    edits, so something has to be able to judge a file nobody watched being written.
    """
    if os.path.isdir(path):
        return ["%s is a DIRECTORY, not a ledger file" % path]
    if not os.path.isfile(path):
        return ["%s does not exist" % path]
    name = os.path.basename(path)
    if os.path.dirname(os.path.abspath(path)) == os.path.join(ROOT, "ledger") \
            and not YEAR_FILE_RX.match(name):
        return ["%s is not a ledger file — a ledger is `ledger/<year>.csv`, and `euer_report.py` "
                "reads only those. A stray CSV here is invisible to every report while still "
                "supplying ids to the reversal check, so a reversal of a booking that no report "
                "sees validates clean and the quarter reports a negative total. Move it out of "
                "ledger/ (archive/ or a scratch directory)." % name]
    # `euer_report.py` opens with plain utf-8, so a BOM turns its first column name into
    # "\ufeffid" and every `row["id"]` lookup fails — `read_ledger` names that case explicitly,
    # because as a header mismatch it reads as "someone renamed a column".
    rows, error = read_ledger(path)
    if error:
        return [error]

    year = os.path.splitext(os.path.basename(path))[0]
    labelled = label_rows(rows)
    findings = []
    for where, row in labelled:
        if is_malformed(row):
            findings.append("%s: wrong number of columns" % where)
        findings.extend(validate_row(row, where))
    findings.extend(validate_cross(labelled, year))
    return findings


def run_import(argv):
    ap = argparse.ArgumentParser(prog="ledger_add.py --import")
    ap.add_argument("source", help="CSV with the ledger schema (ids may be blank — they are assigned)")
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args(argv)

    incoming, error = read_ledger(args.source)
    if error:
        refuse(error)
    if not incoming:
        refuse("%s has no rows" % args.source)

    os.makedirs(os.path.join(ROOT, "ledger"), exist_ok=True)
    path = os.path.join(ROOT, "ledger", "%d.csv" % args.year)
    # READ, validate and WRITE under one lock — everything between reading `existing` and saving
    # is a read-modify-write of the whole file.
    held = lock(path)
    try:
        existing, error = read_ledger(path)
        if error:
            refuse("the target ledger is not readable: %s" % error)

        assigned = list(existing)
        for row in incoming:
            if not (row.get("id") or "").strip():
                row["id"] = next_id(args.year, assigned)
                assigned = assigned + [row]

        problems = new_problems(existing, incoming, args.year)
        if problems:
            refuse("the import would make the ledger invalid — NOTHING was written:\n"
                   + "\n".join("  - " + p for p in problems))
        for row in incoming:
            account_for((row.get("category") or "").strip())

        for row in incoming:
            for field in ("net", "gross", "vat_rate"):
                value, _ = read_amount(row.get(field))
                row[field] = "%.2f" % value
            row["source"] = (row.get("source") or "").replace("\\", "/")

        save_atomically(path, existing + incoming)
    finally:
        unlock(held)
    print("[ledger_add] imported %d rows into %s (%s ... %s)"
          % (len(incoming), path, incoming[0]["id"], incoming[-1]["id"]))


def main():
    # `--validate <file>` is a MODE, checked before argparse: every other flag is required for an
    # append, and validation needs none of them.
    # POSITION 1 only. "--validate anywhere in argv" meant `--note "use --validate"` silently
    # became a validation run of the note text, and an append the operator watched succeed had
    # never happened.
    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        if not target:
            refuse("--validate needs a ledger CSV path")
        findings = validate_file(target)
        for finding in findings:
            sys.stderr.write("[ledger_add] INVALID: %s\n" % finding)
        if findings:
            sys.exit(1)
        print("[ledger_add] %s is valid" % target)
        return
    # `--import <csv> --year <y>`: the same validation, for many rows at once. Bank exports and
    # a corrected re-issue of a whole month were the cases that made people edit the CSV by hand.
    if len(sys.argv) > 1 and sys.argv[1] == "--import":
        return run_import(sys.argv[2:])

    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--direction", required=True, choices=DIRECTIONS)
    ap.add_argument("--doc-type", required=True, choices=DOC_TYPES)
    ap.add_argument("--doc-date", required=True)
    ap.add_argument("--payment-date", default="")
    ap.add_argument("--open", action="store_true", help="explicitly unpaid (no payment date yet)")
    ap.add_argument("--counterparty", required=True)
    ap.add_argument("--invoice-no", default="")
    ap.add_argument("--net", required=True)
    ap.add_argument("--vat-rate", required=True, help="percent, e.g. 19, 7 or 0")
    ap.add_argument("--gross", required=True)
    ap.add_argument("--vat-treatment", required=True, choices=VAT_TREATMENTS)
    ap.add_argument("--category", required=True)
    ap.add_argument("--source", required=True, help="archive/ path of the source document")
    ap.add_argument("--reverses", default="", help="entry id a reversal cancels")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    if args.open and args.payment_date:
        refuse("--open and --payment-date are mutually exclusive")
    if not args.open and not args.payment_date:
        refuse("give --payment-date (Zufluss/Abfluss: reports count by payment) or mark --open explicitly")

    ledger_dir = os.path.join(ROOT, "ledger")
    os.makedirs(ledger_dir, exist_ok=True)
    path = os.path.join(ledger_dir, "%d.csv" % args.year)

    held = lock(path)
    try:
        rows, error = read_ledger(path)
        if error:
            refuse("%s — run `--validate %s` for the detail" % (error, path))

        entry_id = next_id(args.year, rows)
        row = {
            "id": entry_id, "doc_date": args.doc_date, "payment_date": args.payment_date,
            "direction": args.direction, "doc_type": args.doc_type,
            "counterparty": args.counterparty, "invoice_no": args.invoice_no,
            "net": str(args.net), "vat_rate": str(args.vat_rate), "gross": str(args.gross),
            "vat_treatment": args.vat_treatment, "category": args.category,
            "source": args.source.replace("\\", "/"), "reverses": args.reverses,
            "note": args.note,
        }

        # THE SAME CORE the file check runs -- append cannot be laxer than `--validate`, and
        # neither can be tightened without the other following.
        problems = new_problems(rows, [row], args.year)
        if problems:
            refuse("this entry would make the ledger invalid — NOTHING was written:\n"
                   + "\n".join("  - " + p for p in problems))
        mapped = account_for(args.category)

        net, gross = read_amount(args.net)[0], read_amount(args.gross)[0]
        vat_rate = read_amount(args.vat_rate)[0]
        payment_date = (args.payment_date or "").strip()
        row["net"], row["gross"] = "%.2f" % net, "%.2f" % gross
        row["vat_rate"] = "%.2f" % vat_rate

        save_atomically(path, rows + [row])
    finally:
        unlock(held)

    print("[ledger_add] appended %s: %s %s %.2f EUR gross (%s, %s%s)"
          % (entry_id, args.direction, args.counterparty, gross,
             payment_date or "OPEN/unpaid", args.category,
             ", account %s %s (%s)" % mapped if mapped else ""))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
invoice_intake.py — the DOCKING POINT for the external invoice application (DEC-0075).

    python scripts/invoice_intake.py inbox/RE-2026-0042.xml            # judge; print the plan
    python scripts/invoice_intake.py inbox/RE-2026-0042.pdf --task TSK-0012   # ...and stage the
                                                                       # filing proposal
    python scripts/invoice_intake.py archive/.../RE-2026-0042.xml --book      # after the move:
                                                                       # book the ledger row
    ... --json                                                          # the verdict as JSON

WHAT IT IS. The office kit produces no outgoing invoice (DEC-0075 (3)): an application the user
runs does, one business at a time, each with its own unbroken number range. This script is the
kit's half of that contract: it takes ONE file the application dropped into `inbox/`, and answers
ACCEPTED or REFUSED with the figures named. Accepted means: the file is a structured e-invoice this
reader understands, the norm's mandatory fields it checks are present, the money triple reconciles,
the number continues a range this business declared, and the document can be filed under a rule
the Aktenplan carries and booked under a category the vocabulary knows. Everything it decides it
prints; nothing it decides is a guess.

WHAT IT READS, in the order it refuses:
  1. the document, through `einvoice_extract.parse_xml` — THE reader BUG-0072 hardened, so an
     app-produced invoice and a supplier's go through one code path; a plain PDF or a scan is
     refused as "no structured data" (exit 1), never OCR'd;
  2. the norm: the EN 16931 business rules in `NORM_RULES` — a SUBSET, named rule by rule with the
     business term (BT) each reads, and the sum rule BR-CO-15 through `reconciliation_failure`;
     a rule this table does not carry is not checked here, and the validator of the application
     project owns the full rule set (the interface contract says so);
  3. the type: 380 books as an invoice, 381 as a credit note that has to name a booked invoice of
     the same range (the cancel-and-reissue case); 384 is refused by name (a corrected invoice is a
     381 plus a new 380, DEC-0075 (5)), and a 380 that names a preceding invoice is refused as the
     second-invoice shape § 14c UStG taxes twice;
  4. the range: `master_data.yaml` -> `number_ranges` — the ONE range whose `pattern` the number
     matches in full, whose `business` is the document's seller; then the ledger, every year file,
     for the numbers already booked in that series (`(?P<year>)` in the pattern restarts it), and
     the arriving number must be the next one: a gap or a repeat is refused with both figures
     (`issued_by: app`), or reported and let through (`issued_by: marketplace`, import-only);
  5. the destination: the plan rule that names the range's `document_type`, its `path_template`
     with the year filled in and its `filename_template` rendered — and `gate_filing`'s OWN matcher
     confirms the destination, because the move this prints is judged by that gate afterwards and
     two readers of one plan is the drift this kit pays for.

WHAT IT DOES NOT DO, said here because the gates cannot see a script:
  * it MOVES nothing and BOOKS nothing by itself. Filing is the reviewed pipeline of constitution
    §2.5 — the proposal this stages (`--task`) is the clerk's shape, the second reading is a second
    run's, and the `mv` line it prints goes through `gate_filing` + `gate_second_reading` like any
    other. `--book` runs `ledger_add.py` with the row it composed, and only once the file stands at
    the destination — the row's `source` column names the archive path, so booking before filing
    would name a place that does not exist.
  * it does not judge whether the document belongs to the delivery it claims: three figures that
    reconcile off the wrong order pass here as they pass everywhere (FR-0065 is the second reader).
    For the same reason a row `--book` writes still owes its booking readings (constitution §2.3,
    `gate_second_booking`): this script writes none, because a reading written by the reader that
    produced the row is no second pair of eyes -- BUG-0072 was the extractor's own error.
  * it books ONE VAT rate per document, because a ledger row carries one; a mixed-rate invoice
    (7 % and 19 % on one document, ordinary in trade) is refused for booking with "by hand" -- a
    gap of the ledger's shape, filed as `BUG-0248` (`H166`), not a rule of the norm.
  * it checks the norm SUBSET in `NORM_RULES` and nothing else — no schema, no Schematron, no code
    lists beyond the type codes it books.

WHICH EXIT CODE A NO IS, and it is a definition rather than a list, because the application on
the other side of this contract BRANCHES on it: a no about the DOCUMENT is a refusal (2) -- the
application fixes the document; a no about the PROJECT's own configuration is not-judgeable (1) --
the business fixes its records, and the same file will pass unchanged. So "this number matches no
declared range" is 2 (the document carries a number nobody issued) while "two ranges match it" is 1
(the declarations are ambiguous), and the class the plan has no rule for, the placeholder the intake
cannot fill and the category the vocabulary does not know are all 1. Until 2026-09-06 three of those
were 2 and the contract page's exit table said 1, which is the half of a contract a machine reads.

Exit 0 = accepted (the plan is printed; `--task` staged the proposal, `--book` booked the row).
Exit 1 = NOT JUDGEABLE: something the judgement needs from this PROJECT is missing or ambiguous.
Exit 2 = REFUSED: something about the DOCUMENT. Nothing was staged or booked.
"""
import argparse
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
from decimal import Decimal

# see harness.py: no bytecode into a tree the harness hashes
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BRIDGE = os.path.join(ROOT, ".claude", "hooks")
STATE = os.path.join(ROOT, "project_memory")
VOCABULARY = os.path.join(STATE, "master_data.yaml")
PROFILE = os.path.join(STATE, "business_profile.yaml")
RANGES = "number_ranges"
sys.path.insert(0, HERE)
import einvoice_extract as reader  # noqa: E402  -- the ONE e-invoice reader (BUG-0072)
import ledger_add  # noqa: E402  -- the ledger's own reader and column names

# THE TYPE CODES THIS DOCKING POINT BOOKS (UNTDID 1001), and what each becomes in the ledger. A
# code outside this table is refused BY NAME below, and 384 is refused with the DEC-0075 sentence:
# the three marketplace cases are create (a new 380), cancel-and-reissue (a 381 naming the old
# number, then a new 380) and import-only (a 380 in a `marketplace` range) — a "corrected invoice"
# collapses two of them into one document and hides which number the correction cancels.
BOOKED_TYPES = {"380": "invoice", "381": "credit_note"}
CORRECTED_INVOICE = "384"
# EN 16931 tax category codes -> the ledger's `vat_treatment` vocabulary. `kleinunternehmer` is
# not a category code (it is § 19 UStG, a fact about the seller) and is derived from the profile.
VAT_TREATMENT = {"S": "standard", "AE": "reverse_charge", "E": "exempt", "Z": "exempt",
                 "K": "exempt", "G": "exempt", "O": "exempt", "L": "exempt", "M": "exempt"}
# The placeholders this script can fill in a plan template, each from the document: anything else
# in a rule that files app invoices needs a human and is refused with the placeholder named.
PLACEHOLDER_RX = re.compile(r"<([^<>/]+)>")
NAME_SAFE_RX = re.compile(r"[^A-Za-z0-9._-]+")
# WHAT "a decimal number" MEANS for the part a series is counted by -- digits and nothing else, so
# the reader is exactly as wide as the sentence it and the contract page write. `int()` alone was
# wider than both: measured 2026-09-06, it read `1_0` as 10, `+7` as 7 and the Eastern Arabic `٧`
# as 7, none of which any application prints into an invoice number.
DECIMAL_RX = re.compile(r"\A[0-9]+\Z")


# THE LEDGER ROW THIS VERDICT COMPOSES, as (the flag `ledger_add` takes, the column it fills).
# ONE declaration, TWO readers: the dict `ledger_add.validate_row` judges, and the command line the
# verdict prints. Until 2026-09-06 only the command line existed and nothing judged it, so the
# intake accepted documents whose own booking line the ledger then refused -- rate and treatment
# derived from a total, `net x (1 + rate) != gross` (measured: intake rc 0, `ledger_add` rc 1).
# The judgement is `ledger_add`'s OWN, imported and not restated: a rule that script gains reaches
# this verdict the day it ships
# (`tools/test_office_package.py::test_the_intake_refuses_a_document_whose_booking_line_the_ledger_would_refuse`).
ROW_FLAGS = (("--direction", "direction"), ("--doc-type", "doc_type"),
             ("--doc-date", "doc_date"), ("--counterparty", "counterparty"),
             ("--invoice-no", "invoice_no"), ("--net", "net"), ("--vat-rate", "vat_rate"),
             ("--gross", "gross"), ("--vat-treatment", "vat_treatment"),
             ("--category", "category"), ("--source", "source"))


class Refusal(Exception):
    """A document this docking point will not accept -- the message names the rule or the figures."""


class NotJudgeable(Exception):
    """Something the judgement needs is missing: the reader, a list, the plan (exit 1)."""


def _present(field):
    return lambda out: bool(str(out.get(field) or "").strip())


def _iso_date(out):
    try:
        datetime.date.fromisoformat(str(out.get("issue_date") or ""))
        return True
    except ValueError:
        return False


# THE NORM SUBSET, one row per rule: (rule id, business term, what the rule says, the check). It is
# a table and not a list of ifs so the refusal can name the rule and the interface contract can be
# generated from the same rows; `--json` prints the ids that were checked. What is NOT here is not
# checked — see the module docstring.
NORM_RULES = (
    ("BR-01", "BT-24", "a specification identifier", _present("guideline")),
    ("BR-02", "BT-1", "an invoice number", _present("invoice_no")),
    ("BR-03", "BT-2", "an issue date (read as a calendar date)", _iso_date),
    ("BR-04", "BT-3", "an invoice type code", _present("type_code")),
    ("BR-05", "BT-5", "an invoice currency code", _present("currency")),
    ("BR-06", "BT-27", "the seller's name", _present("seller")),
    ("BR-07", "BT-44", "the buyer's name", _present("buyer")),
    ("BR-09", "BT-40", "the seller's country code", _present("seller_country")),
    ("BR-11", "BT-55", "the buyer's country code", _present("buyer_country")),
    ("BR-13", "BT-109", "the invoice total amount without VAT", _present("net")),
    ("BR-14", "BT-112", "the invoice total amount with VAT", _present("gross")),
    ("BR-16", "BG-25", "at least one invoice line", lambda out: (out.get("line_count") or 0) > 0),
)
SUM_RULE = ("BR-CO-15", "BT-112 = BT-109 + BT-110")


def norm_violations(out):
    """[(rule, term, what)] for every rule of the subset the document fails -- ALL of them, so
    the application project sees the whole list in one verdict rather than one per run."""
    return [(rule, term, what) for rule, term, what, holds in NORM_RULES if not holds(out)]


def _yaml():
    try:
        import yaml
    except ImportError as exc:
        raise NotJudgeable("PyYAML is missing (%s): pip install -r requirements-office.txt" % exc)
    return yaml


def _load(path, what):
    yaml = _yaml()
    if not os.path.isfile(path):
        raise NotJudgeable("%s is missing, and %s cannot be judged without it" % (
            os.path.relpath(path, ROOT).replace(os.sep, "/"), what))
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    if not isinstance(document, dict):
        raise NotJudgeable("%s is not a YAML mapping" % os.path.relpath(path, ROOT))
    return document


def read_document(path):
    """The extractor's reading of the file, or NotJudgeable for anything without structured data."""
    if not os.path.isfile(path):
        raise NotJudgeable("%s does not exist" % path)
    lower = path.lower()
    if lower.endswith(".xml"):
        with open(path, "rb") as handle:
            data = handle.read()
    elif lower.endswith(".pdf"):
        data = reader.extract_pdf_xml(path)
        if data is None:
            raise NotJudgeable("%s carries no embedded e-invoice XML; the docking point takes "
                               "structured invoices only (ZUGFeRD/Factur-X PDF or XRechnung "
                               "XML)" % path)
    else:
        raise NotJudgeable("%s: the docking point takes .xml or .pdf" % path)
    out = reader.parse_xml(data)
    if not out:
        raise NotJudgeable("%s is not an e-invoice this reader understands (see the reader's "
                           "message above)" % path)
    return out


def ranges_of(vocabulary):
    found = vocabulary.get(RANGES)
    if not isinstance(found, list) or not found:
        raise NotJudgeable(
            "master_data.yaml declares no `%s`, so no invoice number can be placed. Remedy: the "
            "bookkeeper stages the document with the business's range(s) declared (the header of "
            "that file states the fields) and the manager asks for `apply-proposal`." % RANGES)
    return [one for one in found if isinstance(one, dict)]


def range_for(out, ranges):
    """The ONE declared range whose pattern the invoice number matches in full, or a Refusal."""
    number = str(out.get("invoice_no") or "")
    hits = []
    for declared in ranges:
        try:
            match = re.fullmatch(str(declared.get("pattern") or ""), number)
        except re.error as exc:
            raise NotJudgeable("range %r carries a pattern this reader cannot compile (%s)"
                               % (declared.get("key"), exc))
        if match and "number" in match.groupdict():
            hits.append((declared, match))
    if not hits:
        raise Refusal("invoice number %r matches none of the %d declared number range(s) (%s) -- "
                      "refused: a number the business did not declare is not one it issued."
                      % (number, len(ranges), ", ".join(str(r.get("key")) for r in ranges)))
    if len(hits) > 1:
        raise NotJudgeable("invoice number %r matches %d declared ranges (%s); which business "
                           "issued it is a guess. This is the project's declaration, not your "
                           "document. Remedy: make the patterns disjoint."
                           % (number, len(hits), ", ".join(str(r.get("key")) for r, _ in hits)))
    declared, match = hits[0]
    mine = _normalised(declared.get("business"))
    seller = _normalised(out.get("seller"))
    if not mine or mine != seller:
        raise Refusal("the document is issued in the name %r, and range %r belongs to %r -- "
                      "refused: an invoice in another name is not this business's outgoing "
                      "invoice." % (out.get("seller"), declared.get("key"), declared.get("business")))
    return declared, match


def _normalised(text):
    return " ".join(str(text or "").split()).casefold()


def booked_numbers(pattern, series_year):
    """{number: (ledger file, row id)} of every income row whose invoice number is in THIS series.

    Every year file, because a series that does not restart per year runs across them; the ledger's
    own reader (`ledger_add.read_ledger`) is used so a file that reader refuses is not silently
    treated as empty.
    """
    directory = os.path.join(ROOT, "ledger")
    found = {}
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return found
    for name in names:
        if not ledger_add.YEAR_FILE_RX.match(name):
            continue
        rows, error = ledger_add.read_ledger(os.path.join(directory, name))
        if error:
            raise NotJudgeable("ledger/%s cannot be read (%s); the series cannot be judged "
                               "against it" % (name, error))
        for row in rows:
            if row.get("direction") != "income":
                continue
            match = re.fullmatch(pattern, str(row.get("invoice_no") or ""))
            if not match or "number" not in match.groupdict():
                continue
            if match.groupdict().get("year", "") != series_year:
                continue
            row_id = (row.get("id") or "").strip()
            found[series_number(match.group("number"),
                                "ledger/%s row %s: the counting part of %r"
                                % (name, row_id, str(row.get("invoice_no") or "")),
                                problem=NotJudgeable)] = (name, row_id)
    return found


def series_number(text, what, problem=Refusal):
    """`text` as the integer a series is ORDERED by, or `problem` naming `what` it was read from.

    A range's `pattern` is the PROJECT's own regular expression and its `first` the project's own
    figure, so neither is a number because this script wants one. Until 2026-09-05 all three read
    sites called `int()` straight, and a capture like `(?P<number>[A-Za-z0-9]+)` or a `first:` the
    project wrote as a word ended the run in a traceback where the module docstring promises a
    verdict (`tools/test_office_package.py::test_a_series_the_intake_cannot_order_is_refused_and_never_crashes`).

    WHOSE FIGURE IT IS decides the exit code, which is why the caller passes the exception rather
    than this reader choosing one: the arriving DOCUMENT is refused (exit 2), while the project's
    own declaration and its own ledger are not judgeable (exit 1) -- the same line every other
    reader in this file draws.
    """
    if not DECIMAL_RX.match(str(text).strip()):
        raise problem("%s is %r, and the part the range counts by has to be a decimal number -- "
                      "a series that cannot be ordered cannot be continued."
                      % (what, str(text)))
    return int(str(text).strip(), 10)


def continuity(declared, match):
    """(sentence, refusal or None) about where this number stands in its series."""
    pattern = str(declared.get("pattern"))
    year = match.groupdict().get("year", "")
    number = series_number(match.group("number"), "the document's invoice number")
    issued = booked_numbers(pattern, year)
    first = series_number(declared.get("first") or 1,
                          "the `first` of range %s" % declared.get("key"), problem=NotJudgeable)
    # WHERE THE SERIES STANDS, read ONCE for the three sentences below. Two of them used to read
    # `max(issued)` on their own and one of those did it unguarded, so a series with no history at
    # all raised ValueError instead of refusing. Which of the two origins the stand has -- the
    # highest booked number, or the `first` the range declares -- is the difference between a
    # refusal the application can act on and one it cannot, so the sentence carries it.
    last = max(issued) if issued else None
    expected = last + 1 if last is not None else first
    stand = ("last issued %d" % last if last is not None
             else "none issued yet; the range declares %d as its first" % first)
    series = "range %s%s" % (declared.get("key"), " / %s" % year if year else "")
    if number in issued:
        where = issued[number]
        return ("", "number %d of %s is already booked (ledger/%s, row %s) -- refused: one "
                    "number, one document." % (number, series, where[0], where[1]))
    if number == expected:
        return ("%s: %d continues the series (last issued %s)"
                % (series, number, last if last is not None else "none"), None)
    if number < expected:
        return ("", "number %d of %s arrives below where the series stands (%s) -- refused: a "
                    "series runs upward only; a document with a lower number is one that was "
                    "skipped or altered." % (number, series, stand))
    missing = number - expected
    figures = ("%s: %s, arriving %d, %d number(s) missing in between (%d..%d)"
               % (series, stand, number, missing, expected, number - 1))
    if str(declared.get("issued_by") or "app") == "marketplace":
        return ("GAP REPORTED, not refused (issued_by: marketplace) -- %s" % figures, None)
    return ("", "gap in %s -- refused. Remedy: the application issues numbers without a gap. A "
                "number that was CANCELLED is not a hole in the series either: hand its own "
                "invoice in first (the 380, which books like any other), then the 381 credit note "
                "that cancels it -- in that order the range closes and this document continues "
                "it. Handing the 381 in on its own is refused, because a credit note cancels a "
                "booked invoice." % figures)


def document_type_check(out, declared, match):
    """The booked doc type for this type code, with the cross-reference rules of DEC-0075 (5)."""
    code = str(out.get("type_code") or "")
    preceding = str(out.get("preceding_invoice") or "").strip()
    if code == CORRECTED_INVOICE:
        raise Refusal("type code 384 (corrected invoice) is refused by design: a correction is a "
                      "381 credit note naming the cancelled number plus a NEW 380 -- two "
                      "documents, two numbers, so the range stays readable (DEC-0075 (5)).")
    if code not in BOOKED_TYPES:
        raise Refusal("type code %r is not one this docking point books (%s)."
                      % (code, ", ".join("%s = %s" % pair for pair in sorted(BOOKED_TYPES.items()))))
    doc_type = BOOKED_TYPES[code]
    pattern = str(declared.get("pattern"))
    if doc_type == "credit_note":
        if not preceding:
            raise Refusal("a 381 credit note has to name the invoice it cancels (BT-25 preceding "
                          "invoice reference), and this one names none -- refused.")
        ref = re.fullmatch(pattern, preceding)
        if not ref:
            raise Refusal("the credit note cancels %r, which is not a number of range %s -- "
                          "refused: a cancellation stays inside the business's own range."
                          % (preceding, declared.get("key")))
        cancelled = series_number(ref.group("number"),
                                  "the number the credit note cancels")
        if cancelled not in booked_numbers(pattern,
                                           ref.groupdict().get("year", "")):
            raise Refusal("the credit note cancels %r, and no booked income row carries that "
                          "number -- refused: the original is booked first, or was never ours."
                          % preceding)
    elif preceding:
        raise Refusal("a 380 invoice that names a preceding invoice (%r) is the second-invoice "
                      "shape: two invoices over one delivery, and § 14c UStG taxes both -- "
                      "refused. Cancel with a 381, then issue the new 380 without a reference."
                      % preceding)
    return doc_type


def vat_of(out, profile):
    """(vat_rate, vat_treatment) the ledger row carries, or a Refusal the row cannot represent."""
    categories = out.get("tax_categories") or []
    rates = sorted({str(rate).strip() for _code, rate in categories if str(rate).strip()})
    codes = sorted({str(code).strip() for code, _rate in categories if str(code).strip()})
    if len(rates) > 1:
        raise Refusal("the document carries %d VAT rates (%s); one ledger row carries one rate, "
                      "so this document is booked by hand, line group by line group."
                      % (len(rates), ", ".join(rates)))
    rate = rates[0] if rates else "0"
    # A CODE THIS TABLE DOES NOT CARRY IS NOT A CODE THIS SCRIPT MAY BOOK. `VAT_TREATMENT.get`
    # answers None for one, and until 2026-09-05 the None was filtered out and the fallback below
    # decided the treatment off the RATE -- so a document stating a category nobody read booked as
    # `standard` with nothing said. The fallback exists for a document that states NO category at
    # all, which is a different fact and stays.
    unknown = [code for code in codes if code not in VAT_TREATMENT]
    if unknown:
        raise Refusal("the document states VAT category code(s) %s, and this docking point books "
                      "only %s -- refused: a treatment nobody read off the document is a guessed "
                      "one." % (", ".join(unknown), ", ".join(sorted(VAT_TREATMENT))))
    numeric_rate = reader._amount(rate)
    if numeric_rate is None:
        raise Refusal("the document states its VAT rate as %r, which is not a number this reader "
                      "understands -- refused: the rate is booked, so it is read or it is not "
                      "booked." % rate)
    treatments = sorted({VAT_TREATMENT[code] for code in codes})
    if len(treatments) > 1:
        raise Refusal("the document mixes VAT categories (%s) that book differently -- by hand."
                      % ", ".join(codes))
    tax = reader._amount(out.get("tax")) or Decimal("0")
    # NO BREAKDOWN AND A VAT AMOUNT IS NOT A DOCUMENT THIS BOOKS. Without BG-23 the rate and the
    # treatment stand NOWHERE in the document; the fallback below then derived both from the total,
    # and measured 2026-09-06 that produced `--vat-rate 0 --vat-treatment exempt` for a document
    # stating tax 40.70 -- a verdict rc 0 whose own booking line the ledger refuses. The fallback
    # stays only where it states nothing the document does not: no tax, so no rate and no VAT in
    # the amount.
    if not categories and tax != 0:
        raise Refusal("the document states a VAT amount of %s (net %s, gross %s) but carries no "
                      "VAT breakdown (BG-23), so neither the rate nor the category of that amount "
                      "stands in it -- refused: this docking point books the rate the document "
                      "states and never one derived from a total."
                      % (tax, out.get("net"), out.get("gross")))
    treatment = treatments[0] if treatments else ("standard" if numeric_rate else "exempt")
    kleinunternehmer = ((profile.get("tax") or {}).get("kleinunternehmer") is True)
    if kleinunternehmer and tax == 0:
        treatment, rate = "kleinunternehmer", "0"
    return rate, treatment


def _plan_rules():
    """The plan's rules and the gate's matcher, through the hook bridge (as `process_doc.py`)."""
    if not os.path.isfile(os.path.join(BRIDGE, "_kernel.py")):
        raise NotJudgeable("this project has no enforcement layer at %s; the plan reader is not "
                           "installed" % BRIDGE)
    sys.path.insert(0, BRIDGE)
    import _kernel  # type: ignore[import-not-found]
    import gate_filing  # type: ignore[import-not-found]
    _kernel.disarm()
    rules, reason = gate_filing.rules(ROOT)
    if rules is None:
        raise NotJudgeable("%s -- the intake can name no destination" % reason)
    return rules, gate_filing


def _fill(template, values, what):
    def one(match):
        name = match.group(1)
        if name not in values:
            raise NotJudgeable("%s carries the placeholder <%s>, which this intake cannot fill "
                               "from the document (it fills %s) -- a human files this class."
                               % (what, name, ", ".join("<%s>" % key for key in sorted(values))))
        return values[name]
    return PLACEHOLDER_RX.sub(one, template)


def destination_of(out, declared, source):
    """(destination path, rule id): the plan rule naming the range's class, rendered."""
    rules, gate_filing = _plan_rules()
    klass = str(declared.get("document_type") or "")
    hits = [rule for rule in rules if isinstance(rule, dict)
            and klass in [str(one) for one in (rule.get("document_types") or [])]]
    if len(hits) != 1:
        # THE REMEDY FOLLOWS THE COUNT, because the two counts need opposite moves and one
        # sentence for both told the reader of a DOUBLE rule to add a third (verify round 2, R5).
        raise NotJudgeable(
            "%d plan rule(s) file the class %r that range %s declares -- exactly one is needed. "
            "Remedy: %s"
            % (len(hits), klass, declared.get("key"),
               "add the rule (`filing_plan.py --draft` proposes it) or name the class the plan "
               "already carries" if not hits else
               "two rules for one class make the destination a guess, and this kernel never "
               "edits or removes a rule (`kernel/filing.py`): give one of them its own class, or "
               "let the records clerk migrate the tray, and point this range at the class that "
               "stays (%s)" % ", ".join(str(rule.get("id")) for rule in hits)))
    rule = hits[0]
    issued = datetime.date.fromisoformat(out["issue_date"])
    values = {"year": "%04d" % issued.year, "month": "%02d" % issued.month,
              "quarter": "Q%d" % ((issued.month - 1) // 3 + 1)}
    directory = _fill(str(rule.get(gate_filing.PATH_TEMPLATE) or ""), values,
                      "rule %s's path_template" % rule.get("id")).strip("/")
    name = str(rule.get("filename_template") or "YYYY-MM-DD_<counterparty>_<doctype>")
    name = name.replace("YYYY-MM-DD", issued.isoformat()).replace("YYYY-MM", issued.strftime("%Y-%m"))
    name = _fill(name, {"counterparty": _slug(out.get("buyer")), "doctype": klass,
                        "invoice_no": _slug(out.get("invoice_no")),
                        "number": _slug(out.get("invoice_no")), "year": values["year"]},
                 "rule %s's filename_template" % rule.get("id"))
    destination = "%s/%s%s" % (directory, name, os.path.splitext(source)[1].lower())
    # ONE DESTINATION, ONE DOCUMENT. The shipped `filename_template` carries date, counterparty and
    # doc type and no number, so two invoices to one customer on one day render ONE path -- and the
    # move that overwrites the first is one `gate_filing` accepts, because the destination matches
    # the rule either way (measured 2026-09-06: second verdict rc 0, same path, chain rc 0). The
    # intake cannot rewrite the plan, so it refuses to name a path that is already taken and says
    # what makes the rule unambiguous.
    # ...and the document already AT its destination is not a collision with itself: `--book`
    # runs this same judgement on the archived path after the move (measured: the first cut
    # refused its own second run).
    if destination != source and os.path.isfile(os.path.join(ROOT, *destination.split("/"))):
        raise NotJudgeable(
            "%s already stands at %s, so filing this document there would overwrite it. Rule %s's "
            "`filename_template` (%s) carries nothing that tells two documents of one day and one "
            "counterparty apart. Remedy: give that rule a template with <invoice_no> in it "
            "(`add-filing-rule` writes a new rule on the user's approval; this intake fills "
            "<invoice_no>, <number>, <year>, <counterparty> and <doctype>)."
            % (os.path.basename(destination), os.path.dirname(destination), rule.get("id"),
               rule.get("filename_template")))
    if not gate_filing.rule_matches(rule.get(gate_filing.PATH_TEMPLATE), directory):
        raise NotJudgeable("the rendered destination %s does not match its own rule %s by the "
                           "gate's matcher -- report the gap" % (destination, rule.get("id")))
    return destination, str(rule.get("id"))


def _slug(text):
    return NAME_SAFE_RX.sub("-", str(text or "").strip()).strip("-") or "unknown"


def category_check(declared, vocabulary):
    key = str(declared.get("category") or "")
    known = [str(entry.get("key")) for entry in ((vocabulary.get("categories") or {})
                                                 .get("income") or []) if isinstance(entry, dict)]
    if key not in known:
        raise NotJudgeable("range %s books under category %r, and master_data.yaml's income "
                           "categories do not carry it (%s): a booking under a key the vocabulary "
                           "does not know lands in 'ohne Zeile'. Remedy: the bookkeeper stages "
                           "master_data.yaml with the category and the manager asks for "
                           "`apply-proposal`."
                           % (declared.get("key"), key, ", ".join(known) or "none"))
    return key


def judge(source, args):
    """Everything above, in the order of the module docstring; returns the verdict dict."""
    out = read_document(source)
    verdict = {"source": source.replace("\\", "/"), "syntax": out.get("syntax"),
               "invoice_no": out.get("invoice_no"), "seller": out.get("seller"),
               "buyer": out.get("buyer"), "issue_date": out.get("issue_date"),
               "net": out.get("net"), "tax": out.get("tax"), "gross": out.get("gross"),
               "norm_rules_checked": [rule for rule, _t, _w, _h in NORM_RULES] + [SUM_RULE[0]],
               "reasons": []}
    failed = norm_violations(out)
    if failed:
        raise Refusal("mandatory field(s) missing -- %s." % "; ".join(
            "%s (%s): %s" % (rule, term, what) for rule, term, what in failed))
    sum_failure = reader.reconciliation_failure(out)
    if sum_failure:
        raise Refusal("%s (%s): %s" % (SUM_RULE[0], SUM_RULE[1], sum_failure))
    vocabulary = _load(VOCABULARY, "the number ranges and the categories")
    profile = _load(PROFILE, "the tax status") if os.path.isfile(PROFILE) else {}
    declared, match = range_for(out, ranges_of(vocabulary))
    verdict.update({"range": declared.get("key"), "business": declared.get("business")})
    doc_type = document_type_check(out, declared, match)
    sentence, refusal = continuity(declared, match)
    if refusal:
        raise Refusal(refusal)
    verdict["continuity"] = sentence
    category = category_check(declared, vocabulary)
    rate, treatment = vat_of(out, profile)
    destination, rule_id = destination_of(out, declared, source)
    verdict["filing"] = {"destination": destination, "rule_id": rule_id,
                         "move": "mv %s %s" % (source.replace("\\", "/"), destination)}
    booked = {"doc_date": out["issue_date"], "payment_date": args.payment_date or "",
              "direction": "income", "doc_type": doc_type,
              "counterparty": str(out.get("buyer") or ""),
              "invoice_no": str(out.get("invoice_no") or ""), "net": str(out.get("net")),
              "vat_rate": rate, "gross": str(out.get("gross")), "vat_treatment": treatment,
              "category": category, "source": destination}
    findings = ledger_add.validate_row(booked, "the row this verdict would book")
    if findings:
        raise Refusal(
            "the booking line this document produces is one the ledger itself refuses -- %s. "
            "Refused HERE, so a verdict never promises a booking that cannot happen." %
            "; ".join(findings))
    # ONE TOKEN PER FLAG (`--flag=value`), and that is the second half of the promise above.
    # `validate_row` judges the DICT; the argv rendered from it is parsed by argparse, which reads
    # a value beginning with `-` as an option -- measured 2026-09-06 with a buyer literally named
    # `--doc-type`: the verdict was rc 0 and `ledger_add` came back rc 2 with an argparse usage
    # message. In the `=` form the value's first character decides nothing.
    row = ["--year=%s" % out["issue_date"][:4]]
    row += ["%s=%s" % (flag, booked[key]) for flag, key in ROW_FLAGS]
    row += ["--payment-date=%s" % args.payment_date] if args.payment_date else ["--open"]
    verdict["booking"] = {"ledger_add": row}
    return verdict


def stage_proposal(verdict, task, role):
    """The clerk's shape (`kernel/schemas/filing_proposal.yaml`), written into the task's area."""
    directory = os.path.join(STATE, "staging", task)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "filing_proposal_%s.yaml" % _slug(verdict["invoice_no"]))
    findings = ["seller %s" % verdict["seller"], "buyer %s" % verdict["buyer"],
                "issue_date %s" % verdict["issue_date"],
                "net %s tax %s gross %s" % (verdict["net"], verdict["tax"], verdict["gross"]),
                verdict["continuity"]]
    lines = ["task_id: %s" % task, "role: %s" % role, "proposals:",
             "  - source: %s" % verdict["source"],
             "    document_class: %s" % verdict["range"],
             "    destination: %s" % verdict["filing"]["destination"],
             "    rule_id: %s" % verdict["filing"]["rule_id"],
             "    findings:"] + ["      - %s" % json.dumps(one, ensure_ascii=False)
                                 for one in findings]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path.replace("\\", "/")


def book(verdict):
    destination = os.path.join(ROOT, *verdict["filing"]["destination"].split("/"))
    if not os.path.isfile(destination):
        raise Refusal("nothing stands at %s yet -- book AFTER the move (the row's source column "
                      "names the archive path)." % verdict["filing"]["destination"])
    result = subprocess.run([sys.executable, "-B", os.path.join(HERE, "ledger_add.py")]
                            + verdict["booking"]["ledger_add"], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    if result.returncode != 0:
        raise Refusal("ledger_add.py refused the row: %s" % (result.stderr.strip() or result.stdout))
    return result.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("file", help="the invoice file the application dropped (.xml or .pdf)")
    parser.add_argument("--task", metavar="TSK-nnnn",
                        help="stage the filing proposal into project_memory/staging/<TSK>/")
    parser.add_argument("--role", default="bookkeeper", help="the role named in the proposal")
    parser.add_argument("--book", action="store_true",
                        help="book the ledger row (the file must already stand at its destination)")
    parser.add_argument("--payment-date", default="", help="YYYY-MM-DD if already paid; else OPEN")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON on stdout")
    args = parser.parse_args(argv)
    source = os.path.relpath(os.path.abspath(args.file), ROOT).replace("\\", "/")
    try:
        verdict = judge(source, args)
        verdict["verdict"] = "accepted"
        if args.task:
            verdict["proposal"] = stage_proposal(verdict, args.task, args.role)
        if args.book:
            verdict["booked"] = book(verdict)
    except Refusal as refusal:
        sys.stderr.write("[intake] REFUSED %s: %s\n" % (source, refusal))
        if args.json:
            print(json.dumps({"verdict": "refused", "source": source, "reasons": [str(refusal)]},
                             ensure_ascii=False, indent=2))
        return 2
    except NotJudgeable as gap:
        sys.stderr.write("[intake] NOT JUDGEABLE %s: %s\n" % (source, gap))
        if args.json:
            print(json.dumps({"verdict": "not_judgeable", "source": source,
                              "reasons": [str(gap)]}, ensure_ascii=False, indent=2))
        return 1
    if args.json:
        print(json.dumps(verdict, ensure_ascii=False, indent=2))
    else:
        print("[intake] ACCEPTED %s: %s, issued by %s (range %s), %s"
              % (verdict["invoice_no"], verdict["syntax"], verdict["business"], verdict["range"],
                 verdict["continuity"]))
        print("[intake] filing:  %s   (rule %s)" % (verdict["filing"]["move"],
                                                    verdict["filing"]["rule_id"]))
        line = printable(verdict["booking"]["ledger_add"])
        if line:
            print("[intake] booking: python scripts/ledger_add.py %s" % line)
        else:
            print("[intake] booking: this document carries a value no command line can be retyped "
                  "with (a quotation mark in a name, say), so none is printed. Run `python "
                  "scripts/invoice_intake.py %s --book` once the document stands at its "
                  "destination -- that route hands the ledger the values directly."
                  % verdict["filing"]["destination"])
        if verdict.get("proposal"):
            print("[intake] proposal staged: %s" % verdict["proposal"])
        if verdict.get("booked"):
            print("[intake] %s" % verdict["booked"])
    return 0


def printable(argv):
    """`argv` as a command line ONLY when a shell reading that line hands back exactly `argv`.

    A printed line is an offer to retype it, so an offer that books a different customer than
    `--book` does is worse than none. Two measurements, both 2026-09-06, both with the same buyer
    `He said "hi"`: the first rendering quoted on whitespace and escaped nothing, so
    `--counterparty "He said "hi""` came back from a shell as `He said hi`; and
    `kernel.documents.quoted_for_a_command_line`, the rule this repo already owns for a printed
    remedy, SWAPS an inner `"` for `'` -- which is right where the value is a free-text REASON (its
    own docstring says the swap changes nothing an approval binds) and wrong here, where the value
    is BOOKED: it would have booked `He said 'hi'`.

    So this is not a better quoting rule but a property: render, split the rendering back the way a
    POSIX shell splits it, and offer the line only when the two agree. Where they do not, the
    verdict names `--book`, which hands the ledger the values directly and passes no shell at all
    (`tools/test_office_package.py::test_the_printed_booking_line_books_what_the_verdict_read`).

    THE ROUND TRIP IS THE POSIX ONE and this says so rather than implying both shells: PowerShell
    splits a line by its own rules, and a reader that claimed to cover it would be claiming a
    measurement nobody made.
    """
    line = " ".join('"%s"' % str(word).replace('"', "'") for word in argv)
    try:
        return line if shlex.split(line, posix=True) == [str(word) for word in argv] else None
    except ValueError:
        return None


if __name__ == "__main__":
    sys.exit(main())

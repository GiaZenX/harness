#!/usr/bin/env python3
"""
finance_dashboard.py -- the finance dashboard, rendered FROM the ledger (FR-0032).

Reads `ledger/<year>.csv`, `project_memory/master_data.yaml` and
`project_memory/business_profile.yaml`; writes ONE file, `dashboards/finanzen.html`. It renders
state and never sets one: no ledger row, no item, no report is touched.

WHY THE ARITHMETIC IS IMPORTED AND NOT WRITTEN HERE. The sign convention (`euer_report.sign_of`,
`NEGATIVE_DOC_TYPES`) and the reader (`ledger_add.read_ledger`, `COLUMNS`, `YEAR_FILE_RX`) have
one home each. A dashboard that copied them would be a second answer about the same money, and
`euer_report.py`'s own header records what the first copy of that convention cost. The agreement
is measured rather than asserted, in the kit workshop rather than here (that suite does not ship):
`tools/test_finance_dashboard.py::test_the_dashboard_and_euer_report_agree_on_every_quarter` runs
the real report over the same ledger, quarter by quarter.

WHY IT LIVES IN `tools/` AND NOT IN `scripts/`. `scripts/` is the office kit's own machinery, and
`gate_ledger_valid` runs one of those scripts as the ledger judge. This is a reporting command a
project may adjust, and it is started by hand today -- see `dashboards/ABOUT.txt` for the command
and for what is NOT yet wired.

NO CLOCK IN THE OUTPUT. The file is a function of the data alone -- same tree, same bytes -- so
two people can compare their copies. The "Datenstand" in the masthead is the youngest date the
ledger carries, not the moment of rendering. The AGE of an open item is the one thing that cannot
work that way: the page computes it in the browser from the viewer's own clock, so the answer to
"is this one overdue" is that machine's answer. The page says so where it shows it.

Usage:
  python tools/finance_dashboard.py            # from the project root
  python tools/finance_dashboard.py --root DIR # for tests; DIR is a project root

Exit 0 also when the ledger is invalid -- the page IS the report about that state, and it says so
in a banner. Exit 1 only when nothing could be written.
"""
import argparse
import html
import os
import re
import sys
from collections import defaultdict

# The kit's own scripts must not drop bytecode next to themselves: `.claude/` and the repo scripts
# are what `hook_bundle_hash` measures, and a stray `__pycache__` in a hashed tree makes the next
# session report `hooks_trust_required` because somebody rendered a dashboard
# (`kernel/hashing.py`, BYTECODE_SUFFIXES; same reason as in `scripts/generate_dashboard.py`).
sys.dont_write_bytecode = True

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_NAME = "finance_dashboard.template.html"
OUTPUT_REL = os.path.join("dashboards", "finanzen.html")

# THE LEGAL FALLBACK payment term, used where the business has declared none of its own:
# § 286 Abs. 3 BGB -- Verzug 30 days after the invoice is due and received. THE LEDGER STILL
# CARRIES NO DUE DATE, so the term is applied to the document date; what a business really agreed
# with its customers is `receivables.payment_terms_days` in `business_profile.yaml`, and
# `payment_term_days` below prefers it. Until BUG-0202 this constant was the only answer and the
# page presented it as the law -- a business working on 14 days was shown dunning candidates by a
# rule nobody in it had agreed to.
PAYMENT_TERM_DAYS = 30
LEGAL_TERM_SOURCE = "die gesetzliche Verzugsfrist (§ 286 Abs. 3 BGB)"
PROFILE_TERM_SOURCE = "die in business_profile.yaml vereinbarte Zahlungsfrist"


def payment_term_days(profile):
    """(days, where-it-comes-from) for this business, its own declaration first.

    A declaration is read only when it is a whole positive number of days: `null`, an empty string
    and a nonsense value all mean "not declared", and inventing a term out of one of them would put
    a dunning stamp on the page with nothing behind it. The SENTENCE travels with the number, so
    the page can never name a term without naming whose it is.
    """
    declared = ((profile or {}).get("receivables") or {}).get("payment_terms_days")
    if isinstance(declared, bool) or not isinstance(declared, (int, float, str)):
        return PAYMENT_TERM_DAYS, LEGAL_TERM_SOURCE
    try:
        days = int(str(declared).strip())
    except (TypeError, ValueError):
        return PAYMENT_TERM_DAYS, LEGAL_TERM_SOURCE
    if days <= 0:
        return PAYMENT_TERM_DAYS, LEGAL_TERM_SOURCE
    return days, PROFILE_TERM_SOURCE

# § 19 Abs. 1 UStG in the wording in force since 2025-01-01 (JStG 2024): previous calendar year up
# to 25.000 EUR AND current year up to 100.000 EUR. In CENTS, because every money comparison in
# this file is an integer one -- a float limit beside integer sums is two spellings of one number.
KLEINUNTERNEHMER_LIMIT_PREVIOUS_YEAR = 25000_00
KLEINUNTERNEHMER_LIMIT_CURRENT_YEAR = 100000_00

# WHICH ROWS CARRY UMSATZSTEUER is `euer_report.py`'s answer and not one invented here: that script
# counts a row's `gross - net` as VAT exactly when `vat_treatment` says this word, and it decides
# that inline in `main`, so there is nothing to import. The copy is PINNED instead of trusted --
# the parity test compares the USt figures on this page against the ones the report prints for the
# same quarter (`tools/test_finance_dashboard.py::test_the_dashboard_and_euer_report_agree_on_every_quarter`
# in the kit workshop).
VAT_TREATMENT_IN_ZAHLLAST = "standard"

GERMAN_MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# How many rows the page shows before "alle anzeigen". The template's script uses the SAME number
# for the filtered view, and it gets it from here through the {{page_rows}} slot rather than
# carrying a second 100 of its own.
PAGE_ROWS = 100


def project_root(explicit=None):
    """The project root: the directory `tools/` sits in, unless a caller names another one."""
    return os.path.abspath(explicit) if explicit else os.path.dirname(TOOLS_DIR)


def _import_kit_scripts(root):
    """`euer_report` and `ledger_add` from THIS project's `scripts/`, or a refusal that says so."""
    scripts = os.path.join(root, "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        import euer_report
        import ledger_add
    except ImportError as problem:
        sys.stderr.write(
            "[finance_dashboard] cannot import the ledger arithmetic from %s (%s). This command "
            "renders the office kit's ledger and needs the kit's own scripts/ beside it.\n"
            % (scripts, problem))
        raise SystemExit(1)
    return euer_report, ledger_add


def _read_yaml(path):
    """A kit document, or an empty mapping -- a project on day one has neither file filled."""
    if not os.path.isfile(path):
        return {}
    try:
        import yaml
    except ImportError as problem:
        # The SAME shape as the refusal above, for the same reason: a missing dependency is a
        # sentence somebody can act on, and a traceback is not. Measured before this branch
        # existed: `ModuleNotFoundError: No module named 'yaml'` and nothing else.
        sys.stderr.write(
            "[finance_dashboard] cannot read %s: PyYAML is missing (%s). The office kit's own "
            "documents are YAML, so this command needs it: pip install -r "
            "requirements-office.txt\n" % (path, problem))
        raise SystemExit(1)
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _cents(text):
    """A ledger amount as an integer of cents. Every sum in this file is an integer sum."""
    return int(round(_num(text) * 100))


# What separates the amount from its currency sign: a NON-BREAKING space, so no line ever ends
# between "1.234,50" and the euro sign. THE PAGE SCRIPT FORMATS THE SAME FIGURES (`fmtEur` in the
# template, for every filtered sum), and the two spellings have to be one: measured 2026-09-02, an
# ordinary space here and a non-breaking one there printed the same sum two ways on one page --
# the initial total and the filtered total. The kit workshop's
# `tools/test_finance_dashboard.py::test_filters_narrow_rows_and_the_sum_follows` reads the SAME
# node twice for that reason -- out of the written file, where this constant is what stands, and
# out of the browser after a filter, where the script's spelling has replaced it -- and compares
# both against a third one of its own. Reading it only in the browser measured the script alone:
# the page overwrites that node on load.
CURRENCY_GAP = "\u00a0"  # U+00A0, spelled as an escape so an editor cannot eat it


def fmt_eur(cents):
    """-123450 -> '−1.234,50 €'. Corrections carry a real minus sign (U+2212), not a hyphen."""
    negative = cents < 0
    euros, rest = divmod(abs(int(cents)), 100)
    body = "{:,}".format(euros).replace(",", ".") + "," + "%02d" % rest + CURRENCY_GAP + "€"
    return ("−" + body) if negative else body


def plural(count, one, many):
    """German counts read wrong at one ("1 Rechnungen zu zahlen") -- caught while sighting the
    rendered page (BUG-0076 loop), which is where a wording defect becomes visible at all."""
    return one if count == 1 else many


def fmt_date(iso):
    if not iso:
        return ""
    year, month, day = iso.split("-")
    return "%s.%s.%s" % (day, month, year)


def e(text):
    return html.escape(str(text if text is not None else ""), quote=True)


# --- reading the project -------------------------------------------------------------------


def _cancelled_ids(rows):
    """The ids a reversal in `rows` cancels. The SCOPE is the caller's question, not this list's."""
    return {r.get("reverses") for r in rows
            if r.get("doc_type") == "reversal" and r.get("reverses")}


def _status_of(row, cancelled, euer_report):
    """The same case distinction `euer_report.main` makes, in the same order: a reversed original is
    cancelled, a correction is not a receivable, then payment.

    One cascade for two scopes. The page's own views ask it with the reversals of the WHOLE ledger,
    the EÜR tab with the reversals of ONE file, because that is all the report ever opens -- and a
    second copy of the cascade is how the two readings would drift apart.
    """
    if row.get("id") in cancelled:
        return "storniert"
    if row.get("doc_type") in euer_report.NEGATIVE_DOC_TYPES:
        return "korrektur"
    return "bezahlt" if row.get("payment_date") else "offen"


def load_project(root, euer_report, ledger_add):
    """Everything the page renders. One pass over the ledger, one status per row, no clock."""
    profile = _read_yaml(os.path.join(root, "project_memory", "business_profile.yaml"))
    master = _read_yaml(os.path.join(root, "project_memory", "master_data.yaml"))
    categories = {}
    for direction in ("income", "expense"):
        for entry in (master.get("categories") or {}).get(direction) or []:
            # A LIST ITEM THAT IS NOT A MAPPING IS SKIPPED, exactly as `euer_report.read_vocabulary`
            # skips it. `master_data.yaml` tells its reader to rename and add freely, and a bare
            # string where a mapping belongs is what a hand-edited list gives you first -- it used
            # to be an AttributeError and rc 1, i.e. no page at all, while the report over the same
            # file stayed rc 0. Two readers of one file may not answer a typo differently.
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            if not key:
                continue
            categories[key] = {"label": entry.get("label_de") or key,
                               "euer_line": euer_report.line_number(entry.get("euer_line")),
                               "euer_line_label": str(entry.get("euer_line_label") or ""),
                               "direction": direction}

    ledger_dir = os.path.join(root, "ledger")
    # `os.listdir` + the kit's own file rule, NOT `glob`: a `[` in the project path makes `glob`
    # find nothing at all (`ledger_add.sibling_index` carries that measurement). Sorted, because
    # the output has to be a function of the tree and not of the directory order.
    names = sorted(os.listdir(ledger_dir)) if os.path.isdir(ledger_dir) else []
    sources, rows, strays = [], [], []
    for name in names:
        path = os.path.join(ledger_dir, name)
        if not ledger_add.YEAR_FILE_RX.match(name):
            # NOT A SILENT SKIP. `ledger/` is a directory a person writes into, and a file that no
            # report reads while looking exactly like the books is the case `ledger_add`'s own
            # comment names ("2026 - Kopie.csv"). What is wrong with it is the kit judge's
            # sentence, not one invented here; the page only carries it. It does not make the
            # ledger invalid: the sums come from the year files and stay dependable.
            if os.path.isfile(path):
                strays.append({"file": "ledger/" + name,
                               "findings": ledger_add.validate_file(path)
                               or ["%s: kein Ledgerjahr im Namen — kein Bericht liest die Datei"
                                   % name]})
            continue
        findings = ledger_add.validate_file(path)
        loaded, error = ledger_add.read_ledger(path)
        year = name[:4]
        sources.append({"file": "ledger/" + name, "year": year, "rows": len(loaded or []),
                        "valid": not findings and not error,
                        "findings": list(findings or []) + ([error] if error else [])})
        for row in loaded or []:
            rows.append(dict(row, year=year))

    reversed_ids = _cancelled_ids(rows)
    for r in rows:
        r["sign"] = euer_report.sign_of(r)
        r["cents"] = _cents(r.get("gross")) * r["sign"]
        r["net_cents"] = _cents(r.get("net")) * r["sign"]
        r["status"] = _status_of(r, reversed_ids, euer_report)
        known = categories.get(r.get("category")) or {}
        # An unknown category shows as its raw key rather than disappearing: master_data.yaml is
        # the bookkeeper's to extend, and this command never writes it.
        r["category_label"] = known.get("label") or r.get("category") or "—"
        # THE FORM LINE IS A NUMBER OR IT IS NOTHING, and that reading belongs to the script that
        # owns the vocabulary (`euer_report.line_number`), not to a second one here: a category
        # whose `euer_line` is a caption, a range or absent names no line, and its money is
        # reported under its own heading rather than attached to a line nobody chose.
        r["euer_line"] = known.get("euer_line")
        r["euer_line_label"] = known.get("euer_line_label") or ""
        r["quarter"] = "Q%d" % ((int(r["doc_date"][5:7]) - 1) // 3 + 1)
    rows.sort(key=lambda r: (r["doc_date"], r["id"]), reverse=True)

    # THE SAME ROWS AS THE REPORT SEES THEM. `euer_report.py` opens one file per year, so a
    # reversal booked in another year's file does not exist for it -- and a cross-year storno is
    # routine (`ledger_add.validate_cross` accepts it explicitly). The page keeps both readings:
    # its own views use the one that knows every file, the EÜR tab's open-item count follows the
    # report, because that tab is this page's copy of it.
    by_file = defaultdict(list)
    for r in rows:
        by_file[r["year"]].append(r)
    report_rows = []
    for year_rows in by_file.values():
        within_file = _cancelled_ids(year_rows)
        report_rows.extend(dict(r, status=_status_of(r, within_file, euer_report))
                           for r in year_rows)

    dates = [r["doc_date"] for r in rows] + [r["payment_date"] for r in rows if r["payment_date"]]
    data = {
        "business": {"name": (profile.get("business") or {}).get("name") or "",
                     "legal_form": (profile.get("business") or {}).get("legal_form") or "",
                     "kleinunternehmer": (profile.get("tax") or {}).get("kleinunternehmer"),
                     "founding_year": (profile.get("tax") or {}).get("founding_year")},
        # ONE READ, carried on the data: the term and the sentence that says whose it is belong
        # together, and a second read in a view is how the toolbar and the footnote come to name
        # two different numbers.
        "payment_term": payment_term_days(profile),
        "sources": sources,
        "strays": strays,
        "rows": rows,
        "report_rows": report_rows,
        "years": sorted({s["year"] for s in sources}, reverse=True),
        "categories": categories,
        "datenstand": max(dates) if dates else "",
        "valid": all(s["valid"] for s in sources),
        "euer_report": euer_report,
        # THE FORM YEAR, ITS SOURCE AND THE GWG THRESHOLD, read by the script that owns the
        # vocabulary and not a second time here (FR-0076). This page therefore carries no line
        # number, no form year and no threshold of its own -- a renumbered Anlage EÜR is one edit
        # in `project_memory/master_data.yaml` and both readers follow.
        "vocabulary": euer_report.read_vocabulary(root),
    }
    # Last, because it asks the assembled data (the § 19 watch reads the ledger years).
    data["tax"] = tax_state(data)
    return data


def paid_in(data, year, quarter=None):
    """Zufluss/Abfluss: counted by PAYMENT date, the way `euer_report.py` counts (§ 11 EStG)."""
    if quarter:
        start, end = data["euer_report"].quarter_range(int(year), quarter)
    else:
        start, end = "%s-01-01" % year, "%s-12-31" % year
    return [r for r in data["rows"] if r["payment_date"] and start <= r["payment_date"] <= end]


def totals(entries):
    income = sum(r["cents"] for r in entries if r["direction"] == "income")
    expense = sum(r["cents"] for r in entries if r["direction"] == "expense")
    return income, expense


def money(entries, vat_applies=True):
    """Brutto, USt and Netto of one selection -- the three lines the overview and the EÜR tab show.

    `gross` is the sum the report prints. `vat` is the part of it the report counts as
    Umsatzsteuer, so only rows whose treatment is `VAT_TREATMENT_IN_ZAHLLAST` contribute. `net` is
    the remainder, DERIVED rather than summed from the `net` column, so the three lines always add
    up: in a row with any other treatment the difference between gross and net is not German VAT
    (an OSS row carries another member state's), and subtracting it would print a Netto no line of
    the report backs. `other_vat` is exactly that residue, kept so the page can name it instead of
    swallowing it.

    `vat_applies=False` is the § 19 half that an aggregation over rows forgets, and it is not a
    display option: a Kleinunternehmer charges no VAT AND deducts no Vorsteuer, so the tax inside
    a supplier's invoice is a cost and not a claim: § 19 Abs. 1 UStG makes the Umsatz steuerfrei,
    and for a steuerfreier Umsatz § 15 Abs. 2 Satz 1 Nr. 1 UStG excludes the Vorsteuerabzug (§ 15
    Abs. 3, which gives it back for some exempt turnover, explicitly does not apply to § 19).
    Measured against the `regular` fixture, whose income is booked `kleinunternehmer` and whose
    expenses are `standard`: following the rows alone printed "USt-Zahllast −6.077,56 €".
    """
    if not vat_applies:
        gross = sum(r["cents"] for r in entries)
        return {"gross": gross, "vat": 0, "net": gross, "carries_vat": False,
                "other_vat": 0, "other_rows": 0, "rows": len(entries)}
    taxed = [r for r in entries if r["vat_treatment"] == VAT_TREATMENT_IN_ZAHLLAST]
    other = [r for r in entries if r["vat_treatment"] != VAT_TREATMENT_IN_ZAHLLAST
             and r["cents"] != r["net_cents"]]
    gross = sum(r["cents"] for r in entries)
    vat = sum(r["cents"] - r["net_cents"] for r in taxed)
    return {"gross": gross, "vat": vat, "net": gross - vat, "carries_vat": bool(taxed),
            "other_vat": sum(r["cents"] - r["net_cents"] for r in other),
            "other_rows": len(other), "rows": len(entries)}


def split_totals(entries, vat_applies=True):
    """The three figures per direction, and their difference.

    The difference's USt IS the Zahllast -- Umsatzsteuer taken in minus Vorsteuer paid -- and its
    Netto is the result after VAT. Both are what the reader asked to see without opening the
    report (FR-0032, user feedback of 2026-09-02).
    """
    income = money([r for r in entries if r["direction"] == "income"], vat_applies)
    expense = money([r for r in entries if r["direction"] == "expense"], vat_applies)
    surplus = {key: income[key] - expense[key] for key in ("gross", "net", "vat", "other_vat")}
    surplus["carries_vat"] = income["carries_vat"] or expense["carries_vat"]
    surplus["other_rows"] = income["other_rows"] + expense["other_rows"]
    surplus["rows"] = income["rows"] + expense["rows"]
    return {"income": income, "expense": expense, "surplus": surplus}


def tax_state(data):
    """May this page print Umsatzsteuer figures at all -- and if not, which sentence stands there.

    THE FIELD DECIDES, AND ONLY TWO VALUES DECIDE ANYTHING. `tax.kleinunternehmer` is a yes/no
    question, so exactly `True` and exactly `False` are answers and EVERYTHING else -- the shipped
    `null`, a quoted `"true"`, a `Ja`, a missing `tax:` block, a number -- is the absence of one.
    Reading it as "not True, therefore Regelbesteuerung" was an enumeration with one entry and a
    silent fall-through: measured 2026-09-02 against the `regular` fixture, `"true"`, `Ja` and a
    missing block each printed "USt-Zahllast −6.077,56 €" -- the refund the docstring of `money()`
    calls impossible -- while `true` and `yes` printed the sentence. The chain started in the
    SHIPPED state: the office kit's `business_profile.yaml` template carries `kleinunternehmer:
    null`.

    So: `True` -> § 19; `False` -> Regelbesteuerung, the rows carry the answer; anything else ->
    UNKNOWN, and unknown is treated like the § 19 watch's own undecidable case -- no USt figure,
    no Zahllast, and a sentence that names the field and the two values that answer it. The
    workshop measures every one of those spellings in
    `tools/test_finance_dashboard.py::test_only_a_boolean_answers_the_tax_question`.

    Under § 19 there is one more split: the watch may CONTRADICT the field (limit exceeded, or no
    previous year to decide it with). Then neither a figure nor the § 19 sentence is
    defensible -- the `alarm` fixture is exactly that, and following the rows there printed a
    Vorsteuer refund of 5.932,60 € beside a banner saying the relief had ended.
    """
    answer = data["business"]["kleinunternehmer"]
    if answer is False:
        return {"status": "regular", "applies": True, "short": "", "why": ""}
    if answer is not True:
        return {"status": "unknown", "applies": False,
                "short": "Steuerstatus nicht belastbar",
                "why": "Ob dieses Unternehmen Umsatzsteuer ausweist, steht in keiner Datei "
                       "dieses Projekts: business_profile.yaml trägt unter tax.kleinunternehmer "
                       "%s statt true oder false. Ohne diese Antwort ist jede USt-Summe und jede "
                       "Zahllast geraten, darum steht hier keine. Eintragen: "
                       "tax.kleinunternehmer: true (Kleinunternehmer nach § 19 UStG) oder false "
                       "(Regelbesteuerung)." % _as_written(answer)}
    watch = threshold(data)
    if watch is None or watch["verdict"] == "within":
        return {"status": "kleinunternehmer", "applies": False,
                "short": "keine USt — Kleinunternehmer § 19 UStG",
                "why": "Kleinunternehmer nach § 19 Abs. 1 UStG: die Umsätze sind steuerfrei, es "
                       "wird keine Umsatzsteuer ausgewiesen, und für steuerfreie Umsätze ist der "
                       "Vorsteuerabzug ausgeschlossen (§ 15 Abs. 2 Satz 1 Nr. 1 UStG) — Brutto "
                       "ist deshalb gleich Netto, und es gibt keine Zahllast. Die Vorsteuer in "
                       "Lieferantenrechnungen ist hier Kosten, kein Erstattungsanspruch."}
    reason = ("die Umsatzgrenze ist überschritten" if watch["exceeded"]
              else "ohne Vorjahr im Ledger ist die Grenze nicht prüfbar")
    return {"status": "kleinunternehmer_unclear", "applies": False,
            "short": "USt nicht belastbar",
            "why": "Das Profil sagt Kleinunternehmer § 19 UStG, aber %s (Reiter "
                   "„Kleinunternehmer“). Damit sagt keine Datei dieses Projekts, ob für diesen "
                   "Zeitraum Umsatzsteuer auszuweisen und Vorsteuer abziehbar war; die Seite "
                   "zeigt darum weder eine USt-Summe noch eine Zahllast. Mit der Steuerberatung "
                   "klären." % reason}


def _as_written(answer):
    """How to name a non-answer on the page -- in the FILE's language, not Python's.

    `repr` printed `[True]` for a YAML `[true]` and `'true'` for a quoted string: spellings no
    reader of `business_profile.yaml` has ever seen. A string is quoted the way it stands there, a
    number stands as it is, and a list or a mapping is named rather than dumped. The two booleans
    never arrive here -- they are the answers.
    """
    if answer is None:
        return "nichts"
    if isinstance(answer, str):
        return 'den Wert "%s"' % answer
    if isinstance(answer, (list, tuple)):
        return "eine Liste"
    if isinstance(answer, dict):
        return "eine Zuordnung"
    return "den Wert %s" % answer


def vat_line_text(data, entries):
    """What stands in the USt line where no figure may be printed.

    Either the tax state's own sentence (`tax_state`), or -- where VAT applies but nothing in this
    selection carries any -- what the rows themselves say, in the ledger's own vocabulary.
    """
    if not data["tax"]["applies"]:
        return data["tax"]["short"]
    treatments = sorted({r["vat_treatment"] for r in entries if r["vat_treatment"]})
    if not treatments:
        return "keine USt — keine bezahlte Buchung in diesem Zeitraum"
    return "keine USt — USt-Behandlung der Belege: %s" % ", ".join(treatments)


SPLIT_LINES = (("gross", "Brutto"), ("net", "Netto"), ("vat", "USt"))

# The sign convention, said once and printed where the figures are: everything else on the page
# reads it off this sentence.
VAT_RULE_NOTE = ("Unter jeder Zahl stehen Brutto, Netto und USt: als USt zählt, was der "
                 "EÜR-Bericht als Umsatzsteuer führt, Netto ist der Rest. Die USt-Zahllast ist "
                 "vereinnahmte USt minus Vorsteuer; ein negativer Betrag ist ein "
                 "Vorsteuerüberhang, also eine Erstattung.")


def vat_block_note(data):
    """The one sentence that explains the three lines of a block -- the split, or why there is none."""
    return VAT_RULE_NOTE if data["tax"]["applies"] else data["tax"]["why"]


def other_vat_note(split):
    """Tax that sits INSIDE the gross sums and outside the Zahllast, named per direction.

    An OSS row carries another member state's VAT and an exempt row none at all; both are gross
    figures whose `gross - net` the report does not count. Silently dropping that residue would
    make Brutto, Netto and USt add up while the reader has no way to see why the USt line is
    smaller than the tax in the documents.
    """
    said = []
    for key, label in (("income", "Einnahmen"), ("expense", "Ausgaben")):
        part = split[key]
        if part["other_rows"]:
            said.append("%s %s (%d %s)"
                        % (label, fmt_eur(part["other_vat"]), part["other_rows"],
                           plural(part["other_rows"], "Beleg", "Belege")))
    if not said:
        return ""
    return ('<p class="rule-note">Nicht in der USt-Zahllast, weil der EÜR-Bericht nur '
            '<code>%s</code> als Umsatzsteuer führt: %s. Diese Steuer steckt im Brutto.</p>'
            % (e(VAT_TREATMENT_IN_ZAHLLAST), e(" · ".join(said))))


def split_lines(data, entries, split, key, zahllast=False):
    """The three lines under one figure -- (name, label, text, css) each, ONE computation.

    Both places that show them render from this list (the overview and the EÜR tab), so the two
    cannot say different things about the same period. The USt line is the one that changes shape:
    where nothing in the selection carries VAT into the Zahllast it is a sentence rather than a
    zero (`vat_line_text`), and where it is the difference of the two directions it is the
    Zahllast itself.
    """
    part = split[key]
    mine = [r for r in entries if key == "surplus" or r["direction"] == key]
    lines = []
    for name, label in SPLIT_LINES:
        css, text = "", fmt_eur(part[name])
        if name == "vat":
            if not part["carries_vat"]:
                # NOT "USt-Zahllast: <sentence>". Where no VAT figure may be printed there is no
                # Zahllast to name either, and a label carries a claim as much as a number does.
                css, text = "sentence", vat_line_text(data, mine)
            elif zahllast:
                label = "USt-Zahllast"
        lines.append(("%s-%s" % (key, name), label, text, css))
    return lines


def split_dl_html(lines):
    """The three lines of a KPI figure, as a definition list. The FIRST one is the big figure."""
    return "".join('<div class="line %s%s"><dt>%s</dt><dd class="amt" data-figure="%s">%s</dd>'
                   '</div>' % ("big " if index == 0 else "", css, e(label), name, e(text))
                   for index, (name, label, text, css) in enumerate(lines))


def split_rows_html(lines, head, css=""):
    """The three lines as journal rows, the figure's name spanning them."""
    out = []
    for index, (name, label, text, style) in enumerate(lines):
        head_cell = ('<th rowspan="%d">%s</th>' % (len(lines), e(head))) if index == 0 else ""
        out.append('<tr class="%s%s">%s<td class="sub">%s</td>'
                   '<td class="amt" data-figure="%s">%s</td></tr>'
                   % (css if index == 0 else "", style, head_cell, e(label), name, e(text)))
    return "".join(out)


def open_items(rows, direction):
    return [r for r in rows if r["status"] == "offen" and r["direction"] == direction]


def open_until(data, year, end):
    """Open items of ONE ledger year up to `end`, counted the way the EÜR report counts them.

    TWO restrictions, and both are the report's, not this page's. The YEAR, because
    `euer_report.py` opens `ledger/<year>.csv` and nothing else -- and the ledger's filing rule
    puts an open row (no payment date) in the file of its document year
    (`ledger_add.validate_cross`), so that file is where the report finds them. And the STATUS out
    of `report_rows`, because a storno booked in another year's file is invisible to the report
    while this page sees it -- the EÜR tab is the page's copy of the report, so it counts what the
    report counts and says where the two differ.
    """
    return [r for r in data["report_rows"]
            if r["year"] == year and r["status"] == "offen" and r["doc_date"] <= end]


def open_until_cancelled_elsewhere(data, year, end):
    """The rows `open_until` counts that a reversal in ANOTHER ledger file has cancelled.

    The measured difference between the two readings, so the page can name it rather than show two
    numbers for one thing: measured 2026-09-02, an open 2025 invoice reversed in `2026.csv` (which
    `ledger_add.validate_cross` accepts as routine) is one open item on the open-items tab and two
    in the report for 2025 Q4.
    """
    cancelled = _cancelled_ids(data["rows"])
    return [r for r in open_until(data, year, end) if r["id"] in cancelled]


def threshold(data):
    """§ 19 UStG watch, in cents. Only where the profile says the business uses the rule.

    A VERDICT PER CONDITION, and "no previous year in the ledger" is one of them because reading
    it as "within" was a wrong statement about somebody's tax: the previous-year condition is not
    decidable, and until 2026-09-02 that fell through to "within" -- a founding year with 26.000 €
    turnover read "innerhalb der Grenzen — 26.000 von 100.000", while § 19 in the wording in force
    since 2025 puts a business without a previous year under the 25.000 € limit for the CURRENT
    year.

    WHAT SETTLES IT IS `tax.founding_year`, and until TSK-0116 the field did not exist -- the page
    then had to refuse the statement and name both cases. It exists now, and it decides EXACTLY the
    one question the missing previous year leaves open: is there no previous year, or only no file
    for it? A founding year EQUAL to the current one is the first case -- there is no previous-year
    condition to check, and the current year runs against the 25.000 € limit. Anything else is the
    second, and the page goes on refusing rather than guessing
    (`tools/test_finance_dashboard.py::test_the_founding_year_decides_the_case_the_missing_previous_year_leaves_open`).
    """
    if data["business"]["kleinunternehmer"] is not True or not data["years"]:
        return None
    current = data["years"][0]
    previous = str(int(current) - 1)
    founding = _year_number(data["business"]["founding_year"])
    first_year = founding is not None and founding == int(current)
    current_income = totals(paid_in(data, current))[0]
    previous_income = totals(paid_in(data, previous))[0] if previous in data["years"] else None
    previous_over = (previous_income is not None
                     and previous_income > KLEINUNTERNEHMER_LIMIT_PREVIOUS_YEAR)
    # THE LIMIT OF THE CURRENT YEAR IS NOT ONE NUMBER. § 19 Abs. 1 UStG in the wording in force
    # since 2025 puts a business in its FOUNDING year under the 25.000 € figure straight away,
    # while every later year runs against 100.000 €. Deciding that is the whole reason the field
    # above is read here.
    limit_current = (KLEINUNTERNEHMER_LIMIT_PREVIOUS_YEAR if first_year
                     else KLEINUNTERNEHMER_LIMIT_CURRENT_YEAR)
    current_over = current_income > limit_current
    if current_over:
        verdict = "current_exceeded"
    elif previous_over:
        verdict = "previous_exceeded"
    elif previous_income is None and not first_year:
        verdict = "previous_unknown"
    else:
        verdict = "within"
    return {"current_year": current, "previous_year": previous, "current": current_income,
            "previous": previous_income, "verdict": verdict,
            "exceeded": previous_over or current_over,
            "founding_year": founding, "first_year": first_year,
            "limit_previous": KLEINUNTERNEHMER_LIMIT_PREVIOUS_YEAR,
            "limit_current": limit_current}


def _founding_year_note(watch):
    """Why the previous year stays undecidable — the FIELD's answer, not one sentence for both.

    Two different situations end in `previous_unknown` and they need two different next steps: the
    profile names no founding year (then filling it settles the case), or it names one that is not
    the current year (then the ledger file is what is missing). Until TSK-0116 one sentence claimed
    the first for both, and it claimed it about a field that did not exist yet.
    """
    if watch["founding_year"] is None:
        return ("Welcher der beiden Fälle es ist, steht in keinem Feld dieses Projekts — tragen "
                "Sie das Gründungsjahr in business_profile.yaml unter tax.founding_year ein, dann "
                "entscheidet diese Seite den Fall; sonst mit der Steuerberatung klären.")
    return ("business_profile.yaml nennt %d als Gründungsjahr, also ist %s nicht das erste Jahr "
            "und es fehlt die Ledgerdatei des Vorjahres; mit der Steuerberatung klären."
            % (watch["founding_year"], watch["current_year"]))


def _year_number(value):
    """The calendar year this profile value names, or None -- never a guess.

    A YAML `founding_year: 2026` is an int and `"2026"` is a string, and both are what a hand-edited
    profile really carries; anything that is not four digits (a date, a sentence, `null`, `true`)
    names no year and leaves the § 19 watch exactly where it was without this field.
    """
    if isinstance(value, bool):
        return None
    text = str(value if value is not None else "").strip()
    return int(text) if re.fullmatch(r"\d{4}", text) else None


# --- rendering -----------------------------------------------------------------------------


def source_line(data, year=None, count=None, label=("Zeile", "Zeilen")):
    """Under every figure: which file it was read from and how many rows went into it.

    `label` is a PAIR and goes through `plural()` like every other count on this page -- a
    one-row ledger read "1 bezahlte Zeilen" until 2026-09-02, in the fixture built for the
    founding year, which is exactly the project that has one row.
    """
    files = [s for s in data["sources"] if year is None or s["year"] == year]
    names = ", ".join(s["file"] for s in files) or "kein Ledger"
    number = count if count is not None else sum(s["rows"] for s in files)
    return ('<span class="src">aus %s · %d %s</span>'
            % (e(names), number, e(plural(number, label[0], label[1]))))


def row_html(r, compact=False):
    struck = ' class="struck"' if r["status"] == "storniert" else ""
    stamp = {"bezahlt": '<span class="stamp ok">bezahlt</span>',
             "offen": '<span class="stamp open">offen</span>',
             "storniert": '<span class="stamp">storniert</span>',
             "korrektur": '<span class="stamp">Korrektur</span>'}[r["status"]]
    text = " ".join([r["counterparty"], r["invoice_no"], r["id"], r["note"],
                     r["category_label"]]).lower()
    attrs = ('data-year="%s" data-q="%s" data-dir="%s" data-status="%s" data-cat="%s" '
             'data-cp="%s" data-cents="%d" data-doc-date="%s" data-text="%s"'
             % (r["year"], r["quarter"], r["direction"], r["status"], e(r["category"]),
                e(r["counterparty"]), r["cents"], r["doc_date"], e(text)))
    amount = fmt_eur(r["cents"])
    if compact:
        return ('<tr %s%s><td class="date">%s</td><td class="cp">%s <span class="muted small">%s'
                '</span></td><td class="amt %s">%s</td><td class="st">%s</td></tr>'
                % (attrs, struck, e(fmt_date(r["doc_date"])), e(r["counterparty"]),
                   e(r["category_label"]), r["direction"], e(amount), stamp))
    detail = ('<dl><dt>Beleg-Id</dt><dd><code>%s</code></dd><dt>Belegart</dt><dd>%s</dd>'
              '<dt>USt-Behandlung</dt><dd>%s</dd><dt>Quelle</dt><dd><code>%s</code></dd>%s%s</dl>'
              % (e(r["id"]), e(r["doc_type"]), e(r["vat_treatment"]), e(r["source"]),
                 '<dt>Storniert</dt><dd><code>%s</code></dd>' % e(r["reverses"])
                 if r["reverses"] else "",
                 '<dt>Notiz</dt><dd>%s</dd>' % e(r["note"]) if r["note"] else ""))
    return ('<tr %s%s><td class="date">%s</td><td class="no"><code>%s</code></td>'
            '<td class="cp">%s</td><td class="cat">%s</td><td class="amt">%s</td>'
            '<td class="amt">%s</td><td class="amt %s">%s</td><td class="pay">%s</td>'
            '<td class="st">%s</td></tr><tr class="detail" hidden><td colspan="9">%s</td></tr>'
            % (attrs, struck, e(fmt_date(r["doc_date"])), e(r["invoice_no"] or "—"),
               e(r["counterparty"]), e(r["category_label"]), e(fmt_eur(r["net_cents"])),
               e(fmt_eur(r["cents"] - r["net_cents"])), r["direction"], e(amount),
               e(fmt_date(r["payment_date"]) or "—"), stamp, detail))


def view_ueberblick(data):
    if not data["years"]:
        return ('<section id="view-ueberblick" class="view" role="tabpanel">'
                '<div class="empty"><p class="empty-lead">Noch keine Buchung.</p>'
                '<p>Diese Seite rechnet aus <code>ledger/&lt;Jahr&gt;.csv</code>. Die erste '
                'Buchung schreibt die Buchhaltung mit <code>python scripts/ledger_add.py</code> — '
                'sobald eine Zeile dort steht, stehen hier Einnahmen, Ausgaben und Überschuss.'
                '</p></div></section>')
    newest = data["years"][0]
    parts = ['<section id="view-ueberblick" class="view" role="tabpanel">']
    parts.append('<div class="toolbar"><label>Jahr <select data-filter="year" '
                 'data-scope="ueberblick">%s</select></label></div>'
                 % "".join('<option value="%s">%s</option>' % (y, y) for y in data["years"]))
    for year in data["years"]:
        paid = paid_in(data, year)
        split = split_totals(paid, data["tax"]["applies"])
        hidden = "" if year == newest else " hidden"
        parts.append('<div class="year-block" data-year="%s"%s>' % (year, hidden))
        parts.append('<div class="ledger-row kpis">')
        for label, key, css in (("Einnahmen", "income", ""), ("Ausgaben", "expense", ""),
                                ("Überschuss", "surplus", " total")):
            lines = split_lines(data, paid, split, key, zahllast=(key == "surplus"))
            # The Brutto line IS the big figure -- it carries the display face rather than being
            # repeated above the split, which would print one amount twice in one card.
            parts.append('<div class="kpi%s"><span class="label">%s</span>'
                         '<dl class="split">%s</dl>%s</div>'
                         % (css, label, split_dl_html(lines),
                            source_line(data, year, len(paid),
                                        ("bezahlte Zeile", "bezahlte Zeilen"))))
        parts.append('</div>')
        parts.append('<p class="rule-note">Zahlungsprinzip: gezählt wird, was im Jahr %s bezahlt '
                     'wurde (Zufluss/Abfluss). Offene Rechnungen stehen unter '
                     '<a href="#offene-posten">Offene Posten</a>. %s</p>'
                     % (year, e(vat_block_note(data))))
        parts.append(other_vat_note(split))
        receivables = open_items(data["rows"], "income")
        payables = open_items(data["rows"], "expense")
        watch = threshold(data)
        parts.append('<h2>Jetzt ansteht</h2><ul class="due">')
        # The COUNT is the browser's (H118), so the noun beside it has to be too -- but both
        # spellings come from here, the way `plural()` picks them everywhere else: the script only
        # applies the rule. Sighted 2026-09-02 as "1 Mahnkandidaten", the same defect class as
        # "1 Rechnungen zu zahlen" one round earlier, in the half a Python helper cannot reach.
        parts.append('<li><a href="#offene-posten"><span class="figure-s">%d</span> %s · %s</a> '
                     '<span class="muted">— davon <span data-overdue-count>…</span> '
                     '<span data-overdue-word data-one="%s" data-many="%s">%s</span>, älter als '
                     '%d Tage</span></li>'
                     % (len(receivables),
                        plural(len(receivables), "offene Forderung", "offene Forderungen"),
                        e(fmt_eur(sum(r["cents"] for r in receivables))),
                        e("Mahnkandidat"), e("Mahnkandidaten"), e("Mahnkandidaten"),
                        data["payment_term"][0]))
        parts.append('<li><a href="#offene-posten"><span class="figure-s">%d</span> %s · %s</a>'
                     '</li>'
                     % (len(payables),
                        plural(len(payables), "Rechnung zu zahlen", "Rechnungen zu zahlen"),
                        e(fmt_eur(sum(r["cents"] for r in payables)))))
        if watch:
            verdict = {"within": "innerhalb der Grenzen",
                       "previous_unknown": "kein Vorjahr im Ledger — die Vorjahresgrenze ist hier "
                                           "nicht entscheidbar",
                       "previous_exceeded": "Vorjahresgrenze überschritten — Regelbesteuerung seit "
                                            "1. Januar prüfen",
                       "current_exceeded": "Grenze im laufenden Jahr überschritten — ab dem "
                                           "überschreitenden Umsatz Regelbesteuerung"}[
                watch["verdict"]]
            css = ' class="alarm"' if watch["exceeded"] else ""
            if watch["previous"] is not None:
                previous_said = ("Vorjahr %s von %s"
                                 % (fmt_eur(watch["previous"]), fmt_eur(watch["limit_previous"])))
            elif watch["first_year"]:
                # NOT "keine Ledgerdatei": in the founding year there is no previous year, so
                # reporting a missing FILE would name a gap the business does not have.
                previous_said = "Gründungsjahr %s — es gibt kein Vorjahr" % watch["current_year"]
            else:
                previous_said = "Vorjahr: keine Ledgerdatei für %s" % watch["previous_year"]
            # WHICH LIMIT the current year is measured against is only settled once the previous
            # year is: without it, 25.000 € (founding year) and 100.000 € are both live, and
            # naming one of them here made the figure contradict the verdict it links to.
            current_said = ("laufendes Jahr %s von %s oder %s, je nach Gründungsjahr"
                            % (fmt_eur(watch["current"]),
                               fmt_eur(watch["limit_current"]),
                               fmt_eur(watch["limit_previous"]))
                            if watch["verdict"] == "previous_unknown"
                            else "laufendes Jahr %s von %s" % (fmt_eur(watch["current"]),
                                                               fmt_eur(watch["limit_current"])))
            parts.append('<li%s><a href="#kleinunternehmer">Kleinunternehmer § 19 UStG: %s</a> '
                         '<span class="muted">— %s; %s</span></li>'
                         % (css, e(verdict), e(current_said), e(previous_said)))
        elif data["tax"]["status"] == "unknown":
            # ON THE OVERVIEW, not only on the tab behind it: this line hung on `is None` until
            # 2026-09-02, so a profile carrying `"true"` or `Ja` showed no warning at all here.
            # SHORT, because the reason stands in full above the figures it is about -- printed
            # twice it read as two findings, which is what the first sighting of the `unclear`
            # fixture showed.
            parts.append('<li class="muted">Keine Schwellenwache: '
                         '<code>tax.kleinunternehmer</code> trägt keine Antwort — der Grund steht '
                         'über den Zahlen.</li>')
        parts.append('<li>%s</li>'
                     % ('Ledger geprüft: <span class="stamp ok">gültig</span>' if data["valid"]
                        else 'Ledger geprüft: <span class="stamp alarm">ungültig</span> — die '
                             'Summen oben sind nicht belastbar, Befunde im Kopf der Seite'))
        for stray in data["strays"]:
            parts.append('<li class="muted">Nicht gelesen: <code>%s</code> — Meldung des Prüfers: %s</li>'
                         % (e(stray["file"]), e(stray["findings"][0])))
        parts.append('</ul>')
        months = []
        for month in range(1, 13):
            months.append(totals([r for r in paid if int(r["payment_date"][5:7]) == month]))
        peak = max([max(i, x) for i, x in months] + [1])
        parts.append('<h2>Monat für Monat <span class="muted">(bezahlt, brutto)</span></h2>'
                     '<div class="flow">')
        for index, (income_m, expense_m) in enumerate(months):
            parts.append('<div class="month"><div class="bars">'
                         '<span class="bar in" style="height:%d%%" title="Einnahmen %s"></span>'
                         '<span class="bar out" style="height:%d%%" title="Ausgaben %s"></span>'
                         '</div><span class="mlabel">%s</span></div>'
                         % (round(100 * income_m / peak), e(fmt_eur(income_m)),
                            round(100 * expense_m / peak), e(fmt_eur(expense_m)),
                            GERMAN_MONTHS[index]))
        parts.append('</div><p class="legend"><span class="sw in"></span> Einnahmen '
                     '<span class="sw out"></span> Ausgaben</p>')
        last = [r for r in data["rows"] if r["year"] == year][:6]
        parts.append('<h2>Zuletzt gebucht</h2><table class="ledger compact">%s</table>'
                     % "".join(row_html(r, compact=True) for r in last))
        parts.append('<p class="more"><a href="#rechnungen">Alle Buchungen →</a></p>')
        parts.append('</div>')
    parts.append('</section>')
    return "".join(parts)


def view_rechnungen(data):
    if not data["years"]:
        return ('<section id="view-rechnungen" class="view" role="tabpanel" hidden>'
                '<div class="empty"><p class="empty-lead">Keine Rechnungen.</p>'
                '<p>Die Liste füllt sich mit der ersten Buchung.</p></div></section>')
    cats = sorted({(r["category"], r["category_label"]) for r in data["rows"]}, key=lambda t: t[1])
    counterparties = sorted({r["counterparty"] for r in data["rows"]})

    def options(pairs):
        return "".join('<option value="%s">%s</option>' % (e(value), e(label))
                       for value, label in pairs)

    parts = ['<section id="view-rechnungen" class="view" role="tabpanel" hidden>']
    parts.append('<form class="filters" data-scope="rechnungen" onsubmit="return false">'
                 '<input type="search" data-filter="text" placeholder="Suchen: Gegenpartei, '
                 'Rechnungsnummer, Notiz" aria-label="Suchen">'
                 '<label>Richtung <select data-filter="dir"><option value="">alle</option>'
                 '<option value="income">Einnahmen</option>'
                 '<option value="expense">Ausgaben</option></select></label>'
                 '<label>Status <select data-filter="status"><option value="">alle</option>'
                 '<option value="offen">offen</option><option value="bezahlt">bezahlt</option>'
                 '<option value="storniert">storniert</option>'
                 '<option value="korrektur">Korrekturen</option></select></label>'
                 '<label>Jahr <select data-filter="year"><option value="">alle</option>%s</select>'
                 '</label>'
                 '<label>Quartal <select data-filter="q"><option value="">alle</option>'
                 '<option>Q1</option><option>Q2</option><option>Q3</option><option>Q4</option>'
                 '</select></label>'
                 '<label>Kategorie <select data-filter="cat"><option value="">alle</option>%s'
                 '</select></label>'
                 '<label>Gegenpartei <select data-filter="cp"><option value="">alle</option>%s'
                 '</select></label>'
                 '<button type="reset" class="link">Filter zurücksetzen</button></form>'
                 % (options([(y, y) for y in data["years"]]), options(cats),
                    options([(c, c) for c in counterparties])))
    parts.append('<p class="count"><span data-count>%d</span> von %d '
                 '<span data-count-word data-one="%s" data-many="%s">%s</span> · Summe brutto '
                 '<span class="figure-s total" data-sum>%s</span> %s</p>'
                 % (len(data["rows"]), len(data["rows"]), e("Buchung"), e("Buchungen"),
                    e(plural(len(data["rows"]), "Buchung", "Buchungen")),
                    e(fmt_eur(sum(r["cents"] for r in data["rows"]))), source_line(data)))
    parts.append('<table class="ledger full"><thead><tr><th>Datum</th><th>Nr.</th>'
                 '<th>Gegenpartei</th><th>Kategorie</th><th class="amt">Netto</th>'
                 '<th class="amt">USt</th><th class="amt">Brutto</th><th>Bezahlt am</th>'
                 '<th>Status</th></tr></thead><tbody>')
    parts.extend(row_html(r) for r in data["rows"])
    parts.append('</tbody></table><p class="show-all"><button type="button" class="link">alle '
                 'anzeigen</button></p>'
                 '<p class="hint">Eine Zeile aufklappen zeigt Beleg-Id, Belegart, USt-Behandlung '
                 'und die Quelle im Archiv. Korrekturen (Gutschrift, Erstattung, Storno) stehen '
                 'mit Minus in der Summe, so wie <code>euer_report.py</code> sie zählt. Ohne '
                 'Skript stehen alle Zeilen untereinander und die Filterleiste tut nichts.'
                 '</p></section>')
    return "".join(parts)


def view_offene_posten(data):
    parts = ['<section id="view-offene-posten" class="view" role="tabpanel" hidden>']
    if not data["years"]:
        parts.append('<div class="empty"><p class="empty-lead">Keine offenen Posten.</p>'
                     '<p>Eine Buchung ohne Zahlungsdatum erscheint hier.</p></div></section>')
        return "".join(parts)
    parts.append('<div class="toolbar"><label class="check"><input type="checkbox" '
                 'data-filter="overdue" data-scope="offene-posten"> nur Mahnkandidaten '
                 '<span class="muted">(Forderung älter als %d Tage, Stand heute)</span></label>'
                 '</div>' % data["payment_term"][0])
    for direction, title, lead in (("income", "Forderungen", "Was Kunden uns noch schulden"),
                                   ("expense", "Verbindlichkeiten", "Was wir noch zu zahlen haben")):
        items = sorted(open_items(data["rows"], direction), key=lambda r: r["doc_date"])
        parts.append('<h2>%s <span class="muted">— %s</span></h2>' % (title, lead))
        if not items:
            parts.append('<p class="empty-inline">Nichts offen.</p>')
            continue
        parts.append('<table class="ledger open" data-direction="%s"><thead><tr>'
                     '<th>Belegdatum</th><th>Alter</th><th>Nr.</th><th>Gegenpartei</th>'
                     '<th class="amt">Brutto</th><th></th></tr></thead><tbody>' % direction)
        for r in items:
            parts.append('<tr data-doc-date="%s" data-dir="%s" data-cents="%d" data-cp="%s">'
                         '<td class="date">%s</td><td class="age" data-age>—</td>'
                         '<td class="no"><code>%s</code></td><td class="cp">%s '
                         '<span class="muted small">%s</span></td><td class="amt %s">%s</td>'
                         '<td class="st" data-dun></td></tr>'
                         % (r["doc_date"], direction, r["cents"], e(r["counterparty"]),
                            e(fmt_date(r["doc_date"])), e(r["invoice_no"] or "—"),
                            e(r["counterparty"]), e(r["category_label"]), direction,
                            e(fmt_eur(r["cents"]))))
        parts.append('</tbody><tfoot><tr class="sum"><td colspan="4">Summe '
                     '<span class="muted">(<span data-count>%d</span> Posten)</span></td>'
                     '<td class="amt total" data-sum>%s</td><td></td></tr></tfoot></table>'
                     % (len(items), e(fmt_eur(sum(r["cents"] for r in items)))))
    parts.append('<p class="hint">Alter = Tage seit Belegdatum, gerechnet beim Öffnen der Seite '
                 'aus der Uhr dieses Rechners. Das Ledger kennt kein Fälligkeitsdatum; die Frist '
                 'von %d Tagen ist %s. Ohne Skript '
                 'bleibt in der Spalte Alter der Strich stehen und kein Posten trägt den Stempel '
                 '„mahnen".</p></section>' % data["payment_term"])
    return "".join(parts)


def line_text(line, caption):
    """How a form line is written on this page: `27 — Waren, …`, `27`, or an em dash for none."""
    if line is None:
        return "—"
    return "%d — %s" % (line, caption) if caption else "%d" % line


def _cents_of(amount):
    """A euro amount from the report's arithmetic as CENTS, the integer this page compares in."""
    return int(round(float(amount) * 100))


def line_table_html(data, paid):
    """The per-form-line summary — the SAME grouping `euer_report.by_form_line` writes (FR-0076).

    IMPORTED, NOT REBUILT, for the reason the module header gives about the sign convention: two
    answers about the same money is what `euer_report.py` records the cost of. What this function
    owns is the cents and the HTML;
    `tools/test_finance_dashboard.py::test_the_dashboard_and_the_report_agree_on_every_form_line`
    runs the real report over the same ledger and compares line for line.
    """
    vocabulary = data["vocabulary"]
    parts = ['<h3>Nach Zeile der Anlage EÜR%s</h3>'
             % e(data["euer_report"].form_year_suffix(vocabulary))]
    for problem in vocabulary["problems"]:
        parts.append('<p class="rule-note">%s</p>' % e(problem))
    rows = data["euer_report"].by_form_line(paid, vocabulary)
    if not rows:
        parts.append('<p class="empty-inline">Keine bezahlte Buchung in diesem Zeitraum.</p>')
        return "".join(parts)
    parts.append('<table class="ledger cats" data-scope="euer-lines"><thead><tr><th>Zeile</th>'
                 '<th class="amt">Einnahmen</th><th class="amt">Ausgaben</th></tr></thead><tbody>')
    for key, heading, income_sum, expense_sum in rows:
        income_c, expense_c = _cents_of(income_sum), _cents_of(expense_sum)
        parts.append('<tr data-line="%s"><td>%s</td><td class="amt">%s</td>'
                     '<td class="amt">%s</td></tr>'
                     % (e(str(key)), e(heading),
                        e(fmt_eur(income_c)) if income_c else "",
                        e(fmt_eur(expense_c)) if expense_c else ""))
    parts.append('</tbody></table><p class="rule-note">Die Beträge sind die des Belegjournals, '
                 'ungekürzt: keine Quote und keine Obergrenze, die das Formular auf eine einzelne '
                 'Zeile anwendet, ist hier eingerechnet.%s</p>'
                 % (e(" Herkunft der Zeilennummern: %s." % vocabulary["source"])
                    if vocabulary["source"] else ""))
    return "".join(parts)


def asset_hint_html(data, paid):
    """The AfA HINT and nothing else: a booking above the GWG threshold, and one sentence.

    No asset register, no depreciation, no branch on the legal form — FR-0076's third half is a
    flag that hands the question to the Steuerberatung, and both readers say the same sentence
    because both take it from `euer_report.ASSET_HINT`.
    """
    limit = data["vocabulary"]["gwg_limit_net"]
    if limit is None:
        return ""
    hints = data["euer_report"].asset_hints(paid, limit, data["vocabulary"]["no_hint"])
    if not hints:
        return ""
    parts = ['<h3>Mögliche Anlagegüter <span class="muted">(Hinweis, keine Abschreibung)</span>'
             '</h3><table class="ledger afa" data-scope="afa"><thead><tr><th>Belegdatum</th>'
             '<th>Nr.</th><th>Gegenpartei</th><th class="amt">Netto</th><th></th></tr></thead>'
             '<tbody>']
    for entry, net in sorted(hints, key=lambda pair: -pair[1]):
        parts.append('<tr data-afa="%s"><td class="date">%s</td><td class="no"><code>%s</code>'
                     '</td><td class="cp">%s</td><td class="amt">%s</td><td class="st">%s</td>'
                     '</tr>'
                     % (e(str(entry.get("id") or "")), e(fmt_date(entry.get("doc_date") or "")),
                        e(entry.get("invoice_no") or "—"), e(entry.get("counterparty") or ""),
                        e(fmt_eur(_cents_of(net))), e(data["euer_report"].ASSET_HINT)))
    parts.append('</tbody></table><p class="rule-note">Grenze: %s netto (§ 6 Abs. 2 EStG), aus '
                 '<code>project_memory/master_data.yaml</code>. Gemessen wird der BELEG, nicht die '
                 'einzelne Position — eine Rechnung über viele kleine Teile steht hier genauso wie '
                 'eine Maschine. Diese Seite führt kein Anlagenverzeichnis und rechnet keine '
                 'Abschreibung — keine Steuerberatung.</p>' % e(fmt_eur(_cents_of(limit))))
    return "".join(parts)


def view_euer(data):
    parts = ['<section id="view-euer" class="view" role="tabpanel" hidden>']
    if not data["years"]:
        parts.append('<div class="empty"><p class="empty-lead">Noch keine '
                     'Einnahmen-Ausgaben-Rechnung.</p><p>Sie entsteht aus dem Ledger, Quartal für '
                     'Quartal.</p></div></section>')
        return "".join(parts)
    parts.append('<div class="toolbar"><label>Jahr <select data-filter="year" data-scope="euer">%s'
                 '</select></label><label>Zeitraum <select data-filter="period" data-scope="euer">'
                 '<option value="year">ganzes Jahr</option><option value="1">Q1</option>'
                 '<option value="2">Q2</option><option value="3">Q3</option>'
                 '<option value="4">Q4</option></select></label></div>'
                 % "".join('<option value="%s">%s</option>' % (y, y) for y in data["years"]))
    for year in data["years"]:
        for period in ("year", 1, 2, 3, 4):
            paid = paid_in(data, year, None if period == "year" else period)
            split = split_totals(paid, data["tax"]["applies"])
            # The report's own informational VAT sums -- TWO of them, "vereinnahmte USt" and
            # "Vorsteuer", which `euer_report.py` prints for every profile and whatever the
            # treatment. It prints no Zahllast and never has (`grep -c Zahllast` on a generated
            # report: 0), so the difference below is this page's own arithmetic and is shown only
            # where it IS one. They are carried at all so the page does not silently differ from
            # the report where § 19 forbids the deduction.
            reported = split_totals(paid, True)
            by_category = defaultdict(lambda: [0, 0])
            # DOCUMENTS, not rows, and through `euer_report`'s own reader (DEC-0108): a mixed-VAT
            # document books one row per rate under a shared invoice number, so the page and the
            # report would differ by one per such document if either counted rows. Which is
            # exactly what
            # `tools/test_finance_dashboard.py::test_the_dashboard_and_euer_report_agree_on_every_quarter`
            # measures.
            reverse_charge = set()
            for r in paid:
                by_category[(r["category_label"], line_text(r["euer_line"], r["euer_line_label"]))][
                    0 if r["direction"] == "income" else 1] += r["cents"]
                if r["vat_treatment"] == "reverse_charge":
                    reverse_charge.add(data["euer_report"].document_key(r))
            reverse_charge = len(reverse_charge)
            if period == "year":
                period_end, label = "%s-12-31" % year, "Jahr %s" % year
            else:
                period_end = data["euer_report"].quarter_range(int(year), period)[1]
                label = "%s Q%d" % (year, period)
            hidden = "" if (year == data["years"][0] and period == "year") else " hidden"
            parts.append('<div class="euer-block" data-year="%s" data-period="%s"%s>'
                         % (year, period, hidden))
            parts.append('<h2>Einnahmen-Ausgaben-Gegenüberstellung %s <span class="muted">'
                         '(bezahlt im Zeitraum, brutto)</span></h2>' % label)
            # The SAME three lines as the overview, from the same renderer: Brutto, Netto, USt --
            # and for the difference the Zahllast, so the net result after VAT can be read here
            # without opening the report (FR-0032, user feedback of 2026-09-02).
            parts.append('<table class="ledger sums split"><tbody>')
            for label, key, css in (("Einnahmen", "income", ""), ("Ausgaben", "expense", ""),
                                    ("Überschuss", "surplus", "sum")):
                parts.append(split_rows_html(
                    split_lines(data, paid, split, key, zahllast=(key == "surplus")),
                    label, css))
            parts.append('</tbody></table>%s'
                         % source_line(data, year, len(paid),
                                        ("bezahlte Zeile", "bezahlte Zeilen")))
            parts.append('<p class="rule-note">%s</p>' % e(vat_block_note(data)))
            parts.append(other_vat_note(split))
            parts.append('<h3>Nach Kategorie</h3><table class="ledger cats"><thead><tr>'
                         '<th>Kategorie</th><th>Zeile Anlage EÜR</th><th class="amt">Einnahmen'
                         '</th><th class="amt">Ausgaben</th></tr></thead><tbody>')
            for (label_de, line), (income_c, expense_c) in sorted(by_category.items()):
                parts.append('<tr><td>%s</td><td class="muted">%s</td><td class="amt">%s</td>'
                             '<td class="amt">%s</td></tr>'
                             % (e(label_de), e(line),
                                e(fmt_eur(income_c)) if income_c else "",
                                e(fmt_eur(expense_c)) if expense_c else ""))
            parts.append('</tbody></table>')
            parts.append(line_table_html(data, paid))
            parts.append(asset_hint_html(data, paid))
            payload = ('' if not data["tax"]["applies"] else
                       ' · Zahllast: <span data-figure="report-vat-payload">%s</span>'
                       % e(fmt_eur(reported["surplus"]["vat"])))
            parts.append('<h3>Umsatzsteuer <span class="muted">(nur informativ)</span></h3>'
                         '<p>Vereinnahmte USt (%s): <span data-figure="report-vat-out">%s</span> · '
                         'Vorsteuer (%s): <span data-figure="report-vat-in">%s</span>%s · '
                         'Reverse-Charge-Belege (§ 13b): %d</p>'
                         % (e(VAT_TREATMENT_IN_ZAHLLAST), e(fmt_eur(reported["income"]["vat"])),
                            e(VAT_TREATMENT_IN_ZAHLLAST), e(fmt_eur(reported["expense"]["vat"])),
                            payload, reverse_charge))
            if not data["tax"]["applies"]:
                # The reason itself stands under the figures at the top of this block; repeating
                # it here would be the same sentence twice on one tab.
                parts.append('<p class="rule-note">Diese zwei Zahlen stehen so im EÜR-Bericht; '
                             'eine Zahllast folgt daraus in diesem Steuerzustand nicht (Grund '
                             'oben), und in der Aufstellung oben sind sie nicht als USt '
                             'geführt.</p>')
            cancelled_elsewhere = open_until_cancelled_elsewhere(data, year, period_end)
            parts.append('<p class="muted">Offene Posten bis Zeitraumende: '
                         '<span data-open-count>%d</span> — <a href="#offene-posten">Liste</a>%s'
                         '</p>'
                         % (len(open_until(data, year, period_end)),
                            '' if not cancelled_elsewhere else
                            ' <span data-cancelled-elsewhere>· davon %d in einem anderen '
                            'Ledgerjahr storniert: der Bericht liest nur <code>ledger/%s.csv</code>'
                            ' und sieht diese Stornos nicht, die Liste unter „Offene Posten“ '
                            'zeigt sie als storniert</span>'
                            % (len(cancelled_elsewhere), e(year))))
            parts.append('</div>')
    parts.append('<p class="hint">Der Bericht für die Steuerberatung entsteht mit '
                 '<code>python scripts/euer_report.py --year … --quarter …</code> unter '
                 '<code>reports/</code>. Diese Ansicht rechnet mit derselben Vorzeichenregel nach '
                 'und ersetzt ihn nicht. Keine Steuerberatung.</p></section>')
    return "".join(parts)


def view_kleinunternehmer(data):
    watch = threshold(data)
    parts = ['<section id="view-kleinunternehmer" class="view" role="tabpanel" hidden>']
    if watch is None:
        if data["business"]["kleinunternehmer"] is False:
            parts.append('<div class="empty"><p class="empty-lead">Regelbesteuerung.</p>'
                         '<p><code>business_profile.yaml</code> sagt '
                         '<code>tax.kleinunternehmer: false</code> — es gibt keine Umsatzgrenze zu '
                         'beobachten.</p></div>')
        else:
            parts.append('<div class="empty"><p class="empty-lead">Steuerstatus nicht belastbar.'
                         '</p><p>%s</p><p>Die Schwellenwache rechnet, sobald '
                         '<code>tax.kleinunternehmer</code> <code>true</code> trägt und ein Ledger '
                         'Buchungen hat.</p></div>' % e(data["tax"]["why"]))
        parts.append('</section>')
        return "".join(parts)

    def unknown_gauge(label, year, figure, foot):
        """A bar that cannot be drawn: dashed, empty, and it prints no percentage and no rest.

        TWO reasons reach it and both are "the comparison is not available", never a zero: no
        ledger file for that year, and -- in `previous_unknown` -- a year whose LIMIT is not
        settled, because 25.000 € and 100.000 € both depend on whether this is the founding year.
        Drawing 26 % of 100.000 € there was the number that won every skim while the verdict
        underneath said the opposite (measured 2026-09-02 in the `founding` fixture).
        """
        return ('<div class="gauge unknown"><div class="gauge-head">'
                '<span class="label">%s %s</span><span class="figure-s">%s</span></div>'
                '<div class="track"></div>'
                '<div class="gauge-foot"><span>—</span><span>%s</span></div></div>'
                % (e(label), year, figure, e(foot)))

    def gauge(value, limit, label, year, limit_unknown=False):
        """One bar, and none of these is the same display: a year with a ledger, a year over the
        limit, a year with NO ledger file at all, and a year whose LIMIT is not decided. Measured
        2026-09-02 in a founding-year project: the same bar first read "kein Ledger" beside "über
        der Grenze", and then "26 % · Rest 74.000,00 €" against a limit the verdict beside it
        called undecided."""
        if value is None:
            return unknown_gauge(label, year,
                                 'kein Ledger für %s <span class="muted">(Grenze %s)</span>'
                                 % (year, e(fmt_eur(limit))), "nicht belastbar")
        if limit_unknown:
            return unknown_gauge(
                label, year, '%s <span class="muted">von einer Grenze, die noch nicht '
                             'feststeht</span>' % e(fmt_eur(value)),
                "nicht belastbar — %s oder %s, je nach Gründungsjahr"
                % (fmt_eur(KLEINUNTERNEHMER_LIMIT_PREVIOUS_YEAR),
                   fmt_eur(KLEINUNTERNEHMER_LIMIT_CURRENT_YEAR)))
        percent = min(100, round(100 * value / limit))
        state = "alarm" if value > limit else ("warn" if percent >= 80 else "")
        figure = fmt_eur(value)
        rest = (e("Rest %s" % fmt_eur(limit - value)) if value <= limit
                else e("über der Grenze"))
        return ('<div class="gauge %s"><div class="gauge-head"><span class="label">%s %s</span>'
                '<span class="figure-s">%s <span class="muted">von %s</span></span></div>'
                '<div class="track"><span class="fill" style="width:%d%%"></span></div>'
                '<div class="gauge-foot"><span>%d %%</span><span>%s</span></div></div>'
                % (state, e(label), year, e(figure), e(fmt_eur(limit)), percent, percent, rest))

    parts.append('<h2>Kleinunternehmergrenze § 19 UStG</h2>')
    if watch["first_year"]:
        parts.append('<p class="lead">Im Gründungsjahr gilt eine einzige Bedingung: Gesamtumsatz '
                     'bis %s. Gezählt werden die bezahlten Einnahmen (Zufluss), brutto gleich '
                     'netto, Korrekturen abgezogen.</p>' % e(fmt_eur(watch["limit_current"])))
    else:
        parts.append('<p class="lead">Beide Bedingungen müssen gelten: Gesamtumsatz im Vorjahr bis '
                     '%s <strong>und</strong> im laufenden Jahr bis %s. Gezählt werden die '
                     'bezahlten Einnahmen (Zufluss), brutto gleich netto, Korrekturen abgezogen.'
                     '</p>'
                     % (e(fmt_eur(watch["limit_previous"])), e(fmt_eur(watch["limit_current"]))))
    if watch["first_year"]:
        # NO BAR FOR A YEAR THAT DOES NOT EXIST. A founding year has no previous year, so drawing
        # "kein Ledger für 2025" beside it would report a missing FILE where the answer is that
        # there is nothing to file -- the same confusion between "unknown" and "none" the four
        # verdicts exist to keep apart.
        parts.append('<p class="lead" data-first-year="%s">Gründungsjahr %s: es gibt kein Vorjahr, '
                     'also auch keine Vorjahresbedingung. Für das Gründungsjahr gilt nach § 19 '
                     'Abs. 1 UStG die Grenze von %s, und mit dem Umsatz, der sie überschreitet, '
                     'beginnt die Regelbesteuerung.</p>'
                     % (watch["current_year"], watch["current_year"],
                        e(fmt_eur(watch["limit_current"]))))
    else:
        parts.append(gauge(watch["previous"], watch["limit_previous"], "Vorjahr",
                           watch["previous_year"]))
    parts.append(gauge(watch["current"], watch["limit_current"], "Laufendes Jahr",
                       watch["current_year"],
                       limit_unknown=watch["verdict"] == "previous_unknown"))
    verdicts = {
        "within": ("ok", "innerhalb", "Innerhalb der Grenzen."),
        "previous_unknown": (
            "", "unklar",
            "Für %s gibt es keine Ledgerdatei, also ist die Vorjahresbedingung nicht "
            "entscheidbar — und sie fällt hier nicht still auf „innerhalb“. Ist %s Ihr "
            "Gründungsjahr, gilt nach § 19 Abs. 1 UStG in der seit 2025 geltenden Fassung für "
            "dieses Jahr die Grenze von %s, und mit dem Umsatz, der sie überschreitet, beginnt "
            "die Regelbesteuerung — darum steht der Balken „laufendes Jahr“ oben ohne Grenze. "
            "Ist %s kein Gründungsjahr, fehlt nur die Datei ledger/%s.csv. %s"
            % (watch["previous_year"], watch["current_year"],
               fmt_eur(watch["limit_previous"]), watch["current_year"],
               watch["previous_year"], _founding_year_note(watch))),
        "previous_exceeded": (
            "alarm", "überschritten",
            "Der Vorjahresumsatz liegt über %s: die Kleinunternehmerregelung gilt seit dem "
            "1. Januar %s nicht mehr. Mit der Steuerberatung klären, ab wann Umsatzsteuer "
            "auszuweisen ist." % (fmt_eur(watch["limit_previous"]), watch["current_year"])),
        "current_exceeded": (
            "alarm", "überschritten",
            "Der Umsatz des laufenden Jahres liegt über %s: ab dem Umsatz, der die Grenze "
            "überschritten hat, gilt die Regelbesteuerung."
            % fmt_eur(watch["limit_current"]))}
    css, stamp, sentence = verdicts[watch["verdict"]]
    parts.append('<p class="verdict" data-verdict="%s"><span class="stamp %s">%s</span> %s</p>'
                 % (watch["verdict"], css, stamp, e(sentence)))
    parts.append('<p class="hint">Grenzen nach § 19 Abs. 1 UStG in der seit 1. Januar 2025 '
                 'geltenden Fassung. Diese Seite ersetzt keine Steuerberatung.</p></section>')
    return "".join(parts)


VIEWS = (("ueberblick", "Überblick", view_ueberblick),
         ("rechnungen", "Rechnungen", view_rechnungen),
         ("offene-posten", "Offene Posten", view_offene_posten),
         ("euer", "EÜR", view_euer),
         ("kleinunternehmer", "Kleinunternehmer", view_kleinunternehmer))


def render_page(data, template):
    """Fill the template's slots. The TEMPLATE is the list of slots; this function is not.

    A `{{slot}}` the template carries and nothing below fills stays in the output, visible on the
    page -- caught by the kit workshop's
    `tools/test_finance_dashboard.py::test_every_template_slot_is_filled` rather than swallowed
    into an empty string.
    """
    watch = threshold(data)
    banner = ""
    if not data["valid"]:
        findings = [f for s in data["sources"] for f in s["findings"]]
        # The findings are the VALIDATOR'S OWN WORDS and it speaks English, on a German page. They
        # are introduced rather than translated: a translation here would be a second wording of a
        # sentence `scripts/ledger_add.py` owns, and the two would drift. The translation belongs
        # in that script; until then the lead-in says whose sentence this is.
        banner = ('<div class="banner alarm" role="alert"><strong>Ledger ungültig.</strong> Die '
                  'Summen auf dieser Seite sind nicht belastbar, bis die Zeile korrigiert ist. '
                  '<code>python scripts/ledger_add.py --validate ledger/&lt;Jahr&gt;.csv</code> '
                  'zeigt alles. Meldung des Prüfers:<ul>%s</ul></div>'
                  % "".join("<li>%s</li>" % e(f) for f in findings[:6]))
    if data["strays"]:
        # A separate notice and deliberately NOT the alarm banner: the sums come from the year
        # files and stay dependable, so calling the ledger invalid over a stray copy would be the
        # over-alarming half of the same defect.
        banner += ('<div class="banner note"><strong>Nicht gelesen.</strong> In '
                   '<code>ledger/</code> liegen Dateien, die kein Bericht öffnet — was auf dieser '
                   'Seite steht, enthält sie nicht. Meldung des Prüfers:<ul>%s</ul></div>'
                   % "".join("<li><code>%s</code> — %s</li>" % (e(s["file"]), e(s["findings"][0]))
                             for s in data["strays"]))
    show_threshold = data["business"]["kleinunternehmer"] is not False
    tabs, bodies = [], []
    for view_id, label, render in VIEWS:
        if view_id == "kleinunternehmer" and not show_threshold:
            continue
        if view_id == "kleinunternehmer" and watch and watch["exceeded"]:
            label += ' <span class="dot"></span>'
        tabs.append((view_id, label))
        bodies.append(render(data))
    nav = "".join('<button role="tab" data-view="%s" aria-selected="%s">%s</button>'
                  % (view_id, "true" if index == 0 else "false", label)
                  for index, (view_id, label) in enumerate(tabs))
    if data["years"]:
        booked = sum(s["rows"] for s in data["sources"])
        stand = ("Datenstand %s · %s · %d %s"
                 % (fmt_date(data["datenstand"]), ", ".join(s["file"] for s in data["sources"]),
                    booked, plural(booked, "Buchung", "Buchungen")))
    else:
        stand = "Kein Ledger unter ledger/"
    slots = {"title": e(data["business"]["name"] or "Dieses Unternehmen"),
             "legal_form": e(data["business"]["legal_form"]),
             "stand": e(stand),
             "banner": banner,
             "nav": nav,
             "views": "".join(bodies),
             "payment_term_days": str(data["payment_term"][0]),
             "page_rows": str(PAGE_ROWS)}
    page = template
    for name, value in slots.items():
        page = page.replace("{{%s}}" % name, value)
    return page


def write_atomically(path, text):
    """Sibling temp file + `os.replace`, the way `ledger_add.save_atomically` writes the ledger.

    An interrupted run must not leave half a dashboard behind: the page is what somebody reads to
    decide whether to chase an invoice.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp-%d" % os.getpid()
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--root", default=None,
                        help="project root (default: the directory this tools/ folder sits in)")
    args = parser.parse_args(argv)
    root = project_root(args.root)
    euer_report, ledger_add = _import_kit_scripts(root)

    template_path = os.path.join(TOOLS_DIR, TEMPLATE_NAME)
    if not os.path.isfile(template_path):
        sys.stderr.write("[finance_dashboard] the template %s is missing\n" % template_path)
        return 1
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()

    data = load_project(root, euer_report, ledger_add)
    page = render_page(data, template)
    output = os.path.join(root, OUTPUT_REL)
    try:
        write_atomically(output, page)
    except OSError as problem:
        sys.stderr.write("[finance_dashboard] could not write %s: %s\n" % (output, problem))
        return 1
    print("[finance_dashboard] %s · %d Buchungen aus %d Ledgerdatei(en) · Ledger %s"
          % (OUTPUT_REL.replace(os.sep, "/"), len(data["rows"]), len(data["sources"]),
             "gültig" if data["valid"] else "UNGÜLTIG (Befunde stehen auf der Seite)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

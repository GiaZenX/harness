#!/usr/bin/env python3
"""
euer_report.py — deterministic quarterly income/expense statement FROM the ledger.

The report is GENERATED, never written by an LLM: numbers that pass through a model are a second
hallucination opportunity, and sums could drift from the data. Zufluss/Abfluss principle
(§ 11 EStG): paid totals count by PAYMENT date within the quarter; document-dated-but-unpaid
items are listed separately as OPEN, never mixed in. Prose (anomalies, context) belongs in the
bookkeeper's reports/<name>_notes.md.

Usage: python scripts/euer_report.py --year 2026 --quarter 2
Exit 0 = report written to reports/euer_<year>_Q<q>.md. Exit 1 = refused (reason on stderr).
"""
import argparse
import csv
import datetime
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DISCLAIMER = (
    "> **Hinweis:** Vorbereitende Aufstellung aus dem Belegjournal — keine Steuerberatung, keine\n"
    "> Steuererklärung, keine revisionssichere Archivierung. Zahlungsprinzip (Zufluss/Abfluss);\n"
    "> offene Posten sind separat ausgewiesen. Prüfung und Abgabe: Steuerberater/in.\n")


# THE SIGN CONVENTION, in one place because it is the single arithmetic fact this whole report
# rests on. Three doc types REDUCE the total of their own direction:
#
#   reversal     — cancels an earlier entry outright
#   credit_note  — a Gutschrift: reduces what was invoiced
#   refund       — money given back on an earlier booking
#
# `credit_note` and `refund` used to be signed +1, i.e. added. An income invoice of 1190,00 plus
# the credit note that cancels it therefore reported 2380,00 EUR income and 380,00 EUR VAT — in a
# document prepared for a tax office. Nothing flagged it: both rows are individually valid, the
# validator accepted them, and the report has no reason to suspect its input. `direction` says
# WHOSE side the money is on; `doc_type` says whether it adds or removes. Keep this list and
# `ledger_add.py`'s `NEGATIVE_DOC_TYPES` identical — a test pins that they are.
NEGATIVE_DOC_TYPES = ("reversal", "credit_note", "refund")


def sign_of(entry):
    return -1 if entry.get("doc_type") in NEGATIVE_DOC_TYPES else 1


# WHERE THE FORM'S LINE NUMBERS COME FROM, and there is no second answer in this file: the project's
# own `project_memory/master_data.yaml`. It carries the form YEAR, the line NUMBER per category and
# the GWG threshold, so a renumbered Anlage EÜR is one edit in a project file and never a kit update
# (FR-0076). This script therefore contains no line number, no form year and no threshold of its own.
VOCABULARY_REL = os.path.join("project_memory", "master_data.yaml")
# A category maps to a form line exactly when its `euer_line` is a WHOLE NUMBER. A caption, a range,
# a note or nothing all mean the same thing -- this category names no line -- and their sums are
# reported under `UNMAPPED` rather than attached to a line nobody chose.
UNMAPPED = "ohne Zeile"
# THE SENTENCE THE AfA HINT SAYS, written once because both readers say it: this report and the
# dashboard's EÜR tab (`tools/finance_dashboard.py` imports it from here, the way it imports the
# sign convention). It hands the question on and answers nothing -- that is the whole of FR-0076's
# third half.
ASSET_HINT = "Anlagegut — mit der Steuerberatung klären"


def form_year_suffix(vocabulary):
    """` 2025`, or a sentence saying the vocabulary names no form year -- never a guessed year."""
    return (" %s" % vocabulary["year"] if vocabulary["year"] not in (None, "")
            else " (Formularjahr steht nicht im Vokabular)")


def line_number(value):
    """The form line this value names, or None. `True` is not a line: YAML reads `yes` as a bool."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def read_vocabulary(root):
    """{"lines": {category key: (line, caption)}, "year", "gwg_limit_net", "problems": [sentence]}.

    NEVER RAISES AND NEVER REFUSES THE REPORT. The per-category sums, the VAT figures and the open
    items do not depend on this file, so a missing PyYAML, a missing or unreadable `master_data.yaml`
    costs the per-line summary and the AfA hint and nothing else -- and it costs them VISIBLY: the
    reason travels in `problems` and is printed where the summary would have stood. A report that
    silently dropped a section the Steuerberater was told to expect is the failure this avoids.
    """
    found = {"lines": {}, "year": None, "source": "", "gwg_limit_net": None, "no_hint": set(),
             "problems": []}
    path = os.path.join(root, VOCABULARY_REL)
    if not os.path.isfile(path):
        found["problems"].append("%s fehlt — ohne das Vokabular kennt dieser Bericht keine "
                                 "Zeilennummern." % VOCABULARY_REL.replace(os.sep, "/"))
        return found
    try:
        import yaml
    except ImportError as problem:
        found["problems"].append("PyYAML fehlt (%s), also konnte %s nicht gelesen werden: pip "
                                 "install -r requirements-office.txt"
                                 % (problem, VOCABULARY_REL.replace(os.sep, "/")))
        return found
    try:
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}
    except Exception as problem:            # noqa: BLE001 — any parse failure is one sentence
        found["problems"].append("%s ist nicht lesbar (%s)."
                                 % (VOCABULARY_REL.replace(os.sep, "/"), problem))
        return found
    if not isinstance(document, dict):
        found["problems"].append("%s enthält keine Zuordnung."
                                 % VOCABULARY_REL.replace(os.sep, "/"))
        return found
    form = document.get("euer_form") or {}
    if isinstance(form, dict):
        found["year"] = form.get("year")
        found["source"] = str(form.get("source") or "")
        found["gwg_limit_net"] = form.get("gwg_limit_net")
    categories = document.get("categories") or {}
    if not isinstance(categories, dict):
        categories = {}
    unmapped = []
    for direction in ("income", "expense"):
        for entry in categories.get(direction) or []:
            if not isinstance(entry, dict) or not entry.get("key"):
                continue
            # THE USER'S LEVER ON THE AfA HINT, spelled the way `second_reading` is spelled in the
            # same file: only the boolean `false` switches it off, so a typo cannot quietly silence
            # a category. What it is FOR: in a trading business every wholesale invoice is above the
            # GWG threshold and none of them is an asset, so a hint that fires on all of them is a
            # hint nobody reads. Which categories those are is the owner's answer about their own
            # business and never a list in this script.
            if entry.get("afa_hint") is False:
                found["no_hint"].add(str(entry["key"]))
            line = line_number(entry.get("euer_line"))
            if line is None:
                unmapped.append(str(entry.get("key")))
                continue
            found["lines"][str(entry["key"])] = (
                line, str(entry.get("euer_line_label") or "").strip())
    if unmapped:
        found["problems"].append(
            "Ohne Zeilennummer im Vokabular: %s — ihre Beträge stehen unter %r."
            % (", ".join(sorted(unmapped)), UNMAPPED))
    return found


# THE CHART OF ACCOUNTS (FR-0081), the second project document this report reads and the one
# that maps a category to an ACCOUNT of the framework the business books against. Shipped
# inactive (`active: null`); with a framework named, the account's line is the one the per-line
# table uses for its categories, and a category whose two lines disagree is PRINTED, not averaged.
CHART_REL = os.path.join("project_memory", "chart_of_accounts.yaml")
NO_ACCOUNT = "ohne Konto"


def read_chart(root):
    """{"active", "form_year", "by_category": {key: (account, label, line)}, "problems": [..]}.

    `read_vocabulary`'s contract, for the same reason: NEVER RAISES, an unreadable chart costs the
    account table and says so where the table would stand. The shipped state -- `active: null` --
    is an empty answer and no problem: which chart a business uses is the Steuerberatung's.
    """
    found = {"active": None, "form_year": None, "by_category": {}, "problems": []}
    path = os.path.join(root, CHART_REL)
    if not os.path.isfile(path):
        return found
    try:
        import yaml
    except ImportError as problem:
        found["problems"].append("PyYAML fehlt (%s), also konnte %s nicht gelesen werden."
                                 % (problem, CHART_REL.replace(os.sep, "/")))
        return found
    try:
        with open(path, encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}
    except Exception as problem:            # noqa: BLE001 — any parse failure is one sentence
        found["problems"].append("%s ist nicht lesbar (%s)." % (CHART_REL.replace(os.sep, "/"),
                                                               problem))
        return found
    if not isinstance(document, dict) or not document.get("active"):
        return found
    found["active"] = str(document.get("active"))
    found["form_year"] = document.get("form_year")
    entries = (document.get("accounts") or {}).get(document.get("active"))
    if not isinstance(entries, list):
        found["problems"].append("%s nennt `active: %s`, führt aber keine Kontenliste `accounts.%s`."
                                 % (CHART_REL.replace(os.sep, "/"), found["active"],
                                    found["active"]))
        return found
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        account = str(entry.get("account") or "").strip()
        label = str(entry.get("label_de") or "").strip()
        line = line_number(entry.get("euer_line"))
        for key in entry.get("categories") or []:
            key = str(key)
            if key in found["by_category"]:
                found["problems"].append(
                    "Kategorie %s ist zwei Konten zugeordnet (%s und %s) — die Buchung verweigert "
                    "das, der Bericht zeigt das erste." % (key, found["by_category"][key][0],
                                                            account))
                continue
            found["by_category"][key] = (account, label, line)
    return found


def apply_chart(vocabulary, chart):
    """The chart's line WINS for every category it maps, and every disagreement is printed.

    Two documents state one fact -- which form line a category belongs to -- and this is the one
    place they meet. Silently taking either would hide a correction made in the other; taking the
    chart's is the documented rule (its own header says so) and the vocabulary's figure travels
    beside it as a problem line, in the section the Steuerberatung reads.
    """
    if not chart["active"]:
        return
    if (chart["form_year"] not in (None, "") and vocabulary["year"] not in (None, "")
            and str(chart["form_year"]) != str(vocabulary["year"])):
        vocabulary["problems"].append(
            "Formularjahr %s im Kontenrahmen, %s im Vokabular — eine der beiden Dateien ist "
            "veraltet; die Zeilennummern unten stammen aus dem Kontenrahmen."
            % (chart["form_year"], vocabulary["year"]))
    for key, (account, label, line) in sorted(chart["by_category"].items()):
        if line is None:
            continue
        old = vocabulary["lines"].get(key)
        if old is not None and old[0] != line:
            vocabulary["problems"].append(
                "Zeile für %s: %d laut Kontenrahmen %s (Konto %s), %d laut Vokabular — der "
                "Kontenrahmen zählt hier; bitte klären." % (key, line, chart["active"], account,
                                                            old[0]))
        vocabulary["lines"][key] = (line, old[1] if old else label)


def by_account(entries, chart):
    """[(account, label, line, income, expense)] — the paid entries grouped by account, NO_ACCOUNT last.

    Same money as `by_form_line` and the per-category table (one sign convention, one entry list);
    what differs is the grouping key, which is what the Steuerberatung's own software groups by.
    """
    grouped = defaultdict(lambda: [0.0, 0.0])
    meta = {}
    for entry in entries:
        account, label, line = chart["by_category"].get(entry.get("category") or "",
                                                        (NO_ACCOUNT, "", None))
        meta.setdefault(account, (label, line))
        index = 0 if entry.get("direction") == "income" else 1
        grouped[account][index] = round(
            grouped[account][index] + float(entry["gross"]) * sign_of(entry), 2)
    rows = []
    for account in sorted(grouped, key=lambda a: (1, "") if a == NO_ACCOUNT else (0, a)):
        label, line = meta[account]
        rows.append((account, label, line, grouped[account][0], grouped[account][1]))
    return rows


def by_form_line(entries, vocabulary):
    """[(sort key, heading, income, expense)] — the paid entries grouped by Anlage-EÜR line.

    THE SUMS ARE THE LEDGER'S, UNREDUCED. No cap, quota or share the form applies to a particular
    line is applied here (a partly deductible line is summed whole), because that arithmetic is the
    Steuerberatung's answer and this report performs none of it. The line printed beside every sum
    is what makes that checkable in the form itself.
    """
    grouped = defaultdict(lambda: [0.0, 0.0])
    captions = {}
    for entry in entries:
        line, caption = vocabulary["lines"].get(entry.get("category") or "", (None, ""))
        key = UNMAPPED if line is None else line
        if caption and key not in captions:
            captions[key] = caption
        index = 0 if entry.get("direction") == "income" else 1
        grouped[key][index] = round(
            grouped[key][index] + float(entry["gross"]) * sign_of(entry), 2)
    rows = []
    for key in sorted(grouped, key=lambda k: (1, 0) if k == UNMAPPED else (0, k)):
        heading = (UNMAPPED if key == UNMAPPED
                   else "Zeile %d%s" % (key, " — " + captions[key] if captions.get(key) else ""))
        rows.append((key, heading, grouped[key][0], grouped[key][1]))
    return rows


def document_key(entry):
    """What makes two ledger rows ONE document -- counterparty + invoice number, else the row.

    WHY THIS EXISTS AT ALL (DEC-0108): a document carrying two VAT rates books as one row PER RATE
    under a shared invoice number, so a count of ROWS stopped being a count of documents the day
    that shape was sanctioned. Everything in this report that COUNTS or LISTS Belege goes through
    here -- the reverse-charge count, the AfA hints, the open items and the stdout line, all of them
    via `group_by_document` or a set of these keys; everything that sums money keeps summing rows,
    because the money IS per row. The claim is measured by
    `tools/test_office_package.py::test_a_mixed_vat_document_is_one_beleg_everywhere_the_report_counts_them`.

    A ROW WITHOUT AN INVOICE NUMBER IS ITS OWN DOCUMENT, and that is the same reading
    `ledger_add.validate_cross` gives such a row: a receipt or a bank charge often carries none,
    and treating all of them as one document would collapse a quarter of small vouchers into a
    single Beleg. The row id is unique per ledger file, so it is what stands in for the number.
    """
    invoice = str(entry.get("invoice_no") or "").strip()
    if not invoice:
        return ("", "", str(entry.get("id") or ""))
    return (str(entry.get("counterparty") or ""), invoice, "")


def group_by_document(entries):
    """`entries` as a list of ROW GROUPS, one per document, in first-seen order.

    The one place the report turns rows into Belege -- `document_key` says what makes two rows one
    document, and everything that COUNTS or LISTS Belege goes through here while everything that
    sums money keeps summing rows.
    """
    groups, order = {}, []
    for entry in entries:
        key = document_key(entry)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(entry)
    return [groups[key] for key in order]


def _sum_gross(rows):
    """The gross of a whole document, formatted as the ledger writes one row's."""
    total = 0.0
    for row in rows:
        try:
            total += float(row.get("gross"))
        except (TypeError, ValueError):
            return str(rows[0].get("gross"))   # unreadable: say what the first row says, unchanged
    return "%.2f" % total


def asset_hints(entries, limit, silenced=()):
    """The paid bookings this report FLAGS as possible Anlagegüter — a hint, never a calculation.

    THE PROPERTY, and it is the whole rule (FR-0076): an ACQUISITION whose NET exceeds the GWG
    threshold. An acquisition is an expense booking that is not a correction — a credit note or a
    refund gives money back and buys nothing, so the sign convention decides this too rather than a
    second reading of `doc_type`. Nothing here depreciates, writes an asset register or looks at the
    legal form; the flag says one sentence and hands the question to the Steuerberatung.

    IT IS COARSE BY CONSTRUCTION and both readers say so where they print it: a ledger row is a
    DOCUMENT total, not a line item, so one invoice over a hundred small parts looks exactly like
    one machine. `silenced` is the user's answer to that for whole categories
    (`afa_hint: false` in the vocabulary); everything else is left to the person reading the hint.
    """
    if limit is None:
        return []
    try:
        threshold = float(limit)
    except (TypeError, ValueError):
        return []
    # PER DOCUMENT, not per row (DEC-0108). The threshold is a fact about an acquisition, and a
    # mixed-VAT purchase is several rows of one acquisition since a document books one row per
    # rate -- comparing each row on its own would let a 1200 EUR machine invoiced at two rates fall
    # under a 800 EUR limit twice and be flagged never. The sentence printed beside this table
    # ("Gemessen wird der BELEG, nicht die einzelne Position") is the claim this keeps true.
    acquisitions = []
    for entry in entries:
        if entry.get("direction") != "expense" or sign_of(entry) < 0:
            continue
        if (entry.get("category") or "") in silenced:
            continue
        try:
            float(entry["net"])
        except (TypeError, ValueError, KeyError):
            continue
        acquisitions.append(entry)
    flagged = []
    for rows in group_by_document(acquisitions):
        net = sum(float(row["net"]) for row in rows)
        if net > threshold:
            flagged.append((rows[0], net))
    return flagged


def quarter_range(year, quarter):
    start = datetime.date(year, 3 * (quarter - 1) + 1, 1)
    end_month = 3 * quarter
    if end_month == 12:
        end = datetime.date(year, 12, 31)
    else:
        end = datetime.date(year, end_month + 1, 1) - datetime.timedelta(days=1)
    return start.isoformat(), end.isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--quarter", type=int, required=True, choices=(1, 2, 3, 4))
    args = ap.parse_args()

    path = os.path.join(ROOT, "ledger", "%d.csv" % args.year)
    if not os.path.isfile(path):
        sys.stderr.write("[euer_report] no ledger for %d (%s)\n" % (args.year, path))
        sys.exit(1)
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    q_start, q_end = quarter_range(args.year, args.quarter)
    paid, open_items = [], []
    reversed_ids = {r["reverses"] for r in rows if r.get("doc_type") == "reversal" and r.get("reverses")}
    for r in rows:
        pd = r.get("payment_date") or ""
        if pd and q_start <= pd <= q_end:
            # PAID aggregation keeps BOTH the original and the reversal row (sign -1 below): the
            # original stays historically correct in ITS quarter (Zufluss/Abfluss), the reversal
            # subtracts in the quarter it was booked — the year nets to zero. Skipping the original
            # AND subtracting the reversal double-cancelled (a booked+reversed 119 showed as -119).
            paid.append(r)
        elif not pd and (r.get("doc_date") or "") <= q_end:
            # OPEN items: a reversed original is no longer owed, and reversal rows are corrections,
            # not receivables/payables — both stay out of the open list.
            # a credit note / refund is a correction, not a receivable — same reasoning as a
            # reversal, and it belongs in the same list for the same reason
            if r.get("doc_type") not in NEGATIVE_DOC_TYPES and r.get("id") not in reversed_ids:
                open_items.append(r)

    def total(entries, direction):
        return round(sum(float(e["gross"]) * sign_of(e)
                         for e in entries if e.get("direction") == direction), 2)

    income, expense = total(paid, "income"), total(paid, "expense")
    by_cat = defaultdict(lambda: [0.0, 0.0])
    vat_in, vat_out, reverse_charge = 0.0, 0.0, []
    for e in paid:
        sign = sign_of(e)
        gross, net = float(e["gross"]) * sign, float(e["net"]) * sign
        idx = 0 if e.get("direction") == "income" else 1
        by_cat[e.get("category") or "?"][idx] = round(by_cat[e.get("category") or "?"][idx] + gross, 2)
        vat_amount = round(gross - net, 2)
        if e.get("vat_treatment") == "standard":
            if e.get("direction") == "income":
                vat_out = round(vat_out + vat_amount, 2)
            else:
                vat_in = round(vat_in + vat_amount, 2)
        elif e.get("vat_treatment") == "reverse_charge":
            reverse_charge.append(e)

    lines = ["# Einnahmen/Ausgaben-Gegenüberstellung %d Q%d" % (args.year, args.quarter), "",
             DISCLAIMER,
             "Zeitraum (Zahlungsdatum): %s bis %s · Quelle: ledger/%d.csv · generiert: %s"
             % (q_start, q_end, args.year, datetime.date.today().isoformat()), "",
             "## Summen (bezahlt im Quartal)", "",
             "| | Betrag (brutto) |", "|---|---|",
             "| Einnahmen | %.2f EUR |" % income,
             "| Ausgaben | %.2f EUR |" % expense,
             "| **Überschuss** | **%.2f EUR** |" % round(income - expense, 2), "",
             "## Nach Kategorie", "", "| Kategorie | Einnahmen | Ausgaben |", "|---|---|---|"]
    for cat in sorted(by_cat):
        lines.append("| %s | %.2f | %.2f |" % (cat, by_cat[cat][0], by_cat[cat][1]))

    # THE SECOND GROUPING, and it is the one the form asks for (FR-0076). The per-category table
    # above is what the owner steers by; this one is what the Steuerberater maps 1:1, because the
    # Anlage EÜR is coarser than a business's own bookkeeping and several categories land on one
    # line. Both come from the SAME paid entries and the same sign convention, so the two tables
    # sum to the same money -- `tools/test_finance_dashboard.py::
    # test_the_per_line_sums_and_the_per_category_sums_are_the_same_money` measures that.
    vocabulary = read_vocabulary(ROOT)
    chart = read_chart(ROOT)
    apply_chart(vocabulary, chart)
    lines += ["", "## Nach Zeile der Anlage EÜR%s" % form_year_suffix(vocabulary), ""]
    if vocabulary["source"]:
        lines += ["Herkunft der Zeilennummern: %s. Die Zuordnung steht in "
                  "`project_memory/master_data.yaml` und wird dort korrigiert, nicht im Skript."
                  % vocabulary["source"], ""]
    for problem in vocabulary["problems"]:
        lines += ["> %s" % problem, ""]
    by_line = by_form_line(paid, vocabulary)
    if by_line:
        lines += ["| Zeile | Einnahmen | Ausgaben |", "|---|---|---|"]
        for _key, heading, income_sum, expense_sum in by_line:
            lines.append("| %s | %.2f | %.2f |" % (heading, income_sum, expense_sum))
        lines += ["", "Die Beträge sind die des Belegjournals, ungekürzt: keine Quote und keine "
                      "Obergrenze, die das Formular auf eine einzelne Zeile anwendet, ist hier "
                      "eingerechnet.", ""]
    else:
        lines += ["keine bezahlte Buchung in diesem Quartal", ""]

    # THE THIRD GROUPING, only while the business books against a chart (FR-0081): the same paid
    # entries under the ACCOUNT their category maps to, which is the key the Steuerberatung's
    # software carries. `tools/test_office_package.py::test_the_euer_rollup_reads_the_chart_and_prints_a_disagreement`
    # holds this table, the per-line override above and the printed disagreement together.
    if chart["active"] or chart["problems"]:
        lines += ["", "## Nach Konto (%s, Formularjahr %s)"
                  % (chart["active"] or "kein Kontenrahmen aktiv", chart["form_year"] or "?"), ""]
        for problem in chart["problems"]:
            lines += ["> %s" % problem, ""]
        by_acc = by_account(paid, chart) if chart["active"] else []
        if by_acc:
            lines += ["| Konto | Bezeichnung | Zeile | Einnahmen | Ausgaben |", "|---|---|---|---|---|"]
            for account, label, line, income_sum, expense_sum in by_acc:
                lines.append("| %s | %s | %s | %.2f | %.2f |"
                             % (account, label, line if line is not None else "—",
                                income_sum, expense_sum))
            lines += ["", "Konten und Zeilen aus `project_memory/chart_of_accounts.yaml`; "
                          "korrigiert wird dort, nicht im Skript. Eine Kategorie ohne Konto steht "
                          "unter %r." % NO_ACCOUNT, ""]
        elif chart["active"]:
            lines += ["keine bezahlte Buchung in diesem Quartal", ""]

    # AfA AS A HINT AND NOTHING MORE (FR-0076, the user's own boundary: "ich will kein Gerüst für
    # ein Haus bauen das noch nicht existiert"). No asset register, no depreciation arithmetic, no
    # branch on the legal form -- one flagged row and the sentence that hands it on.
    hints = asset_hints(paid, vocabulary["gwg_limit_net"], vocabulary["no_hint"])
    lines += ["## Mögliche Anlagegüter (Hinweis, keine Abschreibung)", ""]
    if vocabulary["gwg_limit_net"] is None:
        lines += ["Keine GWG-Grenze im Vokabular (`euer_form.gwg_limit_net`), also prüft dieser "
                  "Bericht darauf nicht.", ""]
    elif not hints:
        lines += ["Keine bezahlte Ausgabe über %s EUR netto in diesem Quartal."
                  % vocabulary["gwg_limit_net"], ""]
    else:
        lines += ["| Beleg | Gegenpartei | Netto | Hinweis |", "|---|---|---|---|"]
        for entry, net in sorted(hints, key=lambda pair: -pair[1]):
            lines.append("| %s %s | %s | %.2f EUR | %s |"
                         % (entry.get("id"), entry.get("invoice_no") or "",
                            entry.get("counterparty"), net, ASSET_HINT))
        lines += ["", "Grenze: %s EUR netto (§ 6 Abs. 2 EStG, aus "
                      "`project_memory/master_data.yaml`). Gemessen wird der BELEG, nicht die "
                      "einzelne Position — eine Rechnung über viele kleine Teile steht hier "
                      "genauso wie eine Maschine. Dieser Bericht schreibt kein "
                      "Anlagenverzeichnis und rechnet keine Abschreibung."
                  % vocabulary["gwg_limit_net"], ""]

    lines += ["## Umsatzsteuer (nur informativ)", "",
              "Vereinnahmte USt (Einnahmen, standard): %.2f EUR · Vorsteuer (Ausgaben, standard): "
              "%.2f EUR · Reverse-Charge-Belege (§ 13b, netto=brutto): %d"
              % (vat_out, vat_in, len({document_key(e) for e in reverse_charge}))]
    lines += ["", "## Offene Posten (Belegdatum bis Quartalsende, unbezahlt)", ""]
    # ONE LINE PER BELEG, not per row (DEC-0108). A mixed-VAT document books one row per rate under
    # a shared invoice number, so an unpaid one stood here TWICE and was counted as two open items
    # (verifier round 1, F5, measured with one such document). The gross is summed over the rows of
    # the document, which is what the owner has to pay or chase.
    documents = group_by_document(open_items)
    if documents:
        lines += ["| Beleg | Gegenpartei | Belegdatum | Brutto |", "|---|---|---|---|"]
        for rows in sorted(documents, key=lambda group: group[0].get("doc_date") or ""):
            first = rows[0]
            lines.append("| %s %s | %s | %s | %s EUR |"
                         % (" ".join(str(r.get("id")) for r in rows),
                            first.get("invoice_no") or "", first.get("counterparty"),
                            first.get("doc_date"), _sum_gross(rows)))
    else:
        lines.append("keine")
    lines += ["", "_Anmerkungen der Buchhaltung: siehe reports/euer_%d_Q%d_notes.md_"
              % (args.year, args.quarter), ""]

    out_dir = os.path.join(ROOT, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "euer_%d_Q%d.md" % (args.year, args.quarter))
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print("[euer_report] %s written (%d paid entries, %d open items)"
          % (out, len(paid), len(documents)))


if __name__ == "__main__":
    main()

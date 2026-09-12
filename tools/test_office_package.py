"""The office package of generation 5 (TSK-0132, PR-0009), measured on the shipped tree.

Everything here runs the SHIPPED scripts and the SHIPPED entry point (`scripts/harness.py`) as
processes against a project built under `tmp_path` -- outside this repo -- and, where a filing or
a booking is judged, the office kit's REGISTERED hook chain (`test_hooks._office_chain` reads
`settings/settings.json`; nothing here assembles a chain of its own). The helpers are imported from
`test_hooks` rather than copied, so a pilot in this file and a pilot there walk one route.

What each block measures, by the acceptance criterion of PR-0009 it answers to:
  * AC-6 / BUG-0079 -- every remedy the kernel prints for a document write is EXECUTED and accepted;
  * AC-5 / BUG-0071 -- the category vocabulary grows through the kernel, on the shipped document
    and on an old-stock one, and the ledger books against the new category;
  * AC-5 / BUG-0070 -- `add-filing-rule` creates the rules list on an old-stock plan, through the
    entry point;
  * AC-3 / FR-0081 -- the chart of accounts is a kit document with a kernel writer, the booking
    names an account, the EUeR rollup reads the mapping;
  * AC-2 / DEC-0075 -- the docking point: intake of an app-produced invoice, norm rules, the
    reconciling triple, number-range continuity, filing through the registered chain, booking;
  * AC-1 / FR-0033 -- the three correspondence drafts from ledger + master data, and the countable
    half of the humanizer bar on them.
"""
import csv
import datetime
import json
import os
import re
import shlex
import subprocess
import sys

import pytest

import conftest
import test_hooks as hooks
from conftest import mint_via_hook

pytest.importorskip("yaml")

ROOT = conftest.ROOT
TEAM_KITS = conftest.TEAM_KITS
OFFICE = os.path.join(TEAM_KITS, "office-team")
OFFICE_SCRIPTS = hooks.OFFICE_SCRIPTS
TEMPLATE_STATE = os.path.join(OFFICE, "templates", "project_memory")
TASK = "TSK-0001"


# The child writes UTF-8 whatever the console's code page is: what is measured is the script's
# text, and a Windows pipe defaulting to cp1252 would turn `Bürobedarf` into a replacement mark.
UTF8 = dict(os.environ, PYTHONUTF8="1")


def harness(repo, *args):
    """The shipped entry point, from the project root, in its ONE spelling (constitution section 0)."""
    return subprocess.run([sys.executable, "scripts/harness.py", *args], cwd=str(repo),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=UTF8, timeout=180)


def script(repo, name, *args):
    return subprocess.run([sys.executable, "-B", str(repo / "scripts" / name), *args],
                          cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=UTF8, timeout=180)


def read(path):
    with open(str(path), encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def state_of(repo):
    sys.path.insert(0, TEAM_KITS)
    from kernel.state import ProjectState
    return ProjectState(str(repo / "project_memory"))


def mint_the_open_request(repo):
    """Answer the question the LAST `request-approval` printed -- the one step no software performs."""
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals
    state = state_of(repo)
    pending = approvals.open_requests(state)
    assert pending, "no open approval request to answer"
    mint_via_hook(state, pending[-1])


# ---------------- AC-6 / BUG-0079: a remedy is a line the kernel accepts ----------------------
REMEDY_RX = re.compile(r"`(python scripts/harness\.py request-approval [^`]+)`")
NEW_CATEGORY = ('  - key: tax_advisory\n'
                '    label_de: "Steuerberatungs- und Buchführungskosten"\n'
                '    euer_line: 60\n'
                '    euer_line_label: "Sonstige unbeschränkt abziehbare Betriebsausgaben"\n')


def printed_remedy(result):
    """The command line the refusal told the role to run, split the way a shell splits it."""
    found = REMEDY_RX.findall(result.stderr + result.stdout)
    assert found, "no `request-approval` remedy in:\n%s%s" % (result.stdout, result.stderr)
    return shlex.split(found[0], posix=True)[2:]


def stage_a_category(repo, base=None):
    """`staging/TSK-0001/master_data.yaml`: the document as it stands plus ONE expense category.

    Inserted before the counterparty block, so every line the document already carries stays where
    it is -- which is what `apply-proposal` demands of a proposal.
    """
    document = repo / "project_memory" / "master_data.yaml"
    if base is not None:
        write(document, base)
    text = read(document)
    marker = "\n# Counterparty normalisation"
    if "  expense: []\n" in text:
        proposal = text.replace("  expense: []\n", "  expense:\n" + NEW_CATEGORY, 1)
    else:
        proposal = text.replace(marker, NEW_CATEGORY.rstrip("\n") + "\n" + marker, 1)
    assert proposal != text
    write(repo / "project_memory" / "staging" / TASK / "master_data.yaml", proposal)
    return ["--kit-document", "master_data.yaml",
            "--proposal", "staging/%s/master_data.yaml" % TASK,
            "--reason", "Die Steuerberaterrechnung braucht eine eigene Kategorie"]


def stage_a_revision(repo):
    """The same document with ONE label rewritten -- the route that may replace."""
    document = repo / "project_memory" / "master_data.yaml"
    text = read(document)
    assert 'label_de: "Porto"' in text
    write(repo / "project_memory" / "staging" / TASK / "master_data.yaml",
          text.replace('label_de: "Porto"', 'label_de: "Porto und Versand"', 1))
    return ["--kit-document", "master_data.yaml",
            "--proposal", "staging/%s/master_data.yaml" % TASK,
            "--reason", "Porto heißt bei uns Porto und Versand"]


def a_filing_rule(_repo):
    return ["--rule-id", "FP-001", "--path-template", "archive/finance/incoming/<year>/",
            "--document-types", "supplier_invoice",
            "--filename-template", "YYYY-MM-DD_<counterparty>_<doctype>",
            "--retention", "8y (§ 147 AO; mit der Steuerberatung bestätigt)",
            "--reason", "Lieferantenrechnungen hatten keine Regel"]


@pytest.mark.parametrize("command, prepare", [
    ("apply-proposal", stage_a_category),
    ("revise-document", stage_a_revision),
    ("add-filing-rule", a_filing_rule),
])
def test_every_remedy_the_kernel_prints_for_a_document_write_is_a_line_the_kernel_accepts(
        tmp_path, command, prepare):
    """BUG-0079, closed in the direction the bug asked for: the printed line is RUN, not read.

    The defect: `documents.apply` printed `request-approval document_proposal --kit-document …
    --proposal …` and the kernel refused exactly that line with "reason is missing"; the filing
    remedy printed the kind and no flag at all. So each of the three write commands is run
    without an approval, the remedy is cut out of ITS refusal and executed through the shipped
    entry point, and then the TOOTH: the approval that remedy minted is the one the command
    needed -- the same command line succeeds afterwards. A remedy asking a question whose answer
    does not cover the write would pass the first half and fail here.

    Red without the fix: with `--reason` dropped from either document remedy, or the flags dropped
    from the filing one, the executed line exits 2 with the kernel's "must say what it releases".
    """
    repo = hooks._draft_project(tmp_path)
    argv = prepare(repo)
    refused = harness(repo, command, *argv)
    assert refused.returncode != 0 and "Remedy" in refused.stderr, refused.stdout + refused.stderr

    asked = harness(repo, *printed_remedy(refused))
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert "[APR-REQ:" in asked.stdout, asked.stdout

    mint_the_open_request(repo)
    done = harness(repo, command, *argv)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_two_remedies_that_name_no_typed_flag_need_none():
    """The bounded scope of BUG-0079 AC-2, read off the part that runs rather than grepped.

    `presets.py` prints `--preset`, `kitupdate.py` prints the kind alone. Both are complete IF
    every other subject key of their builder is one the CLI derives itself -- and that is a fact
    about `cli.LINE_MANIFEST_RESOLVERS` against the builders' signatures, not about the prose. A
    resolver dropped from the table, or a key added to a builder, turns this red before the
    remedy does.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals, cli
    typed = {name for name in cli.manifest_parameters(approvals.preset_subject_manifest)
             if name not in cli.LINE_MANIFEST_RESOLVERS}
    assert typed == {"preset"}, typed
    typed = {name for name in cli.manifest_parameters(approvals.kit_update_subject_manifest)
             if name not in cli.LINE_MANIFEST_RESOLVERS}
    assert typed == set(), typed


def test_a_printed_remedy_names_only_the_flags_its_own_line_takes():
    """The floor under `cli.remedy_flags`, on the two line kinds that can tell it apart.

    A remedy is a line somebody RETYPES, so it may name only keys the command would accept from
    them. Two kinds of key are not that: one a resolver owns (`--content`, which `_line_manifest`
    refuses when typed) and one the builder defaulted, whose ABSENCE carries the decision
    (`--destination` missing is how a deletion is requested -- verifier finding F8). Both live on
    `filing_correction`, and `document_proposal` carries three resolver-owned keys of its own.

    Red without the fix: the derivation `kernel/filing.py` carried until 2026-09-05 -- every
    parameter of the builder, filled from the manifest -- names `--content` and `--destination ""`
    here. That version was in this tree and this test goes red on it.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import approvals, cli
    correction = cli.remedy_flags(approvals.LINE_MANIFEST_BUILDERS["filing_correction"],
                                  {"document": "inbox/x.pdf", "content": "deadbeef",
                                   "reason": "falsch abgelegt", "destination": ""})
    assert correction == '--document "inbox/x.pdf" --reason "falsch abgelegt"', correction
    kept = cli.remedy_flags(approvals.LINE_MANIFEST_BUILDERS["filing_correction"],
                            {"document": "inbox/x.pdf", "content": "deadbeef",
                             "reason": "falsch abgelegt", "destination": "archive/a/b.pdf"})
    assert kept.endswith(' --destination "archive/a/b.pdf"'), kept

    proposal = cli.remedy_flags(approvals.LINE_MANIFEST_BUILDERS["document_proposal"],
                                {"kit_document": "master_data.yaml", "proposal": "staging/x.yaml",
                                 "base": "1", "proposed": "2", "changes": ["a", "b"],
                                 "reason": 'er sagte "jetzt"'})
    assert proposal == ('--kit-document "master_data.yaml" --proposal "staging/x.yaml" '
                        "--reason \"er sagte 'jetzt'\""), proposal


# ---------------- AC-5 / BUG-0071: the category vocabulary grows through the kernel ------------
OLD_STOCK_MASTER_DATA = (
    "# master_data.yaml — owned by: Bookkeeper\n"
    "# Stable vocabulary for the ledger. Append-only.\n"
    "categories:\n"
    "  income: []\n"
    "  expense: []\n"
    "\n"
    "# Counterparty normalisation: statement/marketplace spellings -> ONE canonical name.\n"
    "counterparties: []\n")


@pytest.mark.parametrize("base", [None, OLD_STOCK_MASTER_DATA], ids=["shipped", "old-stock"])
def test_the_bookkeeper_extends_the_category_vocabulary_through_the_kernel_and_books_against_it(
        tmp_path, base):
    """BUG-0071 AC-1 end to end: the live dead end of 2026-08-29, walked through the kernel.

    The bookkeeper needed `Steuerberatungs- und Buchführungskosten`, the document had no such
    key, and no command could add one -- the user typed a five-line block into an editor. Now:
    the role stages the document as it should stand, the manager runs the remedy-shaped
    `request-approval`, the USER answers (played here by the mint hook, the one step no software
    performs), `apply-proposal` writes exactly those bytes, and the ledger books a row against the
    new category that the generated report then shows. On the SHIPPED document that is a grow; on
    the old-stock shape (the July-era file with two empty lists) it is a fill -- both are additions
    the route accepts.

    Red without the fix: with `documents.COMMAND` renamed away (the state before TSK-0092: no
    command at all), the first `harness` line exits 2 with argparse's invalid choice.
    """
    repo = hooks._draft_project(tmp_path)
    write(repo / "project_memory" / "business_profile.yaml",
          hooks.DRAFT_PROFILE + "tax:\n  kleinunternehmer: false\n")
    argv = stage_a_category(repo, base)
    asked = harness(repo, "request-approval", "document_proposal", *argv)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    mint_the_open_request(repo)
    applied = harness(repo, "apply-proposal", *argv)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert "tax_advisory" in read(repo / "project_memory" / "master_data.yaml")

    booked = script(repo, "ledger_add.py", "--year", "2026", "--direction", "expense",
                    "--doc-type", "invoice", "--doc-date", "2026-08-20",
                    "--payment-date", "2026-08-29", "--counterparty", "Steuerkanzlei Muster",
                    "--invoice-no", "SK-2026-77", "--net", "300.00", "--vat-rate", "19",
                    "--gross", "357.00", "--vat-treatment", "standard",
                    "--category", "tax_advisory",
                    "--source", "archive/finance/incoming/2026/2026-08-20_Steuerkanzlei_invoice.pdf")
    assert booked.returncode == 0, booked.stdout + booked.stderr
    reported = script(repo, "euer_report.py", "--year", "2026", "--quarter", "3")
    assert reported.returncode == 0, reported.stdout + reported.stderr
    report = read(repo / "reports" / "euer_2026_Q3.md")
    assert "| tax_advisory | 0.00 | 357.00 |" in report, report


# ---------------- AC-5 / BUG-0070: the rules list is CREATED on an old-stock plan -------------
def test_add_filing_rule_creates_the_rules_list_on_an_old_stock_plan_through_the_entry_point(
        tmp_path):
    """BUG-0070 AC-1 on the CLI route: the plan of 2026-08-29 (no `rules:` key), the kernel's
    own approval question, the user's answer, and the append -- through `scripts/harness.py`.

    `tools/test_kernel.py::test_add_filing_rule_creates_the_rules_list_when_the_plan_carries_none`
    measures the module; this measures the line the manager types, because the live dead end was
    a printed refusal and not a Python exception. The >1-keys refusal stays where it is measured
    (`tools/test_kernel.py::test_a_plan_this_kernel_cannot_append_to_is_refused_and_left_alone`).

    Red without the fix: with `_with_created_rules` gone (the branch raising the 0-keys refusal
    again), the `add-filing-rule` line exits non-zero with "carries 0 top-level `rules:` key(s)".
    """
    repo = hooks._draft_project(tmp_path)
    plan = repo / "project_memory" / "filing_plan.yaml"
    shipped = read(os.path.join(TEMPLATE_STATE, "filing_plan.yaml"))
    old_stock = "".join(line for line in shipped.splitlines(True) if line.strip() != "rules: []")
    assert "rules:" not in old_stock
    write(plan, old_stock)

    argv = a_filing_rule(repo)
    asked = harness(repo, "request-approval", "filing_rule", *argv)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    mint_the_open_request(repo)
    added = harness(repo, "add-filing-rule", *argv)
    assert added.returncode == 0, added.stdout + added.stderr
    after = read(plan)
    assert after.startswith(old_stock), "the created key rewrote the document above it"
    sys.path.insert(0, TEAM_KITS)
    from kernel import filing
    rules = filing.existing_rules(state_of(repo))
    assert [rule["id"] for rule in rules] == ["FP-001"], rules


# ---------------- AC-3 / FR-0081: the chart of accounts -----------------------------------------
def _yaml():
    import yaml
    return yaml


def _template(name):
    return _yaml().safe_load(read(os.path.join(TEMPLATE_STATE, name)))


def test_the_chart_of_accounts_and_the_vocabulary_name_one_form_year():
    """The shipped chart is CONSISTENT with the shipped vocabulary, category by category.

    Two documents state where a category lands on the form; the report takes the chart's line
    while a framework is active and prints the vocabulary's beside it when they differ. So the
    SHIPPED pair must not differ anywhere: same form year, every shipped category mapped to
    exactly one account in EACH framework, that account's line equal to the category's, and the
    legal space named. A category added to the vocabulary without an account in both charts turns
    this red -- which is the tripwire the chart's header promises.
    """
    chart, vocabulary = _template("chart_of_accounts.yaml"), _template("master_data.yaml")
    assert chart["legal_space"] == "DE"
    assert chart["form_year"] == vocabulary["euer_form"]["year"]
    assert chart["active"] is None, "the kit does not choose a framework for a business"
    shipped = {str(entry["key"]): entry["euer_line"]
               for direction in ("income", "expense")
               for entry in vocabulary["categories"][direction]}
    assert len(shipped) >= 15
    for framework in ("SKR03", "SKR04"):
        entries = chart["accounts"][framework]
        mapped = {}
        for entry in entries:
            assert isinstance(entry["account"], str) and entry["account"].isdigit(), entry
            for key in entry["categories"]:
                assert key not in mapped, "%s: %s maps to two accounts" % (framework, key)
                mapped[key] = entry
        assert set(mapped) == set(shipped), (framework, set(mapped) ^ set(shipped))
        for key, line in shipped.items():
            assert mapped[key]["euer_line"] == line, (framework, key, mapped[key], line)


def test_the_chart_of_accounts_is_a_kit_document_the_kernel_writes(tmp_path):
    """FR-0081's 'a kernel writer exists for the document (no editor line)', measured twice.

    Once on the predicate the write-scope refusal names its route by (`kernel.layout.partial_writers`
    over `documents.accepts`), and once end to end through the entry point: a staged chart with one
    more account is proposed, the user answers the kernel's question, `apply-proposal` writes it.
    """
    sys.path.insert(0, TEAM_KITS)
    from kernel import documents, layout
    repo = hooks._draft_project(tmp_path)
    root = str(repo / "project_memory")
    assert documents.accepts(root, "chart_of_accounts.yaml")
    routes = {entry["command"] for entry in layout.partial_writers("chart_of_accounts.yaml", root)}
    assert {documents.COMMAND, documents.REVISION_COMMAND} <= routes, routes

    document = repo / "project_memory" / "chart_of_accounts.yaml"
    text = read(document)
    anchor = '  - account: "4806"\n'
    assert anchor in text
    proposal = text.replace(anchor, '  - account: "4970"\n    label_de: "Nebenkosten des '
                            'Geldverkehrs"\n    euer_line: 60\n    categories: [bank_fees]\n'
                            + anchor, 1)
    write(repo / "project_memory" / "staging" / TASK / "chart_of_accounts.yaml", proposal)
    argv = ["--kit-document", "chart_of_accounts.yaml",
            "--proposal", "staging/%s/chart_of_accounts.yaml" % TASK,
            "--reason", "Kontoführungsgebühren brauchen ein Konto"]
    asked = harness(repo, "request-approval", "document_proposal", *argv)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    mint_the_open_request(repo)
    applied = harness(repo, "apply-proposal", *argv)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert '"4970"' in read(document)


LEDGER_HEADER = ("id,doc_date,payment_date,direction,doc_type,counterparty,invoice_no,net,"
                 "vat_rate,gross,vat_treatment,category,source,reverses,note\n")
PILOT_PROFILE = (
    "business:\n"
    '  name: "Muster Handel e.K."\n'
    '  billing_address: "Musterstr. 1, 12345 Musterstadt"\n'
    '  legal_form: "Einzelunternehmen"\n'
    '  country: "DE"\n'
    "tax:\n"
    "  kleinunternehmer: false\n"
    "receivables:\n"
    "  payment_terms_days: 14\n"
    "document_sources:\n"
    '  - what: "Meine Ausgangsrechnungen aus der Rechnungs-App"\n'
    "    document_types: [sales_invoice]\n")
PILOT_PLAN = (
    "rules:\n"
    "  - id: FP-002\n"
    '    path_template: "archive/finance/outgoing/<year>/"\n'
    "    document_types: [sales_invoice]\n"
    '    filename_template: "YYYY-MM-DD_<counterparty>_<doctype>"\n'
    '    retention: "10y (§ 147 AO)"\n')


def income_row(number, index, paid="2026-08-20", gross="119.00", net="100.00"):
    return ("L2026-%04d,2026-08-%02d,%s,income,invoice,Kaeufer GmbH,RE-2026-%04d,%s,19.00,%s,"
            "standard,sales_taxable,archive/finance/outgoing/2026/x%d.xml,,\n"
            % (index, index, paid, number, net, gross, index))


def pilot_project(tmp_path, chart_active=None, chart_lines=None):
    """An office project with a sender, a payment term, an outgoing-invoice rule and three
    booked outgoing invoices RE-2026-0001..0003 -- the state the docking point meets."""
    repo = hooks._draft_project(tmp_path, profile=PILOT_PROFILE, plan=PILOT_PLAN)
    write(repo / "ledger" / "2026.csv", LEDGER_HEADER + "".join(
        income_row(number, number) for number in (1, 2, 3)))
    if chart_active:
        chart = repo / "project_memory" / "chart_of_accounts.yaml"
        text = read(chart).replace("active: null", "active: %s" % chart_active, 1)
        for key, line in (chart_lines or {}).items():
            anchor = "    categories: [%s]\n" % key
            assert anchor in text, key
            before = text[:text.index(anchor)]
            head, sep, _tail = before.rpartition("    euer_line: ")
            text = head + sep + "%d\n" % line + text[text.index(anchor):]
        write(chart, text)
    return repo


def book(repo, category, invoice="X-1", gross="119.00", net="100.00"):
    return script(repo, "ledger_add.py", "--year", "2026", "--direction", "expense",
                  "--doc-type", "invoice", "--doc-date", "2026-08-20",
                  "--payment-date", "2026-08-29", "--counterparty", "Muster Lieferant",
                  "--invoice-no", invoice, "--net", net, "--vat-rate", "19", "--gross", gross,
                  "--vat-treatment", "standard", "--category", category,
                  "--source", "archive/finance/incoming/2026/2026-08-20_Lieferant_invoice.pdf")


def test_a_booking_names_its_account_and_a_category_the_chart_does_not_map_is_refused(tmp_path):
    """FR-0081: 'the bookkeeper's booking names an account' -- on the line the bookkeeper reads.

    Three states of one project: no framework active (the shipped state: the row books, no
    account is named), SKR03 active (the row books and the line names `4930 Bürobedarf (SKR03)`),
    and SKR03 active with a category no account maps to (refused, nothing written, the remedy
    names `apply-proposal`). A category mapped to TWO accounts is refused the same way -- the
    mutation that lets it through is the one `account_for`'s docstring denies.
    """
    repo = pilot_project(tmp_path)
    quiet = book(repo, "office_supplies")
    assert quiet.returncode == 0 and "account" not in quiet.stdout, quiet.stdout + quiet.stderr

    repo = pilot_project(tmp_path / "skr03", chart_active="SKR03")
    named = book(repo, "office_supplies")
    assert named.returncode == 0, named.stdout + named.stderr
    assert "account 4930 Bürobedarf (SKR03)" in named.stdout, named.stdout
    rows_before = read(repo / "ledger" / "2026.csv")
    refused = book(repo, "tax_advisory", invoice="X-2")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "maps to 0 account(s) of SKR03" in refused.stderr and "apply-proposal" in refused.stderr
    assert read(repo / "ledger" / "2026.csv") == rows_before

    chart = repo / "project_memory" / "chart_of_accounts.yaml"
    write(chart, read(chart).replace("categories: [postage]",
                                     "categories: [postage, office_supplies]", 1))
    twice = book(repo, "office_supplies", invoice="X-3")
    assert twice.returncode == 1 and "maps to 2 account(s) of SKR03 (4930, 4910)" in twice.stderr, (
        twice.stdout + twice.stderr)


def test_the_euer_rollup_reads_the_chart_and_prints_a_disagreement(tmp_path):
    """FR-0081: 'the EUeR rollup reads the mapping' -- and says so where the two documents differ.

    With SKR03 active and the chart's `4930 Bürobedarf` moved to line 61 while the vocabulary keeps
    60, the generated report (a) groups the booking under `Zeile 61` in the per-line table, (b)
    prints the disagreement as a line the Steuerberatung reads, and (c) carries the account table
    with the same money. With the chart inactive none of the three appears -- which is the shipped
    report, unchanged.
    """
    repo = pilot_project(tmp_path, chart_active="SKR03", chart_lines={"office_supplies": 61})
    assert book(repo, "office_supplies").returncode == 0
    reported = script(repo, "euer_report.py", "--year", "2026", "--quarter", "3")
    assert reported.returncode == 0, reported.stdout + reported.stderr
    report = read(repo / "reports" / "euer_2026_Q3.md")
    assert ("| Zeile 61 — Sonstige unbeschränkt abziehbare Betriebsausgaben | 0.00 | 119.00 |"
            in report), report
    assert ("Zeile für office_supplies: 61 laut Kontenrahmen SKR03 (Konto 4930), 60 laut "
            "Vokabular") in report, report
    assert "## Nach Konto (SKR03, Formularjahr 2025)" in report
    assert "| 4930 | Bürobedarf | 61 | 0.00 | 119.00 |" in report, report
    assert "| 8400 | Erlöse 19 % USt | 15 | 357.00 | 0.00 |" in report, report

    plain = pilot_project(tmp_path / "plain")
    assert book(plain, "office_supplies").returncode == 0
    assert script(plain, "euer_report.py", "--year", "2026", "--quarter", "3").returncode == 0
    report = read(plain / "reports" / "euer_2026_Q3.md")
    assert "Nach Konto" not in report and "laut Kontenrahmen" not in report
    assert ("| Zeile 60 — Sonstige unbeschränkt abziehbare Betriebsausgaben | 0.00 | 119.00 |"
            in report)



# ---------------- AC-4 / FR-0002: the verdict table answers for itself --------------------------
# THE FENCE-BLIND SPAN READER THAT STOOD HERE IS GONE (`BUG-0263` AC-4). It existed because the
# repo-wide reader was fence-BLINDED -- `_CODE_SPAN_RX` pairs single backticks across a whole file,
# a fenced block is an odd number of them, and from the first fence on it paired the GAPS instead of
# the spans, so `docs/office-kit-from-field.md` (which fences in line 23) contributed 0 of its
# citations. `test_repo_hygiene._without_fenced_blocks` is that rule now, applied inside
# `_test_citations` itself, and a second copy of a definition is what this item asked to be deleted
# once the one reader carried it. The floor below is what remains: it keeps this test from passing
# on a document whose citations somebody removed rather than repaired.
FENCED_DOCUMENTS = (("docs/office-kit-from-field.md", 8),
                    ("docs/office/invoice-app-docking-point.md", 9))


@pytest.mark.parametrize("document, floor", FENCED_DOCUMENTS)
def test_every_test_the_field_report_verdicts_name_is_one_that_exists(document, floor):
    """BUG-0263 AC-4 measured from this side: the duplicate fenced-block reader is gone and the ONE
    reader still finds every citation of these two documents, each of which resolves.

    A named test is a claim like any other (DEC-0070): AC-4's whole verdict table rests on one set
    of them, and the contract page's §6 promises an application project that every "refused" and
    "accepted" above it is held by one. Measured 2026-09-06 by the verifier: the repo-wide pointer
    check stayed GREEN with a planted `test_this_name_resolves_to_nothing_at_all` in the field
    report, because it never sees a citation below a code fence -- and both documents fence early.
    That reader carries the fence rule itself now (`test_repo_hygiene._without_fenced_blocks`), so
    this asks it directly and resolves every node id through `test_repo_hygiene._defined_in` --
    parsed, never grepped. The floor is what keeps the removal honest: if the one reader ever stops
    seeing these citations, this goes red on the count before any assertion below it is vacuous.
    """
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import test_repo_hygiene as hygiene
    with open(os.path.join(ROOT, *document.split("/")), encoding="utf-8") as handle:
        text = handle.read()
    citations = hygiene._test_citations(text)
    assert len(citations) >= floor, ("only %d citations read in %s -- the reader stopped seeing "
                                     "them and every assertion below is vacuous"
                                     % (len(citations), document))
    unresolved = []
    for _offset, cited, name in citations:
        defined = hygiene._defined_in(cited)
        if defined is None or name not in defined:
            unresolved.append("%s::%s (%s)" % (cited, name,
                                               "no such suite file" if defined is None
                                               else "no such test in it"))
    assert not unresolved, (
        "%s answers for a judgement by naming a test that does not exist, which makes the "
        "sentence read as measured while nothing measures it: %s" % (document, unresolved))

# ---------------- AC-2 / DEC-0075: the docking point -------------------------------------------
GUIDELINE = "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:en16931"


def cii(invoice_no="RE-2026-0004", issue="20260901", type_code="380", seller="Muster Handel e.K.",
        buyer="Kaeufer GmbH", seller_country="DE", buyer_country="DE", net="214.20", tax="40.70",
        gross="254.90", rate="19", category="S", preceding="", lines=3, guideline=GUIDELINE,
        breakdown=True):
    """An app-produced CII invoice with every field the docking point reads, each overridable.

    `breakdown=False` drops BG-23 entirely -- the shape EN 16931 requires and a generator can still
    omit, and the one the intake used to fill a rate and a treatment for out of the total.
    """
    def party(name, country):
        return "<ram:Name>%s</ram:Name>%s" % (
            name, '<ram:PostalTradeAddress><ram:CountryID>%s</ram:CountryID>'
                  '</ram:PostalTradeAddress>' % country if country else "")
    context = ('<ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>%s</ram:ID>'
               '</ram:GuidelineSpecifiedDocumentContextParameter>' % guideline if guideline else "")
    referenced = ('<ram:InvoiceReferencedDocument><ram:IssuerAssignedID>%s</ram:IssuerAssignedID>'
                  '</ram:InvoiceReferencedDocument>' % preceding if preceding else "")
    per_line = round(float(net) / lines, 2) if lines else 0
    items = "".join(hooks._cii_line(n, 1, per_line) for n in range(1, lines + 1))
    return ('<?xml version="1.0" encoding="UTF-8"?><rsm:CrossIndustryInvoice %s>'
            '<rsm:ExchangedDocumentContext>%s</rsm:ExchangedDocumentContext>'
            '<rsm:ExchangedDocument><ram:ID>%s</ram:ID><ram:TypeCode>%s</ram:TypeCode>'
            '<ram:IssueDateTime><udt:DateTimeString format="102">%s</udt:DateTimeString>'
            '</ram:IssueDateTime></rsm:ExchangedDocument><rsm:SupplyChainTradeTransaction>%s'
            '<ram:ApplicableHeaderTradeAgreement><ram:SellerTradeParty>%s</ram:SellerTradeParty>'
            '<ram:BuyerTradeParty>%s</ram:BuyerTradeParty></ram:ApplicableHeaderTradeAgreement>'
            '<ram:ApplicableHeaderTradeDelivery/><ram:ApplicableHeaderTradeSettlement>'
            '<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>%s%s'
            '<ram:SpecifiedTradeSettlementHeaderMonetarySummation>'
            '<ram:LineTotalAmount>%s</ram:LineTotalAmount>'
            '<ram:TaxBasisTotalAmount>%s</ram:TaxBasisTotalAmount>'
            '<ram:TaxTotalAmount currencyID="EUR">%s</ram:TaxTotalAmount>'
            '<ram:GrandTotalAmount>%s</ram:GrandTotalAmount>'
            '<ram:DuePayableAmount>%s</ram:DuePayableAmount>'
            '</ram:SpecifiedTradeSettlementHeaderMonetarySummation>'
            '</ram:ApplicableHeaderTradeSettlement></rsm:SupplyChainTradeTransaction>'
            '</rsm:CrossIndustryInvoice>'
            % (hooks.CII_NS, context, invoice_no, type_code, issue, items,
               party(seller, seller_country), party(buyer, buyer_country), referenced,
               ('<ram:ApplicableTradeTax><ram:CalculatedAmount>%s</ram:CalculatedAmount>'
                '<ram:TypeCode>VAT</ram:TypeCode><ram:BasisAmount>%s</ram:BasisAmount>'
                '<ram:CategoryCode>%s</ram:CategoryCode><ram:RateApplicablePercent>%s'
                '</ram:RateApplicablePercent></ram:ApplicableTradeTax>'
                % (tax, net, category, rate)) if breakdown else "",
               net, net, tax, gross, gross))


def ubl(invoice_no="RE-2026-0004"):
    return ('<?xml version="1.0" encoding="UTF-8"?><Invoice %s>'
            '<cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:'
            'xrechnung_3.0</cbc:CustomizationID><cbc:ID>%s</cbc:ID>'
            '<cbc:IssueDate>2026-09-01</cbc:IssueDate><cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>'
            '<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>'
            '<cac:AccountingSupplierParty><cac:Party><cac:PartyName><cbc:Name>Muster Handel e.K.'
            '</cbc:Name></cac:PartyName><cac:PostalAddress><cac:Country><cbc:IdentificationCode>DE'
            '</cbc:IdentificationCode></cac:Country></cac:PostalAddress></cac:Party>'
            '</cac:AccountingSupplierParty><cac:AccountingCustomerParty><cac:Party><cac:PartyName>'
            '<cbc:Name>Kaeufer GmbH</cbc:Name></cac:PartyName><cac:PostalAddress><cac:Country>'
            '<cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country></cac:PostalAddress>'
            '</cac:Party></cac:AccountingCustomerParty>'
            '<cac:TaxTotal><cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount><cac:TaxSubtotal>'
            '<cbc:TaxableAmount currencyID="EUR">100.00</cbc:TaxableAmount><cbc:TaxAmount '
            'currencyID="EUR">19.00</cbc:TaxAmount><cac:TaxCategory><cbc:ID>S</cbc:ID>'
            '<cbc:Percent>19</cbc:Percent></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>'
            '<cac:LegalMonetaryTotal><cbc:LineExtensionAmount currencyID="EUR">100.00'
            '</cbc:LineExtensionAmount><cbc:TaxExclusiveAmount currencyID="EUR">100.00'
            '</cbc:TaxExclusiveAmount><cbc:TaxInclusiveAmount currencyID="EUR">119.00'
            '</cbc:TaxInclusiveAmount><cbc:PayableAmount currencyID="EUR">119.00'
            '</cbc:PayableAmount></cac:LegalMonetaryTotal>'
            '<cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="C62">1'
            '</cbc:InvoicedQuantity><cbc:LineExtensionAmount currencyID="EUR">100.00'
            '</cbc:LineExtensionAmount></cac:InvoiceLine></Invoice>' % (hooks.UBL_NS, invoice_no))


RANGES = (
    "number_ranges:\n"
    "  - key: shop_a\n"
    '    business: "Muster Handel e.K."\n'
    '    pattern: "RE-(?P<year>\\\\d{4})-(?P<number>\\\\d{4})"\n'
    "    issued_by: app\n"
    "    document_type: sales_invoice\n"
    "    category: sales_taxable\n"
    "    first: 1\n"
    "  - key: shopify\n"
    '    business: "Muster Handel e.K."\n'
    '    pattern: "SH-(?P<number>\\\\d+)"\n'
    "    issued_by: marketplace\n"
    "    document_type: sales_invoice\n"
    "    category: sales_taxable\n")


def declare_ranges(repo, through_the_kernel=False):
    """The project's half of the interface contract: two ranges in `master_data.yaml`."""
    document = repo / "project_memory" / "master_data.yaml"
    text = read(document)
    assert "number_ranges: []\n" in text
    proposal = text.replace("number_ranges: []\n", RANGES, 1)
    if not through_the_kernel:
        write(document, proposal)
        return
    write(repo / "project_memory" / "staging" / TASK / "master_data.yaml", proposal)
    argv = ["--kit-document", "master_data.yaml",
            "--proposal", "staging/%s/master_data.yaml" % TASK,
            "--reason", "Die zwei Nummernkreise der Rechnungs-App"]
    asked = harness(repo, "request-approval", "document_proposal", *argv)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    mint_the_open_request(repo)
    applied = harness(repo, "apply-proposal", *argv)
    assert applied.returncode == 0, applied.stdout + applied.stderr


def drop(repo, name, xml):
    """The application's drop: one file in `inbox/`, flat, as the interface contract says."""
    path = repo / "inbox" / name
    if name.endswith(".pdf"):
        pypdf = pytest.importorskip("pypdf")
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.add_attachment("factur-x.xml", xml.encode("utf-8"))
        os.makedirs(os.path.dirname(str(path)), exist_ok=True)
        with open(str(path), "wb") as handle:
            writer.write(handle)
    else:
        write(path, xml)
    return "inbox/" + name


def intake(repo, source, *args):
    return script(repo, "invoice_intake.py", source, *args)


DESTINATION = "archive/finance/outgoing/2026/2026-09-01_Kaeufer-GmbH_sales_invoice"


@pytest.mark.parametrize("name, xml", [("RE-2026-0004.xml", cii()), ("RE-2026-0004.pdf", cii()),
                                       ("RE-2026-0004-ubl.xml", ubl())],
                         ids=["cii-xml", "zugferd-pdf", "xrechnung-ubl"])
def test_an_app_produced_invoice_is_accepted_with_its_filing_and_booking_named(tmp_path, name,
                                                                                xml):
    """AC-2, the accepting half, on the fixture set the criterion names (a ZUGFeRD PDF with the
    XML embedded, an XRechnung XML) plus the CII XML the PDF carries: the verdict names the range,
    the business, the continuity figures, the destination under the plan's rule and the ledger
    line -- and moves nothing, books nothing."""
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    source = drop(repo, name, xml)
    result = intake(repo, source, "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["verdict"] == "accepted" and verdict["range"] == "shop_a"
    assert verdict["continuity"] == "range shop_a / 2026: 4 continues the series (last issued 3)"
    assert verdict["filing"]["destination"] == DESTINATION + os.path.splitext(name)[1]
    assert verdict["filing"]["rule_id"] == "FP-002"
    assert "BR-CO-15" in verdict["norm_rules_checked"] and "BR-07" in verdict["norm_rules_checked"]
    assert verdict["booking"]["ledger_add"][-1] == "--open"
    assert "--category=sales_taxable" in verdict["booking"]["ledger_add"]
    assert os.path.isfile(str(repo / source)) and not os.path.isdir(str(repo / "archive"))
    assert "RE-2026-0004" not in read(repo / "ledger" / "2026.csv")


def test_the_docking_point_files_through_the_registered_chain_and_books(tmp_path):
    """AC-2 END TO END on a pilot: the range declared THROUGH THE KERNEL (apply-proposal), the app's
    drop, the intake's verdict and staged proposal, the move refused by the registered chain
    until two independent readings exist, then let through, then the booking -- and the report
    shows the open item. Every step is the shipped one; the played parts are the user's answer
    (the mint hook) and the two readers' runs (`_record_reading` through the PostToolUse chain)."""
    repo = pilot_project(tmp_path)
    declare_ranges(repo, through_the_kernel=True)
    source = drop(repo, "RE-2026-0004.xml", cii())
    judged = intake(repo, source, "--task", TASK)
    assert judged.returncode == 0, judged.stdout + judged.stderr
    proposal = repo / "project_memory" / "staging" / TASK / "filing_proposal_RE-2026-0004.yaml"
    staged = _yaml().safe_load(read(proposal))
    assert staged["proposals"][0]["destination"] == DESTINATION + ".xml"
    assert staged["proposals"][0]["rule_id"] == "FP-002"
    assert set(staged["proposals"][0]) >= {"source", "document_class", "destination", "rule_id",
                                           "findings"}

    destination = DESTINATION + ".xml"
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": "mv %s %s" % (source, destination)}}
    code, said = hooks._through_the_chain(repo, payload)
    assert code == 2 and "gate_second_reading" in said, said
    early = intake(repo, source, "--book")
    assert early.returncode == 2 and "book AFTER the move" in early.stderr, early.stderr

    hooks._record_reading(repo, "run-a", "read_a.yaml", [(source, destination, "sales invoice")])
    hooks._record_reading(repo, "run-b", "read_b.yaml", [(source, destination, "sales invoice")])
    code, said = hooks._through_the_chain(repo, payload)
    assert code == 0, said
    os.makedirs(os.path.dirname(str(repo / destination)), exist_ok=True)
    os.replace(str(repo / source), str(repo / destination))

    booked = intake(repo, destination, "--book")
    assert booked.returncode == 0, booked.stdout + booked.stderr
    ledger = read(repo / "ledger" / "2026.csv")
    assert (",income,invoice,Kaeufer GmbH,RE-2026-0004,214.20,19.00,254.90,standard,"
            "sales_taxable,%s,," % destination) in ledger, ledger
    reported = script(repo, "euer_report.py", "--year", "2026", "--quarter", "3")
    assert reported.returncode == 0, reported.stdout + reported.stderr
    assert ("RE-2026-0004 | Kaeufer GmbH | 2026-09-01 | 254.90 EUR"
            in read(repo / "reports" / "euer_2026_Q3.md"))


@pytest.mark.parametrize("planted, xml, names", [
    ("broken triple", cii(gross="300.00"),
     ["BR-CO-15", "net 214.20, tax 40.70, gross 300.00"]),
    ("gap in the range", cii(invoice_no="RE-2026-0006"),
     ["last issued 3, arriving 6, 2 number(s) missing in between (4..5)"]),
    ("missing mandatory field", cii(buyer=""), ["BR-07 (BT-44)"]),
    ("missing seller country", cii(seller_country=""), ["BR-09 (BT-40)"]),
    ("missing specification identifier", cii(guideline=""), ["BR-01 (BT-24)"]),
    ("no invoice line", cii(lines=0), ["BR-16 (BG-25)"]),
    ("repeated number", cii(invoice_no="RE-2026-0003"),
     ["number 3 of range shop_a / 2026 is already booked"]),
    ("corrected invoice 384", cii(type_code="384"), ["381 credit note", "NEW 380"]),
    ("second invoice over one delivery", cii(preceding="RE-2026-0002"), ["§ 14c UStG"]),
    ("issued in another name", cii(seller="Fremde Firma GmbH"),
     ["issued in the name 'Fremde Firma GmbH'"]),
    ("undeclared range", cii(invoice_no="XX-1"), ["matches none of the 2 declared number range(s)"]),
    ("credit note without a booked original", cii(type_code="381", preceding="RE-2026-0009"),
     ["no booked income row carries that number"]),
    # A VAT CATEGORY NOBODY READ, and a rate that is not a number. Measured 2026-09-05 before the
    # fix: BOTH were ACCEPTED (exit 0). The unknown code was filtered out of the treatment set and
    # the fallback decided `standard` off the rate; the unreadable rate was never looked at, because
    # the fallback that would have parsed it is the else of a conditional the known code satisfied,
    # and it travelled on into the `--vat-rate` of the booking line the verdict prints. The row
    # carries both figures, so both are read off the document or neither is booked.
    ("a VAT category code nobody read", cii(category="B"),
     ["VAT category code(s) B", "guessed"]),
    ("a VAT rate that is not a number", cii(rate="neunzehn"),
     ["states its VAT rate as 'neunzehn'"]),
], ids=lambda value: value if isinstance(value, str) and " " in value else None)
def test_a_planted_violation_is_refused_with_the_figures_named(tmp_path, planted, xml, names):
    """AC-2's refusing half: every planted violation the criterion names, and the ones DEC-0075 (5)
    adds, is REFUSED (exit 2) with the rule or the figures in the message, nothing staged."""
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    source = drop(repo, "drop.xml", xml)
    result = intake(repo, source, "--task", TASK)
    assert result.returncode == 2, (planted, result.stdout + result.stderr)
    for name in names:
        assert name in result.stderr, (planted, name, result.stderr)
    assert not os.path.isdir(str(repo / "project_memory" / "staging" / TASK)), planted


def test_a_marketplace_range_reports_a_gap_and_a_credit_note_cancels_a_booked_invoice(tmp_path):
    """The other two marketplace cases of DEC-0075 (5): import-only (a gap in a range another
    system issues is reported, not refused) and cancel-and-reissue (a 381 naming a booked number
    books as a credit note; the reissued 380 then follows without a reference)."""
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    imported = intake(repo, drop(repo, "SH-1007.xml", cii(invoice_no="SH-1007")), "--json")
    assert imported.returncode == 0, imported.stdout + imported.stderr
    verdict = json.loads(imported.stdout)
    assert verdict["range"] == "shopify"
    assert verdict["continuity"].startswith("GAP REPORTED, not refused (issued_by: marketplace)")
    assert "arriving 1007, 1006 number(s) missing" in verdict["continuity"]

    cancelled = intake(repo, drop(repo, "storno.xml",
                                  cii(type_code="381", preceding="RE-2026-0002")), "--json")
    assert cancelled.returncode == 0, cancelled.stdout + cancelled.stderr
    row = json.loads(cancelled.stdout)["booking"]["ledger_add"]
    assert "--doc-type=credit_note" in row, row



# ---------------- AC-2, round-2 rework: the verdict, the ledger, and the exit codes -------------
def test_the_intake_refuses_a_document_whose_booking_line_the_ledger_would_refuse(tmp_path):
    """The verdict never promises a booking that cannot happen -- verifier round 1, B1.

    Measured before the fix, through the two shipped scripts: a document stating `19 %` with a tax
    of 0.00 came back ACCEPTED with `net=999 rate=19 gross=999`, and a document with no BG-23 at
    all came back ACCEPTED with `rate 0, treatment exempt` while stating tax 40.70 -- both values
    derived from a total, both refused by `ledger_add` a step later. That contradicted three
    written sentences (the module docstring's "nothing it decides is a guess", the contract page's
    "the kit never fills either from the other", PR-0009's money invariant).

    Held in BOTH directions, which is what makes it more than a refusal test: an ACCEPTED
    document's printed booking line is handed to `ledger_add` and taken (rc 0). A guard that
    refused everything would fail that half.
    """
    repo = pilot_project(tmp_path)
    declare_ranges(repo)

    stated = intake(repo, drop(repo, "a.xml", cii(net="999.00", tax="0.00", gross="999.00",
                                                  rate="19")), "--task", TASK)
    assert stated.returncode == 2, stated.stdout + stated.stderr
    assert "the ledger itself refuses" in stated.stderr, stated.stderr
    assert "999.00" in stated.stderr and "19.00" in stated.stderr, stated.stderr

    silent = intake(repo, drop(repo, "b.xml", cii(breakdown=False)), "--task", TASK)
    assert silent.returncode == 2, silent.stdout + silent.stderr
    assert "no VAT breakdown (BG-23)" in silent.stderr, silent.stderr
    assert "40.70" in silent.stderr, silent.stderr
    assert not os.path.isdir(str(repo / "project_memory" / "staging" / TASK))

    good = intake(repo, drop(repo, "c.xml", cii()), "--json")
    assert good.returncode == 0, good.stdout + good.stderr
    row = json.loads(good.stdout)["booking"]["ledger_add"]
    destination = json.loads(good.stdout)["filing"]["destination"]
    os.makedirs(os.path.dirname(str(repo / destination)), exist_ok=True)
    write(repo / destination, "x")
    booked = script(repo, "ledger_add.py", *row)
    assert booked.returncode == 0, booked.stdout + booked.stderr


def test_the_gap_refusal_names_an_order_this_script_actually_walks(tmp_path):
    """Verifier round 1, B2 -- BUG-0079's class inside the BUG-0079 stream.

    The old remedy said a cancelled number's "cancellation documents arrive first", and that is
    the one order `document_type_check` refuses: a 381 on a number no income row carries. So a
    cancelled, never-delivered document had no walkable way in at all -- BUG-0041's dead end.
    The remedy now names the order the script takes, and this test EXECUTES it: the refused 381
    first (still refused), then the 380, then its 381, then the number that had the gap.
    """
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    gap = intake(repo, drop(repo, "gap.xml", cii(invoice_no="RE-2026-0005")))
    assert gap.returncode == 2 and "gap in range shop_a" in gap.stderr, gap.stderr
    assert "hand its own invoice in first" in gap.stderr, gap.stderr

    wrong_way = intake(repo, drop(repo, "storno-first.xml",
                                  cii(invoice_no="RE-2026-0004", type_code="381",
                                      preceding="RE-2026-0004")))
    assert wrong_way.returncode == 2, wrong_way.stderr
    assert "no booked income row carries that number" in wrong_way.stderr, wrong_way.stderr

    original = intake(repo, drop(repo, "original.xml", cii(invoice_no="RE-2026-0004")), "--json")
    assert original.returncode == 0, original.stdout + original.stderr
    write(repo / "ledger" / "2026.csv", read(repo / "ledger" / "2026.csv") + income_row(4, 4))

    storno = intake(repo, drop(repo, "storno.xml",
                               cii(invoice_no="RE-2026-0005", type_code="381",
                                   preceding="RE-2026-0004")), "--json")
    assert storno.returncode == 0, storno.stdout + storno.stderr
    write(repo / "ledger" / "2026.csv", read(repo / "ledger" / "2026.csv") + income_row(5, 5))
    after = intake(repo, drop(repo, "next.xml", cii(invoice_no="RE-2026-0006")), "--json")
    assert after.returncode == 0, after.stdout + after.stderr


def _plant(path, old, new):
    """One replacement in a file the pilot already wrote, and a loud failure when it plants nothing.

    Measured 2026-09-06: `two_ranges` anchored on `number_ranges: []`, which `declare_ranges` has
    already replaced by then -- the helper wrote the document back unchanged and its case passed
    the untouched fixture through as ACCEPTED. A planting helper that cannot fail to plant is the
    same defect class as a test that cannot go red.
    """
    text = read(path)
    assert text.count(old) >= 1, "nothing to plant on: %r" % old
    write(path, text.replace(old, new, 1))


def two_ranges(repo):
    _plant(repo / "project_memory" / "master_data.yaml", "    first: 1\n",
           "    first: 1\n"
           "  - key: twin\n"
           '    business: "Muster Handel e.K."\n'
           '    pattern: "RE-(?P<year>[0-9]{4})-(?P<number>[0-9]{4})"\n'
           "    issued_by: app\n"
           "    document_type: sales_invoice\n"
           "    category: sales_taxable\n")


def unknown_category(repo):
    _plant(repo / "project_memory" / "master_data.yaml", "    category: sales_taxable\n",
           "    category: gibt_es_nicht\n")


def placeholder_rule(repo):
    _plant(repo / "project_memory" / "filing_plan.yaml",
           '"YYYY-MM-DD_<counterparty>_<doctype>"', '"YYYY-MM-DD_<Sachbearbeiter>"')


def no_rule_for_the_class(repo):
    _plant(repo / "project_memory" / "master_data.yaml", "    document_type: sales_invoice\n",
           "    document_type: kein_typ\n")


@pytest.mark.parametrize("planted, prepare, xml, name, exit_code, says", [
    ("a category the vocabulary does not know", unknown_category, None, None, 1,
     "master_data.yaml's income categories do not carry it"),
    ("a placeholder the intake cannot fill", placeholder_rule, None, None, 1,
     "carries the placeholder <Sachbearbeiter>"),
    ("no plan rule for the class", no_rule_for_the_class, None, None, 1,
     "0 plan rule(s) file the class 'kein_typ'"),
    ("two ranges match one number", two_ranges, None, None, 1,
     "matches 2 declared ranges"),
    ("a PDF without embedded XML", None, None, "empty.pdf", 1,
     "carries no embedded e-invoice XML"),
    ("two VAT rates on one document", None, "two-rates", None, 2,
     "carries 2 VAT rates"),
    ("a number the counting part cannot order", None, "underscore", None, 2,
     "has to be a decimal number"),
], ids=lambda value: value if isinstance(value, str) and " " in value else None)
def test_a_project_side_gap_is_not_judgeable_and_a_document_fault_is_refused(
        tmp_path, planted, prepare, xml, name, exit_code, says):
    """Verifier round 1, B3 + B4 + N5 -- six refusals no test held, and the exit code they carry.

    B4 measured all six removable with the whole suite still green, and four of them are literal
    "refused" sentences of `docs/office/invoice-app-docking-point.md`. B3 measured the contract's
    exit-code table wrong for one of them. Both are answered by one definition, which is now the
    module docstring's: a no about the DOCUMENT is 2, a no about this PROJECT's own configuration
    is 1 -- the application on the other side branches on that number, and the business, not the
    application, fixes an exit 1.
    """
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    if prepare is not None:
        prepare(repo)
    if name == "empty.pdf":
        pypdf = pytest.importorskip("pypdf")
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=595, height=842)
        os.makedirs(str(repo / "inbox"), exist_ok=True)
        with open(str(repo / "inbox" / "empty.pdf"), "wb") as handle:
            writer.write(handle)
        source = "inbox/empty.pdf"
    elif xml == "two-rates":
        document = cii().replace("</ram:ApplicableTradeTax>",
                                 "</ram:ApplicableTradeTax><ram:ApplicableTradeTax>"
                                 "<ram:CalculatedAmount>0.00</ram:CalculatedAmount>"
                                 "<ram:TypeCode>VAT</ram:TypeCode>"
                                 "<ram:BasisAmount>0.00</ram:BasisAmount>"
                                 "<ram:CategoryCode>S</ram:CategoryCode>"
                                 "<ram:RateApplicablePercent>7</ram:RateApplicablePercent>"
                                 "</ram:ApplicableTradeTax>", 1)
        source = drop(repo, "drop.xml", document)
    elif xml == "underscore":
        _plant(repo / "project_memory" / "master_data.yaml", '(?P<number>\\\\d{4})',
               '(?P<number>[0-9_]{3,5})')
        source = drop(repo, "drop.xml", cii(invoice_no="RE-2026-1_0"))
    else:
        source = drop(repo, "drop.xml", cii())
    result = intake(repo, source, "--task", TASK)
    assert result.returncode == exit_code, (planted, result.stdout + result.stderr)
    assert says in result.stderr, (planted, result.stderr)
    assert not os.path.isdir(str(repo / "project_memory" / "staging" / TASK)), planted


def test_two_documents_never_render_one_filing_destination(tmp_path):
    """N1: the shipped `filename_template` carries no number, so two invoices to one customer on
    one day rendered ONE path -- and the move that overwrites the first is one `gate_filing`
    accepts, because the destination matches the rule either way. The intake cannot rewrite the
    plan, so it refuses to name a taken path and says which placeholder makes the rule unambiguous.
    """
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    first = intake(repo, drop(repo, "one.xml", cii()), "--json")
    assert first.returncode == 0, first.stdout + first.stderr
    destination = json.loads(first.stdout)["filing"]["destination"]
    os.makedirs(os.path.dirname(str(repo / destination)), exist_ok=True)
    write(repo / destination, "the first document")

    write(repo / "ledger" / "2026.csv", read(repo / "ledger" / "2026.csv") + income_row(4, 4))
    second = intake(repo, drop(repo, "two.xml", cii(invoice_no="RE-2026-0005")), "--task", TASK)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "would overwrite it" in second.stderr, second.stderr
    assert "<invoice_no>" in second.stderr, second.stderr
    assert read(repo / destination) == "the first document"


def test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed(tmp_path):
    """N2 of verifier round 1, and BUG-0072's class reached through a FILE NAME.

    Measured 2026-09-06: a PDF with `factur-x.xml` (the document's real figures) attached FIRST
    and `aaa-invoice.xml` (999.00) attached second was accepted with 999.00 -- pypdf hands
    attachments back in name-tree order, so the alphabetically first one won, and the contract
    page's "the kit takes the first attachment ending in `.xml`" described neither the order nor
    the risk. The reader now decides by what an attachment IS, and refuses to pick between two.
    """
    pypdf = pytest.importorskip("pypdf")
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment("factur-x.xml", cii().encode("utf-8"))
    writer.add_attachment("aaa-invoice.xml",
                          cii(net="999.00", tax="0.00", gross="999.00", rate="0",
                              category="E").encode("utf-8"))
    os.makedirs(str(repo / "inbox"), exist_ok=True)
    with open(str(repo / "inbox" / "two.pdf"), "wb") as handle:
        writer.write(handle)

    result = intake(repo, "inbox/two.pdf", "--task", TASK)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "two.pdf carries 2 embedded e-invoice XML files" in result.stderr.replace(
        "this PDF", "two.pdf"), result.stderr
    assert "factur-x.xml" in result.stderr and "aaa-invoice.xml" in result.stderr, result.stderr
    assert "999" not in result.stdout, result.stdout

    one = pypdf.PdfWriter()
    one.add_blank_page(width=595, height=842)
    one.add_attachment("aaa-invoice.xml", cii().encode("utf-8"))
    with open(str(repo / "inbox" / "one.pdf"), "wb") as handle:
        one.write(handle)
    taken = intake(repo, "inbox/one.pdf", "--json")
    assert taken.returncode == 0, taken.stdout + taken.stderr
    assert json.loads(taken.stdout)["net"] == "214.20", taken.stdout

    # R3 of verify round 2: the first cut of the predicate asked whether the bytes PARSE, which is a
    # different question. PDF/A-3 allows further attachments, and an ordinary note was counted as an
    # e-invoice and made a legitimate PDF "not judgeable" -- while the contract page promises the
    # app project that the kit "takes the one that IS an e-invoice".
    withnote = pypdf.PdfWriter()
    withnote.add_blank_page(width=595, height=842)
    withnote.add_attachment("factur-x.xml", cii().encode("utf-8"))
    withnote.add_attachment("aaa-note.xml", b"<note>hello</note>")
    with open(str(repo / "inbox" / "note.pdf"), "wb") as handle:
        withnote.write(handle)
    beside_a_note = intake(repo, "inbox/note.pdf", "--json")
    assert beside_a_note.returncode == 0, beside_a_note.stdout + beside_a_note.stderr
    assert json.loads(beside_a_note.stdout)["net"] == "214.20", beside_a_note.stdout


@pytest.mark.parametrize("planted, buyer, retypeable", [
    ("a buyer named like a flag", "--doc-type", True),
    ("a buyer carrying a quotation mark", 'He said "hi"', False),
], ids=lambda value: value if isinstance(value, str) and " " in value else None)
def test_the_printed_booking_line_books_what_the_verdict_read(tmp_path, planted, buyer,
                                                              retypeable):
    """R4 of verify round 2: the promise held for the DICT that was judged, not for the LINE.

    Two measured ways one document's verdict booked something else than the verdict read.
    A buyer literally named `--doc-type`: the dict's value is non-empty, so `validate_row` is
    content, and the argv rendered from it made argparse read the VALUE as an option (`ledger_add`
    rc 2, an argparse usage message). That one is closed by rendering `--flag=value`, and the line
    is offered and books the exact name.
    A buyer `He said "hi"`: no rendering of it survives being retyped -- the first cut printed
    `--counterparty "He said "hi""` (a shell reads `He said hi`) and the kernel's own remedy rule
    would have booked `He said 'hi'`, because it SWAPS the character. So no line is offered at all;
    the verdict names `--book`, which passes no shell, and THAT books the exact name.

    The test does what a role does: it takes what was printed, splits it the way a POSIX shell
    splits it, runs `ledger_add` with that -- and compares the booked `counterparty` FIELD, because
    a `"` in a value is doubled by the CSV writer and a substring test over the file would pass for
    a name the ledger does not carry.
    """
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    for index in (4,):
        source = drop(repo, "b%d.xml" % index, cii(invoice_no="RE-2026-%04d" % index,
                                                   buyer=buyer))
        judged = intake(repo, source, "--json")
        assert judged.returncode == 0, (buyer, judged.stdout + judged.stderr)
        verdict = json.loads(judged.stdout)
        destination = verdict["filing"]["destination"]

        # `--json` prints the verdict INSTEAD of the human-readable plan, and the human-readable
        # plan is what this test is about -- so the same file is judged twice. Nothing is written
        # by a judgement without `--task` or `--book`, which is what makes that safe.
        spoken = intake(repo, source)
        assert spoken.returncode == 0, (buyer, spoken.stdout + spoken.stderr)
        os.makedirs(os.path.dirname(str(repo / destination)), exist_ok=True)
        os.replace(str(repo / source), str(repo / destination))

        offered = [line for line in spoken.stdout.splitlines()
                   if line.startswith("[intake] booking: python scripts/ledger_add.py")]
        assert bool(offered) is retypeable, (planted, spoken.stdout)
        if retypeable:
            argv = shlex.split(offered[0].split("ledger_add.py", 1)[1], posix=True)
            assert verdict["booking"]["ledger_add"] == argv, (planted, argv)
            booked = script(repo, "ledger_add.py", *argv)
        else:
            assert "--book" in spoken.stdout, spoken.stdout
            assert "no command line can be retyped with" in spoken.stdout, spoken.stdout
            booked = intake(repo, destination, "--book")
        assert booked.returncode == 0, (planted, booked.stdout + booked.stderr)
        # Compared as a FIELD: a `"` in a value is doubled by the CSV writer, so a substring test
        # over the file would pass for a name the ledger does not carry -- and a name the ledger
        # does not carry is exactly what this test exists to catch.
        with open(str(repo / "ledger" / "2026.csv"), encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        booked_row = [row for row in rows if row["invoice_no"] == "RE-2026-%04d" % index]
        assert len(booked_row) == 1, (buyer, rows)
        assert booked_row[0]["counterparty"] == buyer, (planted, booked_row[0])


def test_two_plan_rules_for_one_class_are_not_judgeable(tmp_path):
    """R5 of verify round 2: `destination_of` says "exactly one is needed" and the ONE case a test
    held was zero. A mutation from `!= 1` to `< 1` -- two rules silently accepted, and the first one
    deciding where the document lands -- left all 62 tests green while the branch worked."""
    repo = pilot_project(tmp_path)
    declare_ranges(repo)
    write(repo / "project_memory" / "filing_plan.yaml", PILOT_PLAN
          + "  - id: FP-003\n"
            '    path_template: "archive/finance/zweitablage/<year>/"\n'
            "    document_types: [sales_invoice]\n"
            '    filename_template: "YYYY-MM-DD_<counterparty>_<doctype>"\n'
            '    retention: "10y (§ 147 AO)"\n')
    result = intake(repo, drop(repo, "drop.xml", cii()), "--task", TASK)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "2 plan rule(s) file the class 'sales_invoice'" in result.stderr, result.stderr
    assert "exactly one is needed" in result.stderr, result.stderr
    # The remedy follows the COUNT: telling the reader of a double rule to add a third was the
    # aside of R5, so the two-rule branch names the two rules and the move that resolves them.
    assert "(FP-002, FP-003)" in result.stderr, result.stderr
    assert "never edits or removes a rule" in result.stderr, result.stderr
    assert not os.path.isdir(str(repo / "project_memory" / "staging" / TASK))

# ---------------- AC-1 / FR-0033: the three drafts -------------------------------------------
LADDER = ('reminders:\n'
          '- level: 1\n  title: "Zahlungserinnerung"\n  days_after_due: 0\n  fee: 0.00\n'
          '- level: 2\n  title: "1. Mahnung"\n  days_after_due: 14\n  fee: 0.00\n'
          '- level: 3\n  title: "2. Mahnung"\n  days_after_due: 28\n  fee: 0.00\n')


# The business's OWN letter terms. The kit ships every one of them empty -- the lists for FR-0028
# and the SCALARS for `BUG-0259`, on the same argument: a value a customer reads is one the user
# chose. A pilot therefore declares them through the DOCUMENT, which is what a real project does;
# the script has no default and refuses with the route until they are there.
DECLARED_TERMS = (("address:", 'address: "Sie"'),
                  ("closing:", 'closing: "Mit freundlichen Grüßen"'),
                  ("valid_days:", "valid_days: 14"))


def declare_the_terms(repo):
    """The three scalar terms of `correspondence.yaml`, as a business would record them."""
    document = repo / "project_memory" / "correspondence.yaml"
    text = read(document)
    # IDEMPOTENT, because two callers reach it (a test directly, and `declare_the_ladder`): a
    # second blind replace produced `address: "Sie" "Sie"` and a YAML parse error in the script
    # under test, which reads as the script crashing rather than as the fixture doing it.
    for empty, declared in DECLARED_TERMS:
        if declared in text:
            continue
        assert empty in text, "%s is not in the shipped template any more" % empty
        text = text.replace(empty, declared, 1)
    write(document, text)


def declare_the_ladder(repo):
    """The business's own dunning steps AND its letter terms -- the kit ships none (FR-0028)."""
    document = repo / "project_memory" / "correspondence.yaml"
    text = read(document)
    assert "reminders: []\n" in text
    write(document, text.replace("reminders: []\n", LADDER, 1))
    declare_the_terms(repo)


def outbox_drafts(repo):
    directory = repo / "outbox" / "office-manager"
    return sorted(os.listdir(str(directory))) if os.path.isdir(str(directory)) else []


def three_drafts(tmp_path):
    repo = pilot_project(tmp_path)
    write(repo / "ledger" / "2026.csv", LEDGER_HEADER + income_row(1, 1) + income_row(
        2, 2, paid="", gross="1190.00", net="1000.00"))
    write(repo / "project_memory" / "content_guidelines.yaml",
          'tone: "sachlich, freundlich, ohne Superlative"\nlanguage: "de"\n')
    declare_the_ladder(repo)
    write(repo / "body.md", "wie besprochen erhalten Sie die Unterlagen zu Ihrer Bestellung 4711.\n"
                            "Die Lieferung verlässt unser Lager am Montag.")
    today = datetime.date(2026, 9, 5)
    runs = [script(repo, "letter_draft.py", "offer", "--to", "Kaeufer GmbH",
                   "--vat-rate", "19",
                   "--line", "Beratung (Tag);2;450.00", "--line", "Anfahrt;1;40.00"),
            script(repo, "letter_draft.py", "reminder", "--entry", "L2026-0002",
                   "--today", today.isoformat()),
            script(repo, "letter_draft.py", "letter", "--to", "Kaeufer GmbH",
                   "--subject", "Ihre Bestellung 4711", "--body-file", "body.md")]
    for run in runs:
        assert run.returncode == 0, run.stdout + run.stderr
    return repo, [read(repo / "outbox" / "office-manager" / name) for name in outbox_drafts(repo)]


def test_the_three_drafts_are_written_from_ledger_and_master_data_into_the_outbox(tmp_path):
    """AC-1's producing half: an offer, a reminder and a letter, each from the recorded data
    (sender from the profile, VAT from its tax status, the reminder's figures and level from the
    ledger row and the payment term, the terms from `correspondence.yaml`), each into `outbox/`,
    each opening with the line that says what has to happen before it may leave."""
    repo, drafts = three_drafts(tmp_path)
    names = outbox_drafts(repo)
    assert [name.rsplit("_", 1)[1] for name in names] == ["angebot.md", "brief.md",
                                                          "mahnung-2.md"], names
    offer, letter, reminder = drafts
    for draft in drafts:
        assert draft.startswith("<!-- ENTWURF") and "/humanizer" in draft and "NUTZER" in draft
        assert "Muster Handel e.K." in draft and "Musterstr. 1, 12345 Musterstadt" in draft
        assert draft.rstrip().endswith("Mit freundlichen Grüßen\nMuster Handel e.K.")
    assert "| 1 | Beratung (Tag) | 2 | 450,00 EUR | 900,00 EUR |" in offer
    assert "Summe netto: 940,00 EUR" in offer and "19 % Umsatzsteuer: 178,60 EUR" in offer
    assert "**Gesamtbetrag: 1.118,60 EUR**" in offer
    assert "**1. Mahnung: Rechnung RE-2026-0002 vom 02.08.2026**" in reminder
    assert "über 1.190,00 EUR" in reminder and "am 16.08.2026 abgelaufen" in reminder
    assert "Das sind heute 20 Tage." in reminder and "Mahngebühr" not in reminder
    assert "Bestellung 4711" in letter and "verlässt unser Lager am Montag" in letter


def sentences_of(draft):
    """The prose sentences of a draft: no header comment, no table row, no address block, no
    closing formula -- the part a person reads as text."""
    body = draft.split("-->", 1)[1]
    body = body.split("Mit freundlichen Grüßen", 1)[0]
    lines = [line.strip() for line in body.splitlines()
             if line.strip() and not line.startswith("|") and not line.startswith("**")]
    prose = " ".join(line for line in lines[3:] if not re.match(r"^\d\d\.\d\d\.\d{4}$", line))
    return [one.strip() for one in re.split(r"(?<=[.!?])\s+", prose) if one.strip()]


def test_the_three_drafts_pass_the_countable_half_of_the_humanizer_bar(tmp_path):
    """AC-1: 'the texts pass the humanizer bar' -- measured on the half of it that COUNTS.

    `skills/humanizer/SKILL.md` is a prose skill by design (DEC-0056) and no script scores it;
    what it states as counts is measured here on the three rendered drafts: sentence lengths that
    vary (property 1: a short sentence exists and the spread is at least five words), no unspaced
    em dash in German text (G4), no "nicht nur … sondern auch" reflex (5b/G2), no closing summary
    or generic closer (6/G6), one form of address throughout (G7). What is NOT measured -- whether
    a customer reads the letter as written by a person -- stays the reviewer's duty, and the skill
    text says so. Red when an em dash or a summary paragraph is written into a template.
    """
    _repo, drafts = three_drafts(tmp_path)
    for draft in drafts:
        text = draft.split("-->", 1)[1]
        assert "—" not in text, "an unspaced em dash in German text (G4)"
        assert not ("nicht nur" in text and "sondern auch" in text), "the not-X-but-Y reflex"
        assert not re.search(r"(?m)^(Zusammenfassend|Abschließend|Insgesamt)", text), "a summary"
        assert not re.search(r"\b(du|dein|deine|dir|dich)\b", text), "a second form of address"
        lengths = [len(one.split()) for one in sentences_of(draft)]
        assert len(lengths) >= 2, sentences_of(draft)
        assert min(lengths) <= 8 and max(lengths) - min(lengths) >= 5, lengths


def test_a_reminder_the_data_does_not_carry_is_refused(tmp_path):
    """The kit invents no ladder, no term, no fee and no sender: each missing input is a refusal
    that names it AND the route that fills it, and nothing lands in the outbox.

    The ladder is the one the kit could most easily have guessed, and shipping it guessed is what
    `tools/test_kit_neutrality.py::test_every_office_state_template_ships_its_lists_empty` forbids:
    after how many days a business writes is its own decision, not the form's. So the SHIPPED
    state refuses, and the refusal carries `apply-proposal` -- without that half it is the
    BUG-0041 dead end (a route the prose promises and the gates forbid).
    """
    repo = pilot_project(tmp_path)
    write(repo / "ledger" / "2026.csv", LEDGER_HEADER + income_row(1, 1)
          + income_row(2, 2, paid="", gross="1190.00", net="1000.00"))
    # ...with the three SCALAR terms declared, because they are refused first now and this row is
    # about the LADDER. The kit ships them empty for the same reason it ships the ladder empty
    # (`BUG-0259`), and the refusal order is not this test's subject.
    declare_the_terms(repo)
    no_ladder = script(repo, "letter_draft.py", "reminder", "--entry", "L2026-0002")
    assert no_ladder.returncode == 1, no_ladder.stdout + no_ladder.stderr
    assert "carries no `reminders` ladder" in no_ladder.stderr, no_ladder.stderr
    assert "apply-proposal" in no_ladder.stderr, no_ladder.stderr
    declare_the_ladder(repo)
    paid = script(repo, "letter_draft.py", "reminder", "--entry", "L2026-0001")
    assert paid.returncode == 1 and "is paid" in paid.stderr
    write(repo / "project_memory" / "business_profile.yaml",
          PILOT_PROFILE.replace("  payment_terms_days: 14\n", "  payment_terms_days: null\n"))
    no_term = script(repo, "letter_draft.py", "reminder", "--entry", "L2026-0002")
    assert no_term.returncode == 1 and "invents no payment term" in no_term.stderr
    write(repo / "project_memory" / "business_profile.yaml",
          PILOT_PROFILE.replace('  name: "Muster Handel e.K."\n', '  name: ""\n'))
    no_sender = script(repo, "letter_draft.py", "offer", "--to", "X", "--line", "A;1;1")
    assert no_sender.returncode == 1 and "no `business.name`" in no_sender.stderr
    assert outbox_drafts(repo) == []



# ---------------- AC-1, round-2 rework: nothing invented, nothing crashing ----------------------
def a_pilot_with_an_open_invoice(tmp_path):
    """A pilot whose ledger carries one paid and one open outgoing invoice, and a declared ladder."""
    repo = pilot_project(tmp_path)
    write(repo / "ledger" / "2026.csv", LEDGER_HEADER + income_row(1, 1)
          + income_row(2, 2, paid="", gross="1190.00", net="1000.00"))
    declare_the_ladder(repo)
    return repo


def _term(repo, old, new):
    _plant(repo / "project_memory" / "correspondence.yaml", old, new)


@pytest.mark.parametrize("planted, plant, argv, names", [
    ("a VAT rate that is not a number", None,
     ["offer", "--to", "Kunde", "--line", "A;1;100.00", "--vat-rate", "neunzehn"],
     "--vat-rate is 'neunzehn'"),
    ("a --today that is not a date", None,
     ["reminder", "--entry", "L2026-0002", "--today", "gestern"], "--today is 'gestern'"),
    ("an offer validity written as a word",
     ("offer:\n  valid_days: 14", "offer:\n  valid_days: vierzehn"),
     ["offer", "--to", "Kunde", "--line", "A;1;100.00"],
     "correspondence.yaml `valid_days` is 'vierzehn'"),
    ("a ladder level written as a word", ("- level: 2\n", "- level: zwei\n"),
     ["reminder", "--entry", "L2026-0002"], "a reminder step's `level` is 'zwei'"),
    ("a ladder step whose days are a word",
     ("  days_after_due: 14\n", "  days_after_due: vierzehn\n"),
     ["reminder", "--entry", "L2026-0002"], "`days_after_due` is 'vierzehn'"),
    # V3-1 of verify round 3: `a_count` says "A whole, non-negative number" and only the
    # non-negative half had a case -- the verifier's mutation removing the WHOLE check left all 70
    # tests green while the refusal worked. A count is what a ladder is sorted and picked by and
    # what a validity is counted in; half a number is neither.
    ("a ladder level that is not a whole number", ("- level: 2\n", "- level: 1.5\n"),
     ["reminder", "--entry", "L2026-0002"],
     "a reminder step's `level` is '1.5', and this script needs a whole number"),
    ("an offer validity that is not a whole number",
     ("offer:\n  valid_days: 14", "offer:\n  valid_days: 2.5"),
     ["offer", "--to", "Kunde", "--line", "A;1;100.00", "--vat-rate", "19"],
     "correspondence.yaml `valid_days` is '2.5', and this script needs a whole number"),
], ids=lambda value: value if isinstance(value, str) and " " in value else None)
def test_a_value_letter_draft_cannot_read_is_refused_and_never_crashes(tmp_path, planted, plant,
                                                                       argv, names):
    """Verifier round 1, B6 -- the D1/D2 class, measured in the file this stream wrote itself.

    Five values a person writes went into `int()`, `Decimal()` and `date.fromisoformat()` without
    a reader; three of them come out of `correspondence.yaml`, the document the kit tells a
    NON-DEVELOPER to fill through `apply-proposal`. Each ended in a Python traceback where the
    module docstring promises "Exit 1 = refused (reason on stderr), nothing written".
    """
    repo = a_pilot_with_an_open_invoice(tmp_path)
    if plant:
        _term(repo, *plant)
    result = script(repo, "letter_draft.py", *argv)
    assert result.returncode == 1, (planted, result.stdout + result.stderr)
    assert "Traceback" not in result.stderr, (planted, result.stderr)
    assert names in result.stderr, (planted, result.stderr)
    assert outbox_drafts(repo) == [], planted


def test_a_ledger_date_the_reminder_cannot_read_is_refused(tmp_path):
    """The fifth of B6's five, and the one that comes from neither the command line nor the terms:
    a ledger row written by hand (which §2.3 of the constitution allows) with a German date."""
    repo = a_pilot_with_an_open_invoice(tmp_path)
    write(repo / "ledger" / "2026.csv",
          read(repo / "ledger" / "2026.csv").replace("2026-08-02,", "02.08.2026,", 1))
    result = script(repo, "letter_draft.py", "reminder", "--entry", "L2026-0002")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert "doc_date in the ledger is '02.08.2026'" in result.stderr, result.stderr


@pytest.mark.parametrize("planted, plant, argv, names", [
    ("no form of address", ('address: "Sie"', "address:"),
     ["offer", "--to", "Kunde", "--line", "A;1;100.00"], "carries no `address`"),
    ("no closing line", ('closing: "Mit freundlichen Grüßen"', "closing:"),
     ["offer", "--to", "Kunde", "--line", "A;1;100.00"], "carries no `closing`"),
    ("no offer validity", ("valid_days: 14", "valid_days:"),
     ["offer", "--to", "Kunde", "--line", "A;1;100.00"], "carries no `valid_days`"),
    ("no title on the ladder step", ('  title: "1. Mahnung"\n', "  title:\n"),
     ["reminder", "--entry", "L2026-0002"], "carries no `title`"),
], ids=lambda value: value if isinstance(value, str) and " " in value else None)
def test_a_term_the_business_never_recorded_is_refused_with_its_route(tmp_path, planted, plant,
                                                                      argv, names):
    """Verifier round 1, B7 -- three shipped texts said the script invents no term, and it invented
    four.

    Measured with the terms removed: the draft went out with 14 days, `Sie`, 19 % and
    "Mit freundlichen Grüßen", every one of them a value the KIT chose, standing in a letter to a
    customer. The fallbacks are gone; each refusal now names the term AND the route that fills it,
    because a refusal without the route is BUG-0041's dead end for a non-developer.
    """
    repo = a_pilot_with_an_open_invoice(tmp_path)
    _term(repo, *plant)
    result = script(repo, "letter_draft.py", *argv)
    assert result.returncode == 1, (planted, result.stdout + result.stderr)
    assert names in result.stderr, (planted, result.stderr)
    assert "apply-proposal" in result.stderr, (planted, result.stderr)
    assert outbox_drafts(repo) == [], planted


def test_an_offer_states_the_vat_rate_the_business_gave_it_and_no_reminder_goes_to_nobody(tmp_path):
    """The other two halves of B7 and N6.

    The VAT rate of an offer had an argparse `default="19"`: a business on another rate got 19 % in
    a customer's letter without being asked. Round 2 of the review measured that the default was
    still there while three texts said it was gone, and that the case here passed `--vat-rate ""`
    and therefore never walked the branch argparse takes when the flag is ABSENT -- so both are run
    now, and the default is `""`. And a ledger row with an empty `counterparty` produced
    a reminder addressed to nobody (file `…_unbekannt_mahnung-2.md`, empty recipient line) while a
    missing SENDER was refused -- one half of the same question answered twice.
    """
    repo = a_pilot_with_an_open_invoice(tmp_path)
    for argv in (["offer", "--to", "Kunde", "--line", "A;1;100.00"],
                 ["offer", "--to", "Kunde", "--line", "A;1;100.00", "--vat-rate", ""]):
        no_rate = script(repo, "letter_draft.py", *argv)
        assert no_rate.returncode == 1, (argv, no_rate.stdout + no_rate.stderr)
        assert "invents none" in no_rate.stderr, (argv, no_rate.stderr)
        assert "--vat-rate 19" in no_rate.stderr, (argv, no_rate.stderr)

    write(repo / "ledger" / "2026.csv",
          read(repo / "ledger" / "2026.csv").replace(",income,invoice,Kaeufer GmbH,RE-2026-0002,",
                                                     ",income,invoice,,RE-2026-0002,", 1))
    nobody = script(repo, "letter_draft.py", "reminder", "--entry", "L2026-0002")
    assert nobody.returncode == 1, nobody.stdout + nobody.stderr
    assert "names no counterparty" in nobody.stderr, nobody.stderr
    assert outbox_drafts(repo) == []


@pytest.mark.parametrize("planted, rate, says", [
    ("not a number at all", "neunzehn", "--vat-rate is 'neunzehn'"),
    ("a quiet NaN", "NaN", "which is not a finite number"),
    ("an infinity", "Infinity", "which is not a finite number"),
    ("a negative rate", "-19", "writes no negative --vat-rate"),
], ids=lambda value: value if isinstance(value, str) and " " in value else None)
def test_a_number_letter_draft_cannot_write_into_a_letter_is_refused(tmp_path, planted, rate,
                                                                     says):
    """R2 of verify round 2: the reader that replaced the unguarded reads was WEAKER than the one it
    stood beside.

    `money()` had asked `is_finite()` and about the sign since it was written; `a_value`, which read
    `--vat-rate`, asked neither -- and `Decimal("NaN")` and `Decimal("Infinity")` are valid Decimals.
    Measured 2026-09-06: `NaN` came back out of `eur()` as a `ValueError` traceback, `Infinity` as a
    `decimal.InvalidOperation`, and `-19` was ACCEPTED (rc 0) with "zuzueglich -19 % Umsatzsteuer"
    and a total of 81,00 EUR on a 100,00 EUR offer. Both of those are the classes this script exists
    to refuse, arriving through the newer reader.
    """
    repo = a_pilot_with_an_open_invoice(tmp_path)
    result = script(repo, "letter_draft.py", "offer", "--to", "Kunde", "--line", "A;1;100.00",
                    "--vat-rate", rate)
    assert result.returncode == 1, (planted, result.stdout + result.stderr)
    assert "Traceback" not in result.stderr, (planted, result.stderr)
    assert says in result.stderr, (planted, result.stderr)
    assert outbox_drafts(repo) == [], planted


def test_a_rate_a_person_wrote_in_exponent_form_reads_as_a_number_in_the_letter(tmp_path):
    """R7: `1e2` is a rate somebody can type, and `zuzueglich 1E+2 % Umsatzsteuer` is not a sentence
    a customer can read. Measured 2026-09-06 before `plain()`; the arithmetic was right and only the
    rendering was unreadable, so this is a rendering rule and not a refusal."""
    repo = a_pilot_with_an_open_invoice(tmp_path)
    written = script(repo, "letter_draft.py", "offer", "--to", "Kunde", "--line", "A;1;100.00",
                     "--vat-rate", "1e2")
    assert written.returncode == 0, written.stdout + written.stderr
    draft = read(repo / "outbox" / "office-manager" / outbox_drafts(repo)[0])
    assert "zuzüglich 100 % Umsatzsteuer: 100,00 EUR" in draft, draft
    assert "E+" not in draft, draft

    # V3-2: and a rate that is NOT whole is set the way the money beside it is set. A letter with
    # `zuzüglich 19.5 % Umsatzsteuer: 19,50 EUR` puts two conventions in one sentence.
    fractional = script(repo, "letter_draft.py", "offer", "--to", "Kunde 2",
                        "--line", "A;1;100.00", "--vat-rate", "19.5")
    assert fractional.returncode == 0, fractional.stdout + fractional.stderr
    # BY NAME, not by position: `outbox_drafts` sorts, and `Kunde-2` sorts before `Kunde`.
    named = [one for one in outbox_drafts(repo) if "Kunde-2" in one]
    assert len(named) == 1, outbox_drafts(repo)
    second = read(repo / "outbox" / "office-manager" / named[0])
    assert "zuzüglich 19,5 % Umsatzsteuer: 19,50 EUR" in second, second
    assert "19.5" not in second, second

def test_the_correspondence_terms_are_a_kit_document_the_kernel_writes(tmp_path):
    sys.path.insert(0, TEAM_KITS)
    from kernel import documents, layout
    repo = hooks._draft_project(tmp_path)
    root = str(repo / "project_memory")
    assert documents.accepts(root, "correspondence.yaml")
    routes = {entry["command"] for entry in layout.partial_writers("correspondence.yaml", root)}
    assert {documents.COMMAND, documents.REVISION_COMMAND} <= routes, routes


# THE SERIES WITH NO HISTORY, and the number the series cannot be ordered by. Both are the same
# defect class -- a figure the intake reads without asking whether it IS one -- and both were
# measured on this tree before the fix, as a Python traceback where the module docstring promises
# "exit 2 = REFUSED, with the rule or the figures named".
NO_HISTORY_RANGES = (
    "number_ranges:\n"
    "  - key: shop_b\n"
    '    business: "Muster Handel e.K."\n'
    '    pattern: "MP-(?P<number>%s)"\n'
    "    issued_by: app\n"
    "    document_type: sales_invoice\n"
    "    category: sales_taxable\n"
    "    first: %s\n")


@pytest.mark.parametrize("planted, capture, first, number, exit_code, names", [
    ("below the first of an empty series", "[0-9]+", "100", "MP-42", 2,
     ["number 42", "none issued yet", "declares 100 as its first"]),
    ("a number the series cannot be ordered by", "[A-Za-z0-9]+", "1", "MP-A1", 2,
     ["the part the range counts by", "'A1'"]),
    ("a `first` the range declares as a word", "[0-9]+", "eins", "MP-7", 1,
     ["the `first` of range shop_b", "'eins'"]),
], ids=lambda value: value if isinstance(value, str) and " " in value else None)
def test_a_series_the_intake_cannot_order_is_refused_and_never_crashes(tmp_path, planted, capture,
                                                                       first, number, exit_code,
                                                                       names):
    """AC-2's refusing half where the series carries NO history -- the branch every other case
    walks around.

    Measured 2026-09-05 on this tree before the fix: `continuity` read `max(issued)` in the
    below-the-stand refusal without asking whether anything was issued, and `int()` the number
    captures without asking whether they were numbers. All three cases ended in a traceback and
    exit 1, i.e. "not judgeable", while the document was judged and refusable. Red without the
    fix: no `[intake] REFUSED` line at all, and `Traceback` on stderr.
    """
    repo = pilot_project(tmp_path)
    document = repo / "project_memory" / "master_data.yaml"
    write(document, read(document).replace("number_ranges: []\n",
                                           NO_HISTORY_RANGES % (capture, first), 1))
    result = intake(repo, drop(repo, "drop.xml", cii(invoice_no=number)), "--task", TASK)
    assert result.returncode == exit_code, (planted, result.stdout + result.stderr)
    assert "Traceback" not in result.stderr, (planted, result.stderr)
    for name in names:
        assert name in result.stderr, (planted, name, result.stderr)


NL = chr(10)  # a newline, spelled rather than written into the CSV rows below


def test_one_voucher_booked_twice_without_an_invoice_number_is_refused(tmp_path):
    """BUG-0182: two rows that differ in nothing but their id are one voucher booked twice.

    The duplicate rule of `validate_cross` needed `invoice_no`, which a receipt, a fee or a bank
    charge often does not carry -- and `gate_second_booking` pairs its readings on `source`, so
    BOTH rows were covered by ONE reading pair. Every layer therefore let the double booking
    through, and the quarter reported the amount twice.

    THE COUNTER-END, because a rule that simply refused equal-looking rows would be useless to a
    business with two real positions on one voucher: the same two rows told apart in `note` are
    accepted, which is the route the finding names.
    """
    repo = pilot_project(tmp_path)
    row = ("L2026-%04d,2026-02-01,2026-02-01,expense,fee,Tankstelle,,50.00,19.00,59.50,"
           "standard,fahrzeug,archive/t.pdf,,%s" + NL)
    write(repo / "ledger" / "2026.csv", LEDGER_HEADER + (row % (1, "")) + (row % (2, "")))
    done = script(repo, "ledger_add.py", "--validate", "ledger/2026.csv")
    assert done.returncode != 0, done.stdout + done.stderr
    assert "differs only in its id" in (done.stdout + done.stderr), done.stdout + done.stderr

    write(repo / "ledger" / "2026.csv",
          LEDGER_HEADER + (row % (1, "Hinfahrt")) + (row % (2, "Rueckfahrt")))
    told_apart = script(repo, "ledger_add.py", "--validate", "ledger/2026.csv")
    assert told_apart.returncode == 0, told_apart.stdout + told_apart.stderr

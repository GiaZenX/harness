#!/usr/bin/env python3
"""The office kit's finance dashboard, measured against the ledger it renders (FR-0032, TSK-0109).

EVERY TEST HERE RUNS THE SHIPPED FILES. The generator is started as a process inside a project
built from the kit's own `templates/repo/` tree, the EÜR report it is compared against is the kit's
own `scripts/euer_report.py` run as a process, the write-scope decision comes from the kit's own
hook as a process, and the browser tests load the page a run of the generator produced. Nothing
below reads a source file for a sentence.

WHY THE FIXTURES ARE FILES AND NOT A GENERATOR. `tools/fixtures/finance/<state>/` holds frozen
ledgers, each one a state somebody's books are really in: `regular` (two years, 318 rows, open and
overdue items, a credit note and a reversal, § 19 profile), `empty` (day one, no ledger at all),
`alarm` (a row whose net exceeds its gross -- the BUG-0072 shape -- plus a previous year over the
§ 19 UStG limit), `crossyear` (Regelbesteuerung: an open 2025 invoice reversed by a row in
`2026.csv`, a second 2025 invoice that stays open, an OSS row and a credit note) and `founding`
(one ledger year, no previous one to compare against). A fixture that were regenerated per run
would make the parity numbers below depend on a random seed, and the sums they pin are the whole
point.
"""
import ast
import csv
import datetime
import hashlib
import html
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFFICE_TEMPLATE = os.path.join(ROOT, "team-kits", "office-team", "templates", "repo")
OFFICE_HOOKS = os.path.join(ROOT, "team-kits", "office-team", "hooks")
OFFICE_SETTINGS = os.path.join(ROOT, "team-kits", "office-team", "settings", "settings.json")
KERNEL = os.path.join(ROOT, "team-kits", "kernel")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "finance")
GENERATOR_REL = os.path.join("tools", "finance_dashboard.py")
OUTPUT_REL = os.path.join("dashboards", "finanzen.html")

# The day the browser tests pretend it is. Frozen because "overdue" is the one figure on the page
# that depends on a clock, and a test that asked the real one would change its answer every night.
FROZEN_TODAY = datetime.date(2026, 9, 2)

# Every state `tools/fixtures/finance/` carries, read off the directory: a
# fixture that ships is a fixture the whole-corpus checks below see.
FIXTURE_STATES = tuple(sorted(name for name in os.listdir(FIXTURES)
                              if os.path.isdir(os.path.join(FIXTURES, name))))


# ---------------------------------------------------------------- a project the kit would produce

def build_project(directory, state=None, ledgers=None, profile=None, master=None):
    """An office project as the scaffold leaves it, with one fixture's data in it.

    `scripts/`, `tools/` and `dashboards/` are COPIED FROM THE KIT, so what runs below is what
    ships. `state` names a fixture directory; `ledgers` / `profile` / `master` override its parts
    for the tests that need a ledger of their own.
    """
    root = str(directory)
    os.makedirs(os.path.join(root, "project_memory"), exist_ok=True)
    for name in ("scripts", "tools", "dashboards"):
        shutil.copytree(os.path.join(OFFICE_TEMPLATE, name), os.path.join(root, name),
                        ignore=shutil.ignore_patterns("__pycache__"))
    if state:
        source = os.path.join(FIXTURES, state)
        if os.path.isdir(os.path.join(source, "ledger")):
            shutil.copytree(os.path.join(source, "ledger"), os.path.join(root, "ledger"))
        for name in ("master_data.yaml", "business_profile.yaml"):
            shutil.copy(os.path.join(source, name), os.path.join(root, "project_memory", name))
    for name, rows in (ledgers or {}).items():
        write_ledger(os.path.join(root, "ledger", "%s.csv" % name), rows)
    if profile is not None:
        _write_yaml(os.path.join(root, "project_memory", "business_profile.yaml"), profile)
    if master is not None:
        _write_yaml(os.path.join(root, "project_memory", "master_data.yaml"), master)
    return root


def _write_yaml(path, data):
    yaml = pytest.importorskip("yaml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def _columns():
    """The ledger's column order, from the script that owns it -- never a second list here."""
    sys.path.insert(0, os.path.join(OFFICE_TEMPLATE, "scripts"))
    try:
        import ledger_add
        return list(ledger_add.COLUMNS)
    finally:
        sys.path.pop(0)


def write_ledger(path, rows):
    """Rows (dicts of the kit's columns, missing keys empty) into a ledger CSV."""
    columns = _columns()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def run_generator(root, *args, cwd=None):
    return subprocess.run([sys.executable, "-B", os.path.join(root, GENERATOR_REL), *args],
                          capture_output=True, text=True, cwd=cwd or root, timeout=300)


def generated_page(root):
    with open(os.path.join(root, OUTPUT_REL), encoding="utf-8") as handle:
        return handle.read()


def page_url(root):
    return "file:///" + os.path.join(root, OUTPUT_REL).replace("\\", "/")


# ---------------------------------------------------------------- a very small DOM over the page

class Node(object):
    __slots__ = ("tag", "attrs", "children", "parent", "_text")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children, self._text = [], []

    @property
    def classes(self):
        return set((self.attrs.get("class") or "").split())

    def text(self):
        out = list(self._text)
        for child in self.children:
            out.append(child.text())
        return " ".join(part for part in (piece.strip() for piece in out) if part)

    def find_all(self, tag=None, cls=None, attr=None):
        found = []
        for child in self.children:
            if ((tag is None or child.tag == tag)
                    and (cls is None or cls in child.classes)
                    and (attr is None or attr in child.attrs)):
                found.append(child)
            found.extend(child.find_all(tag=tag, cls=cls, attr=attr))
        return found

    def by_id(self, wanted):
        for node in self.find_all(attr="id"):
            if node.attrs.get("id") == wanted:
                return node
        return None


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "param", "source", "track", "wbr"}


class _Parser(html.parser.HTMLParser):
    """Enough of an HTML reader to ASK THE DOCUMENT a question instead of grepping its bytes.

    House rule: a check reads the part that runs. For everything a browser is not needed for, the
    part that runs is the element tree the generator emitted -- so tags, attributes and text are
    parsed, and no assertion below matches a raw string against the file.
    """

    def __init__(self):
        html.parser.HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#document", {}, None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {key: (value or "") for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {key: (value or "") for key, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1]._text.append(data)


def dom(text):
    parser = _Parser()
    parser.feed(text)
    return parser.root


# ---------------------------------------------------------------- a second reading of the ledger

def ledger_rows(root):
    """Every ledger row with the status the page must give it -- computed HERE, not imported.

    The sign convention and the correcting doc types come from the kit's own `euer_report`, which
    is where they live; the status cascade is spelled out again so a defect in the generator's copy
    of it cannot make this file agree with it.
    """
    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        import euer_report
    finally:
        sys.path.pop(0)
    rows = []
    ledger_dir = os.path.join(root, "ledger")
    for name in sorted(os.listdir(ledger_dir) if os.path.isdir(ledger_dir) else []):
        if not re.match(r"^[0-9]{4}\.csv$", name):
            continue
        with open(os.path.join(ledger_dir, name), encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    cancelled = {r["reverses"] for r in rows if r["doc_type"] == "reversal" and r["reverses"]}
    for row in rows:
        row["cents"] = int(round(float(row["gross"]) * 100)) * euer_report.sign_of(row)
        if row["id"] in cancelled:
            row["status"] = "storniert"
        elif row["doc_type"] in euer_report.NEGATIVE_DOC_TYPES:
            row["status"] = "korrektur"
        elif row["payment_date"]:
            row["status"] = "bezahlt"
        else:
            row["status"] = "offen"
    return rows


def _quarter_bounds(year, quarter):
    """The calendar's answer, spelled here rather than imported: this file is the third reading."""
    start = datetime.date(year, 3 * (quarter - 1) + 1, 1)
    end = (datetime.date(year, 12, 31) if quarter == 4
           else datetime.date(year, 3 * quarter + 1, 1) - datetime.timedelta(days=1))
    return start.isoformat(), end.isoformat()


def csv_quarter(root, year, quarter):
    """The figures of one quarter, aggregated HERE out of `ledger/<year>.csv` -- a third reading.

    Neither the generator nor the report is asked. The rows are read with `csv`, the quarter is the
    calendar's, and WHICH ROWS CARRY VAT is spelled out again on purpose: the generator holds it in
    a constant and the report decides it inline, so this literal is the independent third spelling
    that makes a drift on either side visible rather than agreed.

    The sign convention is the one exception and comes from `euer_report`, because that is where it
    lives -- restating it here would be the copy its own header records the cost of.
    """
    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        sys.modules.pop("euer_report", None)
        import euer_report
        sign_of = euer_report.sign_of
    finally:
        sys.path.pop(0)
        sys.modules.pop("euer_report", None)
    start, end = _quarter_bounds(int(year), quarter)
    path = os.path.join(root, "ledger", "%s.csv" % year)
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    figures = {"income": {"gross": 0, "vat": 0, "taxed": 0},
               "expense": {"gross": 0, "vat": 0, "taxed": 0}}
    opened = 0
    cancelled = {r["reverses"] for r in rows if r["doc_type"] == "reversal" and r["reverses"]}
    for row in rows:
        sign = sign_of(row)
        paid = row["payment_date"]
        if paid and start <= paid <= end:
            side = figures[row["direction"]]
            side["gross"] += int(round(float(row["gross"]) * 100)) * sign
            if row["vat_treatment"] == "standard":
                side["taxed"] += 1
                side["vat"] += (int(round(float(row["gross"]) * 100))
                                - int(round(float(row["net"]) * 100))) * sign
        elif not paid and row["doc_date"] <= end:
            if row["doc_type"] not in euer_report.NEGATIVE_DOC_TYPES and row["id"] not in cancelled:
                opened += 1
    for side in figures.values():
        side["net"] = side["gross"] - side["vat"]
    figures["surplus"] = {name: figures["income"][name] - figures["expense"][name]
                          for name in ("gross", "net", "vat")}
    figures["surplus"]["taxed"] = figures["income"]["taxed"] + figures["expense"]["taxed"]
    figures["open"] = opened
    return figures


MISSING = type("Missing", (), {"__repr__": lambda self: "<no tax: block>"})()


def _profile_with(tmp_path, fixture, spelling):
    """The fixture's own profile, with `tax.kleinunternehmer` written a different way -- or None.

    THE SPELLINGS ARE THE POINT, and they are what a real profile carries: `"true"` in quotes is
    what a hand-edited YAML gives you the moment somebody quotes the value, a missing `tax:` block
    is what an interview that never asked leaves behind, and `null` is what the office kit SHIPS
    (`templates/project_memory/business_profile.yaml`). None of the three is a yes and none is a
    no, so none of them may buy a VAT figure.
    """
    if spelling is None:
        return None
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(FIXTURES, fixture, "business_profile.yaml"), encoding="utf-8") as handle:
        profile = yaml.safe_load(handle)
    if spelling == "missing":
        profile.pop("tax", None)
        return profile
    profile.setdefault("tax", {})["kleinunternehmer"] = {"true": "true", "null": None}[spelling]
    return profile


def figure_of(node, name):
    """The amount the page carries under `data-figure="<name>"`, or None."""
    for found in node.find_all(attr="data-figure"):
        if found.attrs.get("data-figure") == name:
            return found.text()
    return None


def eur(cents):
    """The German amount the page prints, spelled independently of the generator and of the page.

    A non-breaking space before the euro sign, because that is what neither of the two producers
    may break: they format the same sums from two languages, and until this test existed one of
    them used an ordinary space (measured 2026-09-02).
    """
    sign = "−" if cents < 0 else ""
    euros, rest = divmod(abs(int(cents)), 100)
    return "%s%s,%02d\u00a0€" % (sign, "{:,}".format(euros).replace(",", "."), rest)


# ---------------------------------------------------------------- 1. the arithmetic has one home

@pytest.mark.parametrize("fixture,spelling", [
    ("regular", None), ("crossyear", None),
    ("regular", "true"), ("regular", "missing"), ("regular", "null"),
])
def test_the_dashboard_and_euer_report_agree_on_every_quarter(tmp_path, fixture, spelling):
    """Eight quarters, THREE readings: the page the generator wrote, the report the kit's own
    `euer_report.py` writes for the same ledger, and an aggregation of the CSV done in this file.

    This is the test the whole design rests on -- the generator imports `euer_report.sign_of` and
    `quarter_range` instead of restating them, and a copy would drift exactly here. Goes red when
    the sign convention is restated (a credit note added instead of subtracted), when a reversed
    original is dropped as well as its reversal, and when the open-item count stops being the
    report's: the `crossyear` fixture carries an open 2025 invoice reversed by a row in `2026.csv`
    (routine, `ledger_add.validate_cross` accepts it) plus a second 2025 invoice that stays open,
    so BOTH ends of the year binding in `open_until` are load-bearing here -- dropping it counts
    the 2025 rows into 2026's quarters, keeping the whole-ledger status counts one row fewer than
    the report in 2025 Q4.

    THE THREE VAT LINES are measured on the same three readings, and which shape they take is
    derived from the fixture's own profile rather than assumed: under § 19 the page must show no
    VAT figure and Netto must equal Brutto in BOTH directions, because a Kleinunternehmer deducts
    no Vorsteuer either -- an aggregation that just follows the rows printed a refund of 6.077,56 €
    for the `regular` fixture. The report's own informational sums are compared in every state,
    since the page prints them under the EÜR figures whatever the profile says.
    """
    yaml = pytest.importorskip("yaml")
    root = build_project(tmp_path / ("parity-%s-%s" % (fixture, spelling)), fixture,
                         profile=_profile_with(tmp_path, fixture, spelling))
    assert run_generator(root).returncode == 0
    page = dom(generated_page(root))
    with open(os.path.join(root, "project_memory", "business_profile.yaml"),
              encoding="utf-8") as handle:
        answer = (yaml.safe_load(handle).get("tax") or {}).get("kleinunternehmer")
    # ONLY an explicit `false` buys a VAT figure. The rule is spelled here a second time on
    # purpose: the generator holds its own, and a drift between them is what this pins.
    prints_vat = answer is False
    relief = not prints_vat

    blocks = {}
    for block in page.find_all(cls="euer-block"):
        blocks[(block.attrs["data-year"], block.attrs["data-period"])] = block
    assert blocks, "the page carries no EÜR blocks at all"

    checked = 0
    for year in ("2025", "2026"):
        for quarter in (1, 2, 3, 4):
            report = subprocess.run(
                [sys.executable, "-B", os.path.join(root, "scripts", "euer_report.py"),
                 "--year", year, "--quarter", str(quarter)],
                capture_output=True, text=True, cwd=root, timeout=300)
            assert report.returncode == 0, report.stderr
            with open(os.path.join(root, "reports", "euer_%s_Q%d.md" % (year, quarter)),
                      encoding="utf-8") as handle:
                markdown = handle.read()
            said_income = float(re.search(r"\| Einnahmen \| (-?[\d.]+) EUR", markdown).group(1))
            said_expense = float(re.search(r"\| Ausgaben \| (-?[\d.]+) EUR", markdown).group(1))
            said_vat = re.search(r"standard\): (-?[\d.]+) EUR · Vorsteuer \(Ausgaben, standard\): "
                                 r"(-?[\d.]+) EUR", markdown)
            said_out, said_in = (round(float(said_vat.group(1)) * 100),
                                 round(float(said_vat.group(2)) * 100))
            open_block = markdown.split("## Offene Posten")[1]
            said_open = len([line for line in open_block.splitlines()
                             if line.startswith("| ") and "EUR |" in line])
            third = csv_quarter(root, year, quarter)

            block = blocks[(year, str(quarter))]
            said = (year, quarter)
            assert (round(said_income * 100), round(said_expense * 100), said_out, said_in,
                    said_open) == (third["income"]["gross"], third["expense"]["gross"],
                                   third["income"]["vat"], third["expense"]["vat"],
                                   third["open"]), (
                "the report and this file's own aggregation disagree -- one of the two is wrong "
                "before the page is even looked at: %s" % (said,))

            for key in ("income", "expense", "surplus"):
                assert figure_of(block, key + "-gross") == eur(third[key]["gross"]), (said, key)
            assert block.find_all(attr="data-open-count")[0].text() == str(said_open), said
            assert figure_of(block, "report-vat-out") == eur(third["income"]["vat"]), said
            assert figure_of(block, "report-vat-in") == eur(third["expense"]["vat"]), said
            if prints_vat:
                assert figure_of(block, "report-vat-payload") == eur(third["surplus"]["vat"]), said
            else:
                # NO SECOND PRINT SITE for a figure the state above forbids: the informational
                # block carries the report's two sums and stops there. The page said "es gibt
                # keine Zahllast" four lines under "Zahllast: −6.077,56 €" until 2026-09-02.
                assert figure_of(block, "report-vat-payload") is None, (
                    said, "a Zahllast is printed where the tax state says there is none")

            for key in ("income", "expense", "surplus"):
                shown_net, shown_vat = figure_of(block, key + "-net"), figure_of(block, key + "-vat")
                if relief:
                    assert shown_net == eur(third[key]["gross"]), (
                        "§ 19 UStG: no VAT is charged and none deducted, so Netto is Brutto: %s %s"
                        % (said, key))
                    assert "§ 19" in shown_vat or "nicht belastbar" in shown_vat, (said, key,
                                                                                   shown_vat)
                elif third[key]["taxed"]:
                    assert shown_vat == eur(third[key]["vat"]), (said, key)
                    assert shown_net == eur(third[key]["net"]), (said, key)
                else:
                    # A period without a single taxed row gets the SENTENCE, not "0,00 EUR" --
                    # a zero there reads as "nothing owed", which is a different claim.
                    assert "keine USt" in shown_vat, (said, key, shown_vat)
                    assert shown_net == eur(third[key]["gross"]), (said, key)
            checked += 1
    assert checked == 8, "the parity was measured over %d quarters, not eight" % checked


# ---------------------------------------------------------------- 2./3. what a run leaves behind

def _tree(root):
    """{relative path: sha256} of every file under `root` -- the ground truth for "wrote what"."""
    seen = {}
    for directory, _subdirs, files in os.walk(root):
        for name in files:
            path = os.path.join(directory, name)
            with open(path, "rb") as handle:
                seen[os.path.relpath(path, root).replace("\\", "/")] = hashlib.sha256(
                    handle.read()).hexdigest()
    return seen


def test_the_generator_writes_exactly_one_file(tmp_path):
    """One run, one new file, nothing else touched -- the dashboard renders state and sets none.

    Everything is compared, not a chosen list of suspects: bytecode caches, a report under
    `reports/`, a lock, a stray temp file from the atomic write and any edit to the ledger or to a
    kit document would all show up as a difference. Goes red the moment the generator writes
    anywhere but `dashboards/finanzen.html`.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "once", "regular")
    before = _tree(root)
    assert run_generator(root).returncode == 0
    after = _tree(root)

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
    assert added == ["dashboards/finanzen.html"], added
    assert not removed and not changed, (removed, changed)


def test_the_same_tree_renders_the_same_bytes(tmp_path):
    """Same data, same bytes -- also from another working directory and through `--root`.

    A generated artifact that is not a pure function of its input is one nobody can reproduce or
    diff. Goes red on a rendering clock, an unsorted `listdir`, a set iteration or a path that
    leaks the caller's working directory into the output.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "twice", "regular")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    assert run_generator(root).returncode == 0
    first = generated_page(root)
    assert run_generator(root, "--root", root, cwd=str(elsewhere)).returncode == 0
    assert generated_page(root) == first


# ---------------------------------------------------------------- 4. the command a user is given

def _documented_commands():
    """Every shell line the shipped `dashboards/` guide tells a user to run.

    DERIVED FROM THE SHIPPED FILES, not written down twice: whatever the kit places in
    `templates/repo/dashboards/` is read, and every line whose command word is `python` and whose
    argument is the generator counts. A guide that renamed the command without this test noticing
    would have to stop naming the generator at all -- and the assertion below refuses that too.
    """
    found = []
    guide = os.path.join(OFFICE_TEMPLATE, "dashboards")
    for name in sorted(os.listdir(guide)):
        with open(os.path.join(guide, name), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line.startswith("python ") and "finance_dashboard.py" in line:
                    found.append(line)
    return sorted(set(found))


def _office_shell_hook_commands():
    """Every PreToolUse command line the office kit registers on a shell tool, WHOLE.

    The whole line and not its last word: `_gate.py` is a launcher and takes a LIST of gates, so
    two of the office kit's entries start two gates each. Reading `split()[-1]` measured six of
    eight and left `gate_filing` and `gate_ledger_valid` out of every claim made below.
    """
    with open(OFFICE_SETTINGS, encoding="utf-8") as handle:
        settings = json.load(handle)
    return [hook["command"]
            for entry in settings.get("hooks", {}).get("PreToolUse", [])
            if "bash" in str(entry.get("matcher", "")).lower()
            for hook in entry.get("hooks", [])]


def _gate_names(command):
    """The gate files a registered command line hands to the launcher -- every `.py` word but it."""
    names = [os.path.basename(word.strip('"').replace("\\", "/")) for word in command.split()]
    return [name for name in names if name.endswith(".py") and not name.startswith("_")]


def test_the_documented_command_passes_the_write_scope_gate(tmp_path):
    """The line the folder guide gives the user, through the office kit's real shell gates.

    `generate_dashboard.py` in the development kit had to MOVE OUT of the state directory because
    `gate_write_scope` refuses every write-capable command line that names it, and the documented
    command exited 2 for every agent while it lived there. So the command is measured, not assumed.

    THROUGH THE REGISTERED LINE, not through a gate name picked out of it: each entry is run as
    the provider would run it, launcher and all, so WHICH gates decide is the launcher's answer and
    not this file's. The per-gate loop below is only the attribution -- which one refused -- and
    the set it covers is pinned against the names those command lines carry, because a reader that
    silently shrinks is exactly what made the claim in `docs/POST_V2_WISHLIST.md` (H117) larger
    than the measurement: `split()[-1]` measured six of eight gates.

    BOTH ENDS. The counter-line names the state directory in exactly the way an `--root` argument
    could -- if that stopped being refused, this test would pass for a reason that has nothing to
    do with the documented command.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "gate", "regular")
    shutil.copytree(OFFICE_HOOKS, os.path.join(root, ".claude", "hooks"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(KERNEL, os.path.join(root, ".claude", "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    registered = _office_shell_hook_commands()
    assert registered, "the office settings register no shell hook at all"
    gates = sorted({name for command in registered for name in _gate_names(command)})
    commands = _documented_commands()
    assert commands, "the shipped dashboards guide names no command that runs the generator"

    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["CLAUDE_PROJECT_DIR"] = root

    def payload(command):
        return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": root,
                           "hook_event_name": "PreToolUse"})

    def as_registered(entry, command):
        # Split FIRST, substitute after: the project root may carry a space, and the placeholder
        # travels inside a quoted word.
        words = [word.strip('"').replace("${CLAUDE_PROJECT_DIR}", root) for word in entry.split()]
        return subprocess.run([sys.executable, *words[1:]], input=payload(command),
                              capture_output=True, text=True, env=environment, timeout=180)

    def decide(gate, command):
        return subprocess.run(
            [sys.executable, "-B", os.path.join(root, ".claude", "hooks", gate)],
            input=payload(command), capture_output=True, text=True, env=environment, timeout=120)

    for command in commands:
        for entry in registered:
            through = as_registered(entry, command)
            assert through.returncode == 0, (entry, command, through.stdout + through.stderr)
        # ...and once more one by one, only so a refusal says WHICH gate refused; the claim above
        # rests on the line the provider runs, not on this list.
        for gate in gates:
            seen = decide(gate, command)
            assert seen.returncode == 0, (gate, command, seen.stdout + seen.stderr)
    refused = decide("gate_write_scope.py", commands[0] + " --root project_memory")
    assert refused.returncode == 2, (
        "the state directory stopped being refused, so this test's other end says nothing: %s"
        % (refused.stdout + refused.stderr))


# ---------------------------------------------------------------- 5./6./10. the page in a browser

@pytest.fixture(scope="module")
def browser():
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        try:
            engine = driver.chromium.launch(headless=True)
        except Exception as problem:                      # no browser binary on this machine
            pytest.skip("no Chromium available: %s" % problem)
        yield engine
        engine.close()


def shown(page, selector):
    """The text a node CARRIES, not the text the layout renders.

    `inner_text()` is a rendering answer: measured 2026-09-02, the filtered sum came back as
    `2.736,05 €` because the amount sits in a `white-space: nowrap` span, while the
    script had written an ordinary space. The subject here is the figure the page computed, so the
    DOM's own text is what is read.
    """
    return (page.locator(selector).first.text_content() or "").strip()


def _open(browser, root, clock=None):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    if clock is not None:
        page.clock.install(time=datetime.datetime(clock.year, clock.month, clock.day, 10, 0))
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    page.goto(page_url(root))
    page.wait_for_load_state("load")
    return page, requests


def test_filters_narrow_rows_and_the_sum_follows(browser, tmp_path):
    """Direction + status in the real page, against the same selection read off the CSV here.

    The count and the sum are over EVERY matching row, while the list itself is cut at the first
    hundred -- both halves are asserted, because a sum that quietly followed the visible rows would
    tell an owner she is owed less than she is. Goes red when a filter reads the wrong attribute,
    when the sum follows the page cut, or when "Filter zurücksetzen" leaves rows hidden.

    BOTH PRODUCERS OF THE SAME FIGURE, which is why the file is read before the browser is opened:
    the generator writes `[data-sum]` and the page script overwrites it on load, so in a browser
    only the script's spelling is ever visible. `CURRENCY_GAP` and `fmtEur` format one amount from
    two languages -- measured 2026-09-02, one used an ordinary space and one a non-breaking one,
    and the same sum stood twice on one page. Both are compared against the third spelling in
    `eur()` below, the static half here and the script's half after the filter.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "filter", "regular")
    assert run_generator(root).returncode == 0
    rows = ledger_rows(root)
    wanted = [r for r in rows if r["direction"] == "income" and r["status"] == "offen"]
    assert wanted, "the fixture carries no open receivable, so this test would measure nothing"

    written = dom(generated_page(root)).by_id("view-rechnungen")
    assert written.find_all(attr="data-sum")[0].text() == eur(sum(r["cents"] for r in rows)), (
        "the sum the GENERATOR wrote is spelled differently from this file's third spelling")

    page, _requests = _open(browser, root)
    try:
        page.click('[role="tab"][data-view="rechnungen"]')
        page.select_option('select[data-filter="dir"]', "income")
        page.select_option('select[data-filter="status"]', "offen")
        visible = page.locator(
            'table.ledger.full tbody tr:not(.detail):not([hidden])').count()
        assert visible == len(wanted), (visible, len(wanted))
        assert shown(page, '#view-rechnungen [data-count]') == str(len(wanted))
        assert shown(page, '#view-rechnungen [data-sum]') == eur(
            sum(r["cents"] for r in wanted))

        page.click('form.filters button[type="reset"]')
        page.wait_for_timeout(100)
        assert shown(page, '#view-rechnungen [data-count]') == str(len(rows))
        assert shown(page, '#view-rechnungen [data-sum]') == eur(
            sum(r["cents"] for r in rows))
        after_reset = page.locator(
            'table.ledger.full tbody tr:not(.detail):not([hidden])').count()
        assert after_reset == min(len(rows), 100), (after_reset, len(rows))
    finally:
        page.close()


@pytest.mark.parametrize("fixture", ["regular", "crossyear"])
def test_dunning_candidates_follow_the_frozen_clock(browser, tmp_path, fixture):
    """"Overdue" is computed in the browser, so it is measured with the browser's clock frozen.

    The expected set is derived here from the CSV and the same legal term the generator prints,
    read out of the generator's own constant rather than repeated as a number. Goes red when the
    term changes without the page saying so, when a payable is stamped as a receivable, or when the
    age is counted from the payment date instead of the document date.

    TWO FIXTURES because German counts read wrong at one: `crossyear` has exactly one candidate at
    the frozen date and `regular` has more, and the noun beside the number is written by the page
    script -- sighted as "1 Mahnkandidaten" on 2026-09-02, which no assertion here saw.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / ("dunning-" + fixture), fixture)
    assert run_generator(root).returncode == 0
    term = _generator_constant(root, "PAYMENT_TERM_DAYS")
    overdue = [r for r in ledger_rows(root)
               if r["direction"] == "income" and r["status"] == "offen"
               and (FROZEN_TODAY - datetime.date.fromisoformat(r["doc_date"])).days > term]
    assert overdue, "the fixture carries no dunning candidate at the frozen date"
    if fixture == "crossyear":
        assert len(overdue) == 1, (
            "this fixture is here for the SINGULAR, and it now has %d candidates" % len(overdue))
    else:
        assert len(overdue) > 1, "and this one for the plural"

    page, _requests = _open(browser, root, clock=FROZEN_TODAY)
    try:
        page.click('[role="tab"][data-view="offene-posten"]')
        assert page.locator('table.ledger.open .stamp.alarm').count() == len(overdue)
        assert shown(page, '[data-overdue-count]') == str(len(overdue))
        # The two spellings come off the page itself; only the choice is measured.
        node = page.locator('[data-overdue-word]').first
        one, many = node.get_attribute("data-one"), node.get_attribute("data-many")
        assert one and many and one != many, (one, many)
        assert shown(page, '[data-overdue-word]') == (one if len(overdue) == 1 else many), (
            len(overdue), shown(page, '[data-overdue-word]'))
        page.check('input[data-filter="overdue"]')
        page.wait_for_timeout(100)
        visible = page.locator(
            'table.ledger.open[data-direction="income"] tbody tr:not([hidden])').count()
        assert visible == len(overdue), (visible, len(overdue))
    finally:
        page.close()


def test_the_page_dunning_term_is_the_one_this_business_agreed(tmp_path):
    """BUG-0202: the dunning term was the law's, and the page presented it as this business's rule.

    `§ 286 Abs. 3 BGB` is the FALLBACK and stays one -- what a business really agreed with its
    customers is `receivables.payment_terms_days`, and a business working on 14 days was shown
    dunning candidates by a rule nobody in it had agreed to. Both directions in one test, because
    a generator that always printed the profile's number would be the same defect mirrored.

    WHAT IS READ IS THE GENERATED PAGE: the number the page script computes with
    (`{{payment_term_days}}`) and the sentence under the table have to move TOGETHER, or the page
    dunns by one rule and names another. The undeclared case is asserted against the generator's
    own constant rather than against a repeated 30.
    """
    pytest.importorskip("yaml")
    profile = {"business": {"name": "Nordlicht Handel", "legal_form": "Einzelunternehmen"},
               "tax": {"kleinunternehmer": True, "fiscal_year": "calendar"},
               "receivables": {"payment_terms_days": 14}}

    agreed = build_project(tmp_path / "agreed", "regular", profile=profile)
    assert run_generator(agreed).returncode == 0
    page = generated_page(agreed)
    assert "var TERM_DAYS = 14;" in page, "the page script still counts with the legal default"
    assert "von 14 Tagen ist die in business_profile.yaml vereinbarte Zahlungsfrist" in page, (
        "the footnote does not say whose term this is")
    assert "Forderung älter als 14 Tage" in page, "the filter label kept the legal default"

    undeclared = dict(profile)
    undeclared.pop("receivables")
    legal = build_project(tmp_path / "legal", "regular", profile=undeclared)
    assert run_generator(legal).returncode == 0
    term = _generator_constant(legal, "PAYMENT_TERM_DAYS")
    page = generated_page(legal)
    assert "var TERM_DAYS = %d;" % term in page
    assert "von %d Tagen ist die gesetzliche Verzugsfrist (§ 286 Abs. 3 BGB)" % term in page, (
        "a business that declared nothing must still be told where the term comes from")


def test_a_payment_term_that_is_not_a_positive_number_of_days_is_not_a_term(tmp_path):
    """BUG-0202, the fail-closed half: a declaration nobody can read must not reach the page.

    `null` is what the shipped template carries, and an empty string, a word and a zero are what a
    hand-edited profile produces. Each of them means "not declared" -- a dunning stamp built out of
    one of them would be a rule with nothing behind it.
    """
    pytest.importorskip("yaml")
    sys.path.insert(0, os.path.join(OFFICE_TEMPLATE, "tools"))
    try:
        sys.modules.pop("finance_dashboard", None)
        import finance_dashboard
        legal = (finance_dashboard.PAYMENT_TERM_DAYS, finance_dashboard.LEGAL_TERM_SOURCE)
        for value in (None, "", "  ", "vierzehn", 0, -3, True, [14]):
            assert finance_dashboard.payment_term_days(
                {"receivables": {"payment_terms_days": value}}) == legal, value
        assert finance_dashboard.payment_term_days({}) == legal
        assert finance_dashboard.payment_term_days({"receivables": {"payment_terms_days": "7"}}) == (
            7, finance_dashboard.PROFILE_TERM_SOURCE)
    finally:
        sys.path.pop(0)
        sys.modules.pop("finance_dashboard", None)


def _generator_constant(root, name):
    """A constant out of the generator the project actually carries -- imported, not re-typed."""
    tools = os.path.join(root, "tools")
    sys.path.insert(0, tools)
    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        for module in ("finance_dashboard", "euer_report", "ledger_add"):
            sys.modules.pop(module, None)
        import finance_dashboard
        return getattr(finance_dashboard, name)
    finally:
        sys.path.remove(tools)
        sys.path.remove(os.path.join(root, "scripts"))
        sys.modules.pop("finance_dashboard", None)


def test_the_page_makes_no_request_beyond_itself(browser, tmp_path):
    """One document, no network. The office kit's pages fetch nothing, and this is how that is
    known: every request the browser makes while loading and using the page is recorded.

    Goes red the day a web font, an icon set, a chart library or an analytics beacon is added --
    each of which would also make the page useless on a machine without internet, which is where a
    bookkeeper's laptop often is.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "offline", "regular")
    assert run_generator(root).returncode == 0
    page, requests = _open(browser, root)
    try:
        for view in ("rechnungen", "offene-posten", "euer", "kleinunternehmer"):
            page.click('[role="tab"][data-view="%s"]' % view)
        page.wait_for_timeout(200)
    finally:
        page.close()
    assert requests == [page_url(root)], requests


# ---------------------------------------------------------------- 7./8. the two loud states

def test_an_empty_project_renders_a_direction(tmp_path):
    """Day one: no `ledger/` at all. Exit 0, no traceback, and every view says what will fill it.

    Emptiness is the state a new project is in for its first week, so it is a rendered state and
    not an error. Goes red when a missing `ledger/` raises, and when a view drops its empty block
    -- which would leave a user with a blank page and no next step.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "empty", "empty")
    run = run_generator(root)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "Traceback" not in run.stderr, run.stderr

    page = dom(generated_page(root))
    views = page.find_all("section", cls="view")
    assert views, "the page carries no views"
    for view in views:
        assert view.find_all(cls="empty"), "%s has no empty state" % view.attrs.get("id")
    overview = page.by_id("view-ueberblick")
    assert "scripts/ledger_add.py" in overview.text(), overview.text()[:400]


def test_an_invalid_ledger_is_named_on_the_page(tmp_path):
    """A broken row is reported ON the page, in the validator's own words, and the sums are marked.

    The generator is not on `gate_ledger_valid._BLOCKED_SCRIPT_RX`, so unlike `euer_report.py` it
    runs against an invalid ledger -- which is why it validates itself and says so instead of
    printing dependable-looking numbers. The finding compared here is produced by running the kit's
    own `ledger_add.validate_file`, so a reworded message moves both sides at once.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "alarm", "alarm")
    run = run_generator(root)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "UNGÜLTIG" in run.stdout or "UNG" in run.stdout

    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        sys.modules.pop("ledger_add", None)
        import ledger_add
        findings = []
        for name in sorted(os.listdir(os.path.join(root, "ledger"))):
            findings.extend(ledger_add.validate_file(os.path.join(root, "ledger", name)) or [])
    finally:
        sys.path.pop(0)
        sys.modules.pop("ledger_add", None)
    assert findings, "the alarm fixture validates clean, so this test would measure nothing"

    page = dom(generated_page(root))
    banners = [node for node in page.find_all(cls="banner") if "alarm" in node.classes]
    assert banners, "an invalid ledger produced no banner"
    said = banners[0].text()
    assert findings[0] in said, (findings[0], said[:400])
    overview = page.by_id("view-ueberblick")
    stamps = [node.text() for node in overview.find_all(cls="stamp") if "alarm" in node.classes]
    assert "ungültig" in stamps, stamps


# ------------------------------------------- 14. Brutto / Netto / USt, and the two tax states

@pytest.mark.parametrize("fixture,spelling,relief", [
    ("crossyear", None, False), ("regular", None, True),
    ("regular", "true", True), ("regular", "missing", True), ("regular", "null", True),
])
def test_the_three_lines_stand_under_every_figure_in_both_tax_states(tmp_path, fixture, spelling,
                                                                    relief):
    """Einnahmen, Ausgaben and Überschuss each carry Brutto, Netto and USt -- on the overview and
    on the EÜR tab, and the two say the same thing about the same year.

    The reader asked for this so the net result after VAT and the VAT payload can be read without
    opening the report (FR-0032, user feedback of 2026-09-02). Two states, and the difference
    between them is a statement about somebody's tax, not a display option:

    * Regelbesteuerung -- three amounts per figure, and the Überschuss's USt line IS the Zahllast:
      VAT taken in minus Vorsteuer paid, checked here against the two lines above it.
    * § 19 UStG -- no VAT is charged AND no Vorsteuer deducted, so Brutto equals Netto in BOTH
      directions and the USt line is a sentence rather than "0,00 €". Goes red when the split
      follows the rows instead of the profile: the `regular` fixture's expenses are booked
      `standard`, and following them printed a refund claim of 6.077,56 €.

    The figures themselves are pinned against the report and against a third aggregation in
    `test_the_dashboard_and_euer_report_agree_on_every_quarter`; what is measured here is that
    both places show the three lines and agree with each other.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / ("split-%s-%s" % (fixture, spelling)), fixture,
                         profile=_profile_with(tmp_path, fixture, spelling))
    assert run_generator(root).returncode == 0
    page = dom(generated_page(root))

    year = sorted({name[:4] for name in os.listdir(os.path.join(root, "ledger"))})[-1]
    blocks = [node for node in page.find_all(cls="year-block")
              if node.attrs.get("data-year") == year]
    euer = [node for node in page.find_all(cls="euer-block")
            if node.attrs.get("data-year") == year and node.attrs.get("data-period") == "year"]
    assert blocks and euer, (year, "no overview or EÜR block for the newest ledger year")

    for key in ("income", "expense", "surplus"):
        for name in ("gross", "net", "vat"):
            shown = figure_of(blocks[0], "%s-%s" % (key, name))
            assert shown, ("the overview shows no %s-%s line" % (key, name))
            assert shown == figure_of(euer[0], "%s-%s" % (key, name)), (
                "overview and EÜR tab disagree about %s-%s" % (key, name))

    if relief:
        for key in ("income", "expense", "surplus"):
            assert figure_of(blocks[0], key + "-net") == figure_of(blocks[0], key + "-gross"), (
                "no VAT figure may be printed, so Netto is Brutto: " + key)
            assert "€" not in figure_of(blocks[0], key + "-vat"), (
                "no VAT amount may be printed in this tax state: " + key)
        labels = [node.text() for node in blocks[0].find_all("dt")]
        assert "USt-Zahllast" not in labels, (
            "a line labelled Zahllast where there is none is a claim like a figure is: %s" % labels)
        # ...and the sentence under the block explains the figures that ARE there, not the ones
        # this state forbids: the generic note ends on how a Zahllast is computed.
        note = " ".join(node.text() for node in blocks[0].find_all("p", cls="rule-note"))
        assert "USt-Zahllast ist vereinnahmte" not in note, (
            "the block explains a Zahllast it does not print: %s" % note[:300])
    else:
        figures = {name: figure_of(blocks[0], name)
                   for name in ("income-vat", "expense-vat", "surplus-vat", "income-net",
                                "income-gross")}
        assert all("€" in value for value in figures.values()), figures
        cents = {name: _amount(value) for name, value in figures.items()}
        assert cents["surplus-vat"] == cents["income-vat"] - cents["expense-vat"], (
            "the Überschuss's USt line is the Zahllast and must be the difference of the two "
            "above it: %s" % figures)
        assert cents["income-net"] == cents["income-gross"] - cents["income-vat"], figures
        labels = [node.text() for node in blocks[0].find_all("dt")]
        assert "USt-Zahllast" in labels, labels


def _amount(text):
    """'−1.234,50 €' -> -123450. The page's own spelling, read back."""
    negative = text.startswith("−")
    digits = re.sub(r"[^0-9]", "", text.replace(" ", ""))
    value = int(digits[:-2] or "0") * 100 + int(digits[-2:])
    return -value if negative else value


# ----------------------------------------------- 19. German counts read wrong at one, everywhere

def _singular_plural_pairs(root, pages):
    """Every (singular, plural) the page can choose between -- from BOTH producers, derived.

    Three sources, none of them a list in this file:

    * the generator's own helper, read as code: `plural(n, one, many)` with two constants;
    * the pairs it hands that helper as a tuple, which is how `source_line` takes its label --
      two string constants side by side where the plural extends the singular;
    * the pairs the PAGE hands its own script, `data-one` / `data-many`, because the counts the
      browser writes cannot go through a Python helper at all.

    A producer that stops being any of these three stops being a producer.
    """
    with open(os.path.join(root, "tools", "finance_dashboard.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    pairs = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "plural"
                and len(node.args) == 3
                and all(isinstance(a, ast.Constant) and isinstance(a.value, str)
                        for a in node.args[1:])):
            if node.args[1].value != node.args[2].value:
                pairs.add((node.args[1].value, node.args[2].value))
        if (isinstance(node, ast.Tuple) and len(node.elts) == 2
                and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                        for e in node.elts)
                and node.elts[1].value.startswith(node.elts[0].value)
                and node.elts[1].value != node.elts[0].value):
            pairs.add((node.elts[0].value, node.elts[1].value))
    for text in pages.values():
        for one, many in re.findall(r'data-one="([^"]+)" data-many="([^"]+)"', text):
            if one != many:
                pairs.add((one, many))
    return pairs


def test_every_count_on_the_page_reads_right_at_one(browser, tmp_path):
    """A number followed by a word: at one, the word is the singular -- on every fixture.

    THE RULE IS DERIVED and it has both ends. The pairs come from the producers themselves
    (`_singular_plural_pairs`); a word standing after a "1" then has to be one of two things, or
    it is a defect:

    * the SINGULAR of a pair -- the normal case; or
    * a noun this page treats as invariant, and the corpus proves that by printing the same word
      after another number somewhere ("Summe (4 Posten)" beside "Summe (1 Posten)").

    That second clause is what makes the test survive its own subject: a suffix rule missed
    "1 Belege" (the one plural here that does not end in -n), and a rule that only read the pairs
    would go blind the moment a call site stops using `plural()` at all -- which is exactly the
    mutation this was measured against. `founding` is the one-row project and `crossyear` the one
    with a single OSS document, so between them every count on the page reaches one.
    """
    pytest.importorskip("yaml")
    pages, roots = {}, {}
    for state in FIXTURE_STATES:
        root = build_project(tmp_path / ("singular-" + state), state)
        assert run_generator(root).returncode == 0
        roots[state] = root
        pages[state] = generated_page(root)
    assert len(ledger_rows(roots["founding"])) == 1, "the one-row fixture stopped being one"

    pairs = _singular_plural_pairs(roots["founding"], pages)
    assert len(pairs) >= 4, "the pair harvest found almost nothing: %s" % sorted(pairs)
    # THE PAGE IN DOCUMENT ORDER, because the question is what stands next to what: the little DOM
    # above returns a node's own text before its children's, which puts words side by side that no
    # reader ever sees together (measured: it produced "1 Ob" out of two neighbouring list items).
    def plain(text):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text)))

    corpus = " ".join(plain(text) for text in pages.values())
    spelled = {word.split()[0] for pair in pairs for word in pair}
    # A noun this page treats as invariant: it stands after some other number in the corpus AND no
    # producer here chooses a form for it. The second half matters -- "bezahlte" stands after 128
    # too, and that must not buy "1 bezahlte Zeilen" a pass.
    invariant = {word for word in re.findall(r"(?<![\d.,])(?!1 )\d+ ([A-Za-zÄÖÜäöüß-]+)", corpus)
                 if word not in spelled}

    def begins(tail, word):
        return re.match(re.escape(word) + r"(?![A-Za-zÄÖÜäöüß])", tail) is not None

    def offences(text):
        found = []
        for match in re.finditer(r"(?<![\d.,])1 ([A-Za-zÄÖÜäöüß-]+)", text):
            tail, word = text[match.start(1):], match.group(1)
            if "§" in text[max(0, match.start() - 30):match.start()]:
                continue         # a legal citation counts nothing: "§ 15 Abs. 2 Satz 1 Nr. 1"
            if any(begins(tail, one) for one, _many in pairs):
                continue                                    # the singular: right
            if any(begins(tail, many) for _one, many in pairs):
                found.append(match.group(0))                # the plural: wrong
            elif word[:1].isupper() and word not in invariant:
                # a capitalised noun after a one that NO producer here spells -- which is what a
                # call site that stopped asking `plural()` leaves behind. CAPITALISED and not any
                # word: the counted thing is a German noun, and a lowercase word after a "1" is
                # the rest of a sentence. Taking the clause out was proposed as a widening and
                # measured instead: the page says "davon 1 in einem anderen Ledgerjahr storniert",
                # so every fixture went red on `1 in` (TSK-0114). What the clause therefore does
                # NOT reach is a lowercase word a call site prints as a count.
                found.append(match.group(0))
        return found

    for state, text in pages.items():
        said = plain(text)
        assert not offences(said), (state, offences(said))

    # ...and the counts the SCRIPT writes, in a browser, where the noun is chosen at all.
    live, _requests = _open(browser, roots["founding"], clock=FROZEN_TODAY)
    try:
        live.click('[role="tab"][data-view="rechnungen"]')
        said = shown(live, "#view-rechnungen .count")
        assert not offences(said), said
    finally:
        live.close()


# ------------------------------- 17./18. the tax question, and the figure that must not appear

@pytest.mark.parametrize("written,answers", [
    (True, True), (False, True),
    ("true", False), ("yes", False), ("Ja", False), (None, False), (1, False), ("", False),
    (MISSING, False), ([True], False), ({"ja": True}, False),
])
def test_only_a_boolean_answers_the_tax_question(tmp_path, written, answers):
    """`tax.kleinunternehmer` is a yes/no question, and only `true` and `false` answer it.

    EVERY OTHER VALUE IS THE ABSENCE OF AN ANSWER, and the page then prints no USt figure and no
    Zahllast -- because the two states it could otherwise fall into say opposite things about
    somebody's tax. Measured 2026-09-02 against the `regular` fixture, whose expenses carry 19 %:
    `"true"` in quotes, `Ja` and a missing `tax:` block each printed "USt-Zahllast −6.077,56 €",
    a refund § 15 Abs. 2 Satz 1 Nr. 1 UStG excludes, while `true` printed the § 19 sentence. The
    chain starts in the shipped state: the kit's own profile template carries `null`.

    BOTH ENDS. The two real answers must still work -- `false` prints the split, `true` prints the
    § 19 sentence -- or "print nothing" would pass this test by never printing anything.

    And the refusal has to be READABLE WHERE THE FIGURES ARE: the mitigation hung on `is None`
    until 2026-09-02, so a profile carrying `"true"` warned on no tab at all. It is asserted on
    the overview, which is the tab the page opens with.
    """
    yaml = pytest.importorskip("yaml")
    profile = {"business": {"name": "Schreibweise", "legal_form": "Einzelunternehmen"}}
    if written is not MISSING:
        profile["tax"] = {"kleinunternehmer": written, "fiscal_year": "calendar"}
    root = build_project(tmp_path / ("answer-%s" % re.sub(r"\W+", "-", repr(written))), "regular",
                         profile=profile)
    assert run_generator(root).returncode == 0
    with open(os.path.join(root, "project_memory", "business_profile.yaml"),
              encoding="utf-8") as handle:
        found = yaml.safe_load(handle)
        stored = (found.get("tax") or {}).get("kleinunternehmer", MISSING)
        assert stored == written or (stored is MISSING and written is MISSING), (
            "the spelling did not survive the round trip through YAML, so this case measures "
            "something else than it says")

    page = dom(generated_page(root))
    overview = page.by_id("view-ueberblick")
    vat = figure_of(overview, "surplus-vat")
    if answers and written is False:
        assert "€" in vat, ("an explicit false is Regelbesteuerung and prints the Zahllast", vat)
    elif answers:
        assert "§ 19" in vat, ("an explicit true prints the § 19 sentence", vat)
    else:
        assert "€" not in vat, (
            "%r is not an answer to a yes/no question, and this page turned it into one: %s"
            % (written, vat))
        assert figure_of(overview, "surplus-net") == figure_of(overview, "surplus-gross")
        # ON EVERY TAB THAT SHOWS THE FIGURES, derived from the page rather than listed: a view
        # carrying an amount carries the reason there is no VAT in it.
        showing = [view for view in page.find_all("section", cls="view")
                   if view.find_all(attr="data-figure")]
        assert len(showing) >= 2, [view.attrs.get("id") for view in showing]
        for view in showing:
            said = view.text()
            assert "tax.kleinunternehmer" in said, (
                "%s prints figures and never names the field that would settle them"
                % view.attrs.get("id"))
            assert "true" in said and "false" in said, (
                "the refusal must name BOTH values that answer the question: %s" % said[:400])
            if isinstance(written, (list, tuple, dict)):
                # ...and it names the value the way `business_profile.yaml` spells it: `repr`
                # printed `[True]` for a YAML `[true]`, a spelling no reader of that file sees.
                assert repr(written) not in said, (
                    "the page names the value in Python's spelling: %s" % said[:200])
        # ...and in the overview's own "Jetzt ansteht" list, where the § 19 line would stand.
        due = " ".join(node.text() for node in overview.find_all("ul", cls="due"))
        assert "tax.kleinunternehmer" in due, (
            "the list a reader skims says nothing about the missing answer: %s" % due[:300])


def test_no_zahllast_is_printed_where_the_tax_state_says_there_is_none(tmp_path):
    """One page, one answer: where no VAT figure may be printed, the word Zahllast carries no
    number anywhere -- not in the headline lines, not in the informational block below them.

    The informational block exists because `euer_report.py` prints two VAT sums for every profile
    and the page must not silently differ from it. It prints TWO, never a Zahllast (measured: a
    generated report carries the string zero times), so the difference is this page's own
    arithmetic -- and under § 19 it is the refund the same page calls impossible four lines
    higher. Goes red when the difference is printed again, or when the label alone comes back.
    """
    pytest.importorskip("yaml")
    for state in ("regular", "alarm"):
        root = build_project(tmp_path / ("zahllast-" + state), state)
        assert run_generator(root).returncode == 0
        page = dom(generated_page(root))

        report = subprocess.run(
            [sys.executable, "-B", os.path.join(root, "scripts", "euer_report.py"),
             "--year", "2026", "--quarter", "1"],
            capture_output=True, text=True, cwd=root, timeout=300)
        assert report.returncode == 0, report.stderr
        with open(os.path.join(root, "reports", "euer_2026_Q1.md"), encoding="utf-8") as handle:
            assert "Zahllast" not in handle.read(), (
                "the report prints a Zahllast now, so the page may carry one too -- rewrite this")

        for view in ("view-euer", "view-ueberblick"):
            said = page.by_id(view).text()
            for piece in said.split("Zahllast")[1:]:
                assert "€" not in piece[:80], (state, view, piece[:120])
        assert figure_of(page.by_id("view-euer"), "report-vat-payload") is None, state


# ---------------------------------------------------------------- 9. the § 19 UStG limits

def _turnover_rows(year, cents):
    """One paid Kleinunternehmer income row of `cents` in `year` -- brutto equals netto (§ 19)."""
    return [{"id": "L%s-0001" % year, "doc_date": "%s-03-01" % year,
             "payment_date": "%s-03-01" % year, "direction": "income", "doc_type": "invoice",
             "counterparty": "Kundin", "invoice_no": "RE-%s-001" % year,
             "net": "%d.%02d" % divmod(cents, 100), "vat_rate": "0.00",
             "gross": "%d.%02d" % divmod(cents, 100), "vat_treatment": "kleinunternehmer",
             "category": "sales_local", "source": "archive/finanzen/%s/ausgang/RE.pdf" % year,
             "reverses": "", "note": ""}]


@pytest.mark.parametrize("previous_cents,current_cents,expected", [
    (2500000, 100, "within"),
    (2500001, 100, "previous_exceeded"),
    (100, 10000000, "within"),
    (100, 10000001, "current_exceeded"),
    (None, 2600000, "previous_unknown"),
])
def test_the_threshold_verdict_switches_at_the_limits(tmp_path, previous_cents, current_cents,
                                                      expected):
    """§ 19 Abs. 1 UStG is "up to", so the limit itself is still inside -- one cent over is not.

    Four ledgers one cent apart at each of the two limits, and a FIFTH case with no previous year
    at all: § 19 in the wording in force since 2025 puts a business without a previous year under
    the 25.000 € limit for the current year, so "no file for 2025" is not the same question as
    "2025 was small". Nothing in this project answers which of the two it is -- the shipped
    `business_profile.yaml` carries no founding year -- so the verdict is its own, and the page
    says what would settle it. Goes red when a comparison is written as `>=`, when the two limits
    are swapped, when the previous year is taken from the wrong file, when the figures are compared
    as floats and one cent disappears, and when a missing previous year falls back to "within":
    measured 2026-09-02, a founding year with 26.000 € read "innerhalb der Grenzen".
    """
    pytest.importorskip("yaml")
    ledgers = {"2026": _turnover_rows("2026", current_cents)}
    if previous_cents is not None:
        ledgers["2025"] = _turnover_rows("2025", previous_cents)
    root = build_project(
        tmp_path / ("limit-%s-%d" % (previous_cents, current_cents)),
        ledgers=ledgers,
        profile={"business": {"name": "Grenzfall", "legal_form": "Einzelunternehmen"},
                 "tax": {"kleinunternehmer": True}},
        master={"categories": {"income": [{"key": "sales_local", "label_de": "Direktverkauf",
                                           "euer_line": "Betriebseinnahmen"}], "expense": []}})
    assert run_generator(root).returncode == 0
    page = dom(generated_page(root))
    verdicts = [node.attrs["data-verdict"] for node in page.find_all(attr="data-verdict")]
    assert verdicts == [expected], (verdicts, expected)

    if expected == "previous_unknown":
        said = page.by_id("view-kleinunternehmer").text()
        assert "2025" in said and eur(2500000) in said, (
            "the refusal must name the missing year and the limit that would apply instead: %s"
            % said[:400])
        # ONE bar per condition, and NEITHER of them can be drawn here: the previous year has no
        # ledger file, and the current year has no settled limit without it. The display had
        # "kein Ledger" beside "über der Grenze" in one gauge until 2026-09-02, and a confident
        # "26 % · Rest 74.000,00 €" in the other until the round after it.
        gauges = page.by_id("view-kleinunternehmer").find_all(cls="gauge")
        unknown = [node for node in gauges if "unknown" in node.classes]
        assert len(unknown) == 2, [sorted(node.classes) for node in gauges]
        assert "alarm" not in unknown[0].classes and "warn" not in unknown[0].classes
        assert "über der Grenze" not in unknown[0].text(), unknown[0].text()
        assert not unknown[0].find_all(cls="fill"), "an undrawable bar must have no fill"
        # BOTH BARS, because the second one is measured against a limit that is not settled
        # either: with no previous year, 25.000 € (founding year) and 100.000 € are both live.
        # Drawing "26 % · Rest 74.000,00 €" there was the figure that won the skim while the
        # verdict beside it said the question was open (measured 2026-09-02).
        assert len(gauges) == len(unknown), (
            "the current-year bar still claims a limit the verdict calls undecided: %s"
            % [node.text()[:90] for node in gauges])
        for node in unknown:
            assert "%" not in node.text() and "Rest" not in node.text(), node.text()
            assert eur(2500000) in node.text() and eur(10000000) in node.text() or (
                "kein Ledger" in node.text()), node.text()
        due = [node.text() for node in page.by_id("view-ueberblick").find_all("li")]
        watching = [said for said in due if "§ 19" in said]
        assert watching and eur(2500000) in watching[0] and eur(10000000) in watching[0], (
            "the overview names one limit as if it were settled: %s" % watching)
    else:
        assert not [node for node in page.find_all(cls="gauge") if "unknown" in node.classes]


# ---------------------------------------------------------------- 11. the template owns its slots

def test_every_template_slot_is_filled(tmp_path):
    """The template is the list of slots; the generator keeps no second one.

    Both ends: the template must still HAVE slots (a template that lost them would make the second
    assertion trivially true), and the rendered page must carry none of them. Goes red the moment
    a slot is added to the shell and not filled by the renderer -- which is exactly what would
    otherwise ship as a literal pair of braces in front of a user.
    """
    pytest.importorskip("yaml")
    with open(os.path.join(OFFICE_TEMPLATE, "tools", "finance_dashboard.template.html"),
              encoding="utf-8") as handle:
        template = handle.read()
    slots = set(re.findall(r"\{\{(\w+)\}\}", template))
    assert len(slots) >= 5, "the template carries %d slots -- that is not the shell" % len(slots)

    for state in ("regular", "empty", "alarm"):
        root = build_project(tmp_path / ("slots-" + state), state)
        assert run_generator(root).returncode == 0
        page = generated_page(root)
        left = sorted(name for name in slots if "{{%s}}" % name in page)
        assert not left, (state, left)
        assert "{{" not in page, state


# --------------------------------------- 15./16. two ways to be handed a project that is not one

def test_a_file_in_ledger_that_no_report_reads_is_named_on_the_page(tmp_path):
    """A copy of a year file is invisible to every report while looking exactly like the books.

    `ledger/` is a directory a person writes into, and `2026 - Kopie.csv` is the case
    `ledger_add.validate_file` names in its own refusal. The generator used to skip it in silence
    and stamp "Ledger gültig" beside it. What the page says about it is the KIT VALIDATOR'S
    sentence, produced by running it here, so a reworded refusal moves both sides at once.

    BOTH ENDS. The stray must be named AND the sums must stay dependable: they come from the year
    files, so calling the ledger invalid over a backup copy would be the over-alarming half of the
    same defect -- measured against `test_an_invalid_ledger_is_named_on_the_page`, which is what a
    real finding looks like.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "stray", "regular")
    shutil.copy(os.path.join(root, "ledger", "2026.csv"),
                os.path.join(root, "ledger", "2026 - Kopie.csv"))
    run = run_generator(root)
    assert run.returncode == 0, run.stdout + run.stderr

    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        sys.modules.pop("ledger_add", None)
        import ledger_add
        said = ledger_add.validate_file(os.path.join(root, "ledger", "2026 - Kopie.csv"))
    finally:
        sys.path.pop(0)
        sys.modules.pop("ledger_add", None)
    assert said, "the kit validator accepts the stray file, so this test would measure nothing"

    page = dom(generated_page(root))
    notes = [node for node in page.find_all(cls="banner") if "note" in node.classes]
    assert notes, "a file no report reads produced no notice at all"
    assert "2026 - Kopie.csv" in notes[0].text(), notes[0].text()[:300]
    assert said[0] in notes[0].text(), (said[0], notes[0].text()[:400])
    assert not [node for node in page.find_all(cls="banner") if "alarm" in node.classes], (
        "a stray copy made the page call the ledger invalid")
    stamps = [node.text() for node in page.by_id("view-ueberblick").find_all(cls="stamp")]
    assert "gültig" in stamps, stamps


def test_a_missing_pyyaml_is_a_sentence_and_not_a_traceback(tmp_path):
    """The kit documents are YAML, so without PyYAML nothing can be rendered -- and the answer to
    that is the same shape the same file already gives for a missing `scripts/`: one line naming
    the command that installs it.

    Goes red when the import moves back into the reading and raises through: measured before this
    branch existed, the run ended in `ModuleNotFoundError: No module named 'yaml'` and a traceback
    a non-developer cannot act on.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "noyaml", "regular")
    blocker = os.path.join(root, "blockyaml")
    os.makedirs(blocker)
    with open(os.path.join(blocker, "yaml.py"), "w", encoding="utf-8") as handle:
        handle.write("raise ImportError('No module named yaml')\n")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = blocker
    run = subprocess.run([sys.executable, "-B", os.path.join(root, GENERATOR_REL)],
                         capture_output=True, text=True, cwd=root, env=environment, timeout=300)

    assert "Traceback" not in run.stderr, run.stderr
    assert run.stderr.startswith("[finance_dashboard]"), run.stderr
    assert "requirements-office.txt" in run.stderr, run.stderr
    with open(os.path.join(OFFICE_TEMPLATE, "requirements-office.txt"), encoding="utf-8") as handle:
        assert "yaml" in handle.read().lower(), (
            "the refusal names a requirements file that does not carry PyYAML")
    # IT REFUSES, and it refuses the same way as the refusal beside it. The equality alone was
    # not a pin: turning BOTH `raise SystemExit(1)` into `SystemExit(0)` left this file green
    # while the command reported success and wrote nothing (measured 2026-09-02).
    without_scripts = build_project(tmp_path / "noscripts", "regular")
    shutil.rmtree(os.path.join(without_scripts, "scripts"))
    beside = run_generator(without_scripts).returncode
    assert run.returncode != 0, "a missing dependency ended in success"
    assert beside != 0, "a missing scripts/ ended in success"
    assert run.returncode == beside, (run.returncode, beside)
    assert not os.path.isfile(os.path.join(root, OUTPUT_REL)), (
        "the refusal still wrote a page")


# ------------------------------------------------- 13. dashboards/ is an output, not a document tray

def test_the_dashboards_directory_is_not_a_document_tray(tmp_path):
    """`dashboards/` holds what a command in the repo wrote, so the ad-hoc name guard keeps guarding.

    A DOCUMENT TRAY is a directory the kit ships nothing into but a folder guide, because what lands
    there comes from OUTSIDE the project -- and inside one, `guard_no_adhoc` stands down. That is
    decided by `kernel.trays.document_trays` on the STEM of the shipped files, which is why the
    guide here is `ABOUT.txt` and not `README.txt`.

    BOTH ENDS, or the name would be a superstition: the shipped tree must not make `dashboards` a
    tray, AND the same tree with the guide renamed must. The second half is measured in a copy
    outside the kit, so what is read is the running definition and not this docstring.
    """
    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    try:
        sys.modules.pop("kernel.trays", None)
        from kernel import trays
        kit = os.path.join(ROOT, "team-kits", "office-team")
        assert "dashboards" not in trays.document_trays(kit), trays.document_trays(kit)

        copy = str(tmp_path / "kit")
        shutil.copytree(os.path.join(kit, "templates"), os.path.join(copy, "templates"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        guide = os.path.join(copy, "templates", "repo", "dashboards")
        shipped = sorted(os.listdir(guide))
        assert len(shipped) == 1, ("the tray rule reads EVERY shipped file of the directory, so "
                                   "this test speaks for one guide only: %s" % shipped)
        os.rename(os.path.join(guide, shipped[0]), os.path.join(guide, "README.txt"))
        assert "dashboards" in trays.document_trays(copy), (
            "renaming the guide no longer makes the directory a tray, so the name it carries is "
            "not what keeps the guard here -- say what does")
    finally:
        sys.path.remove(os.path.join(ROOT, "team-kits"))

    record = os.path.join(ROOT, "team-kits", "office-team", "hooks", "document_trays.txt")
    with open(record, encoding="utf-8-sig") as handle:
        recorded = [line.strip() for line in handle if line.strip()]
    assert "dashboards" not in recorded, recorded


# ---------------------------------------------------------------- 12. the watch follows the field

def test_a_kleinunternehmer_false_profile_hides_the_watch_and_null_names_the_gap(tmp_path):
    """The threshold view is derived from `tax.kleinunternehmer`, and all three of its values mean
    something different: `true` watches, `false` has nothing to watch, unset is a missing answer.

    An unset field must not read as "false" -- that would silently drop the watch for every project
    whose onboarding never asked. Goes red when the tab is derived from the ledger, from a
    truthiness test over the field, or when the empty state stops naming the field a user has to
    fill.
    """
    pytest.importorskip("yaml")
    seen = {}
    for label, value in (("false", False), ("null", None), ("true", True)):
        root = build_project(tmp_path / ("ku-" + label), "regular",
                             profile={"business": {"name": "Nordlicht", "legal_form": "e.K."},
                                      "tax": {"kleinunternehmer": value}})
        assert run_generator(root).returncode == 0
        seen[label] = dom(generated_page(root))

    tabs = {label: [node.attrs.get("data-view") for node in page.find_all(attr="role")
                    if node.attrs.get("role") == "tab"] for label, page in seen.items()}
    assert "kleinunternehmer" not in tabs["false"], tabs["false"]
    assert "kleinunternehmer" in tabs["null"] and "kleinunternehmer" in tabs["true"]
    assert seen["false"].by_id("view-kleinunternehmer") is None

    gap = seen["null"].by_id("view-kleinunternehmer")
    assert gap.find_all(cls="empty"), "the unset case shows no empty state"
    assert "tax.kleinunternehmer" in gap.text(), gap.text()[:300]
    watching = seen["true"].by_id("view-kleinunternehmer")
    assert watching.find_all(cls="gauge"), "the watching case shows no gauge"


# ---------------------------------------------------------------- FR-0076: the form's own lines

OFFICE_MEMORY = os.path.join(ROOT, "team-kits", "office-team", "templates", "project_memory")


def shipped_vocabulary():
    """The category vocabulary the kit SHIPS, parsed -- never a string search over the template."""
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(OFFICE_MEMORY, "master_data.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def shipped_profile():
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(OFFICE_MEMORY, "business_profile.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def kit_module(root, name):
    """One of the project's own scripts, imported from the tree the test built."""
    sys.path.insert(0, os.path.join(root, "scripts"))
    try:
        sys.modules.pop(name, None)
        return __import__(name)
    finally:
        sys.path.pop(0)
        sys.modules.pop(name, None)


def report_of(root, year, quarter):
    result = subprocess.run(
        [sys.executable, "-B", os.path.join(root, "scripts", "euer_report.py"),
         "--year", str(year), "--quarter", str(quarter)],
        capture_output=True, text=True, cwd=root, timeout=300)
    assert result.returncode == 0, result.stderr
    with open(os.path.join(root, "reports", "euer_%s_Q%s.md" % (year, quarter)),
              encoding="utf-8") as handle:
        return handle.read()


def report_line_sums(markdown):
    """{heading: (income, expense)} out of the report's per-form-line table, in CENTS."""
    section = markdown.split("## Nach Zeile der Anlage E\u00dcR")[1].split("\n## ")[0]
    found = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("Zeile", "---") or cells[0].startswith("---"):
            continue
        try:
            found[cells[0]] = (int(round(float(cells[1]) * 100)),
                               int(round(float(cells[2]) * 100)))
        except ValueError:
            continue
    return found


def test_a_fresh_project_ships_a_category_vocabulary_the_p4_12_stall_cannot_recur_on(tmp_path):
    """P4-12 / BUG-0071: the office pilot met an EMPTY category vocabulary and stopped.

    The template used to ship `categories: {income: [], expense: []}` with the vocabulary as a
    COMMENT, so a fresh project had none and no role could write one. Measured as the shipped file
    parsed -- not searched -- plus the consequence on a real page: a booking under a shipped key
    shows its German label and the form line it belongs to, where an unknown key shows the raw key.

    THE PROPERTY IS CHECKED, NOT THE NAMES: every shipped category carries a key, a label and an
    `euer_line` the report reads as a whole number, and the form YEAR and its source stand in the
    file rather than in a script. A list of the twelve names here would be a second vocabulary.
    """
    shipped = shipped_vocabulary()
    categories = shipped["categories"]
    assert categories["income"] and categories["expense"], (
        "the kit ships an empty vocabulary again -- this is the P4-12 stall")
    form = shipped["euer_form"]
    assert isinstance(form["year"], int) and str(form["source"]).strip(), form

    root = build_project(tmp_path / "fresh", "regular", master=shipped)
    report = kit_module(root, "euer_report")
    for direction in ("income", "expense"):
        for entry in categories[direction]:
            assert entry["key"] and entry["label_de"], entry
            assert report.line_number(entry["euer_line"]) is not None, entry

    one = categories["expense"][0]
    write_ledger(os.path.join(root, "ledger", "2026.csv"), [
        {"id": "L1", "doc_date": "2026-02-01", "payment_date": "2026-02-01", "direction": "expense",
         "doc_type": "invoice", "counterparty": "ACME", "net": "100.00", "vat_rate": "19",
         "gross": "119.00", "vat_treatment": "standard", "category": one["key"],
         "source": "archive/x.pdf"},
        {"id": "L2", "doc_date": "2026-02-02", "payment_date": "2026-02-02", "direction": "expense",
         "doc_type": "invoice", "counterparty": "ACME", "net": "10.00", "vat_rate": "19",
         "gross": "11.90", "vat_treatment": "standard", "category": "was_nie_definiert_wurde",
         "source": "archive/y.pdf"}])
    assert run_generator(root).returncode == 0
    text = dom(generated_page(root)).by_id("view-euer").text()
    assert one["label_de"] in text and str(one["euer_line"]) in text, text[:400]
    assert "was_nie_definiert_wurde" in text, "an unknown category must stay visible as its key"


@pytest.mark.parametrize("fixture", ["regular", "crossyear"])
def test_the_dashboard_and_the_report_agree_on_every_form_line(tmp_path, fixture):
    """The per-line parity FR-0076 (2) asks for: the Steuerberater maps the page 1:1 to the report.

    Two producers, one grouping: the report writes a table per quarter and the page renders the
    same rows from the same function (`euer_report.by_form_line`). `crossyear` is here because its
    vocabulary deliberately keeps a CAPTION where a line number belongs -- the "names no line"
    branch is then measured on a real page and not only on an inline override.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / ("lines-" + fixture), fixture)
    assert run_generator(root).returncode == 0
    blocks = {(block.attrs["data-year"], block.attrs["data-period"]): block
              for block in dom(generated_page(root)).find_all(cls="euer-block")}
    checked = 0
    for (year, period), block in sorted(blocks.items()):
        if period == "year":
            continue
        said = report_line_sums(report_of(root, year, period))
        shown = {}
        for row in block.find_all(attr="data-line"):
            cells = row.find_all("td")
            shown[cells[0].text()] = (cells[1].text(), cells[2].text())
        assert set(shown) == set(said), (year, period, sorted(shown), sorted(said))
        for heading, (income_c, expense_c) in said.items():
            assert shown[heading] == (eur(income_c) if income_c else "",
                                      eur(expense_c) if expense_c else ""), (year, period, heading)
        checked += 1
    assert checked == 8, checked


def test_the_per_line_sums_and_the_per_category_sums_are_the_same_money(tmp_path):
    """One quarter's money, grouped two ways, has to come out the same.

    The per-category table is what the owner steers by and the per-line table is what the form
    asks for; several categories land on one line, so the second is coarser and never smaller.
    Goes red if a booking is dropped when its category names no line, or counted twice when two
    categories share one.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "same-money", "regular")
    for quarter in (1, 2, 3, 4):
        markdown = report_of(root, 2026, quarter)
        lines = report_line_sums(markdown)
        totals = re.search(r"\| Einnahmen \| (-?[\d.]+) EUR \|\n\| Ausgaben \| (-?[\d.]+) EUR",
                           markdown)
        assert totals, markdown[:400]
        assert (sum(one[0] for one in lines.values()),
                sum(one[1] for one in lines.values())) == (
                    int(round(float(totals.group(1)) * 100)),
                    int(round(float(totals.group(2)) * 100))), quarter


def test_a_category_whose_line_is_not_a_number_is_named_rather_than_attached_to_a_line(tmp_path):
    """`euer_line` is a NUMBER or it is nothing — and "nothing" is reported, never guessed away.

    A project that filled the field with a caption (which is what the kit shipped before this
    round) must not have its money silently attached to some line: it lands under its own heading
    and the report says which categories are unmapped. Measured on both ends -- the same ledger
    with a numbered vocabulary puts the same money on the line.
    """
    pytest.importorskip("yaml")
    rows = [{"id": "L1", "doc_date": "2026-02-01", "payment_date": "2026-02-01",
             "direction": "expense", "doc_type": "invoice", "counterparty": "ACME",
             "net": "100.00", "vat_rate": "19", "gross": "119.00", "vat_treatment": "standard",
             "category": "porto", "source": "archive/x.pdf"}]
    captioned = {"euer_form": {"year": 2025, "source": "test"},
                 "categories": {"income": [],
                                "expense": [{"key": "porto", "label_de": "Porto",
                                             "euer_line": "\u00dcbrige Betriebsausgaben"}]}}
    root = build_project(tmp_path / "captioned", "regular", ledgers={"2026": rows},
                         master=captioned)
    markdown = report_of(root, 2026, 1)
    report = kit_module(root, "euer_report")
    assert report.UNMAPPED in report_line_sums(markdown)
    assert "porto" in markdown.split("## Nach Zeile")[1].split("\n## ")[0]

    numbered = {"euer_form": {"year": 2025, "source": "test"},
                "categories": {"income": [],
                               "expense": [{"key": "porto", "label_de": "Porto", "euer_line": 60,
                                            "euer_line_label": "Sonstige"}]}}
    root = build_project(tmp_path / "numbered", "regular", ledgers={"2026": rows}, master=numbered)
    headings = report_line_sums(report_of(root, 2026, 1))
    assert report.UNMAPPED not in headings and "Zeile 60 \u2014 Sonstige" in headings, headings


def _afa_ledger():
    def row(number, net, gross, category="tools"):
        return {"id": "L%d" % number, "doc_date": "2026-02-0%d" % number,
                "payment_date": "2026-02-0%d" % number, "direction": "expense",
                "doc_type": "invoice", "counterparty": "Werkzeug AG", "invoice_no": "R-%d" % number,
                "net": net, "gross": gross, "vat_rate": "19", "vat_treatment": "standard",
                "category": category, "source": "archive/x.pdf"}
    return [row(1, "1200.00", "1428.00"), row(2, "700.00", "833.00")]


def _afa_master(limit=800, silenced=False):
    category = {"key": "tools", "label_de": "Werkzeug", "euer_line": 60,
                "euer_line_label": "Sonstige"}
    if silenced:
        category["afa_hint"] = False
    return {"euer_form": {"year": 2025, "source": "test", "gwg_limit_net": limit},
            "categories": {"income": [], "expense": [category]}}


def _flagged_in(page, year, period):
    """The booking ids the AfA hint flags in ONE block of the EÜR tab.

    Per BLOCK and not per page: the tab renders a block for the whole year and one per quarter, so
    a booking legitimately appears in two of them and a page-wide list would count it twice.
    """
    for block in dom(page).find_all(cls="euer-block"):
        if (block.attrs["data-year"], block.attrs["data-period"]) == (year, period):
            return [node.attrs["data-afa"] for node in block.find_all(attr="data-afa")]
    raise AssertionError("the page carries no EÜR block for %s/%s" % (year, period))


def test_the_afa_hint_is_a_flag_whose_limit_comes_from_the_vocabulary(tmp_path):
    """FR-0076 (3): a HINT, and its threshold is a project value rather than a constant.

    Three measurements in one, because they are three halves of the same claim: the booking over
    the limit is flagged and the one under it is not; the flag is a SENTENCE and no depreciation
    figure appears anywhere; and raising the limit in `master_data.yaml` alone makes the flag go
    away -- which is what "a profile/vocabulary value, not a constant" means.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "afa", "regular", ledgers={"2026": _afa_ledger()},
                         master=_afa_master())
    report = kit_module(root, "euer_report")
    markdown = report_of(root, 2026, 1)
    section = markdown.split("## M\u00f6gliche Anlageg\u00fcter")[1].split("\n## ")[0]
    assert "R-1" in section and "R-2" not in section, section
    assert report.ASSET_HINT in section
    assert "Abschreibung" in section and "AfA-Betrag" not in markdown

    assert run_generator(root).returncode == 0
    assert _flagged_in(generated_page(root), "2026", "1") == ["L1"]

    raised = build_project(tmp_path / "afa-raised", "regular", ledgers={"2026": _afa_ledger()},
                           master=_afa_master(limit=2000))
    assert "R-1" not in report_of(raised, 2026, 1).split("## M\u00f6gliche Anlageg\u00fcter")[1]
    assert run_generator(raised).returncode == 0
    assert _flagged_in(generated_page(raised), "2026", "1") == []


def test_a_category_can_switch_the_afa_hint_off_and_only_the_boolean_false_does_it(tmp_path):
    """The user's lever on the hint, spelled the way `second_reading` is spelled — both ends.

    In a trading business every wholesale invoice is over the GWG threshold and none of them is an
    asset, so a hint that fires on all of them is one nobody reads. The lever is the vocabulary's,
    not the kit's, and like `second_reading` only the boolean `false` operates it: a quoted "false"
    is a typo and must NOT quietly silence a category.
    """
    pytest.importorskip("yaml")
    for silenced, expected in ((False, ["L1"]), (True, [])):
        root = build_project(tmp_path / ("afa-lever-%s" % silenced), "regular",
                             ledgers={"2026": _afa_ledger()},
                             master=_afa_master(silenced=silenced))
        assert run_generator(root).returncode == 0
        assert _flagged_in(generated_page(root), "2026", "1") == expected
    typo = _afa_master()
    typo["categories"]["expense"][0]["afa_hint"] = "false"
    root = build_project(tmp_path / "afa-typo", "regular", ledgers={"2026": _afa_ledger()},
                         master=typo)
    assert run_generator(root).returncode == 0
    assert _flagged_in(generated_page(root), "2026", "1") == ["L1"]


def test_the_founding_year_decides_the_case_the_missing_previous_year_leaves_open(tmp_path):
    """The seam I3 left open, closed WITH the reader that needs it (TSK-0113 -> TSK-0116).

    The `founding` fixture has one ledger year and 26.000 € of income. Without a founding year the
    page could not decide whether that is a first year (25.000 € limit, exceeded) or a missing file
    (nothing decidable), and it refused -- correctly. With `tax.founding_year` equal to the ledger
    year the same page reaches a verdict, and it is the ALARMING one: § 19 Abs. 1 UStG in the
    wording in force since 2025 puts a founding year under 25.000 €.

    A founding year that is NOT the current one is the other case and must not buy a verdict: then
    a previous year exists and only its ledger file is missing.
    """
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(FIXTURES, "founding", "business_profile.yaml"),
              encoding="utf-8") as handle:
        base = yaml.safe_load(handle)
    verdicts = {}
    for label, year in (("none", None), ("first", 2026), ("earlier", 2024)):
        profile = json.loads(json.dumps(base))
        profile.setdefault("tax", {})["founding_year"] = year
        root = build_project(tmp_path / ("founding-" + label), "founding", profile=profile)
        assert run_generator(root).returncode == 0
        page = dom(generated_page(root))
        verdicts[label] = page.find_all(attr="data-verdict")[0].attrs["data-verdict"]
    assert verdicts == {"none": "previous_unknown", "first": "current_exceeded",
                        "earlier": "previous_unknown"}, verdicts


def test_the_shipped_profile_leaves_the_tax_status_and_the_founding_year_unanswered(tmp_path):
    """A fresh project starts UNKNOWN on both questions, and the page says so instead of guessing.

    Shipping a default for either would be a wrong statement about somebody's tax on every page
    that prints a figure. Measured as the shipped file PARSED plus the consequence on a page built
    from it: no VAT figure, and the sentence that names the field.
    """
    pytest.importorskip("yaml")
    tax = shipped_profile()["tax"]
    assert tax["kleinunternehmer"] is None and tax["founding_year"] is None, tax

    root = build_project(tmp_path / "unanswered", "regular", profile=shipped_profile())
    assert run_generator(root).returncode == 0
    page = dom(generated_page(root))
    assert not page.find_all(attr="data-verdict"), "no watch without an answer"
    assert "tax.kleinunternehmer" in page.by_id("view-euer").text()


def test_a_vocabulary_entry_that_is_not_a_mapping_costs_a_category_and_not_the_page(tmp_path):
    """N3 of rework 1: the page died where the report shrugged, over the same typo.

    `master_data.yaml` invites its reader to rename and add categories, and the first thing a
    hand-edited list produces is a bare string where a mapping belongs. The report skipped it; the
    generator called `.get` on it and exited 1 with an AttributeError, so the project had no page at
    all. Two readers of one file may not answer one typo differently -- both skip the entry, keep
    every other one, and the booking under the broken entry stays visible as its raw key.
    """
    pytest.importorskip("yaml")
    master = {"euer_form": {"year": 2025, "source": "test", "gwg_limit_net": 800},
              "categories": {"income": [],
                             "expense": ["porto",
                                         {"key": "software", "label_de": "Software",
                                          "euer_line": 60, "euer_line_label": "Sonstige"}]}}
    rows = [{"id": "L1", "doc_date": "2026-02-01", "payment_date": "2026-02-01",
             "direction": "expense", "doc_type": "invoice", "counterparty": "ACME",
             "net": "10.00", "vat_rate": "19", "gross": "11.90", "vat_treatment": "standard",
             "category": "porto", "source": "archive/x.pdf"},
            {"id": "L2", "doc_date": "2026-02-02", "payment_date": "2026-02-02",
             "direction": "expense", "doc_type": "invoice", "counterparty": "ACME",
             "net": "20.00", "vat_rate": "19", "gross": "23.80", "vat_treatment": "standard",
             "category": "software", "source": "archive/y.pdf"}]
    root = build_project(tmp_path / "broken-entry", "regular", ledgers={"2026": rows},
                         master=master)
    assert report_of(root, 2026, 1)
    result = run_generator(root)
    assert result.returncode == 0, result.stdout + result.stderr
    text = dom(generated_page(root)).by_id("view-euer").text()
    assert "Software" in text and "porto" in text, text[:400]


def test_a_ledger_write_renders_the_finance_page(tmp_path):
    """BUG-0201: a booking moves the page, because the ledger hook starts the generator.

    The ledger has no kernel writer, so both of its write paths pass exactly one place --
    `gate_ledger_valid.handle_post_tool_use` -- and that handler validated the changed file and did
    nothing else. The page was therefore as old as its last run by hand, and the masthead cannot
    tell anyone so: it prints the youngest date the ledger carries, which a back-dated booking
    leaves byte-identical.

    Driven as the REAL hook process with the payload the provider sends, in a project built from
    the shipped kit, so what is measured is the shipped handler and not a function call. Two halves:
    the page appears where there was none, and a SECOND booking moves it again -- the second is
    what a run that merely happened once would not show.
    """
    pytest.importorskip("yaml")
    root = build_project(tmp_path / "rendered", "regular")
    ledger = [name for name in sorted(os.listdir(os.path.join(root, "ledger")))
              if name.endswith(".csv")][0]
    ledger_path = os.path.join(root, "ledger", ledger)
    page = os.path.join(root, OUTPUT_REL)
    assert not os.path.exists(page)

    def edited():
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "cwd": root,
                   "tool_input": {"file_path": ledger_path}}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=root, HARNESS_KERNEL_PATH=os.path.dirname(KERNEL))
        return subprocess.run(
            [sys.executable, os.path.join(OFFICE_HOOKS, "gate_ledger_valid.py")],
            input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=180)

    edited()
    assert os.path.isfile(page), "no page after a ledger edit"
    first = open(page, encoding="utf-8").read()

    with open(ledger_path, "a", encoding="utf-8", newline="") as handle:
        handle.write("L2026-9999,2026-11-01,2026-11-01,expense,invoice,ZZZ,R-9,100.00,19.00,"
                     "119.00,standard,porto,archive/z.pdf,," + chr(10))
    edited()
    assert open(page, encoding="utf-8").read() != first, "the page did not follow the booking"

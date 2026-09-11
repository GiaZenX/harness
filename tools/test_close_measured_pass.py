"""PR-0012 AC-2: the re-run tool measured against the RUNNING script, never against its text.

Every test here drives `close_measured_pass.main` or one of its readers over a table and a state
directory built for the case, with `ROOT` pointed at a tree whose pytest nodes are this file's own
fixtures -- so what is measured is the pass/fail decision, the Evidence it does and does not write,
and the batch lines it prints.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "team-kits"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import close_measured_pass as tool  # noqa: E402
from kernel import approvals, report  # noqa: E402
from kernel.state import ProjectState  # noqa: E402

PR_BODY = {"title": "Kasse", "class": "normal", "priority": "high", "problem": "p", "goal": "g",
           "acceptance_criteria": [{"id": "AC-1", "text": "t"}],
           "invariants": ["i"], "out_of_scope": ["o"]}

HEADER = "| Item | Stand | Loch | Verdikt | Evidenz | Gemessene Zeile | Titel |\n|---|---|---|---|---|---|---|\n"


def _row(item_id, verdict, node=None, counts="1/1 passed"):
    measured = "%s, first: %s" % (counts, node) if node else ""
    return "| %s | TRIAGED | - | %s | - | %s | a defect |\n" % (item_id, verdict, measured)


def _table(tmp_path, rows):
    path = tmp_path / "survey-table.md"
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# a survey\n\n" + HEADER + "".join(rows))
    return str(path)


def _tree(tmp_path, naming=None):
    """A tiny tree under `tools/` carrying one test per named defect, passing or failing.

    `naming` maps a defect id to the outcome of the test that NAMES it, so a case can plant exactly
    the shape it is about: a defect a green test names, one a red test names, one nothing names.
    """
    tree = tmp_path / "tree"
    (tree / "tools").mkdir(parents=True)
    body = ["def test_still_holds():\n    assert True\n"]
    for item_id, outcome in sorted((naming or {}).items()):
        body.append('def test_names_%s():\n    """about %s"""\n    assert %s\n'
                    % (item_id.replace("-", "_").lower(), item_id, outcome))
    with io.open(str(tree / "tools" / "test_tiny.py"), "w", encoding="utf-8",
                 newline="\n") as handle:
        handle.write("\n\n".join(body))
    return str(tree)


def _node(item_id):
    return "tools/test_tiny.py::test_names_%s" % item_id.replace("-", "_").lower()


def _state(tmp_path, bugs):
    root = tmp_path / "project_memory"
    root.mkdir()
    state = ProjectState(str(root))
    goal = state.capture("PR", dict(PR_BODY))
    made = []
    for title in bugs:
        bug = state.capture("BUG", {"title": title, "related_pr": goal["id"], "observed": "o",
                                    "expected": "e", "repro": "r", "severity": "low",
                                    "acceptance_criteria": [{"id": "AC-1", "text": "t"}]})
        state.transition(bug["id"], "TRIAGED")
        made.append(bug["id"])
    return state, made


def test_a_row_whose_test_no_longer_passes_earns_no_evidence_and_is_reported(tmp_path, monkeypatch,
                                                                             capsys):
    """AC-2's sharpest line: the tool closes nothing it did not just measure. A row whose node fails
    today is written into the log as a failure, is named in the end lines, and stands in NO batch --
    and the store gains no Evidence that could walk it to VERIFIED behind our backs.

    RED WITHOUT the `result == PASSING` condition around `record_evidence`: the failing defect gets
    a passing Evidence, joins a batch line, and one answer of the user's closes a defect whose test
    is red on the current tree.
    """
    state, (good, bad) = _state(tmp_path, ["still repaired", "regressed"])
    monkeypatch.setattr(tool, "ROOT", _tree(tmp_path, {good: "True", bad: "False"}))
    table = _table(tmp_path, [_row(good, "MEASURED-PASS"), _row(bad, "MEASURED-PASS")])
    tool.main(["--table", table, "--state-root", state.root,
               "--log-dir", str(tmp_path / "log"), "--evidence"])
    printed = capsys.readouterr().out

    assert "no longer passes: %s" % bad in printed
    batch = [line for line in printed.splitlines() if line.startswith("python scripts/harness.py")]
    assert batch and all(bad not in line for line in batch), batch
    assert any(good in line for line in batch), batch

    verdicts = report.qa_verdicts(state, bad, report.CONFIRMATION_QUESTION)
    assert verdicts == {}, "a failing re-run wrote an Evidence -- it must write none"
    passing = report.qa_verdicts(state, good, report.CONFIRMATION_QUESTION)
    assert passing["test"]["result"] == "pass"


def test_a_pass_is_recorded_as_a_declared_selection_naming_the_node(tmp_path, monkeypatch):
    """AC-2: the Evidence is what BUG-0090's rule needs -- kind test, result pass, the bug named,
    the node as the run command, and the scope declared as the selection it is.

    RED WITHOUT `--run-scope selection` on the recorder's line: DEC-0061's delivery filter is the
    one that would then read the record, and the confirming edge finds nothing (BUG-0090 exactly).
    RED WITHOUT `--related`: the Evidence covers no item and confirms nothing.
    """
    state, (bug,) = _state(tmp_path, ["still repaired"])
    monkeypatch.setattr(tool, "ROOT", _tree(tmp_path, {bug: "True"}))
    table = _table(tmp_path, [_row(bug, "MEASURED-PASS")])
    tool.main(["--table", table, "--state-root", state.root,
               "--log-dir", str(tmp_path / "log"), "--evidence"])

    evidence_dir = os.path.join(state.root, "evidence")
    records = [state._read_yaml(os.path.join(evidence_dir, name))
               for name in os.listdir(evidence_dir) if name.startswith("EVD-")]
    assert len(records) == 1, records
    record = records[0]
    assert record["kind"] == "test" and record["result"] == "pass"
    assert bug in record["related"]
    assert record["run_scope"] == "selection"
    assert _node(bug) in record["run_command"]
    assert record["summary"] == "tests naming %s: 1 nodes, all passed" % bug
    # and the whole point of the shape: this record is what lets the batch be asked for at all
    assert approvals.verification_batch(state, [bug])[0][approvals.LISTED_EVIDENCE_FIELD] == \
        record["id"]


def test_only_measured_pass_rows_of_still_active_items_with_a_node_are_planned(tmp_path):
    """The reading of the survey, all four cases at once: a MEASURED-PASS row of an active item with
    a node is planned; another verdict is not a row of this run at all; an item that has since been
    archived cannot be closed; and a row naming no test is AC-3's route and is reported as such.

    RED WITHOUT the active filter: an archived id joins a batch and earns a refusal at request time.
    RED WITHOUT the node condition: `plan` returns a row with no test to run.
    """
    state, (active, other, unnamed) = _state(
        tmp_path, ["still open", "will be archived", "nothing names it"])
    state.transition(other, "REJECTED")
    state.archive(other)
    tree = _tree(tmp_path, {active: "True", other: "True"})
    table = _table(tmp_path, [_row(active, "MEASURED-PASS"), _row(other, "MEASURED-PASS"),
                              _row("BUG-0999", "MEASURED-OPEN"), _row(unnamed, "MEASURED-PASS")])
    todo, skipped = tool.plan(table, state.root, tree)

    assert todo == [(active, [_node(active)])], todo
    reasons = dict(skipped)
    assert "no longer active" in reasons[other], reasons
    assert "no test names it" in reasons[unnamed], reasons
    assert "BUG-0999" not in reasons, "a row of another verdict is not this run's business"


def test_the_log_is_the_resume_point_so_a_finished_row_is_not_measured_twice(tmp_path, monkeypatch,
                                                                            capsys):
    """The ~98 nodes do not fit one call, so the run has to be resumable -- and the resume point is
    the LOG the run itself writes, not a counter in memory.

    RED WITHOUT `already_done`: the second call re-measures every row, which on the real table is
    another six minutes of pytest and a second Evidence per defect.
    """
    state, (bug,) = _state(tmp_path, ["still repaired"])
    monkeypatch.setattr(tool, "ROOT", _tree(tmp_path, {bug: "True"}))
    table = _table(tmp_path, [_row(bug, "MEASURED-PASS")])
    log_dir = str(tmp_path / "log")
    tool.main(["--table", table, "--state-root", state.root, "--log-dir", log_dir])
    capsys.readouterr()
    tool.main(["--table", table, "--state-root", state.root, "--log-dir", log_dir])
    second = capsys.readouterr().out

    assert "(1 already in the log)" in second, second
    with io.open(os.path.join(log_dir, tool.LOG_NAME), encoding="utf-8", newline="") as handle:
        lines = [one for one in handle.read().splitlines() if one.strip()]
    assert len(lines) == 1, lines


def test_the_log_is_written_with_lf_endings_only(tmp_path, monkeypatch):
    """The host rule the generation-3 merge paid for: a file opened in text mode is rewritten with
    CRLF here, and the diff then shows the writer instead of the measurement.

    RED WITHOUT `newline="\\n"` on the log's open: the bytes carry CR on this host.
    """
    state, (bug,) = _state(tmp_path, ["still repaired"])
    monkeypatch.setattr(tool, "ROOT", _tree(tmp_path, {bug: "True"}))
    table = _table(tmp_path, [_row(bug, "MEASURED-PASS")])
    log_dir = str(tmp_path / "log")
    tool.main(["--table", table, "--state-root", state.root, "--log-dir", log_dir])
    with open(os.path.join(log_dir, tool.LOG_NAME), "rb") as handle:
        blob = handle.read()
    assert b"\r" not in blob, blob


def test_a_defect_the_same_goal_assigns_to_another_route_is_held_back_from_every_batch(
        tmp_path, monkeypatch, capsys):
    """Measured on the real records, 2026-09-11: four survey rows read MEASURED-PASS for defects
    PR-0012's OWN AC-3 lists as still to be fixed. The survey's verdict is a measurement, not a
    judgement (its header says so), so a batch built from it alone would have the user close, with
    one click, defects the goal that ordered the batch calls open.

    The rule is read out of the goal item, not written down in the tool -- so an id added to or
    removed from that criterion moves with no edit here.

    RED WITHOUT `held_back_by`: the id stands in a batch line, it is not reported as held back, and
    the reason nobody sees is that nothing said it.
    """
    state, (closable, claimed) = _state(tmp_path, ["really repaired", "claimed by AC-3"])
    monkeypatch.setattr(tool, "ROOT", _tree(tmp_path, {closable: "True", claimed: "True"}))
    goal = state.capture("PR", dict(
        PR_BODY, title="Bug-Null",
        acceptance_criteria=[{"id": "AC-1", "text": "the batch"},
                             {"id": "AC-3", "text": "%s is fixed red-first" % claimed}]))
    table = _table(tmp_path, [_row(one, "MEASURED-PASS") for one in (closable, claimed)])
    tool.main(["--table", table, "--state-root", state.root, "--log-dir", str(tmp_path / "log"),
               "--goal", goal["id"], "--other-route", "AC-3"])
    printed = capsys.readouterr().out

    assert "held back: %s" % claimed in printed, printed
    batch = [line for line in printed.splitlines() if line.startswith("python scripts/harness.py")]
    assert batch and all(claimed not in line for line in batch), batch
    assert any(closable in line for line in batch), batch
    # ...and the other end: hold nothing back, and the same row IS closable
    assert tool.held_back_by(state.root, goal["id"], "") == {}
    assert set(tool.held_back_by(state.root, goal["id"], "AC-3")) == {claimed}


def test_the_batch_lines_are_cut_at_the_kernels_own_limit_and_name_every_id_once():
    """The lines handed to the lead are the exact command the kernel accepts, cut at the length its
    own builder refuses to exceed -- and the number is the kernel's, read, not repeated here.

    RED WITHOUT `approvals.BATCH_LIMIT` as the cut (a literal 25 in the tool): the day the kernel's
    bound moves, the tool prints a line the builder refuses.
    """
    ids = ["BUG-%04d" % number for number in range(approvals.BATCH_LIMIT * 2 + 1)]
    lines = tool.batch_lines(ids)
    assert len(lines) == 3, lines
    named = []
    for line in lines:
        words = line.split("--batch", 1)[1].split()
        assert len(words) <= approvals.BATCH_LIMIT, line
        assert approvals.VERIFICATION_KIND in line.split("--batch", 1)[0]
        named += words
    assert named == sorted(ids), named


def test_a_node_that_never_answers_is_a_failure_and_not_a_pass(tmp_path, monkeypatch):
    """A timeout is not a measurement, so it must not become one: the row is logged as `timeout`,
    earns no Evidence and stands in no batch.

    RED WITHOUT the `TimeoutExpired` branch: the exception escapes the run and every remaining node
    of a ~98-row sequence goes unmeasured.
    """
    tree = _tree(tmp_path)
    with io.open(os.path.join(tree, "test_slow.py"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("import time\n\n\ndef test_never_answers():\n    time.sleep(30)\n")
    monkeypatch.setattr(tool, "ROOT", tree)
    result, spent, tail = tool.run_node("test_slow.py::test_never_answers", timeout=5.0)
    assert result == "timeout" and result != tool.PASSING, (result, tail)
    assert spent >= 4.0, spent


def test_the_active_filter_finds_the_store_the_kernel_actually_writes_into(tmp_path):
    """`active_ids` has to name the same directory the kernel captures into -- measured by capturing
    through the kernel and asking the reader, rather than by comparing two spellings of a path.

    RED WITHOUT the `ACTIVE_DIRS` lookup (a path written out in the tool): a layout change makes the
    filter match nothing, every row reads as "no longer active", and the run prints no batch at all
    while reporting success.
    """
    state, made = _state(tmp_path, ["one", "two"])
    assert tool.active_ids(state.root) == set(made)
    state.transition(made[0], "REJECTED")
    state.archive(made[0])
    assert tool.active_ids(state.root) == {made[1]}
    assert tool.active_ids(str(tmp_path / "nowhere")) == set()


def test_the_evidence_comes_from_the_tests_that_name_the_bug_and_from_no_other_node(tmp_path):
    """BUG-0090's rule read literally (DEC-0100 (3)), and the correction of the first cut: a defect
    closes on the tests that are ABOUT it, never on whatever node a survey row happened to quote
    first.

    Measured on the real records before the fix: BUG-0002 ("robocopy /MOVE reads as a copy") was
    quoted with `test_board.py::test_a_hostile_field_cannot_add_an_element_or_an_attribute_to_the_
    page`, and BUG-0074 with a node whose own docstring is about BUG-0071.

    All four shapes of "names it" in one tree: the docstring, a comment, a parametrize case id, and
    a neighbouring test that names a DIFFERENT id and must not be picked up.

    RED WITHOUT `nodes_naming`: the selection comes from the survey cell and this tree's own naming
    is invisible.
    RED WITHOUT the decorator span: the parametrize case id is outside the function body and its
    test is missed.
    RED WITHOUT the per-function attribution (a plain grep of the file): the module constant and the
    neighbour are attributed to whichever test follows them.
    """
    tree = tmp_path / "tree"
    (tree / "tools").mkdir(parents=True)
    with io.open(str(tree / "tools" / "test_shapes.py"), "w", encoding="utf-8",
                 newline="\n") as handle:
        handle.write(
            'import pytest\n\n'
            'NOTE = "BUG-0300 is named by a module constant and by no test"\n\n\n'
            'def test_by_docstring():\n    """closes BUG-0100"""\n    assert True\n\n\n'
            'def test_by_comment():\n    # the shape BUG-0100 left behind\n    assert True\n\n\n'
            '@pytest.mark.parametrize("case", ["BUG-0200"])\n'
            'def test_by_case_id(case):\n    assert case\n\n\n'
            'def test_about_something_else():\n    """closes BUG-0400"""\n    assert True\n')

    assert tool.nodes_naming("BUG-0100", str(tree)) == [
        "tools/test_shapes.py::test_by_comment", "tools/test_shapes.py::test_by_docstring"]
    assert tool.nodes_naming("BUG-0200", str(tree)) == ["tools/test_shapes.py::test_by_case_id"]
    assert tool.nodes_naming("BUG-0400", str(tree)) == [
        "tools/test_shapes.py::test_about_something_else"]
    assert tool.nodes_naming("BUG-0300", str(tree)) == [], "a module constant is no test"
    assert tool.nodes_naming("BUG-0999", str(tree)) == []


def test_a_defect_passes_only_when_every_test_that_names_it_passes(tmp_path, monkeypatch, capsys):
    """A defect measured by five tests of which one is red is not repaired, and closing it on the
    four green ones is the false verdict this whole route exists to avoid.

    RED WITHOUT the all-nodes loop (the first node deciding): the defect passes on its first green
    test, earns an Evidence, and stands in a batch line with a red test naming it.
    """
    state, (bug,) = _state(tmp_path, ["green and red at once"])
    tree = tmp_path / "tree"
    (tree / "tools").mkdir(parents=True)
    with io.open(str(tree / "tools" / "test_pair.py"), "w", encoding="utf-8",
                 newline="\n") as handle:
        handle.write('def test_a_green_one():\n    """%s"""\n    assert True\n\n\n'
                     'def test_a_red_one():\n    """%s"""\n    assert False\n' % (bug, bug))
    monkeypatch.setattr(tool, "ROOT", str(tree))
    table = _table(tmp_path, [_row(bug, "MEASURED-PASS")])
    tool.main(["--table", table, "--state-root", state.root,
               "--log-dir", str(tmp_path / "log"), "--evidence"])
    printed = capsys.readouterr().out

    assert "no longer passes: %s" % bug in printed, printed
    assert not [line for line in printed.splitlines()
                if line.startswith("python scripts/harness.py")], printed
    assert report.qa_verdicts(state, bug, report.CONFIRMATION_QUESTION) == {}


def test_a_defect_no_test_names_is_held_back_for_the_order_that_writes_one(tmp_path, monkeypatch,
                                                                          capsys):
    """The honest answer to "nothing measures this": it needs a closing test, not a click. It is
    reported by name, earns no Evidence, and stands in no batch.

    RED WITHOUT the empty-list branch of `plan`: the defect either joins a batch on somebody else's
    node, or -- with no node at all -- silently disappears from the report.
    """
    state, (named, unnamed) = _state(tmp_path, ["a test names it", "nothing names it"])
    monkeypatch.setattr(tool, "ROOT", _tree(tmp_path, {named: "True"}))
    table = _table(tmp_path, [_row(named, "MEASURED-PASS"), _row(unnamed, "MEASURED-PASS")])
    tool.main(["--table", table, "--state-root", state.root,
               "--log-dir", str(tmp_path / "log"), "--evidence"])
    printed = capsys.readouterr().out

    assert "skipped %s: no test names it" % unnamed in printed, printed
    batch = [line for line in printed.splitlines() if line.startswith("python scripts/harness.py")]
    assert batch and all(unnamed not in line for line in batch), batch
    assert any(named in line for line in batch), batch

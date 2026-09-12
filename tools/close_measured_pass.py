"""Re-run what the survey measured, record the proof, and print the batch questions (PR-0012 AC-2).

WHAT IT DOES: the survey of TSK-0131 marked 98 defects MEASURED-PASS. This takes each one that is
still active, finds THE TESTS THAT NAME IT (`nodes_naming`), runs every one of them on the current
tree, and records one Evidence per defect that passes them all -- because `VERIFIED` is reachable
only on a passing test Evidence covering the bug (BUG-0090's rule, DEC-0100 (3)).

THE SURVEY'S OWN NODE IS NOT USED, and that is the whole correction of the first cut: the table
quotes the FIRST node of whatever run the surveyor made, which need not be about that defect at all
(see `ID_COLUMN`'s comment for the two measured cases). An Evidence built from it asks the user to
close a defect on a run that never looked at it.

Three properties a hand run cannot hold:

  * ONE NODE AT A TIME, sequentially, each with its own timeout (the host rule); the defect passes
    only when EVERY test naming it passes, and the first failure ends its run;
  * NO EVIDENCE ON FAIL. Such a defect is REPORTED, never closed, and the absence of an Evidence is
    what keeps the batch question from being able to name it;
  * A DEFECT NO TEST NAMES IS HELD BACK, not guessed at. It needs a closing test, not a click, and
    it is listed for the order that writes one.

WHAT IT DOES NOT DO, on purpose: it never asks the user anything and never mints. It prints the
`request-approval verification --batch ...` lines, cut at `approvals.BATCH_LIMIT`, and the lead
relays them. The clicks are the user's.

THE LOG IS THE RESUME POINT. Every finished node is appended as one LF-terminated line, and a
second run reads that file back and skips what it already holds -- so a run that is interrupted (or
deliberately bounded with `--minutes`) continues instead of re-measuring.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# WHERE THE KERNEL LIVES, frozen at import: `ROOT` is the tree the NODES are relative to and a test
# points it at a tree of its own, while the kernel that records the Evidence is this repository's
# either way. One constant rather than a second `os.path.join(ROOT, ...)` inside the recorder, which
# is how the recorder would quietly follow a relocated ROOT and write nowhere.
TEAM_KITS = os.path.join(ROOT, "team-kits")
# NO BYTECODE INTO THE KIT TREE. Importing `kernel` from a script writes `team-kits/kernel/
# __pycache__`, which lands INSIDE the hashed hook bundle -- and a bundle whose hash moved is a
# project whose `kit_trust_state` drops to `hooks_trust_required` and whose spawns are refused
# until somebody runs the scaffold. That is why `validate.py` states the rule for itself and why
# the suites redirect the cache; a tool that imports the kernel owes it too
# (`tools/test_hooks_v2.py::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`).
sys.dont_write_bytecode = True
sys.path.insert(0, TEAM_KITS)

from kernel import approvals, naming_tests  # noqa: E402 -- after the kernel path is on sys.path
from kernel.backlog_types import ACTIVE_DIRS  # noqa: E402

MEASURED_PASS = "MEASURED-PASS"
# The verdict column and the id column of the survey table, by position in the pipe-delimited row.
# The survey's own `Gemessene Zeile` cell is NOT read for the node any more, and that is B2 of the
# first verification round: it quotes the FIRST node of whatever run the surveyor made, which need
# not measure that defect at all -- BUG-0002 ("robocopy /MOVE reads as a copy") was quoted with
# `test_board.py::test_a_hostile_field_cannot_add_an_element_or_an_attribute_to_the_page`, and
# BUG-0074 with a node whose docstring is about BUG-0071; 63 of the 98 rows quote runs of more than
# one node. An Evidence built that way asks the user to close a defect on a run that never looked at
# it. BUG-0090's rule is taken literally instead: a defect closes on the tests that NAME it.
ID_COLUMN, VERDICT_COLUMN = 0, 3
# WHERE A TEST THAT NAMES A DEFECT CAN LIVE, as the two surfaces this repository actually runs:
# `tools/test_*.py` and the gate suite under `.claude/hooks/`, which is deliberately outside
# `pytest tools/` (CLAUDE.md says so) and would otherwise be invisible to exactly the defects it is
# the only measurement of. A glob rather than a file list, so a new test module is covered.
TEST_SOURCES = ("tools/test_*.py", ".claude/hooks/test_gates.py")
PASSING = "pass"
LOG_NAME = "rerun.log"
# ONE RECORD PER LINE, and the fields separated by a character no pytest node and no id contains,
# so the resume reader can split a line back apart without a parser.
FIELD = " | "


def survey_rows(path):
    """The table's data rows as lists of cells -- the rows that begin with a BUG id and nothing else.

    Read off the rendered table rather than off a parsed structure because the table IS the record
    (`project_memory/staging/TSK-0131/survey-table.md`); what is parsed here is its row shape, not
    its prose.
    """
    # A TABLE THAT IS NOT THERE IS A SENTENCE, NEVER A TRACEBACK. This tool's defaults ARE this
    # repository's records, so a caller that gives it no arguments at all -- the import probe of
    # `tools/test_hooks_v2.py::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`
    # is one, and so is a copy of this tree without the staging directory -- reached an unguarded
    # `io.open` and died on its way in. A tool that dies on import cannot be measured for anything
    # else, which is what that test went red for.
    if not os.path.isfile(path):
        raise SystemExit(
            "no survey table at %s. Remedy: pass --table <path to the survey table>; this tool "
            "reads the table as the record it is and invents no rows." % path)
    rows = []
    with io.open(path, encoding="utf-8", newline="") as handle:
        for line in handle:
            if not line.startswith("| BUG-"):
                continue
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def active_ids(state_root, item_type="BUG"):
    """The ids of `item_type` still ACTIVE in this store -- what the survey has to be filtered by.

    Asked of `backlog_types.ACTIVE_DIRS`, not of a path spelled here: a row whose item has since
    been archived (closed, rejected, merged away) is not a defect anybody can still close, and
    putting it in a batch would only earn a refusal at request time.
    """
    directory = os.path.join(state_root, *ACTIVE_DIRS[item_type].split("/"))
    if not os.path.isdir(directory):
        return set()
    return {name[:-5] for name in os.listdir(directory) if name.endswith(".yaml")}


def nodes_naming(item_id, root=None, sources=TEST_SOURCES):
    """Every pytest node whose test NAMES `item_id` -- sorted, possibly empty.

    THIS IS BUG-0090'S RULE READ LITERALLY: a defect reaches VERIFIED on a passing test Evidence
    that covers it, and what makes a test cover a defect is that the test is ABOUT it.

    THE DERIVATION IS THE KERNEL'S (`kernel.naming_tests`), not this tool's, and that is round 1's
    F2: `approvals.batch_walk_blockers` has to ask the same question about an evidence's run before
    a click closes anything, and two readers of "a test names this item" would answer differently
    the day one of them was tightened -- which is exactly what happened when this tool accepted an
    id ANYWHERE in a test's span while H195 had already measured that an incidental mention is not
    a naming. One module, two callers: this one SEARCHES, the kernel CHECKS.

    WHAT IT DELIBERATELY DOES NOT DO is guess. A defect no test names comes back as an empty list,
    and the caller HOLDS IT BACK: such a defect needs a closing test, not a click.
    """
    return naming_tests.nodes_naming(item_id, ROOT if root is None else root, sources)


def plan(table, state_root, root=None):
    """([(id, [nodes])] to re-run, [(id, reason)] that cannot be) -- the reading of the survey."""
    active = active_ids(state_root)
    todo, skipped = [], []
    for row in survey_rows(table):
        item_id = row[ID_COLUMN]
        if row[VERDICT_COLUMN] != MEASURED_PASS:
            continue
        if item_id not in active:
            skipped.append((item_id, "no longer active -- nothing to close"))
            continue
        nodes = nodes_naming(item_id, root)
        if not nodes:
            skipped.append((item_id, "no test names it -- it needs a closing test, not a click"))
            continue
        todo.append((item_id, nodes))
    return todo, skipped


def already_done(log_path):
    """{id: result} out of the log -- the resume point, read from the file the run itself writes."""
    done = {}
    if not os.path.isfile(log_path):
        return done
    with io.open(log_path, encoding="utf-8", newline="") as handle:
        for line in handle:
            parts = line.strip().split(FIELD)
            if len(parts) >= 3 and parts[0].startswith("BUG-"):
                done[parts[0]] = parts[2]
    return done


def run_node(node, timeout):
    """One pytest NODE, once, with its own clock. Returns (result, seconds, last line)."""
    started = time.time()
    line = [sys.executable, "-B", "-m", "pytest", node, "-q", "--no-header",
            "-p", "no:cacheprovider"]
    try:
        done = subprocess.run(line, cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", time.time() - started, "no verdict within %ss" % timeout
    spent = time.time() - started
    tail = [one.strip() for one in (done.stdout + done.stderr).splitlines() if one.strip()]
    return (PASSING if done.returncode == 0 else "fail"), spent, (tail[-1] if tail else "")


def run_command_for(nodes):
    """The line an auditor re-runs to reproduce this defect's verdict: every node that names it.

    The nodes are RUN one at a time, each with its own clock (the host rule), and recorded as this
    single line -- which produces the same verdict and is what a person would type. The count in the
    summary and the node list here are the same measurement said twice for two readers, not two
    measurements.
    """
    return "python -B -m pytest %s -q" % " ".join(nodes)


def record_evidence(state_root, item_id, nodes, artifact):
    """The measurement, through the kernel -- the only writer of canonical state.

    `--run-scope selection` because that is what it IS: the tests that NAME this defect, run on the
    current tree. Since DEC-0071 a declared selection confirms the bug it names while still opening
    no merge, which is the reading BUG-0090 bought -- so the honest declaration is also the one that
    works. Returns the EVD id, or "" when the kernel refused.

    THE SUMMARY SAYS WHAT WAS MEASURED, because that sentence is what a later reader has instead of
    the run: "tests naming BUG-nnnn: k nodes, all passed". The first cut said "re-run of the node
    TSK-0131 measured" about a node that in 63 of 98 cases was simply the first of somebody else's
    run -- a sentence that was true about the survey and false about the defect.
    """
    done = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", state_root, "evidence",
         "--kind", "test", "--result", PASSING, "--related", item_id,
         "--summary", "tests naming %s: %d nodes, all passed" % (item_id, len(nodes)),
         "--artifact-ref", artifact, "--run-command", run_command_for(nodes),
         "--run-scope", "selection"],
        env=dict(os.environ, PYTHONPATH=TEAM_KITS),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if done.returncode != 0:
        return ""
    return (done.stdout.split() or [""])[0]


ID_RX = re.compile(r"\bBUG-\d{4}\b")


def held_back_by(state_root, goal_id, criterion_id):
    """The defect ids the SAME goal has already assigned to another route -- ({} when it has none).

    WHY THIS EXISTS, measured 2026-09-11: the survey's verdict is a MEASUREMENT and not a judgement
    (its own header says so), and four rows read MEASURED-PASS for defects PR-0012's AC-3 lists as
    still to be fixed -- BUG-0058, BUG-0074, BUG-0075, BUG-0076. Putting those into a batch would
    have the user close, with one click, four defects the goal that ordered the batch says are open;
    that is the "stock lies" defect this goal exists to remove, pointed the other way.

    IT IS READ OUT OF THE RUNNING ITEM, not written down here, which is what makes it a rule rather
    than a list: whatever ids the goal's other criterion names are the ids this route holds back,
    and an id added to or removed from that criterion moves with no edit. The reason travels with
    the id so the report can say WHY each one was held back.
    """
    path = os.path.join(state_root, "product", "active", "%s.yaml" % goal_id)
    if not (goal_id and criterion_id and os.path.isfile(path)):
        return {}
    sys.path.insert(0, TEAM_KITS)
    from kernel.state import ProjectState

    item = ProjectState(state_root)._read_yaml(path)
    for criterion in item.get("acceptance_criteria") or []:
        if isinstance(criterion, dict) and criterion.get("id") == criterion_id:
            return {found: "%s %s names it as a defect still to be fixed" % (goal_id, criterion_id)
                    for found in ID_RX.findall(str(criterion.get("text") or ""))}
    return {}


def batch_lines(ids, limit=None):
    """The exact `request-approval verification --batch ...` lines, cut at the kernel's own limit.

    The number comes from `approvals.BATCH_LIMIT` and is not repeated here: the builder refuses a
    longer list, so a second copy of the number would only ever be the one that is wrong.
    """
    limit = approvals.BATCH_LIMIT if limit is None else limit
    ids = sorted(ids)
    return ["python scripts/harness.py request-approval %s --batch %s"
            % (approvals.VERIFICATION_KIND, " ".join(ids[start:start + limit]))
            for start in range(0, len(ids), limit)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--table", default=os.path.join(
        ROOT, "project_memory", "staging", "TSK-0131", "survey-table.md"))
    parser.add_argument("--state-root", default=os.path.join(ROOT, "project_memory"))
    parser.add_argument("--log-dir", default=os.path.join(
        ROOT, "project_memory", "staging", "TSK-0138"))
    parser.add_argument("--timeout", type=float, default=180.0,
                        help="seconds one node may take before it counts as no verdict")
    parser.add_argument("--minutes", type=float, default=None,
                        help="stop cleanly after this many minutes; the log is the resume point")
    parser.add_argument("--evidence", action="store_true",
                        help="record an EVD through the kernel for every node that passes")
    parser.add_argument("--plan-only", action="store_true",
                        help="print what would run, measure nothing")
    # THE GOAL'S OWN OTHER ROUTE (see `held_back_by`). Defaulted like the table and the state root
    # above -- this script's defaults ARE this repository's records -- and overridable, because the
    # rule is "the goal's other criterion", not "PR-0012".
    parser.add_argument("--goal", default="PR-0012")
    parser.add_argument("--other-route", default="AC-3",
                        help="the acceptance criterion of --goal whose named defects this route "
                             "must NOT close; pass an empty value to hold nothing back")
    args = parser.parse_args(argv)

    todo, skipped = plan(args.table, args.state_root)
    log_path = os.path.join(args.log_dir, LOG_NAME)
    artifact = os.path.relpath(log_path, args.state_root).replace(os.sep, "/")
    done = already_done(log_path)
    print("rows to re-run: %d (%d already in the log), %d node(s) total, skipped: %d"
          % (len(todo), len([one for one, _ in todo if one in done]),
             sum(len(nodes) for _one, nodes in todo), len(skipped)))
    for item_id, reason in skipped:
        print("  skipped %s: %s" % (item_id, reason))
    if args.plan_only:
        for item_id, nodes in todo:
            print("  %s %d node(s): %s" % (item_id, len(nodes), " ".join(nodes)))
        return 0

    os.makedirs(args.log_dir, exist_ok=True)
    deadline = None if args.minutes is None else time.time() + args.minutes * 60.0
    for item_id, nodes in todo:
        if item_id in done:
            continue
        if deadline is not None and time.time() > deadline:
            print("stopping on the clock: %d of %d rows still to run"
                  % (len(todo) - len(done), len(todo)))
            break
        # ONE NODE AT A TIME with its own clock (the host rule), and the defect passes only when
        # EVERY test that names it passes: a defect measured by five tests of which one is red is
        # not repaired, and closing it on the four that are green is the false verdict this whole
        # route exists to avoid. The first failure ends the defect's run -- there is nothing left to
        # learn, and the remaining nodes would only spend the clock.
        spent, tail, result = 0.0, "", PASSING
        for node in nodes:
            outcome, seconds, line = run_node(node, args.timeout)
            spent += seconds
            if outcome != PASSING:
                result, tail = outcome, "%s: %s" % (node, line)
                break
            tail = line
        evidence = ""
        if result == PASSING and args.evidence:
            evidence = record_evidence(args.state_root, item_id, nodes, artifact)
        with io.open(log_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(FIELD.join([item_id, " ".join(nodes), result, evidence or "-",
                                     "%.1fs" % spent, tail]) + "\n")
        done[item_id] = result
        print("%s %s %s (%d nodes, %.1fs)" % (item_id, result, evidence or "-", len(nodes), spent))

    held = held_back_by(args.state_root, args.goal, args.other_route)
    passed = sorted(one for one, result in done.items() if result == PASSING)
    failed = sorted(one for one, result in done.items() if result != PASSING)
    closable = [one for one in passed if one not in held]
    print("\n-- END --")
    print("measured: %d, still passing: %d, no longer passing: %d, held back: %d, "
          "left to run: %d" % (len(done), len(passed), len(failed),
                               len([one for one in passed if one in held]), len(todo) - len(done)))
    for item_id in failed:
        print("no longer passes: %s" % item_id)
    for item_id in passed:
        if item_id in held:
            print("held back: %s -- %s" % (item_id, held[item_id]))
    for line in batch_lines(closable):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

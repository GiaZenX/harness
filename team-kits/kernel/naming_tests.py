"""Which test NAMES a defect -- the one reader of DEC-0100 (3), for the kernel and for the tools.

WHY THIS IS A MODULE OF ITS OWN. Two questions are asked about the same property and they have
different subjects, so they were written twice and drifted at once. `tools/close_measured_pass.py`
SEARCHES: given a bug id, which nodes name it, so a round knows what to re-run. `approvals`
CHECKS: given an evidence's run command, do its nodes name the bug the batch wants to close. The
property under both -- "this test function names this item in a place a reader can point at" -- is
one fact, and `names_the_item` is where it lives. The search and the check are two callers of it.

WHAT COUNTS AS NAMING, and this is the half BUG-0279 / H195 measured: an id ANYWHERE in a test's
span is not a naming. A test whose docstring mentions a bug in passing, in a "see also" line or in
a paragraph about a neighbouring defect, would close that bug on a click. So the id has to stand
where a reader looks for the subject of a test:

  * the FIRST PARAGRAPH of the docstring -- the sentence that says what the test is about, or
  * a DECORATOR -- a `parametrize` case id or a marker, which is where a parametrised test puts the
    case it is about.

Anything else is a mention. That is a rule about where an author writes the subject, and it is the
convention every suite in this repository already follows.

WHAT THIS CANNOT SEE, said here rather than left to be found: a test that measures the defect
perfectly and never writes its id is invisible to both callers, and a test that names an id in its
first paragraph while measuring something else passes both. The second is what a reviewer is for;
the first is why `close_measured_pass` reports a bug with no naming node instead of guessing.
"""
from __future__ import annotations

import ast
import glob
import io
import os
import re

# A pytest node, as it stands on a command line: the file, then the test, then optionally a
# parametrisation. Only the first two are the FUNCTION; the case id after a further `[` belongs to
# one row of it and is dropped, because the source declares the function and not the row.
_NODE_RX = re.compile(r"(?<![\w./\\-])([\w./\\-]+\.py)::([A-Za-z_]\w*)(\[[^\]]*\])?")


def nodes_in(run_command) -> list:
    """Every pytest node a command line names, as (file, test) pairs joined by `::`, sorted.

    A COMMAND LINE and not a plan: what the evidence RECORDS is what was run, and a node is the one
    part of a pytest line that says which test. A line that names none -- a whole-file run, a `-k`
    selection, a directory -- comes back empty, and the caller decides what that means. For a
    verification batch it means "this evidence measured a run, not this defect" (DEC-0100 (3)).
    """
    found = {"%s::%s" % (match.group(1).replace("\\", "/"), match.group(2))
             for match in _NODE_RX.finditer(str(run_command or ""))}
    return sorted(found)


# ONE PARSE PER FILE, keyed on the file's identity ON DISK, because the callers ask about the same
# tree many times: a batch of 31 defects asks `nodes_naming` 31 times over 46 modules, and the
# unmemoised reading re-parsed ~15 000 lines of `test_hooks_v2.py` for every one of them -- measured
# at over nine minutes for a plan that prints in seconds with this cache. The key is the STAT and
# not the path, so a file rewritten between two calls is read again.
_PARSED = {}


def _declarations(path):
    """{test name: (first docstring paragraph, decorator source)} for one file -- memoised.

    Parsed with `ast`, never scanned: a hit attributed by line proximity lands on whichever test
    happens to follow a module-level constant. The decorators are read from the SOURCE text of the
    decorator list, so a `parametrize` case id -- which is data inside a call -- is covered without
    this having to understand the call.
    """
    try:
        stat = os.stat(path)
        key = (os.path.abspath(path), stat.st_size, stat.st_mtime_ns)
    except OSError:
        return {}
    if key in _PARSED:
        return _PARSED[key]
    found = {}
    text, tree = "", None
    try:
        with io.open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        tree = None               # a file pytest could not collect declares no test either
    if tree is not None:
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            document = ast.get_docstring(node) or ""
            decorators = "\n".join(ast.get_source_segment(text, one) or ""
                                   for one in node.decorator_list)
            found[node.name] = (document.split("\n\n")[0], decorators)
    _PARSED[key] = found
    return found


def _declaration_of(path, test_name):
    """(first docstring paragraph, decorator source) for one test, or None when it is not there."""
    return _declarations(path).get(test_name)


def names_the_item(path, test_name, item_id) -> bool:
    """Does this test name `item_id` in a place a reader looks for the test's SUBJECT?

    THE ONE DEFINITION both callers of this module decide on -- see the module docstring for the
    two places and for why an id anywhere else in the span is a mention and not a naming.
    """
    declaration = _declaration_of(path, test_name)
    if declaration is None:
        return False
    first_paragraph, decorators = declaration
    return str(item_id) in first_paragraph or str(item_id) in decorators


def declares(root, node) -> bool:
    """Does the test this node names EXIST in this checkout?

    Asked of the source and not of pytest, because the answer has to be available where no runner
    is: a node that resolves to nothing is a run nobody can repeat, and an evidence built on one
    measured whatever the author typed.
    """
    path, _sep, test_name = str(node).partition("::")
    if not test_name:
        return False
    return _declaration_of(os.path.join(root, path.replace("/", os.sep)), test_name) is not None


def nodes_naming(item_id, root, patterns) -> list:
    """Every node under `patterns` whose test names `item_id` -- the SEARCH caller's question."""
    found = []
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(root, pattern.replace("/", os.sep)))):
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            for name, (first_paragraph, decorators) in _declarations(path).items():
                if not name.startswith("test"):
                    continue
                if str(item_id) in first_paragraph or str(item_id) in decorators:
                    found.append("%s::%s" % (relative, name))
    return sorted(found)


def coverage_blocker(root, item_id, run_command) -> str:
    """Why this evidence does not close `item_id`, or "" when it does -- the CHECK caller's question.

    DEC-0100 (3) LITERALLY: the evidence's run has to name tests that NAME the bug. Two ways to
    fail, and they are different sentences because they need different repairs -- a node that
    resolves to nothing was never run, and a node that runs and does not name the defect measured
    something else.

    MEASURED, and it is why this check exists at all: a TRIAGED bug whose passing test evidence
    carried a run command naming a node that does not exist anywhere in the tree was walked to
    VERIFIED and archived by one click (verification round 1, F2).
    """
    nodes = nodes_in(run_command)
    if not nodes:
        return ("its evidence records a run that names no test node at all (%r), so it measured a "
                "RUN and not this defect (DEC-0100 (3))" % (str(run_command or "")[:120]))
    missing = [node for node in nodes if not declares(root, node)]
    if missing:
        return ("its evidence names %s, which resolves to no test in this checkout -- a run "
                "nobody can repeat" % ", ".join(sorted(missing)[:3]))
    naming = [node for node in nodes
              if names_the_item(os.path.join(root, node.split("::")[0].replace("/", os.sep)),
                                node.split("::")[1], item_id)]
    if not naming:
        return ("its evidence names %s, and none of those tests NAMES %s where a reader looks for "
                "a test's subject (the docstring's first paragraph or a parametrize id) -- so the "
                "run measured something else (DEC-0100 (3), H195)"
                % (", ".join(sorted(nodes)[:3]), item_id))
    return ""

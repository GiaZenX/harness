"""Parallel specialists (FR-0021): the pre-dispatch check, and the claims the kit texts make.

WHAT THIS FILE HOLDS, in the order the round built it:

  * `tools/check_scope_overlap.py` -- the DEC-0062 (1)/(2) reading made mechanical for the
    workshop. Driven as a real process against work orders captured through the kernel, over a real
    git tree under `tmp_path`, never by calling its functions with hand-made dictionaries.
  * THE CLAIM THE KIT TEXTS MAKE about it: "nothing refuses an overlapping pair". That sentence
    stands in three constitutions and in the parallel-streams skill, so it is a test here rather
    than prose there -- and it is written so that it goes RED the day a refusal is built, which is
    the moment the sentence has to be corrected.
  * The wiring a reference skill needs when the role it names is the kit's SESSION AGENT: the
    dispatch header cannot deliver it, so a text that role reads has to.
  * N2 of the generation-2 merge: a role definition whose `description` restated a cadence its own
    body says lives in the code.

WHAT IT DOES NOT DO. It does not re-measure the mirror rule, the declaration contract or the
lead-in rule of the constitutions -- `tools/test_shared_skill_contract.py`,
`tools/test_reference_skills.py` and
`tools/test_role_contracts.py::test_a_paragraph_the_constitutions_share_is_one_text` own those, and
a second copy here would be a second answer to one question.
"""
import io
import json
import os
import re
import subprocess
import sys

import pytest

import conftest
from conftest import drive_task_to, satisfy_the_architect_step, walk_to_status
from test_reference_skills import _kit_dirs, _reference_skills  # noqa: E402 -- one derivation

ROOT = conftest.ROOT
TEAM_KITS = conftest.TEAM_KITS
KITS = ("dev-team", "office-team", "research-team")
CHECKER = os.path.join(ROOT, "tools", "check_scope_overlap.py")

yaml = pytest.importorskip("yaml")

sys.path.insert(0, TEAM_KITS)
from kernel import backlog_types, references  # noqa: E402

PR_FIELDS = {"title": "Checkout flow", "class": "normal", "problem": "no checkout",
             "goal": "working checkout",
             "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
             "invariants": [], "out_of_scope": [], "priority": "high",
             "user_story": "As a buyer I can pay"}
TSK_FIELDS = {"derives_from": "PR-0001", "type": "implementation",
              "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"],
              "required_inputs": [], "allowed_scope": ["src/**"], "forbidden_scope": [],
              "expected_outputs": ["src/x.py"], "dependencies": []}


# ================================================== the fixture: real orders, a real tree
def orders_project(tmp_path, scopes, files=(), status="READY"):
    """A git repo with `files` and one work order per entry of `scopes`, captured by the KERNEL.

    The orders go through `state.capture` and the root through `conftest.walk_to_status`, so the
    check below reads the field shapes the kernel really writes -- a hand-written work order would
    make every assertion here a statement about the fixture.

    `scopes` is [(allowed, forbidden)]; `files` are repo-relative paths that get a byte each, so
    `git ls-files -o` sees them.
    """
    from kernel.state import ProjectState

    repo = tmp_path / "repo"
    for relative in files:
        path = repo / relative
        os.makedirs(str(path.parent), exist_ok=True)
        io.open(str(path), "w", encoding="utf-8", newline="\n").write("x\n")
    os.makedirs(str(repo / "project_memory"), exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True,
                   capture_output=True, text=True)
    state = ProjectState(str(repo / "project_memory"))
    root = state.capture("PR", dict(PR_FIELDS))
    walk_to_status(state, root, "APPROVED")
    ids = []
    for allowed, forbidden in scopes:
        task = state.capture("TSK", dict(TSK_FIELDS, product_requirement=root["id"],
                                         allowed_scope=list(allowed),
                                         forbidden_scope=list(forbidden),
                                         root_revision=root["revision"]))
        ids.append(task["id"])
    # The architect step the goal's class asks for (FR-0085, DEC-0072), through the kernel's own
    # predicate: one ACCEPTED SR under the root covers every order under it, and without it no
    # order here could be leased at all. Before the walk, so a caller asking for READY gets orders
    # that a later `create_lease` can actually take.
    if ids:
        satisfy_the_architect_step(state, state.read_item(ids[0]), state.read_item(root["id"]))
    for task_id in ids:
        if status != "DRAFT":
            drive_task_to(state, task_id, status)
    return repo, state, ids


def check(repo, *extra):
    """Run the SHIPPED checker as a process, the way an orchestrator runs it."""
    return subprocess.run(
        [sys.executable, "-B", CHECKER, "--root", str(repo / "project_memory")] + list(extra),
        capture_output=True, text=True, timeout=120)


# ================================================== 1. the check itself
def test_two_orders_that_own_the_same_file_are_refused(tmp_path):
    """The case DEC-0062 (1) is about: two orders, one file, and the file exists today."""
    repo, _state, ids = orders_project(
        tmp_path, [(["src/**"], []), (["src/api/**"], [])], files=["src/api/handler.py"])
    result = check(repo)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "src/api/handler.py" in result.stdout, result.stdout
    assert "OVERLAP %s x %s" % (ids[0], ids[1]) in result.stdout, result.stdout


def test_two_orders_whose_scope_entries_differ_only_in_case_are_refused(tmp_path):
    """B1 of the first verification: the gate FOLDS both sides, so the check has to fold too.

    `gate_write_scope` never asks `_matches` about raw words -- the entry went through
    `_scope_entries` (`_norm(entry)`) and the path through `_repo_relative(..., fold=True)`
    (`_norm(rel)`), and `_norm` is normcase + slashes + `.lower()`. So `allowed_scope: ["Tools/**"]`
    and `["tools/**"]` are ONE scope at the door -- the gate lets both orders write `tools/foo.py`,
    which its own end measures as
    `tools/test_hooks_v2.py::test_a_case_mismatched_scope_entry_still_matches`. Measured before the
    fix: this pair was rc 0, "disjoint", while both specialists could have written the same file.

    THE FOLD IS TAKEN FROM THE GATE (`gate_write_scope._norm`), not spelled again here, for the
    same reason `_matches` is: two spellings of one rule drift, and this test would then measure
    the copy rather than the door.
    """
    repo, _state, ids = orders_project(
        tmp_path, [(["Tools/**"], []), (["tools/**"], [])], files=["tools/foo.py"])
    result = check(repo)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "tools/foo.py" in result.stdout, result.stdout
    assert "OVERLAP %s x %s" % (ids[0], ids[1]) in result.stdout, result.stdout


def test_two_orders_that_own_no_common_file_pass(tmp_path):
    """The other end: a cut that holds is not reported, so the check can say yes."""
    repo, _state, _ids = orders_project(
        tmp_path, [(["src/**"], []), (["docs/**"], [])],
        files=["src/api/handler.py", "docs/readme.md"])
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "disjoint" in result.stdout, result.stdout


def test_an_overlap_in_a_directory_that_is_still_empty_is_refused(tmp_path):
    """The half a file-resolving check alone cannot see, and the reason the witnesses exist.

    Both orders claim `src/**`; the tree holds no `src/` at all, so the intersection over real
    files is EMPTY and a check built on it would call this cut disjoint -- while the first file
    either order creates lands in both scopes.
    """
    repo, _state, _ids = orders_project(
        tmp_path, [(["src/**"], []), (["src/**"], [])], files=["docs/readme.md"])
    result = check(repo)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "witness" in result.stdout and "src/_" in result.stdout, result.stdout
    assert "    file " not in result.stdout, "a file was reported although the tree has none"


def test_a_forbidden_scope_takes_the_file_back_out_of_the_overlap(tmp_path):
    """`forbidden_scope` is asked first, as the gate asks it -- so an order that denies itself the
    shared subtree does not own it, and the pair is disjoint again."""
    repo, _state, _ids = orders_project(
        tmp_path, [(["src/**"], ["src/api/**"]), (["src/api/**"], [])],
        files=["src/api/handler.py", "src/core.py"])
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_declared_seam_is_shared_on_purpose_and_does_not_fail_the_check(tmp_path):
    """DEC-0062 (5): the files no order can own alone are declared, not eliminated.

    The same pair fails without the declaration and passes with it, and the declared paths are
    still PRINTED -- a seam that disappeared from the report would be a shared file nobody applies
    in the merge.
    """
    repo, _state, _ids = orders_project(
        tmp_path, [(["src/**", "notes/holes.md"], []), (["docs/**", "notes/holes.md"], [])],
        files=["src/a.py", "docs/b.md", "notes/holes.md"])
    assert check(repo).returncode == 2
    result = check(repo, "--seam", "notes/holes.md")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "seam      notes/holes.md" in result.stdout, result.stdout


def test_the_matcher_is_the_shipped_gates_own_and_not_a_second_spelling(tmp_path):
    """The reason this check imports `gate_write_scope._matches` instead of using `fnmatch`.

    A single `*` does NOT cross a directory separator in the gate (`_matches`, and its own comment
    says what it cost when it did), while `fnmatch.fnmatch("src/sub/b.py", "src/*")` is True. So
    these two orders are disjoint under the predicate the specialists actually meet and overlapping
    under the obvious substitute -- and this test is the one that goes red if the substitute ever
    creeps in. Both halves are asserted: the gate's answer, and that `fnmatch` really disagrees, so
    the case cannot quietly stop discriminating.
    """
    import fnmatch
    assert fnmatch.fnmatch("src/sub/b.py", "src/*"), "the substitute no longer disagrees here"
    repo, _state, _ids = orders_project(
        tmp_path, [(["src/*"], []), (["src/sub/**"], [])], files=["src/a.py", "src/sub/b.py"])
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_check_reads_the_orders_that_are_still_open(tmp_path):
    """"Open" is `backlog_types.is_terminal` and not a status word: an order that is finished owns
    nothing any more, and a pair whose only overlap is with a finished order is not a finding."""
    repo, state, ids = orders_project(
        tmp_path, [(["src/**"], []), (["src/**"], [])], files=["src/a.py"])
    assert check(repo).returncode == 2
    drive_task_to(state, ids[1], "CANCELLED")
    assert backlog_types.is_terminal("TSK", state.read_item(ids[1])["status"])
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    # ...and `--only` reaches it anyway, because a cut is judged before a status exists
    named = check(repo, "--only", ids[0], ids[1])
    assert named.returncode == 2, named.stdout + named.stderr


def test_a_route_the_caller_named_has_to_resolve_and_one_nobody_named_does_not(tmp_path):
    """M4 of the first verification, as the definition it was fixed with.

    A mistyped `--root` and a clean cut used to read the same: exit 0, because there was no pair.
    That is the shape a silent pass hides in. The line drawn is not "fewer than two orders is an
    error" -- that would break the tool being run with no arguments outside a project, which is how
    `tools/test_hooks_v2.py::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`
    drives it -- but: WHAT THE CALLER SPELLED OUT HAS TO RESOLVE. A named `--root` that is not a
    directory and an `--only` id no order carries are rc 1; a default root in a directory that is
    not a project is rc 0 and says NOTHING WAS COMPARED, never "disjoint".

    THE OTHER HALF IS CLOSED SINCE BUG-0225: a named route that DOES resolve and still yields no
    pair -- `--only` with a single real id -- is rc 1 as well, because `--only` is a request for a
    COMPARISON and answering 0 tells a script the cut was checked. The run nobody narrowed keeps
    its 0, which is the case two assertions above.
    """
    repo, _state, ids = orders_project(tmp_path, [(["src/**"], [])], files=["src/a.py"])
    state = str(repo / "project_memory")

    def run(*args, **environment):
        return subprocess.run([sys.executable, "-B", CHECKER] + list(args), capture_output=True,
                              text=True, timeout=120, cwd=environment.get("cwd"))

    named_typo = run("--root", state + "-typo")
    assert named_typo.returncode == 1, named_typo.stdout + named_typo.stderr
    assert "no such directory" in named_typo.stdout, named_typo.stdout

    unknown_id = run("--root", state, "--only", ids[0], "TSK-0404")
    assert unknown_id.returncode == 1, unknown_id.stdout + unknown_id.stderr
    assert "TSK-0404" in unknown_id.stdout, unknown_id.stdout

    for root in (str(tmp_path / "bare" / "project_memory"), state):
        os.makedirs(root, exist_ok=True)
        quiet = run("--root", root)
        assert quiet.returncode == 0, root + quiet.stdout + quiet.stderr
        assert "NOTHING WAS COMPARED" in quiet.stdout, (root, quiet.stdout)
        assert "disjoint" not in quiet.stdout, (root, quiet.stdout)

    # ...and the default root outside a project, which is the shape the bytecode test drives
    outside = run(cwd=str(tmp_path))
    assert outside.returncode == 0, outside.stdout + outside.stderr
    assert "NOTHING WAS COMPARED" in outside.stdout, outside.stdout

    # ...and the named route that resolves but cannot be a pair -- rc 1 since BUG-0225, told apart
    # from the refused cut's rc 2 and from the run nobody narrowed, which is rc 0 just above
    single = run("--root", state, "--only", ids[0])
    assert single.returncode == 1, single.stdout + single.stderr
    assert "NOTHING WAS COMPARED" in single.stdout and ids[0] in single.stdout, single.stdout


def test_a_seam_that_swallows_an_orders_whole_ownership_is_refused(tmp_path):
    """M5 of the first verification: a seam names shared FILES, not a whole ownership.

    `--seam "**"` turned a real collision -- two orders on `src/**`, sharing `src/a.py` -- into
    "seam only", rc 0. Declared that wide, the seam is not a declaration, it is the deletion of the
    check. So an order that owns NOTHING outside the seam is refused before any pair is judged.

    Both ends are here: the swallowing seam is refused, and the seam DEC-0062 (5) is actually about
    -- a named shared file beside ownership each order keeps -- still passes. The residue is named
    (`H143`): a seam that covers only PART of an overlap while both orders keep ownership elsewhere
    hides that part, and the last case measures it.

    WHICH REFUSAL, decided in the TSK-0120 merge round: `2`, not `1`. Two readers of this question
    were built in the same generation -- this workshop tool and `kernel.scopes` behind
    `harness.py check-scopes` -- and they answered a swallowing seam differently: the tool with
    `1` ("the check could not do what the caller spelled out") and the kernel with `2` (the seam is
    not subtracted at all, so the collision is reported as the collision it is). `2` is the true
    one: the check COULD run, and it found a shared file. The tool now has no predicate of its own
    -- it is the kernel verb with a command line in front of it -- so this measures the kernel's
    answer through the tool's route.
    """
    repo, _state, _ids = orders_project(
        tmp_path, [(["src/**"], []), (["src/**"], [])], files=["src/a.py"])
    for seam in ("**", "src/**"):
        result = check(repo, "--seam", seam)
        assert result.returncode == 2, (seam, result.stdout + result.stderr)
        assert "owning nothing of its own" in result.stdout, (seam, result.stdout)
        assert "src/a.py" in result.stdout, (seam, result.stdout)

    slice_repo, _state2, _ids2 = orders_project(
        tmp_path / "slice", [(["src/**", "notes/holes.md"], []),
                             (["lib/**", "notes/holes.md"], [])],
        files=["src/a.py", "lib/b.py", "notes/holes.md"])
    kept = check(slice_repo, "--seam", "notes/holes.md")
    assert kept.returncode == 0, kept.stdout + kept.stderr

    hidden_repo, _state3, _ids3 = orders_project(
        tmp_path / "hidden", [(["src/**", "lib/**"], []), (["src/**", "docs/**"], [])],
        files=["src/a.py", "lib/b.py", "docs/c.md"])
    hidden = check(hidden_repo, "--seam", "src/**")
    assert hidden.returncode == 0, hidden.stdout + hidden.stderr


def test_the_checker_leaves_no_bytecode_in_the_kit_tree_it_imports():
    """It reaches into `team-kits/` for the gate and the kernel, so it owes the same promise the
    stamper owes -- stated here as the property and measured against the RUNNING process by
    `tools/test_hooks_v2.py::test_a_repo_tool_that_imports_the_kit_tree_leaves_no_bytecode_in_it`,
    which found this file caching into the tree on its first run. What is asserted here is only
    that the switch is still in the module that has to carry it, read off the parse tree.
    """
    import ast
    with io.open(os.path.join(ROOT, "tools", "check_scope_overlap.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    switched = [node for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                and any(getattr(target, "attr", None) == "dont_write_bytecode"
                        for target in node.targets)
                and getattr(node.value, "value", None) is True]
    assert switched, "check_scope_overlap.py no longer switches bytecode writing off"


# ================================================== 2. what the kernel now enforces (C-2/C-3)
def test_the_lease_refusal_reaches_a_region_no_single_witness_reaches(tmp_path):
    """BUG-0238 and BUG-0218 where they meet: the lease refusal inherits `kernel.scopes` whole.

    The refusal is not a second reading of "do these two collide" -- it asks `scopes`, so a repair
    there arrives here with no edit. This is that arrival, over the EMPTY tree: `a/*x` and `a/y*`
    share `a/yx`, no single-entry witness lands in it, no such file exists, and the second lease is
    refused naming the path. Before the pair witnesses it was granted, and the two builders met in
    the merge.

    WHAT STAYS OUTSIDE THE REFUSAL, and the second half of this test is what makes that a division
    of labour rather than a gap: two READY orders that are never leased at the same time share no
    lease, so nothing here sees them -- and `check-scopes` does, because it walks the OPEN orders.
    Both are asserted, so neither can be claimed without the other.
    """
    from kernel import dispatch, scopes

    _repo, state, ids = orders_project(
        tmp_path, [(["a/*x"], []), (["a/y*"], [])], files=[], status="READY")
    dispatch.create_lease(state, ids[0])
    with pytest.raises(Exception) as refusal:
        dispatch.create_lease(state, ids[1])
    assert "a/yx" in str(refusal.value), refusal.value
    assert ids[0] in str(refusal.value), refusal.value

    # ...and the same two orders, with NO lease taken at all, are invisible to the refusal and
    # visible to the check that walks open orders
    _repo2, other, other_ids = orders_project(
        tmp_path / "second", [(["a/*x"], []), (["a/y*"], [])], files=[], status="READY")
    code, lines = scopes.check(other)
    assert code == 2, lines
    assert any("a/yx" in line for line in lines), lines
    assert all(other.read_item(one)["status"] == "READY" for one in other_ids)


def test_the_second_lease_is_refused_when_the_scopes_overlap(tmp_path):
    """PR-0005 AC-5 / stream D's C-2, and it replaces the sentence this file used to measure.

    UNTIL 2026-09-04 THIS TEST ASSERTED THE OPPOSITE. It was called
    `test_nothing_shipped_refuses_two_tasks_whose_scopes_overlap` and it drove two orders with the
    SAME `allowed_scope` to LEASED to show that the kernel had no opinion about two tasks -- the
    claim three constitutions and the parallel-streams skill make. It was written to go red the day
    a refusal was built, and this is that day; the paragraphs it stood for are the seam handed to
    G4-3.

    THE REAL LIFECYCLE AND NOTHING ELSE: the leases are minted through
    `kernel.dispatch.create_lease`, the only route to one there is, over a real git tree under
    `tmp_path`. The refusal has to NAME the shared path, because "you collide" without the file is
    not a repair anybody can act on.
    """
    from kernel import dispatch

    _repo, state, ids = orders_project(
        tmp_path, [(["src/**"], []), (["src/**"], [])], files=["src/a.py"], status="READY")
    first = dispatch.create_lease(state, ids[0])
    assert first["task_id"] == ids[0]
    with pytest.raises(Exception) as refusal:
        dispatch.create_lease(state, ids[1])
    assert "src/a.py" in str(refusal.value), refusal.value
    assert ids[0] in str(refusal.value), refusal.value
    assert state.read_item(ids[1])["status"] == "READY", "the refused order was moved anyway"


def test_a_seam_both_orders_declare_lets_the_second_lease_through(tmp_path):
    """The other end of the same rule, so the refusal cannot be satisfied by refusing everything.

    A path BOTH orders declare in `seam_scope` is shared on purpose and applied in the merge round
    (DEC-0062 (5)), so it is subtracted before the verdict -- by `kernel.scopes`, which is where
    that rule lives, and not by a second reading inside `dispatch`. Each order still owns a file of
    its own, which is what keeps the declaration a seam rather than a scope handed over
    (`kernel.scopes.owns_anything_outside`).
    """
    from kernel import dispatch
    from kernel.scopes import SEAM_FIELD

    _repo, state, ids = orders_project(
        tmp_path, [(["src/**", "notes/holes.md"], []), (["lib/**", "notes/holes.md"], [])],
        files=["src/a.py", "lib/b.py", "notes/holes.md"], status="DRAFT")
    for one in ids:
        state.update_item(one, {SEAM_FIELD: ["notes/holes.md"]})
        drive_task_to(state, one, "READY")
    dispatch.create_lease(state, ids[0])
    assert dispatch.create_lease(state, ids[1])["task_id"] == ids[1]


def test_the_lease_carries_the_tree_it_was_granted_for(tmp_path):
    """PR-0005 AC-5 / stream D's C-3, and it replaces `test_the_lease_carries_no_tree_of_its_own`.

    That test asserted that no key of a lease names a checkout, which was the honest reading while
    "one tree per order" lived in the lead's head: a lease named a task and nothing else, so no
    reader could say which tree an order was being worked in. It was written to go red the day the
    field existed.

    BOTH ENDS, because a field that always carries the same value answers nothing: the DEFAULT is
    the tree the state directory lives in -- true for every project that runs in one -- and a
    caller working in its own checkout against a shared state directory names that one, which is
    the case the field exists for. Read off the lease the kernel really writes.
    """
    from kernel import dispatch

    repo, state, ids = orders_project(
        tmp_path, [(["src/**"], []), (["lib/**"], [])], files=["src/a.py", "lib/b.py"],
        status="READY")
    default = dispatch.create_lease(state, ids[0])
    assert os.path.normcase(default[dispatch.WORKTREE_FIELD]) == os.path.normcase(str(repo))

    elsewhere = tmp_path / "second-checkout"
    os.makedirs(str(elsewhere), exist_ok=True)
    named = dispatch.create_lease(state, ids[1], worktree=str(elsewhere))
    assert os.path.normcase(named[dispatch.WORKTREE_FIELD]) == os.path.normcase(str(elsewhere))
    assert named[dispatch.WORKTREE_FIELD] != default[dispatch.WORKTREE_FIELD]


def test_a_work_order_carries_exactly_one_product_requirement(tmp_path):
    """The claim the shared constitution paragraph makes about the KERNEL, measured on it.

    The paragraph says a work order is given exactly one goal, which is why a bundle belongs at the
    goal and not inside the order (`DEC-0067`). That is a statement about the kernel's contract, so
    it is a test rather than a sentence: `product_requirement` is a REQUIRED field of a `TSK` and
    one of its two PARENT fields -- the binding to the item it hangs from -- and the running
    producer takes one id there and cannot take a list.

    ASKED OF THE PRODUCER, not of the table: `dispatch.create_task` is the only route a kit has to
    a work order, and it is what a list meets. Today it meets the id parser, which raises rather
    than composing a remedy -- the refusal is ungraceful, and that is what "cannot represent" looks
    like; the day the kernel learns to carry several goals, the list is accepted, this goes RED,
    and the paragraph in all three constitutions is the one to correct.
    """
    from kernel import backlog_types, dispatch
    from kernel.state import ProjectState

    assert "product_requirement" in backlog_types.REQUIRED_FIELDS["TSK"]
    assert "product_requirement" in backlog_types.PARENT_FIELDS["TSK"]

    os.makedirs(str(tmp_path / "project_memory"))
    state = ProjectState(str(tmp_path / "project_memory"))
    roots = []
    for title in ("first goal", "second goal"):
        root = state.capture("PR", dict(PR_FIELDS, title=title))
        walk_to_status(state, root, "APPROVED")
        roots.append(root["id"])
    fields = dict(TSK_FIELDS)
    fields.pop("derives_from")

    with pytest.raises(Exception):
        dispatch.create_task(state, dict(fields, product_requirement=list(roots),
                                         derives_from=list(roots)))
    accepted = dispatch.create_task(state, dict(fields, product_requirement=roots[0],
                                                derives_from=roots[0]))
    assert accepted["product_requirement"] == roots[0]


# ================================================== 3. the skill and the texts that reach it
def _session_agent(kit):
    """The role a session of this kit STARTS as, read off the settings the provider reads."""
    with io.open(os.path.join(TEAM_KITS, kit, "settings", "settings.json"),
                 encoding="utf-8") as handle:
        return json.load(handle).get("agent")


_CODEX_ROUTE = re.compile(r"\.agents/skills/([a-z0-9][a-z0-9-]*)/SKILL\.md")


def _texts_a_session_agent_reads(kit):
    """The files a session of `kit` can reach without a dispatch header: its constitution, its own
    role definition, and its own procedure skill. Everything else arrives on a work order."""
    agent = _session_agent(kit)
    for relative in (("constitution", "AGENTS.md"),
                     ("agents", "%s.md" % agent),
                     ("skills", agent, "SKILL.md")):
        path = os.path.join(TEAM_KITS, kit, *relative)
        if os.path.isfile(path):
            with io.open(path, encoding="utf-8") as handle:
                yield path, handle.read()


def test_a_reference_skill_named_for_a_session_agent_is_named_by_a_text_it_reads():
    """A declaration that names the session agent promises a delivery the dispatch cannot make.

    `kernel.references.for_task` stamps the reference names onto a LEASE (`create_lease`,
    `REFERENCES_KEY`), and a session agent is bound by `settings.json` `agent:` without one. So for
    that role the declaration is a statement about where the skill BELONGS, and the only thing that
    can actually put it in front of the role is a text the role reads. Measured shape of the
    failure: `humanizer` named both kit leads for one release and no lead text named the route, so
    the skill was shipped, copied into every project and reachable by nobody it was declared for.
    """
    judged = 0
    for kit in KITS:
        agent = _session_agent(kit)
        assert agent, "%s registers no session agent" % kit
        kit_dir = os.path.join(TEAM_KITS, kit)
        declared = references.declarations(os.path.join(kit_dir, "skills"))
        routed = {name for _path, text in _texts_a_session_agent_reads(kit)
                  for name in _CODEX_ROUTE.findall(text)}
        for name, rule in sorted(declared.items()):
            if agent not in rule[references.ROLES_KEY]:
                continue
            judged += 1
            assert name in routed, (
                "%s declares `skills/%s` for %s, which is this kit's session agent and therefore "
                "never receives a dispatch header -- and no text that role reads (constitution, "
                "role definition, own procedure skill) spells its retrieval route, so it reaches "
                "the role nowhere" % (kit, name, agent))
    assert judged >= 3, "only %d declaration(s) named a session agent -- the reader stopped" % judged


def _kits_shipping(name):
    return [kit_dir for kit_dir in _kit_dirs()
            if os.path.isfile(os.path.join(kit_dir, "skills", name, "SKILL.md"))]


def test_the_parallel_procedure_is_declared_for_every_task_type():
    """The other end of the one enumeration this skill's declaration carries.

    The cut is made BEFORE the orders are typed, so the declaration names the whole vocabulary --
    and a vocabulary that grows would leave it a type short with nothing noticing. Derived from
    `backlog_types.TASK_TYPES`, so the day a type ships this is the failure and not a silence.
    """
    shipping = _kits_shipping("parallel-streams")
    assert shipping, "no kit ships skills/parallel-streams -- FR-0021's procedure is gone"
    for kit_dir in shipping:
        rule = references.declarations(os.path.join(kit_dir, "skills"))["parallel-streams"]
        assert rule[references.TASK_TYPES_KEY] == set(backlog_types.TASK_TYPES), (
            "%s: the parallel procedure declares %s and the kernel's vocabulary is %s"
            % (os.path.basename(kit_dir), sorted(rule[references.TASK_TYPES_KEY]),
               sorted(backlog_types.TASK_TYPES)))
        assert "parallel-streams" in _reference_skills(kit_dir), (
            "%s: a role has taken the parallel procedure into ownership" % kit_dir)


# ================================================== 4. N2 -- a cadence stated twice
# THE WORDS A ROLE TEXT STATES A RHYTHM IN -- the vocabulary stands here ONCE and the pattern is
# built from it, so the tripwire below can walk the entries instead of taking them apart again out
# of a compiled regex. `BUG-0224` is the limit of the whole construction and it is measured in
# `test_the_cadence_reader_is_an_enumeration_held_at_both_ends`, at both ends.
_CADENCE_WORDS = ("weekly", "wöchentlich", "daily", "täglich", "nightly", "monthly", "monatlich",
                  "quarterly", "every day", "every week", "every month", "every quarter",
                  "each day", "each week", "each month", "each quarter")
_CADENCE_IN_PROSE = re.compile(
    r"\b(?:%s)\b" % "|".join(word.replace(" ", r"\s+") for word in _CADENCE_WORDS), re.I)


def _blocks_naming(text, role):
    """Every blank-line-separated block of `text` that names `role` as a word.

    A BLOCK and not the whole file, because a constitution names dozens of roles and the question
    is about the passage that describes THIS one. The word boundary keeps `project-auditor` from
    matching inside a longer name.
    """
    pattern = re.compile(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])" % re.escape(role))
    return [block for block in re.split(r"\n[ \t]*\n", text) if pattern.search(block)]


def test_the_cadence_reader_is_an_enumeration_held_at_both_ends():
    """BUG-0224: `_CADENCE_IN_PROSE` is a list of adverbs, and a list needs a tripwire at BOTH ends.

    END ONE -- EVERY ENTRY EARNS ITS PLACE: for each word the vocabulary lists, a sentence built
    from it fires, and the SAME sentence against a pattern built WITHOUT that entry does not. That
    is the difference between "the word is there" and "the word is the reason": an entry another
    entry already covers passes the first reading and fails this one.

    END TWO -- THE BLIND SPELLINGS ARE ROWS AND NOT A DOCSTRING CLAIM, which is what this round
    changed: the five forms measured silent in TSK-0118's probe stand here as assertions, so the
    day somebody widens the reader they go RED and the limit is re-decided rather than drifting.
    "Is this sentence a cadence" is world knowledge no derivation from this tree produces -- a test
    that claimed otherwise would be the next enumeration -- so the blindness is DECLARED here
    instead of repaired.

    The cost, said plainly: a role text that writes the rhythm as `cadence: 7d` states it twice and
    no test says so.
    """
    assert len(_CADENCE_WORDS) >= 8, _CADENCE_WORDS
    for word in _CADENCE_WORDS:
        sentence = "the auditor runs %s and reports" % word
        assert _CADENCE_IN_PROSE.search(sentence), (
            "%r is listed and fires for nothing -- a dead entry" % word)
        without = re.compile(
            r"\b(?:%s)\b" % "|".join(other.replace(" ", r"\s+")
                                     for other in _CADENCE_WORDS if other != word), re.I)
        assert not without.search(sentence), (
            "%r is carried by another entry -- the sentence fires without it" % word)

    for blind in ("the auditor runs once a week",
                  "the auditor runs on Mondays",
                  "the auditor runs every seven days",
                  "the auditor runs each Monday morning",
                  "cadence: 7d"):
        assert not _CADENCE_IN_PROSE.search(blind), (
            "%r is now READ -- BUG-0224's limit changed, and it has to be re-decided rather than "
            "silently widened" % blind)


def test_no_text_that_describes_the_audited_role_states_the_cadence_the_code_owns():
    """N2 of the generation-2 merge, as a test rather than as a residue.

    THE SUBJECT IS DERIVED TWICE OVER: `_routine.AUDIT_ROLE` names the role whose recurring run the
    shipped code schedules, and `_routine.audit_period_id` IS the cadence -- it answers "has it run
    in this period" with an ISO week id. The texts held against that are the role's own definition
    and every constitution BLOCK that names it, so a passage that starts describing the role
    tomorrow is covered without an edit here.

    What stood before: the `description` of all three `agents/project-auditor.md` opened with
    "weekly / event-triggered" while the body of the same file said "Your cadence stands in the
    code and not a second time here" -- the same fact twice in ONE file, which is the mechanism
    that sentence was written to end -- and the office constitution's role row repeated it a third
    time. The description is the surface the ROUTER reads, so this is not cosmetic: a cadence that
    changes in the code would leave a wrong one on the routing surface of three kits at once.

    THE MIRRORED HOOK'S OWN MODULE DOCSTRING is the neighbouring subject and has its own reader
    since TSK-0140: `test_the_shipped_routine_module_claims_no_cadence_for_a_text_it_does_not_own`.
    """
    from test_routine_feed import routine_module
    judged = 0
    for kit in KITS:
        role = routine_module(kit).AUDIT_ROLE
        texts = [os.path.join(TEAM_KITS, kit, "agents", "%s.md" % role),
                 os.path.join(TEAM_KITS, kit, "constitution", "AGENTS.md")]
        for path in texts:
            with io.open(path, encoding="utf-8") as handle:
                text = handle.read()
            for block in _blocks_naming(text, role):
                judged += 1
                found = sorted({hit.group(0) for hit in _CADENCE_IN_PROSE.finditer(block)})
                assert not found, (
                    "%s states the audited role's cadence in prose (%s) while "
                    "`_routine.audit_period_id` is what decides it:\n%s"
                    % (os.path.relpath(path, ROOT), ", ".join(found), block[:400]))
    assert judged >= 2 * len(KITS), "only %d block(s) read -- the subject stopped matching" % judged


def test_the_shipped_routine_module_claims_no_cadence_for_a_text_it_does_not_own():
    """BUG-0220 / H137: the mirrored `hooks/_routine.py` said in its own module docstring that every
    kit's constitution rides the audited role on a weekly rhythm -- which none of the three does any
    more, so a shipped file asserted a cadence for three files it does not own and nothing read it.

    THE SUBJECT IS THE MODULE DOCSTRING AND NOTHING ELSE OF THE FILE, parsed rather than searched:
    the cadence legitimately stands in `audit_period_id`'s own docstring, because that function IS
    the cadence -- so a reader over the whole file would refuse the one place the rule allows. The
    module docstring is the place that speaks ABOUT other files, which is where house rule 3's
    "prefer naming a location over quoting another file" bites.

    THE CADENCE READER IS THE SAME ONE the role texts are judged by (`_CADENCE_IN_PROSE`), with the
    same measured blind spots (`BUG-0224` / H141: a period written as a number of days, a weekday or
    a duration token is invisible to it). Sharing it is the point -- a second spelling here would be
    a second answer to "does this sentence state a cadence".
    """
    import ast
    judged = 0
    for kit in KITS:
        path = os.path.join(TEAM_KITS, kit, "hooks", "_routine.py")
        with io.open(path, encoding="utf-8") as handle:
            module = ast.parse(handle.read())
        docstring = ast.get_docstring(module) or ""
        assert docstring, "%s carries no module docstring -- the subject stopped existing" % path
        judged += 1
        found = sorted({hit.group(0) for hit in _CADENCE_IN_PROSE.finditer(docstring)})
        assert not found, (
            "%s states a cadence (%s) in the docstring that speaks about OTHER files, while "
            "`audit_period_id` is the one place that owns it: %s"
            % (os.path.relpath(path, ROOT), ", ".join(found), docstring[:400]))
    assert judged == len(KITS), "only %d of %d kits read" % (judged, len(KITS))


@pytest.mark.parametrize("text,fires", [
    ("Project Auditor — weekly / event-triggered READ-ONLY reviewer", True),
    ("runs every week", True),
    ("wöchentlich, ohne Ausnahme", True),
    # ...and the class it does not read, measured rather than described (`H141`)
    ("eine wöchentliche Prüfung", False),
    ("runs once a week", False),
    ("on Mondays", False),
    ("every seven days", False),
    ("cadence: 7d", False),
    # ...and prose that must stay quiet whatever the reader learns
    ("the period one run covers", False),
    ("a run carrying this week id", False),
    ("READ-ONLY reviewer, dispatched per run on a routine approval", False),
])
def test_the_cadence_reader_reads_what_it_claims(text, fires):
    """The floor under the test above, so neither "matches everything" nor "matches nothing" can
    pass as a clean tree.

    WHAT IT CANNOT READ IS A CLASS, not a case, and naming the narrow version of it was a finding
    against the first cut of this file. The reader is an ENUMERATION of cadence adverbs; a period
    written any other way is invisible to it -- as a count of days ("every seven days"), as a
    weekday ("on Mondays", "runs each Monday morning"), as a paraphrase ("runs once a week"), as a
    duration token ("cadence: 7d"), or with a German inflection (`wöchentliche`). Every form
    named here was measured quiet against `weekly` firing (`_round-scratch/TSK-0118/probe_h141.py`), and the
    entry that carries the chain and the judgement is `H141` in `docs/POST_V2_WISHLIST.md`. The
    last two rows below are the other end: prose that must NOT fire.
    """
    assert bool(_CADENCE_IN_PROSE.search(text)) is fires, text


def test_the_workshop_tool_carries_no_predicate_of_its_own():
    """One predicate, one place -- decided in the TSK-0120 merge round and measured here.

    Generation 3 produced TWO readers of "do two orders own a common file": this tool (stream D)
    and `kernel.scopes` behind `harness.py check-scopes` (stream C). They agreed on the predicate
    and disagreed on the INPUT -- the kernel also reads the `seam_scope` item field -- and a second
    body is a second thing to keep in step, which is the failure this whole file exists against.
    The kernel is the shipped one, so the tool kept its command line and nothing else.

    THE PARSED TREE, not the text: what makes a second spelling is a FUNCTION defined here whose
    name the kernel module also defines. Two names are the tool's own by construction and named
    with the reason -- `main` reads a command line, which the kernel verb has none of, and
    `_kernel` finds the module in either layout.
    """
    import ast as _ast
    import importlib.util
    with io.open(CHECKER, encoding="utf-8") as handle:
        tool = _ast.parse(handle.read())
    defined = {node.name for node in tool.body if isinstance(node, _ast.FunctionDef)}
    assert defined == {"main", "_kernel"}, defined

    sys.path.insert(0, os.path.join(ROOT, "team-kits"))
    from kernel import scopes
    shared = defined & {name for name in vars(scopes)
                        if callable(getattr(scopes, name, None))
                        and getattr(getattr(scopes, name), "__module__", "") == scopes.__name__}
    assert not shared, shared
    assert importlib.util.find_spec("kernel.scopes") is not None


def test_a_worktree_nobody_can_stand_in_is_refused(tmp_path):
    """The one half of `--worktree` that can be checked, and the halves that cannot -- both named.

    A lease records the checkout an order is granted for so a reader can SAY which tree it is being
    worked in. A path that is not a directory records a dispatch nobody can perform, and the
    round-1 verification measured that such a path was taken without a word.

    WHAT IS NOT CHECKED and is deliberately still granted: a tree INSIDE the repo (that is the
    ordinary single-tree case) and a second lease naming the same tree (several orders in one tree
    is normal -- what keeps them apart is the scope rule, not the tree). `H156` carries the
    remainder.
    """
    from kernel import dispatch

    repo, state, ids = orders_project(
        tmp_path, [(["src/**"], []), (["lib/**"], [])], files=["src/a.py", "lib/b.py"],
        status="READY")
    with pytest.raises(Exception, match="no directory at"):
        dispatch.create_lease(state, ids[0], worktree=str(tmp_path / "nothing-here"))
    assert state.read_item(ids[0])["status"] == "READY", "the refused order was moved anyway"

    inside = os.path.join(str(repo), "src")
    granted = dispatch.create_lease(state, ids[0], worktree=inside)
    assert os.path.normcase(granted[dispatch.WORKTREE_FIELD]) == os.path.normcase(inside)
    second = dispatch.create_lease(state, ids[1], worktree=inside)
    assert second[dispatch.WORKTREE_FIELD] == granted[dispatch.WORKTREE_FIELD], (
        "two orders in one tree are the ordinary case and stay granted")

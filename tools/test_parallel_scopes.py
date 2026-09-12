#!/usr/bin/env python3
"""The pre-dispatch scope check (`kernel.scopes`, `check-scopes`) -- DEC-0062 (1)/(2)/(5).

Every verdict here is measured on ORDERS THE KERNEL WROTE and on the command run as a PROCESS: the
question is whether a cut holds, and a cut is made of stored work orders, not of dictionaries a
test happens to build.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM_KITS = os.path.join(ROOT, "team-kits")
sys.path.insert(0, TEAM_KITS)

from conftest import approve  # noqa: E402 -- the sanctioned approval walker
from kernel import dispatch, scopes  # noqa: E402
from kernel.state import ProjectState  # noqa: E402

PR_FIELDS = {
    "title": "Checkout flow", "class": "normal", "problem": "no checkout",
    "goal": "working checkout",
    "acceptance_criteria": [{"id": "AC-1", "text": "order completes"}],
    "invariants": [], "out_of_scope": [], "priority": "high",
}


def _project(tmp_path):
    """A state directory inside a real git repository -- the tree half needs one to answer."""
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    os.makedirs(os.path.join(repo, "project_memory"), exist_ok=True)
    return repo, ProjectState(os.path.join(repo, "project_memory"))


def _order(state, root_id, allowed, forbidden=(), seam=None):
    """One work order, written THROUGH the kernel -- a hand-rolled file would measure a fixture."""
    fields = {
        "product_requirement": root_id, "derives_from": root_id, "type": "implementation",
        "assigned_role": "backend-developer", "acceptance_refs": ["AC-1"], "required_inputs": [],
        "allowed_scope": list(allowed), "forbidden_scope": list(forbidden),
        "expected_outputs": ["x"], "dependencies": [],
    }
    if seam is not None:
        fields[scopes.SEAM_FIELD] = list(seam)
    return dispatch.create_task(state, fields)


def _run(repo, *args):
    """`check-scopes` as a PROCESS on the kernel's own surface -- (rc, stdout)."""
    env = dict(os.environ, PYTHONPATH=TEAM_KITS)
    result = subprocess.run(
        [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "check-scopes",
         *args],
        cwd=repo, capture_output=True, text=True, env=env, timeout=120)
    return result.returncode, result.stdout + result.stderr


def _two_orders(tmp_path, first, second, **kwargs):
    repo, state = _project(tmp_path)
    root = state.capture("PR", dict(PR_FIELDS))
    approve(state, root["id"], "scope")
    _order(state, root["id"], first, seam=kwargs.get("seam_a"))
    _order(state, root["id"], second, seam=kwargs.get("seam_b"))
    return repo, state


def test_a_wildcard_free_entry_is_offered_as_the_directory_prefix_the_gate_reads():
    """BUG-0218's remaining class, measured by round 1 of this item's verification.

    An entry WITHOUT a wildcard is a DIRECTORY PREFIX to the gate -- it owns everything under it --
    and was a literal path to `_unify`, which can unify a literal with nothing that goes deeper. So
    every pairing of a wildcard-free entry with a glob one was blind over an empty tree. The
    verifier found it by brute force over every path up to five segments against the SHIPPED
    predicate: SIX pairs shared a real path and produced no witness at all. All six are rows here.

    THE COUNTERWEIGHTS ARE THE SECOND LIST, because offering a second reading of an entry is how a
    check starts refusing cuts that hold: a different first segment, a different tray and a sibling
    directory whose name merely starts the same way must still come back empty -- `in_scope` with
    the gate's own predicate is what decides that, and the second reading only ever proposes.
    """
    matches, _norm, _gate = scopes._shipped_halves()

    def shared(left, right):
        found = scopes.overlaps(matches, [
            {"id": "TSK-0001", "allowed": [left], "forbidden": [], "seam": []},
            {"id": "TSK-0002", "allowed": [right], "forbidden": [], "seam": []}], [])
        return found[0]["witnesses"] if found else []

    for left, right in (("a/b", "a/**/c"), ("a/b", "a/*/c"), ("a/b", "a/**/*.py"),
                        ("a/b", "**/c"), ("a", "**/c"), ("a", "*/c")):
        assert shared(left, right), (left, right)

    for left, right in (("a/b", "x/**/c"), ("docs", "src/**"), ("a/b", "a/b2/**")):
        assert shared(left, right) == [], (left, right)

    assert scopes._readings(["a/b"]) == ["a/b", "a/b/**"]
    assert scopes._readings(["a/*"]) == ["a/*"], "an entry that already globs gets no second reading"


def test_two_orders_that_share_only_a_region_no_single_witness_reaches_collide():
    """BUG-0218: the witness half filled every entry ALONE, so a shared region could be invisible.

    The measured row is `a/*x` against `a/y*`: filling each entry by itself gives `a/_x` and `a/y_`,
    neither of which the other order owns, while `a/yx` belongs to both -- so two orders were cut
    as disjoint over an empty tree and collided the moment somebody created the file. The builder
    now works on the PAIR, so the character a wildcard stands for is chosen by the other pattern
    wherever that one is literal.

    THE COUNTERWEIGHTS ARE THE POINT OF THE SECOND LIST, because a builder that returned a path for
    every pair would report every cut as colliding: a different first segment, a different file
    name, and above all the separator -- `*` and `?` do not cross one, so `a/*` and `a/b/c` share
    nothing. What this builder produces is only ever a CANDIDATE; `in_scope` decides with the
    gate's own predicate, which is why widening it cannot invent an overlap.
    """
    for left, right, expected in (
            ("a/*x", "a/y*", "a/yx"),
            ("src/**", "src/kernel/x.py", "src/kernel/x.py"),
            ("tools/test_*.py", "tools/*_hooks.py", "tools/test_hooks.py"),
            ("team-kits/kernel/**", "team-kits/*/VERSION", "team-kits/kernel/VERSION"),
            ("a/*/c", "a/b/*", "a/b/c"),
            ("**/x.py", "src/deep/x.py", "src/deep/x.py")):
        assert scopes._unify(scopes._tokens(left), scopes._tokens(right), 0, 0, {}) == expected, (
            left, right)
    for left, right in (("a/*x", "b/y*"), ("tools/test_*.py", "docs/*.md"),
                        ("a/b.py", "a/c.py"), ("a/*", "a/b/c")):
        assert scopes._unify(scopes._tokens(left), scopes._tokens(right), 0, 0, {}) is None, (
            left, right)

    first = {"id": "TSK-0001", "allowed": ["a/*x"], "forbidden": [], "seam": []}
    second = {"id": "TSK-0002", "allowed": ["a/y*"], "forbidden": [], "seam": []}
    matches, _norm, _gate = scopes._shipped_halves()
    found = scopes.overlaps(matches, [first, second], [])
    assert len(found) == 1 and found[0]["witnesses"] == ["a/yx"], found


def test_a_named_route_that_cannot_be_a_pair_is_a_usage_answer_and_not_a_clean_cut(tmp_path):
    """BUG-0225: `--only` with one real id resolved, compared nothing, and answered 0.

    `--only` is a request for a COMPARISON, so an answer of 0 tells a script the cut was checked
    when nothing was. It is rc 1 -- a usage answer, which the three exit codes already tell apart
    from the refused cut's rc 2.

    THE COUNTERWEIGHT IS THE RUN NOBODY NARROWED, in this same test: a state directory with one
    open order and no `--only` stays rc 0 with NOTHING WAS COMPARED, because that run asked for
    nothing -- making "fewer than two orders" an error outright would break the tool being run with
    no arguments outside a project.
    """
    root = tmp_path / "project_memory"
    root.mkdir()
    st = ProjectState(str(root))

    code, lines = scopes.check(st)
    assert code == 0 and "NOTHING WAS COMPARED" in lines[0], lines

    code, lines = scopes.check(st, only=["TSK-0001"])
    assert code == 1, lines
    assert "NOTHING WAS COMPARED" in lines[0] and "TSK-0001" in lines[0], lines
    assert "disjoint" not in " ".join(lines), lines


def test_two_spellings_of_one_seam_are_named_as_such_and_not_as_a_collision(tmp_path):
    """BUG-0231, second residue: `pair_seam` intersects STRINGS while the gate compares file sets.

    Two entries that denote the same paths in different words leave the intersection empty, so the
    pair was refused with the ordinary OVERLAP message -- fail-closed, and a worse answer: the
    caller reads "these two collide" where the truth is "you spelled one seam twice". The verdict
    is unchanged on purpose; what changes is that every such path is named as spelled apart.

    MEASURED CORRECTION TO THE ITEM'S EXAMPLE, and it is asserted here rather than argued: against
    the SHIPPED predicate `docs/` and `docs/**` are NOT one set -- `docs/a.md` matches the second
    and not the first (probe, 2026-09-12). What they do share is the directory path itself, and
    that is the row below: `docs/` is matched by both declarations and missed by the string
    intersection, which is exactly the residue.

    The counterweight is the pair that really collides: two orders that declare NO seam at all over
    the same paths get no such line, so the hint cannot be read as "this is fine".
    """
    matches, _norm, _gate = scopes._shipped_halves()
    shared = ["docs/a.md", "docs/"]

    apart = scopes.overlaps(matches, [
        {"id": "TSK-0001", "allowed": ["docs/**"], "forbidden": [], "seam": ["docs/"]},
        {"id": "TSK-0002", "allowed": ["docs/**"], "forbidden": [], "seam": ["docs/**"]},
    ], shared)
    assert len(apart) == 1, apart
    assert apart[0]["spelled_apart"] == ["docs/"], apart
    assert "docs/" in apart[0]["files"], (
        "the verdict does not change -- the path is still counted as a collision")

    plain = scopes.overlaps(matches, [
        {"id": "TSK-0001", "allowed": ["docs/**"], "forbidden": [], "seam": []},
        {"id": "TSK-0002", "allowed": ["docs/**"], "forbidden": [], "seam": []},
    ], shared)
    assert plain[0]["spelled_apart"] == [], plain


def test_a_seam_narrower_than_the_overlap_leaves_the_rest_colliding_and_prints_what_it_covers(
        tmp_path):
    """BUG-0226: what a partial seam covers is not hidden -- it is printed path by path.

    The bound the item names is the whole of its answer, and until now nothing measured it: a seam
    is the orchestrator's DECLARATION, the merge round applies exactly the list it declares, so a
    seam is only as safe as the report is complete. Both halves here: the covered path appears as
    its own `seam` line, and the part of the overlap the declaration does NOT reach stays a
    collision with its own rc 2.
    """
    matches, _norm, _gate = scopes._shipped_halves()
    first = {"id": "TSK-0001", "allowed": ["src/**"], "forbidden": [], "seam": ["src/shared.py"]}
    second = {"id": "TSK-0002", "allowed": ["src/**"], "forbidden": [], "seam": ["src/shared.py"]}
    found = scopes.overlaps(matches, [first, second], ["src/shared.py", "src/other.py"])

    assert len(found) == 1, found
    assert found[0]["seam"] == ["src/shared.py"], found
    assert found[0]["files"] == ["src/other.py"], (
        "the part the declaration does not reach is still a collision")


def test_two_orders_with_the_same_scope_are_refused_and_disjoint_ones_are_not(tmp_path):
    """C-1, both directions in one test -- separately either half passes on a stuck check.

    RED WITHOUT THE FIX: without the command there is no `check-scopes` on the parser at all, so
    the process exits 2 with an argparse usage error and the disjoint half fails.
    """
    repo, _state = _two_orders(tmp_path, ["team-kits/kernel/**"], ["team-kits/kernel/**"])
    code, output = _run(repo)
    assert code == 2, output
    assert "OVERLAP" in output and "TSK-0001" in output and "TSK-0002" in output

    other, _state = _two_orders(tmp_path / "b", ["team-kits/kernel/**"], ["docs/**"])
    code, output = _run(other)
    assert code == 0, output
    assert "disjoint" in output


def test_an_overlap_that_exists_only_in_an_empty_directory_is_still_an_overlap(tmp_path):
    """C-1, the witness half: a stream that will CREATE the file owns nothing there today.

    The tree half alone is blind to exactly the collision that hurts most -- two orders that both
    claim a directory neither has written into yet -- so this plants a scope no file matches and
    asserts the refusal anyway.

    RED WITHOUT THE FIX: with `witnesses` reduced to the empty list, the tree holds no file under
    `src/` at all and the pair reads as disjoint.
    """
    repo, _state = _two_orders(tmp_path, ["src/api/**"], ["src/**"])
    assert not os.path.isdir(os.path.join(repo, "src"))
    code, output = _run(repo)
    assert code == 2, output
    assert "witness" in output and "src/" in output


def test_a_declared_seam_on_both_orders_is_shared_on_purpose(tmp_path):
    """C-4: the seam lives on the ITEM, so the cut a project wrote down is the cut it is judged on.

    RED WITHOUT THE FIX (measured): with the seam not subtracted in `scopes.overlaps` the pair is
    an OVERLAP and this is rc 2. NOT what makes it red, measured rather than assumed: removing the
    field from `OPTIONAL_FIELDS["TSK"]` changes nothing here -- the kernel stores an undeclared
    field without complaint (`state.py` says so about `update_item`, and `capture` is no stricter),
    so what the contract entry buys is the DECLARATION and not a refusal. That half is held by
    `test_the_seam_field_is_declared_once_and_read_from_there`.
    """
    repo, _state = _two_orders(tmp_path, ["docs/**", "team-kits/kernel/**"],
                               ["docs/**", "tools/**"],
                               seam_a=["docs/**"], seam_b=["docs/**"])
    code, output = _run(repo)
    assert code == 0, output
    assert "seam" in output and "disjoint" in output

    # ...and the same pair without the declaration is the refusal it was
    bare, _state = _two_orders(tmp_path / "bare", ["docs/**", "team-kits/kernel/**"],
                               ["docs/**", "tools/**"])
    code, output = _run(bare)
    assert code == 2, output


def test_a_seam_only_one_of_the_two_declares_is_not_a_seam(tmp_path):
    """The fail-closed half of `scopes.pair_seam`, and the reason it is fail-closed.

    A seam is a file NO stream can own alone (DEC-0062 (5)). If one order declares `docs/**` and
    the other simply owns it, the second was cut believing the file was its own -- which is the
    surprise the seam table exists to prevent. So one-sided is not declared.

    RED WITHOUT THE FIX: with `pair_seam` taking the UNION of the two declarations, this pair reads
    as a seam and the check reports disjoint on a cut that is not.
    """
    repo, _state = _two_orders(tmp_path, ["docs/**"], ["docs/**"], seam_a=["docs/**"])
    code, output = _run(repo)
    assert code == 2, output
    assert "OVERLAP" in output


def test_a_seam_the_two_orders_spell_differently_is_still_one_seam(tmp_path):
    """N1 of rework 2: `Docs/**` and `docs/**` are one entry, so the pair has a seam.

    RED WITHOUT THE FIX: `pair_seam` intersected the two `seam_scope` lists as raw strings, so the
    declaration matched nothing and the pair came back rc 2 as an ordinary OVERLAP -- fail-closed,
    but the reader was sent to fix a collision instead of a spelling.

    THE COUNTER-ASSERTION keeps it from passing by everything becoming a seam: the same pair with
    a seam neither order declares is still refused.
    """
    seamed, _state = _two_orders(tmp_path,
                                 ["docs/**", "team-kits/kernel/**"],
                                 ["docs/**", "tools/**"],
                                 seam_a=["Docs/**"], seam_b=["docs/**"])
    code, output = _run(seamed)
    assert code == 0, output
    assert "seam only" in output and "disjoint" in output

    bare, _state = _two_orders(tmp_path / "bare",
                               ["docs/**", "team-kits/kernel/**"],
                               ["docs/**", "tools/**"])
    assert _run(bare)[0] == 2


def test_the_matcher_is_the_shipped_gates_own_and_not_a_second_spelling():
    """`kernel.scopes` asks the gate the specialists really meet -- read off the module, not the text.

    BOTH HALVES, and the second one is the measured defect: the gate never calls its predicate on
    unfolded text (`_scope_entries` folds every entry, `_repo_relative(fold=True)` folds the path),
    so asking `_matches` raw answers a different question. This asserts identity of the two FUNCTION
    OBJECTS, then a behaviour only that predicate has (a single `*` does not cross a separator while
    `**` does), then the folding itself.
    """
    matches, gate = scopes.matcher()
    assert gate.endswith(os.path.join("hooks", "gate_write_scope.py"))
    sys.path.insert(0, os.path.dirname(gate))
    import gate_write_scope
    shipped_matches, shipped_norm, _where = scopes._shipped_halves()
    assert shipped_matches is gate_write_scope._matches
    assert shipped_norm is gate_write_scope._norm
    assert matches("src/a/b.py", "src/**") and not matches("src/a/b.py", "src/*")
    assert matches("Tools/x.py", "tools/**"), "the gate folds both sides; so must this"


def test_a_case_only_difference_is_the_same_ownership_the_gate_grants(tmp_path):
    """M1 of rework 1, end to end: `Tools/**` and `tools/**` are one scope to the gate.

    RED WITHOUT THE FIX: with `matcher` handing back the raw `_matches`, this pair comes back
    `disjoint` at rc 0 -- while `gate_write_scope` lets both orders write the same file, which is
    the collision the check exists to predict.
    """
    repo, _state = _two_orders(tmp_path, ["Tools/**"], ["tools/**"])
    os.makedirs(os.path.join(repo, "tools"), exist_ok=True)
    with open(os.path.join(repo, "tools", "x.py"), "w", encoding="utf-8") as handle:
        handle.write("# a real file both orders own" + chr(10))
    code, output = _run(repo)
    assert code == 2, output
    assert "tools/x.py" in output


def test_a_seam_that_leaves_an_order_owning_nothing_is_refused(tmp_path):
    """N3 of rework 1, both ends: a declaration is a shared FILE, not a handed-over scope.

    END ONE -- `**` on both orders (or on the command line) used to turn every collision into
    "seam only" and the check reported rc 0 on a cut that is entirely shared. It is refused now,
    and the line says why rather than only that.

    END TWO -- the legitimate seam stays legitimate: an order owning the kernel and declaring
    `team-kits/*/VERSION` still owns the kernel afterwards, so that pair passes. Without this half
    the rule would be "a wide seam is forbidden", which would have refused the real generation-3
    seam.
    """
    swallowed, _state = _two_orders(tmp_path, ["team-kits/kernel/**"], ["team-kits/kernel/**"],
                                    seam_a=["**"], seam_b=["**"])
    code, output = _run(swallowed)
    assert code == 2, output
    assert "NOT A SEAM" in output and "owning nothing" in output

    flagged, _state = _two_orders(tmp_path / "flag", ["team-kits/kernel/**"],
                                  ["team-kits/kernel/**"])
    code, output = _run(flagged, "--seam", "**")
    assert code == 2, output

    real, _state = _two_orders(tmp_path / "real",
                               ["team-kits/kernel/**", "team-kits/*/VERSION"],
                               ["team-kits/dev-team/hooks/**", "team-kits/*/VERSION"],
                               seam_a=["team-kits/*/VERSION"], seam_b=["team-kits/*/VERSION"])
    code, output = _run(real)
    assert code == 0, output
    assert "seam" in output and "NOT A SEAM" not in output


def test_a_state_with_nothing_to_compare_never_says_disjoint(tmp_path):
    """Nothing measured and everything fine are different answers, and they share no word.

    A missing task tray, one open order and a mistyped `--root` all land here; reporting "disjoint"
    for any of them would be the check telling a caller its cut holds when nothing was read.
    """
    repo, state = _project(tmp_path)
    code, output = _run(repo)
    assert code == 0 and "NOTHING WAS COMPARED" in output and "disjoint" not in output

    root = state.capture("PR", dict(PR_FIELDS))
    approve(state, root["id"], "scope")
    _order(state, root["id"], ["docs/**"])
    code, output = _run(repo)
    assert code == 0 and "NOTHING WAS COMPARED" in output and "disjoint" not in output


def test_a_terminal_order_is_not_part_of_the_cut(tmp_path):
    """"Open" is `is_terminal` and not a status word: a cancelled order owns nothing any more."""
    repo, state = _project(tmp_path)
    root = state.capture("PR", dict(PR_FIELDS))
    approve(state, root["id"], "scope")
    first = _order(state, root["id"], ["team-kits/kernel/**"])
    _order(state, root["id"], ["team-kits/kernel/**"])
    assert _run(repo)[0] == 2
    state.transition(first["id"], "CANCELLED")
    code, output = _run(repo)
    assert code == 0 and "NOTHING WAS COMPARED" in output, output


def test_the_seam_field_is_frozen_with_the_rest_of_the_work_order(tmp_path):
    """C-4's consequence, asserted rather than left to be discovered.

    A seam added to a LEASED order re-decides a cut that has already been handed out, so the field
    rides in `TSK_PLAN_FIELDS` with `allowed_scope`. Declaring one later stays legitimate -- it
    just has to be visible, which is what the freeze forces.
    """
    from kernel.backlog_types import TSK_PLAN_FIELDS
    from kernel.state import StateError

    assert scopes.SEAM_FIELD in TSK_PLAN_FIELDS
    repo, state = _project(tmp_path)
    root = state.capture("PR", dict(PR_FIELDS))
    approve(state, root["id"], "scope")
    task = _order(state, root["id"], ["docs/**"])
    state.transition(task["id"], "READY")
    with pytest.raises(StateError, match="frozen outside"):
        state.update_item(task["id"], {scopes.SEAM_FIELD: ["docs/**"]})


def _mini_install(repo):
    """The two directories a scaffold puts under `.claude/` -- hooks and kernel, nothing else.

    Enough for the shipped entry point to resolve a kernel (`scripts/harness.py` refuses a project
    without an enforcement layer, which is the check this borrows rather than defeats). Built here
    rather than by running the scaffold, because the scaffold installs agents, settings and a
    constitution this test has no use for.
    """
    installed = os.path.join(repo, ".cl" "aude")
    shutil.copytree(os.path.join(TEAM_KITS, "dev-team", "hooks"),
                    os.path.join(installed, "hooks"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(TEAM_KITS, "kernel"), os.path.join(installed, "kernel"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    os.makedirs(os.path.join(repo, "scripts"), exist_ok=True)
    shutil.copyfile(
        os.path.join(TEAM_KITS, "dev-team", "templates", "repo", "scripts", "harness.py"),
        os.path.join(repo, "scripts", "harness.py"))


def test_the_verb_runs_through_the_shipped_entry_point(tmp_path):
    """C-1's own wording: the verb as a PROCESS through `scripts/harness.py`, not only through the
    kernel module.

    That entry point is the only route a project has -- a script under a skill directory is rc 2 at
    `gate_write_scope` (`H136`) -- so a verb that worked in the module and not through the shim
    would be a verb no project could run. The shim forwards argv to the kernel parser, which is
    exactly what this measures: the same two orders, the same two exit codes.
    """
    repo, state = _project(tmp_path)
    root = state.capture("PR", dict(PR_FIELDS))
    approve(state, root["id"], "scope")
    # Each order keeps something of its own outside the seam -- a declaration that left one of
    # them owning nothing is not a seam (`scopes.owns_anything_outside`).
    _order(state, root["id"], ["docs/**", "team-kits/kernel/**"], seam=["docs/**"])
    _order(state, root["id"], ["docs/**", "tools/**"])
    _mini_install(repo)

    def shim(*args):
        result = subprocess.run([sys.executable, os.path.join("scripts", "harness.py"),
                                 "check-scopes", *args],
                                cwd=repo, capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout + result.stderr

    code, output = shim()
    assert code == 2, output
    assert "OVERLAP" in output
    code, output = shim("--seam", "docs/**")
    assert code == 0, output
    assert "disjoint" in output


def test_the_check_command_is_on_the_shipped_parser():
    """The surface itself, so "the module works" cannot pass for "a project can run it"."""
    from kernel.cli import build_parser

    choices = build_parser()._subparsers._group_actions[0].choices
    assert "check-scopes" in choices
    assert json.dumps(sorted(choices)).count("check-scopes") == 1


def test_the_seam_field_is_declared_once_and_read_from_there():
    """The field name has one home, and the check reads it from there rather than spelling it.

    BOTH ENDS, because a field name in two places is the drift this repo keeps removing: the
    contract of `TSK` declares it, and `kernel.scopes.SEAM_FIELD` is that same string -- so a
    renamed field takes its reader with it instead of leaving a check that silently reads nothing.

    WHAT THIS DOES NOT CLAIM, measured: nothing refuses a work order carrying an UNDECLARED field.
    A `TSK` captured with `seam_scope` while the contract does not name it is stored and passes
    `validate_state` without a finding. So the declaration is what a reader and the flag surface
    point at, not a wall -- and the wall the seam really has is the freeze
    (`test_the_seam_field_is_frozen_with_the_rest_of_the_work_order`).
    """
    from kernel.backlog_types import OPTIONAL_FIELDS, REQUIRED_FIELDS

    assert scopes.SEAM_FIELD in OPTIONAL_FIELDS["TSK"]
    assert scopes.SEAM_FIELD not in REQUIRED_FIELDS["TSK"], (
        "most orders share nothing, so a required seam would be a field every planner types to "
        "say 'none'")

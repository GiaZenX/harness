#!/usr/bin/env python3
"""The archive door (DEC-0117): one test reference of an archived item follows a rename.

Every refusal the decision names is one test here, driven through `kernel.cli.main` -- the surface
the lead types -- over a project directory with a real archive and real test modules, so
"resolves" is asked of the same reader (`holes.citation_resolution`) the door asks.
"""
import io
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "team-kits"))

from kernel import cli, holes  # noqa: E402
from kernel.archive_door import COMMAND  # noqa: E402
from kernel.backlog_types import TEST_REF_AMENDMENTS_FIELD  # noqa: E402
from kernel.state import ProjectState, StateError  # noqa: E402

OLD = "tools/test_renamed.py::test_the_old_name"
NEW = "tools/test_renamed.py::test_the_new_name"
ARCHIVED = {
    "id": "BUG-0007",
    "title": "a closed hole",
    "related_pr": "PR-0001",
    "observed": "measured",
    "severity": "low",
    "hole_number": "H7",
    "limits": "bounded",
    "regression_tests": [OLD, "tools/test_renamed.py::test_a_neighbour"],
    "status": "VERIFIED",
    "revision": 1,
    "approval_ref": "APR-0003",
    "approved_hash": "abc",
    "created": "2026-09-01T10:00:00",
    "closed_at": "2026-09-02T10:00:00",
}


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


@pytest.fixture()
def project(tmp_path):
    state = ProjectState(str(tmp_path / "project_memory"))
    _write(os.path.join(str(tmp_path), "tools", "test_renamed.py"),
           "def test_the_new_name():\n    pass\n\n\ndef test_a_neighbour():\n    pass\n\n\n"
           "def helper_not_a_test():\n    pass\n")
    path = os.path.join(state.archive_root(), "BUG", "2026", "BUG-0007.yaml")
    _write(path, yaml.safe_dump(ARCHIVED, sort_keys=False, allow_unicode=True))
    return state, path


def _run(state, *args):
    return cli.main(["--root", state.root, COMMAND] + list(args))


def _door(state, item="BUG-0007", old=OLD, new=NEW, *extra):
    return _run(state, item, "--old", old, "--new", new, "--reason", "renamed in TSK-9",
                "--by", "harness-lead", *extra)


def _refused(capsys, rc, words):
    """rc 1 and the refusal's own words on stderr -- how `kernel.cli.main` reports a StateError."""
    assert rc == 1, rc
    err = capsys.readouterr().err
    assert words in err, err


def _read(path):
    with io.open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_the_door_corrects_one_reference_and_leaves_every_other_field_as_it_was(project, capsys):
    """DEC-0117 (1)/(3): the old node is replaced by the new one, in place, and nothing else moves
    but the audit record -- status, approval and the approval stamp included."""
    state, path = project
    assert _door(state) == 0
    after = _read(path)
    assert after["regression_tests"] == [NEW, "tools/test_renamed.py::test_a_neighbour"]
    assert {key: value for key, value in after.items()
            if key not in ("regression_tests", TEST_REF_AMENDMENTS_FIELD)} == {
        key: value for key, value in ARCHIVED.items() if key != "regression_tests"}
    assert "%s -> %s" % (OLD, NEW) in capsys.readouterr().out


def test_every_use_leaves_an_audit_record_with_who_when_old_new_and_why(project):
    """DEC-0117 (2): the record carries the five things the decision names, one per use."""
    state, path = project
    assert _door(state) == 0
    records = _read(path)[TEST_REF_AMENDMENTS_FIELD]
    assert len(records) == 1
    record = records[0]
    assert record["by"] == "harness-lead" and record["reason"] == "renamed in TSK-9"
    assert record["old"] == OLD and record["new"] == NEW
    assert record["field"] == "regression_tests" and record["at"][:2] == "20"


def test_an_item_that_is_not_archived_is_refused(project, capsys):
    """Refusal 1: the door corrects the archive; an ACTIVE item changes through `update`."""
    state, _path = project
    active = dict(ARCHIVED, id="BUG-0008")
    active.pop("closed_at")
    _write(state.active_path("BUG-0008"), yaml.safe_dump(active, sort_keys=False))
    _refused(capsys, _door(state, "BUG-0008"), "not archived")
    assert _read(state.active_path("BUG-0008"))["regression_tests"][0] == OLD


def test_a_field_that_is_not_a_test_reference_is_refused(project, capsys):
    """Refusal 5: no other field of an archived item becomes writable (DEC-0117 (3))."""
    state, path = project
    for field in ("status", "limits", "approval_ref", TEST_REF_AMENDMENTS_FIELD):
        _refused(capsys, _door(state, "BUG-0007", OLD, NEW, "--field", field),
                 "not a test-reference field")
    assert _read(path) == ARCHIVED


def test_an_old_node_the_item_does_not_name_is_refused(project, capsys):
    """Refusal 2: the door corrects a reference the item carries; it adds none."""
    state, path = project
    _refused(capsys, _door(state, old="tools/test_renamed.py::test_something_else"),
             "does not name")
    assert _read(path) == ARCHIVED


def test_an_old_node_that_still_resolves_is_refused(project, capsys):
    """Refusal 3: a working reference is not corrected -- `test_a_neighbour` exists."""
    state, path = project
    _refused(capsys, _door(state, old="tools/test_renamed.py::test_a_neighbour"),
             "still resolves")
    assert _read(path) == ARCHIVED


@pytest.mark.parametrize("new", [
    "tools/test_renamed.py::test_never_written",       # no such test
    "tools/test_renamed.py::helper_not_a_test",         # declared, but pytest would not collect it
    "test_the_new_name",                                # no file: not a node a runner takes
    "tools/test_missing.py::test_the_new_name",         # no such module
])
def test_a_new_node_that_does_not_resolve_now_is_refused(project, capsys, new):
    """Refusal 4: the new node resolves to exactly one collectable test in this checkout."""
    state, path = project
    _refused(capsys, _door(state, new=new), new)
    assert _read(path) == ARCHIVED


_FAR = "def test_far_away():\n    pass\n"


def _outside(tmp_path, folder):
    """A real test module BESIDE the checkout -- one the old door accepted (verify round 1, F2)."""
    where = tmp_path.parent / ("%s-%s" % (tmp_path.name, folder))
    _write(str(where / "test_elsewhere.py"), _FAR)
    return where


def _link_directory(link, target):
    """A directory link `link` -> `target` an unprivileged user can make: a JUNCTION on Windows
    (`mklink /J` needs no admin), a symlink elsewhere."""
    if os.name == "nt":
        import subprocess
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                              capture_output=True)  # bytes: cmd answers in the console code page
        assert done.returncode == 0, (done.stdout + done.stderr).decode("ascii", "replace")
    else:
        os.symlink(str(target), str(link), target_is_directory=True)


@pytest.mark.parametrize("shape, words", [
    ("climbs", "outside this checkout"),
    ("absolute_outside", "outside this checkout"),
    ("absolute_outside_with_a_space", "outside this checkout"),
    ("state_directory", "state directory"),
    ("absolute_inside", "write the module as the runner names it"),
    ("detour", "write the module as the runner names it"),
    ("junction_out", "outside this checkout"),
    ("junction_to_state", "state directory"),
    ("symlink_file_out", "outside this checkout"),
])
def test_a_new_node_outside_the_checkouts_test_modules_is_refused(project, capsys, tmp_path,
                                                                   shape, words):
    """F2 of verify round 1: the new node's module is a test module of THIS checkout, outside its
    state directory, spelled as the runner names it -- every other spelling of an existing test is
    refused with the reason, and the item stays as it was. Each shape names a real, declared
    `test_far_away` (or the real new test), so only the checkout rule can refuse it.

    The three link shapes are F4 of verify round 2: a path spelled inside the checkout that the file
    system leads out of it, or into the state directory -- the walk lists such a module, so only the
    resolved comparison refuses it."""
    state, path = project
    if shape == "junction_out":
        _link_directory(tmp_path / "tools" / "lnk", _outside(tmp_path, "outside"))
        new = "tools/lnk/test_elsewhere.py::test_far_away"
    elif shape == "junction_to_state":
        _write(os.path.join(state.root, "staging", "X", "test_throwaway.py"), _FAR)
        _link_directory(tmp_path / "tools" / "lnk2", os.path.join(state.root, "staging", "X"))
        new = "tools/lnk2/test_throwaway.py::test_far_away"
    elif shape == "symlink_file_out":
        target = _outside(tmp_path, "outside") / "test_elsewhere.py"
        try:
            os.symlink(str(target), str(tmp_path / "tools" / "test_linked.py"))
        except (OSError, NotImplementedError) as error:
            pytest.skip("this host refuses an unprivileged file symlink (%s); the junction shapes "
                        "measure the same resolved comparison" % error)
        new = "tools/test_linked.py::test_far_away"
    elif shape == "climbs":
        new = "../%s/test_elsewhere.py::test_far_away" % _outside(tmp_path, "outside").name
    elif shape == "absolute_outside":
        new = (_outside(tmp_path, "outside") / "test_elsewhere.py").as_posix() + "::test_far_away"
    elif shape == "absolute_outside_with_a_space":
        new = (_outside(tmp_path, "out side") / "test_elsewhere.py").as_posix() + "::test_far_away"
    elif shape == "state_directory":
        _write(os.path.join(state.root, "staging", "X", "test_throwaway.py"), _FAR)
        new = "project_memory/staging/X/test_throwaway.py::test_far_away"
    elif shape == "absolute_inside":
        new = (tmp_path / "tools" / "test_renamed.py").as_posix() + "::test_the_new_name"
    else:
        new = "tools/../tools/test_renamed.py::test_the_new_name"
    _refused(capsys, _door(state, new=new), words)
    assert _read(path) == ARCHIVED


def test_a_new_node_whose_path_carries_a_space_is_judged_as_spelled(project, tmp_path):
    """A space inside the path is kept, not removed: a real test module in a directory with a space
    is accepted, and the item names it exactly as it was typed (verify round 1, F2)."""
    state, path = project
    _write(str(tmp_path / "tools" / "with space" / "test_spaced.py"), _FAR)
    new = "tools/with space/test_spaced.py::test_far_away"
    assert _door(state, new=new) == 0
    assert _read(path)["regression_tests"][0] == new


def test_a_correction_nobody_signs_is_refused(project, capsys):
    """The audit record is the point: an empty --by or --reason writes nothing."""
    state, path = project
    _refused(capsys, _run(state, "BUG-0007", "--old", OLD, "--new", NEW, "--reason", " ",
                          "--by", "lead"), "--reason and --by")
    assert _read(path) == ARCHIVED


def test_the_audit_record_has_one_writer(project):
    """Capture and update refuse a body that carries the audit field -- history is not typed."""
    state, _path = project
    with pytest.raises(StateError, match="archive door"):
        state.capture("BUG", {"title": "t", "related_pr": "PR-0001", "observed": "o",
                              "expected": "e", "repro": "r", "severity": "low",
                              "acceptance_criteria": [{"id": "AC-1", "text": "x"}],
                              TEST_REF_AMENDMENTS_FIELD: [{"old": "a", "new": "b"}]})
    active = dict(ARCHIVED, id="BUG-0008")
    active.pop("closed_at")
    _write(state.active_path("BUG-0008"), yaml.safe_dump(active, sort_keys=False))
    with pytest.raises(StateError, match="archive door"):
        state.update_item("BUG-0008", {TEST_REF_AMENDMENTS_FIELD: [{"old": "a", "new": "b"}]})
    assert TEST_REF_AMENDMENTS_FIELD not in _read(state.active_path("BUG-0008"))


def test_the_hole_list_shows_the_correction(project):
    """DEC-0117 (2): the generated hole index names the correction in the hole's Stand cell."""
    state, _path = project
    before = [line for line in holes.render_index(state) if line.startswith("| H7 ")]
    assert before and "Testverweis" not in before[0]
    assert _door(state) == 0
    after = [line for line in holes.render_index(state) if line.startswith("| H7 ")]
    assert "VERIFIED; Testverweis korrigiert" in after[0] and "(1x)" in after[0]


def test_the_door_leaves_the_board_nothing_to_regenerate(project):
    """Why `amend_test_ref` may skip the index/board regeneration every other kernel writer owes
    (`tools/test_board.py::_WRITERS_THE_BOARD_DOES_NOT_RENDER`): the index lists active items only
    and the board shows the archive as a count per type, so the door has to rewrite the one
    archived file IN PLACE -- no second file, no move, the same counts."""
    from kernel import board
    state, path = project

    def files():
        return sorted(os.path.relpath(os.path.join(where, name), state.root)
                      for where, _dirs, names in os.walk(state.root) for name in names
                      if not name.startswith("."))

    counts, before = board.archived_counts(state), files()
    assert _door(state) == 0
    assert board.archived_counts(state) == counts
    assert files() == before

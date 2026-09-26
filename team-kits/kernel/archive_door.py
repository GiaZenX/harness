"""The archive door (DEC-0117): correct ONE test reference in an ARCHIVED item, and nothing else.

WHY A DOOR AT ALL. The archive is history and the kernel has no writer into it but `archive`
itself. A closed hole still names the test that would notice its relapse, and the test that reads
those names keeps reading the archive on purpose (DEC-0117 (4): a deleted regression test of a
closed bug has to stay visible). So a test renamed AFTER its bug was archived turns that reader red
with no way back -- measured on H138 (BUG-0221) and H155 (BUG-0237), handover 2026-09-13.
Rejected by the user with the decision: stop reading the archive, or keep alias tests under the
old names.

WHAT THE DOOR REFUSES, each one a test in `tools/test_archive_door.py`:
  * an item that is not archived -- an active item changes through `update`;
  * a field that is not a test-reference field -- status, verdict, evidence and approvals stay
    frozen (DEC-0117 (3));
  * an old node the field does not name;
  * an old node that still RESOLVES -- a working reference is not corrected, it is replaced by a
    decision, and the door is not that decision;
  * a new node whose module is no test module of THIS checkout (`_why_not_a_test_module`), or
    that does not resolve there to exactly one test the runner would collect;
  * a correction nobody signs or explains -- the audit record is the point (DEC-0117 (2)).

"RESOLVES" HAS ONE READER, `holes.citation_resolution`, the one the hole migration decides a
citation with; this module asks it and never re-derives it.
"""
from __future__ import annotations

import os

from .backlog_types import HOLE_TEST_FIELD, TEST_REF_AMENDMENTS_FIELD, field_elements, parse_id
from .state import ProjectState, StateError, _now_iso

COMMAND = "amend-archived-test-ref"

# The field that holds TEST REFERENCES -- the only field this door opens. Named through the
# contract's own constant, so a renamed field moves the door with it. ONE constant and not a tuple
# of them, because the write below goes through THIS name: a key the kernel's status-write reader
# can resolve to one string, which is how "the door writes no status" is measured rather than said
# (`tools/test_approvals_dispatch.py::test_no_direct_status_write_can_produce_a_status_an_approval_commits`).
# A second field would make that key computed again, and the reader then asks for a guard.
TEST_REFERENCE_FIELD = HOLE_TEST_FIELD


def _node(value) -> str:
    """A node as a comparison sees it: trimmed at both ends, forward slashes.

    Whitespace INSIDE stays: a directory may carry a space, and removing it answered a different
    path than the one typed (verify round 1, F2) -- such a node is judged as spelled.
    """
    return str(value or "").strip().replace("\\", "/")


def _repo_of(state: ProjectState) -> str:
    """The checkout the state directory belongs to -- where its tests live."""
    return os.path.dirname(os.path.abspath(state.root))


def _lies_under(path: str, top: str) -> bool:
    """Is `path` `top` or inside it, where the file system RESOLVES both (links, case, drive)?

    Resolved and not merely absolute: a junction or symlink spelled inside the checkout leads
    wherever it points, and the walk lists the module behind it (verify round 2, F4).
    """
    path, top = (os.path.normcase(os.path.realpath(one)) for one in (path, top))
    try:
        return os.path.commonpath([path, top]) == top
    except ValueError:  # another drive
        return False


def _why_not_a_test_module(state: ProjectState, repo: str, module: str):
    """None when `module` is a test module of this checkout, else why it is not.

    THE DEFINITION, and the only thing that decides: `module` is one of the paths
    `holes.test_modules_under(repo)` lists -- the kernel's one answer to "which files would a
    runner collect here", written as it writes them (relative to the checkout root, forward
    slashes) -- and neither the checkout nor the STATE directory is left or entered where the file
    system resolves it (`_lies_under`). A spelling that is absolute, climbs with `..` or takes a
    detour is not in that list; a spelling through a junction or symlink can be (the walk enters a
    junction and lists a linked file by its name), and is judged by where it resolves -- no spelling
    needs a rule of its own. The state directory is excluded because what lies there is the
    kernel's store and a proposal in staging, and a throwaway file is no regression test even where
    a bare `pytest` would collect it (verify round 1, F2). A throwaway file ELSEWHERE in the
    checkout is not excluded -- that remainder is BUG-0312 (H222). The branches below only NAME the
    reason for the refusal.
    `tools/test_archive_door.py::test_a_new_node_outside_the_checkouts_test_modules_is_refused`
    """
    from .holes import test_modules_under

    where = os.path.join(repo, module.replace("/", os.sep))
    if not _lies_under(where, repo):
        return "its module lies outside this checkout (%s)" % repo
    if _lies_under(where, state.root):
        return ("its module lies in the state directory %s -- a file there is a proposal or the "
                "kernel's store, not a regression test" % state.root)
    if module not in test_modules_under(repo):
        spelled = os.path.relpath(os.path.normpath(where), repo).replace(os.sep, "/")
        if spelled != module and spelled in test_modules_under(repo):
            return "write the module as the runner names it from the checkout root: %s" % spelled
        return "no test module of this checkout is %s" % module
    return None


def archived_path(state: ProjectState, item_id: str):
    """The archived file of `item_id`, or None when the archive holds none.

    Walks `archive/<TYPE>/<year>/` because `state.archive_path` needs the year and the caller has
    only the id.
    """
    item_type, _ = parse_id(item_id)
    base = os.path.join(state.archive_root(), item_type)
    if not os.path.isdir(base):
        return None
    for year in sorted(os.listdir(base)):
        candidate = os.path.join(base, year, item_id + ".yaml")
        if os.path.isfile(candidate):
            return candidate
    return None


def _collectable(node: str) -> bool:
    """Is this a `<module>::<function>` node whose function pytest's default rule collects?

    The MODULE half is `_why_not_a_test_module`'s question, not this one's.
    """
    path, _sep, name = node.partition("::")
    return bool(path) and name.startswith("test")


def amend_test_ref(state: ProjectState, item_id: str, old: str, new: str, reason: str, by: str,
                   field: str = HOLE_TEST_FIELD) -> dict:
    """Replace `old` by `new` in the archived item's `field`, record who/when/why, return the item.

    Every other field of the item is written back exactly as it was read.
    """
    from .holes import citation_resolution

    if field != TEST_REFERENCE_FIELD:
        raise StateError(
            "%s: `%s` is not a test-reference field -- the archive door opens %s and nothing "
            "else; status, verdict, evidence and approvals of an archived item stay frozen "
            "(DEC-0117 (3))." % (item_id, field, TEST_REFERENCE_FIELD))
    old_node, new_node = _node(old), _node(new)
    if not str(reason or "").strip() or not str(by or "").strip():
        raise StateError(
            "%s: a correction needs --reason and --by -- the audit record says who changed a "
            "closed item's reference and why (DEC-0117 (2))." % item_id)
    repo = _repo_of(state)
    with state.lock:
        path = archived_path(state, item_id)
        if path is None:
            active = os.path.isfile(state.active_path(item_id))
            raise StateError(
                "%s is not archived%s -- this door corrects the archive only. Remedy: %s"
                % (item_id, " (it is active)" if active else " (and not active either)",
                   "change an active item with `update`." if active else "check the id."))
        item = state._read_yaml(path)
        if not isinstance(item, dict) or item.get("id") != item_id:
            raise StateError("%s: the archived file %s does not read as that item." % (item_id, path))
        named = [_node(one) for one in field_elements(item.get(TEST_REFERENCE_FIELD))]
        if old_node not in named:
            raise StateError(
                "%s does not name %s in `%s` (it names: %s) -- the door corrects a reference the "
                "item carries, it does not add one." % (item_id, old_node, TEST_REFERENCE_FIELD,
                                                        ", ".join(named) or "nothing"))
        still = citation_resolution(repo, old_node)
        if still:
            raise StateError(
                "%s still resolves (%s) -- a reference that works is not corrected here; replacing "
                "it is a decision about the closed item, not a rename to follow." % (
                    old_node, ", ".join(still)))
        if "::" not in new_node or not _collectable(new_node):
            raise StateError(
                "%s is no node the runner would collect -- write it as `<path/test_x.py>::"
                "<test_name>` from the checkout root." % new_node)
        why = _why_not_a_test_module(state, repo, new_node.partition("::")[0])
        if why:
            raise StateError(
                "%s is refused: %s -- the door points a closed item at a regression test of THIS "
                "checkout." % (new_node, why))
        found = citation_resolution(repo, new_node)
        if found != [new_node]:
            raise StateError(
                "%s does not resolve to a test in this checkout (%s) -- the door points a closed "
                "item at a test that exists NOW." % (new_node, ", ".join(found) or "no test"))
        if new_node in named:
            raise StateError(
                "%s already names %s in `%s` -- drop nothing through this door; a duplicate is "
                "not a correction." % (item_id, new_node, TEST_REFERENCE_FIELD))
        values = [str(one) for one in field_elements(item.get(TEST_REFERENCE_FIELD))]
        values[named.index(old_node)] = new_node
        record = {"at": _now_iso(), "by": str(by).strip(), "field": TEST_REFERENCE_FIELD,
                  "old": old_node, "new": new_node, "reason": str(reason).strip()}
        amended = dict(item)
        amended[TEST_REFERENCE_FIELD] = values
        amended[TEST_REF_AMENDMENTS_FIELD] = list(item.get(TEST_REF_AMENDMENTS_FIELD) or []) + [
            record]
        state._write_yaml_atomic(path, amended)
    return amended

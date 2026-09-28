"""The integration door (DEC-0125): unite ONE goal's work branches on `integrate/<GOAL>`.

WHY A DOOR AND NOT A GATE READING. BUG-0333: `gate_git` reads every `git merge` that names a goal
as a DELIVERY of it and demands the goal's full passing verdict first, while the kit lets a goal be
built in parallel branches (DEC-0092 (2)) and says only the united tree can be judged (DEC-0063
(1)) -- a circle, measured in the field. Rejected with DEC-0125: teaching the gate the merge TARGET
(resolve `cd`/`-C`, tell a work branch from the base), because that is one more reader of command
lines -- the class DEC-0070 rule 2 names. Here the kernel runs git itself, so the question "where
does this merge land" is answered by construction: always `integrate/<GOAL>`, never the base. The
delivery merge of that branch into the base is still `gate_git`'s, unchanged.

WHICH BRANCHES ARE THE GOAL'S: a local branch whose NAME carries the goal id, in the shape
`gate_git.TARGET_RX` reads it (root type, `-`, four or more digits, word-bounded, any case). A
branch that names ANOTHER root item as well is never pulled in -- it is reported as skipped. The
lease half of DEC-0125 (1) is not built, and the reason is measured: a lease records a WORKTREE
(`dispatch.WORKTREE_FIELD`), not a branch, and the BUG-0333 forensics found a synaipse lease
carrying the MAIN checkout -- the branch standing there is the delivery base, which would then be
"the goal's".

WHAT THE DOOR PROMISES, each one a test in `tools/test_bug0333_integrate.py`: the base is never
written; a conflict leaves the integration branch where this run found it (and removes what this
run created); a branch of another goal is never merged; a branch-less goal, a non-root item, an
unclean integration worktree and a base that names a root item are refused before git moves.

WHAT IT DOES NOT DO, named: only COMMITTED work is united (a work tree's uncommitted edits are not
read); the integration branch is not refreshed from the base on reuse; two concurrent runs for the
same goal are not serialised by the kernel's lock.
"""
from __future__ import annotations

import os
import re
import subprocess

from . import presets
from .backlog_types import ROOT_TYPE_BY_KIT, parse_id
from .state import ProjectState, StateError

COMMAND = "integrate"
BRANCH_PREFIX = "integrate/"

# One git call may take this long before the door gives up on it. A merge in a large checkout is
# the slow case; a hung git (a credential prompt, a hook waiting for input) must not hang the door.
GIT_TIMEOUT = 300

# The root types, from the kernel's own map, so a kit that adds one reaches this door with it.
_ROOT_TYPES = tuple(sorted(set(ROOT_TYPE_BY_KIT.values())))

# The id shape a branch name carries -- the same shape `gate_git.TARGET_RX` builds from the hooks'
# `_root.ROOT_ITEM_TYPES` (`tools/test_bug0333_integrate.py::test_the_door_and_the_gate_read_a_branch_name_the_same_way`).
ROOT_ID_RX = re.compile(r"\b(?:%s)-\d{4,}\b" % "|".join(_ROOT_TYPES), re.IGNORECASE)


def integration_branch(goal: str) -> str:
    return BRANCH_PREFIX + goal


def _git(cwd: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True,
                                timeout=GIT_TIMEOUT, **presets.CHILD_TEXT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise StateError("`git %s` could not run: %s. Remedy: the door needs git on PATH and a "
                         "checkout; run it from the project." % (" ".join(args), exc)) from None
    if check and result.returncode != 0:
        raise StateError("`git %s` failed (exit %d): %s" % (
            " ".join(args), result.returncode, (result.stderr or result.stdout).strip()))
    return result


def _same_path(one: str, other: str) -> bool:
    """Resolved at both ends (DEC-0121 (2)), never compared as spelled."""
    return (os.path.normcase(os.path.realpath(one))
            == os.path.normcase(os.path.realpath(other)))


def _checkout_of(state: ProjectState) -> str:
    """The checkout the state directory lives in, as git names its top level."""
    here = os.path.dirname(os.path.abspath(state.root))
    return _git(here, "rev-parse", "--show-toplevel").stdout.strip()


def names_goal(branch: str, goal: str) -> bool:
    return any(match.group(0).upper() == goal for match in ROOT_ID_RX.finditer(branch))


def other_goals(branch: str, goal: str) -> list:
    return sorted({match.group(0).upper() for match in ROOT_ID_RX.finditer(branch)} - {goal})


def _require_goal(state: ProjectState, goal: str) -> str:
    goal = str(goal or "").strip().upper()
    try:
        item_type, _number = parse_id(goal)
    except ValueError as exc:
        raise StateError(str(exc)) from None
    if item_type not in _ROOT_TYPES:
        raise StateError(
            "%s is not a goal: the door unites the work branches of a ROOT item (%s). Remedy: name "
            "the goal the branches belong to." % (goal, "/".join(_ROOT_TYPES)))
    state.read_item(goal)       # raises with its own remedy when there is no active item
    return goal


def _local_branches(checkout: str) -> list:
    listed = _git(checkout, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return [line.strip() for line in listed.stdout.splitlines() if line.strip()]


def _worktrees(checkout: str) -> dict:
    """{branch: worktree path} for every worktree that has a branch checked out."""
    found, path = {}, None
    for line in _git(checkout, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
        elif line.startswith("branch refs/heads/") and path:
            found[line[len("branch refs/heads/"):].strip()] = path
    return found


def default_worktree(checkout: str, goal: str) -> str:
    """The path the door names for a goal's integration worktree: a sibling of the checkout.

    Outside the checkout on purpose: a worktree inside it would stand in the delivery base's tree
    as an untracked directory, which is the tree the field could not merge in (BUG-0333 forensics,
    section 3: a plain merge refused for untracked files in the MAIN tree).
    """
    checkout = os.path.abspath(checkout)
    return os.path.join(os.path.dirname(checkout),
                        "%s-integrate-%s" % (os.path.basename(checkout), goal))


def _base_of(checkout: str, base) -> str:
    if base:
        base = str(base).strip()
        if _git(checkout, "rev-parse", "--verify", "--quiet", "refs/heads/" + base,
                check=False).returncode != 0:
            raise StateError("`%s` is no local branch. Remedy: name the branch deliveries merge "
                             "into." % base)
        return base
    standing = _git(checkout, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not standing or standing == "HEAD":
        raise StateError("the checkout of the state directory stands on no branch, so there is no "
                         "delivery base to start from. Remedy: pass `--base <branch>`.")
    return standing


def sources_for(branches, goal: str, base: str):
    """(branches to unite, {skipped branch: reason}) -- the attribution, as one pure function."""
    target = integration_branch(goal)
    chosen, skipped = [], {}
    for branch in sorted(branches):
        if branch in (target, base) or not names_goal(branch, goal):
            continue
        others = other_goals(branch, goal)
        if others:
            skipped[branch] = "names %s as well -- whose work it carries is not decidable" % (
                ", ".join(others))
            continue
        chosen.append(branch)
    return chosen, skipped


def _unmerged_files(worktree: str) -> list:
    listed = _git(worktree, "diff", "--name-only", "--diff-filter=U", check=False).stdout
    return sorted(line.strip() for line in listed.splitlines() if line.strip())


def integrate(state: ProjectState, goal: str, base: str = None) -> dict:
    """Unite every work branch of `goal` on `integrate/<goal>`; all or nothing.

    Returns {branch, worktree, base, created, merged: [(branch, tip)], skipped: {branch: why},
    tip}. Raises StateError before git moves for every refusal the module docstring names, and
    after a failed merge with the conflicting files -- the branch then stands where it stood.
    """
    goal = _require_goal(state, goal)
    checkout = _checkout_of(state)
    base = _base_of(checkout, base)
    if ROOT_ID_RX.search(base):
        raise StateError(
            "the delivery base `%s` names a goal, so by the reading `gate_git` softens a push with it "
            "is a work branch, not the base. Remedy: pass `--base <the branch deliveries merge "
            "into>`." % base)
    target = integration_branch(goal)
    branches = _local_branches(checkout)
    sources, skipped = sources_for(branches, goal, base)
    if not sources:
        raise StateError(
            "no local branch carries %s in its name, so there is nothing to unite%s. Remedy: name "
            "each work branch of the goal after it (`feat/%s-<topic>`)."
            % (goal, (" (skipped: %s)" % "; ".join("%s -- %s" % pair for pair in skipped.items()))
                     if skipped else "", goal))

    checked_out = _worktrees(checkout)
    created = target not in branches
    if target in checked_out and _same_path(checked_out[target], checkout):
        raise StateError("`%s` is checked out in the project's own checkout; the door merges only "
                         "in a worktree of its own. Remedy: switch that checkout back to the base."
                         % target)
    made_worktree = target not in checked_out
    if made_worktree:
        worktree = default_worktree(checkout, goal)
        if os.path.exists(worktree):
            raise StateError(
                "the integration worktree the door names, %s, already exists and does not hold "
                "`%s`. Remedy: move it aside; the door does not reuse a directory it did not make."
                % (worktree, target))
        _git(checkout, *(["worktree", "add", "-b", target, worktree, base] if created
                         else ["worktree", "add", worktree, target]))
    else:
        worktree = checked_out[target]
        dirty = _git(worktree, "status", "--porcelain").stdout.strip()
        if dirty:
            raise StateError("the integration worktree %s is not clean:\n%s\nRemedy: commit or "
                             "remove what is there; the door merges only into a clean tree."
                             % (worktree, dirty))
    before = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    left = ("the branch and the worktree this run created are removed" if created else
            "`%s` is back at %s%s" % (target, before[:12], ", and the worktree this run added is "
                                      "removed" if made_worktree else ""))

    merged = []
    try:
        for branch in sources:
            result = _git(worktree, "merge", "--no-ff", "--no-edit", "-m",
                          "integrate(%s): %s" % (goal, branch), "refs/heads/" + branch,
                          check=False)
            if result.returncode != 0:
                conflicts = _unmerged_files(worktree)
                raise StateError(
                    "uniting `%s` into `%s` stopped%s. Nothing of this run is left behind: %s. "
                    "Remedy: resolve the conflict in the work branches (or merge one forward into "
                    "the other), then run the door again.\n%s"
                    % (branch, target,
                       " on a conflict in: %s" % ", ".join(conflicts) if conflicts else "",
                       left, (result.stderr or result.stdout).strip()))
            merged.append((branch, _git(checkout, "rev-parse",
                                        "refs/heads/" + branch).stdout.strip()))
        tip = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    except BaseException:
        _undo(checkout, worktree, target, before, created, made_worktree)
        raise
    return {"branch": target, "worktree": worktree, "base": base, "created": created,
            "merged": merged, "skipped": skipped, "tip": tip}


def _undo(checkout: str, worktree: str, target: str, before: str, created: bool,
          made_worktree: bool) -> None:
    """Leave nothing half-merged: abort, reset to this run's start, drop what this run made."""
    _git(worktree, "merge", "--abort", check=False)
    _git(worktree, "reset", "--hard", before, check=False)
    if made_worktree:
        _git(checkout, "worktree", "remove", "--force", worktree, check=False)
    if created:
        _git(checkout, "branch", "-D", target, check=False)
